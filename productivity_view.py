"""Productivity, 140-H: every employee on one page, as HTML.

Shamroze, 25 Nov 2026: a score for every employee, to hand in -- "CEO
dekhe to usko acha lage" -- from everything measured: the attendance
machines for everybody, and where a camera sees the employee's own named
desk, the time at it and what was going on there (on the computer, on the
phone, talking).

  productivity  attendance 40%, desk 40%, desk activity 20% -- a part not
                measured hands its weight to the others, so a desk no camera
                sees is the attendance score alone, never a zero
  attendance    attendance_view.score: hours in the building of a 10-hour
                day, at their own usual hour, days in (machines)
  desk          progress_view.period_score: at the desk of the office day,
                in stretches of an hour+, on time (cameras)
  activity      over the days the desk's activity was read: on the computer
                (70%) and NOT on the phone or talking (30%), as shares of the
                desk time; a desk whose camera never sees a screen is "not
                readable", not zero

Time in the building and at the desk, and what the camera saw there --
never the worth of the work (CLAUDE.md: "at the desk", never
"productive"). No Streamlit, no OpenCV (the hosted page has neither):
rows in, HTML out. Names, IDs and directory-photo icons only where the
caller passes them (cloud_names); never a camera picture.
"""
from collections import defaultdict
from datetime import datetime

import attendance_view as av
import progress_view as pv
from overview import css, esc

WEIGHTS = (("attendance", 0.4), ("desk", 0.4), ("activity", 0.2))
ACT_DAYS = 7
# Workforce staff (Shamroze, 26 Nov: "janitorial, office boys ... desk pe
# baithte nahi -- unko alag section mein, alag tarah se measure"): by the
# roster's designation, a word in it -> the group they are compared within.
WORKFORCE = (("janitor", "Janitorial"), ("office boy", "Office boys"),
             ("gate keeper", "Gate and security"),
             ("security supervisor", "Gate and security"),
             ("guard", "Gate and security"), ("valet", "Valet"),
             ("driver", "Valet"), ("rider", "Valet"),
             ("technician", "Technicians"), ("electrician", "Technicians"),
             ("plumber", "Technicians"), ("cleaner", "Janitorial"),
             ("housekeep", "Janitorial"), ("tea boy", "Office boys"),
             ("gardener", "Janitorial"))


def crew_group(role):
    """The workforce group a designation belongs to, or None (desk staff)."""
    r = str(role or "").lower()
    return next((g for w, g in WORKFORCE if w in r), None)


def _key(eid):
    return str(eid or "").strip().lstrip("0") or "0"


def activity(p, days=ACT_DAYS):
    """{computer, talk_phone (% of desk time), phone_min, talking_min (a
    day), score, days} over the last `days` days the desk's activity was
    read; None when never read, or when the camera never saw a screen there
    (then "on the computer" cannot be told from "at the desk")."""
    recs = [r for r in p.get("history") or []
            if r.get("computer_min") is not None
            and (r.get("desk_min") or 0) > 0][-days:]
    if not recs:
        return None
    desk = sum(float(r["desk_min"]) for r in recs)
    comp = sum(float(r.get("computer_min") or 0) for r in recs)
    phone = sum(float(r.get("phone_min") or 0) for r in recs)
    talk = sum(float(r.get("talking_min") or 0) for r in recs)
    if comp <= 0 or desk <= 0:
        return None
    c = min(1.0, comp / desk)
    t = min(1.0, (phone + talk) / desk)
    return {"computer": 100.0 * c, "talk_phone": 100.0 * t,
            "phone": 100.0 * min(1.0, phone / desk),
            "talking": 100.0 * min(1.0, talk / desk),
            "phone_min": phone / len(recs), "talking_min": talk / len(recs),
            "score": 100.0 * (0.7 * c + 0.3 * (1.0 - t)), "days": len(recs)}


def productivity(att, desk, act):
    """The weighted mean of the parts measured; None with none."""
    got = [(v, w) for (k, w), v in zip(WEIGHTS, (att, desk, act))
           if v is not None]
    if not got:
        return None
    return int(round(sum(v * w for v, w in got) / sum(w for _, w in got)))


