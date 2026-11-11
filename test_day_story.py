"""Check a room's day is told the way it happened.

    python test_day_story.py
"""
import sys
from datetime import timedelta

import pandas as pd

import day_story as ds

FAILURES = []
DAY = pd.Timestamp("2026-11-11 00:00", tz="Asia/Karachi")
END = DAY + timedelta(days=1)


def check(label, ok, detail=""):
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> %s" % (detail,)))
    if not ok:
        FAILURES.append(label)


def at(h, m=0):
    return DAY + timedelta(hours=h, minutes=m)


def events(rows):
    return pd.DataFrame([{"timestamp": t, "status": s, "people": p}
                         for t, s, p in rows])


def main():
    # The day everybody describes: the cleaner at seven, empty until nine,
    # the room filling to six by half past eleven, the last out at seven.
    room = events([
        (at(-3), "empty", 0),            # last night, carried in
        (at(7, 10), "occupied", 1),      # housekeeping
        (at(7, 28), "empty", 0),
        (at(9, 5), "occupied", 2),
        (at(10, 0), "occupied", 4),
        (at(11, 30), "occupied", 6),
        (at(13, 0), "occupied", 3),
        (at(19, 15), "empty", 0),
    ])
    day = ds.spells(room, DAY, END)
    s = ds.story(day, DAY)
    check("first in is the cleaner", s["first_in"] == at(7, 10), s["first_in"])
    check("which is read as an early visit", s["early"] is not None)
    check("and how long the room then sat empty",
          round(s["early"]["empty_after_min"]) == 97, s["early"])
    check("the day proper starts at 9:05", s["starts"] == at(9, 5), s["starts"])
    check("peak is six", s["peak"] == 6, s["peak"])
    check("reached at 11:30", s["peak_at"] == at(11, 30), s["peak_at"])
    check("last out at 7:15 PM", s["last_out"] == at(19, 15), s["last_out"])
    busy = (18 + 10 * 60 + 10) / (24 * 60) * 100
    check("busy share of the whole watched day",
          abs(s["busy_pct"] - busy) < 0.1, s["busy_pct"])
    check("in twelve-hour time", ds.clock(s["starts"]) == "9:05 AM",
          ds.clock(s["starts"]))
    check("and in the evening", ds.clock(s["last_out"]) == "7:15 PM")
    check("midnight reads 12, not 0", ds.clock(at(0, 5)) == "12:05 AM")

    # The database hands back UTC. The page first showed the cleaner at
    # 2:08 AM instead of 7:08 because the clock read UTC hours.
    utc = room.assign(timestamp=room["timestamp"].dt.tz_convert("UTC"))
    s_utc = ds.story(ds.spells(utc, DAY, END), DAY)
    check("UTC rows give the same story",
          s_utc["starts"] == at(9, 5) and s_utc["early"] is not None)
    check("and the clock still says 9:05 AM, not 4:05 AM",
          ds.clock(s_utc["starts"]) == "9:05 AM", ds.clock(s_utc["starts"]))
    check("the cleaner reads 7:10 AM", ds.clock(s_utc["first_in"]) == "7:10 AM",
          ds.clock(s_utc["first_in"]))

    # A first visit long enough to be work is not "early".
    long_first = events([(at(-3), "empty", 0), (at(8, 0), "occupied", 2),
                         (at(10, 0), "empty", 0), (at(11, 0), "occupied", 3),
                         (at(17, 0), "empty", 0)])
    s = ds.story(ds.spells(long_first, DAY, END), DAY)
    check("a two-hour first spell is the day starting, not a visit",
          s["early"] is None and s["starts"] == at(8, 0), s)

    # A flicker -- a seated person lost for a frame -- is one visit, not two.
    flicker = events([(at(-3), "empty", 0), (at(9, 0), "occupied", 1),
                      (at(9, 20), "empty", 0), (at(9, 24), "occupied", 1),
                      (at(18, 0), "empty", 0)])
    s = ds.story(ds.spells(flicker, DAY, END), DAY)
    check("a four-minute dip is not an early visit", s["early"] is None, s)
    check("and counts as one visit", s["visits"] == 1, s["visits"])

    # Occupied when the day began: carried over, never an arrival.
    overnight = events([(at(-2), "occupied", 1), (at(6, 0), "empty", 0),
                        (at(9, 0), "occupied", 3), (at(18, 0), "empty", 0)])
    s = ds.story(ds.spells(overnight, DAY, END), DAY)
    check("a room busy at midnight is marked carried over", s["carried"])
    check("and that is not taken for an early visit", s["early"] is None)

    # Time nobody was watching is neither busy nor empty.
    beats = [at(9) + timedelta(minutes=m) for m in range(0, 9 * 60, 2)]
    day = ds.spells(events([(at(-3), "empty", 0), (at(10, 0), "occupied", 2),
                            (at(14, 0), "empty", 0)]), DAY, END, beats)
    s = ds.story(day, DAY)
    check("only the watched nine hours are counted",
          abs(s["watched_min"] - 9 * 60) < 10, s["watched_min"])
    check("so four busy hours of nine is 44%, not 17%",
          abs(s["busy_pct"] - 400 / 9.0) < 2, s["busy_pct"])
    hours = ds.hourly(day, DAY)
    check("an hour nobody watched has no value", hours[3] is None, hours[3])
    check("a watched empty hour reads nought", hours[9] == 0, hours[9])
    check("a watched busy hour reads its people", hours[11] == 2, hours[11])

    # A room nobody entered all day.
    s = ds.story(ds.spells(events([(at(-3), "empty", 0)]), DAY, END), DAY)
    check("an empty day has no first in", s["first_in"] is None)
    check("and is 0% busy", s["busy_pct"] == 0, s["busy_pct"])

    # A room the loop never wrote down.
    s = ds.story(ds.spells(events([]).reindex(columns=["timestamp", "status",
                                                        "people"]),
                           DAY, END), DAY)
    check("a room with no rows at all is not 0% busy, it is unknown",
          s["busy_pct"] is None, s["busy_pct"])

    print()
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
