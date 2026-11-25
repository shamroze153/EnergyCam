"""Energy: what the meters and the panels say, beside what the cameras saw.

Two pages use this: Meters (the readings, day by day, and the bills, month
by month) and Analysis (where the empty-and-cooled hours are, room by room,
and what they would cost). Like overview.py it holds no Streamlit and no
database: the dashboard hands in frames and gets back figures and HTML.

What it fixed, 11 November, when the page "looked strange":

  * the monthly bills were drawn in alphabetical order -- Apr 26, Aug 25,
    Aug 26, Dec 25 -- because the month was a label, not a date;
  * July 2026's 41,145 units, a month the first-floor connection cannot
    physically draw, set the scale for every other bar, which then all
    looked empty;
  * solar readings were saved and never shown anywhere;
  * "empty and still cooled, last 7 days" was counted from the last
    twenty-five hours of events, so it said a day while claiming a week;
  * a day with no reading turned the next one into two days of units,
    drawn as a spike.
"""
import math
import statistics
from bisect import bisect_right

import pandas as pd

import analysis_view as av
import meters_view
import overview as ov
from overview import TOKENS, esc

LOCAL = "Asia/Karachi"

# Three series, so three categorical slots: grid blue, solar yellow, the
# other meter aqua. Run through the dataviz validator in this order, both
# themes, against the card colours: all checks pass (light needs its labels
# beside the marks, which the legend and the table give it).
SERIES = {
    "dark": {"gf": "#3987e5", "solar": "#c98500", "ff": "#199e70"},
    "light": {"gf": "#2a78d6", "solar": "#eda100", "ff": "#1baf7a"},
}


# ===================================================================== figures

def solar_per_day(solar):
    """kWh the panels made each day, whichever number was typed in.

    An inverter shows two numbers, today's and its lifetime total, and the
    form cannot tell which one a person read off it. A lifetime total only
    ever rises and is far bigger than a day's change, so that is the test;
    a running total is turned into days by difference.

    Returns (frame of day, kwh), and "daily" or "total" for what was read.
    """
    if solar is None or solar.empty:
        return pd.DataFrame(columns=["day", "kwh"]), "daily"
    s = solar.copy()
    s["taken"] = pd.to_datetime(s["taken"], utc=True)
    s = s.sort_values("taken")
    # The form saves every press of its button: one figure a day, the last
    # typed, or four identical saves read as a running total that never
    # moved.
    s = s.groupby(s["taken"].dt.tz_convert(LOCAL).dt.normalize()).tail(1)
    values = s["kwh"].astype(float).tolist()
    steps = [b - a for a, b in zip(values, values[1:])]
    total = (len(values) >= 3 and all(d >= 0 for d in steps)
             and statistics.median(steps) > 0
             and statistics.median(values) > 15 * statistics.median(steps))
    days = s["taken"].dt.tz_convert(LOCAL).dt.normalize()
    if total:
        out = pd.DataFrame({"day": list(days)[1:], "kwh": steps})
        return out, "total"
    return pd.DataFrame({"day": list(days), "kwh": values}), "daily"


def reading_periods(readings, meters):
    """Units between consecutive readings, a day's worth each.

    A reading taken at eleven covers eleven yesterday to eleven today, so it
    is drawn on yesterday -- most of its hours are yesterday's. A gap of two
    days is shared out as two equal days rather than drawn as one tall one,
    and marked, so a missed reading is not mistaken for a busy day.
    """
    periods = meters_view.daily_units(readings)
    if periods.empty:
        return periods
    rows = []
    for _, p in periods.iterrows():
        hours = float(p["hours"] or 0)
        if hours <= 0:
            continue
        days = max(1, int(round(hours / 24.0)))
        # Put on a 24-hour footing. Shamroze reads the meters "at about six"
        # (12 Nov): 213 units over 25.7 hours is a 199-unit day, and without
        # this a reading taken an hour late made the day look bigger.
        each = float(p["units"]) * 24.0 / hours
        end = pd.Timestamp(p["to"]).tz_convert(LOCAL).normalize()
        for k in range(days):
            rows.append({"meter": p["meter"],
                         "day": end - pd.Timedelta(days=k + 1),
                         "units": each, "shared": days > 1,
                         "raw": float(p["units"]) / days,
                         "hours": hours / days,
                         "from": p["from"], "to": p["to"]})
    return pd.DataFrame(rows)


def daily_table(readings, meters, solar):
    """One row a day: each meter's units and the panels' kWh."""
    periods = reading_periods(readings, meters)
    sun, kind = solar_per_day(solar)
    if not len(sun):
        sun = pd.DataFrame(columns=["day", "kwh"])
    # Solar typed in on a day is drawn on the day before, with the reading
    # it was entered beside: the form asks for yesterday's full figure.
    shifted = (dict(zip(sun["day"] - pd.Timedelta(days=1), sun["kwh"]))
               if len(sun) else {})
    days = set(periods["day"]) if len(periods) else set()
    if days:
        # A solar day before the first pair of readings still happened:
        # the panels' first figure is drawn, the meters' columns stay blank.
        days |= {d for d in shifted if d >= min(days) - pd.Timedelta(days=7)}
    days = sorted(days)
    if not days:
        return pd.DataFrame(), kind
    table = pd.DataFrame({"day": days})
    for code in meters["code"] if len(meters) else []:
        mine = periods[periods["meter"] == code] if len(periods) else periods
        table[code] = table["day"].map(
            dict(zip(mine["day"], mine["units"])) if len(mine) else {})
        table[code + "_shared"] = table["day"].map(
            dict(zip(mine["day"], mine["shared"])) if len(mine) else {}) \
            .fillna(False).astype(bool)
        # The units as read and the hours they covered, for the tooltip.
        for extra in ("raw", "hours"):
            table[code + "_" + extra] = table["day"].map(
                dict(zip(mine["day"], mine[extra]))
                if len(mine) and extra in mine else {})
    table["solar"] = table["day"].map(shifted) if shifted else None
    return table, kind


LONG_GAP_H = 30          # a stretch longer than this is shared out (weekend)


def counted_as(start, end):
    """The days a stretch between two readings is put on (Shamroze, 24
    Nov: "Friday ke baad Monday subah ki reading weekend ki hai, Monday
    shaam ki Monday ki"): a day or less is its end's day -- 6 pm Monday to
    6 pm Tuesday is Tuesday, 09:30 to 18:00 Monday is Monday; longer, the
    days between its two readings -- Friday evening to Monday morning is
    Saturday and Sunday, to Monday evening Saturday to Monday.
    Returns [day] (naive local midnights)."""
    a = pd.Timestamp(start).tz_convert(LOCAL).tz_localize(None)
    b = pd.Timestamp(end).tz_convert(LOCAL).tz_localize(None)
    if (b - a).total_seconds() / 3600.0 <= LONG_GAP_H:
        return [b.normalize()]
    first = a.normalize() + pd.Timedelta(days=1)
    last = b.normalize() if b.hour >= 12 else \
        b.normalize() - pd.Timedelta(days=1)
    days = list(pd.date_range(first, last, freq="D")) if last >= first \
        else [b.normalize()]
    return days


def day_series(readings, meters, solar):
    """Every day the readings cover, each meter's units as the meter moved,
    put on the days counted_as() says: the days add up to the meter's own
    count. A day shared out of a longer stretch (the weekend) is an
    estimate (<meter>_est); a day holding only part of a day -- Monday
    09:30 to 18:00 after a Monday-morning reading -- is <meter>_part. The
    panels' figure is the calendar day's (the form asks for yesterday's,
    beside today's reading).

    Returns one row a day: day, and <meter>, <meter>_est, <meter>_part for
    each meter, solar."""
    codes = list(meters["code"]) if meters is not None and len(meters) else []
    if readings is None or readings.empty or not codes:
        return pd.DataFrame()
    periods = meters_view.daily_units(readings, every=True)
    if periods.empty:
        return pd.DataFrame()
    per = {}
    for _, p in periods.iterrows():
        if p["meter"] not in codes:
            continue
        days = counted_as(p["from"], p["to"])
        share = float(p["units"]) / len(days)
        for day in days:
            row = per.setdefault(day, {})
            code = p["meter"]
            row[code] = row.get(code, 0.0) + share
            row[code + "_est"] = row.get(code + "_est", False) or len(days) > 1
            row[code + "_part"] = len(days) == 1 and float(p["hours"]) < 18
    rows = []
    for day in sorted(per):
        row = {"day": day}
        for code in codes:
            row[code] = per[day].get(code)
            row[code + "_est"] = bool(per[day].get(code + "_est", False))
            row[code + "_part"] = bool(per[day].get(code + "_part", False))
        rows.append(row)
    out = pd.DataFrame(rows)
    sun, _ = solar_per_day(solar)
    if len(sun):
        shifted = dict(zip(pd.to_datetime(sun["day"]).dt.tz_localize(None)
                           - pd.Timedelta(days=1), sun["kwh"]))
        out["solar"] = out["day"].map(shifted)
    else:
        out["solar"] = None
    return out


BILL_DAY = 7             # K-Electric reads these meters on the 7th (Shamroze)


def dow_means(ds, code, weeks=4):
    """{0..6: units} -- a meter's usual Monday ... Sunday over the last
    `weeks`, each day as day_series() puts it (a Monday after a morning
    reading is its daytime; a weekend day a share of the weekend); a day
    of the week with none borrows the usual working or weekend day."""
    if ds is None or ds.empty or code not in ds:
        return {}
    d = ds[ds["day"] > ds["day"].max() - pd.Timedelta(weeks=weeks)]
    d = d[d[code].notna()]
    out = {}
    for k, g in d.groupby(d["day"].dt.dayofweek):
        out[int(k)] = float(g[code].mean())
    work = [v for k, v in out.items() if k < 5]
    rest = [v for k, v in out.items() if k >= 5]
    for k in range(7):
        if k not in out:
            pool = (work if k < 5 else rest) or work or rest
            if pool:
                out[k] = sum(pool) / len(pool)
    return out


def cycle_estimate(ds, meters, bills, today, bill_day=BILL_DAY):
    """The bill under way, the 7th to the 7th (Shamroze, 24 Nov: "K-Electric
    7 se 7 tak ka bill deta hai ... ab tak ka average ye, bill ye
    expected"): each meter's units so far as read, the days before the
    first reading and the days still to come at that meter's usual day of
    the week, and the whole at its own last bills' rate. None without a
    day of readings."""
    if ds is None or ds.empty or meters is None or not len(meters):
        return None
    today = pd.Timestamp(today)
    today = (today.tz_convert(LOCAL).tz_localize(None) if today.tzinfo
             else today).normalize()
    start = today.replace(day=bill_day) if today.day >= bill_day else \
        (today - pd.DateOffset(months=1)).replace(day=bill_day)
    end = start + pd.DateOffset(months=1)            # the next reading day
    rates = bill_rates(bills, meters)
    out = {"start": start, "end": end, "meters": {}, "units": 0.0,
           "rs": 0.0, "so_far": 0.0, "before": 0.0, "to_come": 0.0}
    have = ds[(ds["day"] >= start) & (ds["day"] < end)]
    last = None
    for code in meters["code"]:
        if code not in ds:
            continue
        mine = have[have[code].notna()]
        if not len(mine):
            continue
        usual = dow_means(ds, code)
        if not usual:
            continue
        first_read, last_read = mine["day"].min(), mine["day"].max()
        last = last_read if last is None else min(last, last_read)
        so_far = float(mine[code].sum())
        before = sum(usual[d.dayofweek] for d in pd.date_range(
            start, first_read - pd.Timedelta(days=1), freq="D"))
        to_come = sum(usual[d.dayofweek] for d in pd.date_range(
            last_read + pd.Timedelta(days=1), end - pd.Timedelta(days=1),
            freq="D"))
        units = so_far + before + to_come
        rate = rates.get(code, (None,))[0]
        out["meters"][code] = {"so_far": so_far, "before": before,
                               "to_come": to_come, "units": units,
                               "rate": rate,
                               "rs": units * rate if rate else None,
                               "first": first_read, "last": last_read,
                               "usual": usual}
        out["units"] += units
        out["so_far"] += so_far
        out["before"] += before
        out["to_come"] += to_come
        out["rs"] += units * rate if rate else 0.0
    if not out["meters"]:
        return None
    out["last"] = last
    out["rated"] = all(m["rate"] for m in out["meters"].values())
    out["days"] = (end - start).days
    out["days_done"] = (last - start).days + 1
    first = min(m["first"] for m in out["meters"].values())
    out["first"] = first
    both = [m["usual"] for m in out["meters"].values()]
    out["weekday"] = sum(sum(u[k] for k in range(1, 5)) / 4 for u in both)
    out["weekend"] = sum((u[5] + u[6]) / 2 for u in both)
    out["monday"] = sum(u[0] for u in both)
    return out


