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
          "later": "Later", "blocked": "Waiting"}


def colours(mode):
    t = dict(TOKENS["dark" if mode == "dark" else "light"])
    t.update({"desk": "#2a9d63", "away": "#e8a21a",
              "out": t["s2"], "unwatched": "transparent",
              "doing": t["accent"], "done": "#2a9d63", "next": "#e8a21a",
              "later": t["t3"], "blocked": "#d03b3b",
              # what the employee was doing (progress_track kinds)
              "computer": "#2a9d63", "phone": "#e5383b",
              "talking": "#8b5cf6", "unseen": "#e8a21a",
              "deskread": "#6fbf8f"})
    for k in ("meeting", "own room", "office", "cafe", "smoking", "prayer",
              "corridor", "outside"):
        t[k] = "#3987e5"
    return t


# The day's kinds, as the page names them, in the order the bar shows them.
DAY_PARTS = [("computer", "At the computer"), ("phone", "On the phone"),
             ("talking", "Talking at the desk"),
             ("unseen", "Away from the desk")]


def day_block(focus, c, frm=8, to=24):
    """The day in focus: first in, last out, last seen; hours by activity
    as one bar; and the day as coloured slots."""
    if not focus:
        return ""

    def t(x):
        return x.strftime("%H:%M") if x is not None else "--"
    m, est = focus["minutes"], focus["estimate"]
    at_desk = sum(m.get(k, 0.0) for k in ("computer", "phone", "talking",
                                           "desk"))
    away = sum(v for k, v in m.items()
               if k not in ("computer", "phone", "talking", "desk"))
    parts = {"computer": est["computer"] if sum(est.values()) else
             m.get("desk", 0.0), "phone": est["phone"],
             "talking": est["talking"], "unseen": away}
    total = sum(parts.values()) or 1.0
    bar = "".join('<i style="width:%.2f%%;background:%s" title="%s %s"></i>'
                  % (100 * parts[k] / total, c[k], esc(label), dur(parts[k]))
                  for k, label in DAY_PARTS if parts[k] > 0)
    legend = "".join('<span><b style="background:%s"></b>%s <em>%s</em>'
                     '</span>' % (c[k], esc(label), dur(parts[k]))
                     for k, label in DAY_PARTS)
    slots = focus.get("slots") or []
    cols = []
    for s in slots:
        key = "deskread" if s == "desk" else s
        cols.append(c.get(key, "transparent"))
    n = max(1, len(cols))
    rects = "".join('<rect x="%.3f" y="0" width="%.3f" height="10" fill="%s"/>'
                    % (i * 100.0 / n, 100.0 / n + 0.02, col)
                    for i, col in enumerate(cols) if col != "transparent")
    import datetime as _dt
    label = _dt.date.fromisoformat(focus["day"]).strftime("%a %d %b")
    facts = [("First in", t(focus.get("first_in"))),
             ("Last out", t(focus.get("last_out"))),
             ("Last seen", t(focus.get("last_seen"))),
             ("At the desk", dur(at_desk))]
    # Where they went: confirmed places only; possible ones wait below.
    places = focus.get("places") or {}
    names = {"meeting": "meetings", "own room": "own room, not at desk",
             "office": "other offices", "cafe": "cafe / pantry",
             "smoking": "smoking area", "prayer": "prayer",
             "corridor": "corridors / reception", "outside": "outside"}
    went = " · ".join("%s %s" % (esc(names.get(k, k)), dur(v))
                      for k, v in sorted(places.items(), key=lambda x: -x[1]))
    n_possible = len(focus.get("possible") or [])
    where = ('<div class="pg-where"><b>Away, seen in:</b> %s%s</div>'
             % (went or "no confirmed place yet",
                (' <span>· %d possible sighting%s to check below</span>'
                 % (n_possible, "" if n_possible == 1 else "s"))
                if n_possible else ""))
    return (
        '<div class="pg-today"><div class="pg-th">%s<span>%s activity '
        'reading%s</span></div><div class="pg-facts4">%s</div>'
        '<div class="pg-split">%s</div><div class="pg-leg">%s</div>%s'
        '<div class="pg-days" style="padding-bottom:16px"><div class="pg-day">'
        '<span class="d">%s</span><svg viewBox="0 0 100 10" '
        'preserveAspectRatio="none" class="pg-bar">%s</svg><span class="r">'
        '</span></div>%s</div></div>'
        % (esc(label), focus.get("read", 0),
           "" if focus.get("read", 0) == 1 else "s",
           "".join('<div><span>%s</span><b>%s</b></div>' % (esc(k), esc(v))
                   for k, v in facts),
           bar, legend, where, esc(label[:6]), rects, axis(frm, to)))


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


