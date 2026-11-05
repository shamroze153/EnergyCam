"""Capture real frames now, then try detector settings against them later.

Changing a detector setting and watching the live count move tells you very
little: the people moved too. To know whether a setting is better you need the
same picture, scored both ways, with the right answer known -- and the only
way to know the right answer is to look.

So this comes in two halves, and they are separate on purpose.

    python tune_detect.py capture          needs the recorders
    python tune_detect.py compare          needs nothing

Capture takes several frames from each room over a few minutes, while people
are in them, and writes them to tune_frames/. That is the half that needs the
cable. Compare runs every setting over those saved frames, draws the boxes it
found, and writes one folder per setting -- which can be done at a desk, a week
later, as many times as you like, on identical pictures.

Then open two folders side by side and count the people yourself. The number
printed under each setting is what it detected, not what was there; only your
own eyes supply the second number.

Options worth trying:
    --models yolov8n.pt,yolov8s.pt     s is slower and sees more
    --sizes 640,1280                   bigger finds smaller and further people
    --confs 0.25,0.4                   lower finds more, and invents more
    --ious 0.7,0.5                     lower merges two boxes on one person

Confidence and overlap are not interchangeable. Confidence decides how faint a
detection may be, so raising it to clear a duplicate box also drops the distant
half-hidden person -- an over-count traded for an under-count, which is the
wrong way round. Overlap only removes a box drawn on top of another one.

These frames have faces in them and are not blurred. Keep the folders local.
"""
import argparse
import os
import sys
import time
from datetime import datetime

os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")

import cv2  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from room_loop import PKT, load_rooms, recorder_login, widen  # noqa: E402
from test_camera import build_url, grab  # noqa: E402

FRAME_DIR = "tune_frames"
OUT_DIR = "tune_out"


def capture(args):
    load_dotenv()
    recorders, rooms = load_rooms(args.config, args.recorder, args.room)
    if not args.room:
        rooms = [r for r in rooms if r.watched_for_waste]
        print(">> no --room given, so capturing the %d room(s) that can alert"
              % len(rooms))
    for key in {r.recorder for r in rooms}:
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password

    os.makedirs(FRAME_DIR, exist_ok=True)
    saved = 0
    for round_no in range(1, args.rounds + 1):
        print(">> round %d of %d" % (round_no, args.rounds))
        for room in rooms:
            rec = recorders[room.recorder]
            want_main = rec.get("stream", "sub") == "main"
            for channel in room.channels:
                url = build_url(rec["host"], channel, rec["user"],
                                rec["password"], want_main,
                                rec.get("brand", "hikvision"))
                frame, _ = grab(url, max_seconds=args.timeout)
                if frame is None:
                    print("   %-26s ch%-3d no frame" % (room.name, channel))
                    continue
                stamp = datetime.now(PKT).strftime("%H%M%S")
                name = "%s_ch%02d_%s.jpg" % (room.name.replace(" ", "_"),
                                             channel, stamp)
                cv2.imwrite(os.path.join(FRAME_DIR, name), widen(frame))
                saved += 1
                print("   %-26s ch%-3d %s" % (room.name, channel, name))
        if round_no < args.rounds:
            print(">> waiting %ds so people have moved" % args.gap)
            time.sleep(args.gap)

    print(">> %d frame(s) in %s/" % (saved, FRAME_DIR))
    print(">> now run:  python tune_detect.py compare")
    print(">> these frames are not blurred. Keep the folder on this machine.")


def compare(args):
    frames = sorted(f for f in os.listdir(FRAME_DIR)
                    if f.lower().endswith(".jpg")) \
        if os.path.isdir(FRAME_DIR) else []
    if not frames:
        sys.exit("no frames in %s/ -- run the capture half first" % FRAME_DIR)

    from ultralytics import YOLO

    settings = [(m, int(s), float(c), float(i))
                for m in args.models.split(",")
                for s in args.sizes.split(",")
                for c in args.confs.split(",")
                for i in args.ious.split(",")]
    print(">> %d frame(s), %d setting(s)" % (len(frames), len(settings)))

    totals = {}
    for model_name, size, conf, iou in settings:
        label = "%s_sz%d_conf%s_iou%s" % (model_name.replace(".pt", ""),
                                          size, conf, iou)
        out = os.path.join(OUT_DIR, label)
        os.makedirs(out, exist_ok=True)
        model = YOLO(model_name)
        # The first inference a model does is slower than the rest: weights get
        # moved and buffers allocated on the way through. Timing that alongside
        # the real work makes the first setting compared look slow and every
        # later one look fast, which is an ordering artefact rather than a
        # difference between them -- and on a handful of frames it is most of
        # the number. So warm it up before starting the clock.
        warmup = cv2.imread(os.path.join(FRAME_DIR, frames[0]))
        model(warmup, classes=[0], conf=conf, imgsz=size, iou=iou,
              verbose=False)
        started, found = time.time(), 0
        for name in frames:
            frame = cv2.imread(os.path.join(FRAME_DIR, name))
            results = model(frame, classes=[0], conf=conf, imgsz=size,
                            iou=iou, verbose=False)
            boxes = results[0].boxes.xyxy.tolist()
            found += len(boxes)
            drawn = frame.copy()
            for x1, y1, x2, y2 in boxes:
                cv2.rectangle(drawn, (int(x1), int(y1)), (int(x2), int(y2)),
                              (0, 220, 0), 2)
            cv2.rectangle(drawn, (0, 0), (260, 34), (0, 0, 0), -1)
            cv2.putText(drawn, "%s: %d" % (label, len(boxes)), (8, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
                        cv2.LINE_AA)
            cv2.imwrite(os.path.join(out, name), drawn)
        seconds = time.time() - started
        totals[label] = (found, seconds / len(frames))
        print("   %-28s %4d detected   %.2fs per frame"
              % (label, found, seconds / len(frames)))

    print()
    print(">> folders are in %s/ -- open two side by side and count for"
          " yourself." % OUT_DIR)
    print(">> more boxes is not better on its own: a setting that finds four")
    print("   people in a room of four beats one that finds six.")
    slowest = max(totals.values(), key=lambda v: v[1])[1]
    if slowest * 48 > 55:
        print(">> note: at %.2fs per frame a 48-camera pass would take about"
              " %.0fs, before the time spent opening the streams."
              % (slowest, slowest * 48))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["capture", "compare"])
    ap.add_argument("--config", default="rooms.yaml")
    ap.add_argument("--recorder", action="append")
    ap.add_argument("--room", action="append")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--gap", type=int, default=30,
                    help="seconds between rounds (default 30)")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--models", default="yolov8n.pt,yolov8s.pt")
    ap.add_argument("--sizes", default="640,1280")
    ap.add_argument("--confs", default="0.25")
    ap.add_argument("--ious", default="0.7",
                    help="overlap allowed between two boxes; lower merges"
                         " duplicates (default 0.7)")
    args = ap.parse_args()
    (capture if args.mode == "capture" else compare)(args)


if __name__ == "__main__":
    main()