def cycle_page(theme, cyc, meters, bills=None):
    """The card for cycle_estimate: so far, a usual day, the bill to expect,
    and each meter's part."""
    if not cyc:
        return ""
    by_code = {m["code"]: m for _, m in meters.iterrows()}
    s, e, last = cyc["start"], cyc["end"], cyc["last"]
    span = "%s to %s" % (s.strftime("%d %b"), e.strftime("%d %b"))
    left = (e - last).days - 1
    tiles = [
        tile("This bill so far", "%s units" % _n(cyc["so_far"]
                                                 + cyc["before"]),
             "%s to %s, %d of its %d days%s"
             % (s.strftime("%d %b"), last.strftime("%d %b"),
                cyc["days_done"], cyc["days"],
                ("<br>%s of them (%s to %s, before the first reading) at "
                 "the usual day" % (_n(cyc["before"]), s.strftime("%d"),
                                     (cyc["first"] - pd.Timedelta(days=1))
                                     .strftime("%d %b")))
                if cyc["before"] >= 1 else "")),
        tile("A usual day now", "%s units" % _n(cyc["weekday"]),
             "a working day, both meters<br>a weekend day %s · a Monday "
             "(its daytime, after a morning reading) %s"
             % (_n(cyc["weekend"]), _n(cyc["monday"]))),
        tile("This bill, expected", ("Rs %s" % _n(cyc["rs"]))
             if cyc["rated"] else "%s units" % _n(cyc["units"]),
             "%s units for %s: so far, and %d day%s to come at the usual "
             "day of the week%s"
             % (_n(cyc["units"]), span, left, "" if left == 1 else "s",
                "; each meter at its own last bills' rate"
                if cyc["rated"] else "")),
    ]
    rows = []
    for code, m in cyc["meters"].items():
        rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                    '<td>%s</td><td>%s</td></tr>'
                    % (esc(by_code[code]["label"] if code in by_code
                           else code),
                       _n(m["so_far"] + m["before"]), _n(m["to_come"]),
                       _n(m["units"]),
                       ("Rs %.0f" % m["rate"]) if m["rate"] else "—",
                       ("Rs %s" % _n(m["rs"])) if m["rs"] else "—"))
    last_bill = ""
    if bills is not None and len(bills):
        bl = bills.copy()
        bl["end_"] = pd.to_datetime(bl["period_end"])
        lastb = bl[bl["end_"].dt.to_period("M")
                   == bl["end_"].max().to_period("M")]
        last_bill = (" The last bill (%s): %s units, Rs %s."
                     % (bl["end_"].max().strftime("%b %Y"),
                        _n(lastb["units"].astype(float).sum()),
                        _n(lastb["amount_rs"].astype(float).sum())))
    return "".join([
        '<div class="ec-h"><span class="t">This bill, %s</span><span '
        'class="c">K-Electric reads these meters on the %dth: the units so '
        'far, and what the rest of the bill will be</span></div>'
        % (span, s.day),
        '<div class="en-tiles">', "".join(tiles), "</div>",
        '<table class="en-bt" style="margin-top:10px"><tr><th></th><th>So '
        'far</th><th>To come</th><th>The bill</th><th>A unit</th><th>Rs'
        '</th></tr>%s</table>' % "".join(rows),
        '<div class="en-note" style="margin-top:6px">The days to come are '
        'each meter&rsquo;s usual Monday, Tuesday ... Sunday over the last '
        'four weeks, counted the way the readings are: Friday evening to '
        'Monday morning is the weekend, Monday morning to evening is Monday. '
        'The ground floor meter is after the solar panels, so this is what '
        'the grid will bill.%s</div>' % last_bill])


def bill_per_day(bills, meters):
    """[(label, units a day)] from the bills, both meters together: the
    last bill, the one before the panels, and this month a year ago."""
    if bills is None or bills.empty:
        return []
    b = bills.copy()
    codes = set(meters["code"]) if meters is not None and len(meters) else None
    if codes:
        b = b[b["meter"].isin(codes)]
    if b.empty:
        return []
    b["period_start"] = pd.to_datetime(b["period_start"])
    b["period_end"] = pd.to_datetime(b["period_end"])
    b["key"] = b["period_end"].dt.to_period("M")
    g = b.groupby("key").agg(units=("units", "sum"),
                             start=("period_start", "min"),
                             end=("period_end", "max"),
                             n=("meter", "nunique")).sort_index()
    g = g[g["n"] == g["n"].max()]                  # both meters billed
    if g.empty:
        return []
    g["a_day"] = g["units"] / ((g["end"] - g["start"]).dt.days + 1)
    out = []
    last = g.index[-1]
    out.append(("Last bill, %s" % last.strftime("%b %Y"),
                float(g.loc[last, "a_day"])))
    year_ago = (pd.Timestamp.now().to_period("M") - 12)
    if year_ago in g.index and year_ago != last:
        out.append(("%s, a year ago" % year_ago.strftime("%b %Y"),
                    float(g.loc[year_ago, "a_day"])))
    return out


def daily_history(theme, ds, by_code, gf, ff, bills=None, meters=None,
                  weeks=4):
    """Every day since the first reading, one column a day, the newest at
    the right and the page scrolled to it (Shamroze, 24 Nov: "purane units
    ye aa rahe the, naye ye, weekend ke ye ... neeche date aa rahi ho, day
    aa raha ho"): the grid units of both meters and the panels' kWh,
    weekends shaded, estimates (a day inside the weekend's gap) paler;
    above it, a usual weekday and weekend day against the bills."""
    if ds is None or ds.empty:
        return ""
    c = SERIES[theme]

    def grid(r):
        vals = [r.get(k) for k in (gf, ff) if k]
        if any(x is None or pd.isna(x) for x in vals):
            return None
        return sum(float(x) for x in vals)
    ds = ds.copy()
    ds["grid"] = [grid(r) for _, r in ds.iterrows()]
    ds["est"] = [any(bool(r.get(k + "_est")) for k in (gf, ff) if k)
                 for _, r in ds.iterrows()]
    ds["part"] = [any(bool(r.get(k + "_part")) for k in (gf, ff) if k)
                  for _, r in ds.iterrows()]
    recent = ds[ds["day"] > ds["day"].max() - pd.Timedelta(weeks=weeks)]
    wk = recent[(recent["day"].dt.dayofweek < 5) & ~recent["est"]
                & ~recent["part"] & recent["grid"].notna()]["grid"]
    we = recent[(recent["day"].dt.dayofweek >= 5)
                & recent["grid"].notna()]["grid"]
    tiles = []
    if len(wk):
        tiles.append(tile("A weekday, usual", "%s units" % _n(wk.mean()),
                          "from the grid, both meters · last %d weeks, %d "
                          "day%s" % (weeks, len(wk), "" if len(wk) == 1
                                     else "s")))
    if len(we):
        tiles.append(tile("A weekend day, usual", "%s units" % _n(we.mean()),
                          "Saturday and Sunday, shared out from the "
                          "readings either side"))
    for label, a_day in bill_per_day(bills, meters):
        tiles.append(tile(label, "%s units" % _n(a_day),
                          "a day, from the K-Electric bill"))
    def num(x):
        return 0.0 if x is None or pd.isna(x) else float(x)
    top = max([1.0] + [num(r.get(gf)) + num(r.get(ff)) + num(r.get("solar"))
                       for _, r in ds.iterrows()])
    high = top * 1.08
    cols = []
    for _, r in ds.iterrows():
        d = pd.Timestamp(r["day"])
        parts = [(r.get(gf) if gf else None, c["gf"], "Ground floor + "
                  "basement, grid"),
                 (r.get("solar"), c["solar"], "Solar"),
                 (r.get(ff) if ff else None, c["ff"], "First floor + cafe, "
                  "grid")]
        segs, tip = [], [d.strftime("%A %d %B")]
        for value, colour, name in parts:
            if value is None or pd.isna(value):
                tip.append("%s —" % name)
                continue
            segs.append('<i style="height:%.2f%%;background:%s"></i>'
                        % (100.0 * float(value) / high, colour))
            tip.append("%s %s" % (name, _n(value)))
        if r["grid"] is not None:
            tip.append("grid, both meters %s units" % _n(r["grid"]))
        if r["est"]:
            tip.append("a share of the weekend: Friday evening to the next "
                       "reading, shared over the days between")
        elif r["part"]:
            tip.append("its daytime only: the morning reading closed the "
                       "weekend, and its night is the next day's")
        weekend = d.dayofweek >= 5
        month = d.day == 1 or not cols
        cols.append(
            '<div class="d%s%s" title="%s"><div class="st"><b>%s</b>%s</div>'
            '<span>%s</span><em>%s</em></div>'
            % (" we" if weekend else "", " est" if r["est"] else "",
               esc(" · ".join(tip)),
               _n(r["grid"]) if r["grid"] is not None else "",
               "".join(reversed(segs)), d.strftime("%a"),
               d.strftime("%d") + (" " + d.strftime("%b") if month else "")))
    # The scroller runs right to left, so it opens on the newest days; the
    # days inside it run left to right, oldest first.
    return (
        '<div class="ec-h"><span class="t">Every day since the first reading'
        '</span><span class="c">units as the meters moved · scroll back for '
        'older days · hover a day</span>%s</div>'
        '%s<div class="ec-card en-days"><div class="sc"><div class="row">%s'
        '</div></div><div class="en-note">A day is its reading&rsquo;s: '
        'Monday 6 pm to Tuesday 6 pm is Tuesday. Friday evening to Monday '
        'morning is the weekend, shared over Saturday and Sunday (paler); '
        'Monday morning to evening is Monday, its daytime only. The days add '
        'up to what the meters moved. The number over a day is the '
        'grid&rsquo;s, both meters (what K-Electric bills); the yellow is '
        'what the panels made besides.</div></div>'
        % (legend([(c["gf"], "Ground floor + basement, grid"),
                   (c["solar"], "Solar"),
                   (c["ff"], "First floor + cafe, grid")]),
           ('<div class="en-tiles" style="margin-bottom:12px">%s</div>'
            % "".join(tiles)) if tiles else "",
           "".join(cols)))


def suspicious(readings, meters):
    """Readings that cannot be right, worth a second look by a person."""
    out = []
    if readings.empty:
        return out
    kw = dict(zip(meters["code"], meters.get("sanctioned_kw",
                                              [None] * len(meters))))
    for meter, rows in readings.groupby("meter"):
        rows = rows.sort_values("taken")
        prev = None
        for _, r in rows.iterrows():
            if prev is not None and pd.notna(r["reading"]) \
                    and pd.notna(prev["reading"]):
                used = float(r["reading"]) - float(prev["reading"])
                hours = (r["taken"] - prev["taken"]).total_seconds() / 3600
                when = ov.clock(r["taken"])
                day = pd.Timestamp(r["taken"]).tz_convert(LOCAL).strftime(
                    "%d %b")
                if used < 0:
                    out.append("%s, %s %s: the meter went backwards by %s"
                               " units -- a mistyped digit, or a new meter."
                               % (meter, day, when, format(int(-used), ",")))
                elif meters_view.impossible(used, kw.get(meter), hours):
                    out.append("%s, %s %s: %s units in %.0f hours is more than"
                               " the connection can draw -- probably a typo."
                               % (meter, day, when, format(int(used), ","),
                                  hours))
            prev = r
    return out


def cooled_in_windows(history, rooms, windows, peak):
    """Empty-with-a-unit hours inside each window, from the events."""
    out = []
    for start, end in windows:
        off, on_peak = av.cooled_while_empty(history, rooms, start, end, peak)
        out.append((off + on_peak) / 60.0)
    return out


def person_hours_in_windows(history, rooms, windows, alive=None):
    """People times hours in the rooms over each window, from the events.

    The usage a day's units were for (Shamroze, 12 Nov: "a chart of the
    units, depending on the usage too"): ten people for an hour is ten.
    alive: per window, the stretches the loop was running; a state is not
    carried across hours nobody was watching.
    """
    mine = history[history["room"].isin(set(rooms))].sort_values(
        ["room", "timestamp"])
    # On seconds, and from each window's own rows: until 18 Nov every
    # window walked a month of every room's rows in Timestamps (two
    # seconds of the Energy tab's meters).
    rooms_rows = []
    for _, rows in mine.groupby("room"):
        rooms_rows.append(([pd.Timestamp(t).value / 1e9
                            for t in rows["timestamp"]],
                           list(rows["status"]), list(rows["people"])))
    out = []
    for k, (start, end) in enumerate(windows):
        spans = alive[k] if alive is not None else [(start, end)]
        s, e = pd.Timestamp(start).value / 1e9, pd.Timestamp(end).value / 1e9
        spans = [(pd.Timestamp(a).value / 1e9, pd.Timestamp(b).value / 1e9)
                 for a, b in spans]
        total = 0.0
        for stamps, status, people in rooms_rows:
            # The row the window opens in, and on until one starts after it.
            for i in range(max(0, bisect_right(stamps, s) - 1), len(stamps)):
                a = stamps[i]
                if a >= e:
                    break
                if status[i] != "occupied":
                    continue
                b = stamps[i + 1] if i + 1 < len(stamps) else e
                n = people[i] if people[i] == people[i] else 1
                weight = max(1, int(n or 1))
                for s0, s1 in spans:
                    x, y = max(a, s, s0), min(b, e, s1)
                    if y > x:
                        total += weight * (y - x) / 3600.0
        out.append(total)
    return out


