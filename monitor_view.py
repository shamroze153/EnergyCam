"""Monitor: one campus on one screen, the way plant-monitoring dashboards
put it (Shamroze, 27 Nov, a picture of an energy-monitoring dashboard:
"is tarah ka dashboard ... energy, ACs ya employees ke liye").

A row of live cards, each with its figure now and a small line of the
day behind it; the period's total; the AC's rupees hour by hour (with
people in / nobody in), the meters' days (grid and solar), the people in
the building through the day; and the system's own status.

Rows in, HTML out -- no Streamlit, no database (the dashboard hands
`m`, a dict, see page()). Never a camera picture, never a name.
"""
from overview import css, esc

ICONS = {
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "people": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c.6-3.6 3-5.5 6-5.5'
              's5.4 1.9 6 5.5"/><circle cx="17" cy="9" r="2.4"/><path d="M16.5 '
              '14.6c2.4.2 4 1.9 4.5 4.9"/>',
    "door": '<rect x="5" y="3" width="14" height="18" rx="1.5"/><circle cx="15"'
            ' cy="12" r="1"/>',
    "meter": '<path d="M4 15a8 8 0 1 1 16 0"/><path d="m12 15 4-5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 '
           '12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 '
           '6.3l1.4-1.4"/>',
}

CSS = """<style>
.mo{--mo-gap:14px}
.mo .mo-top{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:4px 0 14px}
.mo .mo-top h2{font-size:22px;font-weight:750;letter-spacing:-.02em;margin:0}
.mo .mo-top .c{color:var(--t3);font-size:13px}
.mo .mo-top .r{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.mo .pill{font-size:12px;color:var(--t2);border:1px solid var(--line2);
padding:4px 11px;border-radius:999px;white-space:nowrap}
.mo .grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--mo-gap)}
.mo .grid3{display:grid;grid-template-columns:1fr 1.6fr 1.3fr;gap:var(--mo-gap);
margin-top:var(--mo-gap)}
.mo .grid2{display:grid;grid-template-columns:1.6fr 1fr;gap:var(--mo-gap);
margin-top:var(--mo-gap)}
.mo .card{background:var(--s1);border:1px solid var(--line);border-radius:16px;
padding:16px 18px;box-shadow:var(--shadow);min-width:0}
.mo .kpi{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;
align-items:center;position:relative;overflow:hidden}
.mo .ic{width:40px;height:40px;border-radius:12px;display:flex;
align-items:center;justify-content:center;grid-row:span 2}
.mo .ic svg{width:21px;height:21px;fill:none;stroke:currentColor;
stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.mo .kpi .k{font-size:11.5px;color:var(--t3);font-weight:600;
letter-spacing:.02em}
.mo .kpi .v{font-size:26px;font-weight:750;letter-spacing:-.02em;
line-height:1.05;white-space:nowrap}
.mo .kpi .v small{font-size:14px;font-weight:600;color:var(--t2);margin-left:3px}
.mo .kpi .s{grid-column:1/-1;margin-top:6px;font-size:12px;color:var(--t3)}
.mo .kpi .s .tx{line-height:1.35;min-height:2.7em}
.mo .kpi .s svg{display:block;width:100%;height:40px;margin-top:6px}
.mo .chip{display:inline-block;font-size:11.5px;font-weight:650;
padding:1px 7px;border-radius:999px;background:var(--s2);color:var(--t2)}
.mo .chip.up{color:var(--crit);background:var(--crit-bg)}
.mo .chip.dn{color:var(--good);background:var(--s2)}
.mo h4{margin:0;font-size:13.5px;font-weight:700;display:flex;gap:8px;
align-items:center;flex-wrap:wrap}
.mo h4 .lg{margin-left:auto;display:flex;gap:10px;font-weight:500;
font-size:11.5px;color:var(--t3)}
.mo h4 .lg i{display:inline-block;width:9px;height:9px;border-radius:3px;
margin-right:4px;vertical-align:-1px}
.mo .big{font-size:38px;font-weight:750;letter-spacing:-.03em;line-height:1.1;
margin-top:10px}
.mo .big small{font-size:16px;color:var(--t2);font-weight:600;margin-left:4px}
.mo .sub{font-size:12.5px;color:var(--t3);margin-top:4px}
.mo .pair{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px;
border-top:1px solid var(--line);padding-top:12px}
.mo .pair .k{font-size:11.5px;color:var(--t3)}
.mo .pair .v{font-size:18px;font-weight:700;margin-top:2px}
.mo .chart svg{width:100%;height:auto;display:block;margin-top:8px}
.mo .chart text{font-size:12px;fill:var(--t3);font-family:inherit}
.mo .chart .bar:hover{opacity:.8}
.mo .st{display:flex;flex-direction:column;gap:9px;margin-top:10px}
.mo .st div{display:flex;gap:9px;align-items:flex-start;font-size:13px}
.mo .st b{font-weight:650}
.mo .st span{color:var(--t3);font-size:12px;display:block}
.mo .dot{flex:none;width:9px;height:9px;border-radius:50%;margin-top:5px}
.mo .ok{background:var(--good)}.mo .bad{background:var(--crit)}
.mo .na{background:var(--line2)}
.mo .allok{margin-top:12px;font-size:12.5px;font-weight:650;color:var(--good)}
.mo .allok.no{color:var(--crit)}
@media (max-width:900px){.mo .grid4{grid-template-columns:repeat(2,minmax(0,1fr))}
.mo .grid3,.mo .grid2{grid-template-columns:1fr}}
@media (max-width:520px){.mo .kpi .v{font-size:22px}.mo .big{font-size:32px}
.mo .kpi{padding:14px}.mo .ic{width:34px;height:34px}}
</style>"""


