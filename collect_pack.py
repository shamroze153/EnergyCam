"""An hour of every camera, for studying away from the building.

    python collect_pack.py                  6 rounds, 10 minutes apart
    python collect_pack.py --rounds 3 --every 5

Run it on the laptop with the loop running in the other window. Each round
takes one frame from every camera the loop watches -- the same stream the
loop reads, widened the same way -- and writes down, beside them, what the
dashboard was showing for each room at that moment. Several rounds rather
than one, because one frame of a building with people walking about in it
says very little: a chair read as a person turns up round after round, a
person walking past turns up once.

At the end it adds what the loop has recorded (the last two days of room
events and heartbeats, and cycles.csv: how long each pass took), and packs
everything into zips small enough to upload: pack_<time>_part1of3.zip and
so on. No passwords and no database address go in.

Frames are scaled to at most 1280 wide -- the detector works at 1280, so
nothing it could see is lost -- and saved at a quality that keeps an hour of
170 cameras to a few uploads.

These pictures are NOT blurred, and they show people at their desks. Look
before sending, and keep them off anything public.
"""
import argparse
import csv
import glob
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

if __name__ == "__main__":
    # On Windows the decoder only listens to settings it was born with.
    import quiet_start
    quiet_start.relaunch()

import cv2  # noqa: E402
import psycopg2  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from room_loop import (PKT, fetch, load_rooms, muffled,  # noqa: E402
                       recorder_login, set_gates)

MAX_WIDTH = 1280
QUALITY = 65
PART_MB = 24.0