def gantt(stages, c, today=None):
    """The stages on a calendar: a bar from start to end each, filled to
    its progress, and a line at today. Stages without dates are left off."""
    import datetime as _dt

    def d(x):
        try:
            return _dt.date.fromisoformat(str(x))
        except (TypeError, ValueError):
            return None
    dated = [(s, d(s.get("start")), d(s.get("end"))) for s in stages]
    dated = [x for x in dated if x[1] and x[2]]
    if not dated:
        return ""
    lo = min(x[1] for x in dated)
    hi = max(x[2] for x in dated)
    span = float((hi - lo).days + 1)
    today = today or _dt.date.today()

    def pct(day):
        return 100.0 * (day - lo).days / span
    ticks = []
    day = lo
    while day <= hi:
        if day.weekday() == 0 or day == lo:
            ticks.append('<span style="left:%.2f%%">%s</span>'
                         % (pct(day), day.strftime("%d %b")))
        day += _dt.timedelta(days=1)
    rows = []
    for s, a, b in dated:
        status = s.get("status", "later")
        p = float(s.get("progress") or 0)
        left, width = pct(a), 100.0 * ((b - a).days + 1) / span
        rows.append(
            '<div class="pg-grow"><div class="pg-gname"><b>%s</b>'
            '<span class="pg-pill" style="background:%s">%s</span></div>'
            '<div class="pg-gtrack"><div class="pg-gbar" style="left:%.2f%%;'
            'width:%.2f%%;border-color:%s"><i style="width:%.0f%%;'
            'background:%s"></i></div></div></div>'
            % (esc(s.get("name", "")), c.get(status, c["t3"]),
               STATUS.get(status, status), left, width,
               c.get(status, c["t3"]), p, c.get(status, c["t3"])))
    line = ""
    if lo <= today <= hi:
        line = ('<div class="pg-gtoday" style="left:calc(var(--gl) + '
                '(100%% - var(--gl)) * %.4f)"><span>today</span></div>'
                % ((today - lo).days / span + 0.5 / span))
    return ('<div class="pg-gantt">%s<div class="pg-gaxis">%s</div>%s</div>'
            % ("".join(rows), "".join(ticks), line))


def tracker(stages, c, needs=None, today=None):
    """The project, stage by stage: on a calendar, then in words."""
    if not stages:
        return ""
    overall = sum(float(s.get("progress") or 0) for s in stages) / len(stages)
    chart = gantt(stages, c, today)
    asks = ""
    if needs:
        asks = ('<div class="pg-needs"><b>What it needs next</b><ul>%s</ul>'
                '</div>' % "".join("<li>%s</li>" % esc(n) for n in needs))
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
            '%s%s%s</div>' % (len(stages), overall, overall, chart,
                              "".join(rows), asks))


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
    recent = [r["desk_pct"] for p in people
              for r in (p.get("history") or [])[-5:]
              if r.get("desk_pct") is not None]
    cells = [
        ("Desk %, last 5 days", pct(sum(recent) / len(recent))
         if recent else "--", "of the time in the office, all five"),
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
            '%s<div class="pg-sub">The last working days at the desk</div>'
            '<div class="pg-facts">%s</div>%s<div class="pg-days">%s%s</div>'
            '<div class="pg-why">%s</div></div>'
            % (esc(p["code"]), esc(who(p)),
               esc("desk in %s · %s" % (p["department"], basis)), big,
               day_block(p.get("focus"), c, frm, to),
               "".join('<span class="ec-pill">%s</span>' % esc(f)
                       for f in facts if f),
               agree, "".join(rows), axis(frm, to),
               esc(p.get("why", ""))))


LIVE_COLOURS = {"desk": "#2a9d63", "away": "#e8a21a", "out": "#898781",
                "gone": "#898781", "unwatched": "#d03b3b"}


