"""Check the savings scoreboard, the peak hours and the weekly report.

    python test_savings.py
"""
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

import energy_rooms as er
import ledger_data as ld
import savings
import weekly_report as wr

PKT = timezone(timedelta(hours=5))
FAILURES = []
RATES = (67.0, 81.0)
WINDOW = (18.5, 22.5)


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def at(h, m=0, day=12):
    return (pd.Timestamp(2026, 11, day).tz_localize(PKT)
            + pd.Timedelta(hours=h, minutes=m)).tz_convert("UTC")


def row(name, waste=0.0, rs=100.0, peak=0.0, peak_waste=0.0, over=0.0,
        watched=24.0, basis=er.READ):
    return {"room": name, "rs": rs, "kwh": rs / 67.0, "waste_rs": waste,
            "waste_kwh": waste / 67.0, "over_rs": over, "over_kwh": 0.0,
            "peak_rs": peak, "peak_kwh": peak / 81.0,
            "peak_waste_rs": peak_waste, "measured_kwh": 0.0,
            "empty_on_h": 0.0, "watched_h": watched, "building": "140-H",
            "basis": basis, "read": 1, "units": 1, "hourly": None}


def day(n, rows, so_far=False):
    return (pd.Timestamp(2026, 11, n).date(), rows, so_far)


