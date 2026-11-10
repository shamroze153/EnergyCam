"""Check the audit's conclusions against records whose answer is known.

The audit says things about somebody's building: this room has a false
person in it, that camera is not answering, nobody has been seen in this
room for three days. A wrong conclusion sends a person walking to a room
for no reason, or worse, quietly excuses the one fault that matters -- a
room reporting empty while people sit in it.

"It ran without crashing" is not evidence for any of that. So each pattern
is built here out of events whose right answer is known by construction.

    python test_audit.py
"""
import sys

import pandas as pd

import audit
from schedule import DEFAULT_HOURS

FAILURES = []
NOW = pd.Timestamp("2026-11-10 17:00", tz="Asia/Karachi").tz_convert("UTC")
HOURS = DEFAULT_HOURS
KNOWN = {
    "Marketing": {"name": "Marketing", "zone": "Offices"},
    "Admin Room": {"name": "Admin Room", "zone": "Offices"},
    "P2 Parking": {"name": "P2 Parking", "zone": "Outside & plant"},
}


def check(label, got, want):
    ok = got == want
    print("%-4s %s" % ("OK" if ok else "FAIL", label))
    if not ok:
        FAILURES.append("%s: got %r, wanted %r" % (label, got, want))


def at(day_offset, hour, minute=0):
    return (NOW.tz_convert("Asia/Karachi").normalize()
            - pd.Timedelta(days=day_offset)
            + pd.Timedelta(hours=hour, minutes=minute)).tz_convert("UTC")


def frame(rows):
    return pd.DataFrame(rows, columns=["timestamp", "room", "status",
                                       "people", "ac_state"])


def run(rows, rooms=None):
    events = frame(rows)
    rooms = rooms or sorted(set(events["room"]))
    return audit.findings(events, rooms, KNOWN, HOURS, NOW)