def live_strip(people, c, as_of=""):
    """Right now, every employee in one row -- the way the campus page says
    which ACs are on."""
    if not any(p.get("live") for p in people):
        return ""
    chips = []
    for p in people:
        lv = p.get("live") or {}
        state = lv.get("state", "out")
        since = lv.get("since")
        if hasattr(since, "strftime"):
            mins = lv.get("minutes")
            when = ("since %s" % since.strftime("%H:%M")) + (
                " · %s" % dur(mins) if mins and state in ("desk", "away")
                else "")
        else:
            when = ""
        if state == "gone" and hasattr(since, "strftime"):
            when = "left at %s" % since.strftime("%H:%M")
        chips.append(
            '<div class="pg-live" style="border-left-color:%s">'
            '<span class="pg-code sm">%s</span><div><b>%s</b><span>%s%s'
            '</span></div></div>'
            % (LIVE_COLOURS.get(state, "#898781"), esc(p.get("code", "?")),
               esc(lv.get("label", "")), esc(when),
               (" · %s" % esc(lv["place"])) if lv.get("place") else ""))
    return ('<div class="ec-h"><span class="t">Right now</span><span class="c">'
            '%s</span></div><div class="pg-lives">%s</div>'
            % (("as of %s" % esc(as_of)) if as_of else "", "".join(chips)))


def pct(x):
    return "%.0f%%" % (100 * x) if x is not None else "--"


def team_table(people, c, days_shown=10):
    """Every employee against every day kept: desk % (and computer % where
    the activity was read), first in and last out."""
    days = sorted({r["day"] for p in people for r in p.get("history") or []})
    days = days[-days_shown:]
    if not days:
        return ""
    import datetime as _dt
    head = "".join('<th>%s</th>' % esc(
        _dt.date.fromisoformat(d).strftime("%a %d")) for d in days)
    rows = []
    for p in people:
        by_day = {r["day"]: r for r in p.get("history") or []}
        cells = []
        shares = []
        for d in days:
            r = by_day.get(d)
            if not r or r.get("first") is None:
                cells.append('<td class="none">%s</td>'
                             % ("not in" if r else "--"))
                continue
            share = r.get("desk_pct")
            if share is not None:
                shares.append(share)
            alpha = 0.12 + 0.55 * min(1.0, max(0.0, share or 0.0))
            comp = r.get("computer_pct")
            cells.append(
                '<td style="background:rgba(42,157,99,%.2f)" title="in %s, out '
                '%s; %s at the desk of %s watched%s"><b>%s</b>%s<small>%s-%s'
                '</small></td>'
                % (alpha, r["first"].strftime("%H:%M"),
                   r["last"].strftime("%H:%M"), dur(r.get("desk_min")),
                   dur(r.get("in_min")),
                   " (part of the day)" if r.get("part") else "",
                   pct(share) + ("*" if r.get("part") else ""),
                   ('<i>computer %s</i>' % pct(comp)) if comp is not None
                   else "", r["first"].strftime("%H:%M"),
                   r["last"].strftime("%H:%M")))
        avg = sum(shares) / len(shares) if shares else None
        rows.append('<tr><th class="who">%s<span>%s</span></th>%s'
                    '<td class="avg"><b>%s</b></td></tr>'
                    % (esc(p.get("code", "?")), esc(p.get("department", "")),
                       "".join(cells), pct(avg)))
    return ('<div class="ec-h"><span class="t">Every day</span><span class="c">'
            'desk %% = time at the desk of the time in the office (first in to '
            'last out, as watched); computer %% where the activity was read; '
            '* part of the day watched</span></div>'
            '<div class="ec-card pg-tablewrap"><table class="pg-team"><thead>'
            '<tr><th></th>%s<th>usual</th></tr></thead><tbody>%s</tbody>'
            '</table></div>' % (head, "".join(rows)))


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
            + live_strip(people, c, as_of) + tiles(people, c)
            + team_table(people, c)
            + tracker(cfg.get("stages") or [], c, cfg.get("needs"))
            + body + note + "</div>")


