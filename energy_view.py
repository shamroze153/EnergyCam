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
import statistics

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
    out = []
    for k, (start, end) in enumerate(windows):
        spans = alive[k] if alive is not None else [(start, end)]
        total = 0.0
        for _, rows in mine.groupby("room"):
            stamps = list(rows["timestamp"])
            status, people = list(rows["status"]), list(rows["people"])
            for i, a in enumerate(stamps):
                if status[i] != "occupied":
                    continue
                b = stamps[i + 1] if i + 1 < len(stamps) else end
                n = people[i] if people[i] == people[i] else 1
                for s0, s1 in spans:
                    x, y = max(a, start, s0), min(b, end, s1)
                    if y > x:
                        total += max(1, int(n or 1)) \
                            * (y - x).total_seconds() / 3600.0
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
    b = b.assign(impossible=b.index.isin(bad.index))
    return b.sort_values("period_start")


# ===================================================================== drawing

def _nice(top):
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000,
                 2500, 5000, 10000):
        if top / step <= 5:
            return step, max(step, -(-int(top) // step) * step)
    return 10000, -(-int(top) // 10000) * 10000


def columns(labels, stacks, colours, tips, height=220, cap=None,
            marks=None):
    """Stacked columns, one per label; the parts of each stack in order.

    stacks: per column, a list of values (None or 0 draws nothing).
    cap: a ceiling for the scale; a column above it is drawn to the top
         and marked, so one impossible month does not flatten the rest.
    marks: per column, None or a short word drawn above it.
    """
    totals = [sum(v or 0 for v in s) for s in stacks]
    top = max([1.0] + [t for t in totals if cap is None or t <= cap])
    step, high = _nice(top * 1.05)
    n = len(labels)
    width = 100.0 / max(1, n)
    bar = min(width * 0.7, width - 0.6)
    svg = ['<svg viewBox="0 0 100 100" preserveAspectRatio="none" '
           'aria-hidden="true">']
    for v in range(0, high + 1, step):
        y = 100 - 100.0 * v / high
        svg.append('<line x1="0" x2="100" y1="%.2f" y2="%.2f" stroke="%s" '
                   'stroke-width="1" vector-effect="non-scaling-stroke"/>'
                   % (y, y, "var(--axis)" if v == 0 else "var(--grid)"))
    over = []
    for i, parts in enumerate(stacks):
        x = i * width + (width - bar) / 2
        base = 0.0
        clipped = cap is not None and totals[i] > cap
        scale = (high / totals[i]) if clipped and totals[i] else 1.0
        for value, colour in zip(parts, colours):
            if not value:
                continue
            h = 100.0 * value * scale / high
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
    for v in range(0, high + 1, step):
        # In full under ten thousand, compact on an axis that reaches it:
        # "25,000" did not fit the gutter and broke over two lines.
        text = (("%gk" % (v / 1000.0)) if high >= 10000 and v
                else format(v, ","))
        html.append('<span class="yt" style="top:%.2f%%">%s</span>'
                    % (100 - 100.0 * v / high, text))
    every = max(1, -(-n // 10))
    for i, label in enumerate(labels):
        if i % every == 0 or i == n - 1:
            html.append('<span class="xt" style="left:%.2f%%">%s</span>'
                        % ((i + 0.5) * width, esc(label)))
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
.en-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
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
@media (max-width:760px){.en-ranked .row{grid-template-columns:1fr 90px}
.en-ranked .tr{grid-column:1/-1;order:3}.en-sun{grid-template-columns:1fr}}
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


# ===================================================================== pages

def meters_page(theme, table, kind, meters, bills, cooled_hours, rate,
                problems, campus_has_meters, campus, usage=None):
    """The Meters view below the form: days, then months."""
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
        last = (table[has_units].iloc[-1]
                if has_units is not None and has_units.any()
                else table.iloc[-1])
        grid = sum(float(last[k]) for k in (gf, ff)
                   if k and pd.notna(last.get(k)))
        sun = float(last["solar"]) if pd.notna(last.get("solar")) else None
        h.append('<div class="ec-h"><span class="t">%s</span><span class="c">'
                 'the last full day between two readings</span></div>'
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
        h.append(solar_block(table, gf, rate, c["solar"], c["gf"]))

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
        h.append('<div class="ec-h"><span class="t">What the building used, '
                 'day by day</span><span class="c">units; hover a day</span>%s'
                 '</div>' % legend([(c["gf"], "Ground floor + basement, grid"),
                                    (c["solar"], "Solar"),
                                    (c["ff"], "First floor + cafe, grid")]))
        h.append('<div class="ec-card" style="padding:16px 18px 26px">%s'
                 '<div class="en-note">A reading at eleven covers eleven the '
                 'day before to eleven that day, so it is drawn on the day '
                 'before. Every day is put on a 24-hour footing, so a reading '
                 'taken an hour early or late does not make a day look smaller '
                 'or bigger: hover a day for the units as read and the hours '
                 'they covered. "avg" is a day with no reading of its own: the '
                 'units across the gap are shared out evenly.%s</div></div>'
                 % (columns(labels, stacks, [c["gf"], c["solar"], c["ff"]],
                            tips, height=230, marks=marks),
                    " Solar was read as the inverter's running total and"
                    " turned into days." if kind == "total" else ""))

        if cooled_hours is not None:
            tips = ["%s · %.0f room-hours empty with a unit assumed on"
                    % (pd.Timestamp(d).strftime("%A %d %B"), v)
                    for d, v in zip(table["day"], cooled_hours)]
            h.append('<div class="ec-h"><span class="t">Rooms on these meters '
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
                h.append('<div class="ec-h"><span class="t">Units for the use '
                         'they were for</span><span class="c">grid and solar '
                         'units per person-hour in the building · lower is '
                         'better</span></div><div class="ec-card" style="'
                         'padding:16px 18px 26px">%s<div class="en-note">A '
                         'person-hour is one person in for an hour, from the '
                         'cameras: a busy day is allowed more units, an empty '
                         'day with the same units shows up tall. Days the '
                         'cameras watched only part of read high.</div></div>'
                         % columns(labels, per, [c["ff"]], tips, height=150))
    for p in problems:
        h.append('<div class="en-warn">%s %s</div>' % (ov.WARN, esc(p)))

    months = month_bills(bills, meters)
    if len(months):
        wide = months.pivot_table(index="period_start", columns="meter",
                                  values="units", aggfunc="sum").sort_index()
        flags = months.groupby("period_start")["impossible"].any()
        normal = [v for d, row in wide.iterrows() if not flags.get(d)
                  for v in [row.sum()]]
        cap = max(normal) * 1.15 if normal else None
        order = [k for k in (gf, ff) if k in wide.columns] + \
            [k for k in wide.columns if k not in (gf, ff)]
        palette = [c["gf"], c["ff"], c["solar"]]
        labels, stacks, tips = [], [], []
        for d, row in wide.iterrows():
            labels.append(pd.Timestamp(d).strftime("%b %y"))
            stacks.append([row.get(k) if pd.notna(row.get(k)) else None
                           for k in order])
            tips.append("%s · %s" % (
                pd.Timestamp(d).strftime("%B %Y"), " · ".join(
                    "%s %s units" % (by_code[k]["label"] if k in by_code
                                     else k,
                                     format(int(row[k]), ","))
                    for k in order if pd.notna(row.get(k)))))
        h.append('<div class="ec-h"><span class="t">The bills, month by month'
                 '</span><span class="c">units, in date order</span>%s</div>'
                 % legend([(palette[i], by_code[k]["label"] if k in by_code
                            else k) for i, k in enumerate(order)]))
        h.append('<div class="ec-card" style="padding:16px 18px 26px">%s'
                 % columns(labels, stacks, palette[:len(order)], tips,
                           height=230, cap=cap))
        for _, b in months[months["impossible"]].iterrows():
            h.append('<div class="en-warn">%s <b>%s, %s: %s units for Rs %s.'
                     '</b> More than the connection can deliver in that month'
                     ' — worth querying with K-Electric. It is left out'
                     ' of the scale above.</div>'
                     % (ov.WARN, esc(b["month"]),
                        esc(by_code[b["meter"]]["label"] if b["meter"]
                            in by_code else b["meter"]),
                        format(int(b["units"]), ","),
                        format(int(round(float(b["amount_rs"]))), ",")))
        h.append("</div>")
    h.append("</div>")
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
