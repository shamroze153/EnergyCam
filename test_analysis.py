"""Checks on the analysis arithmetic.

The money on this page is the end of a chain -- cameras, to minutes, to
hours split by tariff, to rupees -- and every link multiplies the one
before. A mistake anywhere comes out the far end as a confident number with
a currency symbol on it, which is the hardest kind of error to doubt.
"""
import sys

from decimal import Decimal

import pandas as pd

import analysis_view as av

WINDOW = (18.5, 22.5)
ASSUME = {"unit_kw": 1.2, "tariff_rs_per_kwh": 67, "peak_rs_per_kwh": 81,
          "peak_start": "18:30", "peak_end": "22:30"}
FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s" % ("OK" if ok else "FAIL", label))
    if not ok:
        FAILURES.append("%s: got %r, wanted %r" % (label, got, want))


def T(s):
    # Karachi's clock: the peak window is K-Electric's 18:30-22:30 here.
    # These used to be UTC, which is how the tests agreed with a page that
    # counted 23:30-03:30 as the peak.
    return pd.Timestamp(s, tz="Asia/Karachi")



def check_bill_columns():
    """Every column the analysis page reads must exist on the frame it gets.

    The page took its bills from meters_view.load and asked for a `month`
    column, which only analysis_view.load_bills ever added. Two loaders,
    one shape expected, and the difference surfaced as a KeyError halfway
    down an already-rendered page -- after the headline figures, so it
    looked like the bills were broken rather than the frame.

    The columns the page reads are taken from its source rather than
    written out here, so a new one cannot be added without this noticing.
    """
    import re

    import analysis_view as av

    source = open("rooms_dashboard.py", encoding="utf-8").read()
    start = source.index("def show_analysis")
    end = source.index("\ndef ", start + 10)
    body = source[start:end]
    wanted = set(re.findall(r'bills\["(\w+)"\]', body))
    wanted |= set(re.findall(r'drop_duplicates\("(\w+)"\)', body))
    wanted |= set(re.findall(r'(?:index|columns|values)="(\w+)"', body))
    wanted |= set(re.findall(r'b\["(\w+)"\]', body))

    # Exactly the columns meters_view.load selects, before enrichment.
    raw = pd.DataFrame({
        "meter": ["first_cafe", "gf_basement"],
        "period_start": ["2026-09-01", "2026-10-01"],
        "period_end": ["2026-09-30", "2026-10-31"],
        "units": [5986, 11623],
        "amount_rs": [Decimal("594336.61"), Decimal("887174.92")],
    })
    have = set(av.enrich_bills(raw).columns)
    missing = sorted(wanted - have)
    check("the analysis page's bill columns all exist", missing, [])

    # And the pivot the page builds must actually build.
    rich = av.enrich_bills(raw)
    wide = rich.pivot_table(index="month", columns="meter", values="units",
                            aggfunc="sum")
    check("the bills chart pivots", sorted(wide.columns),
          ["first_cafe", "gf_basement"])
    check("one row per month", len(wide), 2)

    check("enriching twice changes nothing",
          list(av.enrich_bills(rich).columns), list(rich.columns))
    check("and an empty frame is left alone",
          av.enrich_bills(pd.DataFrame()).empty, True)

    # meters_view.load must be the one that hands them over enriched, or
    # the page is back where it started.
    loader = open("meters_view.py", encoding="utf-8").read()
    check("meters_view hands its bills over enriched",
          "enrich_bills(bills)" in loader, True)


