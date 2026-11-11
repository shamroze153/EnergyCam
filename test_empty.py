"""Check the "Empty time" ledger: minutes empty, in use, and not watched.

    python test_empty.py
"""
import sys
from datetime import date

import pandas as pd

import empty_view as evw

FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def pkt(h, m=0, day=11):
    return pd.Timestamp(2026, 11, day, h, m, tz="Asia/Karachi") \
        .tz_convert("UTC")


def events(rows):
    return pd.DataFrame([{"room": r, "timestamp": t, "status": s,
                          "people": 0, "ac_state": None}
                         for r, t, s in rows])


def main():
    # Wednesday 11 Nov, working hours 10 to 8, seen at 6 in the evening.
    now = pkt(18)
    spans = evw.windows_for(date(2026, 11, 11), None, now, evw.WORKING)
    check("a weekday's working window runs ten to now",
          [(a.tz_convert("Asia/Karachi").hour,
            b.tz_convert("Asia/Karachi").hour) for a, b in spans], [(10, 18)])
    check("a Sunday has no working window",
          evw.windows_for(date(2026, 11, 8), None, pkt(18, day=8),
                          evw.WORKING), [])
    check("and its after-hours is all of it",
          round(sum(evw.minutes(a, b) for a, b in evw.windows_for(
              date(2026, 11, 8), None, pkt(23, 59, day=9), evw.AFTER))), 1440)

    # Empty since last night, people in from 11 to 1, empty again after.
    ev = events([("Board", pkt(21, day=10), "empty"),
                 ("Board", pkt(11), "occupied"),
                 ("Board", pkt(13), "empty")])
    rooms = pd.DataFrame([{"room": "Board", "zone": "Offices",
                           "has_unit": True, "alerts": True, "ac_count": 1,
                           "status": "empty", "ac_state": None}])
    rows = evw.ledger(ev, rooms, spans, [(spans[0][0], spans[0][1])])
    r = rows[0]
    check("the morning counts as empty, from last night's state",
          round(r["empty"]), 60 + 300)
    check("the meeting counts as in use", round(r["occupied"]), 120)
    check("the longest stretch is the afternoon", round(r["longest"]), 300)

    # The loop asleep from 2 to 3: that hour is neither empty nor in use.
    beats = [t for t in pd.date_range(pkt(9, 50), pkt(18), freq="4min")
             if not (pkt(14) <= t < pkt(15))]
    alive = evw.watched(beats, spans[0][0], spans[0][1])
    r = evw.ledger(ev, rooms, spans, alive)[0]
    check("an hour nobody watched is not handed to the room as empty",
          round(r["empty"]), 60 + 300 - 52)
    # beats at 13:58 and 15:02, each vouching six minutes: 14:04 to 14:56
    check("and is drawn as not watched", round(r["unwatched"]), 52)
    check("a stretch broken by a gap is two stretches, not one",
          round(r["longest"]), 184)

    # A room with no events at all is unknown, not empty.
    rooms2 = pd.DataFrame([{"room": "New", "zone": "Offices",
                            "has_unit": True, "alerts": True, "ac_count": 1,
                            "status": "unknown", "ac_state": None}])
    r = evw.ledger(ev, rooms2, spans, [(spans[0][0], spans[0][1])])[0]
    check("a room nothing was recorded for is never called empty",
          (round(r["empty"]), round(r["unknown"])), (0, 480))

    # Right now: rooms with a unit, empty, longest first.
    df = pd.DataFrame([
        {"room": "A", "has_unit": True, "alerts": True, "status": "empty",
         "empty_since": pkt(17), "timestamp": pkt(17), "ac_state": "on"},
        {"room": "B", "has_unit": True, "alerts": True, "status": "empty",
         "empty_since": pkt(12), "timestamp": pkt(12), "ac_state": None},
        {"room": "C", "has_unit": False, "alerts": True, "status": "empty",
         "empty_since": pkt(9), "timestamp": pkt(9), "ac_state": None},
        {"room": "S", "has_unit": True, "alerts": False, "status": "empty",
         "empty_since": pkt(9), "timestamp": pkt(9), "ac_state": None},
        {"room": "D", "has_unit": True, "alerts": True, "status": "occupied",
         "empty_since": None, "timestamp": pkt(9), "ac_state": None}])
    now_rows = evw.empty_now(df, now)
    check("empty now: only rooms with a unit somebody could switch off",
          [x["room"] for x in now_rows], ["B", "A"])
    check("with how long", [round(x["minutes"]) for x in now_rows], [360, 60])

    html = evw.page("dark", evw.ledger(ev, rooms, spans, alive), now_rows,
                    spans[0][0], spans[0][1], "Today", "working hours",
                    {"campus": "140-H"}, (432, 480))
    check("the page draws", "Empty right now" in html and "ev-line" in html,
          True)
    check("and owns up to the unwatched hour", "not watched" in html, True)

    print("\n%s" % ("all checks passed" if not FAILURES
                    else "%d FAILED" % len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