def locked(mode, why):
    """The page before the password, or when it cannot be shown at all."""
    text = {
        "unset": ("Progress is locked.", "Its password is not set. Put a "
                  "line PROGRESS_PASSWORD=... in .env on the office laptop "
                  "(and in the app's secrets where it is hosted)."),
        "ask": ("Progress", "Private: the employees' time at their desks, "
                "for the productivity project. Enter its own password."),
        "none": ("Progress has not reached this page yet.", "The office "
                 "laptop sends its numbers (never a name or a picture) every "
                 "five minutes, once an administrator has run "
                 "sql/11_progress.sql in Supabase."),
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
.pg .pg-today{margin:12px 0 6px;padding:12px 12px 4px;border-radius:12px;
background:var(--s2)}
.pg .pg-th{display:flex;align-items:baseline;gap:8px;font-weight:700;font-size:13.5px}
.pg .pg-th span{font-weight:500;font-size:11.5px;color:var(--t3)}
.pg .pg-facts4{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:8px 0 10px}
.pg .pg-facts4 div{display:flex;flex-direction:column}
.pg .pg-facts4 span{font-size:11px;color:var(--t3)}
.pg .pg-facts4 b{font-size:16px;font-weight:700;white-space:nowrap}
.pg .pg-split{display:flex;height:14px;border-radius:7px;overflow:hidden;
background:var(--line)}
.pg .pg-split i{display:block;height:100%%}
.pg .pg-leg{display:flex;flex-wrap:wrap;gap:4px 12px;margin:7px 0 2px;font-size:11.5px;
color:var(--t2)}
.pg .pg-leg b{display:inline-block;width:9px;height:9px;border-radius:2px;
margin-right:5px;vertical-align:-1px}
.pg .pg-leg em{font-style:normal;font-weight:650;color:var(--t1)}
.pg .pg-sub{font-size:11.5px;color:var(--t3);margin-top:8px}
.pg .pg-where{font-size:12px;color:var(--t2);margin:6px 0 2px}
.pg .pg-where b{color:var(--t1);font-weight:650}
.pg .pg-where span{color:#3987e5;font-weight:600}
.pg .pg-gantt{position:relative;--gl:170px;margin:22px 0 14px;padding-bottom:20px}
.pg .pg-grow{display:grid;grid-template-columns:var(--gl) 1fr;align-items:center;
min-height:30px}
.pg .pg-gname{display:flex;align-items:center;gap:6px;min-width:0;padding-right:8px}
.pg .pg-gname b{font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pg .pg-gname .pg-pill{font-size:9.5px;padding:1px 6px}
.pg .pg-gtrack{position:relative;height:18px;border-radius:4px;
background:repeating-linear-gradient(90deg,var(--line) 0 1px,transparent 1px 7.14%%)}
.pg .pg-gbar{position:absolute;top:2px;height:14px;border-radius:7px;border:1.5px solid;
overflow:hidden;background:var(--s1)}
.pg .pg-gbar i{display:block;height:100%%;opacity:.85}
.pg .pg-gaxis{position:absolute;left:var(--gl);right:0;bottom:0;height:16px}
.pg .pg-gaxis span{position:absolute;font-size:10px;color:var(--t3);white-space:nowrap}
.pg .pg-gtoday{position:absolute;top:-4px;bottom:16px;width:0;
border-left:2px dashed %(crit)s}
.pg .pg-gtoday span{position:absolute;top:-14px;left:-14px;font-size:9.5px;
color:%(crit)s;font-weight:700}
.pg .pg-lives{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));
gap:10px}
.pg .pg-live{display:flex;gap:9px;align-items:center;background:var(--s1);
border:1px solid var(--line);border-left:5px solid;border-radius:12px;padding:9px 11px;
min-width:0}
.pg .pg-live div{display:flex;flex-direction:column;min-width:0}
.pg .pg-live b{font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pg .pg-live span:not(.pg-code){font-size:11.5px;color:var(--t3)}
.pg .pg-code.sm{font-size:11.5px;padding:4px 7px;border-radius:8px}
.pg .pg-tablewrap{padding:6px;overflow-x:auto}
.pg .pg-team{border-collapse:separate;border-spacing:3px;font-size:12px;min-width:100%%}
.pg .pg-team th{font-weight:600;color:var(--t3);font-size:11px;white-space:nowrap;
padding:2px 4px}
.pg .pg-team th.who{text-align:left;color:var(--t1);font-size:13px}
.pg .pg-team th.who span{display:block;font-size:10.5px;color:var(--t3);font-weight:500}
.pg .pg-team td{border-radius:7px;padding:5px 6px;text-align:center;
white-space:nowrap;min-width:64px}
.pg .pg-team td b{display:block;font-size:14px}
.pg .pg-team td i{display:block;font-style:normal;font-size:10.5px;color:var(--t2)}
.pg .pg-team td small{display:block;font-size:10px;color:var(--t3)}
.pg .pg-team td.none{color:var(--t3);background:var(--s2)}
.pg .pg-team td.avg{background:var(--s2)}
.pg .pg-needs{margin-top:10px;padding-top:10px;border-top:1px solid var(--line);font-size:13px}
.pg .pg-needs ul{margin:6px 0 0 18px;padding:0;color:var(--t2)}
.pg .pg-needs li{margin:3px 0}
@media (max-width:420px){
.pg .pg-gantt{--gl:118px}
.pg .pg-gname .pg-pill{display:none}
.pg .pg-facts4 b{font-size:14px}
.pg .pg-day{grid-template-columns:40px 1fr 62px;gap:6px}
.pg .pg-axis{left:46px;right:68px}
.pg .pg-big{font-size:24px}
}
</style>"""