def safe(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_")


def page_state():
    """What the dashboard shows for every room right now; {} if unreadable."""
    url = os.getenv("DASHBOARD_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        return {}
    try:
        conn = psycopg2.connect(url, sslmode=os.getenv("DB_SSLMODE", "require"),
                                connect_timeout=15)
    except psycopg2.Error:
        return {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT ON (room) room, status, people, timestamp"
                    "  FROM room_events ORDER BY room, timestamp DESC")
        return {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
    except psycopg2.Error:
        return {}
    finally:
        conn.close()


def export_history(folder, days=2):
    """Room events and heartbeats as CSV: counts and times, nothing else."""
    url = os.getenv("DASHBOARD_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        return ["no database URL in .env; history not exported"]
    notes = []
    try:
        conn = psycopg2.connect(url, sslmode=os.getenv("DB_SSLMODE", "require"),
                                connect_timeout=15)
    except psycopg2.Error as e:
        return ["database unreachable (%s); history not exported"
                % type(e).__name__]
    try:
        for name, sql in (
                ("room_events.csv",
                 "SELECT timestamp, recorder, room, status, people, ac_state"
                 "  FROM room_events WHERE timestamp >= now() - interval"
                 " '%d days' ORDER BY room, timestamp" % days),
                ("heartbeat.csv",
                 "SELECT timestamp FROM heartbeat WHERE timestamp >= now() -"
                 " interval '%d days' ORDER BY timestamp" % days),
                ("meter_readings.csv",
                 "SELECT meter, taken, reading, units, max_temp FROM"
                 " meter_readings ORDER BY meter, taken"),
                ("solar_daily.csv",
                 "SELECT taken, kwh FROM solar_daily ORDER BY taken")):
            try:
                cur = conn.cursor()
                cur.execute(sql)
                with open(os.path.join(folder, name), "w", newline="",
                          encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow([d[0] for d in cur.description])
                    w.writerows(cur.fetchall())
                notes.append("%s exported" % name)
            except psycopg2.Error as e:
                conn.rollback()
                notes.append("%s not exported (%s)" % (name, type(e).__name__))
    finally:
        conn.close()
    return notes


def take_round(n, rooms, recorders, timeout, folder):
    """One frame from every camera; the page's state beside each room."""
    state = page_state()
    stamp = datetime.now(PKT)
    out = os.path.join(folder, "round_%02d_%s" % (n, stamp.strftime("%H%M")))
    os.makedirs(out, exist_ok=True)
    rows = []
    with muffled():
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = {pool.submit(fetch, room, recorders, timeout): room
                    for room in rooms}
            got = {}
            for job in as_completed(jobs):
                room = jobs[job]
                try:
                    got[room.name] = job.result()
                except Exception:                           # noqa: BLE001
                    got[room.name] = {}
    for room in rooms:
        status, people, since = state.get(room.name, (None, None, None))
        for (rec, ch) in room.cameras:
            frame = got.get(room.name, {}).get((rec, ch))
            name = ""
            size = ""
            if frame is not None:
                h, w = frame.shape[:2]
                size = "%dx%d" % (w, h)
                if w > MAX_WIDTH:
                    frame = cv2.resize(frame, (MAX_WIDTH,
                                               int(h * MAX_WIDTH / float(w))),
                                       interpolation=cv2.INTER_AREA)
                name = "%s__%s_ch%02d.jpg" % (safe(room.name), rec, ch)
                cv2.imwrite(os.path.join(out, name), frame,
                            [cv2.IMWRITE_JPEG_QUALITY, QUALITY])
            rows.append([stamp.strftime("%Y-%m-%d %H:%M:%S"), room.name, rec,
                         ch, size, name, status or "", "" if people is None
                         else people, since or ""])
    with open(os.path.join(out, "index.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["taken", "room", "recorder", "channel", "sent_size",
                    "file", "page_status", "page_people", "page_since"])
        w.writerows(rows)
    shot = sum(1 for r in rows if r[5])
    print(">> round %d at %s: %d of %d cameras"
          % (n, stamp.strftime("%H:%M"), shot, len(rows)))
    return shot, len(rows)


def pack(folder, stamp):
    """Everything in the folder, in zips of at most PART_MB each."""
    files = sorted(p for p in glob.glob(os.path.join(folder, "**", "*"),
                                        recursive=True) if os.path.isfile(p))
    parts, current, size = [], [], 0.0
    for p in files:
        mb = os.path.getsize(p) / 1e6
        if current and size + mb > PART_MB:
            parts.append(current)
            current, size = [], 0.0
        current.append(p)
        size += mb
    if current:
        parts.append(current)
    names = []
    for i, chunk in enumerate(parts, 1):
        name = "pack_%s_part%dof%d.zip" % (stamp, i, len(parts))
        with zipfile.ZipFile(name, "w", zipfile.ZIP_STORED) as z:
            for p in chunk:
                z.write(p, os.path.relpath(p, folder))
        names.append((name, os.path.getsize(name) / 1e6))
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--every", type=float, default=10.0,
                    help="minutes between the starts of two rounds")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--per-recorder", type=int, default=2,
                    help="streams open at once on one recorder; the loop is"
                         " running too")
    args = ap.parse_args()

    load_dotenv()
    recorders, rooms = load_rooms("rooms.yaml")
    for key in {rec for room in rooms for rec, _ in room.cameras}:
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password
    set_gates(recorders, args.per_recorder)

    stamp = datetime.now(PKT).strftime("%Y%m%d_%H%M")
    folder = "pack_%s" % stamp
    os.makedirs(folder, exist_ok=True)
    cameras = sum(len(r.cameras) for r in rooms)
    print(">> %d rooms, %d cameras, %d rounds %g minutes apart -> %s/"
          % (len(rooms), cameras, args.rounds, args.every, folder))
    for n in range(1, args.rounds + 1):
        began = time.time()
        take_round(n, rooms, recorders, args.timeout, folder)
        if n < args.rounds:
            wait = args.every * 60 - (time.time() - began)
            if wait > 0:
                print("   next round in %d min" % round(wait / 60.0))
                time.sleep(wait)

    for note in export_history(folder):
        print(">> %s" % note)
    if os.path.exists("cycles.csv"):
        import shutil
        shutil.copy("cycles.csv", os.path.join(folder, "cycles.csv"))
        print(">> cycles.csv copied")
    names = pack(folder, stamp)
    print()
    for name, mb in names:
        print(">> %s  %.1f MB" % (name, mb))
    print(">> Send all %d part(s). These pictures are NOT blurred -- look"
          " before sending." % len(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
