"""Department -> its people as cards -> one employee's report card.

Shamroze, 25 Nov 2026, night: "ek naya banda dashboard par jaaye to usko
samajh aaye ke productivity kaise dekhni hai". One way in, not three tabs:
the department's card (how many employees, its productivity), its people
as cards (their productivity beside the department's, the hours they
usually spend), and one employee's report card -- when they come and go,
productivity today so far and on average, how they compare with their
team (where they are strong, where weak: late, out of the building, on
the phone, talking a lot), and the signs people analytics watches before
somebody burns out or leaves. "CEO ko decision lene mein aasani ho" --
small and graphic, not every number of the day.

The factors, each against the employee's own team (their department; all
of 140-H where fewer than TEAM_MIN of it are measured on that factor):

  machines  in the building a day, usual arrival, a regular arrival
            (within half an hour of their own usual), days present,
            time out of the building in the day
  camera    at the desk (of the office day), focus (desk time in
            stretches of an hour or more), on the computer, on the phone,
            talking at the desk (shares of the desk time) -- only where a
            camera sees their own named desk

What big companies do, and what this copies (research, 25 Nov night):
presence and hours by badge or machine (Tesla's absenteeism reports,
Amazon's badge data); uninterrupted focus of an hour or more, and long
days as a wellbeing warning, never as credit (Microsoft Viva Insights;
WHO/ILO on 55-hour weeks); the phone apart from talk at the desk, which
is often the work itself (Google's Project Aristotle, Humanyze at Bank of
America) -- so being quiet is no merit, and only a lot of talk is
mentioned, as worth a look; time out of the building shown neutrally
(Amazon and Barclays were faulted for punishing breaks); changes against
the person's OWN usual as a reason for a check-in, not a penalty (IBM's
attrition work, HBR's signs before quitting); teams compared only in
groups of five or more (Microsoft's floor). Not measured: the results of
the work, which Microsoft and Google weigh most -- the card says so.

Time in the building and at the desk, and what the camera saw there --
never the worth of the work (CLAUDE.md). Rows in, HTML out: no
Streamlit, no OpenCV (the hosted page has neither); names and directory
icons only as the caller passes them, never a camera picture.
"""
import math
from datetime import datetime
from statistics import median

import pandas as pd

import productivity_view as prv
import progress_view as pv
from overview import esc

TEAM_MIN = 5             # Microsoft Viva's floor for a group; else 140-H
LONG_DAY_H = 10.5        # a day this long in the building is a long one
LATE_OUT_H = 21.5        # ... as is leaving after this hour
MISSED_SHARE = 0.35      # working days missed that make an early sign
CUT_BEFORE = 17.0        # the export's last day, if nobody punched later
# key, label, what the number is, better (+1 more, -1 less), measured by
FACTORS = (
    ("hours", "In the building", "hours a day", 1, "machines"),
    ("arrival", "Usual arrival", "clock time", -1, "machines"),
    ("regular", "Regular arrival", "days within 30 min of their usual", 1,
     "machines"),
    ("present", "Days present", "of the working days", 1, "machines"),
    ("out", "Out of the building", "minutes a day", -1, "machines"),
    ("desk", "At the desk", "of the office day", 1, "camera"),
    ("focus", "Focus", "desk time in stretches of 1 h+", 1, "camera"),
    ("computer", "On the computer", "of desk time", 1, "camera"),
    ("phone", "On the phone", "of desk time", -1, "camera"),
    ("talking", "Talking at the desk", "of desk time (often work)", -1,
     "camera"),
)
LABEL = {k: lab for k, lab, _, _, _ in FACTORS}
WHAT = {k: what for k, _, what, _, _ in FACTORS}
# How far from the team's usual is a real difference, not noise.
MARGIN = {"hours": 0.5, "arrival": 20 / 60.0, "regular": 10.0,
          "present": 5.0, "out": 25.0, "desk": 5.0, "focus": 5.0,
          "computer": 5.0, "phone": 3.0, "talking": 5.0}
# Where each factor sits in the productivity score (productivity_view):
# its part, its weight inside the part, and the factor as 0-100 points.
IN_SCORE = {
    "hours": ("attendance", 0.5, lambda v: 100.0 * min(1.0, v / 10.0)),
    "regular": ("attendance", 0.3, lambda v: v),
    "present": ("attendance", 0.2, lambda v: v),
    "desk": ("desk", 0.5, lambda v: v),
    "focus": ("desk", 0.3, lambda v: v),
    "computer": ("activity", 0.7, lambda v: v),
    "phone": ("activity", 0.3, lambda v: 100.0 - v),
    "talking": ("activity", 0.3, lambda v: 100.0 - v),
}
PART_W = dict(prv.WEIGHTS)
SOURCES = (
    "<b>How big companies do it, and what this card copies:</b> presence "
    "and hours by badge or machine (Tesla, Amazon); focus in stretches of "
    "an hour or more, and long days as a wellbeing warning, never as "
    "credit (Microsoft Viva Insights); the phone apart from talk at the "
    "desk, which is often the work itself (Google, Humanyze); breaks shown, "
    "not punished; a change against the person's own usual as a reason to "
    "talk, not a penalty (IBM, HBR); teams compared in groups of five or "
    "more (Microsoft). <b>Not measured here:</b> the results of the work "
    "&mdash; goals met, quality &mdash; which Microsoft and Google weigh "
    "most; add the manager's rating when HR has it.")


# ---------------------------------------------------------------- numbers

def _hour(x):
    """A time as a clock hour (9.5 = 09:30), or None."""
    if x is None:
        return None
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    return t.hour + t.minute / 60.0 + t.second / 3600.0