def _n(v):
    return format(int(round(float(v))), ",")


def _rs(v):
    return "Rs %s" % _n(v)


def spark(values, colour, w=112, h=34):
    """A small line of the day: the area under it faint, the line 2 px."""
    pts = [(i, float(v)) for i, v in enumerate(values or [])
           if v is not None]
    if len(pts) < 2:
        return '<svg viewBox="0 0 %d %d"></svg>' % (w, h)
    n = max(len(values) - 1, 1)
    top = max(v for _, v in pts) or 1.0
    xy = [(2 + (w - 4) * i / float(n), h - 3 - (h - 8) * v / top)
          for i, v in pts]
    line = " ".join("%.1f,%.1f" % p for p in xy)
    area = "M%.1f,%d L%s L%.1f,%d Z" % (xy[0][0], h - 2, line, xy[-1][0],
                                         h - 2)
    return ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" '
            'aria-hidden="true"><path d="%s" '
            'style="fill:%s;opacity:.14"/><polyline points="%s" '
            'style="fill:none;stroke:%s;stroke-width:2;stroke-linejoin:round;'
            'stroke-linecap:round"/></svg>' % (w, h, area, colour, line,
                                               colour))


def _chip(now, before, lower_better=True, unit="%"):
    """+12% / -8% against `before`, red where it went the wrong way."""
    if now is None or not before:
        return ""
    ch = 100.0 * (float(now) / float(before) - 1)
    worse = ch > 0 if lower_better else ch < 0
    return '<span class="chip %s">%s%.0f%s</span>' % (
        "up" if worse else "dn", "+" if ch >= 0 else "&minus;", abs(ch), unit)


def kpi(icon, tint, label, value, unit, note, line, colour):
    return ('<div class="card kpi"><div class="ic" style="background:%s;'
            'color:%s"><svg viewBox="0 0 24 24">%s</svg></div><div class="k">'
            '%s</div><div class="v">%s<small>%s</small></div><div class="s">'
            '<div class="tx">%s</div>%s</div></div>'
            % (tint, colour, ICONS[icon], esc(label), value, esc(unit), note,
               spark(line, colour)))


def bars(labels, stacks, colours, tips, w=520, h=170, marks=None, every=1):
    """Columns of stacked parts, thin and rounded at the top, a 2 px gap
    between parts; a label under every `every`th column."""
    n = len(stacks)
    if not n:
        return ""
    totals = [sum(p or 0 for p in s) for s in stacks]
    top = max(totals) or 1.0
    left, base, head = 30, h - 20, 14
    gap = 4 if n <= 12 else 2
    bw = (w - left - 4 - gap * (n - 1)) / float(n)
    out = ['<svg viewBox="0 0 %d %d" role="img">' % (w, h)]
    for k in range(3):
        v = top * k / 2.0
        y = base - (base - head) * k / 2.0
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" style="stroke:'
                   'var(--line);stroke-width:1"/><text x="%d" y="%.1f" '
                   'text-anchor="end">%s</text>'
                   % (left, w, y, y, left - 5, y + 3,
                      ("%.0fk" % (v / 1000.0)) if v >= 1000 else "%.0f" % v))
    for i, (s, tip) in enumerate(zip(stacks, tips)):
        x = left + 2 + i * (bw + gap)
        y = base
        parts = [(p, c) for p, c in zip(s, colours) if p]
        for j, (p, c) in enumerate(parts):
            ph = (base - head) * p / top
            last = j == len(parts) - 1
            r = min(3.0, bw / 2, ph) if last else 0
            y2 = y - ph
            hh = max(ph - (2 if j else 0), 0.5)
            if r:
                out.append('<path class="bar" d="M%.1f %.1f v-%.1f q0 -%.1f '
                           '%.1f -%.1f h%.1f q%.1f 0 %.1f %.1f v%.1f z" '
                           'style="fill:%s"><title>%s</title></path>'
                           % (x, y - (2 if j else 0), hh - r, r, r, r,
                              bw - 2 * r, r, r, r, hh - r, c, esc(tip)))
            else:
                out.append('<rect class="bar" x="%.1f" y="%.1f" width="%.1f" '
                           'height="%.1f" style="fill:%s"><title>%s</title>'
                           '</rect>' % (x, y2, bw, hh, c, esc(tip)))
            y = y2
        if marks and marks[i]:
            out.append('<text x="%.1f" y="%.1f" text-anchor="middle" style="'
                       'font-weight:650;fill:var(--t2)">%s</text>'
                       % (x + bw / 2, y - 4, esc(marks[i])))
        if i % every == 0 and labels[i]:
            out.append('<text x="%.1f" y="%d" text-anchor="middle">%s</text>'
                       % (x + bw / 2, h - 5, esc(labels[i])))
    out.append("</svg>")
    return "".join(out)


