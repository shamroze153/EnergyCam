"""The building, floor by floor: every room, who is in it, what its AC does.

Asked for on 12 Nov: "when we enter a campus, the whole dashboard -- every
floor, every room, the AC on it, the people in it as little figures, and a
small line saying when it usually fills and empties". This is that page's
body. Everything else on the campus page is detail under it.

Each room is drawn: its outline, a figure for each person the cameras count
(up to a handful, then "+n"), and its air conditioner on the wall --
green running, grey off, dashed when nobody can see it, absent when the room
has none. A room with nobody in and a unit running is outlined red and says
SWITCH OFF: the one thing on the page somebody walking past can act on.

"Usually" is the room's ordinary working day over the last few working days:
when people first stayed (an office boy's early round does not count -- the
day starts with the first visit somebody stayed for) and when the last one
left. It comes from day_story, the same arithmetic as Who comes when.

Floors come from rooms.yaml (`floor:`), else from the room's name ("(1st
floor)"), and 141's rooms are grouped by block. A room nobody has placed yet
goes under "Not placed on a floor yet" rather than on a guessed floor.

No Streamlit and no database: frames in, HTML out.
"""
import re

import pandas as pd

import day_story as ds
import energy_view as ev
import overview as ov
from overview import TOKENS, esc

OUTSIDE = {"H perimeter", "Outside & plant", "Unused"}
WORK = {"Offices", "H offices", "Basement", "Server rooms"}
ORDER = ["Ground floor", "First floor", "Second floor", "Third floor",
         "Basement", "Cafe"]
NUMBER = {1: "First floor", 2: "Second floor", 3: "Third floor"}


# ===================================================================== figures

def floor_of(row):
    """Which floor heading a room goes under."""
    # A room with no floor written down comes out of the page's table with
    # NaN there, which is truthy: on 12 Nov the campus page had a floor
    # called "NAN" holding Commons and the lobbies.
    floor = row.get("floor")
    if isinstance(floor, str) and floor.strip():
        return floor.strip()
    name = str(row["room"])
    m = re.search(r"\((\d)(?:st|nd|rd|th) floor\)", name)
    level = NUMBER.get(int(m.group(1))) if m else None
    # 141's XVR 3 rooms (12 Nov) are named "(ground floor)".
    if level is None and re.search(r"\(ground floor\)", name, re.I):
        level = "Ground floor"
    if name.startswith("141"):
        block = ("141-C" if name.startswith("141-C") else
                 "141-D" if name.startswith("141-D") else "Main building")
        return "%s · %s" % (block, level) if level else block
    return level or "Not placed on a floor yet"


def on_floor(name):
    """A room's name under its floor's heading: "(2nd floor)" is said there.

    "Room 6 (ground floor)" sat right under "Main building · Ground floor".
    """
    short = re.sub(r"\s*\((?:ground|\d(?:st|nd|rd|th)) floor\)", "",
                   ov.short(str(name)), flags=re.I).strip()
    return short or ov.short(str(name))


def floor_rank(label):
    for i, word in enumerate(ORDER):
        if label == word:
            return (0, i, label)
    if label.startswith(("Main building", "141-C", "141-D")):
        block, _, level = label.partition(" · ")
        return (1, ["Main building", "141-C", "141-D"].index(block),
                ORDER.index(level) if level in ORDER else -1)
    return (2, 0, label)


OPENS_AT = 5                 # a start before 5am is the night, not the day
MIN_DAYS = 2                 # one day is an anecdote, not "usually"
MORNING, EVENING = (6, 12), (17, 24)   # hours that must have been watched


def _mean(values):
    return sum(values) / len(values) if len(values) >= MIN_DAYS else None


