"""Check the floor-by-floor view: placing rooms, usual hours, the drawing.

    python test_floors.py
"""
import sys
from datetime import timedelta, timezone

import pandas as pd

import floors_view as fv

PKT = timezone(timedelta(hours=5))
FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def day(n):
    return pd.Timestamp(2026, 11, n).tz_localize(PKT)


def at(n, h, m=0):
    return (day(n) + pd.Timedelta(hours=h, minutes=m)).tz_convert("UTC")


def main():
    check("a floor written down is used",
          fv.floor_of({"room": "Marketing", "floor": "Ground floor"}),
          "Ground floor")
    check("a 141 room's floor comes from its name, under its block",
          fv.floor_of({"room": "141-D MR01 (2nd floor)"}),
          "141-D · Second floor")
    check("a 141 room on the ground floor says so",
          fv.floor_of({"room": "141 Room 7 (ground floor)"}),
          "Main building · Ground floor")
    # 13 Nov survey: rooms.yaml can say the building where the name cannot.
    check("rooms.yaml's building wins over the name",
          fv.floor_of({"room": "141 Room 7 (ground floor)",
                       "building": "141-D"}), "141-D · Ground floor")
    check("  with its floor written out too",
          fv.floor_of({"room": "141-C Cafe", "building": "141-C",
                       "floor": "Ground floor"}), "141-C · Ground floor")
    check("under its floor's heading a room drops the floor from its name",
          fv.on_floor("141 Room 7 (ground floor)"), "Room 7")
    check("  and so does a numbered floor",
          fv.on_floor("141-D MR01 (2nd floor)"), "141-D MR01")
    check("  a name with no floor is left alone",
          fv.on_floor("141 Learning Center"), "Learning Center")
    check("a 141 room with no floor in its name is its block",
          fv.floor_of({"room": "141 Admin Room"}), "Main building")
    check("an unplaced 140-H room is not guessed onto a floor",
          fv.floor_of({"room": "Lobby"}), "Not placed on a floor yet")
    # 12 Nov, Shamroze: "5 AC · 5 t -- why 5T? write the total tons".
    import overview as ov
    check("same-size units: each and the total",
          ov.ac_size(5, "1+1+1+1+1", 5.0), "5 AC · 1 ton each · 5 ton total")
    check("mixed sizes: added up in front of you",
          ov.ac_size(4, "1+1.5+1+1.5", 5.0),
          "4 AC · 1.5 + 1.5 + 1 + 1 = 5 ton total")
    check("one unit: its size", ov.ac_size(1, "2", 2.0), "1 AC · 2 ton")
    check("sizes unknown: the total where there is one",
          ov.ac_size(3, "", 6.0), "3 AC · 6 ton total")
    check("nothing known: the count", ov.ac_size(2, None, float("nan")),
          "2 AC")
    check("no unit", ov.ac_size(0), "no AC")
    check("a blank floor from the table (NaN) is no floor, not 'nan'",
          fv.floor_of({"room": "Commons", "floor": float("nan")}),
          "Not placed on a floor yet")

    # A room that opens at 9:30 and empties at 7 on three watched weekdays,
    # with the cleaner's 7:10 round first: the round is not the opening.
    rows = []
    for n in (9, 10, 11):
        rows += [(at(n, 7, 10), "occupied", 1), (at(n, 7, 20), "empty", 0),
                 (at(n, 9, 30), "occupied", 4), (at(n, 19, 0), "empty", 0)]
    ev = pd.DataFrame([{"timestamp": t, "room": "HR Room", "status": s,
                        "people": p} for t, s, p in rows])
    beats = [t for n in (9, 10, 11) for t in pd.date_range(
        at(n, 0), at(n, 23, 59), freq="5min")]
    usual = fv.usual_days(ev, ["HR Room"], [day(9), day(10), day(11)], beats)
    starts, leaves, nights, _ = usual["HR Room"]
    check("usually opens at 9:30, the cleaner's round left out",
          round(starts), 9 * 60 + 30)
    check("usually empty by 7 in the evening", round(leaves), 19 * 60)
    check("and says so", fv.usual_text(usual["HR Room"]),
          "usually 9:30 morning – 7:00 evening")

    # Still in at midnight on both days: a night, never a 12:00 departure.
    late = pd.DataFrame([{"timestamp": t, "room": "Room 17", "status": s,
                          "people": 2}
                         for t, s in ((at(9, 10), "occupied"),
                                      (at(10, 10), "occupied"))])
    u = fv.usual_days(late, ["Room 17"], [day(9), day(10)], beats)
    check("a room busy through midnight is a night, not a 12:00 leaving",
          (u["Room 17"][1], u["Room 17"][2]), (None, 2))
    check("one day is not 'usually'",
          fv.usual_days(ev, ["HR Room"], [day(9)], beats)["HR Room"][0], None)
    unwatched = fv.usual_days(ev, ["HR Room"], [day(9), day(10)], [])
    check("days the cameras did not watch say nothing", unwatched, {})

    df = pd.DataFrame([
        {"room": "Admin Room", "zone": "Offices", "floor": "Ground floor",
         "dept": "", "status": "empty", "people": 0, "has_unit": True,
         "alerts": True, "ac_count": 1, "tons_total": 1.0, "ac_state": "on",
         "ac_units_on": 1, "empty_since": pd.Timestamp("2026-11-12 08:00",
                                                       tz="UTC")},
        {"room": "Marketing", "zone": "Offices", "floor": "Ground floor",
         "dept": "", "status": "occupied", "people": 11, "has_unit": True,
         "alerts": True, "ac_count": 5, "tons_total": 5.0, "ac_state": None,
         "ac_units_on": None, "empty_since": None},
        {"room": "Entry H", "zone": "H entrance", "floor": "Ground floor",
         "dept": "", "status": "occupied", "people": 1, "has_unit": False,
         "alerts": True, "ac_count": 0, "tons_total": None, "ac_state": None,
         "ac_units_on": None, "empty_since": None},
        {"room": "H Street", "zone": "H perimeter", "dept": "",
         "status": "occupied", "people": 4, "has_unit": False},
    ])
    floors = fv.tiles(df, {}, pd.Timestamp("2026-11-12 09:00", tz="UTC"))
    check("outside is left off the building", len(floors), 1)
    g = floors[0]
    check("an empty room with its AC running comes first",
          g["rooms"][0]["room"], "Admin Room")
    check("  and is marked to switch off", g["rooms"][0]["waste"], True)
    check("a corridor is a space, not a room tile",
          [s["room"] for s in g["spaces"]], ["Entry H"])
    check("the floor adds its people up", g["people"], 12)
    html = fv.page("light", floors, {"campus": "140-H", "k": "t"}, 5)
    check("the page draws", "The building, floor by floor" in html, True)
    check("links carry the entry ticket", "k=t" in html, True)
    check("eleven people: seven figures and +4",
          html.count("<circle") >= 7 and "+4" in html, True)
    check("every unit's size known: the floor's total", g["tons"], 6.0)
    unknown = df.copy()
    unknown.loc[unknown["room"] == "Marketing", "tons_total"] = None
    g2 = fv.tiles(unknown, {}, pd.Timestamp("2026-11-12 09:00", tz="UTC"))[0]
    check("one size unknown: no total, rather than a wrong one",
          g2["tons"], None)

    print("\n%s" % ("all checks passed" if not FAILURES
                    else "%d FAILED" % len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
