"""Every employee at a campus by the attendance machines, as HTML.

Shamroze, 25 Nov 2026: HR's export -- "sab daldo". Two views, one at a
time: the usual (every working day of the export: days in, the usual in
and out, hours in the building, late days, times out and back), and one
day's list (in, out, hours, outings), earliest first. On the office
laptop only: it names everybody.

No Streamlit and no database: rows in (attendance.summary), HTML out.
"""
from overview import css, esc

_CSS = """<style>
.at .at-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
gap:12px;margin:6px 0 14px}
.at .at-tiles .ec-kpi{padding:12px 14px}
.at .at-wrap{max-height:560px;overflow:auto;border-radius:12px}
.at table{width:100%;border-collapse:collapse;font-size:13px;
font-variant-numeric:tabular-nums}
.at th{position:sticky;top:0;background:var(--s1);text-align:right;
font-size:11.5px;font-weight:650;color:var(--t3);padding:8px;
border-bottom:1px solid var(--line);white-space:nowrap}
.at td{text-align:right;padding:7px 8px;border-bottom:1px solid var(--line);
white-space:nowrap}
.at th:first-child,.at td:first-child,.at th:nth-child(2),
.at td:nth-child(2){text-align:left}
.at td:first-child b{font-weight:650}
.at td:first-child span{display:block;font-size:11px;color:var(--t3)}
.at td.late{color:var(--crit);font-weight:650}
.at .bar{display:inline-block;height:6px;border-radius:99px;background:#2a9d63;
vertical-align:middle;margin-left:6px}
.at .note{font-size:12px;color:var(--t3);margin-top:8px;line-height:1.5}
</style>"""


def _hhmm(h):
    if h is None:
        return "--"
    m = int(round(h * 60))
    return "%02d:%02d" % ((m // 60) % 24, m % 60)


def _t(x):
    return x.strftime("%H:%M") if x is not None and hasattr(x, "strftime") \
        else "--"


def _dur(minutes):
    if minutes is None:
        return "--"
    m = int(round(minutes))
    return "%dh %02dm" % (m // 60, m % 60)


def _who(r, roster):
    p = roster.get(r["eid"], {})
    return ('<b>%s</b><span>%s</span>'
            % (esc(p.get("name") or "Code %s" % r["eid"]),
               esc(" · ".join(x for x in (p.get("employee_id"),
                                          p.get("designation")) if x))))


def usual(mode, rows, roster, start=10.0, grace=15):
    """Every employee over the export: the usual, one row each."""
    if not rows:
        return ""
    rows = sorted(rows, key=lambda r: (
        (roster.get(r["eid"], {}).get("department") or "~"),
        (roster.get(r["eid"], {}).get("name") or r["eid"])))
    work = [r for r in rows if r["days_in"]]
    ins = sorted(r["usual_in"] for r in work if r["usual_in"] is not None)
    hrs = [r["inside_h"] for r in work if r["inside_h"] is not None]
    late = sum(r["late"] for r in work)
    seen = sum(r["days_in"] for r in work)
    tiles = [("Employees through the machines", "%d" % len(rows),
              "at least one day in the export"),
             ("Usual arrival", _hhmm(ins[len(ins) // 2]) if ins else "--",
              "the middle employee's usual first IN"),
             ("In the building, a day", "%.1f h" % (sum(hrs) / len(hrs))
              if hrs else "--", "IN to OUT, averaged"),
             ("In after %s" % _hhmm(start + grace / 60.0),
              "%d%%" % round(100.0 * late / seen) if seen else "--",
              "of days in -- teams on a later shift included")]
    top = max(hrs) if hrs else 1.0
    body = []
    for r in rows:
        p = roster.get(r["eid"], {})
        w = 0 if r["inside_h"] is None else int(60 * r["inside_h"] / top)
        body.append(
            '<tr><td>%s</td><td>%s</td><td>%d of %d</td><td>%s</td>'
            '<td>%s</td><td>%s<i class="bar" style="width:%dpx"></i></td>'
            '<td class="%s">%s</td><td>%s</td></tr>'
            % (_who(r, roster), esc(p.get("department") or ""), r["days_in"],
               r["of"], _hhmm(r["usual_in"]), _hhmm(r["usual_out"]),
               ("%.1f h" % r["inside_h"]) if r["inside_h"] is not None
               else "--", w, "late" if r["late"] >= 3 else "",
               r["late"], ("%.1f" % r["outings"]) if r["outings"]
               is not None else "--"))
    return "".join([
        css(mode), _CSS, '<div class="ec at">',
        '<div class="at-tiles">%s</div>' % "".join(
            '<div class="ec-card ec-kpi"><div class="k">%s</div><div class="v">'
            '%s</div><div class="s">%s</div></div>' % (esc(k), esc(v), esc(s))
            for k, v, s in tiles),
        '<div class="ec-card at-wrap"><table><thead><tr><th>Employee</th>'
        '<th>Department</th><th>Days in</th><th>Usual in</th><th>Usual out'
        '</th><th>In the building</th><th>Days in after %s</th><th>Out and '
        'back, a day</th></tr></thead><tbody>%s</tbody></table></div>'
        % (_hhmm(start + grace / 60.0), "".join(body)),
        '<div class="note">From HR\'s export of the attendance machines '
        '(hand-typed Life app punches left out): working days only; the '
        'usual is the middle day. A day with no OUT punch has no "out"; a '
        'night shift crosses midnight and is split between two days. Time '
        'in the building, not the work done.</div></div>'])


def one_day(mode, rows, roster, day, start=10.0, grace=15):
    """One day: everybody in, earliest first."""
    got = [(r, r["days"][day]) for r in rows if day in r["days"]]
    if not got:
        return '<div class="ec"><div class="ec-calm">Nobody through the ' \
               'machines on %s.</div></div>' % esc(day)
    got.sort(key=lambda x: x[1]["first_in"])
    late_line = start + grace / 60.0
    body = []
    for r, s in got:
        p = roster.get(r["eid"], {})
        f = s["first_in"]
        late = f.hour + f.minute / 60.0 > late_line
        out_min = sum((b - a).total_seconds() / 60.0 for a, b in s["outings"])
        body.append(
            '<tr><td>%s</td><td>%s</td><td class="%s">%s</td><td>%s</td>'
            '<td>%s</td><td>%s</td></tr>'
            % (_who(r, roster), esc(p.get("department") or ""),
               "late" if late else "", _t(f), _t(s["last_out"]),
               _dur(s["inside_min"]),
               ("%d, %s" % (len(s["outings"]), _dur(out_min)))
               if s["outings"] else "--"))
    return "".join([
        css(mode), _CSS, '<div class="ec at">',
        '<div class="ec-card at-wrap"><table><thead><tr><th>Employee</th>'
        '<th>Department</th><th>In</th><th>Out</th><th>In the building</th>'
        '<th>Out and back</th></tr></thead><tbody>%s</tbody></table></div>'
        % "".join(body),
        '<div class="note">%d employees in; red: in after %s. A night '
        'shift crosses midnight: its hours are split between two days.'
        '</div></div>' % (len(got), _hhmm(late_line))])
