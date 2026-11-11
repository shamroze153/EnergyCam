"""Draw what the detector thinks is a person, so a wrong count can be argued with.

A room that insists it has one person in it while nobody is there cannot be
fixed from the number alone. The number says "1". It does not say whether that
1 is a coat on a chair, a poster, a reflection in a glass door, or a real
person in a corner nobody thought to check. This grabs a live frame from each
camera, draws every detection on it with its confidence, and prints the lines
you would paste into rooms.yaml to deal with it.

One room:

    python check_room.py --room "AutoOS"

The whole site, which is the useful one -- but run it when the building is
EMPTY, late at night or at the weekend:

    python check_room.py --all --zip

Run at a quiet hour, every detection is wrong by definition. Nobody has to
judge whether a box is a real person, because there are no real people. It is
also far less of the building's footage to go anywhere: only the cameras that
saw something are saved, so a clean site produces almost no pictures at all.

The zip contains report.txt -- every detection, its score, its size and where
it sits -- and the pictures for the cameras that saw something. report.txt on
its own is often enough to settle a room: a box forty pixels wide, high on a
wall, that has not moved in a week is not a person.

These frames are NOT blurred. They are the building's cameras as they are.
Look at the zip before it goes anywhere, and if a picture shows somebody who
should not be in it, delete it and send the rest.

Nothing is written to rooms.yaml. This prints lines for you to paste, because
a tool that edited the room map on its own would quietly undo the survey
somebody walked the building to produce.
"""
import argparse
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

if __name__ == "__main__":
    # On Windows the decoder only listens to settings it was born with.
    import quiet_start
    quiet_start.relaunch()

import cv2
from dotenv import load_dotenv

from privacy_blur import DETECT_CONF, DETECTOR, people_boxes
from room_loop import (BATCH, DETECT_IOU, DETECT_SIZE, PKT, WORKERS, fetch,
                       ignored, load_rooms, recorder_login, set_gates)
from schedule import WORKING, describe, period

OUT_DIR = "frames"
GREEN = (80, 220, 90)          # counted as a person
AMBER = (0, 190, 255)          # counted, but faint enough to be worth a look
GREY = (150, 150, 150)         # already inside an ignore zone
FAINT = 0.45                   # below this, a detection is worth questioning


