"""The Progress page: the project's stages, and each watched desk's days.

Shamroze, 23 Nov: a "Progress" section, password-protected, for him and
his boss -- the employee-productivity project, run like a project: where
it stands, stage by stage, and what the cameras have found so far.

What the page claims is only what progress_data measures: a desk with
somebody at it, pass by pass. It says "at the desk", never "productive",
and every card carries how its readings did when checked by eye.

No Streamlit and no database: figures in, HTML out.
"""
from overview import TOKENS, css, esc

STATUS = {"done": "Done", "doing": "In progress", "next": "Next",
          "later": "Later"}


def colours(mode):
    t = dict(TOKENS["dark" if mode == "dark" else "light"])
    t.update({"desk": "#2a9d63", "away": "#e8a21a",
              "out": t["s2"], "unwatched": "transparent",
              "doing": t["accent"], "done": "#2a9d63", "next": "#e8a21a",
              "later": t["t3"]})
    return t


def hhmm(hour):
    """10.5 -> "10:30"; None -> "--"."""
    if hour is None:
        return "--"
    m = int(round(hour * 60))
    return "%02d:%02d" % ((m // 60) % 24, m % 60)


def dur(minutes):
    """372 -> "6h 12m"."""
    if minutes is None:
        return "--"
    m = int(round(minutes))
    return "%dh %02dm" % (m // 60, m % 60) if m >= 60 else "%dm" % m


def strip_svg(slots, c, frm=8, to=24):
    """A day as a bar of slots, with the hours marked under it."""
    n = max(1, len(slots))
    w = 100.0 / n
    rects = []
    for i, s in enumerate(slots):
        if s == "unwatched":
            continue
        rects.append('<rect x="%.3f" y="0" width="%.3f" height="10" '
                     'fill="%s"/>' % (i * w, w + 0.02, c[s]))
    return ('<svg viewBox="0 0 100 10" preserveAspectRatio="none" '
            'class="pg-bar">%s</svg>' % "".join(rects))


def axis(frm=8, to=24, marks=(10, 14, 18, 22)):
    span = float(to - frm)
    return '<div class="pg-axis">%s</div>' % "".join(
        '<span style="left:%.2f%%">%s</span>' % (100 * (h - frm) / span,
                                                 "%02d" % h) for h in marks)


def tracker(stages, c):
    """The project, stage by stage."""
    if not stages:
        return ""
    overall = sum(float(s.get("progress") or 0) for s in stages) / len(stages)
    rows = []
    for i, s in enumerate(stages, 1):
        status = s.get("status", "later")
        p = float(s.get("progress") or 0)
        when = s.get("done") or s.get("due") or ""
        rows.append(
            '<div class="pg-stage %s"><div class="pg-num">%d</div>'
            '<div class="pg-sbody"><div class="pg-shead"><b>%s</b>'
            '<span class="pg-pill" style="background:%s">%s</span>'
            '<span class="pg-when">%s%s</span></div>'
            '<div class="pg-what">%s</div>%s'
            '<div class="ec-meter"><i style="width:%.0f%%;background:%s">'
            '</i></div></div></div>'
            % (esc(status), i, esc(s.get("name", "")), c.get(status, c["t3"]),
               STATUS.get(status, status),
               "done " if s.get("done") else ("due " if when else ""),
               esc(str(when)), esc(s.get("what", "")),
               ('<div class="pg-next">Next: %s</div>' % esc(s["next"])
                if s.get("next") else ""),
               p, c.get(status, c["accent"])))
    return ('<div class="ec-h"><span class="t">The project</span>'
            '<span class="c">%d stages &middot; %.0f%% done overall</span>'
            '</div><div class="ec-card pg-track"><div class="pg-overall">'
            '<div class="ec-meter"><i style="width:%.0f%%"></i></div></div>'
            '%s</div>' % (len(stages), overall, overall, "".join(rows)))


def tiles(people, c):
    """Across the desks: a usual day, the latest out, the check by eye."""
    used = [p["usual"] for p in people
            if p.get("usual") and p["usual"].get("desk_h") is not None]
    if not used:
        return ""
    desk_h = sum(u["desk_h"] for u in used) / len(used)
    share = [u["share"] for u in used if u.get("share") is not None]
    late = max((p for p in people if p.get("usual")
                and p["usual"].get("last_h") is not None),
               key=lambda p: p["usual"]["last_h"], default=None)
    frames = sum(int((p.get("check") or {}).get("frames") or 0)
                 for p in people)
    agree = sum(int((p.get("check") or {}).get("agree") or 0)
                for p in people)
    cells = [
        ("Employees watched", "%d" % len(people),
         "in %d departments" % len({p["department"] for p in people})),
        ("At the desk, a usual day", "%.1f h" % desk_h,
         "%.0f%% of office hours, on average" % (100 * sum(share) / len(share))
         if share else ""),
        ("Stays latest", hhmm(late["usual"]["last_h"]) if late else "--",
         "%s, usually" % who(late) if late else ""),
        ("Checked by eye", "%d of %d" % (agree, frames) if frames else "--",
         "readings agree with the picture" if frames else "not yet"),
    ]
    return '<div class="ec-kpis pg-tiles">%s</div>' % "".join(
        '<div class="ec-card ec-kpi"><div class="k">%s</div>'
        '<div class="v">%s</div><div class="s">%s</div></div>'
        % (esc(k), esc(v), esc(s)) for k, v, s in cells)


def who(p):
    """The employee as the page names them: the name kept in progress.yaml
    on the office laptop where there is one, else "Employee P1"."""
    return p.get("name") or "Employee %s" % p.get("code", "?")


def day_label(day):
    import datetime as _dt
    d = _dt.date.fromisoformat(day)
    return d.strftime("%a ") + str(d.day)


def card(p, c, frm=8, to=24, whole=480):
    """One desk: its usual day, its days, and how it did by eye. `whole`:
    the office-hour minutes a day must be watched to count as whole."""
    u = p.get("usual")
    check = p.get("check") or {}
    rows = []
    for s, slots in zip(p["days"], p["slots"]):
        if s.get("before"):
            right = '<span class="t3">cam moved</span>'
        elif s["watched_min"] <= 0:
            right = '<span class="t3">unwatched</span>'
        elif s["first"] is None:
            right = '<span class="t3">not in</span>'
        elif s["watched_min"] < whole:
            # A day the loop watched only part of (23 Nov: the laptop slept
            # 12:05-19:01) -- its hours are what was seen, not the day's.
            right = '<span class="t3" title="part of the day watched">%s*' \
                    '</span>' % dur(s.get("total_min", s["desk_min"]))
        else:
            right = "<b>%s</b>" % dur(s.get("total_min", s["desk_min"]))
        rows.append('<div class="pg-day"><span class="d">%s</span>%s'
                    '<span class="r">%s</span></div>'
                    % (day_label(s["day"]), strip_svg(slots, c, frm, to),
                       right))
    if u and u.get("desk_h") is not None:
        big = '%.1f<small>h at the desk</small>' % u["desk_h"]
        facts = [
            "%.0f%% of office hours" % (100 * u["share"])
            if u.get("share") is not None else None,
            "in %s" % hhmm(u.get("first_h")),
            "out %s" % hhmm(u.get("last_h")),
            "longest break %s" % dur(u["longest_break"])
            if u.get("longest_break") else None,
            "%.1f h after hours" % u["late_h"]
            if (u.get("late_h") or 0) >= 0.1 else None,
        ]
        basis = "a usual day: in %d of %d whole day%s watched" % (
            u["days_in"], u["days"], "" if u["days"] == 1 else "s")
    else:
        big, facts, basis = "--", [], "no whole day watched yet"
    agree = ""
    if check.get("frames"):
        ok = int(check["agree"]) == int(check["frames"])
        agree = ('<div class="pg-check %s">Checked by eye, %s: %d of %d '
                 'frames agree%s</div>'
                 % ("ok" if ok else "warn", esc(str(check.get("date", ""))),
                    int(check["agree"]), int(check["frames"]),
                    (" &middot; missed: %s" % esc(check["missed"]))
                    if check.get("missed") else ""))
    return ('<div class="ec-card pg-card"><div class="pg-hd">'
            '<span class="pg-code">%s</span><div class="pg-dept"><b>%s</b>'
            '<span>%s</span></div><div class="pg-big">%s</div></div>'
            '<div class="pg-facts">%s</div>%s<div class="pg-days">%s%s</div>'
            '<div class="pg-why">%s</div></div>'
            % (esc(p["code"]), esc(who(p)),
               esc("desk in %s · %s" % (p["department"], basis)), big,
               "".join('<span class="ec-pill">%s</span>' % esc(f)
                       for f in facts if f),
               agree, "".join(rows), axis(frm, to),
               esc(p.get("why", ""))))


def legend(c):
    items = [("desk", "at the desk"), ("away", "away from the desk"),
             ("out", "not in yet / gone")]
    return ('<div class="ec-legend">%s<span><i class="box pg-hatch"></i>'
            'not watched</span></div>'
            % "".join('<span><i class="box" style="background:%s"></i>%s'
                      '</span>' % (c[k], esc(t)) for k, t in items))


def page(mode, cfg, people, as_of, hours=(10, 20), frm=8, to=24):
    """The whole page. people: [{code, department, why, check, days,
    slots, usual}], one per desk, days and slots oldest first."""
    c = colours(mode)
    head = ('<div class="ec-h" style="margin-top:6px"><span class="t">'
            'Progress</span><span class="c">employees&rsquo; time at their '
            'desks &middot; %s &middot; %d employees &middot; private '
            '&middot; worked out %s</span></div>'
            % (esc(cfg.get("campus", "")), len(people), esc(as_of)))
    whole = 0.8 * 60 * (hours[1] - hours[0])
    cards = "".join(card(p, c, frm, to, whole) for p in people)
    body = ('<div class="ec-h"><span class="t">The employees</span>'
            '<span class="c">office hours %s-%s; the bars run %02d:00-'
            '%02d:00; * part of the day watched</span>%s</div>'
            '<div class="pg-cards">%s</div>'
            % (hhmm(hours[0]), hhmm(hours[1]), frm, to, legend(c), cards))
    note = (
        '<div class="ec-note pg-note"><b>How this is measured.</b> Each '
        'employee is followed at their own desk. Every pass of the loop '
        '(about every 4-5 minutes) notes where each person the cameras count '
        'is in the picture; a note on the employee&rsquo;s desk is "at the '
        'desk", none is "away". One missed pass between two at the desk is '
        'the detector blinking and counts as at the desk; one lone pass is '
        'somebody passing and does not. A pass the loop never made (the '
        'laptop asleep) is "not watched", never "away". The camera sees the '
        'desk, not a face: the pictures checked by eye show the same person '
        'at each desk, but a colleague sitting there would be counted too. '
        'Where an employee goes when away, and what they do at the desk, are '
        'the next stages -- until then the page does not guess. Which '
        'employee is which code is kept on the office laptop only.</div>')
    # Each <style> on lines of its own: Streamlit's markdown ends an HTML
    # block at the end of the line holding </style>, so "</style><style>"
    # on one line left the second block unclosed and the whole page inside
    # it, invisible (23 Nov, the first look in the dashboard).
    return (css(mode) + "\n" + _CSS % c + "\n" + '<div class="ec pg">' + head
            + tiles(people, c) + tracker(cfg.get("stages") or [], c) + body
            + note + "</div>")


def locked(mode, why):
    """The page before the password, or when it cannot be shown at all."""
    text = {
        "unset": ("Progress is locked.", "Its password is not set. Put a "
                  "line PROGRESS_PASSWORD=... in .env on the office laptop "
                  "(and in the app's secrets where it is hosted)."),
        "ask": ("Progress", "Private: the employees' time at their desks, "
                "for the productivity project. Enter its own password."),
        "none": ("Progress runs on the office laptop.", "Its desk list and "
                 "the seat notes it reads never leave that machine."),
    }[why]
    return (css(mode) + '<div class="ec"><div class="ec-h" style="margin-top:'
            '6px"><span class="t">%s</span></div><div class="ec-note" '
            'style="margin-top:0">%s</div></div>' % (esc(text[0]),
                                                     esc(text[1])))


_CSS = """<style>
.pg .pg-tiles{grid-template-columns:repeat(auto-fit,minmax(140px,1fr));margin-top:8px}
.pg .pg-tiles .ec-kpi{padding:14px 16px}
.pg .pg-track{padding:16px 18px}
.pg .pg-overall{margin-bottom:6px}
.pg .pg-stage{display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line)}
.pg .pg-stage:first-of-type{border-top:0}
.pg .pg-num{flex:none;width:26px;height:26px;border-radius:50%%;display:flex;
align-items:center;justify-content:center;font-size:12.5px;font-weight:700;
background:var(--s2);color:var(--t2)}
.pg .pg-stage.done .pg-num{background:%(done)s;color:#fff}
.pg .pg-stage.doing .pg-num{background:%(doing)s;color:#fff}
.pg .pg-sbody{flex:1;min-width:0}
.pg .pg-shead{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.pg .pg-shead b{font-size:14.5px}
.pg .pg-pill{font-size:11px;font-weight:650;color:#fff;padding:2px 8px;
border-radius:99px}
.pg .pg-when{margin-left:auto;font-size:12px;color:var(--t3);white-space:nowrap}
.pg .pg-what{font-size:13px;color:var(--t2);margin-top:3px}
.pg .pg-next{font-size:12.5px;color:var(--t3);margin-top:2px}
.pg .pg-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
gap:14px}
.pg .pg-card{padding:16px 18px;min-width:0}
.pg .pg-hd{display:flex;align-items:center;gap:10px}
.pg .pg-code{flex:none;font-weight:750;font-size:13px;color:#fff;
background:linear-gradient(135deg,#3987e5,#2a9d63);border-radius:10px;
padding:6px 9px;letter-spacing:.02em}
.pg .pg-dept{min-width:0;display:flex;flex-direction:column}
.pg .pg-dept b{font-size:15.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pg .pg-dept span{font-size:11.5px;color:var(--t3)}
.pg .pg-big{margin-left:auto;font-size:28px;font-weight:720;line-height:1;
white-space:nowrap}
.pg .pg-big small{font-size:11.5px;font-weight:500;color:var(--t3);margin-left:4px}
.pg .pg-facts{display:flex;flex-wrap:wrap;gap:6px;margin:11px 0 8px}
.pg .pg-check{font-size:12px;border-radius:9px;padding:6px 9px;margin-bottom:8px}
.pg .pg-check.ok{background:rgba(42,157,99,.12);color:var(--t1)}
.pg .pg-check.warn{background:rgba(232,162,26,.13);color:var(--t1)}
.pg .pg-days{position:relative;padding-bottom:16px}
.pg .pg-day{display:grid;grid-template-columns:48px 1fr 74px;gap:8px;
align-items:center;margin-top:5px;font-size:12px}
.pg .pg-day .d{color:var(--t3);white-space:nowrap}
.pg .pg-day .r{text-align:right;white-space:nowrap}
.pg .pg-bar{display:block;width:100%%;height:12px;border-radius:3px;
background:repeating-linear-gradient(45deg,transparent 0 3px,var(--line) 3px 5px)}
.pg .pg-axis{position:absolute;left:56px;right:82px;bottom:0;height:14px}
.pg .pg-axis span{position:absolute;transform:translateX(-50%%);font-size:10px;
color:var(--t3)}
.pg .pg-why{font-size:11.5px;color:var(--t3);margin-top:8px}
.pg .pg-hatch{background:repeating-linear-gradient(45deg,transparent 0 2px,
var(--line2) 2px 4px)}
.pg .pg-note{line-height:1.5}
@media (max-width:420px){
.pg .pg-day{grid-template-columns:40px 1fr 62px;gap:6px}
.pg .pg-axis{left:46px;right:68px}
.pg .pg-big{font-size:24px}
}
</style>"""
