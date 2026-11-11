"""Which rooms sat empty, and for how long.

Asked for on 11 November in so many words: show on the dashboard which room
stayed empty, and for how long. The other pages answer "who is in now" and
"what did the empty, cooled hours cost"; this is the plain ledger under
both -- per room, for one day, the minutes empty, the minutes in use, and
the longest stretch nobody came back, drawn on a timeline.

Three rules keep the minutes honest:

  * Time the loop was not running is not "empty". It is drawn as not
    watched and kept out of every total: a laptop asleep for an hour must
    not hand every room an hour of emptiness.
  * The state at the start of the window is the last one recorded before
    it, so a room empty since last night starts the morning empty, not
    unknown. (The loader brings that one extra row per room.)
  * The default window is the working day from rooms.yaml (10 to 8,
    weekdays). An office empty at three in the morning is the expected
    answer, not a finding; the whole day and the hours after work are one
    click away for the rooms where they are.

Like overview.py and energy_view.py it holds no Streamlit and no database:
frames in, figures and HTML out.
"""
from datetime import timedelta

import pandas as pd

import energy_view as ev
import overview as ov
from overview import TOKENS, esc
from schedule import DAY_NAMES, DEFAULT_HOURS, PKT, _minutes

# The loop beats once a pass, about every four minutes. A beat vouches for
# this long either side of it; a longer silence is time nobody was looking.
VOUCH = timedelta(minutes=6)

WORKING, WHOLE, AFTER = "working", "whole", "after"


# ===================================================================== figures

def merge(spans):
    """Overlapping or touching spans, joined."""
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def watched(beats, start, end):
    """The parts of [start, end) the loop was alive for, from its beats.

    None means nothing is known about the beats, and everything counts as
    watched -- the pages that have no heartbeat to hand still get minutes.
    """
    if beats is None:
        return [(start, end)]
    spans = [(max(start, b - VOUCH), min(end, b + VOUCH)) for b in beats
             if b + VOUCH > start and b - VOUCH < end]
    return [(a, b) for a, b in merge(spans) if b > a]


def windows_for(day, hours, now, which=WORKING):
    """The stretch(es) of one local day to count, in UTC, cut off at now.

    day: a date (local). which: WORKING, WHOLE or AFTER. A day the building
    is closed has no working window at all, and its "after hours" is the
    whole of it.
    """
    hours = hours or DEFAULT_HOURS
    op = hours.get("operations", DEFAULT_HOURS["operations"])
    open_days = [d.strip().lower()[:3] for d in op.get("days", [])]
    midnight = pd.Timestamp(year=day.year, month=day.month, day=day.day,
                            tz=PKT)
    end_of_day = midnight + pd.Timedelta(days=1)
    s = _minutes(op.get("start", "10:00"))
    e = _minutes(op.get("end", "20:00"))
    work = None
    if DAY_NAMES[midnight.weekday()] in open_days and s < e:
        work = (midnight + pd.Timedelta(minutes=s),
                midnight + pd.Timedelta(minutes=e))
    if which == WORKING:
        spans = [work] if work else []
    elif which == AFTER:
        spans = ([(midnight, work[0]), (work[1], end_of_day)] if work
                 else [(midnight, end_of_day)])
    else:
        spans = [(midnight, end_of_day)]
    cut = pd.Timestamp(now).tz_convert(PKT)
    out = []
    for a, b in spans:
        b = min(b, cut)
        if b > a:
            out.append((a.tz_convert("UTC"), b.tz_convert("UTC")))
    return out


def _kind(status):
    return status if status in ("empty", "occupied") else "unknown"


def segments(events, room, windows, alive):
    """One room's day as (kind, start, end) pieces, in order.

    kind is "empty", "occupied", "unknown" (watched, but no state recorded
    yet) or "unwatched" (the loop was not running). Neighbouring pieces of
    the same kind are joined, so a room that stayed empty while its unit's
    reading changed is one stretch, not two.
    """
    mine = events[events["room"] == room].sort_values("timestamp")
    stamps = list(mine["timestamp"])
    kinds = [_kind(s) for s in mine["status"]]
    out = []
    for wa, wb in windows:
        raw = []
        if not stamps or stamps[0] > wa:
            raw.append(("unknown", wa, min(stamps[0], wb) if stamps else wb))
        for i, kind in enumerate(kinds):
            a = max(stamps[i], wa)
            b = min(stamps[i + 1] if i + 1 < len(stamps) else wb, wb)
            if b > a:
                raw.append((kind, a, b))
        live = [(max(a, wa), min(b, wb)) for a, b in alive
                if min(b, wb) > max(a, wa)]
        for kind, a, b in raw:
            cursor = a
            for x, y in live:
                x, y = max(x, a), min(y, b)
                if y <= x:
                    continue
                if x > cursor:
                    out.append(("unwatched", cursor, x))
                out.append((kind, x, y))
                cursor = y
            if cursor < b:
                out.append(("unwatched", cursor, b))
    joined = []
    for kind, a, b in out:
        if joined and joined[-1][0] == kind and joined[-1][2] >= a:
            joined[-1] = (kind, joined[-1][1], max(joined[-1][2], b))
        else:
            joined.append((kind, a, b))
    return joined


