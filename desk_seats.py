"""The desks of 140-H: every regular seat of an office camera.

The loop's half of desks_data.py (it needs seat_map, and so OpenCV, which
the hosted dashboard has not): find_desks() for desk_watch.py and for the
nightly build of progress/desks.csv.

    python desk_seats.py build [upto]
"""
import json
import os
from datetime import datetime

import desks_data
import progress_data as pdx

SEAT_DAYS = 5
MIN_SHARE = 0.10
HOURS = (9, 21)
# A seat found within this many pixels of a desk already numbered is that
# desk (seat_map's spots wander a few pixels from day to day).
CODE_REACH = 60


def stable_numbers(cam, spots, reg, reach=CODE_REACH):
    """Each spot's desk number on camera `cam` ("dvr2.2"), kept from day to
    day in `reg` ({cam: [[number, x, y], ...]}): the numbered desk nearest
    a spot (within `reach`, closest pairs first, one spot one desk) keeps
    its number and follows the spot; a spot with none gets the next free
    number. Numbers are never reused (24 Nov 18:00: desks had been numbered
    busiest-first, afresh each day and at every restart -- 126 of 170 were
    somewhere else than the day before, and the names and pictures given
    to a code moved with it)."""
    known = reg.setdefault(cam, [])
    pairs = sorted(((x - k[1]) ** 2 + (y - k[2]) ** 2, i, j)
                   for i, (x, y) in enumerate(spots)
                   for j, k in enumerate(known))
    num, used = {}, set()
    for d2, i, j in pairs:
        if d2 > reach * reach:
            break
        if i in num or j in used:
            continue
        num[i] = known[j][0]
        used.add(j)
        known[j][1:] = [round(float(spots[i][0]), 1),
                        round(float(spots[i][1]), 1)]
    nxt = max([k[0] for k in known] or [0]) + 1
    for i, (x, y) in enumerate(spots):
        if i not in num:
            num[i] = nxt
            known.append([nxt, round(float(x), 1), round(float(y), 1)])
            nxt += 1
    return [num[i] for i in range(len(spots))]


def _load_codes(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_codes(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def find_desks(upto, days=SEAT_DAYS, folder=pdx.SEATS, codes=None):
    """The regular seats of 140-H's office cameras over the last `days`
    working days up to `upto`: [{code, room, recorder, channel, seat,
    share}], busiest first per camera. A seat is a spot held in
    MIN_SHARE+ of the passes; an office is a room that is not a lobby,
    the cafe, a meeting room or outside (progress_data.place_of).

    `codes` (desks_data.CODES, numbers only, this laptop): each desk keeps
    its code from day to day (stable_numbers); without it they are
    numbered busiest first, as they were before 24 Nov 18:00."""
    import seat_map
    wd = pdx.working_days(upto, days, folder)
    if not wd:
        return []
    notes = seat_map.load(wd, HOURS, folder)
    found = seat_map.seats(notes, passes=seat_map.passes_in(wd, HOURS),
                           min_share=MIN_SHARE)
    data = _load_codes(codes) if codes else {}
    reg = data.setdefault("desks", {})
    before = json.dumps(reg, sort_keys=True)
    desks = []
    for (room, rec, ch), spots in sorted(found.items()):
        if rec not in desks_data.CAMPUS or pdx.place_of(room) != "office":
            continue
        cam = "%s.%d" % (rec, int(ch))
        nums = (stable_numbers(cam, [(s[0], s[1]) for s in spots], reg)
                if codes else range(1, len(spots) + 1))
        for i, (x, y, held, share) in zip(nums, spots):
            desks.append({"code": "%s.%d-%d" % (rec, int(ch), i),
                          "room": room, "recorder": rec, "channel": int(ch),
                          "seat": [round(float(x), 1), round(float(y), 1)],
                          "share": round(float(share), 3)})
    if codes and json.dumps(reg, sort_keys=True) != before:
        # since: from when a code means one place (desks_data.build reads
        # the desks' activity only from then on)
        data.setdefault("since", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        _save_codes(codes, data)
    return desks


def main(argv):
    if len(argv) > 1 and argv[1] == "build":
        upto = argv[2] if len(argv) > 2 else datetime.now().strftime(
            "%Y-%m-%d")
        df = desks_data.build(upto, desks=find_desks(
            upto, codes=desks_data.CODES), codes=desks_data.CODES)
        n = df["code"].nunique() if len(df) else 0
        print("desks:", n, "desk-days:", len(df), "->", desks_data.OUT)
    else:
        print(__doc__)


if __name__ == "__main__":
    import sys
    main(sys.argv)
