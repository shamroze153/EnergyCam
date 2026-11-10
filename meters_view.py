"""The two meters, beside what this system thinks was wasted.

The point of this page is a comparison nobody can make yet and everybody
will want to: on the left, units the building actually drew; on the right,
the hours rooms sat empty with their cooling on. Neither explains the other
on its own, and the page is built to make that plain rather than to imply a
causation it cannot show.

Three things keep it honest.

The GF + basement meter has solar behind it. Its units are what came from
the grid after the panels, so a bright day reads low for reasons that have
nothing to do with anybody switching anything off. Any figure drawn from
that meter alone carries the warning; the first floor + cafe meter does not
need it.

A reading is taken by a person at roughly the same hour, not at midnight, so
a "day" here runs from one reading to the next. The occupancy hours set
beside it are counted over exactly that window, not over the calendar day,
or the night -- the part worth measuring -- would be split across two
numbers.

And the derived figure, kWh per empty-and-cooled hour, is the one that would
replace the guess in rooms.yaml. It is not shown until there is enough to
support it, and when it is shown it says how many days it rests on.
"""
import pandas as pd

# Below this the line through the points is a line through noise. Four weeks
# of daily readings is the first point at which a week of bad weather stops
# dominating the answer.
ENOUGH_DAYS = 24

# A sanity bound that comes from the connection rather than from a guess:
# 19 kW cannot draw more than 456 units in a day and 37 kW cannot draw more
# than 888, whatever happens in the building. Anything above is arithmetic
# that has gone wrong somewhere upstream, and should be shown as a problem
# rather than averaged in.
def impossible(units, sanctioned_kw, hours):
    if not sanctioned_kw or not hours:
        return False
    return float(units) > float(sanctioned_kw) * float(hours) * 1.02


def load(conn, days=120):
    """Readings, bills and the meters themselves."""
    meters = pd.read_sql_query("SELECT * FROM meters ORDER BY code", conn)
    readings = pd.read_sql_query(
        "SELECT meter, taken, reading, units, max_temp, note"
        " FROM meter_readings WHERE taken >= now() - interval '%d days'"
        " ORDER BY meter, taken" % days, conn)
    bills = pd.read_sql_query(
        "SELECT meter, period_start, period_end, units, amount_rs"
        " FROM meter_bills ORDER BY period_end DESC", conn)
    if not readings.empty:
        readings["taken"] = pd.to_datetime(readings["taken"], utc=True)
    return meters, readings, bills


def daily_units(readings):
    """Units per reading period, whichever way the number was given.

    A cumulative reading is differenced against the one before it; units
    given directly are taken as they are. A meter that went backwards is
    dropped rather than turned into a negative day: that is a replaced meter
    or a mistyped digit, and either way it is not consumption.
    """
    if readings.empty:
        return pd.DataFrame(columns=["meter", "from", "to", "units",
                                     "hours", "max_temp"])
    out = []
    for meter, rows in readings.groupby("meter"):
        rows = rows.sort_values("taken")
        prior_time = prior_reading = None
        for _, r in rows.iterrows():
            units = r["units"]
            if units is None or pd.isna(units):
                if prior_reading is None or pd.isna(r["reading"]):
                    prior_time, prior_reading = r["taken"], r["reading"]
                    continue
                units = float(r["reading"]) - float(prior_reading)
            if prior_time is None or units is None or pd.isna(units) \
                    or float(units) < 0:
                prior_time, prior_reading = r["taken"], r["reading"]
                continue
            out.append({
                "meter": meter, "from": prior_time, "to": r["taken"],
                "units": float(units),
                "hours": (r["taken"] - prior_time).total_seconds() / 3600.0,
                "max_temp": (None if pd.isna(r["max_temp"])
                             else float(r["max_temp"])),
            })
            prior_time, prior_reading = r["taken"], r["reading"]
    return pd.DataFrame(out)


def wasted_hours_between(recent, rooms_on_meter, start, end, status_minutes):
    """Hours rooms on this meter sat empty with the cooling on, in a window.

    Counted from the events over exactly the reading window, because the
    reading is taken at eleven in the morning and a calendar day would cut
    the night in half.
    """
    total = 0.0
    for room in rooms_on_meter:
        totals = status_minutes(recent, room, start, end)
        total += totals.get("empty", 0.0)
    return total / 60.0


def per_hour(periods, hours_by_period):
    """Units per empty-and-cooled hour, if there is enough to say.

    Returns (figure, days, why_not). The figure is what would replace the
    1.2 kW guess in rooms.yaml, and it is withheld rather than estimated
    from a fortnight, because a fortnight of this is mostly weather.
    """
    usable = [(u, h) for u, h in zip(periods, hours_by_period)
              if h and h > 0 and u and u > 0]
    if len(usable) < ENOUGH_DAYS:
        return None, len(usable), ("%d days of readings; the figure is held"
                                   " back until %d, because less than that is"
                                   " mostly weather"
                                   % (len(usable), ENOUGH_DAYS))
    # The slope through the origin: total units against total hours. A full
    # regression would also need a temperature term, and until that is in the
    # data this is the honest version of the same question.
    units = sum(u for u, _ in usable)
    hours = sum(h for _, h in usable)
    return units / hours, len(usable), None


def tariff_from_bills(bills):
    """Rupees per unit, from the bills rather than from the assumption."""
    if bills.empty:
        return None, None
    recent = bills.head(3)
    units = recent["units"].astype(float).sum()
    amount = recent["amount_rs"].astype(float).sum()
    if units <= 0:
        return None, None
    return amount / units, len(recent)
