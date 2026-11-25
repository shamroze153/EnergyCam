"""The Progress page: the project's stages, and each watched desk's days.

Shamroze, 23 Nov: a "Progress" section, password-protected, for him and
his boss -- the employee-productivity project, run like a project: where
it stands, stage by stage, and what the cameras have found so far.

What the page claims is only what progress_data measures: a desk with
somebody at it, pass by pass. It says "at the desk", never "productive",
and every card carries how its readings did when checked by eye.

No Streamlit and no database: figures in, HTML out.
"""
import math

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
              "talking": "#a23cb8", "unseen": "#e8a21a",
              "deskread": "#6fbf8f",
              # out through the gate: a neutral, they are not here
              "left": "#6b7280"})
    # Seen somewhere off the desk: one colour on the bar, the place in words
    # under it (24 Nov: a colour a place was ten colours no eye could tell
    # apart; the validator put talking's old violet too near this blue).
    for k in ("meeting", "own room", "office", "cafe", "smoking", "prayer",
              "corridor", "outside"):
        t[k] = "#2f6fd6"
    return t


# Away from the desk, as the board says it (progress_data KINDS).
AWAY_WORDS = [("own room", "own room"), ("meeting", "meetings"),
              ("cafe", "cafe"), ("smoking", "smoking area"),
              ("prayer", "prayer"), ("outside", "outside on campus"),
              ("office", "other rooms"), ("corridor", "corridors"),
              ("left", "out of the building"), ("unseen", "not seen")]
SLOT_WORDS = dict([("computer", "at the computer"), ("phone", "on the phone"),
                   ("talking", "talking at the desk"),
                   ("desk", "at the desk")] + AWAY_WORDS)


def away_word(kind, p=None):
    """A place away from the desk in words; their own room by its name
    (25 Nov: "in the Basement", where the Basement's people are measured
    by where they are)."""
    room = (p or {}).get("department") or ""
    if kind == "own room" and room:
        return "in the %s, off the desk" % room
    return dict(AWAY_WORDS).get(kind, kind)


def presence(p):
    """Only where this employee is is measured -- not what they do at the
    desk (progress_data.presence_only; the Basement since 25 Nov)."""
    return bool((p or {}).get("presence_only"))


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
    if sum(est.values()):
        parts = {"computer": est["computer"], "phone": est["phone"],
                 "talking": est["talking"], "unseen": away}
        shown = DAY_PARTS
    else:
        # nothing read (or presence only, the Basement): the desk is the
        # desk -- never "at the computer" for minutes nobody looked at
        parts = {"desk": at_desk, "unseen": away}
        shown = [("desk", "At the desk"), ("unseen", "Away from the desk")]
    total = sum(parts.values()) or 1.0
    bar = "".join('<i style="width:%.2f%%;background:%s" title="%s %s"></i>'
                  % (100 * parts[k] / total, c[k], esc(label), dur(parts[k]))
                  for k, label in shown if parts[k] > 0)
    legend = "".join('<span><b style="background:%s"></b>%s <em>%s</em>'
                     '</span>' % (c[k], esc(label), dur(parts[k]))
                     for k, label in shown)
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
             "corridor": "corridors / reception", "outside": "outside",
             "left": "out of the building"}
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
        '</span></div>%s</div>%s</div>'
        % (esc(label), focus.get("read", 0),
           "" if focus.get("read", 0) == 1 else "s",
           "".join('<div><span>%s</span><b>%s</b></div>' % (esc(k), esc(v))
                   for k, v in facts),
           bar, legend, where, esc(label[:6]), rects, axis(frm, to),
           stretch_list(focus, c)))


KIND_WORDS = {"computer": "computer", "phone": "phone", "talking": "talking",
              "desk": "not read"}
HOW_WORDS = {"face": "seen by face", "seen": "seen", "possible": "possibly"}


