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


def check_reading_form():
    """The readings form's word on a typed number (18 Nov)."""
    last = (52434.0, pd.Timestamp("2026-11-17 17:36", tz="Asia/Karachi"))
    at = pd.Timestamp("2026-11-18 18:08", tz="Asia/Karachi")
    k = ev.reading_check(52630, last, at, usual=190)
    got = (k["level"], int(k["units"]), round(k["per_day"]))
    check("a day's reading: the units since and the day's pace",
          got == ("ok", 196, 192), got)
    check("  said plainly", k["text"].startswith("+196 units in 24.5 h"),
          k["text"])
    for value, usual, want, label in (
            (52340, None, "low", "lower than the last: wrong"),
            (54400, 190, "odd", "a slipped digit (ten times the usual): "
                                "worth a second look"),
            (52434, None, "odd", "the same number a day later: worth a "
                                 "second look"),
            (None, None, "none", "nothing typed: nothing said")):
        got = ev.reading_check(value, last, at, usual)["level"]
        check(label, got == want, got)
    got = ev.reading_check(52630, None, at)["level"]
    check("no reading before: nothing to compare", got == "none", got)
    soon = ev.reading_check(34560, (34402.0, at), at + pd.Timedelta(hours=1.7))
    check("an evening's two hours: the units, but no day's pace from them",
          soon["per_day"] is None and "a day" not in soon["text"],
          soon["text"])
    r = pd.DataFrame([
        {"meter": "a", "taken": pd.Timestamp("2026-11-16 12:00", tz="UTC"),
         "reading": 10.0},
        {"meter": "a", "taken": pd.Timestamp("2026-11-17 12:00", tz="UTC"),
         "reading": 20.0},
        {"meter": "b", "taken": pd.Timestamp("2026-11-17 12:00", tz="UTC"),
         "reading": None}])
    check("the last reading of a meter", ev.last_reading(r, "a")[0] == 20.0,
          ev.last_reading(r, "a"))
    check("a meter with no number yet has none",
          ev.last_reading(r, "b") is None, ev.last_reading(r, "b"))