def draw(frame, boxes, zones):
    canvas = frame.copy()
    for zone in zones or []:
        x1, y1, x2, y2 = zone
        cv2.rectangle(canvas, (x1, y1), (x2, y2), GREY, 1)
        cv2.putText(canvas, "ignored", (x1, max(12, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, GREY, 1)
    for n, box in enumerate(boxes, 1):
        x1, y1, x2, y2, score = box
        if ignored(box, zones):
            colour = GREY
        elif score < FAINT:
            colour = AMBER
        else:
            colour = GREEN
        cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(canvas, "%d: %.2f" % (n, score), (x1, max(14, y1 - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    return canvas


def look(rooms, recorders, model, args, say):
    """Every room's cameras, with the detections drawn on.

    Fetched several at a time for the same reason the loop is: the waiting is
    almost all of it. A whole-site check that took a quarter of an hour would
    be run once and never again.
    """
    findings = []
    for i in range(0, len(rooms), BATCH):
        batch = rooms[i:i + BATCH]
        frames = {}
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(fetch, r, recorders, args.timeout): r
                    for r in batch}
            for job in as_completed(jobs):
                room = jobs[job]
                try:
                    frames[room.name] = job.result()
                except Exception as e:                  # noqa: BLE001
                    say("   %-28s could not be read (%s)" % (room.name, e))
                    frames[room.name] = {}
        for room in batch:
            conf = args.conf or room.conf_for(
                getattr(args, "after_hours", False))
            for key in room.cameras:
                frame = frames[room.name].get(key)
                if frame is None:
                    findings.append({"room": room, "camera": key,
                                     "frame": None, "boxes": [],
                                     "counted": [], "conf": conf})
                    continue
                zones = room.ignore.get(key)
                boxes = people_boxes(frame, model, conf=conf,
                                     imgsz=args.imgsz, iou=args.iou)
                findings.append({
                    "room": room, "camera": key, "frame": frame,
                    "boxes": boxes, "conf": conf,
                    "counted": [b for b in boxes if not ignored(b, zones)]})
        frames.clear()
    return findings


def zones_past_frame(zones, width, height):
    """Zones that reach past the frame they are meant for.

    A zone is pixels in one picture. 141 Reception Meeting Room's was
    measured on the 1920x1080 main stream while the loop reads that camera
    at 640x360, where it covered the room's own table and hid the people
    at it -- for a day, with nothing to show for it but a ghost elsewhere.
    A zone drawn on a bigger picture nearly always runs off the smaller one,
    so this is the cheap test that would have caught it.
    """
    return [z for z in zones or []
            if z[2] > width + 2 or z[3] > height + 2]


def describe_finding(f, say):
    room, (recorder, channel) = f["room"], f["camera"]
    if f["frame"] is None:
        say("   %-28s %-5s ch%-3d no frame came back"
            % (room.name, recorder, channel))
        return
    say("   %-28s %-5s ch%-3d %dx%d  %d detection(s), %d counted"
        % (room.name, recorder, channel, f["frame"].shape[1],
           f["frame"].shape[0], len(f["boxes"]), len(f["counted"])))
    zones = room.ignore.get(f["camera"])
    for z in zones_past_frame(zones, f["frame"].shape[1],
                              f["frame"].shape[0]):
        say("   !! zone %s reaches past this %dx%d frame: it was drawn on a"
            " picture of another size and covers the wrong place. Redraw it"
            " in this frame's pixels." % (list(z), f["frame"].shape[1],
                                          f["frame"].shape[0]))
    for n, (x1, y1, x2, y2, score) in enumerate(f["boxes"], 1):
        mark = "ignored" if ignored((x1, y1, x2, y2, score), zones) \
            else ("faint  " if score < FAINT else "counted")
        say("        %d  %s  %.2f  box %4d,%4d %4d,%4d  (%dx%d)"
            % (n, mark, score, x1, y1, x2, y2, x2 - x1, y2 - y1))


def paste_lines(findings, say):
    wrong = [f for f in findings if f["counted"]]
    if not wrong:
        return
    say("")
    say("=" * 70)
    say("If a box is NOT a person, paste one of these under that room in")
    say("rooms.yaml, then restart the loop.")
    say("=" * 70)
    for f in wrong:
        say("")
        recorder, channel = f["camera"]
        many = len({rec for rec, _ in f["room"].cameras}) > 1
        label = "%s:%d" % (recorder, channel) if many else str(channel)
        say("  %s, %s channel %d" % (f["room"].name, recorder, channel))
        say("    # stop counting those exact spots:")
        say("    ignore:")
        say("      %s:" % ('"%s"' % label if many else label))
        for x1, y1, x2, y2, score in f["counted"]:
            say("        - [%d, %d, %d, %d]   # %.2f" % (x1, y1, x2, y2, score))
        faintest = min(s for *_, s in f["counted"])
        strongest = max(s for *_, s in f["counted"])
        if faintest < FAINT:
            say("    # or, if they are all faint and real people score higher"
                " in this room:")
            say("    conf: %.2f   # faintest %.2f, strongest %.2f"
                % (min(0.6, faintest + 0.05), faintest, strongest))
    say("")
    say(">> A zone is the safer of the two. It is tied to one spot, so a real")
    say(">> person in front of it is still counted; a confidence applies to")
    say(">> the whole room, including the far corner where somebody is half")
    say(">> hidden behind a monitor.")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms.yaml")
    ap.add_argument("--room", action="append", help="repeatable")
    ap.add_argument("--recorder", action="append", help="repeatable")
    ap.add_argument("--all", action="store_true",
                    help="every room on every recorder")
    ap.add_argument("--conf", type=float,
                    help="try this confidence instead of each room's own"
                         " (default %.2f)" % DETECT_CONF)
    ap.add_argument("--imgsz", type=int, default=DETECT_SIZE)
    ap.add_argument("--iou", type=float, default=DETECT_IOU)
    ap.add_argument("--timeout", type=float, default=6.0)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--per-recorder", type=int, default=4)
    ap.add_argument("--every-camera", action="store_true",
                    help="save a picture from every camera, not only the ones"
                         " that saw somebody")
    ap.add_argument("--zip", action="store_true",
                    help="put the pictures and report.txt in one zip file")
    args = ap.parse_args()

    if not (args.room or args.recorder or args.all):
        sys.exit('name a room:   python check_room.py --room "AutoOS"\n'
                 "or the lot:    python check_room.py --all --zip\n"
                 "Run --all when the building is empty: then every detection"
                 " is wrong by definition,\nand there is nothing to judge.")

    load_dotenv()
    recorders, rooms = load_rooms(args.config,
                                  None if args.all else args.recorder,
                                  None if args.all else args.room)
    for key in {r.recorder for r in rooms}:
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password
    set_gates(recorders, args.per_recorder)

    from ultralytics import YOLO
    model = YOLO(DETECTOR)
    os.makedirs(OUT_DIR, exist_ok=True)

    now = datetime.now(PKT)
    lines = []

    def say(text=""):
        print(text)
        lines.append(text)

    say(">> %s" % now.strftime("%A %d %B %Y, %H:%M"))
    say(">> %s" % describe(now, None))
    quiet = period(now, None) != WORKING
    args.after_hours = quiet     # the bar each room is read at tonight
    if args.all and not quiet:
        say(">> NOTE: the building is inside its working hours, so some of"
            " these will be")
        say(">> real people. Run it again at night or at the weekend and"
            " every detection")
        say(">> left is a false one, with nothing to judge and far less"
            " footage saved.")
    say(">> %d room(s), %d camera(s)"
        % (len(rooms), sum(len(r.cameras) for r in rooms)))
    say("")

    findings = look(rooms, recorders, model, args, say)
    for f in findings:
        describe_finding(f, say)

    saved = []
    for f in findings:
        if f["frame"] is None:
            continue
        if not f["counted"] and not args.every_camera:
            continue
        recorder, channel = f["camera"]
        path = os.path.join(OUT_DIR, "%s_%s_ch%02d_boxes.jpg"
                            % (f["room"].name.replace(" ", "_"), recorder,
                               channel))
        cv2.imwrite(path, draw(f["frame"], f["boxes"],
                               f["room"].ignore.get(f["camera"])))
        saved.append(path)

    cameras = sum(1 for f in findings if f["frame"] is not None)
    silent = sum(1 for f in findings if f["frame"] is None)
    counted = sum(len(f["counted"]) for f in findings)
    say("")
    say(">> %d camera(s) answered, %d did not, %d person(s) counted in total"
        % (cameras, silent, counted))
    if not args.every_camera:
        say(">> pictures saved only for the cameras that saw somebody: %d"
            % len(saved))

    paste_lines(findings, say)

    report = os.path.join(OUT_DIR, "report.txt")
    with open(report, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n>> %s" % report)

    if args.zip:
        name = os.path.join(OUT_DIR, "energycam_check_%s.zip"
                            % now.strftime("%Y%m%d_%H%M"))
        with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(report, "report.txt")
            for path in saved:
                z.write(path, os.path.basename(path))
        size = os.path.getsize(name) / 1e6
        print(">> %s  (%d picture(s), %.1f MB)" % (name, len(saved), size))
        print(">> These frames are NOT blurred. Open the zip and look through")
        print(">> it before it goes anywhere; delete any picture that shows")
        print(">> somebody who should not be in it and send the rest.")
        print(">> report.txt carries no pictures and is often enough on its"
              " own.")


if __name__ == "__main__":
    main()
