"""One full-size picture from every camera in every room with an air conditioner.

Calibrating a unit means drawing a box round its display, and nobody can draw
that box without first seeing, at full resolution, whether the display is in
the picture at all. The scans are mostly sub-stream (640x360 and smaller), at
which a display is a few pixels across. So this asks every camera of every
room that can raise an AC check for its MAIN stream, both campuses, and saves
the frames under the room's name.

    python ac_survey.py              both campuses
    python ac_survey.py --campus 141-C/D
    python ac_survey.py --zip        and put them in one zip to send

Server rooms and anything marked alert: never are skipped: their cooling is
not going to be switched off, so their units are not worth calibrating.

These frames are NOT blurred. They are taken while people sit at their desks.
Look through them before they go anywhere.
"""
import argparse
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

if __name__ == "__main__":
    # On Windows the decoder only listens to settings it was born with.
    import quiet_start
    quiet_start.relaunch()

import cv2  # noqa: E402
import yaml  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from room_loop import muffled, recorder_login, widen  # noqa: E402
from test_camera import build_url, grab  # noqa: E402

OUT = "ac_survey"


def safe(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_")


def wanted(cfg, campus=None):
    """(room, campus, recorder, channel) for every camera worth a picture."""
    recorders = cfg["recorders"]
    out = []
    for room in cfg["rooms"]:
        if room.get("watch") is False or room.get("alert") == "never":
            continue
        if room.get("ac") not in ("visible", "hidden"):
            continue
        cams = room.get("cameras") or [{"recorder": room["recorder"],
                                        "channel": c}
                                       for c in room["channels"]]
        where = recorders[cams[0]["recorder"]].get("campus", "?")
        if campus and where != campus:
            continue
        for cam in cams:
            out.append((room, where, cam["recorder"], int(cam["channel"])))
    return out


def calibrated(path="ac_units.yaml"):
    if not os.path.exists(path):
        return {}
    data = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("rooms") or {}
    return {name: len(c.get("units") or []) for name, c in data.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campus")
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--quality", type=int, default=82,
                    help="JPEG quality (default 82: a display stays readable"
                         " and sixty frames still fit in one upload)")
    args = ap.parse_args()

    load_dotenv()
    cfg = yaml.safe_load(open("rooms.yaml", encoding="utf-8"))
    jobs = wanted(cfg, args.campus)
    if not jobs:
        sys.exit("no room with an air conditioner matches")
    done = calibrated()
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    os.makedirs(OUT, exist_ok=True)
    print(">> %d cameras in %d rooms with a unit, main stream"
          % (len(jobs), len({j[0]["name"] for j in jobs})))

    # One recorder at a time per thread, a few recorders at once: the same
    # courtesy the loop shows them, so a survey cannot knock one over.
    by_rec = {}
    for job in jobs:
        by_rec.setdefault(job[2], []).append(job)
    logins = {}
    for key in by_rec:
        try:
            logins[key] = recorder_login(key, cfg["recorders"][key])
        except SystemExit as e:
            print(">> %s: %s" % (key, e))

    from room_loop import private_cameras
    private = private_cameras()

    def walk(key):
        rec = cfg["recorders"][key]
        rows = []
        for room, where, _, ch in by_rec[key]:
            if (key, ch) in private:
                # Private hours (the 141 gym, 15:00-20:00): not opened.
                rows.append((room, where, key, ch, None, "private hours"))
                continue
            if key not in logins:
                rows.append((room, where, key, ch, None, "no login in .env"))
                continue
            user, password = logins[key]
            url = build_url(rec["host"], ch, user, password, True,
                            rec.get("brand", "hikvision"))
            frame, status = grab(url, max_seconds=args.timeout)
            if frame is None:
                rows.append((room, where, key, ch, None, status))
                continue
            frame = widen(frame)
            folder = os.path.join(OUT, safe(where))
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "%s__%s_ch%02d.jpg"
                                % (safe(room["name"]), key, ch))
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, args.quality])
            rows.append((room, where, key, ch, path,
                         "%dx%d" % (frame.shape[1], frame.shape[0])))
        return rows

    with muffled():
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = [r for rows in pool.map(walk, sorted(by_rec))
                       for r in rows]

    lines = ["# ac_survey %s -- room | campus | unit label | units | measured"
             " | recorder ch | picture" % stamp]
    for room, where, key, ch, path, status in sorted(
            results, key=lambda r: (r[1], r[0]["name"], r[2], r[3])):
        lines.append("%-34s | %-8s | %-7s | %d | %d | %s ch%-2d | %s"
                     % (room["name"], where, room["ac"],
                        int(room.get("ac_count", 1) or 1),
                        done.get(room["name"], 0), key, ch,
                        os.path.basename(path) + "  " + status if path
                        else "NONE: " + status))
    listing = os.path.join(OUT, "list.txt")
    open(listing, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    got = sum(1 for r in results if r[4])
    print("\n".join(lines[1:]))
    print(">> %d of %d cameras gave a picture -> %s/" % (got, len(results), OUT))

    if args.zip:
        name = "ac_survey_%s.zip" % stamp
        with zipfile.ZipFile(name, "w", zipfile.ZIP_STORED) as z:
            z.write(listing, "list.txt")
            for r in results:
                if r[4]:
                    z.write(r[4], os.path.relpath(r[4], OUT))
        size = os.path.getsize(name) / 1e6
        print(">> %s, %.1f MB. These pictures are NOT blurred -- look before"
              " sending." % (name, size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