def main():
    check_reading_form()
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
    saved_twice = pd.DataFrame({
        "taken": [at(2), at(2, 11, 1), at(2, 11, 2), at(1), at(1, 11, 1)],
        "kwh": [132.0, 132.0, 132.0, 281.0, 281.0]})
    sun, kind = ev.solar_per_day(saved_twice)
    check("a figure saved four times is one day's figure",
          kind == "daily" and list(sun["kwh"]) == [132, 281], (kind, sun))
    # 26 Nov (Shamroze): a whole month's MWh typed at once -- kept apart,
    # never read as a day of 6,000 kWh
    with_month = pd.DataFrame({
        "taken": [pd.Timestamp("2026-11-01", tz="Asia/Karachi"), at(2),
                  at(1)],
        "kwh": [6200.0, 132.0, 281.0],
        "note": [ev.MONTH_NOTE + ", 2026-11 (6.20 MWh typed)", None, None]})
    sun, kind = ev.solar_per_day(with_month)
    check("a month's total is no day; the days stay the days",
          (kind, list(sun["kwh"]), ev.solar_months(with_month)),
          ("daily", [132.0, 281.0], {"2026-11": 6200.0}))

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
    # 12 Nov: read "at about six" -- 16:49 one day, 18:31 the next. 213
    # units over 25.7 hours is a 199-unit day, not 213.
    late = pd.DataFrame([
        {"meter": "gf_basement", "taken": at(1, 16, 49), "reading": 51505.0,
         "units": None, "max_temp": None},
        {"meter": "gf_basement", "taken": at(0, 18, 31), "reading": 51718.0,
         "units": None, "max_temp": None}])
    p = ev.reading_periods(late, METERS).iloc[0]
    check("a reading taken late is put on a 24-hour footing",
          abs(p["units"] - 213 * 24 / p["hours"]) < 1e-6
          and abs(p["hours"] - (25 + 42 / 60.0)) < 0.01 and p["raw"] == 213,
          p.to_dict())
    # The usage beside the units: ten people for an hour is ten.
    hist = pd.DataFrame([
        {"timestamp": at(1, 9), "room": "A", "status": "occupied",
         "people": 10},
        {"timestamp": at(1, 10), "room": "A", "status": "empty", "people": 0},
        {"timestamp": at(1, 12), "room": "B", "status": "occupied",
         "people": 2},
        {"timestamp": at(1, 15), "room": "B", "status": "empty", "people": 0},
        {"timestamp": at(1, 9), "room": "C", "status": "occupied",
         "people": 50}])
    ph = ev.person_hours_in_windows(hist, ["A", "B"],
                                    [(at(1, 0), at(0, 0))])
    check("person-hours: ten for an hour and two for three, other rooms not",
          ph == [16.0], ph)
    ph = ev.person_hours_in_windows(hist, ["A", "B"], [(at(1, 0), at(0, 0))],
                                    [[(at(1, 12), at(1, 13))]])
    check("only while the loop was watching", ph == [2.0], ph)
    table, _ = ev.daily_table(readings, METERS,
                              pd.DataFrame({"taken": [at(1)], "kwh": [90.0]}))
    check("solar typed in today sits on yesterday, beside its reading",
          table["solar"].notna().sum() == 1
          and table.loc[table["solar"].notna(), "day"].iloc[0]
          == (DAY - timedelta(days=2)).normalize(), table)

    # 24 Nov: every day 6 pm to 6 pm, read off a line through every
    # reading -- the Monday-morning one after the weekend too -- with the
    # weekend shared at its own average and marked an estimate.
    wk = pd.DataFrame([
        {"meter": "gf_basement", "taken": pd.Timestamp(t, tz="Asia/Karachi")
         .tz_convert("UTC").as_unit("us"), "reading": v, "units": None,
         "max_temp": None}
        for t, v in (("2026-11-19 17:55", 52801.0),
                     ("2026-11-20 17:45", 53003.0),
                     ("2026-11-23 09:30", 53268.0),
                     ("2026-11-23 18:00", 53276.0),
                     ("2026-11-24 18:00", 53422.0))])
    ds = ev.day_series(wk, METERS[METERS["code"] == "gf_basement"], None)
    got = {d.strftime("%a %d"): (round(u, 1), e, p) for d, u, e, p in
           zip(ds["day"], ds["gf_basement"], ds["gf_basement_est"],
               ds["gf_basement_part"])}
    check("a day is its reading's: Monday 6 pm to Tuesday 6 pm is Tuesday",
          got.get("Tue 24") == (146.0, False, False), got)
    check("Thursday 17:55 to Friday 17:45 is Friday",
          got.get("Fri 20") == (202.0, False, False), got)
    check("Friday evening to Monday morning is the weekend, Sat and Sun",
          (got.get("Sat 21"), got.get("Sun 22"))
          == ((132.5, True, False), (132.5, True, False)), got)
    check("Monday morning to evening is Monday, once, its daytime",
          got.get("Mon 23") == (8.0, False, True), got)
    check("the days add up to what the meter moved",
          round(ds["gf_basement"].sum(), 6) == 53422.0 - 52801.0,
          ds["gf_basement"].sum())
    # 25 Nov: "The last full day" is day_series' day -- not "Mon 23" over a
    # list saying 6 pm Monday to 6 pm Tuesday is Tuesday.
    last = ev.last_full_day(ds, ("gf_basement",))
    check("the last full day is Tuesday, whole (not Monday's daytime)",
          last is not None and last["day"].strftime("%a %d") == "Tue 24",
          last)
    check("and a weekend share or a part day is never the last full day",
          ev.last_full_day(ds[ds["day"] <= "2026-11-23"],
                           ("gf_basement",))["day"].strftime("%a %d")
          == "Fri 20")
    on = [d.strftime("%a") for d in ev.counted_as(
        pd.Timestamp("2026-11-20 17:45", tz="Asia/Karachi"),
        pd.Timestamp("2026-11-23 18:00", tz="Asia/Karachi"))]
    check("no Monday-morning reading: Friday evening to Monday evening is"
          " Saturday to Monday", on == ["Sat", "Sun", "Mon"], on)
    # The bill under way, the 7th to the 7th: so far as read, the days
    # before the first reading and the days to come at the usual weekday.
    rows = []
    for d in pd.date_range("2026-11-03", "2026-11-24", freq="D"):
        rows.append({"day": d, "gf_basement": 100.0 if d.dayofweek < 5
                     else 40.0, "gf_basement_est": False,
                     "gf_basement_part": False})
    cyc_ds = pd.DataFrame(rows)
    cyc_ds = cyc_ds[cyc_ds["day"] >= "2026-11-10"]
    rate_bills = pd.DataFrame([{"meter": "gf_basement",
                                "period_start": "2026-10-01",
                                "period_end": "2026-10-31", "units": 1000.0,
                                "amount_rs": 80000.0}])
    cyc = ev.cycle_estimate(cyc_ds, METERS[METERS["code"] == "gf_basement"],
                            rate_bills, pd.Timestamp("2026-11-24 22:00"))
    # read 10-24 Nov: 11 working days and 4 weekend days (1,260); before,
    # Sat 7, Sun 8, Mon 9 (180); to come, 25 Nov - 6 Dec: 8 and 4 (960)
    check("the bill 7 Nov to 7 Dec: as read, before and to come by weekday",
          (cyc["start"].strftime("%d %b"), cyc["end"].strftime("%d %b"),
           round(cyc["so_far"]), round(cyc["before"]),
           round(cyc["to_come"]), round(cyc["rs"]))
          == ("07 Nov", "07 Dec", 1260, 180, 960, 192000), cyc)
    tiles_html = ev.daily_history("light", ds, {}, "gf_basement", None)
    shape = (tiles_html.count('<div class="d'),
             tiles_html.count('<div class="d we'),
             tiles_html.index("<span>Tue</span>")
             > tiles_html.index("<span>Mon</span>"))
    check("the chart: a column a day, weekends shaded, the newest last",
          shape == (len(ds), 2, True), shape)
    two = pd.DataFrame([
        {"meter": m, "period_start": s, "period_end": e, "units": u,
         "amount_rs": 1.0}
        for m, s, e, u in (("gf_basement", "2026-10-01", "2026-10-31", 9300),
                           ("first_cafe", "2026-10-01", "2026-10-31", 6200),
                           ("gf_basement", "2026-09-01", "2026-09-30", 9000))])
    per_day = [(lab, round(v)) for lab, v in ev.bill_per_day(two, METERS)]
    check("a bill as units a day, both meters together",
          per_day == [("Last bill, Oct 2026", 500)], per_day)

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

    # ---- 20 Nov: the live meters table has no sanctioned loads ------------
    bare = METERS.drop(columns=["sanctioned_kw"])
    six = pd.DataFrame([
        {"meter": "first_cafe", "period_start": "2026-%02d-01" % m,
         "period_end": "2026-%02d-28" % m, "units": u, "amount_rs": u * 70.0}
        for m, u in ((3, 2130), (4, 2868), (5, 5044), (6, 3277), (7, 41145),
                     (8, 6332), (9, 5986), (10, 7440))])
    flagged = ev.month_bills(six, bare)
    check("without a sanctioned load, a month at many times the usual is "
          "still marked", list(flagged[flagged["impossible"]]["month"])
          == ["Jul 26"], list(flagged[flagged["impossible"]]["month"]))

    # ---- solar, before and after ------------------------------------------
    sb = pd.DataFrame(
        [{"meter": k, "period_start": "2026-10-01", "period_end": "2026-10-31",
          "units": u, "amount_rs": u * 70.0}
         for k, u in (("gf_basement", 11623), ("first_cafe", 7440))])
    days = pd.date_range("2026-11-09", periods=9, tz="Asia/Karachi")
    st = pd.DataFrame({"day": days, "gf_basement": [170.0] * 9,
                       "first_cafe": [210.0] * 9,
                       "solar": [240.0] * 9})
    eff = ev.solar_effect(sb, st, METERS)
    check("before is the last bill before the panels, a day at a time",
          eff and round(eff["gf_before"]) == 375, eff)
    check("after is the readings since",
          eff and eff["gf_after"] == 170.0 and eff["days"] == 9, eff)
    check("the first floor, with no panels, says what the weather did",
          eff and round(eff["expected"]) == round(11623 / 31 * 210 / 240.0),
          eff)
    card = ev.solar_before_after("dark", eff, sb, METERS, 67.0)
    check("the card says the date is assumed until it is written down",
          "solar_since" in card and "Since 9 Nov" in card, card[:200])
    later = ev.solar_effect(sb, st, METERS, "2026-11-12")
    check("a date written down moves 'after' to it",
          later and later["days"] == 6 and not later["assumed"], later)
    check("no bill before the panels, no card",
          ev.solar_effect(sb.iloc[0:0], st, METERS) is None)
    # 140-H's: up on 1 Oct, on test all October, 63.85 kW.
    sep = pd.concat([sb.assign(period_start="2026-09-01",
                               period_end="2026-09-30",
                               units=[10430, 5986]), sb])
    real = ev.solar_effect(sep, st, METERS, "2026-10-01", "2026-11-01", 63.85)
    check("with a test month, before is the month before the panels",
          real and real["month"].month == 9 and not real["assumed"], real)
    check("and each kW's day is the array's day over its size",
          real and abs(real["yield"] - 240 / 63.85) < 0.01, real)
    page = ev.solar_before_after("dark", real, sep, METERS, 67.0)
    check("October is drawn, marked as the test",
          ">test<" in page and "on test until 31 October" in page)
    est = {"meters": {"gf_basement": 170.0, "first_cafe": 210.0},
           "to": pd.Timestamp("2026-11-18 11:00", tz="UTC")}
    bill = ev.month_bill_page(est, METERS, sep)
    check("this month's bill: each meter at its own rate, 30 November days",
          "5,100 units" in bill and "6,300 units" in bill
          and "October: 11,623 units" in bill, bill[:300])

    # ---- two years of bills: the switch, the totals, the hover -------------
    two = pd.DataFrame([
        {"meter": k, "period_start": "%d-%02d-01" % (y, m),
         "period_end": "%d-%02d-28" % (y, m), "units": u, "amount_rs": u * 70}
        for y in (2025, 2026) for m in range(1, 13)
        for k, u in (("gf_basement", 10000 if y == 2025 else 9000),
                     ("first_cafe", 4000))])
    page = ev.meters_page("dark", None, "daily", METERS, two, None, 67.0, [],
                          True, "140-H")
    check("a year switch when there are two years of bills",
          'id="enyr-a"' in page and "Both years" in page
          and "Jan 25 – Dec 25" in page, page[-600:])
    check("each year's total, and this year against the last",
          "156,000 units" in page and "168,000 units" in page
          and "units <b>−7%</b>" in page)
    check("hovering a month gives each meter and the month's total",
          "Total 13,000 units, Rs 910,000" in page)
    check("the year switch offers this year, the year before and both",
          [k for k, _ in ev.bill_years(two, METERS)] == ["a", "b", "c"]
          and ev.bill_years(two, METERS)[1][1] == "Jan 25 – Dec 25")
    last = ev.bills_section("dark", two, METERS, "b")
    check("a year chosen on the page draws that year, with no HTML switch",
          'id="enyr-' not in last and "168,000 units" in last
          and "Jan 2025" in last and "Dec 2026" not in last, last[:300])
    check("and every month of it in figures, the month's total and bill",
          last.split("Month by month, year by year")[0].count("<tr") == 13
          and "<b>14,000</b>" in last
          and "Rs 980,000" in last)
    yoy = ev.meters_page("dark", None, "daily", METERS, two, None, 67.0, [],
                         True, "140-H",
                         expected=(pd.Timestamp("2027-01-01"), 6500, 455000))
    check("each month with a column for every year",
          "Month by month, year by year" in yoy
          and "March · 2025: 14,000 units, Rs 980,000 · 2026: 13,000 units"
          in yoy)
    check("the month under way, expected, dashed, beside the years before",
          "2027: 6,500 units, Rs 455,000 (expected)" in yoy
          and "stroke-dasharray" in yoy and "~6,500*" in yoy)
    check("and the years in figures, with each year's total",
          "<th>2025</th><th>2026</th><th>2027</th>" in yoy
          and "<b>168,000</b>" in yoy and "12 months" in yoy)

    # ---- the charts on a phone -------------------------------------------
    small = ev.columns(["a", "b", "c"], [[0.3], [1.15], [0.8]], ["#000"],
                       ["", "", ""])
    tops = [float(v) for v in re.findall(r'class="yt" style="top:([\d.]+)%',
                                         small)]
    check("a scale under one still reaches above the tallest column",
          ev._nice(1.2)[1] >= 1.2 and min(tops) == 0.0, ev._nice(1.2))
    twelve = ev.columns(["d%d" % i for i in range(12)], [[1]] * 12, ["#000"],
                        [""] * 12)
    shown = re.findall(r'class="xt( alt)?"[^>]*>([^<]+)<', twelve)
    check("every other label drops on a phone, never the newest",
          shown[-1] == ("", "d11") and any(a for a, _ in shown)
          and not any(a and b == "d11" for a, b in shown), shown)

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

    # Units an hour, reading to reading (17 Nov): the weekend and Monday's
    # day apart, both meters side by side.
    t = lambda s: pd.Timestamp(s, tz="Asia/Karachi").tz_convert("UTC")  # noqa
    rd = pd.DataFrame([
        {"meter": m, "taken": t(w), "reading": v, "units": None,
         "max_temp": None}
        for m, w, v in (("gf", "2026-11-13 17:56", 51908),
                        ("ff", "2026-11-13 17:56", 33513),
                        ("gf", "2026-11-16 11:00", 52213),
                        ("ff", "2026-11-16 11:00", 33868),
                        ("gf", "2026-11-16 17:30", 52253),
                        ("ff", "2026-11-16 17:30", 33985))])
    ms = pd.DataFrame([{"code": "gf", "label": "Ground floor",
                        "behind_solar": True},
                       {"code": "ff", "label": "First floor",
                        "behind_solar": False}])
    spans = ev.pace(rd, ms)
    check("pace: two stretches, both meters in each",
          [sorted(s["units"].items()) for s in spans]
          == [[("ff", 355.0), ("gf", 305.0)], [("ff", 117.0), ("gf", 40.0)]],
          spans)
    page = ev.pace_page("light", rd, ms, 67)
    check("pace: the weekend and the day named",
          "incl. weekend" in page and "daytime" in page)

    # A day, and the month it makes (17 Nov).
    est = ev.month_estimate(rd, ms, (67, 81), (18.5, 22.5))
    hours = (t("2026-11-16 17:30") - t("2026-11-13 17:56")).total_seconds() \
        / 3600
    check("month: units a day from first to last reading, both meters",
          est and abs(est["per_day"] - (345 + 472) / hours * 24) < 1e-6
          and abs(est["month"] - est["per_day"] * 30) < 1e-6, est)
    check("month: peak is the 4 evening hours' share, at the peak rate",
          abs(est["peak_units"] - est["month"] / 6) < 1e-6
          and abs(est["rs"] - (est["month"] * 5 / 6 * 67
                               + est["month"] / 6 * 81)) < 1e-3, est)
    page = ev.month_page("light", est, ms, (67, 81))
    check("month: the card names the bill and the split",
          "bill, about" in page and "Off-peak" in page
          and not re.search(r">\s*(None|nan|NaT)\s*<", page))
    check("month: one reading is no estimate",
          ev.month_estimate(rd.iloc[:2], ms, (67, 81)) is None)

    print()
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
