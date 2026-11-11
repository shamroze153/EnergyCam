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
    check("in twelve-hour time", ds.clock(s["starts"]) == "9:05 morning",
          ds.clock(s["starts"]))
    check("and in the evening", ds.clock(s["last_out"]) == "7:15 evening")
    check("midnight reads 12, not 0", ds.clock(at(0, 5)) == "12:05 night")

    # The database hands back UTC. The page first showed the cleaner at
    # 2:08 AM instead of 7:08 because the clock read UTC hours.
    utc = room.assign(timestamp=room["timestamp"].dt.tz_convert("UTC"))
    s_utc = ds.story(ds.spells(utc, DAY, END), DAY)
    check("UTC rows give the same story",
          s_utc["starts"] == at(9, 5) and s_utc["early"] is not None)
    check("and the clock still says 9:05 AM, not 4:05 morning",
          ds.clock(s_utc["starts"]) == "9:05 morning", ds.clock(s_utc["starts"]))
    check("the cleaner reads 7:10 AM", ds.clock(s_utc["first_in"]) == "7:10 morning",
          ds.clock(s_utc["first_in"]))

    check("noon is the afternoon", ds.clock(at(12, 30)) == "12:30 afternoon")
    check("half past nine at night is night",
          ds.clock(at(21, 30)) == "9:30 night")

    # Peak stretch: from reaching half the peak to the last minute at it.
    # The room hit 6 at 11:30 and held at least 3 until it dropped to
    # empty at 19:15, so people started leaving for good at 19:15.
    mins = ds.by_minute(ds.spells(room, DAY, END), DAY)
    p = ds.peak_stretch(mins)
    check("the peak stretch starts when the room first held three",
          p["from"] == 10 * 60, p["from"])
    check("and ends when it emptied for the evening",
          p["to"] == 19 * 60 + 15, p["to"])
    check("nobody went out mid-stretch, so no breaks", p["breaks"] == 0, p)

    # Breaks inside the stretch: lunch, and a short dip that is not one.
    lunch = events([(at(-3), "empty", 0), (at(9, 0), "occupied", 2),
                    (at(13, 0), "empty", 0), (at(13, 40), "occupied", 2),
                    (at(15, 0), "empty", 0), (at(15, 3), "occupied", 2),
                    (at(18, 0), "empty", 0)])
    p = ds.peak_stretch(ds.by_minute(ds.spells(lunch, DAY, END), DAY))
    check("a forty-minute lunch is one break", p["breaks"] == 1, p)
    check("of forty minutes", p["away_min"] == 40, p["away_min"])
    check("a three-minute dip is not a break", p["longest_break"] == 40, p)
    check("the longest unbroken stay is the morning, four hours",
          p["longest_stay"] == 240, p["longest_stay"])

    # Office boys: one person in and out in minutes, several times a day.
    tea = events([(at(-3), "empty", 0), (at(8, 0), "occupied", 1),
                  (at(8, 6), "empty", 0), (at(11, 0), "occupied", 1),
                  (at(11, 4), "empty", 0), (at(16, 0), "occupied", 1),
                  (at(16, 5), "empty", 0)])
    day = ds.spells(tea, DAY, END)
    brief, stays = ds.kinds(ds.visits(day))
    check("three short single-person visits are brief", len(brief) == 3,
          len(brief))
    check("and none of them is a stay", len(stays) == 0, len(stays))
    by_part = {(x["part"], x["from"]): x for x in ds.parts(day, DAY)}
    check("two in the morning", by_part[("morning", 5)]["brief"] == 2,
          by_part[("morning", 5)])
    check("one in the afternoon", by_part[("afternoon", 12)]["brief"] == 1)
    s_tea = ds.story(day, DAY)
    check("a room with only brief visits has no day start",
          s_tea["starts"] is None, s_tea["starts"])
    check("and no early visit either -- there was no day to be early for",
          s_tea["early"] is None, s_tea["early"])
    check("but still records who came first", s_tea["first_in"] == at(8, 0))

    # The office boy before the staff is skipped over, not taken as the start.
    before = events([(at(-3), "empty", 0), (at(8, 50), "occupied", 1),
                     (at(8, 54), "empty", 0), (at(9, 5), "occupied", 3),
                     (at(17, 0), "empty", 0)])
    s_b = ds.story(ds.spells(before, DAY, END), DAY)
    check("tea at 8:50 then staff at 9:05: the day starts at 9:05",
          s_b["starts"] == at(9, 5), s_b["starts"])

    desk = events([(at(-3), "empty", 0), (at(9, 0), "occupied", 1),
                   (at(17, 0), "empty", 0)])
    brief, stays = ds.kinds(ds.visits(ds.spells(desk, DAY, END)))
    check("one person all day is a stay, not an office boy",
          len(stays) == 1 and len(brief) == 0)
    crowd = events([(at(-3), "empty", 0), (at(12, 0), "occupied", 6),
                    (at(12, 10), "empty", 0)])
    brief, stays = ds.kinds(ds.visits(ds.spells(crowd, DAY, END)))
    check("six people for ten minutes is a meeting, not an office boy",
          len(brief) == 0)

    # The peak tariff window, 18:30 to 22:30. Three people until 19:40,
    # one working late until 21:00, then empty: an hour and a half of
    # peak-rate time with nobody in the room.
    late = events([(at(-3), "empty", 0), (at(9, 0), "occupied", 3),
                   (at(19, 40), "occupied", 1), (at(21, 0), "empty", 0)])
    w = ds.window(ds.spells(late, DAY, END), DAY, 18.5, 22.5)
    check("the window is four hours", w["watched_min"] == 240, w)
    check("somebody there for 150 of them", round(w["busy_pct"]) == 62,
          w["busy_pct"])
    check("empty for the last 90", w["empty_min"] == 90, w["empty_min"])
    check("three at its start", w["at_start"] == 3, w["at_start"])
    check("nobody at its end", w["at_end"] == 0, w["at_end"])
    check("and the last person left at 9:00 night",
          w["left_at"] == at(21, 0), w["left_at"])
    check("most at once was three", w["most"] == 3, w["most"])
    check("time-weighted average, not a headcount",
          abs(w["avg"] - (70 * 3 + 80 * 1) / 240.0) < 0.01, w["avg"])
    still = ds.window(ds.spells(events([(at(-3), "empty", 0),
                                        (at(17, 0), "occupied", 2)]),
                                DAY, END), DAY, 18.5, 22.5)
    check("a room still busy at the end has no leaving time",
          still["left_at"] is None and still["empty_min"] == 0)

    # Averaging several days. Three days: two normal, one where the room
    # was busy from the night before. The carried day must not drag the
    # average arrival towards midnight.
    stories, wins = [], []
    for d, (arrive, leave, early) in enumerate([(9 * 60, 19 * 60, True),
                                                (9 * 60 + 20, 18 * 60, False),
                                                (None, 18 * 60 + 30, False)]):
        base = DAY - timedelta(days=3 - d)
        rows = [(base - timedelta(hours=3), "empty" if arrive else "occupied",
                 0 if arrive else 2)]
        if early:
            rows += [(base + timedelta(hours=7), "occupied", 1),
                     (base + timedelta(hours=7, minutes=20), "empty", 0)]
        if arrive:
            rows.append((base + timedelta(minutes=arrive), "occupied", 4))
        rows.append((base + timedelta(minutes=leave), "empty", 0))
        day = ds.spells(events(rows), base, base + timedelta(days=1))
        stories.append(ds.story(day, base))
        wins.append(ds.window(day, base, 18.5, 22.5))
    avg = ds.average_days(stories, wins)
    check("three days averaged", avg["days"] == 3)
    check("the carried day is left out of the arrival average",
          avg["starts"] == 9 * 60 + 10, avg["starts"])
    check("and reads as 9:10 morning",
          ds.clock_minutes(avg["starts"]) == "9:10 morning",
          ds.clock_minutes(avg["starts"]))
    check("an early visit is a frequency, on 1 of 3 days",
          avg["early_days"] == 1, avg["early_days"])
    check("last out averages 7:00, 6:00 and 6:30 evening",
          ds.clock_minutes(avg["last_out"]) == "6:30 evening",
          ds.clock_minutes(avg["last_out"]))
    check("the peak window is averaged too", avg["window"]["days"] == 3)
    check("and says how many evenings anybody was there in it",
          avg["window"]["busy_days"] == 1, avg["window"]["busy_days"])

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

    # The timeline: one track per room, early visits hatched, nothing drawn
    # for a "now" that is not inside the day.
    import day_timeline as dt
    day = ds.spells(room, DAY, END)
    st_ = ds.story(day, DAY)
    html = dt.render([("Marketing", day, st_, True)], DAY, at(21, 30),
                     (18.5, 22.5), "light")
    check("the room is on the timeline", "Marketing" in html)
    check("the early visit is hatched, not solid", "(early visit)" in html
          and "repeating-linear-gradient(45deg" in html)
    check("the peak tariff is shaded", "peak tariff" in html)
    check("now is marked when it falls inside the day", 'title="now"' in html)
    yesterday = dt.render([("Marketing", day, st_, True)], DAY,
                          at(21, 30) + timedelta(days=1), (18.5, 22.5), "dark")
    check("and not on a day that is over", 'title="now"' not in yesterday)
    check("more people are drawn darker on light",
          dt.colour(1, "light") != dt.colour(9, "light"))
    check("and every bucket has its own step",
          len({dt.colour(n, "light") for n in (1, 2, 5, 9)}) == 4)
    unwatched = ds.spells(room, DAY, END, [at(9) + timedelta(minutes=m)
                                           for m in range(0, 120, 2)])
    html = dt.render([("Marketing", unwatched, ds.story(unwatched, DAY), True)],
                     DAY, at(21, 30), (18.5, 22.5), "light")
    check("time nobody watched is drawn as such", "nobody watching" in html)

    # ---- a department: several rooms read as one --------------------------
    # Squat Wolf: Room 0 opens at 9:30 with two, Room 3 at 10:00 with three,
    # Room 0 empties at 18:00, Room 3 at 19:15. Room 4 nobody watched.
    r0 = ds.spells(events([(at(-3), "empty", 0), (at(9, 30), "occupied", 2),
                           (at(18), "empty", 0)]), DAY, END)
    r3 = ds.spells(events([(at(-3), "empty", 0), (at(10), "occupied", 3),
                           (at(19, 15), "empty", 0)]), DAY, END)
    r4 = ds.spells(events([]), DAY, END)
    dept = ds.combine([r0, r3, r4])
    s = ds.story(dept, DAY)
    check("the department starts with its first room", s["starts"] == at(9, 30),
          s["starts"])
    check("and ends with its last", s["last_out"] == at(19, 15), s["last_out"])
    check("its people are added across rooms, not the largest",
          s["peak"] == 5, s["peak"])
    check("an unwatched room does not make the department unknown",
          s["busy_pct"] is not None and s["watched_min"] == 24 * 60,
          s["watched_min"])
    w = ds.window(dept, DAY, 18.5, 22.5)
    check("the peak tariff sees the last room leave", w["left_at"] == at(19, 15),
          w["left_at"])
    check("with three people still in when it opened", w["at_start"] == 3,
          w["at_start"])
    check("unknown only where every room is",
          ds.combine([r4, r4]) == [("unknown", 0, DAY, END)], ds.combine([r4, r4]))
    check("one room is its own department", ds.combine([r0]) == r0)
    check("the spells still cover the day end to end",
          dept[0][2] == DAY and dept[-1][3] == END and all(
              x[3] == y[2] for x, y in zip(dept, dept[1:])))

    print()
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
