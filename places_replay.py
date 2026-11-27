"""Where people went, read again from the recordings: the faces in the
places people go, into the day's sightings.

Shamroze, 27 Nov night: every starred employee's whole day -- the cafes,
meeting rooms, prayer, smoking, the corridors, the other campus -- "purani
recording se karo, wait mat karo". The loop finds a face away from the desk
only where it reads a room at full size, and before 27 Nov 20:20 only by
SFace (40-70 sightings a day, both campuses). This reads the recorders'
own recordings (playback, read only: no setting touched, one login try a
recorder, never again after a refusal) of the places people go -- the
cafes, meeting rooms, prayer, smoking, the corridors and lobbies, and the
offices whose desks the pass reads at this size (people standing in them,
not their seated owners) -- every few minutes at full size, and hands each
picture to cctv_faces exactly as the loop does: SCRFD finds the faces,
AdaFace names them against people/ada_refs.npz at 0.45 by 0.10, the
person's seat skipped in an office. What it finds is written to

    people/sightings/replay/<day>.csv      the loop's columns (cctv_faces)
    people/sightings/replay/<day>/         a small picture of each sighting
    people/sightings/replay/<day>_done.csv the moments read (a rerun goes on)

which places_day reads beside the loop's own (the same look once). All
under people/ (git-ignored, this laptop only). Never a room in its private
hours (the 141 gym is never read at all), office hours only.

    python places_replay.py 2026-11-26 09:30 20:30
    python places_replay.py 2026-11-26 09:30 20:30 --campus 141 --streams 1
    python places_replay.py 2026-11-26 12:00 15:00 --kinds cafe,prayer

Runs beside the loop: --threads caps PyTorch's threads in THIS process (the
loop's own are never touched), and the process asks Windows for a lower
priority, so the loop's passes come first.
"""
import argparse
import csv
import os
import sys
import threading
import time
from datetime import timedelta

import replay_day as rd

CAMPUS = {"140-H": ("nvr1", "nvr4", "dvr2", "xvr3"),
          "141": ("cd_nvr1", "cd_nvr2", "cd_nvr3", "cd_nvr4", "cd_xvr1",
                  "cd_xvr3")}
KINDS = ("cafe", "meeting", "smoking", "prayer", "corridor", "office")
EVERY_MIN = 5
STREAMS = 2
OUT = os.path.join("people", "sightings", "replay")
NEVER = ("gym",)


def cameras(rooms, recorders, wants_main, kinds=KINDS, campus=None):
    """[(key, room)] to read: the rooms of the kinds people go to on these
    recorders -- an office only where the pass reads it at full size (its
    seats are in those pixels: the seated owner is left to seat_faces) --
    never the gym. wants_main(room, recorder): room_loop.wants_main."""
    import progress_data as pdx
    out, seen = [], set()
    for room in rooms:
        if any(w in str(room.name).lower() for w in NEVER):
            continue
        kind = pdx.place_of(room.name)
        kind = "office" if kind in ("office", "own room") else kind
        if kind not in kinds:
            continue
        for key in room.cameras:
            key = (key[0], int(key[1]))
            if campus is not None and key[0] not in campus:
                continue
            if key in seen or key[0] not in recorders:
                continue
            if kind == "office" and not wants_main(room, key[0]):
                continue
            seen.add(key)
            out.append((key, room))
    return out


def done_before(day, folder=OUT):
    """{(camera, HH:MM:SS)} already read (so a rerun goes on)."""
    path = os.path.join(folder, "%s_done.csv" % day)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        return {(r[1], r[0]) for r in csv.reader(fh) if len(r) >= 2}


