"""A day read again from the recorders' own recordings, into the seat notes.

Shamroze, 25 Nov 2026: "purani videos utha ke employees ki productivity
behtar karo". The loop writes where each counted person was, pass by pass
(seats/<date>.csv); a desk's day is read off those notes. Where the loop
was not watching -- 23 Nov the laptop slept 12:05-19:01 -- every desk's
day has a hole, and where it watched a far desk badly, a sitter is missed.
The recorders keep the recording. This reads a frame of each camera every
few minutes from it (playback, read only: no setting is touched, one try
at a login), counts the people exactly as the loop does (room_loop.detect:
the room's bar, zoom, zones), and writes

    seats/replay/<date>.csv          notes in the loop's own format
    seats/replay/<date>_passes.csv   start, end, camera: one camera's pass

progress_data reads both beside the loop's own; a replayed pass is that
camera's only, so a desk on another camera is not called away in it.

    python replay_day.py 2026-11-23 12:00 19:00              the loop's gaps
    python replay_day.py 2026-11-24 10:00 19:00 --cameras nvr4:23,nvr4:25 --all

Only 140-H's recorders, never a room in its private hours, and a camera's
picture is never kept: numbers only (seats/ is git-ignored).
"""
import argparse
import csv
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import quote

CAMPUS = ("nvr1", "nvr4", "dvr2", "xvr3")
EVERY_MIN = 5
GAP_MIN = 3              # a loop pass this near a moment: the loop saw it
PER_RECORDER = 2         # playback sessions open at once on one recorder
OUT = os.path.join("seats", "replay")


def playback_url(rec, ch, when, user, password):
    """The recording of one channel from `when` (Karachi time), RTSP."""
    if rec.get("brand", "hikvision") == "hikvision":
        return ("rtsp://%s:%s@%s:554/Streaming/tracks/%d01?starttime=%s"
                % (quote(user, safe=""), quote(password, safe=""), rec["host"],
                   int(ch), when.strftime("%Y%m%dT%H%M%SZ")))
    end = when + timedelta(seconds=30)
    return ("rtsp://%s:%s@%s:554/cam/playback?channel=%d&subtype=0"
            "&starttime=%s&endtime=%s"
            % (quote(user, safe=""), quote(password, safe=""), rec["host"],
               int(ch), when.strftime("%Y_%m_%d_%H_%M_%S"),
               end.strftime("%Y_%m_%d_%H_%M_%S")))


def moments(day, start, end, every=EVERY_MIN):
    """The moments to read, every `every` minutes from start to end."""
    t = datetime.strptime("%s %s" % (day, start), "%Y-%m-%d %H:%M")
    stop = datetime.strptime("%s %s" % (day, end), "%Y-%m-%d %H:%M")
    out = []
    while t <= stop:
        out.append(t)
        t += timedelta(minutes=every)
    return out


def unwatched(moments_, loop_ends, gap=GAP_MIN):
    """The moments no loop pass came near (the loop's gaps)."""
    import bisect
    ends = sorted(loop_ends)
    out = []
    for t in moments_:
        i = bisect.bisect_left(ends, t)
        near = [abs((ends[j] - t).total_seconds()) for j in (i - 1, i)
                if 0 <= j < len(ends)]
        if not near or min(near) > gap * 60:
            out.append(t)
    return out


def note_rows(when, room, key, boxes, shape):
    """The loop's seat-note rows (room_loop.note_seats) for one picture."""
    out = []
    for b in boxes:
        x1, y1, x2, y2 = (float(v) for v in b[:4])
        out.append([when.strftime("%H:%M:%S"), room, key[0], int(key[1]),
                    "%.0f" % ((x1 + x2) / 2), "%.0f" % ((y1 + y2) / 2),
                    "%.0f" % (x2 - x1), "%.0f" % (y2 - y1),
                    "%.2f" % (float(b[4]) if len(b) > 4 else 0.0),
                    shape[1], shape[0]])
    return out


def append(day, notes, passes, folder=OUT):
    """Add a camera's notes and its passes to the day's replay files."""
    os.makedirs(folder, exist_ok=True)
    npath = os.path.join(folder, "%s.csv" % day)
    new = not os.path.exists(npath)
    with open(npath, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["time", "room", "recorder", "channel", "cx", "cy",
                        "w", "h", "score", "frame_w", "frame_h"])
        w.writerows(notes)
    ppath = os.path.join(folder, "%s_passes.csv" % day)
    new = not os.path.exists(ppath)
    with open(ppath, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["start", "end", "camera"])
        w.writerows(passes)


