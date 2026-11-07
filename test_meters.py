"""Checks on the meter arithmetic.

Two mistakes would be easy here and both would be invisible. Turning a
replaced meter into a negative day's consumption, which then drags an
average down and looks like a saving. And publishing a kWh-per-hour figure
off a fortnight of readings, which is mostly a figure about the weather.
"""
import sys

import pandas as pd

import meters_view

FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s" % ("OK" if ok else "FAIL", label))
    if not ok:
        FAILURES.append("%s: got %r, wanted %r" % (label, got, want))


def at(day, hour=11):
    return pd.Timestamp("2026-11-%02d %02d:00" % (day, hour), tz="UTC")


def readings(rows):
    df = pd.DataFrame(rows)
    df["taken"] = pd.to_datetime(df["taken"], utc=True)
    for col in ("reading", "units", "max_temp"):
        if col not in df:
            df[col] = None
    return df


def main():
    # Cumulative readings become the difference between them.
    df = readings([
        {"meter": "gf", "taken": at(1), "reading": 1000},
        {"meter": "gf", "taken": at(2), "reading": 1120},
        {"meter": "gf", "taken": at(3), "reading": 1265},
    ])
    out = meters_view.daily_units(df)
    check("two periods from three readings", len(out), 2)
    check("and the units are the steps between them",
          [round(u) for u in out["units"]], [120, 145])
    check("each period is a day long", [round(h) for h in out["hours"]],
          [24, 24])

    # Units given straight are taken as they are.
    df = readings([
        {"meter": "first", "taken": at(1), "units": 90},
        {"meter": "first", "taken": at(2), "units": 95},
    ])
    out = meters_view.daily_units(df)
    check("units given directly are used as given",
          [round(u) for u in out["units"]], [95])

    # A meter that went backwards is a replaced meter or a typo. Either way
    # it is not a day on which the building generated electricity.
    df = readings([
        {"meter": "gf", "taken": at(1), "reading": 5000},
        {"meter": "gf", "taken": at(2), "reading": 5100},
        {"meter": "gf", "taken": at(3), "reading": 40},     # replaced
        {"meter": "gf", "taken": at(4), "reading": 160},
    ])
    out = meters_view.daily_units(df)
    check("a backwards step produces no period",
          all(u >= 0 for u in out["units"]), True)
    check("and the days either side still count",
          [round(u) for u in out["units"]], [100, 120])

    # The derived figure is withheld until there is enough behind it.
    figure, days, why = meters_view.per_hour([100] * 10, [50] * 10)
    check("a fortnight gives no figure", figure, None)
    check("and says how many days it has", days, 10)
    check("and why it is holding back", "weather" in why, True)

    figure, days, why = meters_view.per_hour([100] * 30, [50] * 30)
    check("a month gives one", round(figure, 2), 2.0)
    check("with no caveat attached", why, None)

    # Days with nothing to compare against must not drag the slope to zero.
    figure, _, _ = meters_view.per_hour([100] * 30 + [80] * 5,
                                        [50] * 30 + [0] * 5)
    check("a day when no room was empty and cooled is left out",
          round(figure, 2), 2.0)

    # The tariff comes off the bills, not off the assumption.
    bills = pd.DataFrame([
        {"meter": "gf", "period_start": "2026-10-01",
         "period_end": "2026-10-31", "units": 4000, "amount_rs": 240000},
        {"meter": "gf", "period_start": "2026-09-01",
         "period_end": "2026-09-30", "units": 4000, "amount_rs": 200000},
    ])
    rate, count = meters_view.tariff_from_bills(bills)
    check("the rate is the total over the total, not an average of averages",
          round(rate, 2), 55.0)
    check("and says how many bills it rests on", count, 2)
    check("no bills, no rate", meters_view.tariff_from_bills(
        pd.DataFrame(columns=["meter", "units", "amount_rs"]))[0], None)

    check("no readings, no periods", len(meters_view.daily_units(
        pd.DataFrame(columns=["meter", "taken", "reading", "units",
                              "max_temp"]))), 0)

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
