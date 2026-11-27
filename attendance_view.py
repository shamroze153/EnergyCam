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
.at td .dd{font-size:11px;color:var(--t3);font-weight:400}
</style>"""


SCORE_PARTS = (("In the building", 0.5,
                "hours IN to OUT, of a 10-hour office day"),
               ("Regular", 0.3,
                "days in within half an hour of their own usual arrival"),
               ("Days in", 0.2, "working days in, of the export's"))


def score(r, office_h=10.0):
    """An employee's attendance score, 0-100, from the machines alone
    (Shamroze, 25 Nov: a score for every one of 140-H's ~160 a day, not
    only those whose desk a camera sees): time in the building (50%),
    coming in at their own usual hour -- a later shift is not late (30%),
    and days in (20%). Time in the building, never the work itself.
    None for nobody in on a working day."""
    if not r.get("days_in"):
        return None
    hours = r.get("inside_h")
    inside = min(1.0, hours / office_h) if hours is not None else None
    usual = r.get("usual_in")
    firsts = [s["first_in"] for s in (r.get("days") or {}).values()
              if s.get("first_in") is not None]
    if usual is not None and firsts:
        steady = sum(1 for t in firsts
                     if abs(t.hour + t.minute / 60.0 - usual) <= 0.5) \
            / float(len(firsts))
    else:
        steady = 0.0
    present = min(1.0, r["days_in"] / float(max(1, r.get("of") or 1)))
    if inside is None:
        # never an OUT punch to close a day: the hours are not known, so
        # the other two parts carry the score (not a zero for the hours)
        return int(round(100 * (0.3 * steady + 0.2 * present) / 0.5))
    return int(round(100 * (0.5 * inside + 0.3 * steady + 0.2 * present)))


def overall(att, desk):
    """Attendance and desk score together (Shamroze, 25 Nov: one score for
    every employee, to hand in): half each where a camera sees their named
    desk, the attendance score alone where not. Time, never the work."""
    if att is None:
        return None
    if desk is None:
        return att
    return int(round(0.5 * att + 0.5 * desk))


def _key(eid):
    return str(eid or "").strip().lstrip("0") or "0"


def table(rows, roster, desk=None, start=10.0, grace=60):
    """One dict a row, in the page's order -- for the download."""
    desk = desk or {}
    out = []
    for r in sorted(rows, key=lambda r: (
            (roster.get(r["eid"], {}).get("department") or "~"),
            (roster.get(r["eid"], {}).get("name") or r["eid"]))):
        p = roster.get(r["eid"], {})
        att = score(r)
        d = desk.get(_key(r["eid"])) or {}
        ds = int(round(d["score"])) if d.get("score") is not None else None
        out.append({
            "Employee": p.get("name") or "Code %s" % r["eid"],
            "Employee ID": p.get("employee_id") or r["eid"],
            "Designation": p.get("designation") or "",
            "Department": p.get("department") or "",
            "Days in": r["days_in"], "Working days": r["of"],
            "Usual in": _hhmm(r["usual_in"]),
            "Usual out": _hhmm(r["usual_out"]),
            "Hours in the building, a day": round(r["inside_h"], 1)
            if r["inside_h"] is not None else None,
            "Days ending on an OUT punch": r.get("hours_days"),
            "Days in after %s" % _hhmm(start + grace / 60.0): r["late"],
            "Attendance score": att,
            "Desk score": ds, "Desk days": d.get("days"),
            "Overall score": overall(att, ds),
            "Measured by": "machines + desk camera" if ds is not None
            else "machines (desk not seen by a camera, or not named yet)"})
    return out


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