def minutes(a, b):
    return (b - a).total_seconds() / 60.0


def ledger(events, rooms, windows, alive):
    """Every room's minutes over the windows, emptiest first.

    rooms: frame with room, zone, has_unit, alerts, ac_count, status,
    ac_state. Returns a list of dicts.
    """
    rows = []
    for _, r in rooms.iterrows():
        pieces = segments(events, r["room"], windows, alive)
        totals = {"empty": 0.0, "occupied": 0.0, "unknown": 0.0,
                  "unwatched": 0.0}
        longest = (0.0, None, None)
        for kind, a, b in pieces:
            m = minutes(a, b)
            totals[kind] += m
            if kind == "empty" and m > longest[0]:
                longest = (m, a, b)
        seen = totals["empty"] + totals["occupied"]
        rows.append({
            "room": r["room"], "zone": r.get("zone"),
            "has_unit": bool(r.get("has_unit")),
            "alerts": bool(r.get("alerts", True)),
            "ac_count": int(r.get("ac_count") or 0),
            "ac_state": r.get("ac_state"),
            "status": r.get("status"),
            "empty": totals["empty"], "occupied": totals["occupied"],
            "unknown": totals["unknown"], "unwatched": totals["unwatched"],
            "seen": seen,
            "share": (totals["empty"] / seen) if seen else 0.0,
            "longest": longest[0], "longest_from": longest[1],
            "longest_to": longest[2],
            "pieces": pieces,
        })
    # Rooms cooled on purpose (server rooms) go last: they are empty by
    # design, and at the top they pushed the rooms somebody could act on
    # off the first screen of a phone.
    rows.sort(key=lambda x: (not x["alerts"], -x["empty"], x["room"]))
    return rows


def empty_now(rooms, now):
    """Rooms with a unit somebody could switch off, empty at this moment.

    Longest first, with how long and since when. Read off the latest state
    the loop wrote, which is what every other page shows too.
    """
    out = []
    for _, r in rooms.iterrows():
        if not (r.get("has_unit") and r.get("alerts", True)):
            continue
        if r.get("status") != "empty":
            continue
        since = r.get("empty_since")
        if since is None or pd.isna(since):
            since = r.get("timestamp")
        if since is None or pd.isna(since):
            continue
        out.append({"room": r["room"], "since": since,
                    "minutes": max(0.0, minutes(since, now)),
                    "ac_state": r.get("ac_state")})
    out.sort(key=lambda x: -x["minutes"])
    return out


# ===================================================================== drawing

def span(m):
    """3h 05m, 45m, 2d -- one way of saying a length everywhere."""
    return ov.ago(int(round(m))) if m >= 1 else "0m"


