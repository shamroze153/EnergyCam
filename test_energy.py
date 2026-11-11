"""Check the Meters and Analysis pages say what the numbers say.

    python test_energy.py

Each check is one of the things that made the page "look strange" on
11 November, held so it cannot come back.
"""
import re
import sys
from datetime import timedelta

import pandas as pd

import energy_view as ev

FAILURES = []
DAY = pd.Timestamp("2026-11-11 11:00", tz="Asia/Karachi")


def check(label, ok, detail=""):
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> %s" % (detail,)))
    if not ok:
        FAILURES.append(label)


def at(days_back, h=11, m=0):
    return (DAY - timedelta(days=days_back)).replace(hour=h, minute=m) \
        .tz_convert("UTC")


METERS = pd.DataFrame([
    {"code": "gf_basement", "label": "Ground floor + basement",
     "covers": "", "sanctioned_kw": 19.0, "behind_solar": True},
    {"code": "first_cafe", "label": "First floor + cafe", "covers": "",
     "sanctioned_kw": 37.0, "behind_solar": False},
])


def main():
    # ---- the panels -----------------------------------------------------
    daily = pd.DataFrame({"taken": [at(3), at(2), at(1)],
                          "kwh": [92.0, 31.0, 118.0]})
    sun, kind = ev.solar_per_day(daily)
    check("a day's figure is read as a day's figure",
          kind == "daily" and list(sun["kwh"]) == [92, 31, 118], (kind, sun))
    total = pd.DataFrame({"taken": [at(3), at(2), at(1)],
                          "kwh": [25010.0, 25102.0, 25190.0]})
    sun, kind = ev.solar_per_day(total)
    check("the inverter's lifetime total is turned into days",
          kind == "total" and list(sun["kwh"]) == [92, 88], (kind, sun))

    # ---- the readings ----------------------------------------------------
    readings = pd.DataFrame([
        {"meter": "gf_basement", "taken": at(3), "reading": 1000.0,
         "units": None, "max_temp": 30.0},
        {"meter": "gf_basement", "taken": at(2), "reading": 1250.0,
         "units": None, "max_temp": 31.0},
        # no reading the next day: the one after covers two
        {"meter": "gf_basement", "taken": at(0), "reading": 1750.0,
         "units": None, "max_temp": 32.0},
    ])
    periods = ev.reading_periods(readings, METERS)
    check("a reading is drawn on the day before it was taken",
          periods.iloc[0]["day"].strftime("%d") == (DAY - timedelta(days=3))
          .strftime("%d"), periods.iloc[0]["day"])
    gap = periods[periods["shared"]]
    check("a missed day is shared out, not drawn as one tall day",
          len(gap) == 2 and all(abs(u - 250) < 1e-6 for u in gap["units"]),
          gap[["day", "units"]].to_dict("records"))
    table, _ = ev.daily_table(readings, METERS,
                              pd.DataFrame({"taken": [at(1)], "kwh": [90.0]}))
    check("solar typed in today sits on yesterday, beside its reading",
          table["solar"].notna().sum() == 1
          and table.loc[table["solar"].notna(), "day"].iloc[0]
          == (DAY - timedelta(days=2)).normalize(), table)

    wrong = pd.concat([readings, pd.DataFrame([
        {"meter": "gf_basement", "taken": at(0, 15), "reading": 1700.0,
         "units": None, "max_temp": None},
        {"meter": "gf_basement", "taken": at(0, 18), "reading": 9700.0,
         "units": None, "max_temp": None}])])
    said = " | ".join(ev.suspicious(wrong, METERS))
    check("a meter that went backwards is pointed out", "backwards" in said,
          said)
    check("and so is more than the connection can draw",
          "more than the connection" in said, said)

    # ---- the bills -------------------------------------------------------
    bills = pd.DataFrame([
        {"meter": "first_cafe", "period_start": "2026-%02d-01" % m,
         "period_end": "2026-%02d-28" % m, "units": u, "amount_rs": u * 70.0}
        for m, u in ((8, 6332), (10, 7440), (7, 41145), (9, 5986))])
    months = ev.month_bills(bills, METERS)
    check("the months run in date order, not alphabetical",
          list(months["month"]) == ["Jul 26", "Aug 26", "Sep 26", "Oct 26"],
          list(months["month"]))
    check("the month a connection cannot draw is marked",
          list(months["impossible"]) == [True, False, False, False])
    page = ev.meters_page("dark", table, "daily", METERS, bills,
                          [3.0] * len(table), 67.0, [], True, "140-H")
    check("it is drawn off the scale rather than setting it",
          "off the scale" in page)
    check("nothing on the page reads None or nan",
          not re.search(r">\s*(None|nan|NaT)\s*<", page))
    check("no words inside a stretched chart",
          "<text" not in page)
    other = ev.meters_page("dark", None, "daily", METERS.iloc[0:0], bills,
                           None, 0, [], False, "141-C/D")
    check("a campus with no meters says so instead of showing another's",
          "No electricity meters are recorded for 141-C/D" in other)

    # ---- where the waste is ----------------------------------------------
    now = (DAY + timedelta(hours=6)).tz_convert("UTC")
    history = pd.DataFrame([
        (at(1, 9), "Marketing", "occupied", 3, None),
        (at(1, 18), "Marketing", "empty", 0, None),
        (at(1, 9), "HR Room", "occupied", 1, None),
        (at(1, 20), "HR Room", "empty", 0, None),
        (at(1, 9), "Data Centre", "empty", 0, None),
    ], columns=["timestamp", "room", "status", "people", "ac_state"])
    rooms = pd.DataFrame([
        {"room": "Marketing", "zone": "Offices", "dept": "",
         "has_unit": True, "alerts": True, "ac_count": 5},
        {"room": "HR Room", "zone": "Offices", "dept": "", "has_unit": True,
         "alerts": True, "ac_count": 1},
        {"room": "Data Centre", "zone": "Server rooms", "dept": "IT",
         "has_unit": True, "alerts": False, "ac_count": 1},
    ])
    rows = ev.top_rooms(history, rooms, at(2), now, (18.5, 22.5),
                        {"unit_kw": 1.2, "tariff_rs_per_kwh": 67,
                         "peak_rs_per_kwh": 81})
    names = [r["room"] for r in rows]
    check("rooms are ranked by what they would cost",
          names == ["Marketing", "HR Room"], names)
    check("a server room cooled on purpose is never on the list",
          "Data Centre" not in names)
    check("five units cost five times one",
          rows[0]["units"] == 5 and rows[0]["rupees"] > rows[1]["rupees"] * 4,
          [(r["room"], round(r["rupees"])) for r in rows])
    page = ev.analysis_page("light", rows, 10, 4, 1234, 1.2, 1, 2,
                            (67, 81, "18:30–22:30"), 73, 32)
    check("the analysis page names the room to start with",
          "Where to start" in page and "Marketing" in page)
    check("and counts bills, not months", "32 bills" in page)

    print()
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
