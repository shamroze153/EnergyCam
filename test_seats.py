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

    # 13 Nov, 141 Room 22: near the camera a seated person's box is 400-500
    # px tall and where it ends wanders 70-160 px pass to pass. One chair,
    # one seat -- and the chair beside it, 550 px off, a seat of its own.
    near = []
    for i in range(10):
        t = "11:%02d:00" % (i * 5)
        near.append((t, 600 + (-40, 50, 0, 60, -30)[i % 5],
                     500 + (0, 80, -60, 40, 100)[i % 5]))
        near.append((t, 1150, 520))
    big = pd.DataFrame([{"day": "2026-11-13", "time": t, "room": "N",
                         "recorder": "dvr2", "channel": 10, "cx": x,
                         "cy": y, "w": 220, "h": 500, "score": 0.8,
                         "frame_w": 1920, "frame_h": 1080}
                        for t, x, y in near])
    spots = sm.seats(big, passes=10)[("N", "dvr2", 10)]
    check("near the camera one wandering chair is one seat, held all day",
          [round(s[3], 1) for s in spots], [1.0, 1.0])
    check("  which a reach of the frame's width alone split up",
          len(sm.seats(big, passes=10, reach=0)[("N", "dvr2", 10)]) > 2,
          True)

    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