def main():
    check("the window is read from the assumptions",
          av.peak_window(ASSUME), (18.5, 22.5))
    check("and falls back when it is missing",
          av.peak_window({}), (18.5, 22.5))

    print("\n-- splitting an interval against the tariff")
    for label, a, b, off, peak in (
            ("an afternoon", "2026-11-10 14:00", "2026-11-10 17:00", 180, 0),
            ("inside peak", "2026-11-10 19:00", "2026-11-10 21:00", 0, 120),
            ("across the start", "2026-11-10 18:00", "2026-11-10 19:30", 30, 60),
            ("into the night", "2026-11-10 19:00", "2026-11-11 02:00", 210, 210),
            ("Friday to Monday", "2026-11-06 19:00", "2026-11-09 09:00",
             3030, 690)):
        got = av.split_peak(T(a), T(b), WINDOW)
        check(label, tuple(round(v) for v in got), (off, peak))
    # The property that matters more than any single case.
    for a, b in (("2026-11-10 08:00", "2026-11-14 11:00"),
                 ("2026-11-10 22:00", "2026-11-10 23:00")):
        off, peak = av.split_peak(T(a), T(b), WINDOW)
        total = (T(b) - T(a)).total_seconds() / 60
        check("the two halves add back to the whole (%s)" % a[-5:],
              round(off + peak), round(total))
    utc = pd.Timestamp("2026-11-10 14:00", tz="UTC")       # 19:00 here
    check("a UTC timestamp is read on Karachi's clock",
          tuple(round(v) for v in av.split_peak(
              utc, utc + pd.Timedelta(hours=1), WINDOW)), (0, 60))
    check("an interval that ends before it starts is nothing",
          av.split_peak(T("2026-11-10 12:00"), T("2026-11-10 09:00"), WINDOW),
          (0.0, 0.0))

    print("\n-- which rooms count")
    now = T("2026-11-10 23:00")

    def ago(h):
        return now - pd.Timedelta(hours=h)

    recent = pd.DataFrame([
        {"timestamp": ago(6), "room": "Marketing", "status": "empty",
         "people": 0, "ac_state": None},
        {"timestamp": ago(6), "room": "Wellows", "status": "empty",
         "people": 0, "ac_state": "off"},
        {"timestamp": ago(6), "room": "Admin Room", "status": "occupied",
         "people": 2, "ac_state": "on"},
        {"timestamp": ago(6), "room": "H Stairs", "status": "empty",
         "people": 0, "ac_state": None},
    ])
    recent["timestamp"] = pd.to_datetime(recent["timestamp"], utc=True)
    cooled = ["Marketing", "Wellows", "Admin Room"]       # H Stairs has no unit

    off, peak = av.cooled_while_empty(recent, cooled, ago(24), now, WINDOW)
    check("only the room that was empty with an unread unit counts",
          (round(off), round(peak)), (120, 240))

    only_off = av.cooled_while_empty(recent, ["Wellows"], ago(24), now, WINDOW)
    check("a unit known to be OFF is not waste", tuple(round(v) for v in
                                                       only_off), (0, 0))
    busy = av.cooled_while_empty(recent, ["Admin Room"], ago(24), now, WINDOW)
    check("an occupied room is not waste", tuple(round(v) for v in busy),
          (0, 0))
    none = av.cooled_while_empty(recent, [], ago(24), now, WINDOW)
    check("no rooms, no minutes", tuple(round(v) for v in none), (0, 0))

    # Empty 17:00-23:00 on a Tuesday; the working day ends at 20:00.
    hours = {"operations": {"days": ["mon", "tue", "wed", "thu", "fri"],
                            "start": "10:00", "end": "20:00"}}
    work = av.cooled_while_empty(recent, ["Marketing"], ago(24), now, WINDOW,
                                 hours, "working")
    after = av.cooled_while_empty(recent, ["Marketing"], ago(24), now, WINDOW,
                                  hours, "after")
    check("working hours: 17:00 to 20:00, 90 min of it in the peak",
          tuple(round(v) for v in work), (90, 90))
    check("after hours: 20:00 to 23:00, 150 min of it in the peak",
          tuple(round(v) for v in after), (30, 150))
    check("and the two add back to the whole",
          round(sum(work) + sum(after)), 360)

    print("\n-- turning hours into money")
    off_kwh, peak_kwh, rupees = av.money(120, 240, ASSUME)
    check("off-peak kWh", round(off_kwh, 2), 2.4)
    check("peak kWh", round(peak_kwh, 2), 4.8)
    check("rupees at the marginal rates", round(rupees), 550)
    check("a peak hour costs more than an off-peak one",
          av.money(0, 60, ASSUME)[2] > av.money(60, 0, ASSUME)[2], True)
    check("no hours, no money", av.money(0, 0, ASSUME)[2], 0.0)

    print("\n-- the bills")
    meters = pd.DataFrame([{"code": "first_cafe", "sanctioned_kw": 37.0},
                           {"code": "gf_basement", "sanctioned_kw": 19.0}])
    bills = pd.DataFrame([
        {"meter": "first_cafe", "period_start": "2026-07-01",
         "period_end": "2026-07-31", "units": 41145, "amount_rs": 2731004.20},
        {"meter": "first_cafe", "period_start": "2026-08-01",
         "period_end": "2026-08-31", "units": 6332, "amount_rs": 474510.95},
        {"meter": "gf_basement", "period_start": "2026-10-01",
         "period_end": "2026-10-31", "units": 11623, "amount_rs": 887174.92},
    ])
    bad = av.impossible_months(bills, meters)
    check("July is flagged as impossible", list(bad["units"]), [41145])
    check("and nothing else is", len(bad), 1)

    rate, months = av.tariff_from_bills(bills, True, meters)
    clean = bills[bills["units"] != 41145]
    want = clean["amount_rs"].sum() / clean["units"].sum()
    check("the tariff leaves the impossible month out",
          round(rate, 2), round(want, 2))
    check("and says how many months it used", months, 2)
    check("with no meters given, nothing is excluded",
          av.tariff_from_bills(bills, False)[1], 3)
    check("no bills, no rate", av.tariff_from_bills(
        pd.DataFrame(columns=["meter", "units", "amount_rs"]))[0], None)

    print()
    check_bill_columns()

    if FAILURES:
        print("%d FAILURE(S):" % len(FAILURES))
        for line in FAILURES:
            print("  %s" % line)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