def curve(values, colour, w=520, h=150, now_i=None):
    """The people in the building, quarter-hour by quarter-hour."""
    pts = [(i, float(v)) for i, v in enumerate(values or []) if v is not None]
    if len(pts) < 2:
        return '<div class="sub">Not enough of the day watched yet.</div>'
    n = max(len(values) - 1, 1)
    top = max(max(v for _, v in pts), 1.0)
    left, base, head = 30, h - 20, 10
    xy = [(left + (w - left - 4) * i / float(n),
           base - (base - head) * v / top) for i, v in pts]
    line = " ".join("%.1f,%.1f" % p for p in xy)
    out = ['<svg viewBox="0 0 %d %d" role="img">' % (w, h)]
    for k in range(3):
        y = base - (base - head) * k / 2.0
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" style="stroke:'
                   'var(--line)"/><text x="%d" y="%.1f" text-anchor="end">'
                   '%d</text>' % (left, w, y, y, left - 5, y + 3,
                                  round(top * k / 2.0)))
    out.append('<path d="M%.1f,%d L%s L%.1f,%d Z" style="fill:%s;opacity:'
               '.15"/>' % (xy[0][0], base, line, xy[-1][0], base, colour))
    out.append('<polyline points="%s" style="fill:none;stroke:%s;'
               'stroke-width:2;stroke-linejoin:round"/>' % (line, colour))
    for hr in range(0, 25, 6):
        x = left + (w - left - 4) * (hr * 4) / float(n)
        out.append('<text x="%.1f" y="%d" text-anchor="middle">%s</text>'
                   % (x, h - 5, "%d %s" % (hr % 12 or 12,
                                           "am" if hr < 12 or hr == 24
                                           else "pm")))
    out.append("</svg>")
    return "".join(out)


def _hour(h):
    return "%d%s" % (h % 12 or 12, "a" if h < 12 else "p")