def clock(h):
    if h is None:
        return "&ndash;"
    m = int(round(h * 60))
    return "%02d:%02d" % ((m // 60) % 24, m % 60)


def span(minutes):
    """52 -> "52 min", 80 -> "1 h 20 min"."""
    m = int(round(abs(minutes)))
    if m < 60:
        return "%d min" % m
    return "%d h" % (m // 60) + (" %d min" % (m % 60) if m % 60 else "")


def _days(e):
    """The employee's days in by the machines, oldest first."""
    return sorted((d, s) for d, s in (e.get("days") or {}).items()
                  if s and s.get("first_in") is not None)


def _work(e):
    """Their working days in (Monday to Friday), less a day the export
    cut short -- what the usual and the signs are made of."""
    cut = e.get("_cut")
    return [(d, s) for d, s in _days(e)
            if d != cut and pd.Timestamp(d).dayofweek < 5]


def _out_min(s):
    """Minutes out of the building between a day's first IN and last OUT."""
    tot = 0.0
    for o in s.get("outings") or []:
        try:
            a, b = pd.Timestamp(o[0]), pd.Timestamp(o[1])
        except (TypeError, ValueError, IndexError):
            continue
        tot += max(0.0, (b - a).total_seconds() / 60.0)
    return tot


def cut_day(emps):
    """The export's last day when it ends mid-day (25 Nov: at 12:21) --
    nobody's punch on it after CUT_BEFORE -- else None."""
    last = max((d for e in emps for d in (e.get("days") or {})), default=None)
    if last is None:
        return None
    hours = [h for e in emps for s in [(e.get("days") or {}).get(last)] if s
             for h in (_hour(s.get("first_in")), _hour(s.get("last_out")))
             if h is not None]
    return last if hours and max(hours) < CUT_BEFORE else None


def factors(e):
    """{factor: value or None} for one employee (prepare() keeps it)."""
    days = _work(e) or _days(e)
    usual = e.get("usual_in")
    firsts = [h for h in (_hour(s["first_in"]) for _, s in days)
              if h is not None]
    v = {"hours": e.get("hours"), "arrival": usual,
         "regular": (100.0 * sum(1 for h in firsts if abs(h - usual) <= 0.5)
                     / len(firsts)) if usual is not None and firsts
         else None,
         "present": (100.0 * e["days_in"] / e["of"])
         if e.get("days_in") and e.get("of") else None,
         "out": (sum(_out_min(s) for _, s in days) / len(days))
         if days else None}
    parts = e.get("desk_parts") or []
    v["desk"] = parts[0][1] if len(parts) > 0 else None
    v["focus"] = parts[1][1] if len(parts) > 1 else None
    a = e.get("act") or {}
    v["computer"] = a.get("computer")
    v["phone"] = a.get("phone")
    v["talking"] = a.get("talking")
    return v


def prepare(emps, cut=None):
    """Every employee's factors, worked out once (e["f"]), and the day the
    export cut short (e["_cut"])."""
    cut = cut_day(emps) if cut is None else cut
    for e in emps:
        e["_cut"] = cut
        e["f"] = factors(e)
    return emps


def _peers(e, emps, key):
    """(team name, the colleagues measured on this factor): the department,
    or all of 140-H where too few of it are."""
    same = [x for x in emps if x["dept"] == e["dept"] and x["eid"] != e["eid"]
            and x["f"].get(key) is not None]
    if len(same) + 1 >= TEAM_MIN:
        return e["dept"], same
    return e.get("campus") or "140-H", [
        x for x in emps if x["eid"] != e["eid"]
        and x["f"].get(key) is not None]


def compare(e, emps):
    """Each factor measured for the employee against their team:
    [{key, value, median, beat (% of the team they do better than), n,
    team, diff (+ better than the team's usual), real, peers}]."""
    out = []
    for key, _, _, better, src in FACTORS:
        v = e["f"].get(key)
        if v is None:
            continue
        team, peers = _peers(e, emps, key)
        vals = [x["f"][key] for x in peers]
        if not vals:
            continue
        med = median(vals)
        worse = sum(1 for x in vals if (x - v) * better < 0)
        same = sum(1 for x in vals if x == v)
        out.append({"key": key, "value": v, "median": med,
                    "beat": 100.0 * (worse + 0.5 * same) / len(vals),
                    "n": len(vals) + 1, "team": team, "src": src,
                    "better": better, "diff": (v - med) * better,
                    "real": abs(v - med) >= MARGIN[key],
                    "peers": [(x["name"], x["f"][key]) for x in peers]})
    return out


def _fmt(key, v):
    if v is None:
        return "&ndash;"
    if key == "hours":
        return "%.1f h" % v
    if key == "arrival":
        return clock(v)
    if key == "out":
        return "%d min" % round(v)
    return "%d%%" % round(v)


def _gap(key, a, b):
    d = abs(a - b)
    if key == "hours":
        return "%.1f h" % d
    if key == "arrival":
        return span(d * 60)
    if key == "out":
        return "%d min" % round(d)
    return "%d points" % round(d)


def _times(v, m, k, t):
    """"twice GTM's 6%" or "12 points more than GTM's 6%"."""
    times = v / m if m > 0 else None
    if times and times >= 1.8:
        return "%s %s's %s" % ("twice" if times < 2.5 else
                               "%.0f times" % times, t, _fmt(k, m))
    return "%s more than %s's %s" % (_gap(k, v, m), t, _fmt(k, m))


def say(c, e):
    """One comparison in words, good or bad."""
    k, v, m, t = c["key"], c["value"], c["median"], esc(c["team"])
    good = c["diff"] > 0
    cam = ' <span class="cam">camera</span>' if c["src"] == "camera" else ""
    usual = "%s's usual %s" % (t, _fmt(k, m))
    if k == "hours":
        return ("In the building %s a day &mdash; %s %s than %s"
                % (_fmt(k, v), _gap(k, v, m), "more" if good else "less",
                   usual))
    if k == "arrival":
        return ("%s: usually in at %s, %s %s %s"
                % ("Comes in early" if good else "Comes in late", clock(v),
                   span(abs(v - m) * 60), "before" if good else "after",
                   usual))
    if k == "regular":
        return ("%s: within half an hour of their usual on %s of days (%s %s)"
                % ("Regular" if good else "Irregular arrival", _fmt(k, v), t,
                   _fmt(k, m)))
    if k == "present":
        return ("%s %s of %s working days (%s usually %s)"
                % ("In on" if good else "Absent more: in on",
                   e.get("days_in"), e.get("of"), t, _fmt(k, m)))
    if k == "out":
        return ("%s %s a day (%s)%s"
                % ("Rarely out of the building:" if good else
                   "Out of the building", _fmt(k, v), usual,
                   "" if good else " &mdash; long breaks or errands"))
    if k == "desk":
        return ("%s %s of the office day (%s)%s"
                % ("At the desk" if good else "Often away from the desk: at"
                   " it", _fmt(k, v), usual, cam))
    if k == "focus":
        return ("%s %s of desk time in stretches of an hour or more (%s)%s"
                % ("Long focus:" if good else "Short bursts: only",
                   _fmt(k, v), usual, cam))
    if k == "computer":
        return ("%s %s of desk time (%s)%s"
                % ("On the computer" if good else "Less on the computer:",
                   _fmt(k, v), usual, cam))
    if k == "phone":
        if good:
            return ("Rarely on the phone: %s of desk time (%s)%s"
                    % (_fmt(k, v), usual, cam))
        return ("On the phone %s of desk time &mdash; %s%s"
                % (_fmt(k, v), _times(v, m, k, t), cam))
    if k == "talking":
        return ("Talks at the desk a lot: %s of desk time &mdash; %s; may "
                "be work, worth a look%s" % (_fmt(k, v), _times(v, m, k, t),
                                             cam))
    return ""


def _strong_ok(c):
    if c["key"] == "talking":
        return False         # quiet is no merit: talk is often the work
    if c["key"] == "hours" and c["value"] > LONG_DAY_H:
        return False         # long days are a wellbeing sign, never credit
    return True


def _weak_ok(c):
    if c["key"] == "talking":
        return c["value"] >= max(10.0, 2.0 * c["median"])
    if c["key"] == "out":
        return c["value"] >= max(45.0, 2.0 * c["median"])
    return True


def points(e, comps, most=3):
    """(strong, weak): up to `most` comparisons each, the clearest first --
    a real difference, in the team's best or worst third."""
    strong = sorted([c for c in comps if c["real"] and c["diff"] > 0
                     and c["beat"] >= 66 and _strong_ok(c)],
                    key=lambda c: -c["beat"])
    weak = sorted([c for c in comps if c["real"] and c["diff"] < 0
                   and c["beat"] <= 34 and _weak_ok(c)],
                  key=lambda c: c["beat"])
    return strong[:most], weak[:most]


def why(e, comps, emps):
    """One sentence: how far they are from their department's average
    productivity, and which factors put them there (each factor's share
    of the score, against the team's usual on it)."""
    p = e.get("productivity")
    mates = [x["productivity"] for x in emps if x["dept"] == e["dept"]
             and x["productivity"] is not None]
    if p is None or not mates:
        return ""
    avg = sum(mates) / float(len(mates))
    gap = p - avg
    parts = {"attendance": e.get("attendance"), "desk": e.get("desk"),
             "activity": e.get("activity")}
    total = sum(PART_W[k] for k, v in parts.items() if v is not None) or 1.0
    pushes = []
    for c in comps:
        how = IN_SCORE.get(c["key"])
        if not how or parts.get(how[0]) is None:
            continue
        part, w, s = how
        pts = PART_W[part] / total * w * (s(c["value"]) - s(c["median"]))
        pushes.append((pts, c["key"]))
    team = esc(e["dept"])
    if abs(gap) < 3:
        head = "Close to %s's average (%d)" % (team, round(avg))
    else:
        head = "<b>%d points %s</b> %s's average (%d)" % (
            round(abs(gap)), "above" if gap > 0 else "below", team,
            round(avg))
    lead = [k for pts, k in sorted(pushes, key=lambda t: -t[0] if gap >= 0
                                   else t[0])
            if (pts > 0.5 if gap >= 0 else pts < -0.5)][:2]
    if not lead:
        return head + "."
    names = " and ".join(LABEL[k].lower() for k in lead)
    return "%s, mostly from %s." % (head, names)


def signals(e):
    """Early signs, as people analytics watches them -- each against the
    person's own usual (HBR, IBM): burn-out (long days), leaving (hours
    falling, coming later, going earlier, days missed); else a steady
    pattern. [(level, text)] -- level "warn" or "good"."""
    if not e.get("days_in"):
        return [("warn", "Not enough days yet: seen only on the export's "
                 "last day, cut short")] if _days(e) else []
    days = _work(e)
    out = []
    closed = [(d, s) for d, s in days if s.get("closed", True)
              and s.get("inside_min")]
    # 27 Nov (Shamroze: "24/7 ka kaam hai, employee marzi se aata, marzi se
    # jaata -- timing flexible"): a long day is the hours, never the hour
    # somebody leaves
    long_ = {d for d, s in closed if s["inside_min"] >= LONG_DAY_H * 60}
    if len(long_) >= 3:
        out.append(("warn", "Long days: %d of %d over 10&frac12; hours "
                    "&mdash; a burn-out risk" % (len(long_), len(days))))
    hrs = [s["inside_min"] / 60.0 for _, s in closed]
    if len(hrs) >= 6:
        recent, before = sum(hrs[-3:]) / 3.0, sum(hrs[:-3]) / len(hrs[:-3])
        if before - recent >= 1.0:
            out.append(("warn", "Hours falling: %.1f h a day lately, %.1f h "
                        "before &mdash; worth a talk" % (recent, before)))
    firsts = [_hour(s["first_in"]) for _, s in days]
    if len(firsts) >= 6:
        a, b = median(firsts[:-3]), median(firsts[-3:])
        if b - a >= 0.5:
            out.append(("warn", "Coming in later lately: %s against %s "
                        "before" % (clock(b), clock(a))))
    lasts = [_hour(s["last_out"]) for _, s in closed]
    if len(lasts) >= 6:
        a, b = median(lasts[:-3]), median(lasts[-3:])
        if a - b >= 0.5:
            out.append(("warn", "Leaving earlier lately: %s against %s "
                        "before" % (clock(b), clock(a))))
    if e.get("of") and e["of"] - e["days_in"] >= max(
            2, math.ceil(MISSED_SHARE * e["of"])):
        out.append(("warn", "Missed %d of %d working days" % (
            e["of"] - e["days_in"], e["of"])))
    if not out and days:
        out.append(("good", "Steady: no warning sign in their pattern"))
    return out


def today(e, now, hours=(10.0, 20.0), last_day=None):
    """Productivity today so far, from what is in for today: the machines
    (a day closed by an OUT punch) and the desk camera (live). {score,
    facts: [(label, value)], note} -- score None when nothing is known."""
    if now is None:
        return {"score": None, "facts": [], "note": ""}
    day = now.strftime("%Y-%m-%d")
    facts, att, desk, act = [], None, None, None
    s = (e.get("days") or {}).get(day)
    if s and s.get("first_in") is not None:
        f = _hour(s["first_in"])
        facts.append(("In", clock(f)))
        usual = e.get("usual_in")
        regular = 1.0 if usual is None or abs(f - usual) <= 0.5 else 0.0
        if s.get("closed") and s.get("last_out") is not None:
            facts.append(("Out", clock(_hour(s["last_out"]))))
            facts.append(("In the building", "%.1f h" % (s["inside_min"]
                                                          / 60.0)))
            att = 100.0 * (0.5 * min(1.0, s["inside_min"] / 600.0)
                           + 0.3 * regular + 0.2)
        else:
            facts.append(("Out", "not yet"))
    p = e.get("board") or {}
    d = next((x for x in p.get("days") or [] if x.get("day") == day), None)
    if d and d.get("first") is not None:
        start, end = hours
        clock_now = now.hour + now.minute / 60.0
        elapsed = max(0.0, (min(clock_now, end) - start) * 60.0)
        dm = float(d.get("desk_min") or 0.0)
        at = min(1.0, dm / elapsed) if elapsed > 0 else 0.0
        lp = min(1.0, float(d.get("long_min") or 0.0) / dm) if dm else 0.0
        fh = _hour(d["first"])
        late = max(0.0, (fh - start) * 60.0 - pv.LATE_AFTER)
        on_time = max(0.0, 100.0 - 10.0 * math.ceil(late / 15.0)) \
            if late else 100.0
        desk = 0.5 * 100.0 * at + 0.3 * 100.0 * lp + 0.2 * on_time
        facts.append(("At the desk from", clock(fh)))
        facts.append(("At the desk so far", pv.dur(dm)))
        h = next((r for r in p.get("history") or [] if r.get("day") == day),
                 None)
        if h and h.get("computer_min") and h.get("desk_min"):
            dk = float(h["desk_min"])
            c = min(1.0, float(h["computer_min"]) / dk)
            t = min(1.0, (float(h.get("phone_min") or 0)
                          + float(h.get("talking_min") or 0)) / dk)
            act = 100.0 * (0.7 * c + 0.3 * (1.0 - t))
    score = prv.productivity(att, desk, act)
    note = ""
    if score is None:
        note = ("No score for today yet: %s%s." % (
            "the attendance machines' export ends %s" % esc(last_day)
            if last_day and last_day < day else
            "the day is not closed by an OUT punch yet",
            "" if e.get("board") else
            ", and no camera sees their own desk"))
    return {"score": score, "facts": facts, "note": note}


# ------------------------------------------------------------------ cards

_CSS = """<style>
.pr .pe{padding:12px 14px;border-radius:14px;margin-bottom:6px}
.pr .pe .who{display:flex;gap:10px;align-items:center;min-height:48px}
.pr .pe .who img,.pr .pe .who .nop{width:42px;height:42px;border-radius:50%;
object-fit:cover;flex:none;background:var(--s2)}
.pr .pe .who b{display:block;font-size:13.5px;line-height:1.25;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
overflow:hidden}
.pr .pe .who span{display:block;font-size:11.5px;color:var(--t3);
white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.pr .pe .sc{display:flex;align-items:baseline;gap:6px;margin-top:8px}
.pr .pe .sc b{font-size:28px;line-height:1;color:var(--accent);
letter-spacing:-.02em}
.pr .pe .sc span{font-size:11.5px;color:var(--t3)}
.pr .pe .sc em{margin-left:auto;font-style:normal;font-size:11.5px;
color:var(--t2)}
.pr .pe .bar{position:relative;height:6px;border-radius:4px;
background:var(--s2);margin:7px 0 8px}
.pr .pe .bar i{display:block;height:100%;border-radius:4px;
background:var(--accent)}
.pr .pe .bar s{position:absolute;top:-3px;width:2px;height:12px;
background:var(--t1);border-radius:1px}
.pr .pe .ft{font-size:12px;color:var(--t2)}
.pr .rc-head{display:flex;gap:16px;align-items:center;flex-wrap:wrap;
padding:14px 18px;margin-bottom:10px}
.pr .rc-head img,.pr .rc-head .nop{width:76px;height:76px;border-radius:50%;
object-fit:cover;background:var(--s2)}
.pr .rc-head h3{margin:0;font-size:21px}
.pr .rc-head p{margin:2px 0 0;font-size:13px;color:var(--t2)}
.pr .rc-head p.m{color:var(--t3);font-size:12px}
.pr .rc-big{margin-left:auto;display:flex;gap:22px;align-items:flex-end}
.pr .rc-big div{text-align:center}
.pr .rc-big b{display:block;font-size:44px;line-height:1;color:var(--accent);
letter-spacing:-.02em}
.pr .rc-big b.td{font-size:30px;color:var(--t1)}
.pr .rc-big span{font-size:11.5px;color:var(--t3)}
.pr .rc-why{font-size:14px;margin:2px 0 10px;color:var(--t1)}
.pr .rc-why b{color:var(--accent)}
.pr .rc-pts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
gap:12px;margin-bottom:10px}
.pr .rc-pts .ec-card{padding:12px 16px}
.pr .rc-pts h4{margin:0 0 6px;font-size:13.5px;display:flex;gap:6px;
align-items:center}
.pr .rc-pts h4 .ic{width:15px;height:15px}
.pr .rc-pts ul{margin:0;padding-left:18px;font-size:13px;line-height:1.55}
.pr .rc-pts li{margin:3px 0}
.pr .rc-pts .none{font-size:12.5px;color:var(--t3);margin:0}
.pr .cam{font-size:10.5px;color:var(--t3);border:1px solid var(--line);
border-radius:99px;padding:0 6px;margin-left:4px;white-space:nowrap}
.pr .rc-sig{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
.pr .rc-sig span{display:inline-flex;gap:6px;align-items:center;font-size:12.5px;
border:1px solid var(--line);border-radius:99px;padding:4px 12px;
background:var(--s1)}
.pr .rc-sig .ic{width:14px;height:14px}
.pr .rc-box{padding:12px 16px;margin-bottom:10px}
.pr .rc-box h4{margin:0;font-size:14px}
.pr .jy-first{font-size:13px;color:var(--t2);margin:6px 0 8px}
.pr .jy-row{display:grid;grid-template-columns:96px 10px minmax(0,1.2fr) minmax(0,1fr) 78px;
gap:8px;align-items:center;font-size:13px;padding:3px 0;border-top:1px solid var(--line)}
.pr .jy-t{color:var(--t3);font-variant-numeric:tabular-nums;white-space:nowrap}
.pr .jy-d{width:10px;height:10px;border-radius:50%;display:block}
.pr .jy-n{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pr .jy-b{height:8px;background:var(--s2);border-radius:99px;overflow:hidden}
.pr .jy-b i{display:block;height:100%;border-radius:99px}
.pr .jy-m{text-align:right;color:var(--t2);white-space:nowrap}
@media (max-width:640px){.pr .jy-row{grid-template-columns:78px 10px minmax(0,1fr) 62px}
.pr .jy-b{display:none}}
.pr .rc-two{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
gap:12px;margin-bottom:10px}
.pr .rc-two .ec-card{padding:12px 16px}
.pr .rc-lg{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;
color:var(--t2);margin:2px 0 6px}
.pr .rc-lg i{display:inline-block;width:9px;height:9px;border-radius:50%;
margin-right:5px;vertical-align:0}
.pr .rc-lg i.sq{border-radius:2px}
.pr .rc-lg i.tk{width:2px;height:11px;border-radius:1px;vertical-align:-1px}
.pr .rc-today{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;
margin:8px 0 4px}
.pr .rc-today span{color:var(--t3);font-size:11.5px;display:block}
.pr .rc-today b{font-size:15px}
.pr .rc-strip .row,.pr .rc-strip .hd{display:grid;
grid-template-columns:170px minmax(0,1fr) 150px;gap:14px;align-items:center}
.pr .rc-strip .row{padding:7px 0;border-top:1px solid var(--line)}
.pr .rc-strip .hd span{font-size:10.5px;color:var(--t3);text-align:right}
.pr .rc-strip .lab b,.pr .rc-strip .val b{display:block;font-size:13px}
.pr .rc-strip .lab span,.pr .rc-strip .val span{display:block;
font-size:11px;color:var(--t3);line-height:1.3}
.pr .rc-strip .trk{position:relative;height:20px}
.pr .rc-strip .trk:before{content:"";position:absolute;left:0;right:0;
top:50%;height:1px;background:var(--line2)}
.pr .rc-strip .trk i{position:absolute;top:50%;width:8px;height:8px;
margin:-4px 0 0 -4px;border-radius:50%;background:var(--t3);opacity:.45}
.pr .rc-strip .trk s{position:absolute;top:50%;width:2px;height:18px;
margin:-9px 0 0 -1px;border-radius:1px;background:var(--t1)}
.pr .rc-strip .trk u{position:absolute;top:50%;width:14px;height:14px;
margin:-7px 0 0 -7px;border-radius:50%;background:var(--accent);
box-shadow:0 0 0 2px var(--s1)}
.pr .rc-days .row{display:grid;grid-template-columns:86px minmax(0,1fr) 64px;
gap:10px;align-items:center;height:24px}
.pr .rc-days .lab{font-size:12px;color:var(--t2);white-space:nowrap}
.pr .rc-days .hrs{font-size:12px;text-align:right;
font-variant-numeric:tabular-nums}
.pr .rc-days .trk{position:relative;height:100%}
.pr .rc-days .trk s{position:absolute;top:0;bottom:0;width:1px;
background:var(--line)}
.pr .rc-days .trk u{position:absolute;top:0;bottom:0;background:var(--s2)}
.pr .rc-days .trk i{position:absolute;top:6px;height:12px;border-radius:4px;
background:var(--accent)}
.pr .rc-days .trk b{position:absolute;top:7px;width:10px;height:10px;
margin-left:-5px;border-radius:50%;background:var(--accent)}
.pr .rc-days .ax{height:20px}
.pr .rc-days .ax em{position:absolute;top:3px;transform:translateX(-50%);
font-size:11px;font-style:normal;color:var(--t3)}
@media (max-width:640px){
.pr .rc-strip .row{grid-template-columns:minmax(0,1fr) auto;row-gap:4px}
.pr .rc-strip .row .trk{grid-column:1/-1;order:3}
.pr .rc-strip .hd{display:none}
.pr .rc-days .row{grid-template-columns:64px minmax(0,1fr) 46px;gap:6px}
.pr .rc-days .lab{font-size:11px}
.pr .rc-days .ax em:nth-child(even){display:none}
.pr .rc-big{margin-left:0}
}
.pr .ov-head{display:flex;gap:22px;flex-wrap:wrap;margin:8px 0 10px}
.pr .ov-head div{min-width:92px}
.pr .ov-head span{display:block;font-size:11.5px;color:var(--t3)}
.pr .ov-head b{font-size:19px;letter-spacing:-.01em}
.pr .ov-alloc{display:flex;height:26px;border-radius:7px;overflow:hidden;
gap:2px;margin:4px 0 8px;background:var(--s1)}
.pr .ov-alloc i{display:block;height:100%}
.pr .ov-lg{display:flex;gap:6px 16px;flex-wrap:wrap;font-size:12px;
color:var(--t2);margin-bottom:10px}
.pr .ov-lg span b{color:var(--t1);font-weight:700;margin-left:4px}
.pr .ov-lg i{display:inline-block;width:10px;height:10px;border-radius:3px;
margin-right:6px;vertical-align:-1px}
.pr .ov-line{position:relative;height:30px;background:var(--s2);
border-radius:6px;margin:2px 0 2px}
.pr .ov-line i{position:absolute;top:0;bottom:0}
.pr .ov-ax{position:relative;height:18px;margin-bottom:4px}
.pr .ov-ax em{position:absolute;transform:translateX(-50%);font-size:11px;
font-style:normal;color:var(--t3)}
.pr .pair{width:100%;border-collapse:collapse;font-size:13px;
font-variant-numeric:tabular-nums;margin-top:6px}
.pr .pair th{font-size:11px;color:var(--t3);font-weight:650;text-align:right;
padding:6px 8px;border-bottom:1px solid var(--line)}
.pr .pair td{padding:6px 8px;border-bottom:1px solid var(--line);
text-align:right;white-space:nowrap}
.pr .pair th.l,.pr .pair td.l{text-align:left;white-space:normal}
.pr .pair td.w{font-size:11.5px;color:var(--t2)}
.pr .pair td.w b{color:var(--t1)}
.pr .pair td.a{font-weight:700}
.pr .pair .up{color:var(--good)}
.pr .pair .dn{color:var(--crit)}
.pr .rc-vs{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.pr .rc-vs img,.pr .rc-vs .nop{width:40px;height:40px;border-radius:50%;
object-fit:cover;background:var(--s2)}
.pr .rc-vs b.n{font-size:24px;color:var(--accent);letter-spacing:-.02em}
.pr .rc-vs .vs{font-size:12px;color:var(--t3)}
.pr .rc-vs .who b{display:block;font-size:13.5px}
.pr .rc-vs .who span{display:block;font-size:11.5px;color:var(--t3)}
.pr .rc-say{font-size:13.5px;margin:10px 0 2px;line-height:1.5}
.pr .dstrip{position:relative;margin:6px 0 2px;border-bottom:1px solid
var(--line2)}
.pr .dstrip u{position:absolute;top:0;bottom:0;background:var(--s2);
border-radius:4px}
.pr .dstrip s{position:absolute;top:0;bottom:0;width:2px;margin-left:-1px;
background:var(--t1);border-radius:1px}
.pr .dstrip i{position:absolute;width:10px;height:10px;margin-left:-5px;
border-radius:50%;box-shadow:0 0 0 1.5px var(--s1)}
.pr .pe .tag{display:inline-block;font-size:10.5px;font-weight:650;
border-radius:99px;padding:1px 8px;margin-left:6px;vertical-align:1px}
</style>"""

# Where the day went: a kind of place -> its words, in a fixed order
# (dataviz: colour follows the place, never its rank). The reference
# palette's categorical slots; "in the building" and "not known" grey.
PLACES = (("desk", "At the desk"), ("meeting", "Meeting rooms"),
          ("cafe", "Cafe and pantry"), ("smoking", "Smoking area"),
          ("prayer", "Prayer"), ("inside", "In the building, place not seen"),
          ("out", "Out of the building"), ("unknown", "Not known"))
PLACE_LABEL = dict(PLACES)
PLACE_COLOUR = {
    "light": {"desk": "#2a78d6", "meeting": "#1baf7a", "cafe": "#eb6834",
              "smoking": "#e87ba4", "prayer": "#6250d6", "out": "#eda100",
              "inside": "#bdbcb6", "unknown": "#e3e2dd"},
    "dark": {"desk": "#3987e5", "meeting": "#199e70", "cafe": "#d95926",
             "smoking": "#d55181", "prayer": "#9085e9", "out": "#c98500",
             "inside": "#5f5e5a", "unknown": "#383835"}}
_MODE = {"m": "light"}


def styles(mode):
    _MODE["m"] = "dark" if mode == "dark" else "light"
    return prv._styles(mode, prv._PF_CSS, _CSS)


def colour(kind):
    return PLACE_COLOUR[_MODE["m"]].get(kind, PLACE_COLOUR[_MODE["m"]][
        "unknown"])


def dept_avg(es):
    vals = [e["productivity"] for e in es if e["productivity"] is not None]
    return sum(vals) / float(len(vals)) if vals else None


def emp_card(e, avg, state=None):
    """An employee's card in their department's list: photo, name, role,
    their productivity with the department's beside it (a tick on the
    bar), the hours they usually spend and their usual in and out -- and
    "long days" or "low hours" where their workload says so. The
    workforce's: their workforce score beside their group's."""
    p = e.get("productivity")
    crew = e.get("staff") == "workforce"
    tag = ('<span class="tag" style="color:%s;border:1px solid %s">%s</span>'
           % (STATE_COLOUR[state], STATE_COLOUR[state], STATE_WORDS[state])
           if state in ("long", "low") else "")
    return ('<div class="ec pr"><div class="ec-card pe"><div class="who">%s'
            '<div style="min-width:0"><b>%s</b><span>%s</span></div></div>'
            '<div class="sc"><b>%s</b><span>%s</span><em>%s %s'
            '</em></div><div class="bar" role="img" aria-label="%s of 100, '
            'department %s"><i style="width:%d%%"></i>%s</div>'
            '<div class="ft">%s a day &middot; in %s &middot; out %s%s</div>'
            '</div></div>'
            % (prv._photo(e), esc(e["name"]), esc(e["role"] or e["dept"]),
               "%d" % p if p is not None else "-",
               "workforce score" if crew else "productivity",
               "group" if crew else "dept",
               "%d" % round(avg) if avg is not None else "-",
               p if p is not None else "-",
               "%d" % round(avg) if avg is not None else "-", p or 0,
               '<s style="left:calc(%.1f%% - 1px)"></s>' % avg
               if avg is not None else "",
               "%.1f h" % e["hours"] if e.get("hours") is not None
               else "&ndash; h", clock(e.get("usual_in")),
               clock(e.get("usual_out")), tag))


def dept_head(mode, name, es, emps):
    """The department opened: its figures, everybody's day at a glance,
    above its people's cards."""
    return prv.dept_head_html(mode, name, es, emps).replace(
        "click a person for their profile",
        "open a card for the report card") + dept_strip_html(es)


STATE_COLOUR = {"healthy": "var(--good)", "long": "#e8a21a",
                "low": "var(--t3)"}
STATE_WORDS = {"healthy": "healthy hours", "long": "long days",
               "low": "low hours"}


def states(es):
    """{eid: healthy | long | low} by workload() (unknown left out)."""
    w = workload(es)
    return {e["eid"]: k for k in ("healthy", "long", "low") for e in w[k]}


def dept_strip_html(es):
    """Everybody in the department as a dot on hours in the building a day
    -- the healthy band shaded, the department's usual a tick, each dot
    coloured healthy / long / low (research, 26 Nov: a dot strip per
    department, ActivTrak's workload balance). A dot hovered names them."""
    st_ = states(es)
    pts = sorted([(e["hours"], e) for e in es if e.get("hours") is not None],
                 key=lambda t: t[0])
    if len(pts) < 2:
        return ""
    hi = max(13.0, math.ceil(pts[-1][0]))

    def x(h):
        return 100.0 * min(max(h, 0.0), hi) / hi
    rows, dots = [], []
    for h, e in pts:
        r = next((i for i, last in enumerate(rows) if x(h) - last >= 1.8),
                 len(rows))
        if r == len(rows):
            rows.append(x(h))
        else:
            rows[r] = x(h)
        k = st_.get(e["eid"], "healthy")
        dots.append('<i style="left:%.2f%%;top:%dpx;background:%s" title="'
                    '%s: %.1f h a day (%s)"></i>'
                    % (x(h), 6 + 13 * r, STATE_COLOUR[k], esc(e["name"]), h,
                       STATE_WORDS[k]))
    med = median([h for h, _ in pts])
    height = 12 + 13 * len(rows)
    ticks = "".join('<em style="left:%.2f%%">%d h</em>' % (x(t), t)
                    for t in range(0, int(hi) + 1, 2))
    counts = {k: sum(1 for v in st_.values() if v == k)
              for k in STATE_WORDS}
    return ('<div class="ec pr"><div class="ec-card rc-box"><h4>Everybody\'s '
            'day at a glance &middot; hours in the building a day</h4><div '
            'class="rc-lg">%s<span><i class="tk" style="background:var(--t1)'
            '"></i>the department\'s usual %.1f h</span></div><div class='
            '"dstrip" style="height:%dpx"><u style="left:%.2f%%;width:%.2f%%">'
            '</u><s style="left:%.2f%%"></s>%s</div><div class="ov-ax">%s</div>'
            '<div class="pr-note" style="margin-top:2px">Shaded: 6 to 10&frac12;'
            ' h. Hover a dot for who.</div></div></div>'
            % ("".join('<span><i style="background:%s"></i>%s %d</span>'
                       % (STATE_COLOUR[k], STATE_WORDS[k], counts[k])
                       for k in ("healthy", "long", "low")),
               med, height, x(LOW_DAY_H), x(LONG_DAY_H) - x(LOW_DAY_H),
               x(med), "".join(dots), ticks))


LOW_DAY_H = 6.0          # under this in the building a day is a low day
LOW_SHARE = 0.8          # ... as is 20% under their department's usual


def workload(emps):
    """Everybody's usual day by the machines, sorted the way ActivTrak's
    Workload Balance and Gallup's burn-out line do (research, 26 Nov):
    {"healthy", "long" (over 10.5 h a day -- past 50 h a week), "low"
    (under 6 h, or 20% under their department's usual), "unknown"} ->
    [employees]."""
    out = {"healthy": [], "long": [], "low": [], "unknown": []}
    by_dept = {}
    for e in emps:
        if e.get("hours") is not None:
            by_dept.setdefault(e["dept"], []).append(e["hours"])
    for e in emps:
        h = e.get("hours")
        if h is None:
            out["unknown"].append(e)
        elif h > LONG_DAY_H:
            out["long"].append(e)
        elif h < LOW_DAY_H or h < LOW_SHARE * median(by_dept[e["dept"]]):
            out["low"].append(e)
        else:
            out["healthy"].append(e)
    return out


def workload_html(emps):
    """The campus's workload in three counts, under the four figures."""
    import overview
    w = workload(emps)
    known = len(emps) - len(w["unknown"])

    def tile(icon, k, n, s):
        return ('<div class="ec-card ec-kpi"><div class="k">%s%s</div><div '
                'class="v">%d <span style="font-size:13px;color:var(--t3);'
                'font-weight:500">of %d</span></div><div class="s">%s</div>'
                '</div>' % (icon, k, n, known, s))
    return ('<div class="ec pr"><div class="pr-kpis k4" style="grid-template-'
            'columns:repeat(auto-fit,minmax(200px,1fr))">%s%s%s</div><div '
            'class="pr-note" style="margin:-4px 0 10px">Hours in the building '
            'a day, by the attendance machines, over each person\'s days '
            '&mdash; %d without a closed day yet. Long: past 10&frac12; h a '
            'day (over 50 h a week, Gallup\'s burn-out line). Low: under 6 h, '
            'or a fifth under their department\'s usual.</div></div>'
            % (tile(overview.TICK, " Healthy hours", len(w["healthy"]),
                    "6 to 10&frac12; h a day"),
               tile(overview.WARN, " Long days", len(w["long"]),
                    "burn-out risk &mdash; worth a word"),
               tile(overview.WARN, " Low hours", len(w["low"]),
                    "under the team's usual"), len(w["unknown"])))


CREW_WHY = ("Janitorial, office boys, gate and security, valet and "
            "technicians work around the building, not at a desk (Shamroze, "
            "26 Nov: measured apart). Their score is the attendance "
            "machines' for now -- time in the building, a regular arrival, "
            "days in -- and each is compared only with their own kind of "
            "work; the cameras around the building can add where their "
            "day goes. Night shifts cross midnight and the machines' days "
            "split there, so a night shift's hours read short for now.")


def crew_card(crew):
    """The workforce staff's card among the departments."""
    avg = dept_avg(crew)
    groups = sorted({e["dept"] for e in crew})
    return ('<div class="ec pr"><div class="ec-card pr-dc"><div class="nm">'
            'Workforce staff</div><div class="row"><b>%s</b><span>workforce '
            'score</span></div><div class="bar"><i style="width:%d%%"></i>'
            '</div><div class="ct"><b>%d</b> people &middot; %s &middot; '
            'measured apart</div></div></div>'
            % ("%d" % round(avg) if avg is not None else "-",
               round(avg or 0), len(crew), esc(", ".join(g.lower()
                                                         for g in groups))))


def crew_head(mode, crew):
    """The workforce opened: their figures and how they are measured."""
    avg = dept_avg(crew)
    hrs = [e["hours"] for e in crew if e.get("hours") is not None]
    pres = [e["f"]["present"] for e in crew
            if (e.get("f") or {}).get("present") is not None]
    return "".join([
        '<div class="ec pr"><div class="pr-hero sm"><div><h2>Workforce staff'
        '</h2><p>%d people &middot; open a card for the report card</p></div>'
        '</div>' % len(crew),
        prv._kpis([
            ("Workforce score", "%d" % round(avg) if avg is not None else "-",
             "attendance, of 100"),
            ("People", "%d" % len(crew), "%d groups" % len(
                {e["dept"] for e in crew})),
            ("In the building, a day", "%.1f h" % median(hrs) if hrs
             else "-", "the middle person"),
            ("Days present", "%d%%" % round(sum(pres) / len(pres)) if pres
             else "-", "of the working days")]),
        '<div class="pr-note" style="margin:0 0 6px">%s</div></div>'
        % esc(CREW_WHY)])


# ----------------------------------------------------------------- charts

def strip_html(comps, e):
    """Each factor a row: the team as grey dots on the factor's own scale
    -- better to the right -- their usual as a tick, the employee as the
    blue dot; the value and the team's usual written beside it. A dot
    hovered says whose and how much. HTML, not one picture, so the words
    keep their size on a phone (the track goes under the name there)."""
    if not comps:
        return ""
    out = ['<div class="rc-strip" role="list"><div class="hd"><span></span>'
           '<span>better &rarr;</span><span></span></div>']
    for c in comps:
        k, b = c["key"], c["better"]
        vals = [v for _, v in c["peers"]] + [c["value"]]
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-6:
            lo, hi = lo - 1.0, hi + 1.0

        def x(v, lo=lo, hi=hi, b=b):
            f = (v - lo) / (hi - lo)
            return 2.0 + 96.0 * (f if b > 0 else 1.0 - f)
        dots = "".join('<i style="left:%.1f%%" title="%s: %s"></i>'
                       % (x(v), esc(name), _fmt(k, v)) for name, v in c["peers"])
        out.append(
            '<div class="row" role="listitem"><div class="lab"><b>%s</b>'
            '<span>%s%s</span></div><div class="trk" aria-hidden="true">%s'
            '<s style="left:%.1f%%" title="%s usual: %s"></s><u style="left:'
            '%.1f%%" title="%s: %s"></u></div><div class="val"><b>%s</b><span>'
            '%s %s &middot; of %d</span></div></div>'
            % (esc(LABEL[k]), esc(WHAT[k]),
               " &middot; camera" if c["src"] == "camera" else "", dots,
               x(c["median"]), esc(c["team"]), _fmt(k, c["median"]),
               x(c["value"]), esc(e["name"]), _fmt(k, c["value"]),
               _fmt(k, c["value"]), esc(c["team"][:18]),
               _fmt(k, c["median"]), c["n"]))
    out.append("</div>")
    return "".join(out)


def days_html(e, team_in=None, team_out=None, limit=10):
    """Their days, newest at the top: a bar from the first IN to the last
    OUT on the clock (07-23; a punch outside sits at the edge), gaps where
    they were out of the building, the team's usual hours shaded behind,
    the hours at the right. HTML rows, so it reads on a phone too."""
    days = _days(e)[-limit:][::-1]
    if not days:
        return ""
    lo_h, hi_h = 7.0, 23.0

    def x(hr):
        hr = min(max(hr, lo_h), hi_h)
        return 100.0 * (hr - lo_h) / (hi_h - lo_h)
    ticks = range(int(lo_h) + 1, int(hi_h) + 1, 2)
    grid = "".join('<s style="left:%.2f%%"></s>' % x(t) for t in ticks)
    band = ('<u style="left:%.2f%%;width:%.2f%%" title="%s usual: %s to %s">'
            '</u>' % (x(team_in), x(team_out) - x(team_in), esc(e["dept"]),
                      clock(team_in), clock(team_out))) \
        if team_in is not None and team_out is not None \
        and team_out > team_in else ""
    out = ['<div class="rc-days">']
    cut = e.get("_cut")
    for day, s in days:
        try:
            label = datetime.strptime(day, "%Y-%m-%d").strftime("%a %d %b")
        except ValueError:
            label = day
        start = pd.Timestamp(s["first_in"])
        segs = []
        for o in sorted(s.get("outings") or [], key=lambda o: str(o[0])):
            try:
                a, b = pd.Timestamp(o[0]), pd.Timestamp(o[1])
            except (TypeError, ValueError, IndexError):
                continue
            if a > start:
                segs.append((start, a))
            start = b
        last = s.get("last_out")
        last = pd.Timestamp(last) if last is not None else None
        if last is not None and last > start:
            segs.append((start, last))
        bars = "".join(
            '<i style="left:%.2f%%;width:%.2f%%" title="%s: in %s, out %s">'
            '</i>' % (x(_hour(a)), max(0.8, x(_hour(b)) - x(_hour(a)) - 0.3),
                      esc(label), clock(_hour(a)), clock(_hour(b)))
            for a, b in segs)
        if last is None or last <= start:
            bars += ('<b style="left:%.2f%%" title="%s: in %s, no OUT punch">'
                     '</b>' % (x(_hour(start)), esc(label),
                               clock(_hour(start))))
        hrs = (s["inside_min"] / 60.0) if s.get("closed", True) \
            and s.get("inside_min") else None
        out.append('<div class="row"><span class="lab">%s</span><div class='
                   '"trk">%s%s%s</div><span class="hrs">%s</span></div>'
                   % (esc(label), grid, band, bars,
                      "%.1f h" % hrs if hrs is not None else
                      ("partial" if day == cut else "no OUT")))
    out.append('<div class="row ax"><span></span><div class="trk">%s</div>'
               '<span></span></div></div>' % "".join(
                   '<em style="left:%.2f%%">%02d:00</em>' % (x(t), t)
                   for t in ticks))
    return "".join(out)


def mates_html(e, emps, top=12):
    """The department's productivity, highest first, theirs marked -- the
    first `top` and theirs."""
    mates = sorted([x for x in emps if x["dept"] == e["dept"]
                    and x["productivity"] is not None],
                   key=lambda x: -x["productivity"])
    best = float(max([x["productivity"] for x in mates] or [1]))
    rows = []
    for i, x in enumerate(mates, 1):
        me = x["eid"] == e["eid"]
        if i > top and not me:
            continue
        rows.append('<div class="pf-bar%s"><span class="n">%d</span><span '
                    'class="w">%s</span><span class="b"><i style="width:%.1f%%">'
                    '</i></span><span class="v">%d</span></div>'
                    % (" me" if me else "", i, esc(x["name"]),
                       100.0 * x["productivity"] / best if best else 0,
                       x["productivity"]))
    return "".join(rows)


# -------------------------------------------------- where the day went

def _ts(x):
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(t) else t


def _places_for(e, day):
    """What places_day found for the employee on the day, where the board
    sends it (p["places"] for the focus day, p["places_days"] for totals):
    ({kind: minutes} or None, [(start, end, kind, name)] or None)."""
    p = e.get("board") or {}
    pl = p.get("places") or {}
    totals = ((p.get("places_days") or {}).get(day) or
              (pl.get("totals") if pl.get("day") == day else None))
    segs = pl.get("segments") if pl.get("day") == day else None
    if not segs:
        segs = (pl.get("by_day") or {}).get(day)     # every day's (27 Nov)
    return totals, segs


def day_options(e, now=None):
    """The days to look at, newest first: the machines' days in, the desk
    camera's, and today."""
    days = {d for d, _ in _days(e)}
    p = e.get("board") or {}
    days |= {r["day"] for r in p.get("history") or [] if r.get("day")
             and r.get("first") is not None and (r.get("desk_min") or 0) > 0}
    return sorted(days, reverse=True)


def default_day(e, days):
    """Which of day_options() to open on: the newest whole day -- not one
    the HR export cut mid-day (26 Nov: the card opened on Wednesday's
    stub, "In the building -- / not seen" over an empty line) -- with a
    closed day by the machines or desk minutes; else the newest."""
    days_ = e.get("days") or {}
    hist = {r.get("day"): r for r in (e.get("board") or {}).get("history")
            or []}
    for i, d in enumerate(days):
        if d == e.get("_cut"):
            continue
        if (days_.get(d) or {}).get("closed") or \
                (hist.get(d) or {}).get("desk_min"):
            return i
    return 0


def allocation(e, day):
    """Where one day went, in minutes, from what measured it: the machines
    (in the building, out of it, first in, last out), the desk camera (at
    the desk, of it on the computer / phone / talking) and places_day
    (meeting rooms, cafe, smoking, prayer) where they are known."""
    s = (e.get("days") or {}).get(day) or {}
    a = {"day": day, "first": _hour(s.get("first_in")),
         "last": _hour(s.get("last_out")) if s.get("closed") else None,
         "in": s["inside_min"] if s.get("closed") and s.get("inside_min")
         else None, "out": _out_min(s) if s else None,
         "desk": None, "computer": None, "phone": None, "talking": None,
         "places": None, "partial": day == e.get("_cut")}
    p = e.get("board") or {}
    h = next((r for r in p.get("history") or [] if r.get("day") == day),
             None)
    if h:
        a["desk"] = h.get("desk_min")
        if h.get("computer_min") is not None:
            a["computer"] = h.get("computer_min")
            a["phone"] = h.get("phone_min")
            a["talking"] = h.get("talking_min")
        if a["first"] is None and h.get("first") is not None:
            a["first"] = _hour(h["first"])
        if a["in"] is None and h.get("in_min"):
            a["in_cam"] = h.get("in_min")
    a["places"], _ = _places_for(e, day)
    return a


def shares(a):
    """[(kind, minutes)] for the allocation bar: the day in the building
    split by place -- at the desk, the places seen, the rest "in the
    building, place not seen" -- then out of the building."""
    total = a.get("in") or a.get("in_cam")
    out = []
    used = 0.0
    if a.get("places"):
        for kind, _ in PLACES:
            if kind in ("inside", "out", "unknown"):
                continue
            m = float(a["places"].get(kind) or 0.0)
            if kind == "desk" and not m and a.get("desk"):
                m = float(a["desk"])
            if m > 0:
                out.append((kind, m))
                used += m
    elif a.get("desk"):
        out.append(("desk", float(a["desk"])))
        used = float(a["desk"])
    if total:
        rest = max(0.0, float(total) - used)
        if rest > 0:
            out.append(("inside", rest))
    if a.get("out"):
        out.append(("out", float(a["out"])))
    return [(k, round(m, 1)) for k, m in out]


def day_line(e, day):
    """The day in one line, like a room's AC through the day: [(from,
    to, kind, words)] as clock hours. From places_day where it has the
    day; else today's desk camera line; else the machines' in and out."""
    _, segs = _places_for(e, day)
    out = []
    if segs:
        for g in segs:
            a, b = _ts(g[0]), _ts(g[1])
            if a is None or b is None or b <= a:
                continue
            kind = g[2] if g[2] in PLACE_LABEL else "inside"
            name = g[3] if len(g) > 3 and g[3] else PLACE_LABEL[kind]
            out.append((_hour(a), _hour(b), kind, name))
        if out:
            return out
    p = e.get("board") or {}
    f = p.get("focus") or {}
    if f.get("day") == day and f.get("segments"):
        for g in f["segments"]:
            a, b = _ts(g[0]), _ts(g[1])
            if a is None or b is None or b <= a:
                continue
            k = g[2]
            kind = ("desk" if k in ("desk", "computer", "phone", "talking")
                    else "out" if k in ("out", "left") else
                    "unknown" if k == "unwatched" else "inside")
            out.append((_hour(a), _hour(b), kind,
                        PLACE_LABEL[kind] + (" (%s)" % k if kind == "desk"
                                             and k != "desk" else "")))
        if out:
            return out
    s = (e.get("days") or {}).get(day)
    if not s or s.get("first_in") is None:
        return []
    start = _ts(s["first_in"])
    for o in sorted(s.get("outings") or [], key=lambda o: str(o[0])):
        a, b = _ts(o[0]), _ts(o[1])
        if a is None or b is None:
            continue
        if a > start:
            out.append((_hour(start), _hour(a), "inside",
                        PLACE_LABEL["inside"]))
        out.append((_hour(a), _hour(b), "out", PLACE_LABEL["out"]))
        start = b
    last = _ts(s.get("last_out"))
    if last is not None and last > start:
        out.append((_hour(start), _hour(last), "inside",
                    PLACE_LABEL["inside"]))
    return out


JOURNEY_MIN = 3.0        # a stop shorter than this joins its neighbours


def journey(e, day):
    """The day as stops in order (27 Nov, Shamroze: "main aaya to pehle
    kahan gaya -- desk par ya cafe mein -- aur wahan kitna time"): [{from,
    to, kind, name, min}] -- day_line's pieces, the same place running on
    joined, a blip under JOURNEY_MIN folded into the stop around it."""
    stops = []
    for a, b, kind, name in day_line(e, day):
        m = (b - a) * 60.0
        if stops and (stops[-1]["kind"] == kind
                      and stops[-1]["name"] == name
                      and a - stops[-1]["to"] <= JOURNEY_MIN / 60.0):
            stops[-1]["to"] = b
            stops[-1]["min"] = (b - stops[-1]["from"]) * 60.0
            continue
        stops.append({"from": a, "to": b, "kind": kind, "name": name,
                      "min": m})
    # fold blips into what was before them, then join again
    out = []
    for s in stops:
        if out and s["min"] < JOURNEY_MIN:
            out[-1]["to"] = max(out[-1]["to"], s["to"])
            out[-1]["min"] = (out[-1]["to"] - out[-1]["from"]) * 60.0
            continue
        if out and out[-1]["kind"] == s["kind"] \
                and out[-1]["name"] == s["name"]:
            out[-1]["to"] = s["to"]
            out[-1]["min"] = (s["to"] - out[-1]["from"]) * 60.0
            continue
        out.append(dict(s))
    return out


def journey_html(e, day):
    """The stops as a list: when, where, how long -- the first place they
    went after coming in said first, and a line of time for each."""
    st = journey(e, day)
    if not st:
        return ""
    s = (e.get("days") or {}).get(day) or {}
    came = _hour(s.get("first_in"))
    first = next((x for x in st if x["kind"] not in ("out", "unknown")),
                 st[0])
    # a camera that saw them in before the machines' first IN (a punch the
    # report has not got -- 26 Nov's morning -- or a door held open): the
    # earlier of the two is when they came
    by_cam = came is None or first["from"] < came
    if by_cam:
        came = first["from"]
    after = ("%s after coming in" % span((first["from"] - came) * 60.0)
             if not by_cam and first["from"] >= came else "")
    longest = max(x["min"] for x in st) or 1.0
    rows = "".join(
        '<div class="jy-row"><span class="jy-t">%s&ndash;%s</span>'
        '<i class="jy-d" style="background:%s"></i><span class="jy-n">%s'
        '</span><span class="jy-b"><i style="width:%.0f%%;background:%s">'
        '</i></span><span class="jy-m">%s</span></div>'
        % (clock(x["from"]), clock(x["to"]), colour(x["kind"]),
           esc(x["name"]), max(3.0, 100.0 * x["min"] / longest),
           colour(x["kind"]), span(x["min"])) for x in st)
    return ('<div class="ec-card rc-box jy"><h4>The day, stop by stop &middot; '
            '%s</h4><p class="jy-first">Came in %s%s &middot; first went to '
            '<b>%s</b>%s &middot; %d stop%s</p>%s<p class="pr-note">From the '
            'attendance machines, the desk camera and faces on the campus '
            'cameras; "in the building, place not seen" is time inside that '
            'no camera put a name to.</p></div>'
            % (esc(_day_label(day)), clock(came),
               " (first seen by camera)" if by_cam else "",
               esc(first["name"]),
               (" (%s)" % after) if after else "", len(st),
               "" if len(st) == 1 else "s", rows))


def _day_label(day):
    try:
        return datetime.strptime(day, "%Y-%m-%d").strftime("%a %d %b")
    except ValueError:
        return day


def overview_html(e, day):
    """Where the day went, for a CEO's glance (Shamroze, 26 Nov: "is poore
    din itne ghante isme guzare, itne isme ... aur score ye hai"): the day
    in four figures, the hours split by place as one bar with its totals,
    and the day in one line, from first in to last out."""
    a = allocation(e, day)
    parts = shares(a)
    line = day_line(e, day)
    total = sum(m for _, m in parts) or 1.0
    head = [("First in", clock(a["first"])),
            ("Last out", clock(a["last"]) if a["last"] is not None else
             ("partial day" if a["partial"] else "&ndash;")),
            ("In the building", span(a["in"]) if a.get("in") else
             (span(a["in_cam"]) + " (camera)" if a.get("in_cam")
              else "&ndash;")),
            ("At the desk", span(a["desk"]) if a.get("desk") else
             ("not seen" if not e.get("board") else "&ndash;")),
            ("Out of the building", span(a["out"]) if a.get("out")
             else "&ndash;")]
    bar = "".join('<i style="width:%.2f%%;background:%s" title="%s: %s"></i>'
                  % (100.0 * m / total, colour(k), PLACE_LABEL[k], span(m))
                  for k, m in parts if m > 0)
    legend = "".join('<span><i style="background:%s"></i>%s<b>%s</b></span>'
                     % (colour(k), PLACE_LABEL[k], span(m))
                     for k, m in parts if m > 0)
    if a.get("computer") is not None and a.get("desk"):
        legend += ('<span style="color:var(--t3)">at the desk: computer %s, '
                   'phone %s, talking %s</span>'
                   % (span(a["computer"]), span(a.get("phone") or 0),
                      span(a.get("talking") or 0)))
    lo, hi = 7.0, 23.0
    for f_, t_, _, _ in line:
        lo, hi = min(lo, math.floor(f_)), max(hi, math.ceil(t_))
    lo, hi = max(0.0, lo), min(24.0, hi)

    def x(h):
        return 100.0 * (min(max(h, lo), hi) - lo) / (hi - lo)
    segs = "".join(
        '<i style="left:%.2f%%;width:%.2f%%;background:%s" title="%s to %s: '
        '%s"></i>' % (x(f_), max(0.4, x(t_) - x(f_)), colour(k), clock(f_),
                      clock(t_), esc(w)) for f_, t_, k, w in line)
    ticks = "".join('<em style="left:%.2f%%">%02d:00</em>' % (x(t), t)
                    for t in range(int(lo) + 1, int(hi), 2))
    src = "the attendance machines"
    if e.get("board"):
        src += " and the desk camera"
    if a.get("places"):
        src += ", and the cameras around the building for the places"
    return ('<div class="ec-card rc-box"><h4>Where the day went &middot; %s%s'
            '</h4><div class="ov-head">%s</div>%s%s<div class="ov-line" '
            'role="img" aria-label="The day in one line">%s</div><div class='
            '"ov-ax">%s</div><div class="pr-note" style="margin-top:2px">From '
            '%s. Hover the line for each stretch.</div></div>'
            % (_day_label(day), " (partial: the export ends mid-day)"
               if a["partial"] else "",
               "".join('<div><span>%s</span><b>%s</b></div>' % (k, v)
                       for k, v in head),
               '<div class="ov-alloc" role="img" aria-label="Hours by place">'
               '%s</div>' % bar if parts else "",
               '<div class="ov-lg">%s</div>' % legend if legend else "",
               segs, ticks, src))


# ------------------------------------------------ one against another

# ---------------------------------------------------------- ways of working
#
# 27 Nov (Shamroze: "Harvard, Oxford, Tesla, Microsoft ... kya miss kar
# rahe ho"): what Microsoft Viva Insights shows a manager and we did not --
#   focus hours a week   Viva: blocks of 2 h+ without meetings; people who
#                        are not managers do best with 12 h+ a week
#                        (Workplace Patterns report). Ours: time at the
#                        desk in stretches of an hour or more (the cameras).
#   meeting hours a week Viva's "collaboration hours" -- here the meeting
#                        rooms a face put them in (places_day).
#   hours a week         Viva counts after-hours work against each person's
#                        set hours; Disrupt's timing is flexible, 24/7
#                        (Shamroze, 27 Nov), so the hours themselves:
#                        past 50 a week is Gallup's burn-out line.
# Shown beside the team, never added to the score (a long day is no
# credit), and the team's count past 50 h a week is a wellbeing sign for
# the manager, as Viva's after-hours count is.
FOCUS_GOOD_H = 12.0
WEEK_RISK_H = 50.0       # Gallup's burn-out line, as LONG_DAY_H a day


def ways(e, hours=(10.0, 20.0)):
    """{focus_h, meeting_h, week_h} a week (5 working days) or None
    each where not measured."""
    out = {"focus_h": None, "meeting_h": None, "week_h": None}
    p = e.get("board") or {}
    longs = [float(d.get("long_min") or 0) for d in p.get("days") or []
             if d.get("first") is not None and d.get("long_min") is not None]
    if longs:
        out["focus_h"] = 5.0 * sum(longs) / len(longs) / 60.0
    pd_ = p.get("places_days") or {}
    if pd_:
        out["meeting_h"] = 5.0 * sum(float((v or {}).get("meeting") or 0)
                                     for v in pd_.values()) / len(pd_) / 60.0
    # Hours in the building a week, whatever the clock (the timing is
    # flexible, 24/7: Shamroze, 27 Nov) -- Viva's after-hours count has no
    # meaning where there are no fixed hours; the hours themselves do.
    closed = [s for _, s in _work(e) if s.get("closed")
              and s.get("inside_min")]
    if closed:
        out["week_h"] = 5.0 * sum(float(s["inside_min"]) for s in closed) \
            / len(closed) / 60.0
    return out


def ways_html(e, emps, hours=(10.0, 20.0)):
    """Their ways of working beside the team's usual (the median)."""
    me = ways(e, hours)
    mates = [x for x in emps if x["dept"] == e["dept"] and x["eid"] != e["eid"]]
    theirs = [ways(x, hours) for x in mates]

    def team(k):
        vals = [w[k] for w in theirs if w[k] is not None]
        return median(vals) if vals else None
    risk = sum(1 for w in theirs + [me] if (w["week_h"] or 0) > WEEK_RISK_H)
    n_week = sum(1 for w in theirs + [me] if w["week_h"] is not None)

    def h(v):
        return "&ndash;" if v is None else "%.1f h" % v
    tiles = [
        ("Focus time, a week", h(me["focus_h"]),
         "at the desk in stretches of an hour+ &middot; team %s &middot; "
         "Microsoft finds 12 h+ best" % h(team("focus_h"))
         if me["focus_h"] is not None else "no camera reads their desk"),
        ("Meetings, a week", h(me["meeting_h"]),
         "in the meeting rooms, by face &middot; team %s"
         % h(team("meeting_h")) if me["meeting_h"] is not None
         else "not seen in a meeting room yet"),
        ("Hours in the building, a week", h(me["week_h"]),
         "team %s &middot; past 50 h a week is Gallup's burn-out line"
         % h(team("week_h")) if me["week_h"] is not None
         else "no whole day yet"),
        ("In the team, past 50 h a week", "%d of %d" % (risk, n_week)
         if n_week else "&ndash;",
         "a wellbeing sign for the manager, as Microsoft Viva shows it")]
    return ('<div class="ec pr"><div class="ec-h" style="margin-top:14px">'
            '<span class="t">Ways of working</span><span class="c">as '
            'Microsoft Viva Insights shows them &middot; beside the team, '
            'not part of the score</span></div>%s</div>' % prv._kpis(tiles))


def team_usual(e, emps):
    """The team as one person -- each factor its median -- to compare with
    when no colleague is picked."""
    mates = [x for x in emps if x["dept"] == e["dept"] and x["eid"] != e["eid"]]
    f = {}
    for key, _, _, _, _ in FACTORS:
        vals = [x["f"][key] for x in mates if x["f"].get(key) is not None]
        f[key] = median(vals) if vals else None

    def avg(k):
        vals = [x[k] for x in mates if x.get(k) is not None]
        return sum(vals) / float(len(vals)) if vals else None
    p = avg("productivity")
    return {"eid": "_team", "name": "%s's usual" % e["dept"], "role": "",
            "dept": e["dept"], "photo": "", "f": f,
            "productivity": int(round(p)) if p is not None else None,
            "attendance": avg("attendance"), "desk": avg("desk"),
            "activity": avg("activity"), "board": None}


def _points_of(e):
    """Each factor's share of the employee's score, in points."""
    parts = {"attendance": e.get("attendance"), "desk": e.get("desk"),
             "activity": e.get("activity")}
    total = sum(PART_W[k] for k, v in parts.items() if v is not None) or 1.0
    out = {}
    for key, (part, w, s) in IN_SCORE.items():
        v = e["f"].get(key)
        if v is None or parts.get(part) is None:
            continue
        out[key] = PART_W[part] / total * w * s(v)
    return out


def pair(a, b):
    """a against b, factor by factor: [(key, a value, b value, who is
    better: "a" | "b" | "")] for the factors both have, and the factors
    that make the gap in their scores, biggest first: [(key, points)]."""
    rows = []
    for key, _, _, better, _ in FACTORS:
        va, vb = a["f"].get(key), b["f"].get(key)
        if va is None or vb is None:
            continue
        d = (va - vb) * better
        who = "" if abs(va - vb) < MARGIN[key] / 2.0 else (
            "a" if d > 0 else "b")
        if key == "hours" and max(va, vb) > LONG_DAY_H:
            who = ""         # a long day is no credit (wellbeing, Microsoft)
        rows.append((key, va, vb, who))
    pa, pb = _points_of(a), _points_of(b)
    gap = [(k, pa[k] - pb[k]) for k in pa if k in pb]
    sign = 1 if (a.get("productivity") or 0) >= (b.get("productivity") or 0) \
        else -1
    gap = sorted([g for g in gap if g[1] * sign > 0.5],
                 key=lambda g: -abs(g[1]))
    return rows, gap


def _diff_words(key, va, vb):
    if key == "hours":
        return "%+.1f h" % (va - vb)
    if key == "arrival":
        m = (va - vb) * 60
        return "%s %s" % (span(m), "later" if m > 0 else "earlier") \
            if abs(m) >= 1 else "same"
    if key == "out":
        return "%+d min" % round(va - vb)
    return "%+d points" % round(va - vb)


def pair_html(a, b):
    """a and b side by side (Shamroze, 26 Nov: "X same department ke Y se
    kyun behtar hai, din mein aisa kya kiya"): both scores, a sentence on
    what makes the gap, and every factor both have, the better marked."""
    rows, gap = pair(a, b)
    pa, pb = a.get("productivity"), b.get("productivity")
    an, bn = esc(a["name"].split(" ")[0]), esc(b["name"])
    if pa is None or pb is None:
        say_ = "Not enough measured to compare their scores."
    elif abs(pa - pb) < 2:
        say_ = "<b>%s</b> and %s score about the same." % (an, bn)
    else:
        ahead, behind = (an, bn) if pa > pb else (bn, an)
        why_ = ", ".join("%s (%+.0f points)" % (LABEL[k].lower(),
                                                abs(p_))
                         for k, p_ in gap[:3])
        say_ = ("<b>%s</b> is <b>%d points</b> ahead of %s%s." % (
            ahead, abs(pa - pb), behind,
            ", mostly from %s" % why_ if why_ else ""))
    # what each does differently in the day -- the better one named, the
    # better way said (earlier in; less out, on the phone, talking)
    verbs = {"arrival": "comes in %s earlier",
             "out": "is out of the building %s a day less",
             "talking": "talks at the desk %s less",
             "phone": "is on the phone %s less"}

    def by(k, va, vb):
        d = abs(va - vb)
        return (span(d * 60) if k == "arrival" else "%d min" % round(d)
                if k == "out" else "%d points" % round(d))
    extra = [r for r in rows if r[0] in verbs and r[3]]
    if extra:
        say_ += " " + " ".join(
            "%s %s." % (an if r[3] == "a" else bn,
                        verbs[r[0]] % by(r[0], r[1], r[2]))
            for r in extra[:3])
    trs = "".join(
        '<tr><td class="l">%s</td><td class="%s">%s</td><td class="%s">%s'
        '</td><td class="w">%s</td></tr>'
        % (esc(LABEL[k]), "a" if w == "a" else "", _fmt(k, va),
           "a" if w == "b" else "", _fmt(k, vb),
           ('<b class="%s">%s better</b> &middot; ' % (
               "up" if w == "a" else "dn", an if w == "a" else
               esc(b["name"].split(" ")[0]))) + _diff_words(k, va, vb)
           if w else ("%s &middot; past 10&frac12; h a day is no credit"
                      % _diff_words(k, va, vb)
                      if k == "hours" and max(va, vb) > LONG_DAY_H
                      else "about the same"))
        for k, va, vb, w in rows)
    return ('<div class="ec-card rc-box"><h4>Compared with a colleague</h4>'
            '<div class="rc-vs" style="margin-top:8px">%s<div class="who"><b>'
            '%s</b><span>%s</span></div><b class="n">%s</b><span class="vs">'
            'against</span><b class="n" style="color:var(--t2)">%s</b><div '
            'class="who"><b>%s</b><span>%s</span></div>%s</div><div class='
            '"rc-say">%s</div><table class="pair"><thead><tr><th class="l">'
            '</th><th>%s</th><th>%s</th><th class="l">difference</th></tr>'
            '</thead><tbody>%s</tbody></table></div>'
            % (prv._photo(a), esc(a["name"]), esc(a.get("role") or ""),
               "%d" % pa if pa is not None else "-",
               "%d" % pb if pb is not None else "-", bn,
               esc(b.get("role") or ""),
               prv._photo(b) if b.get("eid") != "_team" else "",
               say_, an, esc(b["name"].split(" ")[0]) if b.get("eid") !=
               "_team" else "team", trs or '<tr><td class="l" colspan="4">'
               'No factor measured for both.</td></tr>'))


# ------------------------------------------------------------ the report

def _rank(e, emps):
    mates = [x for x in emps if x["dept"] == e["dept"]]
    ranked = sorted([x for x in mates if x["productivity"] is not None],
                    key=lambda x: -x["productivity"])
    return next((i for i, x in enumerate(ranked, 1) if x["eid"] == e["eid"]),
                None), len(ranked)


def head_html(e, emps, now=None, hours=(10.0, 20.0), last_day=None,
              crew=False):
    """Who, the score on average and today so far, their place in the
    team, why, and their usual against the team's -- the card's top."""
    comps = compare(e, emps)
    td = today(e, now, hours, last_day)
    rank, of = _rank(e, emps)
    mates = [x for x in emps if x["dept"] == e["dept"]]

    def team_median(key):
        vals = [x[key] for x in mates if x.get(key) is not None]
        return median(vals) if vals else None
    t_in, t_out, t_h = (team_median("usual_in"), team_median("usual_out"),
                        team_median("hours"))
    n_days = len(_work(e))
    measured = "attendance machines, %d working day%s" % (
        n_days, "" if n_days == 1 else "s")
    if e.get("desk") is not None:
        measured += " &middot; desk camera, %d day%s" % (
            e.get("desk_days") or 0, "" if e.get("desk_days") == 1 else "s")

    def tile(k, v, s):
        return ('<div class="ec-card ec-kpi"><div class="k">%s</div><div '
                'class="v">%s</div><div class="s">%s</div></div>' % (k, v, s))
    f = e.get("f") or {}
    fourth = tile("At the desk", _fmt("desk", f.get("desk")),
                  "of the office day &middot; camera") \
        if f.get("desk") is not None else \
        tile("Days present", "%s/%s" % (e.get("days_in") or 0,
                                       e.get("of") or "-"),
             "working days")
    p = e.get("productivity")
    word = "workforce score" if crew else "productivity"
    return "".join([
        '<div class="ec pr">',
        '<div class="ec-card rc-head">%s<div><h3>%s</h3><p>%s</p><p class="m">'
        '%s &middot; %s &middot; ID %s</p><p class="m">Measured by: %s</p>'
        '</div><div class="rc-big"><div><b>%s</b><span>%s, average</span>'
        '</div><div><b class="td">%s</b><span>today so far</span></div>'
        '<div><b class="td">%s</b><span>in %s (%d)</span></div></div></div>'
        % (prv._photo(e), esc(e["name"]), esc(e["role"]),
           esc(e.get("home_dept") or e["dept"]), esc(e["bu"]),
           esc(str(e["id"])), measured, "%d" % p if p is not None else "-",
           word, "%d" % td["score"] if td["score"] is not None else "&ndash;",
           prv._ord(rank) if rank else "-", esc(e["dept"]), of),
        '<div class="rc-why">%s</div>' % why(e, comps, emps),
        '<div class="pr-kpis k4">%s%s%s%s</div>' % (
            tile("Usual arrival", clock(e.get("usual_in")),
                 "team %s" % clock(t_in)),
            tile("Usual leaving", clock(e.get("usual_out")),
                 "team %s" % clock(t_out)),
            tile("In the building", "%.1f h" % e["hours"]
                 if e.get("hours") is not None else "&ndash;",
                 "a day &middot; team %s" % ("%.1f h" % t_h
                                              if t_h is not None
                                              else "&ndash;")),
            fourth),
        '</div>'])


def points_html(e, emps):
    """Strong and weak points against the team, and the early signs."""
    import overview
    comps = compare(e, emps)
    strong, weak = points(e, comps)
    sig = signals(e)

    def bullets(cs, empty):
        if not cs:
            return '<p class="none">%s</p>' % empty
        return "<ul>%s</ul>" % "".join("<li>%s</li>" % say(c, e) for c in cs)
    return "".join([
        '<div class="ec pr"><div class="rc-pts"><div class="ec-card"><h4>%s'
        'Strong points</h4>%s</div><div class="ec-card"><h4>%sWeak points'
        '</h4>%s</div></div>'
        % (overview.TICK, bullets(strong, "Nothing clearly above the team "
                                  "yet."),
           overview.WARN, bullets(weak, "Nothing clearly below the team.")),
        '<div class="rc-sig">%s</div></div>' % "".join(
            '<span>%s%s</span>' % (overview.TICK if lv == "good"
                                   else overview.WARN, txt)
            for lv, txt in sig)])


def details_html(e, emps, now=None, hours=(10.0, 20.0), last_day=None):
    """The detail behind the card, a click away: the team factor by factor,
    every day by the machines, today so far, the colleagues, the sources."""
    comps = compare(e, emps)
    td = today(e, now, hours, last_day)
    mates = [x for x in emps if x["dept"] == e["dept"]]

    def team_median(key):
        vals = [x[key] for x in mates if x.get(key) is not None]
        return median(vals) if vals else None
    t_in, t_out = team_median("usual_in"), team_median("usual_out")
    first = esc(e["name"].split(" ")[0])
    return "".join([
        '<div class="ec pr">',
        '<div class="ec-card rc-box"><h4>Against the team, factor by factor'
        '</h4><div class="rc-lg"><span><i style="background:var(--accent)">'
        '</i>%s</span><span><i style="background:var(--t3);opacity:.45"></i>'
        'colleagues (hover a dot for who)</span><span><i class="tk" style="'
        'background:var(--t1)"></i>the team\'s usual</span></div>%s</div>'
        % (first, strip_html(comps, e)),
        '<div class="ec-card rc-box"><h4>Their days by the attendance machines'
        '</h4><div class="rc-lg"><span><i class="sq" style="background:'
        'var(--accent)"></i>in the building (gaps: out and back)</span><span>'
        '<i class="sq" style="background:var(--s2)"></i>%s\'s usual hours'
        '</span></div>%s</div>'
        % (esc(e["dept"]), days_html(e, t_in, t_out) or
           '<p class="pr-note">No punch at %s in the export.</p>'
           % esc(e.get("campus") or "140-H")),
        '<div class="rc-two"><div class="ec-card"><h4 style="margin:0">Today '
        'so far</h4><div class="rc-today">%s</div>%s</div>'
        '<div class="ec-card"><h4 style="margin:0">With colleagues in %s</h4>'
        '<div class="pr-sub">highest first &mdash; theirs marked'
        '</div><div class="pf-bars">%s</div></div></div>'
        % ("".join('<div><span>%s</span><b>%s</b></div>' % (k, v)
                   for k, v in td["facts"]),
           '<div class="pr-note" style="margin-top:6px">%s</div>' % td["note"]
           if td["note"] else "", esc(e["dept"]), mates_html(e, emps)),
        '<div class="pr-note">%s</div>' % SOURCES,
        '</div>'])


def report_html(mode, e, emps, now=None, hours=(10.0, 20.0), last_day=None,
                other=None, day=None, crew=False):
    """The whole card at once (the page shows it in parts, with a day and
    a colleague to pick): the top, where a day went, against a colleague
    (else the team's usual), strong and weak points, and the detail."""
    days = day_options(e, now)
    day = day or (days[0] if days else None)
    return "".join([
        styles(mode), head_html(e, emps, now, hours, last_day, crew),
        '<div class="ec pr">%s</div>' % overview_html(e, day) if day else "",
        '<div class="ec pr">%s</div>' % pair_html(e, other or
                                                  team_usual(e, emps)),
        points_html(e, emps), details_html(e, emps, now, hours, last_day)])