def camera_attendance(rows, people, now=None):
    """The machines' rows carried on by the cameras (27 Nov, Shamroze:
    "attendance to face se khud pehchane na -- ye to bas data train karne
    ke liye"): HR's export ends on a day (25 Nov, 12:21); after it, an
    employee whose desk is named is still seen -- the desk camera's first
    and last sight of them each day (the board's history) stands in for
    the first IN and last OUT. Days the export has are never touched; a
    camera day says so (`source: "camera"`). Returns new rows."""
    import pandas as pd
    end = max((d for r in rows or [] for d in (r.get("days") or {})),
              default=None)
    if end is None:
        return rows
    today = (now.strftime("%Y-%m-%d") if now is not None
             else datetime.now().strftime("%Y-%m-%d"))
    board = {_key(p.get("employee_id")): p for p in people or []
             if p.get("employee_id")}
    watched = sorted({h["day"] for p in board.values()
                      for h in p.get("history") or []
                      if end < h["day"] < today
                      and pd.Timestamp(h["day"]).dayofweek < 5})
    out = []
    for r in rows or []:
        p = board.get(_key(r["eid"]))
        extra = {}
        for h in (p or {}).get("history") or []:
            if h["day"] in watched and h.get("first") is not None \
                    and h.get("last") is not None:
                extra[h["day"]] = {
                    "first_in": pd.Timestamp(h["first"]),
                    "last_out": pd.Timestamp(h["last"]),
                    "inside_min": float(h.get("span_min") or 0.0),
                    "closed": True, "outings": [], "source": "camera"}
        if not p:
            out.append(r)
            continue
        # a named desk the cameras watched on a day and never saw them at:
        # a day out (counted in `of`, not in days_in)
        days = dict(r.get("days") or {}, **extra)
        work = [s for d, s in days.items() if pd.Timestamp(d).dayofweek < 5
                and s.get("first_in") is not None]
        ins = sorted(s["first_in"].hour + s["first_in"].minute / 60.0
                     for s in work)
        outs = sorted(s["last_out"].hour + s["last_out"].minute / 60.0
                      for s in work if s.get("last_out") is not None)
        closed = [s for s in work if s.get("closed", True)
                  and s.get("inside_min")]
        out.append(dict(
            r, days=days, days_in=(r.get("days_in") or 0) + len(extra),
            of=(r.get("of") or 0) + len(watched),
            usual_in=ins[len(ins) // 2] if ins else r.get("usual_in"),
            usual_out=outs[len(outs) // 2] if outs else r.get("usual_out"),
            inside_h=(sum(s["inside_min"] for s in closed) / 60.0
                      / len(closed)) if closed else r.get("inside_h"),
            camera_days=len(extra)))
    return out


def employees(rows, roster, people=None, hours=(10.0, 20.0), now=None,
              photos=None, campus="140-H"):
    """One dict per employee: every attendance row of the directory, and
    any board employee with a desk score the machines never saw. `campus`
    is the campus they belong to (27 Nov: 141-C/D too), carried on each.
    After HR's export ends, a named desk's camera carries their days on
    (camera_attendance)."""
    rows = camera_attendance(rows, people, now)
    board = {}
    for p in people or []:
        eid = p.get("employee_id")
        if eid:
            board[_key(eid)] = p
    photos = photos or {}
    out, seen = [], set()

    def one(eid, ro, r, p):
        e = _one(eid, ro, r, p)
        crew = crew_group(e["role"])
        if crew:
            # compared within their own kind of work, apart from the desks
            e.update(staff="workforce", home_dept=e["dept"], dept=crew)
        else:
            e.update(staff="office", home_dept=e["dept"])
        e["campus"] = campus
        return e

    def _one(eid, ro, r, p):
        att = av.score(r) if r else None
        d = pv.period_score(p, hours[0], hours[1], now) if p else None
        a = activity(p) if p and d else None
        ds = int(round(d["score"])) if d else None
        ac = int(round(a["score"])) if a else None
        return {
            "eid": eid, "id": ro.get("employee_id") or eid,
            "name": ro.get("name") or "Code %s" % eid,
            "role": ro.get("designation") or "",
            "dept": ro.get("department") or "Other",
            "bu": ro.get("project") or "Other",
            "photo": photos.get(eid) or ro.get("photo") or "",
            "days": (r or {}).get("days") or {}, "board": p,
            "attendance": att, "desk": ds, "activity": ac,
            "desk_parts": d["parts"] if d else None,
            "desk_days": d["days"] if d else 0, "act": a,
            "productivity": productivity(att, ds, ac),
            "days_in": r["days_in"] if r else None,
            "of": r["of"] if r else None,
            "usual_in": r["usual_in"] if r else None,
            "usual_out": r["usual_out"] if r else None,
            "hours": r["inside_h"] if r else None,
            "measured": (("desk camera + activity" if ac is not None else
                          "desk camera" if ds is not None else "machines")
                         + (", %d day%s by camera after the export" % (
                             r["camera_days"],
                             "" if r["camera_days"] == 1 else "s")
                            if r.get("camera_days") else ""))
            if r else "desk camera only"}
    for r in rows or []:
        eid = _key(r["eid"])
        if not r.get("days_in") and not r.get("days"):
            # (25 Nov: somebody in only on a day the export cut short has
            # no whole day yet -- listed, their score not known yet)
            continue
        out.append(one(eid, roster.get(r["eid"], {}) or roster.get(eid, {}),
                       r, board.get(eid)))
        seen.add(eid)
    for eid, p in board.items():
        if eid in seen:
            continue
        # a board employee the machines never saw at this campus: their
        # role says "designation, department[, project]" -- the board's own
        # "department" is the room, not a department
        role = [x.strip() for x in str(p.get("role") or "").split(",")]
        e = one(eid, {"employee_id": p.get("employee_id"),
                      "name": p.get("name"), "designation": role[0],
                      "department": role[1] if len(role) > 1 and role[1]
                      else "Other",
                      "project": role[2] if len(role) > 2 and role[2]
                      else "Other",
                      "photo": p.get("photo")}, None, p)
        if e["productivity"] is not None:
            out.append(e)
    return out


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def _hhmm(h):
    if h is None:
        return "&ndash;"
    m = int(round(h * 60))
    return "%02d:%02d" % ((m // 60) % 24, m % 60)


def _bars(values, labels, w=520, h=170):
    """A histogram: thin rounded bars, the count over each."""
    top = float(max(values) or 1)
    n = len(values)
    gap, pad, base, top_pad = 6, 6, h - 24, 16
    bw = (w - 2 * pad - gap * (n - 1)) / float(n)
    out = ['<svg viewBox="0 0 %d %d" width="100%%" role="img">' % (w, h),
           '<line x1="0" x2="%d" y1="%d" y2="%d" style="stroke:var(--line)"/>'
           % (w, base, base)]
    for i, v in enumerate(values):
        x = pad + i * (bw + gap)
        bh = (base - top_pad) * v / top
        if v:
            r = min(4.0, bw / 2, bh)
            out.append('<path d="M%.1f %d v-%.1f q0 -%.1f %.1f -%.1f h%.1f '
                       'q%.1f 0 %.1f %.1f v%.1f z" style="fill:var(--accent)"/>'
                       % (x, base, bh - r, r, r, r, bw - 2 * r, r, r, r,
                          bh - r))
            out.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                       'style="font-size:11px;fill:var(--t2)">%d</text>'
                       % (x + bw / 2, base - bh - 4, v))
        out.append('<text x="%.1f" y="%d" text-anchor="middle" '
                   'style="font-size:10.5px;fill:var(--t3)">%s</text>'
                   % (x + bw / 2, h - 6, labels[i]))
    out.append("</svg>")
    return "".join(out)


_CSS = """<style>
.pr .pr-hero{display:flex;justify-content:space-between;align-items:flex-end;
flex-wrap:wrap;gap:10px;margin:8px 0 14px}
.pr .pr-hero h2{font-size:26px;margin:0;letter-spacing:-.02em}
.pr .pr-hero p{margin:4px 0 0;color:var(--t3);font-size:13px;max-width:760px}
.pr .pr-badge{font-size:12px;color:var(--t2);border:1px solid var(--line);
border-radius:99px;padding:5px 12px;white-space:nowrap}
.pr .pr-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
gap:12px;margin-bottom:14px}
.pr .pr-kpis .ec-kpi{padding:14px 16px}
.pr .pr-two{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
gap:14px;margin-bottom:14px}
.pr .pr-two .ec-card,.pr .pr-card{padding:14px 16px}
.pr h4{margin:0;font-size:14px}
.pr .pr-sub{font-size:12px;color:var(--t3);margin:2px 0 8px}
.pr .pr-cov{display:flex;height:22px;border-radius:7px;overflow:hidden;gap:2px;
margin:6px 0}
.pr .pr-cov i{display:block;height:100%}
.pr .pr-lg{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--t2)}
.pr .pr-lg b{display:inline-block;width:10px;height:10px;border-radius:3px;
margin-right:5px;vertical-align:-1px}
.pr table{width:100%;border-collapse:collapse;font-size:12.5px;
font-variant-numeric:tabular-nums}
.pr th{position:sticky;top:0;background:var(--s1);font-size:11px;
color:var(--t3);font-weight:650;text-align:right;padding:8px;
border-bottom:1px solid var(--line);white-space:nowrap;z-index:1}
.pr td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--line);
white-space:nowrap;vertical-align:middle}
.pr th.l,.pr td.l{text-align:left;white-space:normal}
.pr td .sub{display:block;font-size:11px;color:var(--t3)}
.pr td.ph{width:38px;padding:4px 6px}
.pr td.ph img,.pr .nop{width:30px;height:30px;border-radius:50%;display:block;
object-fit:cover;background:var(--s2)}
.pr td.sc{text-align:left;min-width:120px}
.pr td.sc b{display:inline-block;min-width:24px;text-align:right;font-size:14px}
.pr td.sc i{display:inline-block;height:6px;border-radius:4px;
background:var(--accent);margin-left:8px;vertical-align:middle}
.pr .na{color:var(--t3);font-size:11px}
.pr tr.dh td{text-align:left;font-weight:700;font-size:13px;padding-top:14px;
border-bottom:2px solid var(--t2)}
.pr tr.dh td span{font-weight:400;color:var(--t3);font-size:12px;margin-left:6px}
.pr .pr-wrap{max-height:720px;overflow:auto;border-radius:12px}
.pr .hb{position:relative;height:18px;background:var(--s2);border-radius:5px;
min-width:160px}
.pr .hb i{position:absolute;left:0;top:0;bottom:0;border-radius:5px;
background:var(--accent);opacity:.75}
.pr .hb span{position:absolute;left:8px;top:1px;font-size:11.5px;font-weight:700}
.pr .pr-top{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
gap:10px}
.pr .pr-top .ec-card{display:flex;gap:10px;align-items:center;padding:10px 12px}
.pr .pr-top img,.pr .pr-top .nop{width:44px;height:44px;border-radius:50%;
object-fit:cover}
.pr .pr-top b{display:block;font-size:13px}
.pr .pr-top span{display:block;font-size:11.5px;color:var(--t3)}
.pr .pr-top em{font-style:normal;font-weight:800;font-size:18px;
color:var(--accent);margin-left:auto}
.pr .pr-note{font-size:12px;color:var(--t3);line-height:1.6;margin-top:10px}
.pr .pr-note b{color:var(--t2)}
.pr .pr-kpis.k4{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
gap:10px;margin-bottom:10px}
.pr .pr-kpis.k4 .ec-kpi{padding:10px 14px}
.pr .pr-kpis.k4 .ec-kpi .v{font-size:22px;margin-top:2px}
.pr .pr-hero.sm{margin:2px 0 10px}
.pr .pr-hero.sm h2{font-size:21px}
.pr .pr-dc{padding:12px 14px;margin-bottom:6px;border-radius:14px}
.pr .pr-dc .nm{font-size:13.5px;font-weight:700;line-height:1.3;
min-height:2.6em;display:-webkit-box;-webkit-line-clamp:2;
-webkit-box-orient:vertical;overflow:hidden}
.pr .pr-dc .row{display:flex;align-items:baseline;gap:6px;margin-top:4px}
.pr .pr-dc .row b{font-size:30px;line-height:1;color:var(--accent);
letter-spacing:-.02em}
.pr .pr-dc .row span{font-size:11.5px;color:var(--t3)}
.pr .pr-dc .bar{height:6px;border-radius:4px;background:var(--s2);margin:8px 0}
.pr .pr-dc .bar i{display:block;height:100%;border-radius:4px;
background:var(--accent)}
.pr .pr-dc .ct{font-size:12px;color:var(--t2)}
.pr .pr-dc .ct b{color:var(--t1)}
.pr .pr-dt{max-height:640px;padding:0}
.pr .pr-dt td.rk{color:var(--t3);width:28px}
.pr .pr-dt td{padding:5px 8px}
</style>"""


def _styles(mode, *extra):
    """The style blocks, each its own block for Streamlit's markdown: two
    <style>s on one line end the first block at its </style> and leave
    the second open, and the page after it becomes the style's text (25
    Nov: the Productivity tiles came out unstyled, the heading gone)."""
    return "\n\n".join([css(mode), _CSS] + list(extra)) + "\n\n"


def _photo(e, cls=""):
    return ('<img src="%s" alt="">' % esc(e["photo"])) if e.get("photo") \
        else '<i class="nop"></i>'


def summary_html(mode, emps, days, made="", visitors=0):
    """The top of the page: the campus in figures and pictures.
    `visitors`: employees through its machines who punch mostly at another
    campus -- left out, and said so."""
    if not emps:
        return ""
    n = len(emps)
    prod = [e["productivity"] for e in emps if e["productivity"] is not None]
    with_desk = [e for e in emps if e["desk"] is not None]
    with_act = [e for e in emps if e["activity"] is not None]
    ins = sorted(e["usual_in"] for e in emps if e["usual_in"] is not None)
    pres = _mean([e["days_in"] / float(e["of"]) for e in emps
                  if e.get("of")])
    comp = _mean([e["act"]["computer"] for e in with_act])
    tiles = [
        ("Employees scored", "%d" % n, "100%% of 140-H's employees%s" % (
            " &middot; %d from 141-D left out" % visitors if visitors
            else "")),
        ("Presence, average", "%d" % round(_mean(prod)) if prod else "-",
         "of 100 &middot; attendance, desk, activity"),
        ("In the building, a day", "%.1f h" % (_mean([e["hours"] for e in emps])
                                                or 0),
         "IN to OUT, days that end on an OUT"),
        ("Usual arrival", _hhmm(ins[len(ins) // 2]) if ins else "-",
         "the middle employee's first IN"),
        ("Days present", "%d%%" % round(100 * pres) if pres is not None
         else "-", "of the working days"),
        ("Desk measured by camera", "%d" % len(with_desk),
         "their own named desk in a camera"),
        ("On the computer", "%d%%" % round(comp) if comp is not None else "-",
         "of desk time, where the screen is seen (%d)" % len(with_act)),
        ("Attendance score, average", "%d" % round(_mean(
            [e["attendance"] for e in emps]) or 0), "machines, everybody")]
    bins = [0] * 10
    for v in prod:
        bins[min(9, int(v // 10))] += 1
    arr = defaultdict(int)
    for t in ins:
        arr[min(max(int(t) - 7, 0), 9)] += 1
    n_desk, n_act = len(with_desk), len(with_act)
    cov = [("var(--accent)", n_act, "desk camera + activity"),
           ("var(--accent)", n_desk - n_act, "desk camera"),
           ("var(--line2)", n - n_desk, "machines only")]
    dept = group_rows(emps, "dept")
    units = group_rows(emps, "bu")
    top = sorted(with_desk, key=lambda e: -e["productivity"])[:8]
    return "".join([
        _styles(mode), '<div class="ec pr">',
        '<div class="pr-hero"><div><h2>Presence &middot; 140-H</h2><p>'
        'Every 140-H employee (most of their punches at its machines), %s to '
        '%s: time in the building from the attendance machines, and where a '
        'camera sees their own desk, the time at it and what went on there.'
        '</p></div>'
        '<span class="pr-badge">%d employees &middot; %s</span></div>'
        % (esc(days[0]) if days else "", esc(days[-1]) if days else "", n,
           esc(made)),
        '<div class="pr-kpis">%s</div>' % "".join(
            '<div class="ec-card ec-kpi"><div class="k">%s</div><div class="v">'
            '%s</div><div class="s">%s</div></div>' % (k, v, s)
            for k, v, s in tiles),
        '<div class="pr-two"><div class="ec-card"><h4>Presence score, '
        'every employee</h4><div class="pr-sub">employees per band of 10 '
        'points</div>%s</div>' % _bars(bins, ["%d" % (10 * i)
                                               for i in range(10)]),
        '<div class="ec-card"><h4>When people usually arrive</h4><div '
        'class="pr-sub">employees by the hour of their usual first IN '
        '&mdash; later shifts too</div>%s</div></div>' % _bars(
            [arr[i] for i in range(10)],
            ["%02d" % (7 + i) if i < 9 else "16+" for i in range(10)]),
        '<div class="ec-card pr-card"><h4>How each employee is measured</h4>'
        '<div class="pr-cov">%s</div><div class="pr-lg">%s</div></div>' % (
            "".join('<i style="width:%.2f%%;background:%s;opacity:%s"></i>'
                    % (100.0 * k / n, c, "1" if i == 0 else ".55" if i == 1
                       else "1") for i, (c, k, _) in enumerate(cov) if k),
            "".join('<span><b style="background:%s;opacity:%s"></b>%s: %d'
                    '</span>' % (c, "1" if i == 0 else ".55" if i == 1
                                 else "1", lab, k)
                    for i, (c, k, lab) in enumerate(cov))),
        '<div class="ec-h"><span class="t">Highest presence, measured at '
        'the desk too</span></div><div class="pr-top">%s</div>' % "".join(
            '<div class="ec-card">%s<div><b>%s</b><span>%s</span></div><em>%d'
            '</em></div>' % (_photo(e), esc(e["name"]), esc(e["dept"]),
                             e["productivity"]) for e in top),
        (_group_table("Business units", "presence averaged over each "
                      "business unit's employees", "Business unit", units)
         if len(units) > 1 else ""),
        _group_table("Departments", "presence averaged over each "
                     "department's employees", "Department", dept),
        '</div>'])


def _kpis(tiles):
    return '<div class="pr-kpis k4">%s</div>' % "".join(
        '<div class="ec-card ec-kpi"><div class="k">%s</div><div class="v">%s'
        '</div><div class="s">%s</div></div>' % t for t in tiles)


STAR = "&#9733;"


def screen_unseen(e, days=ACT_DAYS):
    """Their desk's activity was read, but no screen was ever seen there
    (the camera's angle): "on the computer" cannot be told at that desk,
    so the activity part is as measured as it can be."""
    recs = [r for r in (e.get("board") or {}).get("history") or []
            if r.get("computer_min") is not None
            and (r.get("desk_min") or 0) > 0][-days:]
    return bool(recs) and sum(float(r.get("computer_min") or 0)
                              for r in recs) <= 0


# Recorders the pass reads at 640x360 (rooms.yaml stream "sub"; their AC
# calibrations are in those pixels): no screen or phone can be made out at
# their desks -- 27 Nov, every activity row of nvr4's (the Basement's)
# desks was "desk" or "away".
LOW_RES = ("nvr1", "nvr4")


def activity_untold(e):
    """Why desk activity cannot be told at their desk: "low" (a camera read
    at low resolution), "screen" (no screen ever in its view), else ""."""
    if str((e.get("board") or {}).get("recorder") or "") in LOW_RES:
        return "low"
    return "screen" if screen_unseen(e) else ""


# 27 Nov night (Shamroze, on a starred card with 1 h at the desk and 8 h
# "in the building, place not seen": "ye result not good"): the desk must
# show them for this much of their time in the building, on average, for
# the star -- far less, and the desk named for them is in doubt (on 26 Nov
# the desk-camera staff were at their desks 55% of it; 9 under 30%).
DESK_SEEN_MIN = 0.30
# 28 Nov (Shamroze, again on a starred card: "8 hour nazar hi nahi aya ...
# bs 1 hour"): both shares are now of their time in the building BY THE
# MACHINES. The board's desk_pct is of the camera's own first-to-last
# sighting, so somebody seen at their desk only from 12:00 to 13:00 was
# "100% at the desk". And the cameras must place them -- the desk, meeting
# rooms, the cafe, the other campus ... -- for at least half that time.
# On 28 Nov this kept 38 of 70 stars at 140-H and 11 of 32 at 141-C/D.
SEEN_MIN = 0.50
DAY_MIN = 120.0           # a day shorter than this in the building: skipped
_NOT_PLACED = ("inside", "out", "unknown", "campus", "desk")


def outside_min(s):
    """Minutes out of the building between a day's first IN and last OUT
    (the machines' outings)."""
    tot = 0.0
    for o in s.get("outings") or []:
        try:
            a, b = (datetime.fromisoformat(x) if isinstance(x, str) else x
                    for x in o[:2])
            tot += max(0.0, (b - a).total_seconds() / 60.0)
        except (TypeError, ValueError, AttributeError):
            continue
    return tot


def day_shares(e, days=ACT_DAYS, minutes=False):
    """[(at the desk, placed by a camera)] as shares (0-1) of each of
    their last days in the building by the machines -- whole days the board
    has a desk record for and the machines closed (every IN met an OUT).
    `minutes`: [(desk, placed, in the building)] in minutes instead."""
    return [(desk, seen, inside) if minutes else
            (desk / inside, seen / inside)
            for _, desk, seen, inside, _ in _day_minutes(e, days)]


def _day_minutes(e, days=ACT_DAYS):
    """Each of their last whole machine days (see day_shares) as (day,
    at the desk, placed by a camera, in the building, places_day's totals
    or {}) in minutes."""
    p = e.get("board") or {}
    placed = p.get("places_days") or {}
    for h in [r for r in p.get("history") or []
              if r.get("desk_min") is not None][-days:]:
        day = h.get("day")
        s = (e.get("days") or {}).get(day) or {}
        inside = float(s.get("inside_min") or 0.0)
        if day == e.get("_cut") or not s.get("closed", True) \
                or inside < DAY_MIN:
            continue
        pl = placed.get(day) or {}
        desk = max(float(h["desk_min"]), float(pl.get("desk") or 0.0))
        other = sum(float(v or 0.0) for k, v in pl.items()
                    if k not in _NOT_PLACED)
        campus = max(0.0, float(pl.get("campus") or 0.0) - outside_min(s))
        yield (day, min(inside, desk), min(inside, desk + other + campus),
               inside, pl)


# Why the rest of their time in the building was not seen (28 Nov, the
# master brief: "every not-seen case has a state/reason"), from what
# places_day already tells apart -- in this order, each capped by what is
# left: their desk camera watching an empty seat while the machines say
# inside and no camera named them anywhere ("inside": a corridor, a
# restroom, a room without a camera that reads faces); no watching at all
# ("unknown": the desk camera or the loop down, or between passes); and
# what no record covers.
NOT_SEEN = (("desk_empty", "their desk seen empty and no other camera named "
                           "them"),
            ("unwatched", "not watched (the desk camera or the loop was "
                          "down)"),
            ("untracked", "on days before places were tracked (the desk "
                          "only)"),
            ("no_record", "no camera record of the time"))


def not_seen(e, days=ACT_DAYS):
    """The minutes of their time in the building that no camera placed, by
    reason (NOT_SEEN), over the same days as coverage(): {reason:
    minutes}, or None without a whole machine day."""
    out, any_day = {k: 0.0 for k, _ in NOT_SEEN}, False
    for _, _, seen, inside, pl in _day_minutes(e, days):
        any_day = True
        rest = max(0.0, inside - seen)
        if not pl:                   # places_day had not the day (26 Nov on)
            out["untracked"] += rest
            continue
        empty = min(rest, float(pl.get("inside") or 0.0))
        unwatched = min(rest - empty, float(pl.get("unknown") or 0.0))
        out["desk_empty"] += empty
        out["unwatched"] += unwatched
        out["no_record"] += rest - empty - unwatched
    return out if any_day else None


def desk_seen(e, days=ACT_DAYS):
    """Their mean share of their time in the building at their own desk,
    over their last days (0-1), or None: of the machines' time where they
    have it, else of the camera's own first-to-last sighting."""
    sh = day_shares(e, days)
    if sh:
        return sum(a for a, _ in sh) / len(sh)
    vals = [float(r["desk_pct"]) for r in (e.get("board") or {}).get(
        "history") or [] if r.get("desk_pct") is not None][-days:]
    return sum(vals) / len(vals) if vals else None


def day_seen(e, days=ACT_DAYS):
    """Their mean share of their time in the building (by the machines)
    that a camera placed them somewhere -- the desk or a known place --
    over their last days (0-1), or None without a whole machine day."""
    sh = day_shares(e, days)
    return sum(b for _, b in sh) / len(sh) if sh else None


def coverage(e, days=ACT_DAYS):
    """Observation coverage over their last whole machine days, as
    minutes (28 Nov, the master brief: "display numerator, denominator,
    time window"): {"seen", "inside", "days"} or None."""
    sh = day_shares(e, days, minutes=True)
    if not sh:
        return None
    return {"seen": sum(s for _, s, _ in sh),
            "inside": sum(i for _, _, i in sh), "days": len(sh)}


def complete(e):
    """Every part of an office employee's productivity that the cameras
    can measure, measured -- the attendance machines, their own desk in a
    camera (and it shows them for a fair part of their day: DESK_SEEN_MIN),
    the cameras placing them for most of it (SEEN_MIN), and what went on
    at the desk (desk activity; where the camera cannot tell it -- no
    screen in view, or a low-resolution camera -- that part is not waited
    for). Shamroze, 27 Nov: "jin employees ki productivity poori ho jaye,
    un ke report card par star"."""
    seen, placed = desk_seen(e), day_seen(e)
    return (e.get("staff") != "workforce"
            and e.get("attendance") is not None
            and e.get("desk") is not None
            and seen is not None and seen >= DESK_SEEN_MIN
            and placed is not None and placed >= SEEN_MIN
            and (e.get("activity") is not None or bool(activity_untold(e))))


def missing(e):
    """What is not measured yet, in words ("" when complete)."""
    if e.get("staff") == "workforce" or complete(e):
        return ""
    out = []
    if e.get("attendance") is None:
        out.append("attendance")
    seen, placed = desk_seen(e), day_seen(e)
    if e.get("desk") is None:
        out.append("desk camera (their desk not named in a camera yet)")
    elif seen is None or seen < DESK_SEEN_MIN:
        out.append("most of their day: the desk named for them shows them "
                   "%s of their time in the building -- being checked" % (
                       "%d%%" % round(100 * seen) if seen is not None
                       else "too little"))
    elif placed is None:
        out.append("a whole day by the machines (no day with every IN "
                   "matched by an OUT yet)")
    elif placed < SEEN_MIN:
        out.append("most of their day: the cameras placed them for %d%% of "
                   "their time in the building, under half -- the rest is "
                   "\"place not seen\"" % round(100 * placed))
    elif e.get("activity") is None:
        out.append("desk activity (not read yet)")
    return ", ".join(out)


def star_html(e):
    """The gold star beside a complete employee's name, else nothing."""
    return ('<span title="Fully observed: attendance, desk camera and desk '
            'activity measured, and the cameras placed them for at least '
            'half of their time in the building" aria-label="complete" '
            'style="color:'
            '#d99a00;margin-left:.3em">%s</span>' % STAR) if complete(e) \
        else ""


def top_html(mode, emps, days, made="", visitors=0, crew=0, campus="140-H",
             other="141-D"):
    """The page's short top (Shamroze, 25 Nov night: "chhota banao ... itna
    lamba kyun"): a line of title and four figures -- employees monitored,
    the average productivity, departments, desks a camera sees. `campus`
    the page's, `other` where its visitors mostly punch (27 Nov: 141-C/D's
    page too)."""
    if not emps:
        return ""
    n = len(emps)
    prod = _mean([e["productivity"] for e in emps])
    n_desk = sum(1 for e in emps if e["desk"] is not None)
    n_dept = len({e["dept"] for e in emps})
    c = esc(campus)
    return "".join([
        _styles(mode), '<div class="ec pr">',
        '<div class="pr-hero sm"><div><h2>Presence &middot; %s</h2>'
        '<p><b>Open a department, then a person, for their report card.'
        '</b> %s to %s &middot; %s</p></div><span class="pr-badge">'
        '%s</span></div>' % (
            c, esc(days[0]) if days else "", esc(days[-1]) if days else "",
            "attendance machines for everybody, the desk camera where it "
            "sees their own desk" if n_desk else
            "the attendance machines alone: no desk here is named in a "
            "camera yet, so the score is attendance only &mdash; higher than "
            "a campus measured at the desk too, not to be set beside it",
            esc(made)),
        _kpis([
            ("Employees monitored", "%d" % n, "%s%s" % (
                "+ %d workforce staff apart = all %d of %s" % (
                    crew, n + crew, c) if crew else "100% of " + c,
                " &middot; %d visitors from %s left out" % (visitors,
                                                            esc(other))
                if visitors else "")),
            ("Presence, average", "%d" % round(prod) if prod is not None
             else "-", "of 100"),
            ("Departments", "%d" % n_dept, "open one for its people"),
            ("Desks seen by camera", "%d" % n_desk,
             ("%s %d complete (attendance, desk and activity) &middot; the "
              "rest by the machines alone" % (
                  STAR, sum(1 for e in emps if complete(e))))
             if n_desk else "none named here yet: the machines alone")]),
        '</div>'])


def dept_cards(emps):
    """[(department, its employees, flash card html)], the biggest first:
    the department's productivity, how many of its employees are
    monitored and how many of their desks a camera sees."""
    out = []
    for name, es, _ in group_rows(emps, "dept"):
        p = _mean([e["productivity"] for e in es])
        seen = sum(1 for e in es if e["desk"] is not None)
        out.append((name, es,
                    '<div class="ec pr"><div class="ec-card pr-dc"><div '
                    'class="nm" title="%s">%s</div><div class="row"><b>%s</b>'
                    '<span>presence</span></div><div class="bar"><i '
                    'style="width:%d%%"></i></div><div class="ct"><b>%d</b> '
                    'employee%s monitored &middot; %d desk%s by camera</div>'
                    '</div></div>'
                    % (esc(name), esc(name), "%d" % round(p) if p is not None
                       else "-", round(p or 0), len(es),
                       "" if len(es) == 1 else "s", seen,
                       "" if seen == 1 else "s")))
    return out


def dept_head_html(mode, name, es, emps):
    """The department opened: its report card -- employees monitored, its
    productivity beside 140-H's, attendance, hours, arrival."""
    p = _mean([e["productivity"] for e in es])
    allp = _mean([e["productivity"] for e in emps])
    at = _mean([e["attendance"] for e in es])
    hr = _mean([e["hours"] for e in es])
    ins = sorted(e["usual_in"] for e in es if e["usual_in"] is not None)
    seen = sum(1 for e in es if e["desk"] is not None)
    return "".join([
        _styles(mode), '<div class="ec pr">',
        '<div class="pr-hero sm"><div><h2>%s</h2><p>%d employee%s monitored'
        ' &middot; highest presence first &middot; click a person for '
        'their profile</p></div></div>' % (esc(name), len(es),
                                           "" if len(es) == 1 else "s"),
        _kpis([
            ("Presence", "%d" % round(p) if p is not None else "-",
             "%s average %s" % (esc((es[0].get("campus") if es else None)
                                    or "140-H"),
                                "%d" % round(allp) if allp is not None
                                else "-")),
            ("Employees monitored", "%d" % len(es),
             "%d desk%s seen by camera" % (seen, "" if seen == 1 else "s")),
            ("Attendance score", "%d" % round(at) if at is not None else "-",
             "the machines"),
            ("In the building, a day", "%.1f h" % hr if hr is not None
             else "-", "usual arrival %s" % (_hhmm(ins[len(ins) // 2])
                                             if ins else "-"))]),
        '</div>'])


def dept_table_html(mode, es):
    """The department's people, highest productivity first, in the page's
    own colours (Streamlit's table is dark on the light page -- 25 Nov:
    "ajeeb lag raha hai"): rank, photo, name and role, the productivity
    bar, attendance, desk, activity, days in, the usual in and out."""
    rows = []
    for i, e in enumerate(sorted(es, key=lambda e: -(e["productivity"] or 0)),
                          1):
        p = e["productivity"]
        rows.append(
            '<tr><td class="rk">%d</td><td class="ph">%s</td><td class="l">'
            '<b>%s</b><span class="sub">%s</span></td><td class="l"><div '
            'class="hb"><i style="width:%d%%"></i><span>%s</span></div></td>'
            '<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s&ndash;%s</td>'
            '<td>%s</td></tr>'
            % (i, _photo(e), esc(e["name"]), esc(e["role"]), p or 0,
               "%d" % p if p is not None else "-",
               e["attendance"] if e["attendance"] is not None else "&ndash;",
               e["desk"] if e["desk"] is not None else "&ndash;",
               e["activity"] if e["activity"] is not None else "&ndash;",
               ("%d/%d" % (e["days_in"], e["of"])) if e["days_in"] is not None
               and e.get("of") else "&ndash;",
               _hhmm(e["usual_in"]), _hhmm(e["usual_out"]),
               "%.1f h" % e["hours"] if e["hours"] is not None
               else "&ndash;"))
    return "".join([
        _styles(mode), '<div class="ec pr"><div class="ec-card pr-wrap '
        'pr-dt"><table><thead><tr><th>#</th><th></th><th class="l">Employee'
        '</th><th class="l">Presence</th><th>Attendance</th><th>Desk</th>'
        '<th>Activity</th><th>Days in</th><th>Usual in&ndash;out</th><th>'
        'In the building</th></tr></thead><tbody>%s</tbody></table></div>'
        '<div class="pr-note">Presence = attendance 40%%, desk 40%%, '
        'desk activity 20%%; &ndash; where a part is not measured (its '
        'weight goes to the others).</div></div>' % "".join(rows)])


def group_rows(emps, key):
    """[(name, employees, html row)] grouped by `key` ("dept" or "bu"),
    the biggest first."""
    by = defaultdict(list)
    for e in emps:
        by[e[key]].append(e)
    out = []
    for name, es in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        p = _mean([e["productivity"] for e in es])
        dk = _mean([e["desk"] for e in es])
        at = _mean([e["attendance"] for e in es])
        hr = _mean([e["hours"] for e in es])
        out.append((name, es,
                    '<tr><td class="l"><b>%s</b></td><td>%d</td><td class="l">'
                    '<div class="hb"><i style="width:%d%%"></i><span>%s</span>'
                    '</div></td><td>%s</td><td>%s</td><td>%s</td><td>%d of %d'
                    '</td></tr>'
                    % (esc(name), len(es), round(p or 0), "%d" % round(p)
                       if p is not None else "-",
                       "%d" % round(at) if at is not None else "&ndash;",
                       "%d" % round(dk) if dk is not None else "&ndash;",
                       "%.1f h" % hr if hr is not None else "&ndash;",
                       sum(1 for e in es if e["desk"] is not None), len(es))))
    return out


def _group_table(title, sub, first, rows):
    return ('<div class="ec-h"><span class="t">%s</span><span class="c">%s'
            '</span></div><div class="ec-card"><table><thead><tr><th class="l">'
            '%s</th><th>Employees</th><th class="l">Presence</th>'
            '<th>Attendance</th><th>Desk</th><th>In the building</th>'
            '<th>Desk in a camera</th></tr></thead><tbody>%s</tbody></table>'
            '</div>' % (title, sub, first, "".join(r for _, _, r in rows)))


def _ord(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else
                     {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def profile_html(mode, e, emps):
    """One employee: who, the scores and their parts, where they stand
    among their department's colleagues (a bar each, theirs marked), and
    every day by the machines."""
    mates = sorted([x for x in emps if x["dept"] == e["dept"]
                    and x["productivity"] is not None],
                   key=lambda x: -x["productivity"])
    rank = next((i + 1 for i, x in enumerate(mates) if x["eid"] == e["eid"]),
                None)
    dept_avg = _mean([x["productivity"] for x in mates])
    bu_avg = _mean([x["productivity"] for x in emps if x["bu"] == e["bu"]
                    and x["productivity"] is not None])
    all_avg = _mean([x["productivity"] for x in emps
                     if x["productivity"] is not None])
    d, a = e.get("desk_parts"), e.get("act")

    def tile(k, v, s):
        return ('<div class="ec-card ec-kpi"><div class="k">%s</div><div '
                'class="v">%s</div><div class="s">%s</div></div>'
                % (k, "-" if v is None else "%d" % v, s))
    att_sub = "%s in the building a day &middot; %s/%s days in" % (
        "%.1f h" % e["hours"] if e["hours"] is not None else "hours unknown",
        e["days_in"] if e["days_in"] is not None else "-",
        e["of"] if e["of"] is not None else "-")
    desk_sub = ("at the desk %d%% &middot; focus %d%% &middot; on time %d%%"
                % tuple(round(v or 0) for _, v in d)) if d \
        else "no camera sees their own desk"
    act_sub = ("computer %d%% &middot; phone+talking %d%% of desk time"
               % (round(a["computer"]), round(a["talk_phone"]))) if a \
        else "not read at their desk"
    bars = []
    top = float(max([x["productivity"] for x in mates] or [1]))
    for i, x in enumerate(mates, 1):
        me = x["eid"] == e["eid"]
        bars.append(
            '<div class="pf-bar%s"><span class="n">%d</span><span class="w">'
            '%s</span><span class="b"><i style="width:%.1f%%"></i></span>'
            '<span class="v">%d</span></div>'
            % (" me" if me else "", i, esc(x["name"]),
               100.0 * x["productivity"] / top if top else 0,
               x["productivity"]))
    days_rows = []
    for day in sorted(e.get("days") or {}, reverse=True):
        s = e["days"][day]
        f, o = s.get("first_in"), s.get("last_out")
        outs = s.get("outings") or []
        out_min = sum((b - a_).total_seconds() / 60.0 for a_, b in outs)
        try:
            label = datetime.strptime(day, "%Y-%m-%d").strftime("%a %d %b")
        except ValueError:
            label = day
        days_rows.append(
            '<tr><td class="l" style="white-space:nowrap">%s</td><td>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td></tr>'
            % (esc(label), f.strftime("%H:%M") if f is not None else "&ndash;",
               o.strftime("%H:%M") if o is not None else "&ndash;",
               ("%.1f h" % (s["inside_min"] / 60.0)) if s.get("closed", True)
               and s.get("inside_min") else "&ndash;",
               ("%d, %dm" % (len(outs), out_min)) if outs else "&ndash;"))
    return "".join([
        _styles(mode, _PF_CSS), '<div class="ec pr">',
        '<div class="ec-card pf-head">%s<div><h3>%s</h3><p>%s</p><p class="m">'
        '%s &middot; %s &middot; ID %s</p></div><div class="pf-big"><b>%s</b>'
        '<span>presence</span></div></div>'
        % (_photo(e), esc(e["name"]), esc(e["role"]), esc(e["dept"]),
           esc(e["bu"]), esc(str(e["id"])), e["productivity"]
           if e["productivity"] is not None else "-"),
        '<div class="pr-kpis">%s%s%s%s</div>' % (
            tile("Attendance (machines)", e["attendance"], att_sub),
            tile("Desk (cameras)", e["desk"], desk_sub),
            tile("Activity at the desk", e["activity"], act_sub),
            '<div class="ec-card ec-kpi"><div class="k">Among colleagues</div>'
            '<div class="v">%s</div><div class="s">in %s (%d) &middot; dept '
            'avg %s &middot; BU avg %s &middot; %s %s</div></div>'
            % ((_ord(rank) if rank else "-"), esc(e["dept"]), len(mates),
               "%d" % round(dept_avg) if dept_avg is not None else "-",
               "%d" % round(bu_avg) if bu_avg is not None else "-",
               esc(e.get("campus") or "140-H"),
               "%d" % round(all_avg) if all_avg is not None else "-")),
        '<div class="pr-two"><div class="ec-card"><h4>%s with colleagues in '
        '%s</h4><div class="pr-sub">presence, highest first &mdash; '
        'theirs marked</div><div class="pf-bars">%s</div></div>'
        % (esc(e["name"].split(" ")[0]), esc(e["dept"]), "".join(bars)),
        '<div class="ec-card"><h4>Every day by the attendance machines</h4>'
        '<div class="pr-sub">first IN, last OUT, time in the building, out '
        'and back</div><div class="pf-days"><table><thead><tr><th class="l">'
        'Day</th><th>In</th><th>Out</th><th>In the building</th><th>Out and '
        'back</th></tr></thead><tbody>%s</tbody></table></div></div></div>'
        % ("".join(days_rows) or '<tr><td class="l" colspan="5">No punch at '
           '%s in the export</td></tr>' % esc(e.get("campus") or "140-H")),
        '</div>'])


_PF_CSS = """<style>
.pr .pf-head{display:flex;align-items:center;gap:16px;padding:14px 18px;
margin-bottom:12px}
.pr .pf-head img,.pr .pf-head .nop{width:72px;height:72px;border-radius:50%;
object-fit:cover}
.pr .pf-head h3{margin:0;font-size:20px}
.pr .pf-head p{margin:2px 0 0;color:var(--t2);font-size:13px}
.pr .pf-head p.m{color:var(--t3);font-size:12px}
.pr .pf-big{margin-left:auto;text-align:center}
.pr .pf-big b{display:block;font-size:38px;color:var(--accent);line-height:1}
.pr .pf-big span{font-size:11px;color:var(--t3)}
.pr .pf-bars{max-height:380px;overflow:auto}
.pr .pf-bar{display:grid;grid-template-columns:26px minmax(110px,190px) 1fr 30px;
gap:8px;align-items:center;font-size:12px;padding:3px 0;color:var(--t2)}
.pr .pf-bar .n{color:var(--t3);text-align:right}
.pr .pf-bar .w{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pr .pf-bar .b{background:var(--s2);border-radius:4px;height:12px}
.pr .pf-bar .b i{display:block;height:100%;border-radius:4px;
background:var(--line2)}
.pr .pf-bar .v{text-align:right;font-weight:600}
.pr .pf-bar.me{color:var(--t1);font-weight:700}
.pr .pf-bar.me .b i{background:var(--accent)}
.pr .pf-days{max-height:380px;overflow:auto}
</style>"""


def table_html(mode, emps, dept=None):
    """Every employee (or one department's), highest productivity first."""
    by = defaultdict(list)
    for e in emps:
        if dept in (None, "", e["dept"]):
            by[e["dept"]].append(e)
    body = []
    for name, es in sorted(by.items()):
        body.append('<tr class="dh"><td colspan="9">%s<span>%d employee%s'
                    '</span></td></tr>' % (esc(name), len(es),
                                           "" if len(es) == 1 else "s"))
        for e in sorted(es, key=lambda e: -(e["productivity"] or 0)):
            a = e["act"]
            dp = ""
            if e["desk_parts"]:
                dp = '<span class="sub">at desk %s%% &middot; focus %s%% ' \
                     '&middot; on time %s%%</span>' % tuple(
                         "%d" % round(v) if v is not None else "-"
                         for _, v in e["desk_parts"])
            body.append(
                '<tr><td class="ph">%s</td><td class="l"><b>%s</b><span '
                'class="sub">%s &middot; %s</span></td><td class="sc"><b>%s'
                '</b><i style="width:%dpx"></i></td><td>%s</td><td>%s%s</td>'
                '<td>%s</td><td>%s</td><td>%s&ndash;%s</td><td class="l">%s'
                '</td></tr>'
                % (_photo(e), esc(e["name"]), esc(str(e["id"])),
                   esc(e["role"]), e["productivity"] if e["productivity"]
                   is not None else "-", int(0.7 * (e["productivity"] or 0)),
                   e["attendance"] if e["attendance"] is not None else "-",
                   e["desk"] if e["desk"] is not None
                   else '<span class="na">not seen</span>', dp,
                   ('%d<span class="sub">computer %d%% &middot; phone+talk %d%%'
                    '</span>' % (e["activity"], round(a["computer"]),
                                 round(a["talk_phone"]))) if a
                   else '<span class="na">&ndash;</span>',
                   ("%d/%d" % (e["days_in"], e["of"])) if e["days_in"]
                   is not None else "&ndash;",
                   _hhmm(e["usual_in"]), _hhmm(e["usual_out"]),
                   esc(e["measured"])))
    return "".join([
        _styles(mode), '<div class="ec pr"><div class="ec-card pr-wrap">'
        '<table><thead><tr><th></th><th class="l">Employee</th><th class="l">'
        'Presence</th><th>Attendance</th><th>Desk</th><th>Activity</th>'
        '<th>Days in</th><th>Usual in&ndash;out</th><th class="l">Measured by'
        '</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(body),
        '<div class="pr-note"><b>Presence</b> = attendance 40%, desk '
        '40%, desk activity 20%; a part not measured gives its weight to '
        'the others &mdash; a desk no camera sees leaves the attendance score '
        'alone. <b>Attendance</b> (the machines): hours in the building of a '
        '10-hour day 50%, at their own usual hour 30%, days in 20%. '
        '<b>Desk</b> (the cameras): at the desk of the office day 50%, in '
        'stretches of an hour or more 30%, on time 20%. <b>Activity</b>: '
        'on the computer 70% and not on the phone or talking 30%, as '
        'shares of the desk time, over the days it was read; a desk whose '
        'camera never sees a screen has none. Time and what the camera saw '
        '&mdash; never the worth of the work.</div></div>'])