EXTRA = """<style>
.ev-row{display:grid;grid-template-columns:minmax(160px,220px) 1fr 168px;gap:16px;
align-items:center;padding:9px 0;border-top:1px solid var(--line)}
.ev-row:first-of-type{border-top:0}
.ev-row .nm b{display:block;font-weight:650;font-size:14px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.ev-row .nm span{font-size:11.5px;color:var(--t3)}
.ev-line{position:relative;height:16px;border-radius:5px;background:var(--meter);
overflow:hidden}
.ev-line i{position:absolute;top:0;bottom:0}
.ev-line i.empty{background:%(empty)s}
.ev-line i.occupied{background:%(occ)s}
.ev-line i.unknown{background:%(unknown)s}
.ev-line i.unwatched{background:repeating-linear-gradient(135deg,%(hatch)s 0 3px,
transparent 3px 7px)}
.ev-row .v{text-align:right;font-variant-numeric:tabular-nums}
.ev-row .v b{font-size:17px;font-weight:700;color:%(empty_ink)s}
.ev-row .v b.none{color:var(--t3);font-weight:600}
.ev-row .v span{display:block;font-size:11.5px;color:var(--t3)}
.ev-axis{position:relative;height:16px;margin:2px 0 0}
.ev-axis span{position:absolute;transform:translateX(-50%%);font-size:10.5px;
color:var(--t3);white-space:nowrap}
.ev-head{display:grid;grid-template-columns:minmax(160px,220px) 1fr 168px;gap:16px}
.ev-chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:4px}
.ev-chip{display:flex;flex-direction:column;gap:2px;padding:10px 14px;
border-radius:14px;border:1px solid var(--line2);background:var(--s1);
min-width:180px;flex:1 1 200px;max-width:280px}
.ev-chip b{font-size:14px;font-weight:650}
.ev-chip .d{font-size:20px;font-weight:720;color:%(empty_ink)s;
font-variant-numeric:tabular-nums}
.ev-chip .s{font-size:11.5px;color:var(--t3)}
.ev-key{display:inline-flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--t3)}
.ev-key i{display:inline-block;width:11px;height:11px;border-radius:3px;
margin-right:5px;vertical-align:-1px}
@media (max-width:760px){.ev-row,.ev-head{grid-template-columns:1fr 110px}
.ev-row .tl,.ev-head .tl{grid-column:1/-1;order:3}.ev-head .gap{display:none}}
</style>""".replace("\n", "")


def colours(theme):
    t = TOKENS[theme]
    dark = theme == "dark"
    return {"empty": "#e8a21a" if dark else "#eda100",
            "empty_ink": "#f2b84b" if dark else "#a66d00",
            "occ": t["accent"],
            "unknown": "rgba(255,255,255,.14)" if dark else "rgba(11,11,11,.12)",
            "hatch": "rgba(255,255,255,.10)" if dark else "rgba(11,11,11,.10)"}


def axis(start, end):
    """Hour marks under the timelines: every two hours, local time."""
    total = minutes(start, end)
    if total <= 0:
        return ""
    local = start.tz_convert(PKT)
    first = local.ceil("h")
    step = 2 if total > 8 * 60 else 1
    if total > 16 * 60:
        step = 3
    marks = []
    t = first
    while t <= end.tz_convert(PKT):
        if t.hour % step == 0:
            pct = 100.0 * minutes(local, t) / total
            h = t.hour % 12 or 12
            word = ("noon" if t.hour == 12 else "12 night" if t.hour == 0
                    else "%d%s" % (h, "am" if t.hour < 12 else "pm"))
            if 2 <= pct <= 98:
                marks.append('<span style="left:%.2f%%">%s</span>'
                             % (pct, word))
        t += pd.Timedelta(hours=1)
    return '<div class="ev-axis">%s</div>' % "".join(marks)


def timeline(pieces, start, end):
    total = minutes(start, end)
    if total <= 0:
        return '<div class="ev-line"></div>'
    bars = []
    for kind, a, b in pieces:
        left = 100.0 * minutes(start, a) / total
        width = 100.0 * minutes(a, b) / total
        if width <= 0:
            continue
        tip = "%s, %s to %s (%s)" % (
            {"empty": "empty", "occupied": "people in",
             "unknown": "no state yet",
             "unwatched": "not watched"}[kind], ov.clock(a), ov.clock(b),
            span(minutes(a, b)))
        bars.append('<i class="%s" style="left:%.3f%%;width:%.3f%%" '
                    'title="%s"></i>' % (kind, left, width, esc(tip)))
    return '<div class="ev-line">%s</div>' % "".join(bars)


