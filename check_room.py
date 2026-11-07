"""Draw what the detector thinks is a person, so a wrong count can be argued with.

A room that insists it has one person in it while nobody is there cannot be
fixed from the number alone. The number says "1". It does not say whether that
1 is a coat on a chair, a poster, a reflection in a glass door, or a real
person in a corner nobody thought to check. This grabs a live frame from each
of a room's cameras, draws every detection on it with its confidence, and
prints the lines you would paste into rooms.yaml to deal with it.

    python check_room.py --room "AutoOS"

Then open the pictures it names. Every box is drawn with the confidence that
produced it. What you do next depends on what you see:

  A box on something that is not a person, in a spot that never moves
  (a poster, a mannequin, a fire extinguisher, a chair with a jacket) --
  use the ignore zone this prints. It is tied to that one spot, so a real
  person who walks in front of it is still counted.

  Several faint boxes on clutter, all well below the real people's scores --
  use the confidence this suggests. It only applies to this room.

  A box on a real person you forgot about -- the room is right and nothing
  needs changing.

Nothing is written. This prints lines for you to paste, because a tool that
edits the room map on its own would quietly undo the survey somebody walked
the building to produce.
"""
import argparse
import os
import sys

import cv2
from dotenv import load_dotenv

from privacy_blur import DETECT_CONF, people_boxes
from room_loop import (DETECT_IOU, DETECT_SIZE, fetch, ignored, load_rooms,
                       recorder_login)

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


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms.yaml")
    ap.add_argument("--room", action="append", help="repeatable")
    ap.add_argument("--recorder", action="append", help="repeatable")
    ap.add_argument("--conf", type=float,
                    help="try this confidence instead of the room's own"
                         " (default %.2f)" % DETECT_CONF)
    ap.add_argument("--imgsz", type=int, default=DETECT_SIZE)
    ap.add_argument("--iou", type=float, default=DETECT_IOU)
    ap.add_argument("--timeout", type=float, default=6.0)
    args = ap.parse_args()

    if not args.room and not args.recorder:
        sys.exit("name a room: python check_room.py --room \"AutoOS\"\n"
                 "(--recorder dvr2 does a whole recorder, which is slow)")

    load_dotenv()
    recorders, rooms = load_rooms(args.config, args.recorder, args.room)
    for key in {r.recorder for r in rooms}:
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password

    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    os.makedirs(OUT_DIR, exist_ok=True)

    advice = []
    for room in rooms:
        conf = args.conf or room.conf
        print("\n>> %s  (recorder %s, channel%s %s)"
              % (room.name, room.recorder, "" if len(room.channels) == 1
                 else "s", ", ".join(str(c) for c in room.channels)))
        if conf:
            print("   using confidence %.2f" % conf)
        frames = fetch(room, recorders[room.recorder], args.timeout)
        for channel in room.channels:
            frame = frames.get(channel)
            if frame is None:
                print("   ch%-3d no frame came back" % channel)
                continue
            zones = room.ignore.get(channel)
            boxes = people_boxes(frame, model, conf=conf, imgsz=args.imgsz,
                                 iou=args.iou)
            counted = [b for b in boxes if not ignored(b, zones)]
            print("   ch%-3d %dx%d  %d detection(s), %d counted"
                  % (channel, frame.shape[1], frame.shape[0], len(boxes),
                     len(counted)))
            for n, (x1, y1, x2, y2, score) in enumerate(boxes, 1):
                mark = "ignored" if ignored((x1, y1, x2, y2, score), zones) \
                    else ("faint  " if score < FAINT else "counted")
                print("         %d  %s  %.2f  box %4d,%4d %4d,%4d  (%dx%d)"
                      % (n, mark, score, x1, y1, x2, y2, x2 - x1, y2 - y1))
            path = os.path.join(OUT_DIR, "%s_ch%02d_boxes.jpg"
                                % (room.name.replace(" ", "_"), channel))
            cv2.imwrite(path, draw(frame, boxes, zones))
            print("         picture: %s" % path)

            if counted:
                advice.append((room, channel, counted))

    if not advice:
        print("\n>> nothing was counted as a person in any of those rooms.")
        return

    print("\n" + "=" * 68)
    print("If any of those boxes is NOT a person, paste one of these into")
    print("rooms.yaml under that room, then restart the loop.")
    print("=" * 68)
    for room, channel, counted in advice:
        print("\n  %s, channel %d" % (room.name, channel))
        print("    # to stop counting those exact spots:")
        print("    ignore:")
        print("      %d:" % channel)
        for x1, y1, x2, y2, score in counted:
            print("        - [%d, %d, %d, %d]   # %.2f" % (x1, y1, x2, y2, score))
        faintest = min(s for *_, s in counted)
        strongest = max(s for *_, s in counted)
        if faintest < FAINT:
            # Only worth suggesting when it would actually change something
            # and there is somewhere sensible to put the line.
            print("    # or, if they are all faint and real people score"
                  " higher here:")
            print("    conf: %.2f   # faintest %.2f, strongest %.2f"
                  % (min(0.6, faintest + 0.05), faintest, strongest))
    print("\n>> A zone is the safer of the two. It is tied to one spot, so a")
    print(">> real person in front of it is still counted; a confidence")
    print(">> applies to the whole room, including the far corner where")
    print(">> somebody is half hidden behind a monitor.")


if __name__ == "__main__":
    main()
