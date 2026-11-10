"""What the bills, the meters and the cameras say when put beside each other.

Three sources, and they are not equal. The bills are measured and settled.
The meter readings are measured and ours. What the cameras produce is a
count of people and, where a unit has been calibrated, whether it was
running -- turned into money through one assumption that has not yet been
replaced.

This file keeps those apart, because the whole value of the project rests on
not letting the third quietly wear the authority of the first.
"""
from datetime import time

import pandas as pd

# A reading is only ever as good as the hours a loop was running, so every
# figure here that comes from cameras is reported with the hours behind it.
MINUTES = 60.0


def peak_window(assumptions):
    """The time-of-use window, as hours past midnight."""
    def parse(text, fallback):
        try:
            hh, mm = str(text).split(":")
            return int(hh) + int(mm) / 60.0
        except Exception:                                   # noqa: BLE001
            return fallback
    return (parse(assumptions.get("peak_start"), 18.5),
            parse(assumptions.get("peak_end"), 22.5))


def split_peak(start, end, window):
    """Minutes of one interval inside and outside the peak window.

    An interval can run over midnight and over several days -- a room left
    cooled from Friday evening to Monday morning is one interval -- so this
    walks it a day at a time rather than assuming it fits in one.
    """
    low, high = window
    if end <= start:
        return 0.0, 0.0
    peak = 0.0
    day = start.normalize()
    while day < end:
        a = day + pd.Timedelta(hours=low)
        b = day + pd.Timedelta(hours=high)
        overlap = (min(end, b) - max(start, a)).total_seconds() / 60.0
        if overlap > 0:
            peak += overlap
        day += pd.Timedelta(days=1)
    total = (end - start).total_seconds() / 60.0
    return max(0.0, total - peak), min(peak, total)


def cooled_while_empty(recent, rooms, since, until, window):
    """Minutes rooms sat empty, split by whether the hour was peak.

    Only rooms with a unit that can be switched off, because a corridor's
    empty hours are not money. Where a unit has been calibrated and read as
    off, those minutes are left out: the room was empty and already dealt
    with, and counting it would invent waste that did not happen.
    """
    off_total = peak_total = 0.0
    wanted = set(rooms)
    for room, rows in recent[recent["room"].isin(wanted)].groupby("room"):
        rows = rows.sort_values("timestamp")
        stamps = list(rows["timestamp"]) + [until]
        states = list(rows["status"])
        acs = (list(rows["ac_state"]) if "ac_state" in rows.columns
               else [None] * len(states))
        for i, state in enumerate(states):
            if state != "empty":
                continue
            if acs[i] == "off":
                continue
            began, ended = max(stamps[i], since), min(stamps[i + 1], until)
            if ended <= began:
                continue
            off, peak = split_peak(began, ended, window)
            off_total += off
            peak_total += peak
    return off_total, peak_total


def money(off_minutes, peak_minutes, assumptions):
    """Rupees, at the marginal rate for each kind of hour.

    Marginal, not average: fixed charges do not change when a unit goes off,
    so the average on a bill overstates what a switch is worth.
    """
    kw = float(assumptions.get("unit_kw", 1.2) or 1.2)
    off_rate = float(assumptions.get("tariff_rs_per_kwh", 67) or 67)
    peak_rate = float(assumptions.get("peak_rs_per_kwh", off_rate) or off_rate)
    off_kwh = off_minutes / MINUTES * kw
    peak_kwh = peak_minutes / MINUTES * kw
    return (off_kwh, peak_kwh, off_kwh * off_rate + peak_kwh * peak_rate)


def enrich_bills(bills):
    """The two columns every reader of a bill wants, added once.

    `month` and `rs_per_unit` are not in the table; they are derived. They
    used to be derived inside load_bills, which meant a caller that got its
    bills from anywhere else -- meters_view.load, as the dashboard's
    analysis page does -- held a frame missing both, and found out by
    raising KeyError halfway down a rendered page.

    Idempotent, so it is safe to call on a frame that has been through it.
    """
    if bills.empty:
        return bills
    bills = bills.copy()
    bills["period_start"] = pd.to_datetime(bills["period_start"])
    bills["month"] = bills["period_start"].dt.strftime("%b %y")
    bills["rs_per_unit"] = (bills["amount_rs"].astype(float)
                            / bills["units"].astype(float))
    return bills


def load_bills(conn):
    return enrich_bills(pd.read_sql_query(
        "SELECT meter, period_start, period_end, units, amount_rs, note"
        " FROM meter_bills ORDER BY period_start", conn))


def impossible_months(bills, meters):
    """Bills that ask for more than the connection can physically deliver."""
    if bills.empty or meters.empty:
        return bills.iloc[0:0]
    loads = dict(zip(meters["code"], meters.get("sanctioned_kw",
                                                [None] * len(meters))))
    flags = []
    for _, b in bills.iterrows():
        kw = loads.get(b["meter"])
        if not kw or pd.isna(kw):
            flags.append(False)
            continue
        days = (pd.to_datetime(b["period_end"])
                - pd.to_datetime(b["period_start"])).days + 1
        flags.append(float(b["units"]) > float(kw) * 24 * days * 1.02)
    return bills[pd.Series(flags, index=bills.index)]


def tariff_from_bills(bills, skip_impossible=True, meters=None):
    """Rupees a unit, from the bills, with the impossible months left out."""
    if bills.empty:
        return None, 0
    use = bills
    if skip_impossible and meters is not None:
        bad = impossible_months(bills, meters)
        use = bills[~bills.index.isin(bad.index)]
    if use.empty:
        return None, 0
    units = use["units"].astype(float).sum()
    amount = use["amount_rs"].astype(float).sum()
    return (amount / units if units else None), len(use)
