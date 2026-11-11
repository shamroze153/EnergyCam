"""The front of the dashboard: both campuses, then one campus at a glance.

Chosen by Shamroze from three drawn options on 11 November ("Option A"): a
dark page, the numbers people ask for first set large, a chart of the day,
the departments as cards with when they came in and when they left, and the
rooms underneath -- the outside last, and never counted as people inside.

Nothing here touches Streamlit or the database. rooms_dashboard.py hands in
what it has already loaded and graded and gets back HTML, so the arithmetic
can be tested without either, and a room is empty or busy by the same rules
on this page as on every other.

The HTML is written to be inserted as it is, without scripts. Hover still
works: every quarter hour of a chart is its own target with a title the
browser shows, and the column under the pointer lights up in CSS. Words and
dots sit in HTML laid over the SVG rather than inside it, because the SVG
stretches to whatever width the screen has, and text inside it would be
stretched with it -- on a phone, into something nobody could read.
"""
import html as _html
from urllib.parse import urlencode

import pandas as pd

import day_story as ds
from campus_view import OUTSIDE_ZONES

LOCAL = "Asia/Karachi"

# Where people work, as opposed to where they pass through. A room in one of
# these with no department written against it is its own department: at
# 140-H the rooms already carry the department's name (Marketing, HR Room,
# AutoOS), and lumping them all under "Offices" would say nothing.
WORK_ZONES = {"Offices", "H offices", "Basement"}
SERVER_ZONES = {"Server rooms"}

SLOT = 15                       # minutes in one column of a chart
SLOTS = 24 * 60 // SLOT
BUCKETS = ("1", "2–3", "4–6", "7+")

# Two palettes, one set of meanings. The people ramp is one hue, light to
# dark on light and dark to light on dark, so "more people" is always the
# step that stands further out from the card. Both were run through the
# dataviz validator as ordinal ramps against these exact card colours, and
# pass. Red is reserved for one thing -- an empty room with a unit to check
# -- and always comes with a mark and words, never as colour alone.
TOKENS = {
    "dark": {
        "page": "#0d0d0d", "s1": "#171716", "s2": "#1f1f1d",
        "line": "rgba(255,255,255,.08)", "line2": "rgba(255,255,255,.15)",
        "t1": "#f0efec", "t2": "#c3c2b7", "t3": "#898781",
        "accent": "#3987e5", "wash": "rgba(57,135,229,.16)",
        "out": "#6b6a64", "grid": "rgba(255,255,255,.06)",
        "axis": "rgba(255,255,255,.2)", "now": "rgba(255,255,255,.45)",
        "hover": "rgba(255,255,255,.06)",
        "tariff": "rgba(250,178,25,.07)", "tariff_key": "rgba(250,178,25,.4)",
        "crit": "#d03b3b", "crit_bg": "rgba(208,59,59,.10)",
        "crit_line": "rgba(208,59,59,.38)",
        "good": "#0ca30c", "good_ring": "rgba(12,163,12,.18)",
        "warn": "#fab219",
        "ramp": ["#262624", "#1c5cab", "#2a78d6", "#6da7ec", "#b7d3f6"],
        "unwatched": "#121211", "future": "#1d1d1b", "pill_bg":
        "rgba(57,135,229,.16)", "pill_fg": "#b7d3f6", "invert": "#0b0b0b",
        "shadow": "0 1px 0 rgba(255,255,255,.03) inset",
    },
    "light": {
        "page": "#f4f4f1", "s1": "#fcfcfb", "s2": "#f0efec",
        "line": "rgba(11,11,11,.08)", "line2": "rgba(11,11,11,.15)",
        "t1": "#0b0b0b", "t2": "#52514e", "t3": "#898781",
        "accent": "#2a78d6", "wash": "rgba(42,120,214,.12)",
        "out": "#b3b1a8", "grid": "rgba(11,11,11,.06)",
        "axis": "rgba(11,11,11,.22)", "now": "rgba(11,11,11,.45)",
        "hover": "rgba(11,11,11,.05)",
        "tariff": "rgba(250,178,25,.12)", "tariff_key": "rgba(250,178,25,.5)",
        "crit": "#d03b3b", "crit_bg": "rgba(208,59,59,.06)",
        "crit_line": "rgba(208,59,59,.35)",
        "good": "#0ca30c", "good_ring": "rgba(12,163,12,.15)",
        "warn": "#fab219",
        "ramp": ["#e9e8e3", "#86b6ef", "#3987e5", "#256abf", "#184f95"],
        "unwatched": "#f7f6f3", "future": "#efeee9",
        "pill_bg": "rgba(42,120,214,.12)", "pill_fg": "#184f95",
        "invert": "#ffffff",
        "shadow": "0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(40,30,10,.05)",
    },
}


# ===================================================================== figures

def department_of(name, zone, dept):
    """Whose space a room is, when several rooms are read as one.

    Outside is nobody's department and is never counted. A room with a
    department written against it in rooms.yaml belongs to that department.
    A working room without one is its own department, under its own name. A
    lobby, a cafe or a corridor without one is grouped by its zone, because
    those belong to everyone.
    """
    if zone in OUTSIDE_ZONES:
        return None
    if dept:
        return dept
    if zone in WORK_ZONES:
        return name
    return zone


def bucket(v):
    """People to a step of the ramp: -1 unwatched, 0 empty, 1..4 busier."""
    if v is None:
        return -1
    if v < 0.5:
        return 0
    if v < 1.5:
        return 1
    if v < 3.5:
        return 2
    if v < 6.5:
        return 3
    return 4


def add_up(series):
    """Minute by minute, the sum across rooms; None only where every one is."""
    out = [None] * 1440
    for values in series:
        for i, v in enumerate(values):
            if v is not None:
                out[i] = (out[i] or 0) + v
    return out


def quarters(minutes):
    """1440 minutes to 96 quarter-hour averages; None where nobody looked."""
    out = []
    for i in range(SLOTS):
        seen = [v for v in minutes[i * SLOT:(i + 1) * SLOT] if v is not None]
        out.append(sum(seen) / float(len(seen)) if seen else None)
    return out