def main():
    # ---- the peak hours in the ledger (energy_rooms) ------------------
    # One 1.2 kW unit on 18:00-20:00 with people in, then 20:00-21:00 with
    # nobody in: 1.5 h of the first and all of the second are peak hours.
    ev = pd.DataFrame([
        {"timestamp": at(0), "room": "R", "status": "empty", "people": 0,
         "ac_state": "off", "ac_units_on": 0},
        {"timestamp": at(18), "room": "R", "status": "occupied", "people": 3,
         "ac_state": "on", "ac_units_on": 1},
        {"timestamp": at(20), "room": "R", "status": "empty", "people": 0,
         "ac_state": "on", "ac_units_on": 1},
        {"timestamp": at(21), "room": "R", "status": "empty", "people": 0,
         "ac_state": "off", "ac_units_on": 0}])
    cfg = {"room": "R", "has_unit": True, "alerts": True, "ac_count": 1,
           "unit_kw": 1.2, "floor": "", "dept": "", "tons_total": 1.0}
    r = er.room_day(ev, cfg, at(0), at(24), [(at(0), at(24))], 1, RATES,
                    WINDOW, None)
    check("peak kWh: 18:30 to 21:00 of a 1.2 kW unit",
          round(r["peak_kwh"], 3), round(2.5 * 1.2, 3))
    check("peak rupees at the peak rate", round(r["peak_rs"], 2),
          round(2.5 * 1.2 * 81, 2))
    check("of which nobody in: 20:00-21:00", round(r["peak_waste_rs"], 2),
          round(1.2 * 81, 2))
    check("the day's rupees still hold the half hour before the peak",
          round(r["rs"], 2), round(0.5 * 1.2 * 67 + 2.5 * 1.2 * 81, 2))
    t = er.totals([r, r])
    check("totals add the peak up", round(t["peak_rs"], 2),
          round(2 * 2.5 * 1.2 * 81, 2))
    avg = er.average([[r], [dict(r, peak_rs=0.0)]])
    check("and an average day halves it", round(avg[0]["peak_rs"], 2),
          round(2.5 * 1.2 * 81 / 2, 2))
    # The ledger says how much of the peak the cameras saw: beats every
    # five minutes until 19:55, as on 17 Nov.
    beats = [at(0) + pd.Timedelta(minutes=5 * i) for i in range(240)]
    led = er.ledger(ev, pd.DataFrame([cfg]), at(0), at(24), beats, {"R": 1},
                    RATES, WINDOW)
    seen = led[0]["watched_peak_h"]
    check("the ledger keeps the peak hours watched: about 1.5 of 4",
          1.3 <= seen <= 1.7, True)

    # ---- the scoreboard -------------------------------------------------
    before = [day(n, [row("A", waste=200), row("B", waste=100)])
              for n in range(1, 8)]
    this = [day(n, [row("A", waste=100), row("B", waste=50, over=50)])
            for n in range(8, 15)]
    today = [day(15, [row("A", waste=999)], so_far=True)]
    sb = savings.scoreboard(before + this + today)
    check("this week is the last seven finished days, not today",
          [d[0].day for d in sb["this"]], list(range(8, 15)))
    check("could save a day: waste plus too many units",
          (sb["save"]["now"], sb["save"]["before"]), (200.0, 300.0))
    check("a third better", round(sb["save"]["change"], 1), -33.3)
    part = [day(8, [row("A", waste=5000, watched=6)])] + this[1:]
    check("a day the cameras saw six hours of is not a usual day",
          savings.scoreboard(before + part)["save"]["days"], 6)
    check("no week before: no change, said as such",
          savings.scoreboard(this)["save"]["change"], None)
    # 17 Nov: twenty hours watched, a whole day -- but the laptop slept at
    # 19:56, an hour and a half into the four peak hours.
    slept = day(14, [dict(row("A", peak=300), watched_h=20.0,
                          watched_peak_h=1.43)])
    check("a day whose peak hours were slept through is no peak day",
          (savings.whole(slept), savings.peak_whole(slept, WINDOW)),
          (True, False))
    check("a day with all four peak hours seen is",
          savings.peak_whole(day(13, [dict(row("A"), watched_peak_h=4.0)]),
                             WINDOW), True)
    peaky = [day(n, [dict(row("A", peak=800), watched_peak_h=4.0)])
             for n in range(7, 14)] + [slept]
    check("so the usual peak day leaves it out",
          savings.scoreboard(peaky, window=WINDOW)["peak"]["now"], 800.0)
    check("and the peak page marks it",
          "1.4h of 4 seen" in savings.peak_page("light", peaky, RATES,
                                                WINDOW), True)

    bills = pd.DataFrame([
        {"meter": "a", "period_start": "2026-10-01", "period_end":
         "2026-10-31", "units": 310.0, "amount_rs": 1.0},
        {"meter": "b", "period_start": "2026-10-01", "period_end":
         "2026-10-31", "units": 310.0, "amount_rs": 1.0},
        {"meter": "a", "period_start": "2025-11-01", "period_end":
         "2025-11-30", "units": 300.0, "amount_rs": 1.0},
        {"meter": "b", "period_start": "2025-11-01", "period_end":
         "2025-11-30", "units": 300.0, "amount_rs": 1.0},
        {"meter": "a", "period_start": "2026-09-01", "period_end":
         "2026-09-30", "units": 1.0, "amount_rs": 1.0}])
    base = savings.bill_baselines(bills, ["a", "b"], pd.Period("2026-11", "M"))
    check("the last bill and the same month a year ago, units a day",
          [(b["label"], round(b["per_day"], 1)) for b in base],
          [("Oct 2026", 20.0), ("Nov 2025", 20.0)])
    check("a month billed on only one meter is not a baseline",
          savings.bill_baselines(bills[bills["meter"] == "a"], ["a", "b"],
                                 pd.Period("2026-11", "M")), [])
    est = {"meters": {"a": 8.0, "b": 7.0}, "per_day": 15.0,
           "to": pd.Timestamp("2026-11-17 12:00", tz="UTC")}
    m = savings.scoreboard(this, est, bills)["meters"]
    check("meters: 15 a day against 20 is a quarter less",
          [round(b["change"]) for b in m["bills"]], [-25, -25])

    page = savings.scoreboard_page("light", savings.scoreboard(
        before + this, est, bills))
    check("scoreboard page: the week's total in red, the change in green",
          ("Rs 1,400" in page, "sv-chip good" in page,
           "Units a day, 140-H meters" in page), (True, True, True))
    check("and it says the meters fall with the weather too",
          "weather" in page, True)

    # ---- the peak page --------------------------------------------------
    week = [day(n, [row("Cafe", peak=810, peak_waste=81),
                    row("Hall", peak=0)]) for n in range(8, 15)]
    week[-1] = day(14, week[-1][1], so_far=True)
    pp = savings.peak_page("dark", week, RATES, WINDOW)
    check("peak page: the hours and rates in the heading",
          "6:30 pm to 10:30 pm, Rs 81 a unit (Rs 67" in pp, True)
    check("a usual day's peak cost", "Rs 810" in pp, True)
    check("six finished days in the room table, today shown apart",
          ("Rs 4,860" in pp, "so far" in pp), (True, True))
    check("a room with no AC in the peak hours is folded into one line",
          "1 more room ran no AC in the peak" in pp, True)
    check("clock: 18.5 is 6:30 pm, 22 is 10 pm",
          (savings.clock(18.5), savings.clock(22)), ("6:30 pm", "10 pm"))

    # ---- the weekly mail ------------------------------------------------
    mon = datetime(2026, 11, 23, 9, 5, tzinfo=PKT)
    check("due on Monday after nine", wr.due(mon, sent=None, to=["x"]),
          "2026-W48")
    check("not before nine", wr.due(mon.replace(hour=8), sent=None,
                                    to=["x"]), None)
    check("nor once sent that week", wr.due(mon, sent="2026-W48", to=["x"]),
          None)
    check("a laptop off on Monday sends it on Wednesday",
          wr.due(mon + timedelta(days=2), sent="2026-W47", to=["x"]),
          "2026-W48")
    check("nobody to send to, nothing due", wr.due(mon, sent=None, to=[]),
          None)
    meters = pd.DataFrame([{"code": "a", "label": "First"},
                           {"code": "b", "label": "Ground"}])
    est.update({"from": pd.Timestamp("2026-11-10 12:00", tz="UTC"),
                "month": 450.0, "rs": 30000.0, "off_units": 375.0,
                "peak_units": 75.0})
    data = {"sb": savings.scoreboard(before + this, est, bills),
            "rates": RATES, "window": WINDOW, "est": est, "meters": meters}
    subject, html, text = wr.compose(data)
    check("subject: the week and what could have been saved",
          subject, "EnergyCam weekly report, Sun 8 - Sat 14 Nov: Rs 1,400 "
          "could have been saved")
    check("mail: no SVG, no style sheet, no script -- mail-safe",
          ("<svg" in html, "<style" in html, "<script" in html),
          (False, False, False))
    check("mail: the sections are there",
          all(s in html for s in ("Could have been saved this week",
                                  "Peak hours, every room", "Day by day",
                                  "The 140-H meters", "Worth doing")), True)
    check("mail: nobody's address in it", "@" in html, False)
    check("text copy carries the figures", "Rs 1,400" in text and
          "Peak hours a day" in text, True)
    check("text copy has no markup left", "<" in text or "&nbsp;" in text,
          False)
    # A room no camera reads is a question, not a finding.
    guess = [day(n, [row("Room 18", waste=400, basis=er.ASSUMED)])
             for n in range(8, 15)]
    said = wr.tips({"sb": savings.scoreboard(guess), "rates": RATES})
    check("an unread room's tip asks rather than claims",
          "worth a look" in said[0] and "if its AC ran" in said[0], True)

    # ---- ledger_data reads rooms.yaml as the page always did ------------
    rooms = ld.rooms_frame()
    check("every room has a campus", set(rooms["campus"]) - {"unknown"},
          {"140-H", "141-C/D"})
    check("unit sizes: a list is the count", ld.unit_count(
        {"ac_tons": [2, 2], "ac_count": 9}), 2)

    print()
    if FAILURES:
        print("%d failed" % len(FAILURES))
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
