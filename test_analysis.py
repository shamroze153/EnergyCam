"""Checks on the analysis arithmetic.

The money on this page is the end of a chain -- cameras, to minutes, to
hours split by tariff, to rupees -- and every link multiplies the one
before. A mistake anywhere comes out the far end as a confident number with
a currency symbol on it, which is the hardest kind of error to doubt.
"""
import sys

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
    return pd.Timestamp(s, tz="UTC")


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
    if FAILURES:
        print("%d FAILURE(S):" % len(FAILURES))
        for line in FAILURES:
            print("  %s" % line)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