def page(theme, rows, now_rows, start, end, day_text, window_text, base,
         coverage=None):
    """The whole view: right now, then the day, room by room."""
    c = colours(theme)
    h = [ev.css(theme), EXTRA % c, '<div class="ec">']

    # ---- right now ------------------------------------------------------
    h.append('<div class="ec-h" style="margin-top:6px"><span class="t">Empty '
             'right now</span><span class="c">rooms with a unit somebody could'
             ' switch off, longest first</span></div>')
    if now_rows:
        chips = []
        for r in now_rows[:12]:
            unit = {"on": "unit read ON", "off": "unit read off"}.get(
                r["ac_state"], "unit not read")
            chips.append(
                '<a class="ev-chip" target="_self" href="%s#roomdetail">'
                '<b>%s</b><span class="d">%s</span><span class="s">since %s'
                ' &middot; %s</span></a>'
                % (esc(ov.link(base, room=r["room"])), esc(ov.short(r["room"])),
                   span(r["minutes"]), esc(ov.clock(r["since"])), unit))
        more = len(now_rows) - 12
        h.append('<div class="ev-chips">%s</div>%s' % (
            "".join(chips),
            '<div class="en-note">and %d more.</div>' % more if more > 0
            else ""))
    else:
        h.append('<div class="ec-card ec-calm">No room with a unit is empty '
                 'right now.</div>')

    # ---- the day --------------------------------------------------------
    # The figures are about rooms somebody could switch off: a server room
    # empty all day is the system working, not the emptiest room.
    counted = [r for r in rows if r["seen"] > 0 and r["alerts"]]
    total_empty = sum(r["empty"] for r in counted)
    h.append('<div class="ec-h"><span class="t">%s</span><span class="c">%s'
             '</span></div>' % (esc(day_text), esc(window_text)))
    if start is None or end is None or end <= start:
        h.append('<div class="ec-card ec-calm">Nothing to count in this '
                 'window yet: it has not started, or this is not a working '
                 'day. Try the whole day.</div></div>')
        return "".join(h)

    h.append('<div class="en-tiles">')
    h.append(ev.tile("Empty, all these rooms", span(total_empty),
                     "room-time empty while watched; two rooms for an hour "
                     "is two hours"))
    if counted:
        worst = max(counted, key=lambda r: r["empty"])
        h.append(ev.tile("Emptiest", esc(ov.short(worst["room"])),
                         "%s empty of %s watched (%.0f%%)"
                         % (span(worst["empty"]), span(worst["seen"]),
                            100 * worst["share"])))
        longest = max(counted, key=lambda r: r["longest"])
        if longest["longest"] > 0:
            h.append(ev.tile("Longest single stretch",
                             span(longest["longest"]),
                             "%s, %s to %s" % (
                                 esc(ov.short(longest["room"])),
                                 esc(ov.clock(longest["longest_from"])),
                                 esc(ov.clock(longest["longest_to"])))))
        busy = max(counted, key=lambda r: r["occupied"])
        h.append(ev.tile("In use the longest", esc(ov.short(busy["room"])),
                         "%s with people in" % span(busy["occupied"])))
    h.append('</div>')

    if coverage is not None:
        watched_m, window_m = coverage
        if window_m > 0 and watched_m < window_m - 10:
            h.append('<div class="en-warn">%s The cameras were read for %s of '
                     'the %s in this window. The hatched parts were not '
                     'watched and are counted as nothing, neither empty nor '
                     'in use.</div>' % (ov.WARN, span(watched_m),
                                        span(window_m)))

    key = ('<span class="ev-key"><span><i style="background:%s"></i>empty'
           '</span><span><i style="background:%s"></i>people in</span>'
           '<span><i style="background:%s"></i>no state yet</span>'
           '<span><i style="background:repeating-linear-gradient(135deg,%s 0 '
           '2px,transparent 2px 4px)"></i>not watched</span></span>'
           % (c["empty"], c["occ"], c["unknown"], c["hatch"]))
    h.append('<div class="ec-card" style="margin-top:14px;padding:14px 20px 8px">'
             '<div class="ev-head"><div class="gap">%s</div><div class="tl">%s'
             '</div><div class="gap"></div></div>' % (key, axis(start, end)))
    for r in rows:
        if r["empty"] >= 1:
            value = '<b>%s</b>' % span(r["empty"])
        else:
            value = '<b class="none">never empty</b>' if r["seen"] else \
                '<b class="none">&mdash;</b>'
        bits = []
        if r["seen"]:
            bits.append("of %s watched" % span(r["seen"]))
        if r["longest"] >= 1 and r["longest"] < r["empty"] - 0.5:
            bits.append("longest %s" % span(r["longest"]))
        unit = ""
        if r["has_unit"]:
            unit = (" &middot; %d unit%s" % (r["ac_count"], ""
                                            if r["ac_count"] == 1 else "s")
                    if r["ac_count"] else " &middot; unit")
            if not r["alerts"]:
                unit += ", cooled on purpose"
        h.append(
            '<div class="ev-row"><a class="nm" target="_self" '
            'href="%s#roomdetail"><b>%s</b><span>%s%s</span></a>'
            '<div class="tl">%s</div><div class="v">%s<span>%s</span></div>'
            '</div>'
            % (esc(ov.link(base, room=r["room"])), esc(ov.short(r["room"])),
               esc(r["zone"] or ""), unit, timeline(r["pieces"], start, end),
               value, esc(" · ".join(bits))))
    h.append('</div><div class="en-note">Measured from the cameras: a room '
             'is empty when no camera on it sees a person. Hover a bar for '
             'its times. Tap a room for its day in detail.</div></div>')
    return "".join(h)