def usual(mode, rows, roster, start=10.0, grace=60, desk=None):
    """Every employee over the export: the usual, one row each, with the
    desk score where a camera sees their named desk (`desk`: {employee
    code: {"score", "days"}}, progress_view.period_score) and both
    together as the overall score."""
    if not rows:
        return ""
    desk = desk or {}
    rows = sorted(rows, key=lambda r: (
        (roster.get(r["eid"], {}).get("department") or "~"),
        (roster.get(r["eid"], {}).get("name") or r["eid"])))
    work = [r for r in rows if r["days_in"]]
    ins = sorted(r["usual_in"] for r in work if r["usual_in"] is not None)
    hrs = [r["inside_h"] for r in work if r["inside_h"] is not None]
    late = sum(r["late"] for r in work)
    seen = sum(r["days_in"] for r in work)
    scores = [s for s in (score(r) for r in work) if s is not None]
    def desk_of(r):
        d = desk.get(_key(r["eid"])) or {}
        return int(round(d["score"])) if d.get("score") is not None else None
    with_desk = [r for r in work if desk_of(r) is not None]
    overalls = [o for o in (overall(score(r), desk_of(r)) for r in work)
                if o is not None]
    tiles = [("Employees through the machines", "%d" % len(rows),
              "at least one day in the export"),
             ("Overall score, average", "%d" % round(sum(overalls)
                                                     / len(overalls))
              if overalls else "--", "attendance, with the desk where seen"),
             ("With a desk score", "%d of %d" % (len(with_desk), len(work)),
              "their named desk in a camera"),
             ("Attendance score, average", "%d" % round(sum(scores)
                                                        / len(scores))
              if scores else "--", "building 50%, regular 30%, days in 20%"),
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
        sc = score(r)
        d = desk.get(_key(r["eid"])) or {}
        ds = desk_of(r)
        ov = overall(sc, ds)
        body.append(
            '<tr><td>%s</td><td>%s</td><td><b>%s</b></td><td>%s</td>'
            '<td>%s</td><td>%d of %d</td>'
            '<td>%s</td>'
            '<td>%s</td><td>%s<i class="bar" style="width:%dpx"></i></td>'
            '<td class="%s">%s</td><td>%s</td></tr>'
            % (_who(r, roster), esc(p.get("department") or ""),
               ov if ov is not None else "--",
               sc if sc is not None else "--",
               ('%d <span class="dd">%dd</span>' % (ds, d.get("days") or 0))
               if ds is not None else '<span class="dd">not seen</span>',
               r["days_in"],
               r["of"], _hhmm(r["usual_in"]), _hhmm(r["usual_out"]),
               ("%.1f h" % r["inside_h"]) if r["inside_h"] is not None
               else "--", w, "late" if r["late"] >= 3 else "",
               r["late"], ("%.1f" % r["outings"]) if r["outings"]
               is not None else "--"))
    return "".join([
        # each <style> its own markdown block (see productivity_view._styles)
        css(mode), "\n\n", _CSS, "\n\n", '<div class="ec at">',
        '<div class="at-tiles">%s</div>' % "".join(
            '<div class="ec-card ec-kpi"><div class="k">%s</div><div class="v">'
            '%s</div><div class="s">%s</div></div>' % (esc(k), esc(v), esc(s))
            for k, v, s in tiles),
        '<div class="ec-card at-wrap"><table><thead><tr><th>Employee</th>'
        '<th>Department</th><th>Overall</th><th>Attendance</th><th>Desk</th>'
        '<th>Days in</th><th>Usual in</th>'
        '<th>Usual out'
        '</th><th>In the building</th><th>Days in after %s</th><th>Out and '
        'back, a day</th></tr></thead><tbody>%s</tbody></table></div>'
        % (_hhmm(start + grace / 60.0), "".join(body)),
        '<div class="note">From HR\'s export of the attendance machines '
        '(hand-typed Life app punches left out): working days only; the '
        'usual is the middle day. Hours in the building count only the '
        'days that end on an OUT punch; whoever never punches out has the '
        'attendance score from the other two parts. A night shift crosses '
        'midnight and is split between two days. '
        '<b>Attendance</b>: hours in the building of a 10-hour day (50%), '
        'coming in within half an hour of their own usual -- a later shift '
        'is not late (30%), days in (20%). <b>Desk</b>: where a camera sees '
        'their named desk, the last working days\' desk score -- at the '
        'desk of the office day (50%), in stretches of an hour or more '
        '(30%), on time (20%); "5d" is the days it averages. <b>Overall</b>: '
        'half each where both are known, else the attendance score. Time '
        'in the building and at the desk, not the work done.</div></div>'])


def one_day(mode, rows, roster, day, start=10.0, grace=60):
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
        css(mode), "\n\n", _CSS, "\n\n", '<div class="ec at">',
        '<div class="ec-card at-wrap"><table><thead><tr><th>Employee</th>'
        '<th>Department</th><th>In</th><th>Out</th><th>In the building</th>'
        '<th>Out and back</th></tr></thead><tbody>%s</tbody></table></div>'
        % "".join(body),
        '<div class="note">%d employees in; red: in after %s. A night '
        'shift crosses midnight: its hours are split between two days.'
        '</div></div>' % (len(got), _hhmm(late_line))])
