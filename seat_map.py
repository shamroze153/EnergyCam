"""Where people sit, camera by camera, from the loop's seat notes.

Shamroze, 12 Nov: "see where people sit, so we know they sit here and
here". The loop writes every counted person's place in the picture to
seats/<date>.csv (numbers only). This turns a day of them into:

  * seats per camera -- spots where somebody was seen in many passes,
    which is a seat (or a desk somebody works at), not a person walking by;
  * a picture per camera with those seats drawn on a frame taken now, in
    frames/seats/ (this machine only; frames/ is git-ignored);
  * seats.txt, room by room: how many seats were used and how busy each.

    python seat_map.py                 # yesterday and today, working hours
    python seat_map.py --day 2026-11-13 --hours 10-20
    python seat_map.py --no-pictures   # the text only, no camera opened

A camera in its private hours (the 141 gym, 15:00-20:00) is not opened:
room_loop.fetch refuses, and its room is left out of the pictures.
"""
import argparse
import glob
import os
from datetime import datetime, timedelta

import pandas as pd

SEAT_RADIUS = 0.035     # of the frame's width: one seat, give or take
MIN_SHARE = 0.15        # seen in this share of the passes or more


def passes_in(days, hours, path="cycles.csv"):
    """How many passes the loop made in those hours: the denominator."""
    if not os.path.exists(path):
        return None
    c = pd.read_csv(path)
    when = pd.to_datetime(c["time"])
    keep = when.dt.strftime("%Y-%m-%d").isin(days) \
        & (when.dt.hour >= hours[0]) & (when.dt.hour < hours[1])
    return int(keep.sum()) or None


def load(days, hours, folder="seats"):
    """The day(s)' notes inside the hours, one row a person a pass."""
    frames = []
    for day in days:
        path = os.path.join(folder, "%s.csv" % day)
        if os.path.exists(path):
            d = pd.read_csv(path)
            d["day"] = day
            frames.append(d)
    if not frames:
        return pd.DataFrame()
    s = pd.concat(frames, ignore_index=True)
    hour = s["time"].str[:2].astype(int)
    return s[(hour >= hours[0]) & (hour < hours[1])].copy()


def seats(notes, radius=SEAT_RADIUS, min_share=MIN_SHARE, passes=None):
    """Spots people stayed at: greedy clusters of the box bottoms.

    The bottom of a box is where somebody is (their seat or their feet),
    where its middle is half way up their back. passes: the loop's passes
    in the hours (the share's denominator); without it, the passes in
    which this camera saw anybody. Returns per camera a list of
    (x, y, passes held, share) in the camera's own pixels, busiest first.
    """
    out = {}
    if notes.empty:
        return out
    for (room, rec, ch), d in notes.groupby(["room", "recorder", "channel"]):
        width = float(d["frame_w"].iloc[0]) or 1.0
        r = radius * width
        total = passes or d[["day", "time"]].drop_duplicates().shape[0] or 1
        pts = list(zip(d["cx"], d["cy"] + d["h"] / 2.0,
                       d["day"] + d["time"]))
        found = []
        for x, y, when in sorted(pts, key=lambda p: p[1]):
            for spot in found:
                if (spot["x"] - x) ** 2 + (spot["y"] - y) ** 2 <= r * r:
                    spot["seen"].add(when)
                    spot["xs"].append(x)
                    spot["ys"].append(y)
                    break
            else:
                found.append({"x": x, "y": y, "seen": {when}, "xs": [x],
                              "ys": [y]})
        keep = []
        for spot in found:
            share = min(1.0, len(spot["seen"]) / float(total))
            if share >= min_share:
                keep.append((sum(spot["xs"]) / len(spot["xs"]),
                             sum(spot["ys"]) / len(spot["ys"]),
                             len(spot["seen"]), share))
        keep.sort(key=lambda s: -s[2])
        out[(room, rec, int(ch))] = keep
    return out


def report(found):
    """Room by room: how many seats, and how much of the day each held."""
    rooms = {}
    for (room, rec, ch), spots in found.items():
        rooms.setdefault(room, []).extend(spots)
    lines = []
    for room in sorted(rooms, key=lambda n: -len(rooms[n])):
        spots = sorted(rooms[room], key=lambda s: -s[3])
        lines.append("%-34s %2d seat%s used  %s" % (
            room[:34], len(spots), "" if len(spots) == 1 else "s",
            "  ".join("%.0f%%" % (100 * s[3]) for s in spots[:8])))
    return "\n".join(lines)


def draw(found, out_dir=os.path.join("frames", "seats")):
    """Each camera's seats on a frame taken now: a circle a seat, bigger
    and brighter the more of the day it was held."""
    import cv2
    from dotenv import load_dotenv

    import room_loop
    load_dotenv()
    recorders, rooms = room_loop.load_rooms("rooms.yaml")
    by_name = {r.name: r for r in rooms}
    for key in {rec for r in rooms for rec, _ in r.cameras}:
        u, p = room_loop.recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = u, p
    room_loop.set_gates(recorders)
    os.makedirs(out_dir, exist_ok=True)
    made = 0
    for (name, rec, ch), spots in found.items():
        room = by_name.get(name)
        if room is None or not spots:
            continue
        frames = room_loop.fetch(room, recorders, 8.0)   # {} if private
        frame = frames.get((rec, ch))
        if frame is None:
            continue
        for x, y, n, share in spots:
            radius = int(8 + 22 * min(1.0, share))
            colour = (40, 40, 230) if share >= 0.5 else (
                (0, 160, 245) if share >= 0.25 else (60, 200, 90))
            cv2.circle(frame, (int(x), int(y)), radius, colour, 3)
            cv2.putText(frame, "%.0f%%" % (100 * share),
                        (int(x) + radius + 3, int(y) + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
        safe = "".join(c if c.isalnum() else "_" for c in name)
        cv2.imwrite(os.path.join(out_dir, "%s_%s_ch%02d.jpg"
                                 % (safe, rec, ch)), frame)
        made += 1
    return made


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    yday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--day", action="append",
                    help="a date, repeatable (default yesterday and today)")
    ap.add_argument("--hours", default="10-20",
                    help="the hours to count, Karachi clock (default 10-20)")
    ap.add_argument("--no-pictures", action="store_true")
    args = ap.parse_args()
    days = args.day or [yday, today]
    a, b = (int(v) for v in args.hours.split("-"))
    notes = load(days, (a, b))
    found = seats(notes, passes=passes_in(days, (a, b)))
    text = report(found)
    with open("seats.txt", "w", encoding="utf-8") as fh:
        fh.write("Seats used, %s, %02d:00-%02d:00\n\n%s\n"
                 % (", ".join(days), a, b, text))
    print(text or "no seat notes in those hours yet")
    if not args.no_pictures and found:
        print(">> %d seat map(s) in frames/seats/" % draw(found))


if __name__ == "__main__":
    main()