def covered(beats, a, b):
    """Share of [a, b) the loop was alive for, by ten-minute slots."""
    if beats is None:
        return 1.0
    slots = int((b - a).total_seconds() // 600)
    if slots <= 0:
        return 0.0
    seen = {int((t - a).total_seconds() // 600) for t in beats if a <= t < b}
    return len(seen) / float(slots)


def usual_days(history, rooms, days, beats=None):
    """Each room's ordinary day over `days` (local midnights).

    Returns room -> (starts, last_out, nights, days_counted): minutes past
    midnight (None where no day said), and on how many of the counted days
    somebody was still in at midnight.

    Only days mostly watched are counted -- the system's first days began at
    four in the afternoon, and a day half unseen has no honest first or last.
    The day "starts" with the first visit somebody stayed for, after five in
    the morning, so the cleaner's round is not the room opening. A day still
    occupied at midnight has no last-out: it is counted as a night instead,
    not as a departure at 12:00, which once averaged the Admin Room's day
    into "1:37 afternoon to 7:32 morning".
    """
    out = {}
    if history is None or history.empty or not days:
        return out
    by_room = {n: g for n, g in history.groupby("room")}
    # Which days had their morning watched, and which their evening: the
    # first is enough to say when a room opened, the second when it emptied.
    hour = pd.Timedelta(hours=1)
    mornings = {d: covered(beats, d + MORNING[0] * hour,
                           d + MORNING[1] * hour) >= 0.8 for d in days}
    evenings = {d: covered(beats, d + EVENING[0] * hour,
                           d + EVENING[1] * hour) >= 0.8 for d in days}
    for room in rooms:
        events = by_room.get(room)
        if events is None:
            continue
        starts, leaves, nights, counted = [], [], 0, 0
        for d in days:
            if not (mornings[d] or evenings[d]):
                continue
            end = d + pd.Timedelta(days=1)
            s = ds.story(ds.spells(events, d, end, beats), d)
            if mornings[d] and s["starts"] is not None and not s["carried"]:
                local = pd.Timestamp(s["starts"]).tz_convert(d.tzinfo)
                if local.hour >= OPENS_AT:
                    starts.append(local.hour * 60 + local.minute)
            if evenings[d] and s["last_out"] is not None:
                counted += 1
                if pd.Timestamp(s["last_out"]) >= end - pd.Timedelta(
                        minutes=1):
                    nights += 1
                else:
                    local = pd.Timestamp(s["last_out"]).tz_convert(d.tzinfo)
                    leaves.append(local.hour * 60 + local.minute)
        if starts or leaves or nights:
            out[room] = (_mean(starts), _mean(leaves), nights, counted)
    return out


def _num(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def tiles(df, usual, now):
    """Floors in order, each with its room tiles and its shared spaces."""
    floors = {}
    for _, r in df.iterrows():
        zone = r.get("zone") or ""
        if zone in OUTSIDE:
            continue
        label = floor_of(r)
        status = r.get("status")
        people = _num(r.get("people")) or 0
        since = r.get("empty_since")
        empty_for = None
        if status == "empty" and since is not None and not pd.isna(since):
            empty_for = max(0, int((now - pd.Timestamp(since))
                                   .total_seconds() // 60))
        ac_state = r.get("ac_state")
        ac_state = ac_state if ac_state in ("on", "off") else None
        has_unit = bool(r.get("has_unit"))
        tons = r.get("tons_total")
        tons = float(tons) if tons is not None and not pd.isna(tons) else None
        item = {
            "room": r["room"], "dept": r.get("dept") or "",
            "status": status, "people": people if status == "occupied" else 0,
            "empty_for": empty_for, "has_unit": has_unit,
            "units": int(r.get("ac_count") or 0) if has_unit else 0,
            "tons": tons, "ac_state": ac_state,
            "sizes": r.get("ac_sizes") if isinstance(r.get("ac_sizes"), str)
            else "",
            "units_on": _num(r.get("ac_units_on")),
            "alerts": bool(r.get("alerts", True)),
            "usual": usual.get(r["room"]),
            "work": has_unit or zone in WORK or bool(r.get("dept")),
        }
        item["waste"] = (ac_state == "on" and status == "empty"
                         and item["alerts"])
        floors.setdefault(label, []).append(item)
    out = []
    for label in sorted(floors, key=floor_rank):
        items = floors[label]
        rooms = sorted([i for i in items if i["work"]],
                       key=lambda i: (not i["waste"], -i["people"],
                                      i["room"]))
        spaces = sorted([i for i in items if not i["work"]],
                        key=lambda i: (-i["people"], i["room"]))
        out.append({
            "floor": label, "rooms": rooms, "spaces": spaces,
            "people": sum(i["people"] for i in items),
            "units": sum(i["units"] for i in items),
            # A floor's total only where every unit on it has its size: 141's
            # main building said "10 AC · 1 ton total" on 12 Nov, the one
            # unit whose size was known.
            "tons": (sum(i["tons"] for i in items if i["units"])
                     if all(i["tons"] for i in items if i["units"]) else None),
            "running": sum((i["units_on"] if i["units_on"] is not None
                            else 1) for i in items if i["ac_state"] == "on"),
            "waste": sum(1 for i in items if i["waste"]),
        })
    return out


# ===================================================================== drawing

CSS = """<style>
.fv-floor{margin-top:18px}
.fv-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;
padding:0 2px 8px;border-bottom:1px solid var(--line)}
.fv-head .t{font-size:12px;font-weight:750;letter-spacing:.14em;
text-transform:uppercase}
.fv-head .c{font-size:12.5px;color:var(--t3)}
.fv-head .c b{color:var(--t1);font-weight:650}
.fv-head .w{font-size:12px;font-weight:700;color:var(--crit)}
.fv-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(176px,1fr));
gap:10px;margin-top:10px}
.fv-room{display:block;background:var(--s1);border:1px solid var(--line);
border-radius:14px;padding:10px 11px 9px;transition:border-color .15s}
.fv-room:hover{border-color:var(--line2)}
.fv-room.waste{border:1.5px solid var(--crit);background:var(--crit-bg)}
.fv-room .nm{font-size:13.5px;font-weight:650;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.fv-room .dp{font-size:11px;color:var(--t3);white-space:nowrap;overflow:hidden;
text-overflow:ellipsis;min-height:14px}
.fv-room svg{display:block;width:100%%;height:auto;margin:6px 0 4px}
.fv-room .st{font-size:12.5px;font-weight:650}
.fv-room .st.empty{color:var(--t3);font-weight:600}
.fv-room .st.crit{color:var(--crit)}
.fv-room .us{font-size:11px;color:var(--t3);margin-top:1px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.fv-spaces{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.fv-spaces a{font-size:11.5px;color:var(--t2);border:1px solid var(--line);
border-radius:99px;padding:3px 10px;white-space:nowrap}
.fv-spaces a b{color:var(--t1);font-weight:650;margin-left:4px}
.fv-key{display:flex;flex-wrap:wrap;gap:14px;font-size:11.5px;color:var(--t3);
margin-top:12px}
.fv-key i{display:inline-block;width:12px;height:8px;border-radius:2px;
margin-right:5px;vertical-align:0}
@media (max-width:760px){.fv-grid{grid-template-columns:repeat(2,minmax(0,1fr));
gap:8px}.fv-room{padding:8px 9px 8px}.fv-room .nm{font-size:12.5px}}
</style>""".replace("\n", "")


def colours(theme):
    t = TOKENS[theme]
    dark = theme == "dark"
    return {"wall": "rgba(255,255,255,.22)" if dark else "rgba(11,11,11,.22)",
            "floor": "rgba(255,255,255,.035)" if dark else "rgba(11,11,11,.03)",
            "person": t["accent"], "on": "#2a9d63" if dark else "#1f8a55",
            "off": t["t3"], "unseen": t["t3"], "crit": t["crit"]}


def person(x, y, colour):
    return ('<circle cx="%.1f" cy="%.1f" r="4.2" fill="%s"/>'
            '<path d="M%.1f %.1f q%.1f -9 %.1f 0 v6 h-%.1f z" fill="%s"/>'
            % (x, y, colour, x - 6, y + 15, 6, 12, 12, colour))


def drawing(item, c):
    """The room: walls, its unit on the back wall, a figure per person."""
    edge = c["crit"] if item["waste"] else c["wall"]
    h = ['<svg viewBox="0 0 160 66" aria-hidden="true">',
         '<rect x="1.5" y="1.5" width="157" height="63" rx="8" fill="%s" '
         'stroke="%s" stroke-width="%s"/>'
         % (c["floor"], edge, "2" if item["waste"] else "1.2")]
    if item["has_unit"]:
        # One unit drawn per AC, up to six, along the back wall.
        n = max(1, min(item["units"], 6))
        on = item["units_on"]
        for i in range(n):
            x = 150 - (n - i) * 21
            if item["ac_state"] == "on" and (on is None and i == n - 1
                                             or on is not None
                                             and i >= n - on):
                fill, stroke, dash = c["on"], c["on"], ""
            elif item["ac_state"] == "off":
                fill, stroke, dash = "none", c["off"], ""
            else:
                fill, stroke, dash = "none", c["unseen"], ' stroke-dasharray="2 2"'
            h.append('<rect x="%d" y="7" width="17" height="7" rx="2" '
                     'fill="%s" stroke="%s" stroke-width="1.2"%s/>'
                     % (x, fill, stroke, dash))
    # Eight fit; past that, seven and a "+n" in the eighth's place.
    shown = item["people"] if item["people"] <= 8 else 7
    for i in range(shown):
        h.append(person(16 + i * 17, 34, c["person"]))
    if item["people"] > shown:
        h.append('<text x="152" y="52" text-anchor="end" font-size="13" '
                 'font-weight="750" fill="%s">+%d</text>'
                 % (c["person"], item["people"] - shown))
    h.append("</svg>")
    return "".join(h)


def clock(minutes):
    return ds.clock_minutes(minutes) if minutes is not None else None


def usual_text(usual):
    """'usually 9:40 morning - 7:15 evening', or what can be said instead."""
    if not usual:
        return ""
    starts, leaves, nights, counted = usual
    if nights >= MIN_DAYS and nights * 2 > counted:
        first = ("from %s, " % clock(starts)) if starts is not None else ""
        return "usually %sin through the night (%d of %d nights)" % (
            first, nights, counted)
    if starts is not None and leaves is not None:
        return "usually %s – %s" % (clock(starts), clock(leaves))
    if starts is not None:
        return "usually opens %s" % clock(starts)
    if leaves is not None:
        return "usually empty by %s" % clock(leaves)
    return ""


def status_line(item):
    if item["waste"]:
        return ('<div class="st crit">Nobody in &middot; AC running '
                '&middot; switch off</div>')
    if item["status"] == "occupied":
        return '<div class="st">%d %s in</div>' % (
            item["people"], "person" if item["people"] == 1 else "people")
    if item["status"] == "empty":
        if item["empty_for"] is not None:
            return '<div class="st empty">Empty %s</div>' % ov.ago(
                item["empty_for"])
        return '<div class="st empty">Empty</div>'
    return '<div class="st empty">Not seen right now</div>'


def ac_line(item):
    if not item["has_unit"]:
        return "no AC"
    units = ov.ac_size(item["units"], item.get("sizes"), item["tons"])
    if item["ac_state"] == "on":
        run = item["units_on"]
        return "%s · %s running" % (units, run if run else "on,")
    if item["ac_state"] == "off":
        return "%s · off" % units
    return units


def page(theme, floors, base, days_used):
    c = colours(theme)
    h = [ev.css(theme), CSS % {}, '<div class="ec">',
         '<div class="ec-h" style="margin-top:22px"><span class="t">The '
         'building, floor by floor</span><span class="c">who is in each '
         'room now, its AC, and its usual day</span></div>']
    for f in floors:
        bits = ["<b>%d</b> in" % f["people"]]
        if f["units"]:
            bits.append("<b>%d</b> AC%s" % (f["units"], (" · %g ton total"
                                                          % f["tons"])
                                             if f["tons"] else ""))
        if f["running"]:
            bits.append("<b>%d</b> seen running" % f["running"])
        h.append('<div class="fv-floor"><div class="fv-head"><span class="t">'
                 '%s</span><span class="c">%s</span>%s</div>'
                 % (esc(f["floor"]), " &middot; ".join(bits),
                    '<span class="w">%d to switch off</span>' % f["waste"]
                    if f["waste"] else ""))
        if f["rooms"]:
            h.append('<div class="fv-grid">')
            for item in f["rooms"]:
                us = usual_text(item["usual"])
                h.append(
                    '<a class="fv-room%s" target="_self" href="%s#roomdetail">'
                    '<div class="nm">%s</div><div class="dp">%s</div>%s%s'
                    '<div class="us">%s</div><div class="us">%s</div></a>'
                    % (" waste" if item["waste"] else "",
                       esc(ov.link(base, room=item["room"])),
                       esc(on_floor(item["room"])),
                       esc(item["dept"] if item["dept"] != item["room"]
                           else ""),
                       drawing(item, c), status_line(item), esc(ac_line(item)),
                       esc(us)))
            h.append("</div>")
        if f["spaces"]:
            h.append('<div class="fv-spaces">%s</div>' % "".join(
                '<a target="_self" href="%s#roomdetail">%s<b>%s</b></a>'
                % (esc(ov.link(base, room=s["room"])), esc(on_floor(s["room"])),
                   s["people"] if s["people"] else "&middot;")
                for s in f["spaces"]))
        h.append("</div>")
    h.append('<div class="fv-key"><span><i style="background:%s"></i>AC '
             'running</span><span><i style="border:1.2px solid %s"></i>AC '
             'off</span><span><i style="border:1.2px dashed %s"></i>AC not '
             'visible to a camera</span><span>Figures are people the cameras '
             'count now. "Usually" is the last %d working days: when somebody '
             'first stayed after 5am (early rounds by the office boys and '
             'cleaners do not count) and when the last person left, each from '
             'the days the cameras watched that part of; it appears once two '
             'days agree to say so.</span></div></div>'
             % (c["on"], c["off"], c["unseen"], days_used))
    return "".join(h)
