"""Does the dashboard match the room right now? Look, and say where it does not.

audit.py reads the record back and finds patterns in it. This asks the
other question, the one a person standing in the building would ask: the
page says this room is empty -- is it?

It grabs a live frame from every camera, counts people with the same
detector and the same settings the loop uses, and puts that beside what the
database currently holds. Where the two disagree it writes the picture out
with the boxes drawn on, so the disagreement can be settled by looking
rather than argued about.

    python verify_live.py                  every room
    python verify_live.py --room "Admin Room"
    python verify_live.py --zone Offices
    python verify_live.py --pictures all   keep a picture of every room

The loop can keep running. This opens its own streams and writes nothing to
the database.

Two kinds of disagreement, and they are not equally serious:

  MISSED   the page says empty, the camera can see somebody. This is the
           one that matters. It is what makes the system ask for the
           cooling to be switched off in a room with people in it, and it
           raises nothing else, so nobody ever looks at that room.

  GHOST    the page says occupied, the camera can see nobody. Noise, and
           money counted against a room that was not being used. Usually a
           poster, a coat, a screen or a reflection, and rooms.yaml takes
           an ignore zone for it.

A count that is one or two different is usually neither: the database holds
the last cycle, which can be a couple of minutes old, and people move. The
age of each reading is printed so that can be judged rather than guessed.

Pictures have faces in them and are not blurred. They stay on this machine.
"""
import argparse
import os
import sys
from datetime import datetime

import cv2
import psycopg2
from dotenv import load_dotenv

from check_room import OUT_DIR, draw
from room_loop import (DETECT_IOU, DETECT_SIZE, fetch, ignored, load_rooms,
                       recorder_login, set_gates)
from privacy_blur import people_boxes
from schedule import PKT

VERIFY_DIR = os.path.join(OUT_DIR, "verify")


def latest_state(rooms):
    """What the dashboard is showing for each room, and how old it is."""
    load_dotenv()
    url = os.getenv("DASHBOARD_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        sys.exit("No DASHBOARD_DATABASE_URL in .env. This has to read room"
                 " history, which the camera machine's own credential"
                 " cannot do by design.")
    conn = psycopg2.connect(url, sslmode=os.getenv("DB_SSLMODE", "require"),
                            connect_timeout=15)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT ON (room) room, status, people, timestamp"
            "  FROM room_events ORDER BY room, timestamp DESC")
        return {row[0]: {"status": row[1], "people": row[2],
                         "at": row[3]} for row in cursor.fetchall()}
    finally:
        conn.close()


def count_now(room, recorders, model, timeout):
    """People the detector can see in this room right now, and the frames.

    Deliberately the same call the loop makes, with the room's own
    confidence and its ignore zones applied. A verification that counted
    differently from the thing it verifies would prove nothing.
    """
    frames = fetch(room, recorders, timeout)          # already widened
    most, answered, drawn = 0, 0, []
    for key, frame in frames.items():
        if frame is None:
            continue
        answered += 1
        boxes = people_boxes(frame, model, conf=room.conf,
                             imgsz=DETECT_SIZE, iou=DETECT_IOU)
        zones = room.ignore.get(key) or []
        kept = [b for b in boxes if not ignored(b, zones)]
        # The MAXIMUM across cameras, not the sum -- which is what the loop
        # does, because two cameras watching one room see the same people
        # twice and adding them would invent a crowd. Counting differently
        # from the thing being verified would manufacture disagreements and
        # prove nothing about either.
        most = max(most, len(kept))
        drawn.append((key, draw(frame, boxes, zones), len(kept)))
    return most, answered, len(frames), drawn