def main():
    # -- a camera that mostly does not answer ---------------------------
    silent, _, _, _, _ = run([
        (at(6, 9), "Marketing", "unknown", None, None),
        (at(1, 9), "Marketing", "occupied", 3, None),
        (at(1, 18), "Marketing", "empty", 0, None),
    ])
    check("a room unknown for most of the week is reported silent",
          [r[0] for r in silent], ["Marketing"])
    # 09:00 six days ago to 09:00 one day ago is 120 h, of a span that ends
    # at 17:00 today: 152 h. Not 83% -- that was arithmetic done in a hurry.
    check("and with how much of the time", round(silent[0][1]), 79)

    _, _, _, _, _ = run([(at(6, 9), "Marketing", "occupied", 2, None)])
    silent, _, _, _, _ = run([
        (at(6, 9), "Marketing", "occupied", 2, None),
        (at(6, 10), "Marketing", "unknown", None, None),
        (at(6, 11), "Marketing", "occupied", 2, None),
    ])
    check("a brief unknown is not", silent, [])

    # -- somebody who never leaves --------------------------------------
    _, stuck, _, _, _ = run([
        (at(3, 8), "Marketing", "occupied", 1, None),
        (at(2, 8), "Marketing", "empty", 0, None),
        (at(1, 11), "Marketing", "occupied", 4, None),
        (at(1, 17), "Marketing", "empty", 0, None),
    ])
    check("twenty-four hours occupied is flagged as a false person",
          [r[0] for r in stuck], ["Marketing"])
    check("and the spell's length is reported", round(stuck[0][1]), 24)

    _, stuck, _, _, _ = run([
        (at(1, 9), "Marketing", "occupied", 4, None),
        (at(1, 18), "Marketing", "empty", 0, None),
        (at(0, 9), "Marketing", "occupied", 3, None),
        (at(0, 16), "Marketing", "empty", 0, None),
    ])
    check("an ordinary working day is not", stuck, [])

    # -- the one that matters: a room nobody is ever seen in -------------
    _, _, never, _, _ = run([
        (at(6, 2), "Admin Room", "empty", 0, None),
    ], rooms=["Admin Room"])
    check("a room never occupied in operating hours is flagged",
          [r[0] for r in never], ["Admin Room"])
    check("and the reason names operating hours",
          "operating hours" in never[0][1], True)

    # Outside is excluded: a car park with nobody in it is not a fault.
    _, _, never, _, _ = run([
        (at(6, 2), "P2 Parking", "empty", 0, None),
    ], rooms=["P2 Parking"])
    check("an outdoor space is not expected to have people in it",
          never, [])

    # A room with no events at all is the same question, louder.
    _, _, never, _, _ = run([(at(1, 9), "Marketing", "occupied", 2, None)],
                            rooms=["Marketing", "Admin Room"])
    check("a room with no events at all is flagged",
          [r for r in never if r[0] == "Admin Room"],
          [("Admin Room", "no events at all")])

    # Seen, but a while ago.
    _, _, never, _, _ = run([
        (at(5, 11), "Marketing", "occupied", 3, None),
        (at(5, 18), "Marketing", "empty", 0, None),
    ], rooms=["Marketing"])
    check("a room not seen for days says how many",
          "not seen in operating hours for 5 days", never[0][1])

    # -- the small hours -------------------------------------------------
    _, _, _, nights, _ = run([
        (at(1, 1, 30), "Marketing", "occupied", 1, None),
        (at(1, 5), "Marketing", "empty", 0, None),
        (at(0, 11), "Marketing", "occupied", 2, None),
        (at(0, 16), "Marketing", "empty", 0, None),
    ])
    check("somebody there at half past one is reported",
          [r[0] for r in nights], ["Marketing"])
    check("with the hours it lasted", round(nights[0][1], 1), 3.5)

    # -- a count that never moves ----------------------------------------
    # Eight occupied spells at least, or one quiet week of a room genuinely
    # used by one person would be called a poster.
    rows = []
    for day in range(10):
        rows.append((at(day, 9), "Marketing", "occupied", 1, None))
        rows.append((at(day, 18), "Marketing", "empty", 0, None))
    _, _, _, _, flat = run(rows)
    check("always exactly one person is flagged as a fixed thing",
          flat, [("Marketing", 1)])

    rows = []
    for day in range(10):
        rows.append((at(day, 9), "Marketing", "occupied", day % 4 + 1, None))
        rows.append((at(day, 18), "Marketing", "empty", 0, None))
    _, _, _, _, flat = run(rows)
    check("a count that varies is not", flat, [])

    rows = []
    for day in range(3):
        rows.append((at(day, 9), "Marketing", "occupied", 1, None))
        rows.append((at(day, 18), "Marketing", "empty", 0, None))
    _, _, _, _, flat = run(rows)
    check("and three days of one person is too little to call it",
          flat, [])

    # -- coverage ---------------------------------------------------------
    beats = pd.Series([NOW - pd.Timedelta(minutes=m)
                       for m in range(0, 60 * 24, 2)]).sort_values()
    share, gaps = audit.coverage(pd.DataFrame({"timestamp": beats}), 1, NOW)
    check("a day of unbroken beats reads as full coverage",
          round(share, 2), 1.0)
    check("and finds no gaps", gaps, [])

    half = pd.Series([NOW - pd.Timedelta(minutes=m)
                      for m in range(0, 60 * 12, 2)]).sort_values()
    share, gaps = audit.coverage(pd.DataFrame({"timestamp": half}), 1, NOW)
    check("half a day of beats reads as half", round(share, 1), 0.5)
    check("and names the gap", len(gaps), 1)

    share, gaps = audit.coverage(pd.DataFrame({"timestamp": []}), 7, NOW)
    check("no beats at all is no coverage", share, 0.0)
    check("and the whole period is one gap", len(gaps), 1)

    print()
    if FAILURES:
        print("%d FAILURE(S):" % len(FAILURES))
        for line in FAILURES:
            print("  %s" % line)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