def _minutes_since(when, now):
    if when is None or pd.isna(when):
        return None
    return max(0, int((now - pd.Timestamp(when)).total_seconds() // 60))


def campus_summary(name, rooms, history, beats, now, stake=0.0,
                   stake_note="", live=True):
    """Everything the two front pages say about one campus.

    rooms: one row per room of the campus, as the dashboard has them after
        grading -- room, zone, dept, has_unit, alerts, status, people,
        empty_since, occupied_since, level, headline, sub.
    history: room_events rows (timestamp, room, status, people) reaching
        back to at least yesterday's midnight.
    beats: heartbeat timestamps over the same stretch; None to treat every
        minute as watched.
    stake: rupees at stake today, worked out by the dashboard the way it
        always has been, so this page and the others cannot disagree.
    """
    local = now.tz_convert(LOCAL)
    today = local.normalize()
    yday = today - pd.Timedelta(days=1)
    if len(history):
        by_room = {n: g for n, g in history.groupby("room")}
        none = history.iloc[0:0]
    else:
        by_room = {}
        none = pd.DataFrame(columns=["timestamp", "room", "status", "people"])

    entries = []
    for _, r in rooms.iterrows():
        zone = r.get("zone") or "Other"
        if zone == "Unused":
            continue
        status = r.get("status")
        status = status if isinstance(status, str) else "unknown"
        people = r.get("people")
        people = (int(people) if status == "occupied" and pd.notna(people)
                  else 0)
        since = (r.get("occupied_since") if status == "occupied"
                 else r.get("empty_since"))
        day = ds.spells(by_room.get(r["room"], none), today, now, beats)
        entries.append({
            "name": r["room"], "zone": zone,
            "dept": department_of(r["room"], zone, r.get("dept") or ""),
            "outside": zone in OUTSIDE_ZONES, "work": zone in WORK_ZONES,
            "server": zone in SERVER_ZONES,
            "status": status, "people": people,
            "since": _minutes_since(since, now),
            "level": r.get("level") or "Green",
            "headline": r.get("headline") or "",
            "sub": r.get("sub") or "",
            "ac": r.get("ac"), "has_unit": bool(r.get("has_unit")),
            "day": day, "minutes": ds.by_minute(day, today),
        })

    inside = [e for e in entries if not e["outside"]]
    outside = [e for e in entries if e["outside"]]
    total = add_up(e["minutes"] for e in inside)
    peak, peak_at = 0, None
    for i, v in enumerate(total):
        if v is not None and v > peak:
            peak, peak_at = v, today + pd.Timedelta(minutes=i)

    groups = {}
    for e in inside:
        groups.setdefault(e["dept"], []).append(e)
    depts = []
    for dept, members in groups.items():
        day = ds.combine([m["day"] for m in members])
        story = ds.story(day, today)
        busy = sum(1 for m in members if m["status"] == "occupied")
        depts.append({
            "name": dept, "rooms": len(members), "busy": busy,
            "people": sum(m["people"] for m in members),
            "starts": story["starts"], "first_in": story["first_in"],
            "carried": story["carried"],
            "last_out": None if busy else story["last_out"],
            "still_in": bool(busy),
            "peak": story["peak"], "peak_at": story["peak_at"],
            "slots": quarters(ds.by_minute(day, today)),
            "work": any(m["work"] for m in members),
            "server": all(m["server"] for m in members),
            "walk": sum(1 for m in members if m["level"] in ("Red", "Amber")),
            "silent": sum(1 for m in members if m["status"] == "unknown"),
            "members": [m["name"] for m in members],
        })
    depts.sort(key=lambda d: (not d["work"], d["server"], -d["people"],
                              d["starts"] is None,
                              d["starts"] or today, d["name"]))

    # Who opened the campus: the first department to start its day, not the
    # first camera to see anybody -- the cleaner at seven and the guard at
    # the gate are not the day starting. Somebody in since last night is not
    # an arrival either.
    opened = [d for d in depts if d["work"] and d["starts"] is not None
              and not d["carried"]]
    first = min(opened, key=lambda d: d["starts"]) if opened else None

    # When yesterday ended: the last working room to empty. Somebody still
    # in at midnight means it did not end, and the page says that instead.
    lefts, overnight = [], False
    for e in inside:
        if not e["work"]:
            continue
        day = ds.spells(by_room.get(e["name"], none), yday, today, beats)
        story = ds.story(day, yday)
        if story["last_out"] is None:
            continue
        if story["last_out"] >= today - pd.Timedelta(minutes=1):
            overnight = True
        else:
            lefts.append(story["last_out"])

    rank = {"Red": 0, "Amber": 1}
    walk = sorted((e for e in inside if e["level"] in rank),
                  key=lambda e: (rank[e["level"]], -(e["since"] or 0)))
    silent = [e for e in inside if e["status"] == "unknown"]
    return {
        "name": name, "live": live,
        "inside_now": sum(e["people"] for e in inside),
        "outside_now": sum(e["people"] for e in outside),
        "rooms_busy": sum(1 for e in inside if e["status"] == "occupied"),
        "rooms_total": len(inside),
        "curve_in": quarters(total),
        "curve_out": quarters(add_up(e["minutes"] for e in outside)),
        "peak": int(round(peak)), "peak_at": peak_at,
        "first_in": first["starts"] if first else None,
        "first_who": first["name"] if first else None,
        "last_out_yday": max(lefts) if lefts else None,
        "overnight": overnight,
        "stake": stake, "stake_note": stake_note,
        "walk": walk, "silent": silent,
        "depts": depts,
        "rooms": entries,
        "now": now, "today": today,
    }


# ===================================================================== drawing

def esc(text):
    return _html.escape(str(text), quote=True)


def clock(ts):
    """9:06 morning -- the way the rest of the dashboard says a time."""
    return "—" if ts is None or pd.isna(ts) else ds.clock(ts)


def ago(minutes):
    if minutes is None:
        return "—"
    if minutes < 60:
        return "%dm" % minutes
    h, m = divmod(minutes, 60)
    if h >= 48:
        return "%dd" % (h // 24)
    return "%dh" % h if h >= 10 or not m else "%dh %02dm" % (h, m)


def rupees(n):
    return "Rs %s" % format(int(round(n or 0)), ",")


def short(name):
    """Room names without the campus they are already inside."""
    for prefix in ("141 ", "140-H "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def link(base, **extra):
    """A link to this page with different settings; nothing else changes."""
    params = {k: v for k, v in dict(base, **extra).items() if v}
    return "?" + urlencode(params) if params else "?"


def now_slot(summary):
    local = summary["now"].tz_convert(LOCAL)
    return min(SLOTS - 1, (local.hour * 60 + local.minute) // SLOT)


def slot_clock(i):
    h, m = divmod(i * SLOT, 60)
    return "%d:%02d %s" % (h % 12 or 12, m, ds.part_of(h))


HOUR_TICKS = [(0, "12 night", ""), (3, "3", " minor"), (6, "6 morning", ""),
              (9, "9", " minor"), (12, "noon", ""), (15, "3", " minor"),
              (18, "6 evening", ""), (21, "9", " minor"), (24, "12 night", "")]


def _nice(top):
    step = 5 if top <= 20 else 10 if top <= 50 else 25 if top <= 120 else 50
    return step, max(step, -(-int(top) // step) * step)


def area_chart(summary, t, height=240, compact=False, tariff=(74, 90),
               outside=True):
    """People through the day: the office as a filled line, outside thin."""
    inside = summary["curve_in"]
    out = summary["curve_out"] if outside else None
    now = now_slot(summary)
    seen = [v for v in inside[:now + 1] if v is not None]
    seen_out = [v for v in (out or [])[:now + 1] if v is not None]
    step, top = _nice(max([4.0] + seen + seen_out))

    def y(v):
        return 100.0 * (1 - v / float(top))

    svg = ['<svg viewBox="0 0 96 100" preserveAspectRatio="none" '
           'aria-hidden="true">']
    if tariff and not compact:
        svg.append('<rect x="%s" y="0" width="%s" height="100" fill="%s"/>'
                   % (tariff[0], tariff[1] - tariff[0], t["tariff"]))
    if not compact:
        for v in range(0, top + 1, step):
            svg.append('<line x1="0" x2="96" y1="%.2f" y2="%.2f" stroke="%s" '
                       'stroke-width="1" vector-effect="non-scaling-stroke"/>'
                       % (y(v), y(v), t["axis"] if v == 0 else t["grid"]))
    runs, run = [], []
    for i, v in enumerate(inside[:now + 1]):
        if v is None:
            if run:
                runs.append(run)
            run = []
        else:
            run.append((i, v))
    if run:
        runs.append(run)
    for run in runs:
        pts = " ".join("%.2f,%.2f" % (i + .5, y(v)) for i, v in run)
        svg.append('<polygon points="%.2f,100 %s %.2f,100" fill="%s"/>'
                   % (run[0][0] + .5, pts, run[-1][0] + .5, t["wash"]))
        svg.append('<polyline points="%s" fill="none" stroke="%s" '
                   'stroke-width="2" stroke-linejoin="round" '
                   'stroke-linecap="round" '
                   'vector-effect="non-scaling-stroke"/>' % (pts, t["accent"]))
    if out:
        pts = " ".join("%.2f,%.2f" % (i + .5, y(v))
                       for i, v in enumerate(out[:now + 1]) if v is not None)
        if pts:
            svg.append('<polyline points="%s" fill="none" stroke="%s" '
                       'stroke-width="1.5" stroke-linejoin="round" '
                       'vector-effect="non-scaling-stroke"/>' % (pts, t["out"]))
    svg.append('<line x1="%.2f" x2="%.2f" y1="0" y2="100" stroke="%s" '
               'stroke-width="1" vector-effect="non-scaling-stroke"/>'
               % (now + .5, now + .5, t["now"]))
    if not compact:
        # One target per quarter hour, each with its own reading. The
        # browser shows the title on hover; CSS lights the column.
        for i in range(now + 1):
            v = inside[i]
            o = out[i] if out else None
            if v is None:
                tip = "%s · nobody watching" % slot_clock(i)
            else:
                tip = "%s · %d in the office" % (slot_clock(i), round(v))
                if o is not None:
                    tip += ", %d outside" % round(o)
            svg.append('<rect class="hit" x="%d" y="0" width="1" '
                       'height="100"><title>%s</title></rect>' % (i, esc(tip)))
    svg.append("</svg>")

    last = next((v for v in reversed(inside[:now + 1]) if v is not None), 0)
    marks = ['<span class="dot" style="left:%.3f%%;top:%.3f%%"></span>'
             % (100 * (now + .5) / 96, y(last))]
    if not compact:
        if seen:
            pi = max(range(now + 1),
                     key=lambda i: -1 if inside[i] is None else inside[i])
            if inside[pi]:
                marks.append('<span class="dot" style="left:%.3f%%;'
                             'top:%.3f%%"></span>'
                             % (100 * (pi + .5) / 96, y(inside[pi])))
                marks.append('<span class="plab" style="left:%.3f%%;'
                             'top:%.3f%%">busiest %d</span>'
                             % (100 * (pi + .5) / 96, y(inside[pi]),
                                summary["peak"]))
        for v in range(0, top + 1, step):
            marks.append('<span class="yt" style="top:%.3f%%">%d</span>'
                         % (y(v), v))
        for h, label, minor in HOUR_TICKS:
            marks.append('<span class="xt%s" style="left:%.3f%%">%s</span>'
                         % (minor, 100 * h / 24.0, label))
        if tariff:
            marks.append('<span class="tlab" style="left:%.3f%%">peak tariff'
                         '</span>' % (100 * (tariff[0] + tariff[1]) / 2 / 96))
    cls = "ec-chart compact" if compact else "ec-chart"
    return ('<div class="%s" style="height:%dpx"><div class="plot">%s%s</div>'
            '</div>' % (cls, height, "".join(svg), "".join(marks)))


def strip(slots, t, now, height=12):
    """A department's day as one row of quarter hours, darker = more people."""
    rects = []
    i = 0
    while i < SLOTS:
        if i > now:
            rects.append('<rect x="%d" y="0" width="%d" height="1" fill="%s"/>'
                         % (i, SLOTS - i, t["future"]))
            break
        b = bucket(slots[i])
        j = i
        while j + 1 <= now and j + 1 < SLOTS and bucket(slots[j + 1]) == b:
            j += 1
        if b < 0:
            fill, words = t["unwatched"], "nobody watching"
        elif b == 0:
            fill, words = t["ramp"][0], "empty"
        else:
            fill = t["ramp"][b]
            peak = max(v for v in slots[i:j + 1] if v is not None)
            words = "up to %d %s" % (round(peak),
                                     "person" if round(peak) == 1 else "people")
        tip = "%s–%s · %s" % (slot_clock(i), slot_clock(j + 1), words)
        rects.append('<rect x="%d" y="0" width="%d" height="1" fill="%s">'
                     '<title>%s</title></rect>' % (i, j + 1 - i, fill, esc(tip)))
        i = j + 1
    return ('<div class="ec-strip" style="height:%dpx"><svg viewBox="0 0 96 1" '
            'preserveAspectRatio="none">%s</svg></div>'
            % (height, "".join(rects)))


def meter(part, whole):
    share = 0 if not whole else 100.0 * part / whole
    return ('<div class="ec-meter" role="img" aria-label="%d of %d"><i '
            'style="width:%.1f%%"></i></div>' % (part, whole, share))


WARN = ('<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path '
        'd="M8 1.5 15 14H1z" fill="#d03b3b"/><rect x="7.2" y="5.6" '
        'width="1.6" height="4.6" rx=".8" fill="#fff"/><circle cx="8" '
        'cy="12" r=".95" fill="#fff"/></svg>')
TICK = ('<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><circle '
        'cx="8" cy="8" r="7" fill="#0ca30c"/><path d="M4.6 8.2 7 10.5l4.4-4.8"'
        ' fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"'
        ' stroke-linejoin="round"/></svg>')


def css(theme):
    """The page's look. Scoped under .ec so it touches nothing else."""
    t = dict(TOKENS[theme])
    return ("""<style>
.ec{--page:%(page)s;--s1:%(s1)s;--s2:%(s2)s;--line:%(line)s;--line2:%(line2)s;
--t1:%(t1)s;--t2:%(t2)s;--t3:%(t3)s;--accent:%(accent)s;--crit:%(crit)s;
--crit-bg:%(crit_bg)s;--crit-line:%(crit_line)s;--good:%(good)s;
--good-ring:%(good_ring)s;--hover:%(hover)s;--pill-bg:%(pill_bg)s;
--pill-fg:%(pill_fg)s;--meter:%(m0)s;--shadow:%(shadow)s;--invert:%(invert)s;
color:var(--t1);font-family:system-ui,-apple-system,"Segoe UI",Roboto,
"Helvetica Neue",sans-serif;font-size:14px;line-height:1.45}
.ec *{box-sizing:border-box}
.ec a{color:inherit;text-decoration:none}
.ec .t2{color:var(--t2)}.ec .t3{color:var(--t3)}.ec .sp{flex:1}
.ec-top{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:6px 0 10px}
.ec-brand{display:flex;align-items:center;gap:12px}
.ec-brand .mark{height:22px;display:flex;align-items:center}
.ec-brand .mark svg{height:22px;width:auto;display:block}
.ec-brand .prod{font-size:11px;letter-spacing:.2em;color:var(--t3);
border-left:1px solid var(--line2);padding-left:12px}
.ec-live{display:inline-flex;align-items:center;gap:7px;font-size:12px;
color:var(--t2);border:1px solid var(--line2);padding:4px 11px;
border-radius:999px;white-space:nowrap}
.ec-live .d{width:7px;height:7px;border-radius:50%%;background:var(--good);
box-shadow:0 0 0 3px var(--good-ring)}
.ec-live.off .d{background:var(--crit);box-shadow:0 0 0 3px var(--crit-bg)}
.ec-when{font-size:13px;color:var(--t3);white-space:nowrap}
.ec-theme{font-size:12px;color:var(--t2);border:1px solid var(--line2);
padding:4px 10px;border-radius:999px}
.ec-theme:hover{color:var(--t1);border-color:var(--t3)}
.ec-greet{margin:22px 0 4px;color:var(--t3);font-size:14px}
.ec-hero{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.ec-hero .n{font-size:clamp(56px,9vw,84px);font-weight:700;letter-spacing:-.035em;
line-height:1}
.ec-hero .l{font-size:clamp(17px,2.2vw,22px);color:var(--t2);font-weight:500}
.ec-sub{color:var(--t3);margin-top:8px;font-size:14px}
.ec-sub b{color:var(--t1);font-weight:600}
.ec-card{background:var(--s1);border:1px solid var(--line);border-radius:18px;
padding:20px 22px;box-shadow:var(--shadow)}
.ec-camps{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));
gap:20px;margin-top:28px}
.ec-camp{display:block;transition:transform .15s ease,border-color .15s ease}
.ec-camp:hover{transform:translateY(-2px);border-color:var(--line2)}
.ec-camp .head{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.ec-camp .name{font-size:30px;font-weight:750;letter-spacing:-.02em}
.ec-enter{margin-left:auto;font-size:13px;font-weight:600;color:var(--t1);
background:var(--s2);border:1px solid var(--line2);padding:7px 14px;
border-radius:999px;white-space:nowrap}
.ec-camp:hover .ec-enter{background:var(--accent);border-color:var(--accent);
color:#fff}
.ec-big{display:flex;align-items:baseline;gap:10px;margin-top:16px;flex-wrap:wrap}
.ec-big .n{font-size:48px;font-weight:700;letter-spacing:-.02em;line-height:1}
.ec-big .l{font-size:16px;color:var(--t2)}
.ec-big .o{margin-left:auto;font-size:13px;color:var(--t3)}
.ec-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;
margin-top:12px;border-top:1px solid var(--line);padding-top:14px}
.ec-stat .k{font-size:11.5px;color:var(--t3)}
.ec-stat .v{font-size:17px;font-weight:650;margin-top:3px;white-space:nowrap}
.ec-stat .v small{font-size:13px;font-weight:500;color:var(--t3)}
.ec-stat .s{font-size:11.5px;color:var(--t3);margin-top:1px;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}
.ec-meter{height:6px;border-radius:99px;background:var(--meter);margin-top:8px;
overflow:hidden}
.ec-meter i{display:block;height:100%%;background:var(--accent);border-radius:99px}
.ec-foot{display:flex;gap:14px;align-items:center;margin-top:16px;font-size:13px;
color:var(--t2);flex-wrap:wrap}
.ec-flag{display:inline-flex;align-items:center;gap:7px;color:var(--t1)}
.ec .ic{width:15px;height:15px;flex:none;display:inline-block}
.ec-note{margin-top:22px;color:var(--t3);font-size:12.5px}
.ec-chart{position:relative;margin:6px 0 2px}
.ec-chart .plot{position:absolute;left:34px;right:6px;top:22px;bottom:24px}
.ec-chart.compact .plot{left:0;right:0;top:6px;bottom:2px}
.ec-chart svg{position:absolute;inset:0;width:100%%;height:100%%;overflow:visible}
.ec-chart .hit{fill:transparent}
.ec-chart .hit:hover{fill:var(--hover)}
.ec-chart .dot{position:absolute;width:10px;height:10px;margin:-5px 0 0 -5px;
border-radius:50%%;background:var(--accent);box-shadow:0 0 0 2px var(--s1);
pointer-events:none}
.ec-chart .plab{position:absolute;transform:translate(-50%%,-150%%);font-size:12px;
font-weight:650;white-space:nowrap;pointer-events:none}
.ec-chart .yt{position:absolute;left:-34px;width:26px;text-align:right;
transform:translateY(-50%%);font-size:10.5px;color:var(--t3);
font-variant-numeric:tabular-nums}
.ec-chart .xt{position:absolute;top:100%%;margin-top:6px;transform:translateX(-50%%);
font-size:10.5px;color:var(--t3);white-space:nowrap}
.ec-chart .tlab{position:absolute;top:-18px;transform:translateX(-50%%);
font-size:10.5px;color:var(--t3);white-space:nowrap}
.ec-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--t2)}
.ec-legend i{display:inline-block;width:14px;height:2px;vertical-align:middle;
margin-right:6px;border-radius:2px}
.ec-legend i.box{height:9px;width:12px;border-radius:2px}
.ec-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:30px 0 12px}
.ec-h .t{font-size:17px;font-weight:700}
.ec-h .c{font-size:13px;color:var(--t3)}
.ec-h .ec-legend{margin-left:auto}
.ec-r1{display:grid;grid-template-columns:5fr 7fr;gap:16px;margin-top:8px}
.ec-kpis{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.ec-kpi .k{font-size:12px;color:var(--t3)}
.ec-kpi .v{font-size:26px;font-weight:700;margin-top:6px;letter-spacing:-.01em}
.ec-kpi .s{font-size:12.5px;color:var(--t3);margin-top:3px}
.ec-herocard .k{font-size:13px;color:var(--t2)}
.ec-herocard .n{font-size:clamp(60px,8vw,88px);font-weight:700;
letter-spacing:-.035em;line-height:1;margin-top:10px}
.ec-herocard .s{color:var(--t3);margin-top:10px}
.ec-walks{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.ec-walk{display:block;background:var(--crit-bg);border:1px solid var(--crit-line);
border-radius:14px;padding:13px 15px}
.ec-walk .nm{font-weight:650;font-size:15px}
.ec-walk .z{font-size:12px;color:var(--t3);margin-top:1px}
.ec-walk .w{display:flex;align-items:center;gap:7px;margin-top:8px;font-size:13px}
.ec-calm{display:flex;align-items:center;gap:9px;color:var(--t2);font-size:14px}
.ec-depts{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.ec-dept{padding:16px 18px}
.ec-dept .hd{display:flex;align-items:baseline;gap:8px}
.ec-dept .nm{font-weight:700;font-size:16px;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}
.ec-dept .rm{font-size:12px;color:var(--t3);white-space:nowrap}
.ec-dept .pp{margin-left:auto;font-size:26px;font-weight:700;line-height:1}
.ec-dept .pp small{font-size:12px;color:var(--t3);font-weight:500;margin-left:4px}
.ec-dept .io{display:flex;gap:7px;align-items:center;flex-wrap:wrap;
margin:10px 0 10px;font-size:13px;color:var(--t2)}
.ec-dept .io b{color:var(--t1);font-weight:650}
.ec-dept .io .ar{color:var(--t3)}
.ec-pill{font-size:11.5px;padding:2px 8px;border-radius:99px;background:var(--pill-bg);
color:var(--pill-fg);white-space:nowrap}
.ec-dept .ax{display:flex;justify-content:space-between;font-size:10.5px;
color:var(--t3);margin-top:5px}
.ec-dept .ft{display:flex;gap:10px;font-size:12px;color:var(--t3);margin-top:8px;
flex-wrap:wrap}
.ec-dept .ft .ec-flag{color:var(--t2)}
.ec-dept.quiet{opacity:.6}
.ec-strip{border-radius:4px;overflow:hidden}
.ec-strip svg{display:block;width:100%%;height:100%%}
.ec-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.ec-gh{display:flex;align-items:baseline;gap:8px}
.ec-gh b{font-size:14px}.ec-gh span{font-size:12px;color:var(--t3)}
.ec-chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px}
.ec-chip{display:inline-flex;align-items:center;gap:7px;background:var(--s2);
border:1px solid var(--line);border-radius:10px;padding:6px 10px;font-size:12.5px;
color:var(--t1)}
.ec-chip:hover{border-color:var(--line2)}
.ec-chip .b{width:8px;height:8px;border-radius:50%%;flex:none}
.ec-chip .p{font-weight:650}.ec-chip .m{color:var(--t3)}
.ec-out{margin-top:14px}
.ec-out summary{cursor:pointer;list-style:none;display:flex;align-items:center;
gap:12px;color:var(--t2);flex-wrap:wrap}
.ec-out summary::-webkit-details-marker{display:none}
.ec-out summary b{color:var(--t1)}
.ec-out summary .tg{margin-left:auto;font-size:12.5px;color:var(--t1);
border:1px solid var(--line2);border-radius:99px;padding:4px 12px}
.ec-out[open] summary .tg:after{content:" \\2191"}
.ec-switch{display:flex;gap:6px;flex-wrap:wrap}
.ec-switch a{font-size:13px;padding:5px 12px;border-radius:999px;
border:1px solid var(--line2);color:var(--t2)}
.ec-switch a.on{background:var(--t1);color:var(--invert);border-color:var(--t1);
font-weight:650}
.ec-back{color:var(--t2);font-size:13px}
.ec-back:hover{color:var(--t1)}
.ec-title{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:2px 0 4px}
.ec-title .name{font-size:30px;font-weight:750;letter-spacing:-.02em}
.ec-scale{display:flex;gap:10px;align-items:center;font-size:11.5px;color:var(--t3)}
.ec-scale i{display:inline-block;width:12px;height:8px;border-radius:2px;
margin-right:4px;vertical-align:middle}
@media (max-width:760px){
 .ec-r1{grid-template-columns:1fr}
 .ec-stats{grid-template-columns:1fr 1fr}
 .ec-camp .name{font-size:26px}
 .ec-big .o{margin-left:0;width:100%%}
 .ec-kpi .v{font-size:21px}
 .ec-kpis{gap:12px}
 .ec-h .ec-legend{margin-left:0}
 .ec-chart .xt.minor{display:none}
}
</style>""" % dict(t, invert=t["invert"], m0=t["ramp"][0])).replace("\n", "")


# ===================================================================== pages

def topbar(mark, live_text, healthy, when, base, theme, extra=""):
    other = "light" if theme == "dark" else "dark"
    return ('<div class="ec-top"><div class="ec-brand"><span class="mark">%s'
            '</span><span class="prod">ENERGYCAM</span></div>%s'
            '<span class="sp"></span><span class="ec-live%s"><span class="d">'
            '</span>%s</span><span class="ec-when">%s</span>'
            '<a class="ec-theme" href="%s">%s</a></div>'
            % (mark, extra, "" if healthy else " off", esc(live_text),
               esc(when), link(base, theme=None if other == "dark" else other),
               "Light" if other == "light" else "Dark"))


def greeting(now):
    h = now.tz_convert(LOCAL).hour
    return ("Good morning" if 5 <= h < 12 else "Good afternoon" if h < 17
            else "Good evening" if h < 21 else "Good night")


def welcome(summaries, theme, mark, live_text, healthy, when, base):
    """Both campuses, side by side, each a door into its own page."""
    t = TOKENS[theme]
    everyone = sum(s["inside_now"] for s in summaries)
    busy = sum(s["rooms_busy"] for s in summaries)
    walks = sum(len(s["walk"]) for s in summaries)
    quiet = sum(len(s["silent"]) for s in summaries)
    h = [css(theme), '<div class="ec">',
         topbar(mark, live_text, healthy, when, base, theme)]
    h.append('<div class="ec-greet">%s</div><div class="ec-hero"><span '
             'class="n">%s%d</span><span class="l">people in the office across'
             ' both campuses%s</span></div>'
             % (greeting(summaries[0]["now"]) if summaries else "",
                "" if not quiet else '<span style="font-size:.4em;'
                'font-weight:500;color:var(--t3)">at least </span>',
                everyone, " right now" if healthy else ", when last seen"))
    bits = ["<b>%d</b> rooms in use" % busy]
    bits.append(("<b>%d</b> air-conditioned room%s empty a while" %
                 (walks, "" if walks == 1 else "s")) if walks
                else "no air-conditioned room has been left empty")
    if quiet:
        bits.append("%d camera%s not answering" % (quiet, "" if quiet == 1
                                                  else "s"))
    h.append('<div class="ec-sub">%s</div><div class="ec-camps">'
             % " · ".join(bits))
    for s in summaries:
        last = (clock(s["last_out_yday"]) if s["last_out_yday"] is not None
                else "stayed overnight" if s["overnight"] else "—")
        h.append(
            '<a class="ec-card ec-camp" href="%s"><div class="head"><span '
            'class="name">%s</span><span class="ec-enter">Enter campus →'
            '</span></div>'
            '<div class="ec-big"><span class="n">%d</span><span class="l">in '
            'the office</span><span class="o">%d outside · not counted'
            '</span></div>%s'
            '<div class="ec-stats">'
            '<div class="ec-stat"><div class="k">First in</div><div class="v">'
            '%s</div><div class="s">%s</div></div>'
            '<div class="ec-stat"><div class="k">Busiest today</div><div '
            'class="v">%s</div><div class="s">%s</div></div>'
            '<div class="ec-stat"><div class="k">Last out yesterday</div><div '
            'class="v">%s</div><div class="s">last room emptied</div></div>'
            '<div class="ec-stat"><div class="k">Rooms in use</div><div '
            'class="v">%d<small> / %d</small></div>%s</div></div>'
            '<div class="ec-foot">%s<span class="sp"></span><span>%s at stake '
            'today</span></div></a>'
            % (link(base, campus=s["name"]), esc(s["name"]), s["inside_now"],
               s["outside_now"],
               area_chart(s, t, height=74, compact=True, outside=False,
                          tariff=None),
               clock(s["first_in"]), esc(s["first_who"] or "nobody yet"),
               s["peak"] or "—",
               ("at " + clock(s["peak_at"])) if s["peak_at"] is not None
               else "nobody yet", last,
               s["rooms_busy"], s["rooms_total"],
               meter(s["rooms_busy"], s["rooms_total"]),
               ('<span class="ec-flag">%s%d room%s worth a walk</span>'
                % (WARN, len(s["walk"]), "" if len(s["walk"]) == 1 else "s"))
               if s["walk"] else
               '<span class="ec-flag">%sNothing to walk to</span>' % TICK,
               rupees(s["stake"])))
    h.append('</div><div class="ec-note">%s. Counts are what the cameras can'
             ' see — a floor, not a register: somebody no camera covers is'
             ' not counted, and two cameras on one place count once.</div>'
             % " · ".join("%d rooms at %s" % (s["rooms_total"]
                                                   + sum(1 for r in s["rooms"]
                                                         if r["outside"]),
                                                   esc(s["name"]))
                               for s in summaries))
    h.append("</div>")
    return "".join(h)


def campus_head(summary, names, theme, mark, live_text, healthy, when, base):
    """The bar above every view of one campus: back, switch, live."""
    switch = "".join('<a class="%s" href="%s">%s</a>'
                     % ("on" if n == summary["name"] else "",
                        link(base, campus=n), esc(n)) for n in names)
    return "".join([
        css(theme), '<div class="ec">',
        topbar(mark, live_text, healthy, when, base, theme),
        '<div class="ec-title"><a class="ec-back" href="%s">← All '
        'campuses</a><div class="ec-switch">%s</div></div></div>'
        % (link(base, campus=None), switch)])


def _since_text(e):
    if e["status"] == "unknown":
        return "?"
    return ago(e["since"]) if e["since"] is not None else ""


def _chip(e, t, base):
    """One room: a dot for its state, its name, and people or time empty.

    Blue is people, red is an empty room with a unit to check (with the
    time beside it, so the colour never carries that alone), an open ring is
    a camera that did not answer, and grey is simply empty.
    """
    if e["status"] == "occupied":
        dot = "background:%s" % t["accent"]
        tail = '<span class="p">%d</span>' % e["people"]
    elif e["level"] in ("Red", "Amber"):
        dot = "background:%s" % t["crit"]
        tail = '<span class="m">%s</span>' % _since_text(e)
    elif e["status"] == "unknown":
        dot = "box-shadow:inset 0 0 0 1.5px %s" % t["t3"]
        tail = '<span class="m">no answer</span>'
    else:
        dot = "background:%s" % ("#4a4a46" if theme_is_dark(t) else "#c3c2b7")
        tail = '<span class="m">%s</span>' % _since_text(e)
    return ('<a class="ec-chip" href="%s" title="%s"><span class="b" '
            'style="%s"></span>%s %s</a>'
            % (link(base, room=e["name"]) + "#roomdetail",
               esc("%s · %s" % (e["name"], e["headline"] or e["status"])),
               dot, esc(short(e["name"])), tail))


def theme_is_dark(t):
    return t["page"] == TOKENS["dark"]["page"]


def _dept_card(d, t, now):
    if d["carried"]:
        came = 'In <b>since last night</b>'
    elif d["starts"] is not None:
        came = "In <b>%s</b>" % clock(d["starts"])
    elif d["first_in"] is not None:
        came = "Brief visits only, first <b>%s</b>" % clock(d["first_in"])
    else:
        came = "Nobody yet today"
    if d["still_in"]:
        went = '<span class="ec-pill">still in</span>'
    elif d["last_out"] is not None and d["starts"] is not None:
        went = "Out <b>%s</b>" % clock(d["last_out"])
    else:
        went = ""
    quiet = "" if d["people"] or d["first_in"] is not None else " quiet"
    foot = []
    if d["peak"]:
        foot.append("busiest %d at %s" % (d["peak"], clock(d["peak_at"])))
    if d["walk"]:
        foot.append('<span class="ec-flag">%s%d to check</span>'
                    % (WARN, d["walk"]))
    if d["silent"]:
        foot.append("%d camera%s silent" % (d["silent"],
                                             "" if d["silent"] == 1 else "s"))
    return (
        '<div class="ec-card ec-dept%s"><div class="hd"><span class="nm" '
        'title="%s">%s</span><span class="rm">%s</span><span class="pp">%d'
        '<small>in now</small></span></div><div class="io">%s%s%s<span '
        'class="sp"></span><span class="t3">%d of %d room%s in use</span></div>'
        '%s<div class="ax"><span>12 night</span><span>6 morning</span><span>'
        'noon</span><span>6 evening</span><span>12 night</span></div>%s</div>'
        % (quiet, esc(d["name"]), esc(short(d["name"])),
           "%d rooms" % d["rooms"] if d["rooms"] > 1 else "",
           d["people"], came, ' <span class="ar">→</span> ' if went else "",
           went, d["busy"], d["rooms"], "" if d["rooms"] == 1 else "s",
           strip(d["slots"], t, now),
           '<div class="ft">%s</div>' % " · ".join(foot) if foot else ""))


def campus_body(summary, theme, base, tariff=(18.5, 22.5)):
    """One campus at a glance, below the bar and the view switch."""
    t = TOKENS[theme]
    s = summary
    now = now_slot(s)
    band = (int(round(tariff[0] * 4)), int(round(tariff[1] * 4)))
    last = (clock(s["last_out_yday"]) if s["last_out_yday"] is not None
            else "stayed overnight" if s["overnight"] else "—")
    quiet = len(s["silent"])
    h = [css(theme), '<div class="ec">']
    h.append(
        '<div class="ec-r1"><div class="ec-card ec-herocard"><div class="k">'
        'In the office %s</div><div class="n">%s%d</div><div class="s">%d of %d'
        ' rooms in use · %d outside, not counted%s</div>%s</div>'
        '<div class="ec-kpis">'
        '<div class="ec-card ec-kpi"><div class="k">First in today</div>'
        '<div class="v">%s</div><div class="s">%s</div></div>'
        '<div class="ec-card ec-kpi"><div class="k">Busiest so far</div>'
        '<div class="v">%s</div><div class="s">%s</div></div>'
        '<div class="ec-card ec-kpi"><div class="k">Last out yesterday</div>'
        '<div class="v">%s</div><div class="s">when the last working room '
        'emptied</div></div>'
        '<div class="ec-card ec-kpi"><div class="k">At stake today</div>'
        '<div class="v">%s</div><div class="s">%s</div></div></div></div>'
        % ("now" if s["live"] else "when last seen",
           '<span style="font-size:.32em;font-weight:500;color:var(--t3);'
           'letter-spacing:0">at least </span>' if quiet else "",
           s["inside_now"], s["rooms_busy"], s["rooms_total"], s["outside_now"],
           (" · %d camera%s not answering" % (quiet, "" if quiet == 1
                                                   else "s")) if quiet else "",
           meter(s["rooms_busy"], s["rooms_total"]),
           clock(s["first_in"]),
           ("%s opened the campus" % esc(short(s["first_who"])))
           if s["first_who"] else "nobody has started a day yet",
           ("%d people" % s["peak"]) if s["peak"] else "—",
           ("at " + clock(s["peak_at"])) if s["peak_at"] is not None else "",
           last, rupees(s["stake"]),
           esc(s["stake_note"] or "upper bound · empty rooms with a unit")))

    h.append('<div class="ec-h"><span class="t">People through the day</span>'
             '<span class="c">every camera inside, added up · hover for '
             'the count</span><span class="ec-legend"><span><i style="'
             'background:%s"></i>In the office</span><span><i style="'
             'background:%s"></i>Outside</span><span><i class="box" style="'
             'background:%s"></i>Peak tariff</span></span></div>'
             % (t["accent"], t["out"], t["tariff_key"]))
    h.append('<div class="ec-card" style="padding:14px 18px 22px">%s</div>'
             % area_chart(s, t, height=250, tariff=band))

    if s["walk"]:
        h.append('<div class="ec-h"><span class="t">Worth a walk</span><span '
                 'class="c">empty past its own wait, with an air conditioner'
                 '</span></div><div class="ec-walks">')
        for e in s["walk"]:
            unit = ("unit in frame" if e["ac"] == "visible"
                    else "unit out of frame, look in")
            h.append('<a class="ec-walk" href="%s"><div class="nm">%s</div>'
                     '<div class="z">%s</div><div class="w">%s%s · %s'
                     '</div></a>'
                     % (link(base, room=e["name"]) + "#roomdetail",
                        esc(short(e["name"])), esc(e["dept"] or e["zone"]),
                        WARN, esc(e["headline"]), unit))
        h.append("</div>")
    else:
        h.append('<div class="ec-h"><span class="t">Worth a walk</span></div>'
                 '<div class="ec-card ec-calm">%sNothing to walk to: every '
                 'air-conditioned room is in use or was left only a little '
                 'while ago.</div>' % TICK)

    work = [d for d in s["depts"] if d["work"]]
    rest = [d for d in s["depts"] if not d["work"]]
    scale = "".join('<span><i style="background:%s"></i>%s</span>'
                    % (t["ramp"][i + 1], b) for i, b in enumerate(BUCKETS))
    h.append('<div class="ec-h"><span class="t">Departments</span><span '
             'class="c">first in → last out, people added across their '
             'rooms</span><span class="ec-scale" style="margin-left:auto">'
             'people %s</span></div><div class="ec-depts">%s</div>'
             % (scale, "".join(_dept_card(d, t, now) for d in work)))
    if rest:
        h.append('<div class="ec-h"><span class="t">Common areas</span><span '
                 'class="c">cafe, lobbies, the way in and the server rooms '
                 '· counted as inside</span></div><div class="ec-depts">%s'
                 '</div>' % "".join(_dept_card(d, t, now) for d in rest))

    inside = [e for e in s["rooms"] if not e["outside"]]
    groups = [("Offices & meeting rooms", [e for e in inside if e["work"]]),
              ("Cafe, lobbies & entrance",
               [e for e in inside if not e["work"] and not e["server"]]),
              ("Server rooms", [e for e in inside if e["server"]])]

    def order(e):
        return (e["status"] != "occupied", -e["people"],
                e["level"] not in ("Red", "Amber"), e["name"])
    h.append('<div class="ec-h"><span class="t">Rooms</span><span class="c">'
             'busy first \u00b7 click one to open it</span></div>')

    def card(title, rooms):
        rooms = sorted(rooms, key=order)
        return ('<div class="ec-card"><div class="ec-gh"><b>%s</b><span>%d of'
                ' %d in use%s</span></div><div class="ec-chips">%s</div></div>'
                % (title, sum(1 for e in rooms if e["status"] == "occupied"),
                   len(rooms), " \u00b7 cooled on purpose, never flagged"
                   if title == "Server rooms" else "",
                   "".join(_chip(e, t, base) for e in rooms)))
    # The working rooms are most of the campus, so they get the width of the
    # page to themselves; squeezed into a third of it they ran to a column
    # twenty chips long beside two short ones and a hole.
    if groups[0][1]:
        h.append(card(*groups[0]))
    rest = [g for g in groups[1:] if g[1]]
    if rest:
        h.append('<div class="ec-groups" style="margin-top:14px">%s</div>'
                 % "".join(card(*g) for g in rest))
    out = sorted((e for e in s["rooms"] if e["outside"]), key=order)
    if out:
        h.append('<details class="ec-card ec-out"><summary><b>Outside &amp; '
                 'plant</b><span>%d areas · %d %s now · never '
                 'counted as inside</span><span class="tg">Show</span>'
                 '</summary><div class="ec-chips">%s</div></details>'
                 % (len(out), s["outside_now"],
                    "person" if s["outside_now"] == 1 else "people",
                    "".join(_chip(e, t, base) for e in out)))
    h.append("</div>")
    return "".join(h)
