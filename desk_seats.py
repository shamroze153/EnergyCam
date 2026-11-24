"""The desks of 140-H: every regular seat of an office camera.

The loop's half of desks_data.py (it needs seat_map, and so OpenCV, which
the hosted dashboard has not): find_desks() for desk_watch.py and for the
nightly build of progress/desks.csv.

    python desk_seats.py build [upto]
"""
from datetime import datetime

import desks_data
import progress_data as pdx

SEAT_DAYS = 5
MIN_SHARE = 0.10
HOURS = (9, 21)


def find_desks(upto, days=SEAT_DAYS, folder=pdx.SEATS):
    """The regular seats of 140-H's office cameras over the last `days`
    working days up to `upto`: [{code, room, recorder, channel, seat,
    share}], busiest first per camera. A seat is a spot held in
    MIN_SHARE+ of the passes; an office is a room that is not a lobby,
    the cafe, a meeting room or outside (progress_data.place_of)."""
    import seat_map
    wd = pdx.working_days(upto, days, folder)
    if not wd:
        return []
    notes = seat_map.load(wd, HOURS, folder)
    found = seat_map.seats(notes, passes=seat_map.passes_in(wd, HOURS),
                           min_share=MIN_SHARE)
    desks = []
    for (room, rec, ch), spots in sorted(found.items()):
        if rec not in desks_data.CAMPUS or pdx.place_of(room) != "office":
            continue
        for i, (x, y, held, share) in enumerate(spots, 1):
            desks.append({"code": "%s.%d-%d" % (rec, int(ch), i),
                          "room": room, "recorder": rec, "channel": int(ch),
                          "seat": [round(float(x), 1), round(float(y), 1)],
                          "share": round(float(share), 3)})
    return desks


def main(argv):
    if len(argv) > 1 and argv[1] == "build":
        upto = argv[2] if len(argv) > 2 else datetime.now().strftime(
            "%Y-%m-%d")
        df = desks_data.build(upto, desks=find_desks(upto))
        n = df["code"].nunique() if len(df) else 0
        print("desks:", n, "desk-days:", len(df), "->", desks_data.OUT)
    else:
        print(__doc__)


if __name__ == "__main__":
    import sys
    main(sys.argv)