def done_before(day, folder=OUT):
    """{(camera, "HH:MM:SS")} already replayed (so a rerun goes on)."""
    ppath = os.path.join(folder, "%s_passes.csv" % day)
    if not os.path.exists(ppath):
        return set()
    with open(ppath, encoding="utf-8") as fh:
        return {(r["camera"], r["end"][-8:]) for r in csv.DictReader(fh)}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("day")
    ap.add_argument("start", help="HH:MM")
    ap.add_argument("end", help="HH:MM")
    ap.add_argument("--every", type=int, default=EVERY_MIN)
    ap.add_argument("--cameras", help="rec:ch,... (default: every camera of "
                    "140-H's rooms whose desks are watched)")
    ap.add_argument("--all", action="store_true",
                    help="every moment, not only the loop's gaps")
    args = ap.parse_args(argv[1:])

    from dotenv import load_dotenv
    load_dotenv()
    import cv2
    from ultralytics import YOLO

    import progress_data as pdx
    import room_loop as rl
    from privacy_blur import DETECTOR

    import yaml
    hours = yaml.safe_load(open("rooms.yaml", encoding="utf-8")).get("hours")
    recorders, rooms = rl.load_rooms("rooms.yaml", list(CAMPUS), None)
    by_key = {}
    for room in rooms:
        for key in room.cameras:
            if key[0] in CAMPUS:
                by_key.setdefault((key[0], int(key[1])), room)
    if args.cameras:
        wanted = [(c.split(":")[0], int(c.split(":")[1]))
                  for c in args.cameras.split(",")]
    else:
        # the cameras with desks on them, and the rooms people go to
        wanted = sorted(k for k, r in by_key.items()
                        if pdx.place_of(r.name) in ("office", "meeting",
                                                    "own room"))
    wanted = [k for k in wanted if k in by_key]
    times = moments(args.day, args.start, args.end, args.every)
    if not args.all:
        p = pdx.passes(args.day)
        loop = list(p.loc[p["camera"].isna(), "end"]) if len(p) else []
        times = unwatched(times, loop)
    print(">> %d moment(s) x %d camera(s)" % (len(times), len(wanted)))
    if not times or not wanted:
        return 0
    logins, refused = {}, set()
    for rec in {k[0] for k in wanted}:
        try:
            logins[rec] = rl.recorder_login(rec, recorders[rec])
        except SystemExit:
            refused.add(rec)
    model = YOLO(DETECTOR)
    lock = threading.Lock()
    gates = {rec: threading.Semaphore(PER_RECORDER) for rec in logins}
    seen = done_before(args.day)
    todo = [(t, k) for t in times for k in wanted
            if ("%s:%d" % k, t.strftime("%H:%M:%S")) not in seen]
    frames = {}

    def grab(t, key):
        rec = recorders[key[0]]
        user, password = logins[key[0]]
        with gates[key[0]]:
            cap = cv2.VideoCapture(playback_url(rec, key[1], t, user,
                                                password), cv2.CAP_FFMPEG)
            opened = cap.isOpened()
            frame, t0 = None, time.time()
            while opened and time.time() - t0 < 12:
                ok, f = cap.read()
                if ok and f is not None:
                    frame = f
                    break
            cap.release()
        if not opened:
            with lock:
                refused.add(key[0])       # one refusal: leave it be
        return rl.widen(frame) if frame is not None else None

    written = 0
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        for t in times:
            batch = [k for k in wanted if k[0] not in refused
                     and ("%s:%d" % k, t.strftime("%H:%M:%S")) not in seen]
            room_of = {k: by_key[k] for k in batch}
            # never a room in its private hours, at the moment replayed
            batch = [k for k in batch
                     if not rl.is_private(getattr(room_of[k], "private", None),
                                          t.replace(tzinfo=rl.PKT))]
            jobs = {k: pool.submit(grab, t, k) for k in batch}
            notes, passes = [], []
            # the bar the loop would have used at that hour (night/day)
            after = not rl.in_operations(t.replace(tzinfo=rl.PKT), hours)
            for k, job in jobs.items():
                frame = job.result()
                if frame is None:
                    continue
                room = room_of[k]
                boxes = rl.detect(frame, model, room, k,
                                  conf=room.conf_for(after, k),
                                  imgsz=rl.DETECT_SIZE, iou=rl.DETECT_IOU,
                                  after_hours=after)
                counted = [b for b in boxes if not rl.ignored(
                    b, room.ignore.get(k), getattr(room, "keep", {}).get(k))]
                notes += note_rows(t, room.name, k, counted, frame.shape)
                passes.append([(t - timedelta(minutes=args.every))
                               .strftime("%Y-%m-%d %H:%M:%S"),
                               t.strftime("%Y-%m-%d %H:%M:%S"), "%s:%d" % k])
            append(args.day, notes, passes)
            written += len(passes)
            print(">> %s: %d camera(s), %d people" % (t.strftime("%H:%M"),
                                                      len(passes), len(notes)),
                  flush=True)
    print(">> replay done: %d camera-moments%s" % (
        written, ("; left alone (refused): %s" % sorted(refused))
        if refused else ""))
    return written


if __name__ == "__main__":
    main(sys.argv)