def top_rooms(history, df, since, until, peak, assumptions, hours=None):
    """Rooms ranked by what their empty, cooled hours would cost.

    Only rooms with a unit somebody could switch off. The rupees are an
    upper bound -- a unit nobody has calibrated is assumed to be running --
    and the page says so beside them.

    With `hours` (rooms.yaml's working day), the rupees and the ranking are
    the working day's only, and the nights and weekends are carried beside
    them as a separate "if it was left on" figure. Without the split, every
    room empty overnight was charged as if its unit ran till morning, and a
    mosque nobody prays in at 2am came fourth on the list.
    """
    import overview
    rows = []
    paid = df[df["has_unit"] & df["alerts"]]
    for _, r in paid.iterrows():
        units = int(r.get("ac_count") or 1)
        # Money by the room's load (units in typical-unit terms, rated by
        # their tons where known); the count stays for the label.
        load = r.get("ac_load")
        load = float(load) if load is not None and pd.notna(load) and load \
            else float(units)
        if hours is None:
            off, on_peak = av.cooled_while_empty(history, [r["room"]], since,
                                                 until, peak)
            a_off = a_peak = 0.0
        else:
            off, on_peak = av.cooled_while_empty(
                history, [r["room"]], since, until, peak, hours, "working")
            a_off, a_peak = av.cooled_while_empty(
                history, [r["room"]], since, until, peak, hours, "after")
        if off + on_peak + a_off + a_peak <= 0:
            continue
        _, _, rupees = av.money(off * load, on_peak * load, assumptions)
        _, _, after_rs = av.money(a_off * load, a_peak * load, assumptions)
        rows.append({
            "room": r["room"],
            "dept": overview.department_of(r["room"], r.get("zone"),
                                           r.get("dept")) or r.get("zone"),
            "zone": r.get("zone"),
            "hours": (off + on_peak) / 60.0, "peak_hours": on_peak / 60.0,
            "units": units, "rupees": rupees,
            "after_hours": (a_off + a_peak) / 60.0, "after_rupees": after_rs,
        })
    rows.sort(key=lambda x: (-x["rupees"], -x["after_rupees"]))
    return rows


def month_bills(bills, meters):
    """The bills by month, in date order, with the impossible ones marked."""
    if bills.empty:
        return bills
    b = av.enrich_bills(bills)
    bad = av.impossible_months(b, meters)
    flag = b.index.isin(bad.index)
    # The live meters table has no sanctioned loads (20 Nov), so the rule
    # above never fired there and July 2026's 41,145 units on the first
    # floor drew every other month flat. A month at over three times its
    # meter's usual day is the same fault, seen from the bills alone.
    n = (pd.to_datetime(b["period_end"])
         - pd.to_datetime(b["period_start"])).dt.days + 1
    per = b["units"].astype(float) / n.clip(lower=1)
    usual = per.groupby(b["meter"]).transform("median")
    count = per.groupby(b["meter"]).transform("count")
    flag = flag | ((count >= 6) & (per > 3 * usual)).values
    b = b.assign(impossible=flag)
    return b.sort_values("period_start")


# ===================================================================== drawing

def _nice(top):
    """A step and a top for the scale. Steps under one too: units a
    person-hour run 0.3-1.2, and a top of int(1.2) = 1 cut the tallest
    column off at the frame (20 Nov)."""
    for step in (0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200,
                 250, 500, 1000, 2000, 2500, 5000, 10000):
        if top / step <= 5:
            high = max(step, math.ceil(round(top / step, 6)) * step)
            if step >= 1:
                step, high = int(step), int(high)
            return step, high
    return 10000, int(math.ceil(top / 10000.0)) * 10000


def _ticks(step, high):
    """The scale's values, bottom to top, without float creep."""
    n = int(round(high / float(step)))
    return [round(i * step, 6) for i in range(n + 1)]


