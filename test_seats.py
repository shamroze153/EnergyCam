"""Check the seat map: seats from the loop's notes.

    python test_seats.py
"""
import sys

import pandas as pd

import seat_map as sm

FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def main():
    rows = []
    # Ten passes. Somebody sits at one desk all ten; somebody else at
    # another for three; a third walks across once.
    for i in range(10):
        t = "10:%02d:00" % (i * 5)
        rows.append((t, 500, 400))
        if i < 3:
            rows.append((t, 1200, 420))
        if i == 4:
            rows.append((t, 900, 900))
    notes = pd.DataFrame([{"day": "2026-11-13", "time": t, "room": "R",
                           "recorder": "dvr2", "channel": 3, "cx": x,
                           "cy": y, "w": 80, "h": 200, "score": 0.8,
                           "frame_w": 1920, "frame_h": 1080}
                          for t, x, y in rows])
    found = sm.seats(notes, passes=10)
    spots = found[("R", "dvr2", 3)]
    check("a desk held all day and one held for a while are seats",
          len(spots), 2)
    check("the busiest first, held in every pass",
          (round(spots[0][3], 2), round(spots[1][3], 2)), (1.0, 0.3))
    check("a seat is where the box ends, not its middle",
          round(spots[0][1]), 500)
    check("somebody crossing once is not a seat",
          any(abs(s[0] - 900) < 50 for s in spots), False)
    check("the report says so room by room",
          sm.report(found).split()[1:4], ["2", "seats", "used"])
    check("no notes, no seats", sm.seats(pd.DataFrame()), {})
    # A share is of the loop's passes, not only those somebody was seen in:
    # held in 3 of 30 passes is a tenth, under the bar.
    check("the share is of every pass the loop made",
          len(sm.seats(notes, passes=30)[("R", "dvr2", 3)]), 1)

    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