def mark(day, rows, folder=OUT):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "%s_done.csv" % day), "a", newline="",
              encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def low_priority():
    """Ask Windows to run this process below the loop. Never raises."""
    try:
        import ctypes
        BELOW_NORMAL = 0x4000
        h = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(h, BELOW_NORMAL)
    except Exception:                                       # noqa: BLE001
        pass


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("day", help="YYYY-MM-DD, or several comma-separated")
    ap.add_argument("start", help="HH:MM")
    ap.add_argument("end", help="HH:MM")
    ap.add_argument("--every", type=int, default=EVERY_MIN)
    ap.add_argument("--campus", default="140-H", choices=sorted(CAMPUS))
    ap.add_argument("--kinds", default=",".join(KINDS))
    ap.add_argument("--streams", type=int, default=STREAMS,
                    help="playback sessions open at once (at most %d)"
                    % rd.STREAMS)
    ap.add_argument("--skip", default="",
                    help="recorders to leave alone, comma-separated")
    ap.add_argument("--ada-budget", type=float, default=40.0,
                    help="seconds of SCRFD + AdaFace a minute (the loop's "
                    "own is cctv_faces.ADA_BUDGET)")
    ap.add_argument("--threads", type=int, default=2,
                    help="PyTorch threads in this process (YOLO)")
    args = ap.parse_args(argv[1:])
    args.streams = max(1, min(rd.STREAMS, args.streams))
    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    wanted_recs = tuple(r for r in CAMPUS[args.campus] if r not in skip)

    low_priority()
    from dotenv import load_dotenv
    load_dotenv()
    import cv2
    import torch
    torch.set_num_threads(max(1, args.threads))     # this process only
    from ultralytics import YOLO

    import cctv_faces as cf
    import progress_track as pt
    import room_loop as rl
    from privacy_blur import DETECTOR
    import yaml

    cf.ADA_BUDGET = args.ada_budget
    hours = yaml.safe_load(open("rooms.yaml", encoding="utf-8")).get("hours")
    recorders, rooms = rl.load_rooms("rooms.yaml", list(wanted_recs), None)
    cams = cameras(rooms, recorders,
                   lambda room, rec: rl.wants_main(room, recorders[rec]),
                   kinds, set(wanted_recs))
    days = [d.strip() for d in args.day.split(",") if d.strip()]
    plan = [(d, rd.moments(d, args.start, args.end, args.every))
            for d in days]
    for d, times in plan:
        print(">> %s: %d moment(s) x %d camera(s) (%s)" % (
            d, len(times), len(cams), ", ".join(kinds)), flush=True)
    if not cams:
        return 0
    logins, refused = {}, set()
    for rec in sorted({k[0] for k, _ in cams}):
        try:
            logins[rec] = rl.recorder_login(rec, recorders[rec])
        except SystemExit:
            refused.add(rec)               # one try: never again this run
    model = YOLO(DETECTOR)
    lock = threading.Lock()
    gates = {rec: threading.Semaphore(rd.PER_RECORDER) for rec in logins}
    every = threading.Semaphore(args.streams)
    tried = set()

    def grab(t, key):
        rec = recorders[key[0]]
        user, password = logins[key[0]]
        with every, gates[key[0]]:
            with lock:
                if key[0] in refused:
                    return None
            cap = cv2.VideoCapture(rd.playback_url(rec, key[1], t, user,
                                                   password), cv2.CAP_FFMPEG)
            opened = cap.isOpened()
            with lock:
                (tried if opened else refused).add(key[0])
            frame, t0 = None, time.time()
            while opened and time.time() - t0 < 12:
                ok, f = cap.read()
                if ok and f is not None:
                    frame = f
                    break
            cap.release()
        return rl.widen(frame) if frame is not None else None

    found = 0
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=args.streams) as pool:
        for day, times in plan:
            seen = done_before(day)
            seats = pt.regular_seats(day)
            for t in times:
                when = t.replace(tzinfo=rl.PKT)
                batch = [(k, room) for k, room in cams
                         if k[0] not in refused
                         and ("%s:%d" % k, t.strftime("%H:%M:%S")) not in seen
                         and not rl.is_private(getattr(room, "private", None),
                                               when)]
                # a recorder not opened on yet: one camera of it first
                first = {}
                for k, room in batch:
                    if k[0] not in tried and k[0] not in first:
                        first[k[0]] = k
                got = {k: pool.submit(grab, t, k).result()
                       for k in first.values()}
                jobs = {k: pool.submit(grab, t, k) for k, _ in batch
                        if k not in got}
                after = not rl.in_operations(when, hours)
                rows, n = [], 0
                for k, room in batch:
                    frame = got[k] if k in got else jobs[k].result()
                    if frame is None:
                        continue
                    boxes = rl.detect(frame, model, room, k,
                                      conf=room.conf_for(after, k),
                                      imgsz=rl.DETECT_SIZE, iou=rl.DETECT_IOU,
                                      after_hours=after)
                    counted = [b for b in boxes if not rl.ignored(
                        b, room.ignore.get(k),
                        getattr(room, "keep", {}).get(k))]
                    n += cf.observe(room.name, k, frame, counted, now=when,
                                    spots=seats.get(k) or [], out=OUT)
                    rows.append([t.strftime("%H:%M:%S"), "%s:%d" % k])
                mark(day, rows)
                found += n
                print(">> %s %s: %d camera(s), %d sighting(s)" % (
                    day, t.strftime("%H:%M"), len(rows), n), flush=True)
    print(">> places replay done: %d sighting(s)%s" % (
        found, ("; left alone (refused): %s" % sorted(refused))
        if refused else ""))
    return found


if __name__ == "__main__":
    main(sys.argv)
