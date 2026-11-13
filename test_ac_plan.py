"""Check the recommended AC timings.

    python test_ac_plan.py
"""
import sys

import ac_plan as ap

FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def day(stretches, watched=(0, 1440)):
    """1440 minutes: people per minute from (from h, to h, people)."""
    mins = [None] * 1440
    for m in range(*watched):
        mins[m] = 0
    for a, b, n in stretches:
        for m in range(int(a * 60), int(b * 60)):
            mins[m] = n
    return mins


def main():
    # A cafe with six towers: two people from 9:30, a full twelve at lunch,
    # ten in the afternoon, four in the evening, and the office boy for ten
    # minutes at nine at night. Five days alike.
    cafe = day([(9.5, 12, 2), (12, 15, 12), (15, 18, 10), (18, 20, 4),
                (21, 21 + 10 / 60.0, 1)])
    bands = ap.plan([cafe] * 5, 6)
    check("the cafe's day, said as stretches",
          ap.say(bands, 6),
          "off until 9:30am · 1 of 6 9:30am–12pm · all 6 12pm–3pm · "
          "5 of 6 3pm–6pm · 2 of 6 6pm–8pm · off after 8pm")
    check("the office boy's round switches nothing on",
          [n for a, b, n in bands if a <= 21 * 60 < b], [0])
    check("unit-hours a day", round(ap.unit_hours(bands), 1),
          round(2.5 * 1 + 3 * 6 + 3 * 5 + 2 * 2, 1))

    # Half an hour empty in the middle of lunch keeps the towers on.
    gap = day([(9.5, 12, 2), (12, 13, 12), (13.5, 15, 12), (15, 18, 10),
               (18, 20, 4)])
    check("a dip under an hour keeps the units around it",
          [n for a, b, n in ap.plan([gap] * 5, 6) if a <= 13 * 60 < b], [6])

    # People every evening till ten, on most days: one unit after hours.
    late = day([(10, 22, 3)])
    bands = ap.plan([late] * 4 + [day([(10, 20, 3)])], 3)
    check("people there late on most days: one unit after eight",
          [n for a, b, n in bands if a <= 21 * 60 < b], [1])
    check("and all three in working hours",
          [n for a, b, n in bands if a <= 12 * 60 < b], [3])

    # Somebody in only one day in five: not the usual day.
    rare = [day([(10, 18, 4)])] + [day([])] * 4
    check("one day in five is not a habit: off",
          ap.say(ap.plan(rare, 2), 2), "nobody is usually here: keep it off")

    # No day watched: nothing to say. One day: a first guess.
    unwatched = day([], watched=(0, 0))
    check("no day watched: no plan", ap.plan([unwatched] * 5, 6), None)
    # The same day once: 9:30-10 is before opening, and one morning is not
    # yet a habit, so the plan starts at ten.
    check("one watched day among unwatched ones is a first guess",
          ap.say(ap.plan([cafe] + [unwatched] * 4, 6), 6),
          "off until 10am · 1 of 6 10am–12pm · all 6 12pm–3pm · "
          "5 of 6 3pm–6pm · 2 of 6 6pm–8pm · off after 8pm")
    # A morning nobody watched (141 was mapped on 11 Nov at noon) is not
    # known, and is never called "off".
    afternoon = day([(12, 15, 12), (15, 18, 10)], watched=(12 * 60, 1440))
    bands = ap.plan([afternoon], 6)
    check("a half hour nobody watched is not known",
          [n for a, b, n in bands if a <= 9 * 60 < b], [None])
    check("  and is said so", ap.say(bands, 6).split(" · ")[0],
          "not watched yet until 12pm")
    check("  and counts no unit-hours", round(ap.unit_hours(bands), 1),
          round(3 * 6 + 3 * 5, 1))
    meeting = day([(15, 15.5, 6)])
    check("half an hour's meeting is a visit, not a routine",
          ap.say(ap.plan([meeting] * 5, 1), 1),
          "nobody is usually here: keep it off")
    guard = day([(10, 18, 3), (1, 1.5, 1)])
    check("one night's round is not a habit after hours",
          [n for a, b, n in ap.plan([guard], 1) if a <= 60 < b], [0])
    check("one unit is said plainly",
          ap.say([(0, 600, 0), (600, 1200, 1), (1200, 1440, 0)], 1),
          "off until 10am · on 10am–8pm · off after 8pm")
    check("a room with no unit has no plan", ap.plan([cafe] * 5, 0), None)

    # What ran: the read units minute by minute from the room's rows.
    import pandas as pd
    t0 = pd.Timestamp("2026-11-12 00:00", tz="Asia/Karachi")
    at = lambda h: t0 + pd.Timedelta(hours=h)
    mins = ap.units_minutes([at(-2), at(9), at(13), at(20)], [0, 2, 5, 0],
                            t0, [(t0, at(24))])
    check("rows hold until the next one: 2 from nine",
          (mins[8 * 60], mins[9 * 60], mins[13 * 60], mins[21 * 60]),
          (0, 2, 5, 0))
    mins_gap = ap.units_minutes([at(-2), at(9)], [0, 2], t0,
                                [(t0, at(10)), (at(12), at(24))])
    check("a minute the loop was off is not known",
          (mins_gap[11 * 60], mins_gap[12 * 60]), (None, 2))
    unread = ap.units_minutes([at(-2)], [None], t0, [(t0, at(24))])
    check("a row with no reading is not known", unread[600], None)
    bands = ap.ran([mins] * 3)
    check("what ran, as stretches",
          ap.say(bands, 5),
          "off until 9am · 2 of 5 9am–1pm · all 5 1pm–8pm · off after 8pm")
    check("nothing read: nothing to show", ap.ran([unread] * 3), None)

    # Capped by what was seen to be enough: the cafe's fullest lunch ran on
    # three towers, so the plan never asks for more than three.
    capped = ap.plan([cafe] * 5, 6, cap=3)
    check("the busiest half hour gets the most ever seen running",
          max(n for a, b, n in capped if n), 3)
    check("and the quiet morning stays at one",
          [n for a, b, n in capped if a <= 10 * 60 < b], [1])

    print()
    if FAILURES:
        print("%d failure(s)" % len(FAILURES))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