def stretch_list(focus, c):
    """The day stretch by stretch, latest first -- the way a room's page
    lists its AC (Shamroze, 23 Nov: "P1 ke aage poori line ... is se le ke
    yahan tha"). progress_data.stretches() made the list."""
    items = (focus or {}).get("stretches") or []
    if not items:
        return ""
    rows = []
    for st in reversed(items):
        what = st["what"]
        if what == "desk":
            colour, title = c["computer"], "At the desk"
            kinds = sorted(((k, v) for k, v in st["kinds"].items() if v >= 1),
                           key=lambda kv: -kv[1])
            detail = " &middot; ".join("%s %s" % (esc(KIND_WORDS.get(k, k)),
                                                  dur(v)) for k, v in kinds)
        elif what == "unwatched":
            colour, title = c["t3"], "Not watched"
            detail = "the loop or the laptop was off"
        else:
            colour, title = c["unseen"], "Away from the desk"
            bits = [("%s" if r == "out of the building" else "in %s")
                    % esc(r) for r in st.get("where") or []]
            bits += ["%s %s" % (HOW_WORDS.get(h, h), esc(r))
                     for r, h in st.get("seen") or []
                     if r not in (st.get("where") or [])]
            detail = " &middot; ".join(bits) or "on no camera"
        rows.append(
            '<div class="pg-st"><i style="background:%s"></i><span class="w">'
            '%s&ndash;%s</span><span class="m">%s</span><span class="x"><b>%s'
            '</b> %s</span></div>'
            % (colour, st["from"].strftime("%H:%M"), st["to"].strftime("%H:%M"),
               dur(st["minutes"]), title, detail))
    return ('<details class="pg-stretch" open><summary>Stretch by stretch '
            '<span>%d &middot; latest first</span></summary>%s</details>'
            % (len(items), "".join(rows)))


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
    step = (to - frm) * 60.0 / n
    rects = []
    for i, s in enumerate(slots):
        if s == "unwatched":
            continue
        m = int(round(frm * 60 + i * step))
        rects.append('<rect x="%.3f" y="0" width="%.3f" height="10" '
                     'fill="%s"><title>%02d:%02d %s</title></rect>'
                     % (i * w, w + 0.02, c.get(s, c["unseen"]),
                        m // 60, m % 60, esc(SLOT_WORDS.get(s, s))))
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
    code = str(p.get("code", "?"))
    if not p.get("name") and "." in code:
        return "Desk %s" % code           # a desk of 140-H, sitter not named
    return p.get("name") or "Employee %s" % code


def tag(p):
    """Short label where a code stood (Shamroze, 24 Nov: "P3 ki jagah naam
    aur employee ID"): "<name> · <employee ID>" on the laptop, where
    progress.yaml has the name; the code wherever it has not (the hosted
    page gets no names)."""
    if not p.get("name"):
        return p.get("code", "?")
    eid = p.get("employee_id")
    return "%s · %s" % (p["name"], eid) if eid else p["name"]


_ICON_RE = None


def face(p, size=""):
    """The employee's directory-photo icon as an <img> (progress_data.
    photo_icon), or "" -- and "" for anything but a JPEG data icon, so a
    row from the database can never put a link or a script on the page.
    `size`: "" (a card), "sm" (right now) or "xs" (a table row)."""
    global _ICON_RE
    import re
    if _ICON_RE is None:
        _ICON_RE = re.compile(r"data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}")
    src = p.get("photo") or ""
    if not isinstance(src, str) or not _ICON_RE.fullmatch(src):
        return ""
    return '<img class="pg-face%s" src="%s" alt="">' % (
        (" " + size) if size else "", src)


def badge(p, size=""):
    """The photo icon where there is one, else the code's badge."""
    return face(p, size) or '<span class="pg-code%s">%s</span>' % (
        (" " + size) if size else "", esc(p.get("code", "?")))


def named(text, people):
    """A sentence with each employee's code put as their name, where known."""
    for p in people:
        if p.get("name") and p.get("code"):
            text = text.replace(p["code"], p["name"])
    return text


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
            '%s<div class="pg-dept"><b>%s</b>'
            '<span>%s</span></div><div class="pg-big">%s</div></div>'
            '%s<div class="pg-sub">The last working days at the desk</div>'
            '<div class="pg-facts">%s</div>%s<div class="pg-days">%s%s</div>'
            '<div class="pg-why">%s</div></div>'
            % (badge(p), esc(who(p)),
               esc("%sdesk in %s%s · %s" % (
                   # the code, where the photo took its badge's place
                   ("%s · " % p["code"]) if face(p) else "",
                   p["department"], (" · ID %s" % p["employee_id"])
                   if p.get("employee_id") else "", basis)), big,
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
        title = p.get("name") or lv.get("label", "")
        sub = (lv.get("label", "") + (" · " if when else "")) \
            if p.get("name") else ""
        if face(p):
            sub = "%s · %s" % (p.get("code", "?"), sub)
        chips.append(
            '<div class="pg-live" style="border-left-color:%s">'
            '%s<div><b>%s</b><span>%s%s%s'
            '</span></div></div>'
            % (LIVE_COLOURS.get(state, "#898781"), badge(p, "sm"),
               esc(title), esc(sub), esc(when),
               (" · %s" % esc(lv["place"])) if lv.get("place") else ""))
    return ('<div class="ec-h"><span class="t">Right now</span><span class="c">'
            '%s</span></div><div class="pg-lives">%s</div>'
            % (("as of %s" % esc(as_of)) if as_of else "", "".join(chips)))


def pct(x):
    return "%.0f%%" % (100 * x) if x is not None else "--"


AT_DESK_KINDS = ("computer", "phone", "talking", "desk")
STATE_WORDS = {"desk": "At the desk", "away": "Away", "out": "Not in",
               "gone": "Gone home", "unwatched": "Not watched"}


LATE_AFTER = 15          # minutes past the office's start that count as late
BREAK_MIN = 10           # minutes away that make a break


def board_row(p, c, frm=8, to=24, start=10.0):
    """One employee's line on the scoreboard: (html, sort key). `start`:
    the office's first hour (rooms.yaml), for "late"."""
    import progress_data as pdx
    f = p.get("focus") or {}
    m = f.get("minutes") or {}
    lv = p.get("live") or {}
    state = lv.get("state", "out")
    stretches_ = f.get("stretches") or []
    desk_runs = [s["minutes"] for s in stretches_ if s.get("what") == "desk"]
    longest = max(desk_runs) if desk_runs else None
    # A break is ten minutes or more away: shorter is the detector blinking
    # or a word at the next desk (24 Nov: "13 breaks" from flicker).
    breaks = sum(1 for s in stretches_
                 if s.get("what") not in ("desk", "unwatched")
                 and (s.get("minutes") or 0) >= BREAK_MIN)
    gate = [str(t) for t in p.get("gate") or []]
    came = f.get("first_in") is not None
    at = sum(m.get(k, 0.0) for k in AT_DESK_KINDS) if came else 0.0
    away = sum(v for k, v in m.items()
               if k not in AT_DESK_KINDS and k not in ("out", "unwatched")) \
        if came else 0.0
    share = at / (at + away) if (at + away) > 0 else None
    # A share over a few minutes says nothing (24 Nov: 4 minutes in, "100%
    # of time in", +81 on the usual): compared only after an hour in.
    early = (at + away) < 60
    past = [r for r in p.get("history") or [] if r.get("day") != f.get("day")]
    usual = (pdx.average(past, 7) or {}).get("desk_pct")
    since = lv.get("since")
    when = since.strftime("%H:%M") if hasattr(since, "strftime") else ""
    now = ("since %s" % when if state in ("desk", "away") and when else
           "at %s" % when if state == "gone" and when else "")
    first_t = f.get("first_in")
    first = first_t.strftime("%H:%M") if hasattr(first_t, "strftime") else "--"
    late = (hasattr(first_t, "hour") and first_t.hour + first_t.minute / 60.0
            > start + LATE_AFTER / 60.0)
    # Out through the gate since they left the desk (progress_data.live):
    # out of the building, not at the coffee machine.
    left = lv.get("label") == "Out of the building"
    # The day's activity where the loop read it -- shared out over the
    # unread desk minutes the way the read ones were (progress_data).
    est = f.get("estimate") or {}
    total = sum(est.get(k, 0.0) for k in ("computer", "phone", "talking"))
    split = ""
    if f.get("read") and total > 0:
        split = ('<div class="pg-mix">%s</div><div class="pg-mixt">%s</div>'
                 % ("".join('<i style="width:%.1f%%;background:%s"></i>'
                            % (100 * est[k] / total, c[k])
                            for k in ("computer", "phone", "talking")
                            if est.get(k, 0) > 0),
                    " &middot; ".join("%s %s" % (w, dur(est[k]))
                                      for k, w in (("computer", "computer"),
                                                   ("phone", "phone"),
                                                   ("talking", "talking"))
                                      if est.get(k, 0) >= 1)))
    # And where they were when not at the desk (24 Nov, Shamroze: "sirf
    # computer pe baitha dikha rahe ho" -- the cafe, a meeting, out of the
    # building): the campus cameras' faces and the gate's, in words.
    gone_to = [(away_word(k, p), m.get(k, 0.0)) for k, _ in AWAY_WORDS
               if came and m.get(k, 0.0) >= 1]
    if gone_to:
        split += ('<div class="pg-mixt pg-away">away: %s</div>'
                  % " &middot; ".join("%s %s" % (esc(w), dur(v))
                                      for w, v in gone_to))
    if share is not None and early:
        vs = ('<b class="same">--</b><small>%s</small>'
              % ("usual %s" % pct(usual) if usual is not None
                 else "under an hour in"))
    elif share is not None and usual is not None:
        diff = 100 * (share - usual)
        arrow = ("up", "&#9650;") if diff >= 3 else ("down", "&#9660;") \
            if diff <= -3 else ("same", "&#9679;")
        vs = ('<b class="%s">%s %+.0f</b><small>vs usual %s</small>'
              % (arrow[0], arrow[1], diff, pct(usual)))
    elif usual is not None:
        vs = '<b class="same">--</b><small>usual %s</small>' % pct(usual)
    else:
        vs = '<b class="same">--</b><small>no usual yet</small>'
    slots = f.get("slots") or []
    bar = (strip_svg(slots, c, frm, to) if slots else
           '<svg viewBox="0 0 100 10" class="pg-bar"></svg>')
    word = "Out of the building" if left else (
        lv.get("label") or "Gone home") if state == "gone" else \
        STATE_WORDS.get(state, state)
    gate_line = ('<small class="pg-gate">gate out %s</small>'
                 % " &middot; ".join(t[:5] for t in gate[-3:])) if gate else ""
    run_line = []
    if longest and longest >= 15:
        run_line.append("longest sitting %s" % dur(longest))
    if came and breaks:
        run_line.append("%d break%s" % (breaks, "" if breaks == 1 else "s"))
    html = (
        '<div class="pg-row %s">'
        '<div class="pg-who">%s<div><b>%s</b><span>%s</span></div></div>'
        '<div class="pg-now"><em style="background:%s">%s</em><small>%s%s'
        '</small>%s</div>'
        '<div class="pg-in"><small>in</small><b>%s</b>%s</div>'
        '<div class="pg-desk"><b>%s</b><small>at the desk%s</small>'
        '<div class="pg-meter"><i style="width:%.0f%%"></i></div>%s</div>'
        '<div class="pg-line">%s%s</div>'
        '<div class="pg-vs">%s</div></div>'
        % (state, badge(p, "sm"), esc(who(p)),
           esc(" · ".join(x for x in (p.get("department", ""),
                                      ("ID %s" % p["employee_id"])
                                      if p.get("employee_id") else "") if x)),
           LIVE_COLOURS.get(state, "#898781"), word,
           esc(now), (" &middot; %s" % esc(lv["place"]))
           if lv.get("place") else "", gate_line,
           first, '<small class="pg-late">late</small>' if late else "",
           dur(at) if at else "--",
           (" &middot; %s of time in" % pct(share)) if share is not None
           else "", 100 * (share or 0),
           ('<small class="pg-run">%s</small>' % " &middot; ".join(run_line))
           if run_line else "", bar, split, vs))
    order = {"desk": 0, "away": 1, "gone": 2, "out": 3}.get(state, 4)
    return html, (order, -(share or 0))


def today_board(people, c, as_of="", frm=8, to=24, start=10.0):
    """Today, one line an employee (Shamroze, 24 Nov: a tracker for the
    people he names, "bht acha sa"): where they are now, when they came
    in, their time at the desk so far and that as a share of their time
    in, the day as a bar, what they were doing at the desk where it was
    read, and today's share against their own usual. What the cameras
    measure is time at the desk -- never called "productive"."""
    if not any(p.get("focus") or p.get("live") for p in people):
        return ""
    rows = sorted((board_row(p, c, frm, to, start) for p in people),
                  key=lambda r: r[1])
    here = sum(1 for p in people
               if (p.get("live") or {}).get("state") == "desk")
    away = sum(1 for p in people
               if (p.get("live") or {}).get("state") == "away")
    return ('<div class="ec-h"><span class="t">Today, employee by employee'
            '</span><span class="c">%d at the desk &middot; %d away &middot; '
            'the bar runs %02d:00-%02d:00 &middot; %s</span></div>'
            '<div class="ec-card pg-board"><div class="pg-row pg-head"><div>'
            'Employee</div><div>Now</div><div>In</div><div>Desk today</div>'
            '<div>The day</div><div>vs usual</div></div>%s</div>'
            % (here, away, frm, to, ("as of %s" % esc(as_of)) if as_of
               else "", "".join(r[0] for r in rows)))


# ------------------------------------------------ one employee's report card
#
# Shamroze, 24 Nov: "ek employee ka ... chhota sa table card, report card
# uski aaj ke din ki", and "pura chart -- itne time se itne time tak yahan
# gaya, itne time se itne time tak wahan", with "average ka option bhi".
# One employee at a time (rooms_dashboard picks who, and today or a usual
# day): the day's figures beside their usual, the day as lanes -- at the
# desk, each place, out of the building, not seen -- and the day from-to.

# Their own room off the desk, the cafe and the smoking area each a lane of
# their own (25 Nov: the Basement's people by "desk pe, Basement mein,
# smoking area mein, cafe mein").
LANES = [("desk", "At the desk", AT_DESK_KINDS),
         ("own", "Own room, off the desk", ("own room",)),
         ("meeting", "Meetings", ("meeting",)),
         ("cafe", "Cafe", ("cafe",)),
         ("smoking", "Smoking area", ("smoking",)),
         ("prayer", "Prayer", ("prayer",)),
         ("outside", "Outside on campus", ("outside",)),
         ("rooms", "Other rooms", ("office", "corridor")),
         ("left", "Out of the building", ("left",)),
         ("unseen", "Away, not seen", ("unseen",))]
REPORT_VIEWS = ("Today", "Usual day (average)")


def _span(segs, frm=8, to=22):
    """The hours a day chart runs: the day's own, an hour either side,
    at least eight hours."""
    import math
    if not segs:
        return frm, to
    a = min(s[0] for s in segs)
    b = max(s[1] for s in segs)
    lo = max(0, math.floor(a.hour + a.minute / 60.0) - 1)
    hi = min(24, math.ceil(b.hour + b.minute / 60.0 + 0.01) + 1)
    if hi - lo < 8:
        hi = min(24, lo + 8)
        lo = max(0, hi - 8)
    return lo, hi


def _ticks(lo, hi):
    step = 1 if hi - lo <= 10 else 2
    return "".join('<span style="left:%.2f%%">%s</span>'
                   % (100.0 * (h - lo) / (hi - lo), hhmm(h)[:5])
                   for h in range(lo, hi + 1, step))


def day_lanes(focus, c, now=None, own="", only_presence=False):
    """The day as lanes, one a place: a bar wherever they were there, its
    from-to and minutes on hover; "now" marked. `own`: their room, named on
    its lane; `only_presence`: the desk is not read, so its bar is the
    desk's own colour, not the paler "activity not read"."""
    segs = [s for s in (focus or {}).get("segments") or []
            if s[2] not in ("out",)]
    if not segs:
        return ""
    lo, hi = _span(segs)
    base = segs[0][0].normalize()
    span = (hi - lo) * 60.0

    def x(t):
        return max(0.0, min(100.0, 100.0 * ((t - base).total_seconds() / 60.0
                                            - lo * 60) / span))
    rows = []
    for key, label, kinds in LANES:
        mine = [s for s in segs if s[2] in kinds]
        if not mine:
            continue
        if key == "own" and own:
            label = "In the %s, off the desk" % own
        total = sum((s[1] - s[0]).total_seconds() / 60.0 for s in mine)
        bars = []
        for s, e, k, room in mine:
            col = (c["computer"] if only_presence else c["deskread"]) \
                if k == "desk" else c.get(k, c["unseen"])
            what = SLOT_WORDS.get(k, k) + (
                " (%s)" % room if room and k not in AT_DESK_KINDS
                and k != "left" else "")
            bars.append('<i style="left:%.2f%%;width:%.2f%%;background:%s" '
                        'title="%s-%s %s, %s"></i>'
                        % (x(s), max(0.25, x(e) - x(s)), col,
                           s.strftime("%H:%M"), e.strftime("%H:%M"),
                           esc(what), dur((e - s).total_seconds() / 60.0)))
        rows.append('<div class="pg-lane"><span class="l">%s<em>%s</em>'
                     '</span><div class="b">%s</div></div>'
                     % (esc(label), dur(total), "".join(bars)))
    mark = ""
    if now is not None and lo * 60 <= (now - base).total_seconds() / 60.0 \
            <= hi * 60:
        mark = '<b class="pg-nowl" style="left:%.2f%%" title="now"></b>' % x(now)
    return ('<div class="pg-lanes">%s<div class="pg-lane ax"><span class="l">'
            '</span><div class="b">%s%s</div></div></div>'
            % ("".join(rows), _ticks(lo, hi), mark))


def day_list(focus, c, only_presence=False, own=""):
    """The day from-to, oldest first: where, how long, and what. `own`:
    their own room, said as "in the <room>, off the desk"."""
    import progress_data as pdx
    items = (focus or {}).get("stretches") or []
    out = []
    words = dict(KIND_WORDS, desk="activity not read")
    for st in items:
        if st["what"] == "desk":
            col, where = c["computer"], "At the desk"
            kinds = sorted(((k, v) for k, v in st["kinds"].items() if v >= 1),
                           key=lambda kv: -kv[1])
            detail = "" if only_presence else ", ".join(
                "%s %s" % (words.get(k, k), dur(v)) for k, v in kinds)
        elif st["what"] == "unwatched":
            if (st.get("minutes") or 0) < 10:
                continue                  # a short hole: the chart shows it
            col, where, detail = c["t3"], "Not watched", "the loop was off"
        else:
            places = [("out through the gate" if r == pdx.GATE_ROOM else r)
                      for r in st.get("where") or []]
            left = "out of the building" in places or \
                "out through the gate" in places
            col = c["left"] if left else (c["meeting"] if places
                                          else c["unseen"])
            where = ("Out of the building" if left else
                     ("In the %s, off the desk" % own)
                     if own and places == [own] else
                     ("Away: %s" % ", ".join(places)) if places
                     else "Away, not seen")
            seen = [r for r, h in st.get("seen") or [] if r not in places]
            detail = ("possibly %s" % ", ".join(seen)) if seen else ""
        out.append('<tr><td class="t"><i style="background:%s"></i>%s&ndash;%s'
                   '</td><td class="n">%s</td><td><b>%s</b>%s</td></tr>'
                   % (col, st["from"].strftime("%H:%M"),
                      st["to"].strftime("%H:%M"), dur(st["minutes"]),
                      esc(where), (' <span>%s</span>' % esc(detail))
                      if detail else ""))
    if not out:
        return ""
    return ('<table class="pg-list"><thead><tr><th>From&ndash;to</th>'
            '<th>How long</th><th>Where</th></tr></thead><tbody>%s</tbody>'
            '</table>' % "".join(out))


def usual_hours(p, c, frm=8, to=22):
    """A usual day hour by hour: how often they were at the desk in each
    hour over their last working days (bars), today as a dot."""
    days = p.get("days") or []
    slots = p.get("slots") or []
    focus_day = (p.get("focus") or {}).get("day")
    per = 6                                      # 10-minute slots an hour
    past = [sl for d, sl in zip(days, slots)
            if not d.get("before") and d.get("day") != focus_day]
    today = next((sl for d, sl in zip(days, slots)
                  if d.get("day") == focus_day), None)
    if not past:
        return ""
    cols = []
    for h in range(frm, to):
        i = (h - 8) * per                       # strips start at 08:00
        if i < 0:
            continue
        desk = sum(sl[i:i + per].count("desk") for sl in past)
        inside = sum(sum(1 for s in sl[i:i + per] if s in ("desk", "away"))
                     for sl in past)
        share = desk / float(len(past) * per)
        here = inside / float(len(past) * per)
        dot = ""
        seg = today[i:i + per] if today is not None else []
        if any(s in ("desk", "away") for s in seg):
            # only hours they were in today -- not before, after or to come
            t_desk = seg.count("desk") / float(per)
            dot = '<b style="bottom:%.0f%%" title="today %s"></b>' % (
                100 * t_desk, pct(t_desk))
        cols.append('<div class="c" title="%s-%s: at the desk %s of the '
                    'time, in the office %s"><span class="in" style="height:'
                    '%.0f%%"></span><span class="d" style="height:%.0f%%">'
                    '</span>%s<small>%s</small></div>'
                    % (hhmm(h), hhmm(h + 1), pct(share), pct(here),
                       100 * here, 100 * share, dot,
                       str(h) if h % 2 == 0 else ""))
    return ('<div class="pg-hours">%s</div><div class="pg-hkey"><span><i '
            'style="background:%s"></i>at the desk, usually</span><span><i '
            'style="background:var(--line)"></i>in the office, usually</span>'
            '<span><b></b>today</span><span>over %d working day%s</span></div>'
            % ("".join(cols), c["computer"], len(past),
               "" if len(past) == 1 else "s"))


def report_rows(p, start=10.0):
    """The report card's lines: (label, today, usual)."""
    import progress_data as pdx
    f = p.get("focus") or {}
    m = f.get("minutes") or {}
    came = f.get("first_in") is not None
    at = sum(m.get(k, 0.0) for k in AT_DESK_KINDS) if came else 0.0
    away = sum(v for k, v in m.items()
               if k not in AT_DESK_KINDS and k not in ("out", "unwatched")) \
        if came else 0.0
    est = f.get("estimate") or {}
    past = [r for r in p.get("history") or [] if r.get("day") != f.get("day")]
    u = pdx.average(past, 7) or {}
    late, of = late_days(past, 7, start)
    stretches_ = f.get("stretches") or []
    runs = [s["minutes"] for s in stretches_ if s.get("what") == "desk"]
    breaks = [s for s in stretches_ if s.get("what") not in ("desk",
                                                             "unwatched")
              and (s.get("minutes") or 0) >= BREAK_MIN]

    def t(x):
        return x.strftime("%H:%M") if hasattr(x, "strftime") else "--"

    def clock(v):
        return hhmm(v / 60.0) if v is not None else "--"

    def mins(v):
        return dur(v) if v is not None else "--"
    lv = p.get("live") or {}
    still = lv.get("state") in ("desk", "away")
    first = f.get("first_in")
    is_late = hasattr(first, "hour") and \
        first.hour + first.minute / 60.0 > start + LATE_AFTER / 60.0
    read = bool(f.get("read")) and sum(est.get(k, 0.0) for k in
                                       ("computer", "phone", "talking")) > 0
    only = presence(p)
    rows = [
        ("Came in (first at the desk)", t(first) if came else "not in",
         clock(u.get("first"))),
        ("Left (last at the desk)", ("still in" if still else t(
            f.get("last_out"))) if came else "--", clock(u.get("last"))),
    ]
    # The attendance machines (attendance.py, 25 Nov): in and out at the
    # building's own turnstile -- what HR goes by -- beside the desk's.
    att = f.get("attendance") or {}
    if att.get("first_in") is not None:
        outs = att.get("outings") or []
        out_min = sum((b - a).total_seconds() / 60.0 for a, b in outs)
        rows += [
            ("Machine: in &middot; out", "%s &middot; %s" % (
                t(att["first_in"]),
                t(att.get("last_out")) if att.get("last_out") is not None
                else ("still in" if still else "no out")), ""),
            ("&nbsp;&nbsp;in the building", mins(att.get("inside_min")), ""),
            ("&nbsp;&nbsp;out and back", "%d time%s, %s" % (
                len(outs), "" if len(outs) == 1 else "s", dur(out_min))
             if outs else "none", ""),
        ]
    rows += [
        ("Late (after %s)" % hhmm(start + LATE_AFTER / 60.0),
         ("yes" if is_late else "no") if came else "--",
         "%d of %d days" % (late, of) if of else "--"),
        ("In the office (watched)", mins(at + away) if came else "--",
         mins(u.get("in_min"))),
        ("At the desk", ("%s &middot; %s" % (dur(at), pct(at / (at + away))))
         if came and at + away > 0 else "--",
         ("%s &middot; %s" % (mins(u.get("desk_min")), pct(u.get("desk_pct"))))
         if u.get("desk_min") is not None else "--"),
        ("&nbsp;&nbsp;at the computer", mins(est.get("computer")) if read
         else "--", mins(u.get("computer_min"))),
        ("&nbsp;&nbsp;on the phone", mins(est.get("phone")) if read else "--",
         mins(u.get("phone_min"))),
        ("&nbsp;&nbsp;talking at the desk", mins(est.get("talking")) if read
         else "--", mins(u.get("talking_min"))),
        ("Longest sitting", mins(max(runs)) if runs else "--", "--"),
        ("Breaks of %d+ min" % BREAK_MIN, "%d" % len(breaks) if came else "--",
         ("%.1f" % u["breaks"]) if u.get("breaks") is not None else "--"),
        ("Away from the desk", mins(away) if came else "--",
         mins(u["in_min"] - u["desk_min"]) if u.get("in_min") is not None
         and u.get("desk_min") is not None else "--"),
    ]
    if only:
        # presence only (the Basement): where they were, never what they
        # did at the desk -- not even an old day's reading in the usual
        rows = [r for r in rows if r[0] not in (
            "&nbsp;&nbsp;at the computer", "&nbsp;&nbsp;on the phone",
            "&nbsp;&nbsp;talking at the desk")]
    for k, _ in AWAY_WORDS:
        if came and m.get(k, 0.0) >= 1:
            rows.append(("&nbsp;&nbsp;%s" % esc(away_word(k, p)), dur(m[k]),
                         ""))
    return rows, u


FOCUS_MIN = 60           # min: a stretch at the desk this long is a long one
SCORE_PARTS = (("At the desk", 0.5,
                "share of office hours so far at the desk"),
               ("Long stretches", 0.3,
                "share of desk time in stretches of an hour or more"),
               ("On time", 0.2,
                "in by the start (+15 min); 10 off a quarter-hour late"))


def day_score(p, start=10.0, end=20.0, now=None, team=None):
    """A day's desk score (Shamroze, 25 Nov: "score card ko behtar
    banana", the way workplace analytics put it -- time used, focus
    blocks, punctuality; Viva Insights counts focus as blocks of an hour
    or more): {parts: [(name, 0-100, weight, what)], score, focus_min,
    short_min, rank, of}. None before they came in. What it scores is
    time at the desk and how it came -- never the work itself."""
    import datetime as _dt
    f = p.get("focus") or {}
    first = f.get("first_in")
    if first is None:
        return None
    m = f.get("minutes") or {}
    at = sum(m.get(k, 0.0) for k in AT_DESK_KINDS)
    runs = [s["minutes"] for s in f.get("stretches") or []
            if s.get("what") == "desk"]
    long_ = sum(r for r in runs if r >= FOCUS_MIN)
    day = pd_day = f.get("day")
    base = _dt.datetime.fromisoformat(pd_day) if day else None
    office = (end - start) * 60.0
    if now is not None and base is not None and \
            now.strftime("%Y-%m-%d") == day:
        so_far = (now.hour + now.minute / 60.0 - start) * 60.0
        office = max(60.0, min(office, so_far))
    share = min(1.0, at / office) if office > 0 else 0.0
    late = max(0.0, (first.hour + first.minute / 60.0 - start) * 60.0
               - LATE_AFTER)
    on_time = max(0.0, 100.0 - 10.0 * math.ceil(late / 15.0)) if late else 100.0
    parts = [(SCORE_PARTS[0][0], 100.0 * share, SCORE_PARTS[0][1],
              SCORE_PARTS[0][2]),
             (SCORE_PARTS[1][0], 100.0 * long_ / at if at else 0.0,
              SCORE_PARTS[1][1], SCORE_PARTS[1][2]),
             (SCORE_PARTS[2][0], on_time, SCORE_PARTS[2][1],
              SCORE_PARTS[2][2])]
    score = sum(v * w for _, v, w, _ in parts)
    rank = of = None
    if team:
        mins = []
        for q in team:
            fq = q.get("focus") or {}
            if fq.get("first_in") is None or fq.get("day") != day:
                continue
            mq = fq.get("minutes") or {}
            mins.append((sum(mq.get(k, 0.0) for k in AT_DESK_KINDS),
                         q.get("code")))
        mins.sort(reverse=True)
        of = len(mins)
        rank = next((i + 1 for i, (_, code) in enumerate(mins)
                     if code == p.get("code")), None)
    return {"parts": parts, "score": score, "focus_min": long_,
            "short_min": max(0.0, at - long_), "rank": rank, "of": of}


def score_card(p, c, start=10.0, end=20.0, now=None, team=None):
    """day_score as a small card: the score, its parts as bars, where the
    day stands among the board's people."""
    s = day_score(p, start, end, now, team)
    if not s:
        return ""
    bars = "".join(
        '<div class="sp"><span>%s<em>%d%% weight</em></span><div class="m">'
        '<i style="width:%.0f%%"></i></div><b>%.0f</b><small>%s</small></div>'
        % (esc(name), round(w * 100), v, v, esc(what))
        for name, v, w, what in s["parts"])
    rank = ('<span class="rk">%s of %d on the board by time at the desk today'
            '</span>' % (_ordinal(s["rank"]), s["of"])) \
        if s.get("rank") and s.get("of") else ""
    return ('<div class="pg-score"><div class="top"><b>%.0f</b><span>desk '
            'score / 100</span>%s</div>%s<div class="split">long stretches '
            '%s &middot; in shorter bits %s</div></div>'
            % (s["score"], rank, bars, dur(s["focus_min"]),
               dur(s["short_min"])))


def _ordinal(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else
                     {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def report(p, c, view=REPORT_VIEWS[0], start=10.0, now=None, end=20.0,
           team=None):
    """One employee's report card (one at a time, rooms_dashboard picks):
    the head, the figures today beside their usual, and the day chart --
    or, for the usual day, the hours they are usually at the desk."""
    import datetime as _dt
    f = p.get("focus") or {}
    lv = p.get("live") or {}
    rows, u = report_rows(p, start)
    m = f.get("minutes") or {}
    came = f.get("first_in") is not None
    at = sum(m.get(k, 0.0) for k in AT_DESK_KINDS) if came else 0.0
    away = sum(v for k, v in m.items()
               if k not in AT_DESK_KINDS and k not in ("out", "unwatched")) \
        if came else 0.0
    share = at / (at + away) if at + away > 0 else None
    usual = u.get("desk_pct")
    vs = ""
    if share is not None and usual is not None and at + away >= 60:
        d = 100 * (share - usual)
        vs = '<span class="%s">%s %+.0f vs usual %s</span>' % (
            "up" if d >= 3 else "down" if d <= -3 else "same",
            "&#9650;" if d >= 3 else "&#9660;" if d <= -3 else "&#9679;", d,
            pct(usual))
    day = f.get("day")
    label = _dt.date.fromisoformat(day).strftime("%a %d %b") if day else ""
    state = lv.get("state", "out")
    since = lv.get("since")
    now_txt = (lv.get("label") or STATE_WORDS.get(state, state)) + (
        " &middot; %s" % since.strftime("%H:%M") if hasattr(since, "strftime")
        else "") + (" &middot; %s" % esc(lv["place"]) if lv.get("place")
                    else "")
    head = ('<div class="pg-rhead">%s<div class="who"><b>%s</b><span>%s</span>'
            '</div><div class="big"><b>%s</b><span>at the desk%s</span>%s</div>'
            '</div><div class="pg-rnow"><em style="background:%s">%s</em>'
            '<span>%s</span></div>'
            % (badge(p), esc(who(p)),
               esc(" · ".join(x for x in (
                   p.get("department", ""),
                   ("ID %s" % p["employee_id"]) if p.get("employee_id")
                   else "", label,
                   "sitter not named yet -- Name the desks, below"
                   if not p.get("name") and "." in str(p.get("code", ""))
                   else "",
                   "named by the attendance machines, not checked by eye"
                   if p.get("how") == "attendance" else "") if x)),
               dur(at) if came else "--",
               (" &middot; %s of time in" % pct(share)) if share is not None
               else "", vs, LIVE_COLOURS.get(state, "#898781"),
               esc(STATE_WORDS.get(state, state)), now_txt))
    table = ('<table class="pg-rep"><thead><tr><th></th><th>%s</th><th>Usual'
             '<small>%s</small></th></tr></thead><tbody>%s</tbody></table>'
             % ("Today" if day == (now or _dt.datetime.now()).strftime(
                 "%Y-%m-%d") else esc(label),
                ("average, last %d whole day%s" % (
                    u["days"], "" if u["days"] == 1 else "s"))
                if u.get("days") else "no days yet",
                "".join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
                        % (a, b, cc) for a, b, cc in rows)))
    if view == REPORT_VIEWS[1]:
        chart = usual_hours(p, c)
        body = ('<div class="pg-rsec">A usual day, hour by hour</div>%s'
                % (chart or '<div class="pg-empty">No past days watched yet.'
                   '</div>'))
    else:
        own = p.get("department") or ""
        lanes = day_lanes(f, c, now, own, presence(p))
        body = ('<div class="pg-rsec">The day, place by place '
                '<span>hover a bar for its from&ndash;to</span></div>%s'
                '<div class="pg-rsec">From&ndash;to</div>%s'
                % (lanes or '<div class="pg-empty">Not at the desk yet today.'
                   '</div>', day_list(f, c, presence(p), own)))
    table = score_card(p, c, start, end, now, team) + table
    if presence(p):
        how = ('Presence only, as asked for the %s: whether the employee is '
               'at the desk, in the %s off it, in the cafe or the smoking '
               'area, or out of the building -- what they do at the desk is '
               'not read.' % (esc(p.get("department") or "room"),
                              esc(p.get("department") or "room")))
    else:
        how = ('At the computer, on the phone and talking are read every '
               'few passes and shared out over the rest.')
    return ('<div class="ec-card pg-report">%s<div class="pg-rgrid"><div>%s'
            '</div><div>%s</div></div><div class="pg-rfoot">Measured: time '
            'at the desk (every pass of the loop) and where the employee was '
            'seen when away -- by face on the campus cameras and at the gate. '
            '"Not seen" is time on no camera. %s The desk score weighs time '
            'at the desk, long stretches (as workplace analytics count '
            'focus: an hour or more unbroken) and coming in on time -- it '
            'says how the day was spent at the desk, not what the work was '
            'worth.</div></div>' % (head, table, body, how))


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
            comp = None if presence(p) else r.get("computer_pct")
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
        rows.append('<tr><th class="who">%s%s<span>%s</span></th>%s'
                    '<td class="avg"><b>%s</b></td></tr>'
                    % (face(p, "xs"), esc(tag(p)),
                       esc(p.get("department", "")),
                       "".join(cells), pct(avg)))
    return ('<div class="ec-h"><span class="t">Every day</span><span class="c">'
            'desk %% = time at the desk of the time in the office (first in to '
            'last out, as watched); computer %% where the activity was read; '
            '* part of the day watched</span></div>'
            '<div class="ec-card pg-tablewrap"><table class="pg-team"><thead>'
            '<tr><th></th>%s<th>usual</th></tr></thead><tbody>%s</tbody>'
            '</table></div>' % (head, "".join(rows)))


def late_days(history, days=7, start=10.0):
    """(late, of): the days in among the last `days` whose first-in came
    more than LATE_AFTER minutes after the office's start."""
    seen = [r for r in history or [] if r.get("first") is not None][-days:]
    late = sum(1 for r in seen if hasattr(r["first"], "hour")
               and r["first"].hour + r["first"].minute / 60.0
               > start + LATE_AFTER / 60.0)
    return late, len(seen)


def averages_table(people, days=7, start=10.0):
    """Each employee's usual over their last seven days in: in, out, the
    office and the desk, computer and phone, breaks (progress_data.average)
    and the days they came in late (24 Nov). Shamroze, 23 Nov: "per day ya
    7 din ka average"."""
    import progress_data as pdx
    rows = []
    for p in people:
        a = pdx.average(p.get("history"), days)
        if a is None:
            rows.append('<tr><th class="who">%s%s<span>%s</span></th>'
                        '<td colspan="10" class="none">no day in yet</td></tr>'
                        % (face(p, "xs"), esc(tag(p)),
                           esc(p.get("department", ""))))
            continue
        reads = a["read_days"] and not presence(p)
        comp = ('<small>presence only</small>' if presence(p) else
                "%s <small>%d day%s read</small>"
                % (pct(a["computer_pct"]), a["read_days"],
                   "" if a["read_days"] == 1 else "s")
                if a["read_days"] else '<small>not read yet</small>')
        late, of = late_days(p.get("history"), days, start)
        rows.append(
            '<tr><th class="who">%s%s<span>%s</span></th><td>%d</td>'
            '<td><b>%s</b></td><td>%s</td><td><b>%s</b></td><td>%s</td>'
            '<td>%s</td><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td>'
            '</tr>'
            % (face(p, "xs"), esc(tag(p)), esc(p.get("department", "")),
               a["days"], hhmm(a["first"] / 60.0 if a["first"] is not None
                               else None),
               ("%d of %d days" % (late, of)) if of else "--",
               hhmm(a["last"] / 60.0 if a["last"] is not None else None),
               dur(a["in_min"]), dur(a["desk_min"]), pct(a["desk_pct"]),
               comp, dur(a["phone_min"]) if reads else "--",
               "%.1f (longest %s)" % (a["breaks"] or 0, dur(a["longest_break"]))
               if a["breaks"] is not None else "--"))
    return ('<div class="ec-h"><span class="t">The usual week</span>'
            '<span class="c">each employee&rsquo;s average over their last '
            '%d days in (days only partly watched left out) &middot; computer '
            'and phone only on the days the activity was read (from 23 Nov)'
            '</span></div><div class="ec-card pg-tablewrap"><table '
            'class="pg-team pg-avg"><thead><tr><th></th><th>days</th>'
            '<th>in</th><th>late</th><th>out</th><th>in the office</th>'
            '<th>at the desk'
            '</th><th>desk %%</th><th>computer %%</th><th>phone</th>'
            '<th>breaks a day</th></tr></thead><tbody>%s</tbody></table>'
            '</div>' % (days, "".join(rows)))


def cases_block(people):
    """The boss's cases: a few plain sentences from the last week, in
    cards (progress_data.cases)."""
    import progress_data as pdx
    items = pdx.cases(people)
    if not items:
        return ""
    cards = "".join(
        '<div class="ec-card pg-case"><span class="k">%s</span><p>%s</p>'
        '</div>' % (esc(c["title"]), esc(named(c["text"], people)))
        for c in items)
    return ('<div class="ec-h"><span class="t">Cases for the boss</span>'
            '<span class="c">from the last seven days in &middot; what the '
            'cameras measured, at the desk or away -- not the work itself'
            '</span></div><div class="pg-cases">%s</div>' % cards)


def legend(c):
    items = [("desk", "at the desk"), ("away", "away from the desk"),
             ("meeting", "away, seen somewhere (the place in words)"),
             ("left", "out of the building (the gate)"),
             ("out", "not in yet / gone")]
    return ('<div class="ec-legend">%s<span><i class="box pg-hatch"></i>'
            'not watched</span></div>'
            % "".join('<span><i class="box" style="background:%s"></i>%s'
                      '</span>' % (c[k], esc(t)) for k, t in items))


def report_block(mode, p, view=REPORT_VIEWS[0], start=10.0, now=None,
                 end=20.0, team=None):
    """report() with the page's styles, for the dashboard to draw on its
    own between page(part="top") and page(part="rest")."""
    c = colours(mode)
    return (css(mode) + "\n" + _CSS % c + "\n" + '<div class="ec pg">'
            + report(p, c, view, start, now, end, team) + "</div>")


def page(mode, cfg, people, as_of, hours=(10, 20), frm=8, to=24, part=None):
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
    # The scoreboard took the "Right now" strip's place (24 Nov): it says
    # where everybody is too, beside their day.
    board = today_board(people, c, as_of, frm, to, float(hours[0]))
    style = css(mode) + "\n" + _CSS % c + "\n"
    top = head + (board or live_strip(people, c, as_of))
    # The dashboard puts one employee's report card (report(), with its own
    # pickers) between the board and the rest: part "top", then "rest".
    if part == "top":
        return style + '<div class="ec pg">' + top + "</div>"
    if part == "rest":
        top = ""
    return (style + '<div class="ec pg">' + top + tiles(people, c)
            + team_table(people, c)
            + averages_table(people, start=float(hours[0]))
            + cases_block(people)
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
.pg .pg-face{flex:none;width:42px;height:42px;border-radius:50%%;object-fit:cover;
box-shadow:0 0 0 2px var(--s1),0 0 0 3.5px #3987e5}
.pg .pg-face.sm{width:30px;height:30px;box-shadow:0 0 0 1.5px var(--s1),0 0 0 3px #3987e5}
.pg .pg-face.xs{width:22px;height:22px;vertical-align:-6px;margin-right:7px;
box-shadow:0 0 0 1.5px #3987e5}
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
.pg .pg-cases{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
gap:12px;margin-bottom:14px}
.pg .pg-case{padding:14px 16px}
.pg .pg-case .k{font-size:11.5px;font-weight:650;color:var(--t3);text-transform:uppercase;
letter-spacing:.04em}
.pg .pg-case p{margin:6px 0 0;font-size:14px;line-height:1.45;color:var(--t1)}
.pg .pg-stretch{margin:2px 0 8px;font-size:12px}
.pg .pg-stretch summary{cursor:pointer;font-weight:650;color:var(--t1);padding:4px 0}
.pg .pg-stretch summary span{font-weight:500;color:var(--t3);margin-left:4px}
.pg .pg-st{display:grid;grid-template-columns:4px 92px 54px 1fr;gap:8px;
align-items:baseline;padding:5px 0;border-top:1px solid var(--line)}
.pg .pg-st i{display:block;width:4px;height:14px;border-radius:2px;align-self:center}
.pg .pg-st .w{white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--t1)}
.pg .pg-st .m{white-space:nowrap;color:var(--t3);font-variant-numeric:tabular-nums}
.pg .pg-st .x{color:var(--t2);min-width:0}
.pg .pg-st .x b{color:var(--t1);font-weight:650}
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
.pg .pg-board{padding:6px 16px 10px}
.pg .pg-row{display:grid;grid-template-columns:minmax(170px,1.5fr) 118px 52px
minmax(130px,1fr) minmax(180px,2fr) 84px;gap:14px;align-items:center;
padding:11px 0;border-top:1px solid var(--line)}
.pg .pg-row.pg-head{border-top:0;padding:8px 0 4px;font-size:10.5px;font-weight:650;
color:var(--t3);text-transform:uppercase;letter-spacing:.05em}
.pg .pg-who{display:flex;align-items:center;gap:10px;min-width:0}
.pg .pg-who div{display:flex;flex-direction:column;min-width:0}
.pg .pg-who b{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pg .pg-who span{font-size:11px;color:var(--t3);white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.pg .pg-now{display:flex;flex-direction:column;gap:3px;min-width:0}
.pg .pg-now em{font-style:normal;align-self:flex-start;font-size:11px;font-weight:650;
color:#fff;padding:2px 9px;border-radius:99px;white-space:nowrap}
.pg .pg-now small,.pg .pg-in small,.pg .pg-desk small,.pg .pg-vs small{font-size:10.5px;
color:var(--t3)}
.pg .pg-in{display:flex;flex-direction:column;align-items:flex-start}
.pg .pg-in b{font-size:14px;font-variant-numeric:tabular-nums}
.pg .pg-in .pg-late{font-size:10px;font-weight:700;color:#fff;background:%(away)s;
border-radius:99px;padding:0 6px;margin-top:2px}
.pg .pg-now .pg-gate{font-size:10.5px;color:var(--t3);white-space:nowrap}
.pg .pg-desk .pg-run{font-size:10.5px;color:var(--t3);margin-top:3px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.pg .pg-desk{display:flex;flex-direction:column;min-width:0}
.pg .pg-desk b{font-size:17px;font-weight:720;font-variant-numeric:tabular-nums}
.pg .pg-meter{height:6px;border-radius:3px;background:var(--line);overflow:hidden;
margin-top:4px}
.pg .pg-meter i{display:block;height:100%%;border-radius:3px;background:%(desk)s}
.pg .pg-line{min-width:0}
.pg .pg-mix{display:flex;height:5px;border-radius:3px;overflow:hidden;margin-top:5px;
background:var(--line)}
.pg .pg-mix i{display:block;height:100%%}
.pg .pg-mixt{font-size:10.5px;color:var(--t3);margin-top:3px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.pg .pg-away{white-space:normal;color:var(--t2)}
.pg .pg-report{padding:16px 18px;margin-top:8px}
.pg .pg-score{border:1px solid var(--line);border-radius:12px;padding:12px 14px;
margin-bottom:14px}
.pg .pg-score .top{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;
margin-bottom:8px}
.pg .pg-score .top b{font-size:30px;font-variant-numeric:tabular-nums;line-height:1}
.pg .pg-score .top span{font-size:12px;color:var(--t2)}
.pg .pg-score .top .rk{flex-basis:100%%;color:var(--t3);font-size:11.5px}
.pg .pg-score .sp{display:grid;grid-template-columns:118px minmax(0,1fr) 30px;
gap:2px 8px;align-items:center;margin-top:6px}
.pg .pg-score .sp span{font-size:12px;color:var(--t2)}
.pg .pg-score .sp span em{display:block;font-style:normal;font-size:10.5px;
color:var(--t3)}
.pg .pg-score .sp .m{height:7px;border-radius:99px;background:var(--s2);overflow:hidden}
.pg .pg-score .sp .m i{display:block;height:100%%;background:%(computer)s}
.pg .pg-score .sp b{font-size:12.5px;text-align:right;font-variant-numeric:tabular-nums}
.pg .pg-score .sp small{grid-column:2/4;font-size:10.5px;color:var(--t3)}
.pg .pg-score .split{font-size:11.5px;color:var(--t3);margin-top:8px}
.pg .pg-rhead{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.pg .pg-rhead .who{display:flex;flex-direction:column;flex:1;min-width:160px}
.pg .pg-rhead .who b{font-size:17px}
.pg .pg-rhead .who span{font-size:12px;color:var(--t3)}
.pg .pg-rhead .big{display:flex;flex-direction:column;align-items:flex-end}
.pg .pg-rhead .big b{font-size:26px;font-variant-numeric:tabular-nums;line-height:1.1}
.pg .pg-rhead .big span{font-size:12px;color:var(--t2)}
.pg .pg-rhead .big .up{color:#2a9d63;font-weight:600}
.pg .pg-rhead .big .down{color:#d03b3b;font-weight:600}
.pg .pg-rnow{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0 14px;
font-size:12.5px;color:var(--t2)}
.pg .pg-rnow em{font-style:normal;color:#fff;border-radius:10px;padding:2px 9px;
font-size:11.5px;font-weight:600}
.pg .pg-rgrid{display:grid;grid-template-columns:minmax(250px,330px) minmax(0,1fr);
gap:22px;align-items:start}
.pg .pg-rgrid>div{min-width:0}
.pg .pg-rep{width:100%%;border-collapse:collapse;font-size:12.5px}
.pg .pg-rep th{font-size:11px;color:var(--t3);font-weight:600;text-align:right;
padding:4px 6px;border-bottom:1px solid var(--line)}
.pg .pg-rep th small{display:block;font-weight:400}
.pg .pg-rep th:first-child{text-align:left}
.pg .pg-rep td{padding:5px 6px;border-bottom:1px solid var(--line);text-align:right;
font-variant-numeric:tabular-nums;white-space:nowrap}
.pg .pg-rep td:first-child{text-align:left;color:var(--t2);white-space:normal}
.pg .pg-rep td:nth-child(2){font-weight:600;color:var(--t1)}
.pg .pg-rep td:nth-child(3){color:var(--t3)}
.pg .pg-rsec{font-size:12px;font-weight:600;color:var(--t2);margin:2px 0 8px}
.pg .pg-rsec span{font-weight:400;color:var(--t3);margin-left:6px}
.pg .pg-lanes{margin-bottom:16px}
.pg .pg-lane{display:grid;grid-template-columns:150px minmax(0,1fr);align-items:center;
gap:8px;height:24px}
.pg .pg-lane .l{font-size:12px;color:var(--t2);display:flex;justify-content:space-between;
gap:6px;white-space:nowrap;overflow:hidden}
.pg .pg-lane .l em{font-style:normal;color:var(--t3);font-variant-numeric:tabular-nums}
.pg .pg-lane .b{position:relative;height:14px;background:var(--s2);border-radius:3px}
.pg .pg-lane .b i{position:absolute;top:0;bottom:0;border-radius:2px}
.pg .pg-lane.ax{height:18px}
.pg .pg-lane.ax .b{background:none;height:16px}
.pg .pg-lane.ax .b span{position:absolute;top:2px;transform:translateX(-50%%);
font-size:10px;color:var(--t3)}
.pg .pg-nowl{position:absolute;top:-3px;width:2px;height:9px;margin-left:-1px;
background:%(crit)s}
.pg .pg-list{width:100%%;border-collapse:collapse;font-size:12.5px}
.pg .pg-list th{text-align:left;font-size:11px;color:var(--t3);font-weight:600;
padding:4px 6px;border-bottom:1px solid var(--line)}
.pg .pg-list td{padding:5px 6px;border-bottom:1px solid var(--line);vertical-align:top;
color:var(--t1)}
.pg .pg-list td b{color:var(--t1)}
.pg .pg-list td.t{white-space:nowrap;font-variant-numeric:tabular-nums}
.pg .pg-list td.t i{display:inline-block;width:8px;height:8px;border-radius:2px;
margin-right:6px}
.pg .pg-list td.n{white-space:nowrap;color:var(--t2)}
.pg .pg-list td span{color:var(--t3);font-size:11.5px}
.pg .pg-hours{display:flex;align-items:flex-end;gap:3px;height:150px;
margin-bottom:18px}
.pg .pg-hours .c{flex:1;position:relative;height:100%%}
.pg .pg-hours .c span{position:absolute;left:0;right:0;bottom:0;border-radius:3px 3px 0 0}
.pg .pg-hours .c .in{background:var(--line)}
.pg .pg-hours .c .d{background:%(computer)s}
.pg .pg-hours .c b{position:absolute;left:50%%;width:9px;height:9px;margin:0 0 -5px -5px;
border-radius:50%%;background:var(--t1);border:2px solid var(--s1)}
.pg .pg-hours .c small{position:absolute;bottom:-17px;left:0;right:0;text-align:center;
font-size:10px;color:var(--t3)}
.pg .pg-hkey{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:var(--t3)}
.pg .pg-hkey i{display:inline-block;width:10px;height:10px;border-radius:2px;
margin-right:5px;vertical-align:-1px}
.pg .pg-hkey b{display:inline-block;width:8px;height:8px;border-radius:50%%;
background:var(--t1);margin-right:5px}
.pg .pg-empty{font-size:12.5px;color:var(--t3);padding:10px 0}
.pg .pg-rfoot{font-size:11px;color:var(--t3);margin-top:12px;border-top:1px solid var(--line);
padding-top:8px}
@media (max-width:760px){
.pg .pg-rgrid{grid-template-columns:minmax(0,1fr)}
.pg .pg-lane{grid-template-columns:104px minmax(0,1fr)}
.pg .pg-lane .l em{display:none}
.pg .pg-rhead .big{align-items:flex-start;width:100%%}
}
.pg .pg-vs{display:flex;flex-direction:column;align-items:flex-end;text-align:right}
.pg .pg-vs b{font-size:14px;font-variant-numeric:tabular-nums}
.pg .pg-vs b.up{color:%(desk)s}
.pg .pg-vs b.down{color:%(crit)s}
.pg .pg-vs b.same{color:var(--t2)}
.pg .pg-row.gone .pg-who b,.pg .pg-row.out .pg-who b{color:var(--t2)}
@media (max-width:760px){
.pg .pg-board{padding:4px 12px 8px;min-width:0;max-width:100%%;overflow:hidden}
.pg .pg-row{grid-template-columns:minmax(0,1fr) auto;gap:6px 10px}
.pg .pg-row>div{min-width:0}
.pg .pg-row.pg-head{display:none}
.pg .pg-who{grid-column:1;grid-row:1}
.pg .pg-now{grid-column:2;grid-row:1;align-items:flex-end;text-align:right}
.pg .pg-in{grid-column:1;grid-row:2;flex-direction:row;gap:6px;align-items:baseline}
.pg .pg-vs{grid-column:2;grid-row:2;align-items:flex-end}
.pg .pg-desk{grid-column:1 / -1;grid-row:3}
.pg .pg-line{grid-column:1 / -1;grid-row:4}
}
@media (max-width:420px){
.pg .pg-gantt{--gl:118px}
.pg .pg-gname .pg-pill{display:none}
.pg .pg-facts4 b{font-size:14px}
.pg .pg-day{grid-template-columns:40px 1fr 62px;gap:6px}
.pg .pg-axis{left:46px;right:68px}
.pg .pg-big{font-size:24px}
}
</style>"""