def columns(labels, stacks, colours, tips, height=220, cap=None,
            marks=None, top=None):
    """Stacked columns, one per label; the parts of each stack in order.

    stacks: per column, a list of values (None or 0 draws nothing).
    cap: a ceiling for the scale; a column above it is drawn to the top
         and marked, so one impossible month does not flatten the rest.
    marks: per column, None or a short word drawn above it.
    top: the scale's top, so two charts side by side share one scale.
    """
    totals = [sum(v or 0 for v in s) for s in stacks]
    top = top or max([1.0] + [t for t in totals if cap is None or t <= cap])
    step, high = _nice(top * 1.05)
    n = len(labels)
    width = 100.0 / max(1, n)
    bar = min(width * 0.7, width - 0.6)
    svg = ['<svg viewBox="0 0 100 100" preserveAspectRatio="none" '
           'aria-hidden="true">']
    for v in _ticks(step, high):
        y = 100 - 100.0 * v / high
        svg.append('<line x1="0" x2="100" y1="%.2f" y2="%.2f" stroke="%s" '
                   'stroke-width="1" vector-effect="non-scaling-stroke"/>'
                   % (y, y, "var(--axis)" if v == 0 else "var(--grid)"))
    over = []
    for i, parts in enumerate(stacks):
        x = i * width + (width - bar) / 2
        base = 0.0
        clipped = cap is not None and totals[i] > cap
        for value, colour in zip(parts, colours):
            if not value or base >= 100:
                continue
            # Each part at its true height, the one that runs off the top
            # cut there: squeezing the whole column to fit drew July's
            # ground floor at half its units (20 Nov).
            h = min(100.0 * value / high, 100.0 - base)
            y = 100 - (base + h)
            # The surface gap between stacked parts: a hair off each top.
            svg.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" '
                       'fill="%s"/>' % (x, y + 0.6 if base else y, bar,
                                        max(0.0, h - (0.6 if base else 0)),
                                        colour))
            base += h
        svg.append('<rect class="hit" x="%.3f" y="0" width="%.3f" '
                   'height="100"><title>%s</title></rect>'
                   % (i * width, width, esc(tips[i])))
        if clipped:
            over.append(i)
    svg.append("</svg>")
    html = ['<div class="ec-chart" style="height:%dpx"><div class="plot">'
            % height, "".join(svg)]
    for v in _ticks(step, high):
        # In full under ten thousand, compact on an axis that reaches it:
        # "25,000" did not fit the gutter and broke over two lines.
        text = (("%gk" % (v / 1000.0)) if high >= 10000 and v
                else format(v, ",") if v == int(v) else "%g" % v)
        html.append('<span class="yt" style="top:%.2f%%">%s</span>'
                    % (100 - 100.0 * v / high, text))
    every = max(1, -(-n // 10))
    # Not one so close to the last that the two run together.
    shown = [i for i in range(n)
             if (i % every == 0 and n - 1 - i >= every) or i == n - 1]
    for k, i in enumerate(shown):
        # On a phone every other one only (20 Nov: "Mon 09Tue 10Wed 11"
        # ran together under the daily chart). Counted back from the last,
        # so the newest always keeps its label.
        alt = (len(shown) - 1 - k) % 2 == 1
        html.append('<span class="xt%s" style="left:%.2f%%">%s</span>'
                    % (" alt" if alt else "", (i + 0.5) * width,
                       esc(labels[i])))
    for i in over:
        html.append('<span class="plab" style="left:%.2f%%;top:0%%">'
                    '↑ off the scale</span>' % ((i + 0.5) * width))
    for i, word in enumerate(marks or []):
        if word and i not in over:
            top_y = 100 - 100.0 * totals[i] / high
            html.append('<span class="plab mk" style="left:%.2f%%;top:%.2f%%">'
                        '%s</span>' % ((i + 0.5) * width, top_y, esc(word)))
    html.append("</div></div>")
    return "".join(html)


def groups(labels, series, colours, tips, height=220, cap=None,
           dashed=None):
    """Side by side columns, one group per label, one column per series,
    on one scale. series: per series, a value per label (None draws
    nothing). A value over `cap` is drawn to the top and said so;
    dashed[(s, i)] draws that column as an estimate, not a bill."""
    values = [v for s in series for v in s if v]
    top = max([1.0] + [v for v in values if cap is None or v <= cap])
    step, high = _nice(top * 1.05)
    n, k = len(labels), max(1, len(series))
    width = 100.0 / max(1, n)
    gap = 0.25
    bar = min(width * 0.78 / k, width / k - gap)
    left = (width - (bar * k + gap * (k - 1))) / 2
    svg = ['<svg viewBox="0 0 100 100" preserveAspectRatio="none" '
           'aria-hidden="true">']
    for v in _ticks(step, high):
        y = 100 - 100.0 * v / high
        svg.append('<line x1="0" x2="100" y1="%.2f" y2="%.2f" stroke="%s" '
                   'stroke-width="1" vector-effect="non-scaling-stroke"/>'
                   % (y, y, "var(--axis)" if v == 0 else "var(--grid)"))
    over = set()
    for i in range(n):
        for j, s in enumerate(series):
            v = s[i]
            if not v:
                continue
            h = min(100.0, 100.0 * v / high)
            if cap is not None and v > cap:
                over.add(i)
            guess = bool(dashed and dashed.get((j, i)))
            svg.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" '
                       'fill="%s"%s/>'
                       % (i * width + left + j * (bar + gap), 100 - h, bar, h,
                          colours[j],
                          ' fill-opacity=".55" stroke="%s" stroke-dasharray='
                          '"3 2" stroke-width="1.5" vector-effect='
                          '"non-scaling-stroke"' % colours[j] if guess else ""))
        svg.append('<rect class="hit" x="%.3f" y="0" width="%.3f" '
                   'height="100"><title>%s</title></rect>'
                   % (i * width, width, esc(tips[i])))
    svg.append("</svg>")
    html = ['<div class="ec-chart" style="height:%dpx"><div class="plot">'
            % height, "".join(svg)]
    for v in _ticks(step, high):
        text = (("%gk" % (v / 1000.0)) if high >= 10000 and v
                else format(v, ",") if v == int(v) else "%g" % v)
        html.append('<span class="yt" style="top:%.2f%%">%s</span>'
                    % (100 - 100.0 * v / high, text))
    for i in range(n):
        alt = (n - 1 - i) % 2 == 1
        html.append('<span class="xt%s" style="left:%.2f%%">%s</span>'
                    % (" alt" if alt else "", (i + 0.5) * width,
                       esc(labels[i])))
    for i in sorted(over):
        html.append('<span class="plab" style="left:%.2f%%;top:0%%">'
                    '↑ off the scale</span>' % ((i + 0.5) * width))
    html.append("</div></div>")
    return "".join(html)


# One hue, older years paler: the years are an order, not categories.
YEAR_SHADES = (".32", ".6", "1")


def year_on_year(months, colour, expected=None):
    """Each calendar month with a column for every year the bills cover --
    2024, 2025, 2026 -- the whole campus, both meters together, and the
    same in figures below (Shamroze, 20 Nov: "one month, three lines: so
    many units in 2024, in 2025, in 2026"). `expected`: (month start,
    units, Rs) for the month under way, drawn dashed."""
    if months is None or not len(months):
        return ""
    tot = months.assign(u=months["units"].astype(float),
                        rs=months["amount_rs"].astype(float)) \
        .groupby("period_start").agg(u=("u", "sum"), rs=("rs", "sum"),
                                      odd=("impossible", "any"))
    cells = {(pd.Timestamp(d).year, pd.Timestamp(d).month):
             (float(r["u"]), float(r["rs"]), bool(r["odd"]), False)
             for d, r in tot.iterrows()}
    if expected:
        d = pd.Timestamp(expected[0])
        if (d.year, d.month) not in cells:
            cells[(d.year, d.month)] = (float(expected[1]),
                                        float(expected[2]), False, True)
    years = sorted({y for y, _ in cells})[-3:]
    if len(years) < 2:
        return ""
    shades = YEAR_SHADES[-len(years):]
    colours = ["color-mix(in srgb, %s %d%%, transparent)"
               % (colour, int(float(a) * 100)) if a != "1" else colour
               for a in shades]
    labels, series, tips, dashed = [], [[] for _ in years], [], {}
    normal, mons = [], []
    for m in range(1, 13):
        if not any((y, m) in cells for y in years):
            continue
        i = len(labels)
        mons.append(m)
        labels.append(pd.Timestamp(2000, m, 1).strftime("%b"))
        bits = []
        for j, y in enumerate(years):
            cell = cells.get((y, m))
            series[j].append(cell[0] if cell else None)
            if cell:
                if cell[3]:
                    dashed[(j, i)] = True
                if not cell[2]:
                    normal.append(cell[0])
                bits.append("%d: %s units, Rs %s%s" % (
                    y, _n(cell[0]), _n(cell[1]),
                    " (expected)" if cell[3] else
                    " (a queried bill in it)" if cell[2] else ""))
        tips.append("%s · %s" % (pd.Timestamp(2000, m, 1).strftime("%B"),
                                 " · ".join(bits)))
    cap = max(normal) * 1.15 if normal else None
    # The same, in figures: a hover is no use on a phone.
    rows = ['<table class="en-bt"><thead><tr><th>Month</th>%s</tr></thead>'
            '<tbody>' % "".join("<th>%d</th>" % y for y in years)]
    for i, label in enumerate(labels):
        tds = []
        for j, y in enumerate(years):
            v = series[j][i]
            cell = cells.get((y, mons[i]))
            tds.append("<td%s>%s</td>" % (
                ' class="crit"' if cell and cell[2] else "",
                "—" if v is None else
                ("~%s*" % _n(v)) if cell and cell[3] else _n(v)))
        rows.append("<tr><td>%s</td>%s</tr>" % (label, "".join(tds)))
    totals = []
    for j, y in enumerate(years):
        got = [v for v in series[j] if v]
        totals.append("<td><b>%s</b><br><span>%d month%s</span></td>"
                      % (_n(sum(got)), len(got), "" if len(got) == 1 else "s"))
    rows.append('<tr class="tot"><td>Total</td>%s</tr></tbody></table>'
                % "".join(totals))
    return ('<div class="ec-h"><span class="t">Month by month, year by year'
            '</span><span class="c">the whole campus, both meters · units'
            '</span>%s</div><div class="ec-card" style="padding:16px 18px 22px">'
            '%s<details class="en-more" open><summary>In figures</summary>%s'
            '</details><div class="en-note">One column a year, older years '
            'paler. The panels went up in October 2026; the months before '
            'compare the building with itself. * this month so far, at the '
            'pace of the readings. Red: a month with a queried bill in it.'
            '</div></div>'
            % (legend([(c_, str(y)) for c_, y in zip(colours, years)]),
               groups(labels, series, colours, tips, height=240, cap=cap,
                      dashed=dashed), "".join(rows)))


def legend(items):
    return '<span class="ec-legend">%s</span>' % "".join(
        '<span><i class="box" style="background:%s"></i>%s</span>'
        % (colour, esc(label)) for colour, label in items)


def ranked(rows, value, label, note, colour):
    """Ranked horizontal bars, one hue, biggest first."""
    if not rows:
        return ""
    top = max(value(r) for r in rows) or 1
    out = ['<div class="en-ranked">']
    for r in rows:
        out.append(
            '<div class="row"><div class="nm"><b>%s</b><span>%s</span></div>'
            '<div class="tr"><i style="width:%.1f%%;background:%s"></i></div>'
            '<div class="v">%s<span>%s</span></div></div>'
            % (esc(ov.short(r["room"])), esc(note(r)),
               100.0 * value(r) / top, colour, esc(label(r)),
               esc(r.get("sub", ""))))
    out.append("</div>")
    return "".join(out)


EXTRA_CSS = """<style>
.ec{--axis:%(axis)s;--grid:%(grid)s}
.ec-chart .plab.mk{transform:translate(-50%%,-130%%);font-weight:500;
font-size:10.5px;color:var(--t3)}
.en-ranked .row{display:grid;grid-template-columns:minmax(150px,240px) 1fr 140px;
gap:14px;align-items:center;padding:8px 0;border-top:1px solid var(--line)}
.en-ranked .row:first-child{border-top:0}
.en-ranked .nm b{display:block;font-weight:650;font-size:14px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.en-ranked .nm span{font-size:12px;color:var(--t3)}
.en-ranked .tr{height:10px;border-radius:99px;background:var(--meter);overflow:hidden}
.en-ranked .tr i{display:block;height:100%%;border-radius:99px}
.en-ranked .v{text-align:right;font-weight:650;font-variant-numeric:tabular-nums}
.en-ranked .v span{display:block;font-size:11.5px;color:var(--t3);font-weight:400}
.en-note{font-size:12.5px;color:var(--t3);margin-top:8px;line-height:1.5}
.en-warn{background:var(--crit-bg);border:1px solid var(--crit-line);
border-radius:12px;padding:11px 14px;margin-top:10px;font-size:13px}
.en-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}
.en-tiles:has(>.ec-kpi:nth-child(5):last-child){grid-template-columns:repeat(6,minmax(0,1fr))}
.en-tiles:has(>.ec-kpi:nth-child(5):last-child)>.ec-kpi{grid-column:span 2}
.en-tiles:has(>.ec-kpi:nth-child(5):last-child)>.ec-kpi:nth-child(n+4){grid-column:span 3}
@media (max-width:760px){
.en-tiles:has(>.ec-kpi:nth-child(5):last-child){grid-template-columns:repeat(2,minmax(0,1fr))}
.en-tiles:has(>.ec-kpi:nth-child(5):last-child)>.ec-kpi{grid-column:auto}
.en-tiles:has(>.ec-kpi:nth-child(5):last-child)>.ec-kpi:last-child{grid-column:1/-1}}
.en-sun{display:grid;grid-template-columns:minmax(230px,1fr) 2fr;gap:26px;
align-items:center}
.en-sun .lbl{font-size:11.5px;letter-spacing:.13em;text-transform:uppercase;
color:var(--t3);margin-bottom:8px}
.en-sun .big{font-size:46px;font-weight:760;letter-spacing:-.02em;line-height:1;
font-variant-numeric:tabular-nums}
.en-sun .big small{font-size:17px;font-weight:600;color:var(--t3);margin-left:6px}
.en-sun .sub{font-size:13.5px;margin-top:10px;line-height:1.5}
.en-sun .sub b{font-variant-numeric:tabular-nums}
.en-sun .chg{display:inline-block;font-size:12px;font-weight:650;padding:2px 9px;
border-radius:99px;margin-top:10px;border:1px solid var(--line)}
.en-sun-share{margin-top:16px;font-size:13px;line-height:1.5}
.en-sun-share .bar{height:12px;border-radius:99px;background:var(--meter);
overflow:hidden;margin:0 0 7px;display:flex}
.en-sun-share .bar i{display:block;height:100%%}
.en-yr>input{position:absolute;opacity:0;pointer-events:none}
.en-yr>label{display:inline-block;padding:4px 12px;margin:0 6px 10px 0;
border:1px solid var(--line);border-radius:99px;font-size:12.5px;
cursor:pointer;color:var(--t2)}
.en-yr>input:checked+label{background:var(--t1);color:var(--page);
border-color:var(--t1)}
.en-yr>.p{display:none}
#enyr-a:checked~.p.a,#enyr-b:checked~.p.b,#enyr-c:checked~.p.c{display:block}
.en-yr-sum{font-size:13px;color:var(--t2);margin:2px 0 6px;line-height:1.5}
.en-bt{width:100%%;border-collapse:collapse;font-size:13px;margin-top:6px;
font-variant-numeric:tabular-nums}
.en-bt th{font-size:11.5px;font-weight:600;color:var(--t3);text-align:right;
padding:6px 8px;border-bottom:1px solid var(--line)}
.en-bt td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--line)}
.en-bt th:first-child,.en-bt td:first-child{text-align:left;white-space:nowrap}
.en-bt tr.odd td,.en-bt td.crit{color:var(--crit)}
.en-bt tr.tot td{font-weight:650;border-bottom:0;vertical-align:top}
.en-bt tr.tot td span{font-size:11px;font-weight:400;color:var(--t3)}
@media (max-width:760px){.en-bt{font-size:12px}.en-bt th,.en-bt td{padding:5px 4px}}
.en-days{padding:14px 12px 12px}
.en-days .sc{display:flex;flex-direction:row-reverse;overflow-x:auto;
padding-bottom:6px}
.en-days .row{display:flex;flex:none;gap:3px;align-items:flex-end;min-width:100%%}
.en-days .d{flex:1 0 40px;max-width:72px;display:flex;flex-direction:column;
align-items:center;border-radius:6px;padding:4px 0 3px}
.en-days .d.we{background:var(--s2)}
.en-days .st{height:170px;width:100%%;display:flex;flex-direction:column;
justify-content:flex-end;align-items:center;padding-top:16px}
.en-days .st i{display:block;width:22px;margin-top:1px;border-radius:2px}
.en-days .d.est .st i{opacity:.45}
.en-days .st b{font-size:10px;font-weight:600;color:var(--t2);margin-bottom:2px;
font-variant-numeric:tabular-nums;white-space:nowrap}
.en-days .d>span{font-size:10.5px;color:var(--t3);margin-top:4px}
.en-days .d.we>span{color:var(--t1);font-weight:650}
.en-days .d>em{font-style:normal;font-size:10.5px;color:var(--t2);white-space:nowrap}
.en-more{margin-top:18px}.en-more>summary{cursor:pointer;font-weight:650;
font-size:14px;color:var(--t2);padding:6px 0;list-style-position:inside}
@media (max-width:760px){.ec-chart .xt.alt,.ec-chart .plab.mk.alt{display:none}
.en-ranked .row{grid-template-columns:minmax(0,1fr) 96px}
.en-ranked .row>*{min-width:0}.en-ranked .v span{overflow-wrap:anywhere}
.en-ranked .tr{grid-column:1/-1;order:3}.en-sun{grid-template-columns:1fr}
.en-tiles{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.en-tiles>.ec-kpi{padding:14px 14px 15px;min-width:0}
.en-tiles>.ec-kpi .v{font-size:20px;overflow-wrap:anywhere}}
</style>""".replace("\n", "")


def css(theme):
    return ov.css(theme) + EXTRA_CSS % TOKENS[theme]


def tile(label, value, note, tone=""):
    return ('<div class="ec-card ec-kpi"><div class="k">%s</div><div class="v"'
            '%s>%s</div><div class="s">%s</div></div>'
            % (esc(label), ' style="color:var(--crit)"' if tone == "crit"
               else "", value, note))


def day_label(day):
    return pd.Timestamp(day).strftime("%a %d")


def _n(value):
    return format(int(round(float(value))), ",")


def solar_block(table, gf, rate, sun_colour, grid_colour):
    """The panels on their own card: what they made, saved and covered.

    Three readings of one number, each a different question somebody asks:
    how much (kWh), what was it worth (rupees not bought from the grid, at
    the unit rate), and how much of the floor it feeds did it carry (the
    share of solar in solar + that meter's grid units, same day). Under
    them every day typed in so far, the number written on each column.
    """
    if table is None or table.empty or "solar" not in table.columns:
        return ""
    sun = table[table["solar"].notna()]
    if sun.empty:
        return ""
    last = sun.iloc[-1]
    kwh = float(last["solar"])
    out = ['<div class="ec-h"><span class="t">Solar</span><span class="c">'
           'what the panels made, from the inverter\'s daily figure</span>'
           '</div><div class="ec-card" style="padding:20px 22px 24px">'
           '<div class="en-sun"><div>'
           '<div class="lbl">%s</div>'
           '<div class="big" style="color:%s">%s<small>kWh</small></div>'
           '<div class="sub">about <b>Rs %s</b> not bought from the grid, '
           'at Rs %.0f a unit</div>'
           % (esc(pd.Timestamp(last["day"]).strftime("%A %d %B")), sun_colour,
              _n(kwh), _n(kwh * rate), rate)]
    if len(sun) >= 2 and float(sun.iloc[-2]["solar"]) > 0:
        prev = float(sun.iloc[-2]["solar"])
        change = 100.0 * (kwh / prev - 1)
        out.append('<span class="chg">%s%.0f%% on %s (%s kWh)</span>'
                   % ("+" if change >= 0 else "−", abs(change),
                      esc(day_label(sun.iloc[-2]["day"])), _n(prev)))
    grid = float(last[gf]) if gf and pd.notna(last.get(gf)) else None
    if grid is not None and grid + kwh > 0:
        pct = 100.0 * kwh / (grid + kwh)
        out.append('<div class="en-sun-share"><div class="bar">'
                   '<i style="width:%.1f%%;background:%s"></i>'
                   '<i style="width:%.1f%%;background:%s;opacity:.55"></i>'
                   '</div><b>%.0f%%</b> of what the ground floor + basement '
                   'used that day came off the roof: %s kWh solar, %s units '
                   'grid.</div>'
                   % (pct, sun_colour, 100 - pct, grid_colour, pct, _n(kwh),
                      _n(grid)))
    values = [float(v) for v in sun["solar"]]
    total = sum(values)
    out.append('</div><div>%s<div class="en-note">%d day%s typed in, %s kWh '
               'in all, worth about Rs %s. Hover a column for the day.</div>'
               '</div></div></div>'
               % (columns([day_label(d) for d in sun["day"]],
                          [[v] for v in values], [sun_colour],
                          ["%s · %s kWh · about Rs %s" % (
                              pd.Timestamp(d).strftime("%A %d %B"), _n(v),
                              _n(v * rate))
                           for d, v in zip(sun["day"], values)],
                          height=170, marks=[_n(v) for v in values]),
                  len(values), "" if len(values) == 1 else "s", _n(total),
                  _n(total * rate)))
    return "".join(out)


def solar_effect(bills, table, meters, since=None, full_from=None, kw=None):
    """Units a day on each meter before the panels and after (20 Nov,
    Shamroze: "show the difference since the solar went up").

    Before: the last whole billing month that ended before the panels, in
    units a day, so a 31-day month and a 9-day stretch compare. After: the
    metered days since, from the readings. The first-floor meter has no
    panels behind it, so its own change over the same two stretches is the
    weather and the work; the ground floor's change beyond that is the
    panels. `since` is rooms.yaml's `solar_since`, the day the panels went
    up; until somebody writes it down, the first day the inverter's figure
    was typed in. `full_from` (`solar_full_from`) is when they worked in
    full: 140-H's went up on 1 Oct and spent October on test, so October
    is neither before nor after -- it is drawn, marked "test". `kw`, the
    array's size, gives what each kW made a day.

    Returns None when either side is missing, else a dict.
    """
    if table is None or table.empty or bills is None or not len(bills):
        return None
    codes = {m["code"]: m for _, m in meters.iterrows()}
    gf = next((k for k, m in codes.items() if m["behind_solar"]), None)
    ff = next((k for k in codes if k != gf), None)
    if not gf or gf not in table.columns:
        return None
    assumed = since is None
    if assumed:
        sun = table[table["solar"].notna()] if "solar" in table.columns \
            else table.iloc[0:0]
        if sun.empty:
            return None
        since = sun["day"].iloc[0]
    since = pd.Timestamp(since)
    full = pd.Timestamp(full_from) if full_from else since
    days = pd.to_datetime(table["day"])
    if days.dt.tz is not None:
        since = since if since.tzinfo else since.tz_localize(days.dt.tz)
        full = full if full.tzinfo else full.tz_localize(days.dt.tz)
    after = table[(days >= max(since, full)) & table[gf].notna()]
    if ff and ff in table.columns:
        after = after[after[ff].notna()]
    b = month_bills(bills, meters)
    end = pd.to_datetime(b["period_end"]).dt.date
    b = b[(end < since.date()) & ~b["impossible"]]
    gf_months = b[b["meter"] == gf].sort_values("period_start")
    if after.empty or gf_months.empty:
        return None
    last = gf_months.iloc[-1]

    def per_day(row):
        n = (pd.Timestamp(row["period_end"]) - pd.Timestamp(row["period_start"])
             ).days + 1
        return float(row["units"]) / max(1, n)

    out = {"gf": gf, "ff": ff, "since": since, "assumed": assumed,
           "first": pd.Timestamp(after["day"].iloc[0]), "test_until": full,
           "month": pd.Timestamp(last["period_start"]),
           "gf_bill": float(last["units"]), "gf_before": per_day(last),
           "gf_after": float(after[gf].mean()), "days": len(after),
           "ff_before": None, "ff_after": None, "expected": None,
           "saved": None, "solar": None, "kw": float(kw) if kw else None,
           "yield": None}
    if "solar" in table.columns:
        # The days the meters were read too: the first figure typed in can
        # be a part day, before the readings began.
        sun = after["solar"].dropna()
        out["solar"] = float(sun.mean()) if len(sun) else None
        if out["solar"] and out["kw"]:
            out["yield"] = out["solar"] / out["kw"]
    if ff:
        same = b[(b["meter"] == ff)
                 & (b["period_start"] == last["period_start"])]
        if len(same) and ff in after.columns:
            out["ff_before"] = per_day(same.iloc[0])
            out["ff_after"] = float(after[ff].mean())
            if out["ff_before"] > 0:
                out["expected"] = out["gf_before"] * out["ff_after"] / \
                    out["ff_before"]
                out["saved"] = out["expected"] - out["gf_after"]
    return out


def _pct(a, b):
    return "%s%.0f%%" % ("+" if b >= a else "−", abs(100.0 * (b / a - 1))) \
        if a else ""


def solar_before_after(theme, eff, bills, meters, rate):
    """The card for solar_effect: four tiles, then each meter's months in
    units a day on one shared scale, the stretch since the panels last."""
    if not eff:
        return ""
    c = SERIES[theme]
    codes = {m["code"]: m for _, m in meters.iterrows()}
    since = eff["first"].strftime("%d %b").lstrip("0")
    went = eff["since"].strftime("%d %B").lstrip("0")
    month = eff["month"].strftime("%B %Y")
    h = ['<div class="ec-h"><span class="t">Solar: before and after</span>'
         '<span class="c">units a day from the grid · the ground floor meter '
         'has the panels, the first floor\'s has none</span></div>'
         '<div class="en-tiles">']
    h.append(tile("Ground floor, before", "%s a day" % _n(eff["gf_before"]),
                  "%s bill, %s units" % (esc(month), _n(eff["gf_bill"]))))
    h.append(tile("Ground floor, since %s" % since,
                  "%s a day" % _n(eff["gf_after"]),
                  "<b>%s</b> · %d day%s of readings"
                  % (_pct(eff["gf_before"], eff["gf_after"]), eff["days"],
                     "" if eff["days"] == 1 else "s")))
    if eff["ff_before"]:
        h.append(tile("First floor, same two stretches",
                      "%s → %s" % (_n(eff["ff_before"]), _n(eff["ff_after"])),
                      "%s with no panels: the weather and the work"
                      % _pct(eff["ff_before"], eff["ff_after"])))
    if eff["saved"] is not None and eff["saved"] > 0:
        h.append(tile("Off the grid, thanks to the panels",
                      "~%s units a day" % _n(eff["saved"]),
                      "about Rs %s a day, Rs %s a month at Rs %.0f"
                      % (_n(eff["saved"] * rate), _n(eff["saved"] * rate * 30),
                         rate)))
    if eff["yield"]:
        # What each kW of panels made: the one figure that says whether the
        # array is working, whatever the building did.
        h.append(tile("Each kW of panels",
                      "%.1f kWh a day" % eff["yield"],
                      "%s kW made %s kWh a day; about 4 is usual for "
                      "Karachi in November" % (format(eff["kw"], "g"),
                                               _n(eff["solar"]))))
    h.append("</div>")
    start = eff["since"].tz_localize(None) if eff["since"].tzinfo \
        else eff["since"]
    end = eff["test_until"].tz_localize(None) if eff["test_until"].tzinfo \
        else eff["test_until"]

    months = month_bills(bills, meters)
    rows = {}
    for code in (eff["gf"], eff["ff"]):
        if not code:
            continue
        m = months[months["meter"] == code].sort_values("period_start")
        bars = []
        for _, r in m.iterrows():
            a = pd.Timestamp(r["period_start"])
            n = (pd.Timestamp(r["period_end"]) - a).days + 1
            test = start <= a < end
            bars.append((a.strftime("%b %y"),
                         float(r["units"]) / max(1, n), bool(r["impossible"]),
                         "%s · %s units a day (%s on the bill)%s"
                         % (a.strftime("%B %Y"),
                            _n(float(r["units"]) / max(1, n)),
                            _n(r["units"]),
                            " · the panels on test" if test else ""), test))
        rows[code] = bars
    normal = [b[1] for bars in rows.values() for b in bars if not b[2]]
    normal += [eff["gf_after"] + (eff["solar"] or 0)]
    if eff["ff_after"]:
        normal.append(eff["ff_after"])
    top = max(normal) * 1.08
    for code in (eff["gf"], eff["ff"]):
        if code not in rows:
            continue
        bars = rows[code]
        labels = [b[0] for b in bars] + ["Since " + since]
        if code == eff["gf"]:
            stacks = [[b[1], None] for b in bars] + \
                [[eff["gf_after"], eff["solar"]]]
            colours = [c["gf"], c["solar"]]
            last_tip = ("Since %s · %s units a day from the grid%s"
                        % (since, _n(eff["gf_after"]),
                           " + %s kWh a day of solar" % _n(eff["solar"])
                           if eff["solar"] else ""))
            caption = legend([(c["gf"], "grid"), (c["solar"], "solar")])
        else:
            stacks = [[b[1]] for b in bars] + [[eff["ff_after"]]]
            colours = [c["ff"]]
            last_tip = "Since %s · %s units a day" % (since,
                                                      _n(eff["ff_after"]))
            caption = legend([(c["ff"], "grid")])
        # Only the test month is worded: "after solar" over the last column
        # ran into it on a phone, and the yellow and "Since" say it already.
        marks = [("test" if code == eff["gf"] and b[4] else None)
                 for b in bars] + [None]
        h.append('<div class="ec-h"><span class="t">%s</span><span class="c">'
                 'units a day, month by month</span>%s</div>'
                 '<div class="ec-card" style="padding:16px 18px 26px">%s</div>'
                 % (esc(codes[code]["label"] if code in codes else code),
                    caption,
                    columns(labels, stacks, colours,
                            [b[3] for b in bars] + [last_tip], height=190,
                            cap=top / 1.08, marks=marks, top=top)))
    tested = end > start and eff["test_until"] != eff["since"]
    h.append('<div class="en-note">A bill is a month, so each is shared out '
             'over its days; the last column is the readings since %s. '
             '%sThe first floor meter has no panels behind it, so its change '
             'is what the weather and the work did; the ground floor\'s fall '
             'beyond it is the panels. The estimate takes %s as the month '
             'before them.%s</div>'
             % (since, "" if eff["assumed"] else
                "The panels went up on %s%s. " % (
                    went, " and were on test until %s (marked \"test\")"
                    % (end - pd.Timedelta(days=1)).strftime("%d %B")
                    .lstrip("0") if tested else ""), esc(month),
                " The day the panels went up is not written down yet, so "
                "\"after\" starts at the first solar figure typed in; the "
                "date goes in rooms.yaml as solar_since."
                if eff["assumed"] else ""))
    return "".join(h)


# ===================================================================== pages

def pace(readings, meters):
    """Each stretch between two readings, both meters side by side:
    [{from, to, hours, units: {code: units}, per_h: {code: units an hour}}],
    oldest first. Readings taken together (within half an hour) share a
    stretch."""
    p = meters_view.daily_units(readings, every=True)
    if p is None or p.empty:
        return []
    p = p.sort_values("to")
    out = []
    for _, r in p.iterrows():
        hit = next((s for s in out
                    if abs((s["to"] - r["to"]).total_seconds()) <= 1800
                    and abs((s["from"] - r["from"]).total_seconds()) <= 1800),
                   None)
        if hit is None:
            hit = {"from": r["from"], "to": r["to"], "hours": r["hours"],
                   "units": {}, "per_h": {}}
            out.append(hit)
        hit["units"][r["meter"]] = float(r["units"])
        hit["per_h"][r["meter"]] = (float(r["units"]) / r["hours"]
                                    if r["hours"] else None)
    return out


def last_reading(readings, code):
    """(reading, taken) of a meter's latest reading, or None."""
    if readings is None or not len(readings):
        return None
    r = readings[readings["meter"] == code].dropna(subset=["reading"])
    if not len(r):
        return None
    row = r.sort_values("taken").iloc[-1]
    return float(row["reading"]), pd.Timestamp(row["taken"])


def reading_check(value, last, at, usual=None):
    """What a number typed on the readings form says against the meter's
    last reading, said before it is saved (Shamroze, 18 Nov: "the reading
    entry, better, an easy way").

    value: the number typed (None: nothing yet); last: (reading, taken) or
    None; at: when it was read; usual: the meter's units a day, if known.
    Returns {level, units, hours, per_day, text}: level "none" (nothing to
    say), "ok", "odd" (save it if it is right) or "low" (a meter only goes
    up: not saved).
    """
    out = {"level": "none", "units": None, "hours": None, "per_day": None,
           "text": ""}
    if value is None or last is None:
        return out
    before, when = last
    units = float(value) - before
    hours = (pd.Timestamp(at) - when).total_seconds() / 3600.0
    out.update(units=units, hours=hours)
    if units < 0:
        out.update(level="low", text="Lower than the last reading (%s). A "
                   "meter only goes up: check the digits." % _n(before))
        return out
    if hours <= 0:
        out.update(level="odd", text="Earlier than the last reading, %s."
                   % pd.Timestamp(when).tz_convert(LOCAL).strftime(
                       "%a %d %b %H:%M"))
        return out
    # A day's pace only from half a day or more: an evening's two hours
    # scaled up to a day said "about 2,231 a day" (18 Nov).
    per_day = units / hours * 24 if hours >= 12 else None
    out["per_day"] = per_day
    span = (("%.1f" % hours).replace(".0", "") + " h") if hours < 48 \
        else (("%.1f" % (hours / 24)).replace(".0", "") + " days")
    since = "+%s units in %s" % (_n(units), span)
    if per_day is not None:
        since += " · about %s a day" % _n(per_day)
    if units == 0 and hours >= 3:
        out.update(level="odd", text="The same as the last reading: nothing "
                   "used in %.0f hours?" % hours)
    elif usual and per_day is not None and hours >= 6 and (
            per_day > 3 * usual or per_day < usual / 4):
        out.update(level="odd", text="%s, against a usual %s a day: check "
                   "the digits." % (since, _n(usual)))
    else:
        out.update(level="ok", text=since)
    return out


def month_estimate(readings, meters, rates, peak=(18.5, 22.5), days=7):
    """Units a day on each meter over the last week of readings, and what a
    month at that pace would bill (Shamroze, 17 Nov: "how many units a day,
    so what will the month's bill be -- an average, with peak and
    off-peak").

    A week, reading to reading, holds a weekend and its working days in
    their right share, so its average is the month's day. The peak share is
    the peak hours' share of the day -- a rough guess, said so on the page.
    None without two readings a day apart on any meter.
    """
    if readings is None or not len(readings):
        return None
    out = {"meters": {}, "per_day": 0.0}
    spans = []
    for code in meters["code"]:
        r = readings[readings["meter"] == code].dropna(subset=["reading"]) \
            .sort_values("taken")
        if len(r) < 2:
            continue
        last = r.iloc[-1]
        before = r[r["taken"] <= last["taken"] - pd.Timedelta(days=days)]
        first = before.iloc[-1] if len(before) else r.iloc[0]
        hours = (last["taken"] - first["taken"]).total_seconds() / 3600.0
        units = float(last["reading"]) - float(first["reading"])
        if hours < 20 or units < 0:
            continue
        out["meters"][code] = units / hours * 24
        out["per_day"] += units / hours * 24
        spans.append((first["taken"], last["taken"]))
    if not out["meters"]:
        return None
    out["from"] = min(a for a, _ in spans)
    out["to"] = max(b for _, b in spans)
    out["days"] = (out["to"] - out["from"]).total_seconds() / 86400.0
    off, on = rates
    share = max(0.0, min(24.0, peak[1] - peak[0])) / 24.0
    out["month"] = out["per_day"] * 30
    out["peak_units"] = out["month"] * share
    out["off_units"] = out["month"] - out["peak_units"]
    out["peak_rs"] = out["peak_units"] * on
    out["off_rs"] = out["off_units"] * off
    out["rs"] = out["peak_rs"] + out["off_rs"]
    out["peak_share"] = share
    return out


def bill_rates(bills, meters, n=3):
    """Rs a unit on each meter's last n bills, everything in (fixed charges,
    adders, taxes): {code: (rate, bills used, the last bill's row)}."""
    out = {}
    if bills is None or not len(bills):
        return out
    b = month_bills(bills, meters)
    b = b[~b["impossible"]]
    for code, g in b.groupby("meter"):
        g = g.sort_values("period_start").tail(n)
        units = g["units"].astype(float).sum()
        if units > 0:
            out[code] = (float(g["amount_rs"].astype(float).sum()) / units,
                         len(g), g.iloc[-1])
    return out


def month_expected(est, meters, bills):
    """(the month's first day, units, Rs) for the month under way, at the
    readings' pace and each meter's own bill rate; None without both."""
    rates = bill_rates(bills, meters)
    if not est or not rates or not all(k in rates for k in est["meters"]):
        return None
    end = pd.Timestamp(est["to"]).tz_convert(LOCAL)
    days = end.days_in_month
    units = sum(v * days for v in est["meters"].values())
    rs = sum(v * days * rates[k][0] for k, v in est["meters"].items())
    return (pd.Timestamp(end.year, end.month, 1), units, rs)


def month_bill_page(est, meters, bills):
    """This month's bill on each meter at the pace of the readings (20 Nov,
    Shamroze: "from the daily units, what bill to expect this month"),
    against the last bill. Each meter at its own last three bills' rate,
    since the two are billed differently."""
    rates = bill_rates(bills, meters)
    if not est or not rates:
        return ""
    by_code = {m["code"]: m for _, m in meters.iterrows()}
    end = pd.Timestamp(est["to"]).tz_convert(LOCAL)
    days = end.days_in_month
    tiles = []
    for code, per_day in est["meters"].items():
        if code not in rates:
            continue
        rate, used, last = rates[code]
        units = per_day * days
        was = float(last["units"])
        tiles.append(tile(
            "%s, %s" % (by_code[code]["label"] if code in by_code else code,
                        end.strftime("%B")),
            "Rs %s" % _n(units * rate),
            "about %s units (%s a day × %d) at Rs %.0f a unit, its last %d "
            "bills<br>%s: %s units, Rs %s · <b>%s</b>"
            % (_n(units), _n(per_day), days, rate, used,
               esc(pd.Timestamp(last["period_start"]).strftime("%B")),
               _n(was), _n(last["amount_rs"]), _pct(was, units))))
    if not tiles:
        return ""
    return ('<div class="ec-h"><span class="t">This month\'s bill, meter by '
            'meter</span><span class="c">what to expect at the pace of the '
            'readings</span></div><div class="en-tiles">%s</div>'
            '<div class="en-note" style="margin-top:6px">Each meter at what '
            'its own last bills came to a unit, fixed charges and taxes in. '
            'Fixed charges do not fall with the units, so a month with far '
            'fewer units comes out a little above this.</div>'
            % "".join(tiles))


def month_page(theme, est, meters, rates, bills=None):
    """The card for month_estimate: a day, a month, the bill."""
    if not est:
        return ""
    by_code = {m["code"]: m for _, m in meters.iterrows()}
    off, on = rates
    a = pd.Timestamp(est["from"]).tz_convert(LOCAL).strftime("%a %d %b")
    b = pd.Timestamp(est["to"]).tz_convert(LOCAL).strftime("%a %d %b")
    each = " · ".join("%s %s" % (esc(by_code[k]["label"]), _n(v))
                      for k, v in est["meters"].items())
    last_bill = ""
    if bills is not None and len(bills):
        bl = bills[bills["meter"].isin(list(est["meters"]))].copy()
        if len(bl):
            bl["end"] = pd.to_datetime(bl["period_end"])
            end = bl["end"].max()
            m = bl[bl["end"].dt.to_period("M") == end.to_period("M")]
            last_bill = ("<br>Last bill (%s, %d meter%s): %s units, Rs %s."
                         % (end.strftime("%b %Y"), len(m),
                            "" if len(m) == 1 else "s",
                            _n(m["units"].astype(float).sum()),
                            _n(m["amount_rs"].astype(float).sum())))
    # One figure for the month's bill, not two: each meter at what its own
    # bills came to a unit when there are bills (the card below breaks it
    # down), the tariff's peak and off-peak rates when there are none.
    known = bill_rates(bills, meters)
    if known and all(k in known for k in est["meters"]):
        days = pd.Timestamp(est["to"]).tz_convert(LOCAL).days_in_month
        rs = sum(v * days * known[k][0] for k, v in est["meters"].items())
        bill = tile("The month's bill, about", "Rs %s" % _n(rs),
                    "each meter at what its last bills came to a unit; "
                    "meter by meter below")
    else:
        bill = tile("The month's bill, about", "Rs %s" % _n(est["rs"]),
                    "Off-peak %s units × Rs %s = Rs %s<br>Peak %s units × Rs "
                    "%s = Rs %s" % (_n(est["off_units"]), _n(off),
                                    _n(est["off_rs"]), _n(est["peak_units"]),
                                    _n(on), _n(est["peak_rs"])))
    tiles = "".join([
        tile("Units a day", _n(est["per_day"]),
             "both meters together<br>" + each),
        tile("A month at this pace", "%s units" % _n(est["month"]),
             "30 days × %s a day" % _n(est["per_day"])),
        bill,
    ])
    return "".join([
        '<div class="ec-h"><span class="t">A day, and the month it makes'
        '</span><span class="c">from the meter readings, %s to %s (%.1f days)'
        "</span></div>" % (a, b, est["days"]),
        '<div class="en-tiles">', tiles, "</div>",
        '<div class="en-note" style="margin-top:6px">An average: the readings '
        "a week apart hold the weekend and the working days in their right "
        "share. %sThe ground floor meter is after the solar panels, so this "
        "is what the grid will bill, not all the building uses.%s</div>"
        % ("" if known and all(k in known for k in est["meters"]) else
           "Peak is the %s evening hours a day (%.0f%% of the day), counted "
           "as if they draw like any other hour -- a rough split. "
           % (_n(est["peak_share"] * 24), est["peak_share"] * 100),
           last_bill),
        month_bill_page(est, meters, bills)])


def _span_kind(a, b):
    """"night & weekend", "working day", "evening"...: what a stretch held,
    for the label under its column."""
    a = pd.Timestamp(a).tz_convert(LOCAL)
    b = pd.Timestamp(b).tz_convert(LOCAL)
    hours = (b - a).total_seconds() / 3600.0
    if hours >= 40:
        return "incl. weekend" if any(
            (a + pd.Timedelta(days=k)).weekday() >= 5
            for k in range(int(hours // 24) + 1)) else "%.0f days" % (hours / 24)
    if a.date() == b.date() and 8 <= a.hour and b.hour <= 20:
        return "daytime"
    if hours >= 18:
        return "a day and night"
    return "night"


def pace_page(theme, readings, meters, rate):
    """Units an hour, reading to reading (Shamroze, 17 Nov: "a chart of how
    many units are consumed -- the weekend, the day, all of it").

    A reading taken at a different hour each time, or after a weekend, makes
    a day-by-day figure an average of unlike stretches. Units an hour puts
    them side by side: the weekend's idling, a working day, a night.
    """
    spans = pace(readings, meters)[-12:]
    if not spans:
        return ""
    c = SERIES[theme]
    by_code = {m["code"]: m for _, m in meters.iterrows()}
    gf = next((k for k, m in by_code.items() if m.get("behind_solar")), None)
    ff = next((k for k in by_code if k != gf), None)
    codes = [k for k in (gf, ff) if k]
    colours = [c["gf"] if k == gf else c["ff"] for k in codes]
    labels, stacks, tips = [], [], []
    for s in spans:
        b = pd.Timestamp(s["to"]).tz_convert(LOCAL)
        labels.append("%s %s" % (b.strftime("%a"), ov.clock(s["to"])
                                 .replace(" morning", "a")
                                 .replace(" afternoon", "p")
                                 .replace(" evening", "p")
                                 .replace(" night", "p")))
        stacks.append([s["per_h"].get(k) for k in codes])
        bits = ["%s to %s, %.1f h (%s)"
                % (pd.Timestamp(s["from"]).tz_convert(LOCAL)
                   .strftime("%a %d %H:%M"), b.strftime("%a %d %H:%M"),
                   s["hours"], _span_kind(s["from"], s["to"]))]
        for k in codes:
            if k in s["units"]:
                bits.append("%s: %s units, %.1f an hour"
                            % (by_code[k]["label"],
                               format(int(round(s["units"][k])), ","),
                               s["per_h"][k] or 0))
        tips.append(" · ".join(bits))
    rows = []
    for s in reversed(spans):
        total = sum(s["units"].get(k, 0.0) for k in codes)
        per = total / s["hours"] if s["hours"] else 0.0
        days = counted_as(s["from"], s["to"])
        on = days[0].strftime("%a %d") if len(days) == 1 else "%s – %s" % (
            days[0].strftime("%a %d"), days[-1].strftime("%a %d"))
        rows.append(
            '<tr style="border-top:1px solid var(--line)"><td style="padding:'
            '6px 8px 6px 0">%s<br><span style="color:var(--t3);font-size:12px">'
            "to %s</span></td><td>%s<br><span style=\"color:var(--t3);"
            'font-size:12px">counted as %s</span></td><td style="text-align:'
            'right">%.1f h'
            '</td>%s<td style="text-align:right;font-weight:700">%.1f</td><td '
            'style="text-align:right">%s</td></tr>'
            % (esc(pd.Timestamp(s["from"]).tz_convert(LOCAL)
                   .strftime("%a %d, %H:%M")),
               esc(pd.Timestamp(s["to"]).tz_convert(LOCAL)
                   .strftime("%a %d, %H:%M")),
               esc(_span_kind(s["from"], s["to"])), esc(on), s["hours"],
               "".join('<td style="text-align:right">%s</td>'
                       % (format(int(round(s["units"][k])), ",")
                          if k in s["units"] else "—") for k in codes),
               per, "Rs %s" % format(int(round(per * 24 * rate)), ",")))
    return "".join([
        '<div class="ec-h"><span class="t">Units an hour, reading to '
        'reading</span><span class="c">each column one stretch between two '
        "readings, ending at its label · hover for the units</span>%s</div>"
        % legend([(col, by_code[k]["label"])
                  for k, col in zip(codes, colours)]),
        '<div class="ec-card" style="padding:16px 18px 26px">',
        columns(labels, stacks, colours, tips, height=200),
        '<div style="overflow-x:auto;margin-top:12px"><table style="width:'
        "100%%;border-collapse:collapse;font-size:13px;color:var(--t1);"
        'white-space:nowrap;font-variant-numeric:tabular-nums"><tr style="'
        'color:var(--t2);font-size:12px"><th style="text-align:left">From'
        '</th><th style="text-align:left">Held</th><th style="text-align:'
        'right">Hours</th>%s<th style="text-align:right">Units an hour</th>'
        '<th style="text-align:right">A day at that pace</th></tr>%s</table>'
        "</div>"
        % ("".join('<th style="text-align:right">%s</th>'
                   % esc(by_code[k]["label"]) for k in codes), "".join(rows)),
        '<div class="en-note" style="margin-top:8px">A weekend or a night '
        "column is what the building draws with few people in: the floor "
        "nobody switches off. The gap between it and a working day is what "
        "people and their ACs add. The ground floor meter is after the solar "
        "panels, so its daytime pace reads low on a bright day.</div>",
        "</div>"])


def last_full_day(days, codes):
    """The newest day of day_series() that every meter covers whole -- not
    a share of a weekend, not a Monday's daytime -- or None."""
    if days is None or not len(days):
        return None
    ok = pd.Series(True, index=days.index)
    for k in codes:
        if not k or k not in days:
            continue
        ok &= days[k].notna()
        for flag in (k + "_est", k + "_part"):
            if flag in days:
                ok &= ~days[flag].fillna(False).astype(bool)
    return days[ok].iloc[-1] if ok.any() else None


def meters_page(theme, table, kind, meters, bills, cooled_hours, rate,
                problems, campus_has_meters, campus, usage=None,
                solar=None, expected=None, bills_inline=True, days=None,
                more_first=""):
    """The Meters view below the form: days, then months. `solar`: the
    array as rooms.yaml has it -- {since, full_from, kw}. `expected`: this
    month's (start, units, Rs) at the readings' pace, for year_on_year.
    `days`: day_series(), for the chart of every day since the first
    reading (without it, the older chart of the last days). `more_first`:
    a section to fold away first under "More" (the reading-to-reading
    pace, 25 Nov).

    In the order energy dashboards put it (25 Nov, Shamroze: "jo
    standards follow hote hain"): the period's figure and its forecast
    (above this, the bill), the last day, the trend day by day against a
    usual day, what the panels did, the months and the year before; the
    workings folded away."""
    t = TOKENS[theme]
    c = SERIES[theme]
    h = [css(theme), '<div class="ec">']
    if not campus_has_meters:
        h.append('<div class="ec-card ec-calm" style="margin-top:6px">No '
                 'electricity meters are recorded for %s yet. Send the meter '
                 'numbers and the K-Electric account numbers from its bills '
                 'and they go in beside 140-H\'s two.</div></div>'
                 % esc(campus))
        return "".join(h)

    by_code = {m["code"]: m for _, m in meters.iterrows()}
    gf = next((code for code, m in by_code.items() if m["behind_solar"]),
              None)
    others = [code for code in by_code if code != gf]
    ff = others[0] if others else None

    if table is None or table.empty:
        h.append('<div class="ec-card ec-calm">The first reading of each '
                 'meter is in. Tomorrow\'s gives the first day\'s units: a day '
                 'is one reading to the next.</div>')
    else:
        # The last day the meters cover, not merely the last row: a solar
        # figure typed in on its own makes a row with no units in it.
        metered = [k for k in (gf, ff) if k and k in table.columns]
        has_units = table[metered].notna().any(axis=1) if metered else None
        # The day as day_series() counts it (25 Nov: "The last full day, Mon
        # 23" above a list saying 6 pm Monday to 6 pm Tuesday is Tuesday).
        last = last_full_day(days, (gf, ff))
        if last is None:
            last = (table[has_units].iloc[-1]
                    if has_units is not None and has_units.any()
                    else table.iloc[-1])
        grid = sum(float(last[k]) for k in (gf, ff)
                   if k and pd.notna(last.get(k)))
        sun = float(last["solar"]) if pd.notna(last.get("solar")) else None
        # "Tue 17" alone read as a heading of nothing (18 Nov).
        h.append('<div class="ec-h"><span class="t">The last full day, %s'
                 '</span><span class="c">between two readings</span></div>'
                 '<div class="en-tiles">' % day_label(last["day"]))
        if gf:
            h.append(tile(by_code[gf]["label"] + ", from the grid",
                          ("%s units" % format(int(round(last[gf])), ","))
                          if pd.notna(last.get(gf)) else "—",
                          "after the solar panels"))
        if ff:
            h.append(tile(by_code[ff]["label"],
                          ("%s units" % format(int(round(last[ff])), ","))
                          if pd.notna(last.get(ff)) else "—",
                          "no solar behind this one"))
        h.append(tile("Solar made", ("%s kWh" % format(int(round(sun)), ","))
                      if sun is not None else "—",
                      "the inverter's figure for that day" if sun is not None
                      else "not entered for that day"))
        h.append(tile("From the grid, both meters",
                      "Rs %s" % format(int(round(grid * rate)), ","),
                      "%s units at Rs %.0f" % (format(int(round(grid)), ","),
                                               rate)))
        h.append("</div>")
        # The trend day by day comes before the panels and the months.
        if days is not None and len(days):
            # 24 Nov: every day since the first reading, 6 pm to 6 pm,
            # weekends shaded, against the bills (daily_history).
            h.append(daily_history(theme, days, by_code, gf, ff, bills,
                                   meters))
        h.append(solar_block(table, gf, rate, c["solar"], c["gf"]))
        solar = solar or {}
        h.append(solar_before_after(
            theme, solar_effect(bills, table, meters, solar.get("since"),
                                solar.get("full_from"), solar.get("kw")),
            bills, meters, rate))

        labels = [day_label(d) for d in table["day"]]
        stacks, tips, marks = [], [], []
        for _, r in table.iterrows():
            parts = [r.get(gf) if gf else None, r.get("solar"),
                     r.get(ff) if ff else None]
            parts = [float(p) if p is not None and pd.notna(p) else None
                     for p in parts]
            stacks.append(parts)
            shared = any(bool(r.get(k + "_shared")) for k in (gf, ff) if k)
            marks.append("avg" if shared else None)
            bits = ["%s" % pd.Timestamp(r["day"]).strftime("%A %d %B")]
            for name, value, code in (("grid, ground floor", parts[0], gf),
                                      ("solar", parts[1], None),
                                      ("grid, first floor", parts[2], ff)):
                text = "—" if value is None else format(int(round(value)), ",")
                raw = r.get(code + "_raw") if code else None
                hrs = r.get(code + "_hours") if code else None
                if (value is not None and raw is not None and pd.notna(raw)
                        and hrs is not None and pd.notna(hrs)
                        and abs(float(hrs) - 24) >= 0.5):
                    text += " (%s read over %.1f h)" % (
                        format(int(round(float(raw))), ","), float(hrs))
                bits.append("%s %s" % (name, text))
            if shared:
                bits.append("a missed reading, shared out evenly")
            tips.append(" · ".join(bits))
        if days is None or not len(days):
            h.append('<div class="ec-h"><span class="t">What the building '
                     'used, day by day</span><span class="c">units; hover a '
                     'day</span>%s</div>'
                     % legend([(c["gf"], "Ground floor + basement, grid"),
                               (c["solar"], "Solar"),
                               (c["ff"], "First floor + cafe, grid")]))
            h.append('<div class="ec-card" style="padding:16px 18px 26px">%s'
                     '<div class="en-note">A reading at eleven covers eleven '
                     'the day before to eleven that day, so it is drawn on '
                     'the day before. Every day is put on a 24-hour footing, '
                     'so a reading taken an hour early or late does not make '
                     'a day look smaller or bigger: hover a day for the units '
                     'as read and the hours they covered. "avg" is a day with '
                     'no reading of its own: the units across the gap are '
                     'shared out evenly.%s</div></div>'
                     % (columns(labels, stacks, [c["gf"], c["solar"],
                                                 c["ff"]],
                                tips, height=230, marks=marks),
                        " Solar was read as the inverter's running total and"
                        " turned into days." if kind == "total" else ""))

        # The charts that explain rather than report, folded away
        # (Shamroze, 20 Nov: "keep the important graphs, clean").
        more = [more_first] if more_first else []
        if cooled_hours is not None:
            tips = ["%s · %.0f room-hours empty with a unit assumed on"
                    % (pd.Timestamp(d).strftime("%A %d %B"), v)
                    for d, v in zip(table["day"], cooled_hours)]
            more.append('<div class="ec-h"><span class="t">Rooms on these meters '
                     'left empty with a unit</span><span class="c">room-hours '
                     'each day: ten rooms empty for an hour is ten · from '
                     'the cameras</span>'
                     '</div><div class="ec-card" style="padding:16px 18px 26px"'
                     '>%s<div class="en-note">Side by side with the units, not '
                     'as their cause: a hot day and a busy day both raise the '
                     'units. After about four weeks of readings the two '
                     'together say what an empty, cooled room really costs.'
                     '</div></div>'
                     % columns(labels, [[v] for v in cooled_hours],
                               [t["accent"]], tips, height=150))
        if usage is not None and any(usage):
            # Units against the use they were for: a busy day uses more, a
            # wasteful one uses more for fewer people.
            per, tips = [], []
            for (_, r), ph in zip(table.iterrows(), usage):
                units = sum(float(r.get(k)) for k in (gf, ff, "solar")
                            if k and r.get(k) is not None
                            and pd.notna(r.get(k)))
                whole = all(k and r.get(k) is not None and pd.notna(r.get(k))
                            for k in (gf, ff) if k)
                day = pd.Timestamp(r["day"]).strftime("%A %d %B")
                if ph is None:
                    per.append([None])
                    tips.append("%s · the cameras watched only part of it"
                                % day)
                    continue
                v = units / ph if ph >= 1 and whole else None
                per.append([v])
                tips.append("%s · %s units for %s person-hours%s"
                            % (day, format(int(round(units)), ","),
                               format(int(round(ph)), ","),
                               (" · %.2f a person-hour" % v) if v else
                               " · a meter not read that day"))
            if any(p[0] for p in per):
                more.append('<div class="ec-h"><span class="t">Units for the use '
                         'they were for</span><span class="c">grid and solar '
                         'units per person-hour in the building · lower is '
                         'better</span></div><div class="ec-card" style="'
                         'padding:16px 18px 26px">%s<div class="en-note">A '
                         'person-hour is one person in for an hour, from the '
                         'cameras: a busy day is allowed more units, an empty '
                         'day with the same units shows up tall. Days the '
                         'cameras watched only part of read high.</div></div>'
                         % columns(labels, per, [c["ff"]], tips, height=150))
        if more:
            h.append('<details class="en-more"><summary>More: %s</summary>%s'
                     '</details>' % (
                         "reading to reading, rooms left cooled, units for "
                         "each person in" if more_first else
                         "rooms left cooled, and units for each person in",
                         "".join(more)))
    for p in problems:
        h.append('<div class="en-warn">%s %s</div>' % (ov.WARN, esc(p)))
    if bills_inline:
        h.append(bills_section(theme, bills, meters, None, expected))
    h.append("</div>")
    return "".join(h)


def bill_years(bills, meters):
    """The choices for the bills' year switch: [(key, label)], newest
    first -- the last twelve bills, the twelve before, both."""
    months = month_bills(bills, meters) if bills is not None else None
    if months is None or not len(months):
        return []
    dates = sorted(pd.Timestamp(d) for d in months["period_start"].unique())

    def span(ds):
        return "%s – %s" % (ds[0].strftime("%b %y"), ds[-1].strftime("%b %y"))
    out = [("a", span(dates[-12:]))]
    if len(dates) > 12:
        out += [("b", span(dates[-24:-12])), ("c", "Both years")]
    return out


def bills_heading(theme, meters):
    """The bills' heading on its own, so the page can put the year switch
    under it rather than above it."""
    c = SERIES[theme]
    by_code = {m["code"]: m for _, m in meters.iterrows()}
    gf = next((k for k, m in by_code.items() if m["behind_solar"]), None)
    order = [k for k in [gf] + [k for k in by_code if k != gf] if k]
    palette = [c["gf"], c["ff"], c["solar"]]
    return ('<div class="ec-h"><span class="t">The bills, month by month'
            '</span><span class="c">units · hover a month for each meter, '
            'the total and the rupees</span>%s</div>'
            % legend([(palette[i], by_code[k]["label"])
                      for i, k in enumerate(order[:3])]))


def bills_section(theme, bills, meters, view=None, expected=None,
                  heading=True):
    """The bills, month by month, and this year against last year.

    view: "a" (the last twelve bills), "b" (the twelve before) or "c"
    (both), chosen with a Streamlit control the page remembers. Without
    one, all three are drawn behind an HTML switch -- which the page's
    30-second refresh put back to "a" every time (20 Nov: "it doesn't
    work"), so the dashboard always passes a view.
    """
    c = SERIES[theme]
    by_code = {m["code"]: m for _, m in meters.iterrows()}
    gf = next((k for k, m in by_code.items() if m["behind_solar"]), None)
    ff = next((k for k in by_code if k != gf), None)
    h = []
    months = month_bills(bills, meters) if bills is not None else []
    if len(months):
        wide = months.pivot_table(index="period_start", columns="meter",
                                  values="units", aggfunc="sum").sort_index()
        money = months.pivot_table(index="period_start", columns="meter",
                                   values="amount_rs", aggfunc="sum")
        flags = months.groupby("period_start")["impossible"].any()
        normal = [v for d, row in wide.iterrows() if not flags.get(d)
                  for v in [row.sum()]]
        cap = max(normal) * 1.15 if normal else None
        order = [k for k in (gf, ff) if k in wide.columns] + \
            [k for k in wide.columns if k not in (gf, ff)]
        palette = [c["gf"], c["ff"], c["solar"]]
        name = (lambda k: by_code[k]["label"] if k in by_code else k)

        def tip(d, row):
            # Each meter, then the month's total (Shamroze, 20 Nov: "show
            # the total too -- this month so many units, this much bill").
            rs = money.loc[d] if d in money.index else {}
            parts = ["%s %s units, Rs %s" % (
                name(k), _n(row[k]), _n(rs.get(k, 0) or 0))
                for k in order if pd.notna(row.get(k))]
            total = sum(float(row[k]) for k in order if pd.notna(row.get(k)))
            spent = sum(float(rs.get(k, 0) or 0) for k in order
                        if pd.notna(row.get(k)))
            return "%s · %s · Total %s units, Rs %s" % (
                pd.Timestamp(d).strftime("%B %Y"), " · ".join(parts),
                _n(total), _n(spent))

        def chart(dates):
            rows = wide.loc[dates]
            return columns(
                [pd.Timestamp(d).strftime("%b %y") for d in dates],
                [[row.get(k) if pd.notna(row.get(k)) else None
                  for k in order] for _, row in rows.iterrows()],
                palette[:len(order)], [tip(d, r) for d, r in rows.iterrows()],
                height=230, cap=cap, top=cap / 1.15 if cap else None)

        def total(dates):
            """Units and rupees in these months, and the queried bills'
            share of each, so two years compare without them."""
            these = months[months["period_start"].isin(dates)]
            odd = these[these["impossible"]]
            return (float(these["units"].astype(float).sum()),
                    float(these["amount_rs"].astype(float).sum()),
                    float(odd["units"].astype(float).sum()),
                    float(odd["amount_rs"].astype(float).sum()))

        def money_text(rs):
            return ("Rs %.1f million" % (rs / 1e6)) if rs >= 1e6 \
                else "Rs %s" % _n(rs)

        def span(dates):
            return "%s – %s" % (pd.Timestamp(dates[0]).strftime("%b %y"),
                                pd.Timestamp(dates[-1]).strftime("%b %y"))

        def table(dates):
            """Every month of the year chosen, in figures (20 Nov: "show me
            all the units" -- a hover is no use on a phone)."""
            rows = ['<table class="en-bt"><thead><tr><th>Month</th>%s'
                    '<th>Total units</th><th>Bill</th></tr></thead><tbody>'
                    % "".join('<th>%s</th>' % esc(name(k).split(" + ")[0])
                              for k in order)]
            for d in reversed(dates):
                row = wide.loc[d]
                rs = money.loc[d] if d in money.index else {}
                odd = bool(flags.get(d))
                rows.append(
                    '<tr%s><td>%s%s</td>%s<td><b>%s</b></td><td>Rs %s</td>'
                    '</tr>' % (
                        ' class="odd"' if odd else "",
                        pd.Timestamp(d).strftime("%b %Y"),
                        " " + ov.WARN if odd else "",
                        "".join('<td>%s</td>' % (_n(row[k]) if pd.notna(
                            row.get(k)) else "—") for k in order),
                        _n(sum(float(row[k]) for k in order
                               if pd.notna(row.get(k)))),
                        _n(sum(float(rs.get(k, 0) or 0) for k in order
                               if pd.notna(row.get(k))))))
            rows.append("</tbody></table>")
            return "".join(rows)

        dates = list(wide.index)
        panels = [("a", dates[-12:])]
        if len(dates) > 12:
            panels.append(("b", dates[-24:-12]))
            panels.append(("c", dates))
        before = total(panels[1][1]) if len(panels) > 1 else None
        compare = panels[1][1] if len(panels) > 1 else None
        if view:
            panels = [p for p in panels if p[0] == view] or panels[:1]
        if heading:
            h.append(bills_heading(theme, meters))
        h.append('<div class="ec-card en-yr" style="padding:16px 18px 26px">')
        if len(panels) > 1:
            # A pure-HTML switch (radio buttons and CSS), so the page
            # needs no Streamlit round trip to change year.
            for key, ds in panels:
                h.append('<input type="radio" name="enyr" id="enyr-%s"%s>'
                         '<label for="enyr-%s">%s</label>'
                         % (key, " checked" if key == "a" else "", key,
                            "Both years" if key == "c" else span(ds)))
        for key, ds in panels:
            u, rs, odd, odd_rs = total(ds)
            line = "<b>%s units</b> · <b>%s</b> in %d months" % (
                _n(u), money_text(rs), len(ds))
            if odd:
                line += " · %s units, %s of it in the queried bill" % (
                    _n(odd), money_text(odd_rs))
            if key == "a" and before and before[0] - before[2]:
                # Like for like: the queried bill out of both years.
                line += ("<br>Against %s%s: units <b>%s</b>, rupees <b>%s</b>"
                         % (span(compare),
                            ", the queried bill left out" if odd or before[2]
                            else "",
                            _pct(before[0] - before[2], u - odd),
                            _pct(before[1] - before[3], rs - odd_rs)))
            h.append('<div class="%s"><div class="en-yr-sum">%s</div>%s'
                     '<details class="en-more" open><summary>Every month, in '
                     'figures</summary>%s</details></div>'
                     % ("p " + key if len(panels) > 1 else "",
                        line, chart(ds), table(ds)))
        for _, b in months[months["impossible"]].iterrows():
            h.append('<div class="en-warn">%s <b>%s, %s: %s units for Rs %s.'
                     '</b> More than the connection can deliver in that month,'
                     ' or over three times this meter\'s usual month'
                     ' — worth querying with K-Electric. It is left out'
                     ' of the scale above.</div>'
                     % (ov.WARN, esc(b["month"]),
                        esc(by_code[b["meter"]]["label"] if b["meter"]
                            in by_code else b["meter"]),
                        format(int(b["units"]), ","),
                        format(int(round(float(b["amount_rs"]))), ",")))
        h.append("</div>")
        h.append(year_on_year(months, c["gf"], expected))
    return "".join(h)


def analysis_page(theme, rooms_rows, off_h, peak_h, rupees, unit_kw, known,
                  cooled, rates, bill_rate, months_used, days=7, after=None):
    """Where the empty, cooled hours are, and what they would cost.

    after: (hours, rupees) empty outside the working day, when the hours
    above are the working day's only. Shown apart, and plainly as the
    figure nobody can vouch for until the units are calibrated.
    """
    t = TOKENS[theme]
    h = [css(theme), '<div class="ec">']
    h.append('<div class="ec-h" style="margin-top:6px"><span class="t">What a '
             'unit costs</span><span class="c">the price of one more unit, '
             'not the average on a bill</span></div><div class="en-tiles">')
    h.append(tile("Off-peak", "Rs %.0f" % rates[0], "a unit, all in"))
    h.append(tile("Peak, %s" % rates[2], "Rs %.0f" % rates[1],
                  "%d%% more than off-peak"
                  % round(100 * (rates[1] / max(1, rates[0]) - 1))))
    if bill_rate:
        h.append(tile("On the bills", "Rs %.0f" % bill_rate,
                      "average over %d bills, impossible ones left out"
                      % months_used))
    h.append("</div>")

    if after is None:
        h.append('<div class="ec-h"><span class="t">Empty and still cooled, '
                 'last %d days</span><span class="c">rooms with a unit somebody'
                 ' could switch off</span></div><div class="en-tiles">' % days)
        h.append(tile("Off-peak room-hours",
                      "%s" % format(int(round(off_h)), ","),
                      "across %d rooms; two rooms for an hour is two" % cooled))
        h.append(tile("Peak-tariff room-hours",
                      "%s" % format(int(round(peak_h)), ","),
                      "6:30–10:30 evening, the expensive ones"))
        h.append(tile("At stake", "Rs %s" % format(int(round(rupees)), ","),
                      "if those units were running", "crit"))
    else:
        h.append('<div class="ec-h"><span class="t">Empty in working hours, '
                 'last %d days</span><span class="c">rooms with a unit somebody'
                 ' could switch off &middot; 10 to 8 on weekdays, when the units'
                 ' are most likely on</span></div><div class="en-tiles">'
                 % days)
        h.append(tile("Room-hours empty",
                      "%s" % format(int(round(off_h + peak_h)), ","),
                      "across %d rooms; %s of them in the 6:30 peak"
                      % (cooled, format(int(round(peak_h)), ","))))
        h.append(tile("At stake", "Rs %s" % format(int(round(rupees)), ","),
                      "if those units were running while nobody was in",
                      "crit"))
        h.append(tile("Nights and weekends",
                      "%s h" % format(int(round(after[0])), ","),
                      "empty outside working hours: Rs %s only if units were"
                      " left on, which nobody can see until they are "
                      "calibrated" % format(int(round(after[1])), ",")))
    h.append('</div><div class="en-note">The hours are measured by the '
             'cameras. The rupees are not: they assume every unit draws %.1f kW'
             ' and was on. %d of %d units are calibrated, so for the rest '
             '"still cooled" means nobody knows it was off.</div>'
             % (unit_kw, known, cooled))

    if rooms_rows:
        total = sum(r["rupees"] for r in rooms_rows) or 1
        for r in rooms_rows:
            r["sub"] = "%.0f h%s%s" % (
                r["hours"], (", %.0f at peak" % r["peak_hours"])
                if r["peak_hours"] >= 0.5 else "",
                (" · +%.0f h nights" % r["after_hours"])
                if after is not None and r.get("after_hours", 0) >= 0.5
                else "")
        rooms_rows = [r for r in rooms_rows if r["rupees"] > 0] or rooms_rows
        top = rooms_rows[:10]
        share = 100.0 * sum(r["rupees"] for r in top) / total
        h.append('<div class="ec-h"><span class="t">Where to start</span>'
                 '<span class="c">the %d rooms that cost the most, %.0f%% of '
                 'the total — a smart plug or a timer on these first'
                 '</span></div><div class="ec-card">%s</div>'
                 % (len(top), share, ranked(
                     top, value=lambda r: r["rupees"],
                     label=lambda r: "Rs %s" % format(int(round(r["rupees"])),
                                                      ","),
                     note=lambda r: (r["dept"] if r["dept"] != r["room"]
                                     else r.get("zone") or "") + (
                         " · %d units" % r["units"] if r["units"] > 1
                         else ""),
                     colour=t["accent"])))
        depts = {}
        for r in rooms_rows:
            d = depts.setdefault(r["dept"], {"room": r["dept"], "rupees": 0.0,
                                             "hours": 0.0, "n": 0})
            d["rupees"] += r["rupees"]
            d["hours"] += r["hours"]
            d["n"] += 1
        drows = sorted(depts.values(), key=lambda d: -d["rupees"])
        for d in drows:
            d["sub"] = "%.0f h" % d["hours"]
        # Where nearly every department is one room, this is the list above
        # again under other names; it earns its place only where departments
        # gather rooms -- Squat Wolf's five, the meeting rooms.
        if len(drows) > 0.7 * len(rooms_rows):
            drows = []
        h.append('' if not drows else
                 '<div class="ec-h"><span class="t">By department</span>'
                 '<span class="c">the same hours, added up by whose rooms they '
                 'are</span></div><div class="ec-card">%s</div>'
                 % ranked(drows, value=lambda d: d["rupees"],
                          label=lambda d: "Rs %s" % format(
                              int(round(d["rupees"])), ","),
                          note=lambda d: "%d room%s" % (
                              d["n"], "" if d["n"] == 1 else "s"),
                          colour=t["accent"]))
    else:
        h.append('<div class="ec-card ec-calm" style="margin-top:14px">%sNo '
                 'room with a unit sat empty in these %d days, or the loop was'
                 ' not running to see it.</div>' % (ov.TICK, days))
    h.append("</div>")
    return "".join(h)