def page(theme, m, series):
    """`m`: campus, when, live (bool), live_text; ac_kw, units_on,
    units_readable, rate, people_now, people_curve (96 quarter-hours),
    rooms_busy, rooms_total, ac_today_rs, ac_today_waste, ac_yday_rs,
    hourly / hourly_yday ([[rupees, nobody-in rupees]] x 24), now_hour,
    days ([(label, grid units, solar kWh)]), status ([(ok: True / False /
    None, label, note)]). `series`: energy_view.SERIES[theme] -- the grid
    and solar colours the Energy page uses."""
    acc, crit, good = "var(--accent)", "var(--crit)", "var(--good)"
    sun, grid = series["solar"], series["gf"]
    hourly = m.get("hourly") or [[0.0, 0.0]] * 24
    nh = m.get("now_hour", 23)
    # the last 24 hours, as plant monitors show them: yesterday's hours
    # after this one, then today's to now
    yh = m.get("hourly_yday")
    roll = ([(h, yh[h]) for h in range(nh + 1, 24)] if yh else []) + \
        [(h, hourly[h]) for h in range(0, nh + 1)]
    if not yh:
        roll += [(h, [0.0, 0.0]) for h in range(nh + 1, 24)]
    ac_line = [v[0] for _, v in roll]
    days = m.get("days") or []
    used = [g for _, g, _ in days]
    last = days[-1] if days else None
    prev = days[-2] if len(days) > 1 else None
    tint = "color-mix(in srgb, %s 14%%, transparent)"
    kpis = [
        kpi("bolt", tint % acc, "AC drawing now",
            "%.1f" % (m.get("ac_kw") or 0), "kW",
            "%d of %d readable units running &middot; about <b>%s</b> an hour"
            % (m.get("units_on") or 0, m.get("units_readable") or 0,
               _rs((m.get("ac_kw") or 0) * (m.get("rate") or 67))),
            ac_line, acc),
        kpi("people", tint % good, "People in now",
            "%d" % (m.get("people_now") or 0), "",
            "the day's busiest so far <b>%d</b>" % (m.get("peak") or 0),
            [v for v in (m.get("people_curve") or [])][:(nh + 1) * 4], good),
        kpi("door", tint % sun, "Rooms in use",
            "%d" % (m.get("rooms_busy") or 0),
            "of %d" % (m.get("rooms_total") or 0),
            "%.0f%% of the rooms the cameras watch" % (
                100.0 * (m.get("rooms_busy") or 0)
                / max(m.get("rooms_total") or 1, 1)),
            [v for v in (m.get("people_curve") or [])][:(nh + 1) * 4], sun),
        kpi("meter", tint % grid, "Grid, the last full day",
            _n(last[1]) if last and last[1] is not None else "&ndash;",
            "units", ("%s %s" % (esc(last[0]), _chip(last[1], prev[1])
                                if prev else "")) if last else
            "no meter readings yet", used[-14:], grid),
    ]
    today, waste = m.get("ac_today_rs") or 0.0, m.get("ac_today_waste") or 0.0
    yday = m.get("ac_yday_rs") or 0.0
    hours_chart = bars(
        [_hour(h) for h, _ in roll],
        [[v[0] - v[1], v[1]] for _, v in roll], [acc, crit],
        ["%s%s to %s: %s, %s of it with nobody in" % (
            "yesterday " if yh and i < 23 - nh else "", _hour(h),
            _hour((h + 1) % 24), _rs(v[0]), _rs(v[1]))
         for i, (h, v) in enumerate(roll)], w=400, h=170, every=4)
    day_chart = bars(
        [d[0] for d in days],
        [[g or 0, s or 0] for _, g, s in days], [grid, sun],
        ["%s: %s units from the grid%s" % (
            lab, _n(g or 0), (", %s kWh solar" % _n(s)) if s else "")
         for lab, g, s in days],
        w=360, h=170, marks=[_n(g) if g else "" for _, g, _ in days])
    st = m.get("status") or []
    bad = [s for s in st if s[0] is False]
    status = "".join(
        '<div><i class="dot %s"></i><div><b>%s</b><span>%s</span></div></div>'
        % ("ok" if ok else "bad" if ok is False else "na", esc(lab), note)
        for ok, lab, note in st)
    # each <style> its own markdown block: two on one line leave the second
    # open and swallow the page (CLAUDE.md, the Streamlit gotcha)
    return "\n\n".join([css(theme), CSS]) + "\n\n" + "".join([
        '<div class="ec mo">',
        '<div class="mo-top"><h2>Monitor &middot; %s</h2><span class="c">'
        'the ACs, the people and the meters on one screen</span><div '
        'class="r"><span class="pill">Today, midnight to now</span></div>'
        '</div>' % esc(m.get("campus", "")),
        '<div class="grid4">%s</div>' % "".join(kpis),
        '<div class="grid3">',
        '<div class="card"><h4>AC, total for today</h4><div class="big" '
        'style="color:%s">%s</div><div class="sub">every room with a unit, '
        'from midnight</div><div class="pair"><div><div class="k">With nobody '
        'in</div><div class="v" style="color:%s">%s</div></div><div><div '
        'class="k">Yesterday, whole day</div><div class="v">%s</div></div>'
        '</div><div class="pair"><div><div class="k">An hour, so far</div>'
        '<div class="v">%s</div></div><div><div class="k">Solar, last day'
        '</div><div class="v">%s</div></div></div></div>'
        % (acc, _rs(today), crit, _rs(waste), _rs(yday),
           _rs(today / max(nh + 1, 1)),
           ("%s kWh" % _n(last[2])) if last and last[2] else "&ndash;"),
        '<div class="card chart"><h4>AC by the hour, last 24 hours'
        '<span class="lg"><span>'
        '<i style="background:%s"></i>people in</span><span><i style='
        '"background:%s"></i>nobody in</span></span></h4>%s</div>'
        % (acc, crit, hours_chart),
        '<div class="card chart"><h4>Meters, day by day<span class="lg">'
        '<span><i style="background:%s"></i>grid</span><span><i style='
        '"background:%s"></i>solar</span></span></h4>%s</div>'
        % (grid, sun, day_chart or '<div class="sub">No meter readings for '
           'this campus yet.</div>'),
        '</div>',
        '<div class="grid2">',
        '<div class="card chart"><h4>People in the building today</h4>%s</div>'
        % curve(m.get("people_curve") or [], good),
        '<div class="card"><h4>System status</h4><div class="st">%s</div>'
        '<div class="allok%s">%s</div></div>'
        % (status, " no" if bad else "",
           "All systems normal" if not bad else
           "%d need a look" % len(bad)),
        '</div></div>'])
