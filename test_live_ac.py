"""Check the "Air conditioning, right now" panel says only what it can see.

    python test_live_ac.py
"""
import sys

import pandas as pd

import live_ac

FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def room(name, **kw):
    base = {"room": name, "zone": "Offices", "has_unit": True, "alerts": True,
            "ac_count": 1, "ac_tons": None, "unit_kw": 1.2,
            "status": "occupied", "people": 3, "ac_state": None,
            "ac_units_on": None}
    base.update(kw)
    return base


def main():
    df = pd.DataFrame([
        room("141-C Cafe", ac_count=6, ac_tons=2, unit_kw=2.0, people=30,
             ac_state="on", ac_units_on=5),
        room("141 Room 32 (2nd floor)", ac_count=3, people=10,
             ac_state="on", ac_units_on=None),
        room("141 Learning Center", ac_count=3, status="empty", people=0,
             ac_state="on", ac_units_on=1),
        room("141 Finance Room", ac_state="off", ac_units_on=0),
        room("Old Finance Room"),                      # nobody calibrated it
        room("Corridor", has_unit=False, ac_count=0),
    ])
    seen = {"141-C Cafe": 5, "141 Room 32 (2nd floor)": 1,
            "141 Learning Center": 1, "141 Finance Room": 1}
    items = live_ac.rows(df, seen)
    names = [r["room"] for r in items]
    check("only rooms a camera can read are listed", len(items), 4)
    check("an empty room with its unit running comes first",
          names[0], "141 Learning Center")
    check("and is marked as waste", items[0]["waste"], True)
    cafe = next(r for r in items if r["room"] == "141-C Cafe")
    check("the cafe: five towers running", cafe["counted"], 5)
    check("at two tons each, about 10 kW", round(cafe["kw"], 1), 10.0)
    check("five marks running, one not visible",
          live_ac.dots(cafe).count('class="on"'), 5)
    check("  and one drawn as unseen, never as off",
          live_ac.dots(cafe).count('class="unseen"'), 1)
    r32 = next(r for r in items if r["room"] == "141 Room 32 (2nd floor)")
    check("a room read on with no count is one unit, not three",
          r32["counted"], 1)
    check("  and says so", r32["exact"], False)
    check("units out of view are not reported as off",
          live_ac.status_text(cafe)[0],
          "<b>5 running</b> &middot; 1 not readable")
    lc = next(r for r in items if r["room"] == "141 Learning Center")
    check("  nor counted into 'of N running'",
          "of 3" in live_ac.status_text(lc)[0], False)
    off = next(r for r in items if r["room"] == "141 Finance Room")
    check("a unit read off draws nothing", off["kw"], 0.0)

    html = live_ac.page("dark", items, 81.0, True, 14, {"campus": "141-C/D"})
    check("the panel draws", "Air conditioning, right now" in html, True)
    check("the empty room is told to switch off", "SWITCH OFF" in html, True)
    check("a floor is marked as a floor", "&ge;" in html, True)
    check("it says how many units it can read",
          "can read 8 of the 14 units" in html, True)
    check("and the hourly cost at the rate given",
          "Rs %s" % format(int(round((10.0 + 1.2 + 1.2) * 81)), ",") in html,
          True)
    empty = live_ac.page("light", [], 67.0, False, 10, {})
    check("a campus nobody calibrated says so",
          "No unit on this campus can be read" in empty, True)

    print("\n%s" % ("all checks passed" if not FAILURES
                    else "%d FAILED" % len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