def verdict(seen, answered, cameras, state):
    """What to call the difference, if it is one.

    Nobody seen proves nothing unless every camera answered -- the same
    asymmetry the loop itself runs on. A room half of whose cameras are
    down cannot contradict anything.
    """
    if answered == 0:
        return "NO CAMERA", "no camera answered; nothing can be said"
    status = (state or {}).get("status")
    if status is None:
        return "NOT RECORDED", "the loop has never written this room down"
    if status == "unknown":
        return ("RECOVERED" if answered else "SILENT",
                "the page says nobody looked; %d of %d cameras answered"
                % (answered, cameras))
    page = int((state.get("people") or 0))
    if status == "empty" and seen > 0:
        return "MISSED", ("the page says empty, %d person(s) visible"
                          % seen)
    if status == "occupied" and seen == 0 and answered == cameras:
        return "GHOST", ("the page says %d person(s), none visible on any"
                         " of %d cameras" % (page, cameras))
    if status == "occupied" and seen != page:
        return "COUNT", "the page says %d, %d visible now" % (page, seen)
    return "MATCH", ""


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms.yaml")
    ap.add_argument("--room", action="append")
    ap.add_argument("--zone")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--per-recorder", type=int, default=2,
                    help="streams open at once on one recorder (default 2,"
                         " lower than the loop's because the loop is"
                         " probably running too)")
    ap.add_argument("--pictures", choices=["disagreements", "all", "none"],
                    default="disagreements",
                    help="which rooms to write a picture for. The default"
                         " keeps the footage down: a room that agrees needs"
                         " no photograph of the people in it.")
    args = ap.parse_args()

    load_dotenv()
    recorders, rooms = load_rooms(args.config, None, args.room)
    if args.zone:
        rooms = [r for r in rooms if r.zone == args.zone]
    if not rooms:
        sys.exit("no rooms matched")

    # load_rooms reads rooms.yaml, which holds no credentials: the logins
    # live in .env and are attached here, exactly as the loop and
    # check_room.py do it. Every recorder any of these rooms has a camera
    # on, not just each room's own -- a room may be watched across two.
    for key in {rec for room in rooms for rec, _ in room.cameras}:
        if key not in recorders:
            sys.exit("rooms.yaml has a camera on recorder %r but no such"
                     " recorder" % key)
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password
    # And cap the streams per recorder. The loop is almost certainly running
    # while this does, so this is a second set of connections arriving at
    # the same four machines: without a cap they all pile onto whichever
    # recorder answers first, which is how one of them got locked out once.
    set_gates(recorders, args.per_recorder)

    state = latest_state(rooms)
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")

    now = datetime.now(PKT)
    print("Live check — %s, %d room(s)"
          % (now.strftime("%a %d %b %H:%M"), len(rooms)))
    print("=" * 74)
    print("%-26s %-16s %-10s %s" % ("ROOM", "THE PAGE SAYS", "VISIBLE",
                                    "VERDICT"))
    print("-" * 74)

    counts = {}
    for room in sorted(rooms, key=lambda r: r.name):
        seen, answered, cameras, drawn = count_now(room, recorders, model,
                                                   args.timeout)
        mine = state.get(room.name)
        label, why = verdict(seen, answered, cameras, mine)
        counts[label] = counts.get(label, 0) + 1

        if mine and mine.get("status"):
            age = (now - mine["at"].astimezone(PKT)).total_seconds() / 60
            says = "%s %s" % (mine["status"],
                              "" if mine.get("people") in (None, 0)
                              else "(%d)" % mine["people"])
            says = "%-14s" % says.strip()
            age_text = "%.0fm old" % age
        else:
            says, age_text = "%-14s" % "—", ""
        print("%-26s %s %-10s %s"
              % (room.name[:26], says,
                 "%d/%d cam" % (seen, answered) if answered else "none",
                 label))
        if why:
            print("%-26s   %s%s" % ("", why,
                                    "  [reading %s]" % age_text
                                    if age_text else ""))

        keep = (args.pictures == "all"
                or (args.pictures == "disagreements"
                    and label in ("MISSED", "GHOST", "COUNT")))
        if keep and drawn:
            os.makedirs(VERIFY_DIR, exist_ok=True)
            safe = "".join(c if c.isalnum() else "_" for c in room.name)
            for (rec, channel), canvas, kept in drawn:
                path = os.path.join(
                    VERIFY_DIR, "%s_%s_ch%02d_%s_%s.jpg"
                    % (label.lower(), safe, channel, rec,
                       now.strftime("%H%M")))
                cv2.imwrite(path, canvas)
            print("%-26s   pictures in %s" % ("", VERIFY_DIR))

    print("-" * 74)
    for label in ("MISSED", "GHOST", "COUNT", "NO CAMERA", "NOT RECORDED",
                  "RECOVERED", "SILENT", "MATCH"):
        if counts.get(label):
            print("   %-13s %d" % (label, counts[label]))

    if counts.get("MISSED"):
        print("\nMISSED is the one to fix. Open its pictures: if the people"
              "\nare in the frame and no box is on them, the detector needs"
              "\nhelp (tune_detect.py). If they are not in the frame at all,"
              "\nno setting will ever find them and the camera has to move.")
    print("\nPictures are unblurred and stay on this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
