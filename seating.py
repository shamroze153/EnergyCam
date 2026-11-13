"""Desks and how full they are: the admin's seating sheet against the cameras.

Shamroze, 13 Nov: the admin team keeps a seating sheet -- every workstation
in every room, given to somebody ("allocated") or not. It is an estimate,
and desks stay where they are even when people move between them. This
puts the cameras' head counts against it, room by room, the way Envoy's
workplace utilization puts badge swipes against capacity: how many desks,
how many given to somebody, how many people were really there at the
busiest moment and on average, and which rooms sit empty.

seating.yaml holds counts only. The sheet has people's names in it and
this repository is public: import_seating.py reads a downloaded copy and
writes nothing but numbers.
"""
import os
from statistics import median

import yaml

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seating.yaml")

HOLD = 10            # minutes: a busiest moment has to last this long
LEAST = 0.5          # of the office day watched, for the day to count


def load(path=PATH):
    """{"as_of", "source", "spaces": [...]} -- no file, no spaces."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except OSError:
        return {"as_of": None, "source": None, "spaces": []}
    spaces = []
    for s in data.get("spaces") or []:
        seats = int(s.get("seats") or 0)
        given = int(s.get("allocated") or 0)
        spaces.append({
            "name": s["name"], "campus": s.get("campus") or "",
            "building": s.get("building") or s.get("campus") or "",
            "floor": s.get("floor") or "", "codes": list(s.get("codes") or []),
            "seats": seats, "allocated": given,
            "free": max(0, seats - given),
            "in_use": int(s.get("in_use") or 0),
            "out_of_order": int(s.get("out_of_order") or 0),
            "teams": dict(s.get("teams") or {}),
            "rooms": list(s.get("rooms") or []),
            "note": s.get("note") or ""})
    return {"as_of": data.get("as_of"), "source": data.get("source"),
            "spaces": spaces}


def dump(data):
    """seating.yaml's text: the header, then one block a space."""
    def q(v):
        text = yaml.safe_dump(v, default_flow_style=True, width=1000,
                              allow_unicode=True)
        # A plain scalar comes back as "value\n...\n": the "..." ends the
        # document, and is not part of the value.
        if text.endswith("...\n"):
            text = text[:-4]
        return text.strip()

    out = [
        "# Desks per room, from the admin team's seating sheet. COUNTS ONLY:",
        "# the sheet has people's names and codes and this repository is",
        "# public. Refresh with:  python import_seating.py <seating tab .csv>",
        "#",
        "# seats      workstations in the room (fixed, even when people move)",
        "# allocated  given to somebody; the rest are free",
        "# in_use     the sheet's own \"Occupied\"",
        "# teams      allocated desks by business unit",
        "# rooms      the rooms.yaml rooms whose cameras see these desks;",
        "#            none yet means no camera sees them (counted, not watched)",
        "# codes      the sheet's Room Code(s): how a refresh finds the space",
        "",
        "as_of: %s" % q(str(data.get("as_of") or "")),
        "source: %s" % q(data.get("source") or ""),
        "",
        "spaces:"]
    for s in data["spaces"]:
        out.append("  - name: %s" % q(s["name"]))
        for key in ("campus", "building", "floor"):
            if s.get(key):
                out.append("    %s: %s" % (key, q(s[key])))
        out.append("    codes: %s" % q(list(s.get("codes") or [])))
        for key in ("seats", "allocated", "in_use", "out_of_order"):
            if s.get(key) or key in ("seats", "allocated"):
                out.append("    %s: %d" % (key, int(s.get(key) or 0)))
        if s.get("teams"):
            out.append("    teams: %s" % q(dict(sorted(
                s["teams"].items(), key=lambda kv: (-kv[1], kv[0])))))
        if s.get("rooms"):
            out.append("    rooms:")
            out.extend("      - %s" % q(r) for r in s["rooms"])
        if s.get("note"):
            out.append("    note: %s" % q(s["note"]))
    return "\n".join(out) + "\n"


def combined(minute_lists):
    """Several rooms' minutes as one space: people added up, a minute
    unknown only where no camera of the space was watching."""
    if not minute_lists:
        return [None] * 1440
    out = []
    for values in zip(*minute_lists):
        seen = [v for v in values if v is not None]
        out.append(sum(seen) if seen else None)
    return out


def held_peak(values, hold=HOLD):
    """The most people present for `hold` minutes running.

    One pass that counts a coat as a person is a spike of a few minutes;
    a room really that full stays so for longer.
    """
    best = 0
    run = []
    for v in values:
        if v is None:
            run = []
            continue
        run.append(v)
        if len(run) > hold:
            run.pop(0)
        if len(run) == hold:
            best = max(best, min(run))
    return best


def day_figures(minutes, work=(10.0, 20.0), least=LEAST):
    """{"peak", "mean", "busy"} for the office hours of one day, or None
    when the cameras watched less than `least` of them."""
    a, b = int(work[0] * 60), int(work[1] * 60)
    window = list(minutes[a:b])
    seen = [v for v in window if v is not None]
    if not window or len(seen) < least * len(window):
        return None
    return {"peak": held_peak(window), "mean": sum(seen) / float(len(seen)),
            "busy": sum(1 for v in seen if v) / float(len(seen))}


def summary(days):
    """Over the days watched: the usual busiest moment (the median day's),
    the highest, and the average across office hours."""
    days = [d for d in days if d]
    if not days:
        return None
    return {"days": len(days),
            "peak": median([d["peak"] for d in days]),
            "top": max(d["peak"] for d in days),
            "mean": sum(d["mean"] for d in days) / len(days),
            "busy": sum(d["busy"] for d in days) / len(days)}


def verdict(s, seats):
    """(key, words) for a space's card."""
    if not s:
        return "unwatched", "not watched yet"
    if not s["top"]:
        return "empty", "nobody seen in %d day%s" % (
            s["days"], "" if s["days"] == 1 else "s")
    if not seats:
        return "good", "no desks on the sheet"
    r = s["peak"] / float(seats)
    if r > 1.0:
        return "over", "more people than desks"
    if r < 0.25:
        return "low", "hardly used"
    if r < 0.5:
        return "half", "under half full at its busiest"
    return "good", "well used"


ORDER = {"empty": 0, "low": 1, "half": 2, "good": 3, "over": 4,
         "unwatched": 5}


def hourly(minutes, work=(10.0, 20.0), least=LEAST):
    """Average people each hour of the office day; None where unwatched."""
    out = []
    for h in range(int(work[0]), int(-(-work[1] // 1))):
        part = minutes[h * 60:(h + 1) * 60]
        seen = [v for v in part if v is not None]
        out.append(sum(seen) / float(len(seen))
                   if len(seen) >= least * 60 else None)
    return out


def campus_totals(items):
    """Desks, given, watched, and right now, for a list of space items."""
    watched = [i for i in items if i["rooms"]]
    now = [i["now"] for i in watched if i.get("now") is not None]
    return {"seats": sum(i["seats"] for i in items),
            "allocated": sum(i["allocated"] for i in items),
            "free": sum(i["free"] for i in items),
            "watched_seats": sum(i["seats"] for i in watched),
            "now": sum(now) if now else None,
            "spaces": len(items), "watched": len(watched)}


def teams(items):
    """Allocated desks by team, biggest first."""
    out = {}
    for i in items:
        for t, n in (i.get("teams") or {}).items():
            out[t] = out.get(t, 0) + int(n)
    return sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------- drawing

CSS = (
    "<style>.st-tiles{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0 8px}"
    ".st-tile{flex:1 1 140px;border-radius:14px;padding:12px 16px;border:1px"
    " solid var(--stl);background:var(--sts)}"
    ".st-tile .v{font-size:1.55rem;font-weight:740;line-height:1.15}"
    ".st-tile .l{font-size:.74rem;margin-top:3px;opacity:.8}"
    ".st-tile .n{font-size:.66rem;opacity:.65;margin-top:1px}"
    ".st-g{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,"
    "1fr));gap:12px;margin:8px 0 6px}"
    ".st-c{border-radius:14px;padding:12px 14px 10px;border:1px solid "
    "var(--stl);background:var(--sts)}"
    ".st-c .h{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}"
    ".st-c .h b{font-size:.98rem}.st-c .h span{font-size:.7rem;opacity:.7}"
    ".st-chip{display:inline-block;font-size:.66rem;font-weight:650;padding:"
    "1px 8px;border-radius:999px;margin-left:auto}"
    ".st-bar{position:relative;height:14px;border-radius:4px;overflow:hidden;"
    "margin:9px 0 5px}"
    ".st-bar span{position:absolute;top:0;bottom:0;left:0}"
    ".st-line{font-size:.75rem;line-height:1.45}"
    ".st-sec{font-size:1.02rem;font-weight:720;margin:22px 0 2px}"
    ".st-sub{font-size:.74rem;line-height:1.5;opacity:.8}"
    ".st-heat{border-collapse:separate!important;border-spacing:2px;"
    "font-size:.66rem;margin:8px 0 4px;width:100%;table-layout:fixed;"
    "border:none!important}"
    ".st-heat tr{background:none!important;border:none!important}"
    ".st-heat td{height:24px;border-radius:4px;text-align:center;padding:0"
    "!important;border:none!important}"
    ".st-heat th{font-weight:500;opacity:.7;white-space:nowrap;padding:0 2px"
    "!important;border:none!important;background:none!important;"
    "text-align:left}"
    ".st-heat th.d{text-align:left;width:5.2em}"
    ".st-key{display:flex;gap:4px;align-items:center;font-size:.64rem;"
    "opacity:.85;flex-wrap:wrap}"
    ".st-key i{display:inline-block;width:18px;height:10px;border-radius:2px}"
    ".st-t{font-size:.74rem;border-collapse:collapse;width:100%}"
    ".st-t td,.st-t th{padding:4px 6px;border-bottom:1px solid var(--stl);"
    "text-align:left}.st-t td.r,.st-t th.r{text-align:right}"
    ".st details summary{cursor:pointer;font-size:.78rem;opacity:.85}"
    "@media (max-width:520px){.st-g{grid-template-columns:1fr}"
    ".st-tiles{gap:8px}.st-tile{padding:10px 12px}"
    ".st-tile .v{font-size:1.3rem}"
    ".st-heat{font-size:.58rem}.st-heat th.d{width:3.6em}}</style>")

# Sequential blue, light to dark (the dashboard's own people-blue ramp);
# on the dark page the order turns round so "few" recedes into the page.
RAMP_LIGHT = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]
RAMP_DARK = ["#13294a", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"]
FULL = 0.5          # this share of the desks, and over, is the darkest step


def shade(share, ramp):
    """The ramp's colour for a share of the desks, blended between steps.

    Continuous rather than in bins: an office that runs between a tenth
    and a third of its desks all day was one flat colour in bins (13 Nov),
    and the hours it filled up were the thing to see.
    """
    t = max(0.0, min(1.0, share / FULL)) * (len(ramp) - 1)
    i = min(int(t), len(ramp) - 2)
    f = t - i
    a, b = ramp[i], ramp[i + 1]
    mix = [round(int(a[k:k + 2], 16) * (1 - f) + int(b[k:k + 2], 16) * f)
           for k in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(mix)


def ink_index(share, ramp):
    """Which end of the ramp a share sits nearer, for the number on it."""
    return min(len(ramp) - 1, int(round(max(0.0, min(1.0, share / FULL))
                                        * (len(ramp) - 1))))


def _pct(a, b):
    return "%d%%" % round(100.0 * a / b) if b else "&ndash;"


def _n(v):
    if v is None:
        return "&ndash;"
    return "%d" % round(v)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def tile(label, value, note, c):
    return ('<div class="st-tile"><div class="v" style="color:%s">%s</div>'
            '<div class="l" style="color:%s">%s</div><div class="n" '
            'style="color:%s">%s</div></div>'
            % (c["text"], value, c["muted"], label, c["faint"], note))


def seat_bar(it, c):
    """The desks as a track: given to somebody (outlined), the usual
    busiest moment (blue), the office-hours average (the darker part)."""
    seats = max(1, it["seats"])
    s = it.get("summary")
    parts = ['<span style="width:%.1f%%;background:%s;opacity:.55" title="'
             '%d of %d desks given to somebody"></span>'
             % (min(100.0, 100.0 * it["allocated"] / seats), c["given"],
                it["allocated"], it["seats"])]
    if s:
        parts.append('<span style="width:%.1f%%;background:%s" title="usually'
                     ' %s at once at the busiest"></span>'
                     % (min(100.0, 100.0 * s["peak"] / seats), c["peak"],
                        _n(s["peak"])))
        parts.append('<span style="width:%.1f%%;background:%s" title="%s on'
                     ' average in office hours"></span>'
                     % (min(100.0, 100.0 * s["mean"] / seats), c["mean"],
                        _n(s["mean"])))
    return ('<div class="st-bar" style="background:%s;border:1px solid %s">%s'
            '</div>' % (c["track"], c["line"], "".join(parts)))


def card(it, c):
    key, words = it["verdict"]
    tone = c["tones"].get(key, c["tones"]["unwatched"])
    s = it.get("summary")
    bits = ["<b>%d</b> desk%s" % (it["seats"], "" if it["seats"] == 1 else "s"),
            "%d given" % it["allocated"]]
    if s:
        bits.append("usually <b>%s</b> at once at the busiest (%s)"
                    % (_n(s["peak"]), _pct(s["peak"], it["seats"])))
        bits.append("%s on average" % _n(s["mean"]))
        if s["top"] > s["peak"]:
            bits.append("at most %d" % s["top"])
    if it.get("now") is not None:
        bits.append("now %d" % it["now"])
    lines = ['<div class="st-line" style="color:%s">%s</div>'
             % (c["muted"], " &middot; ".join(bits))]
    if s and it["allocated"] and s["peak"] < it["allocated"]:
        lines.append('<div class="st-line" style="color:%s">%d given desk%s'
                     ' empty even at the busiest moment</div>'
                     % (c["muted"], it["allocated"] - round(s["peak"]),
                        "" if it["allocated"] - round(s["peak"]) == 1
                        else "s"))
    if it.get("ac"):
        lines.append('<div class="st-line" style="color:%s">&#10052; %s</div>'
                     % (c["muted"], esc(it["ac"])))
    team = ", ".join("%s %d" % (esc(t), n) for t, n in sorted(
        it["teams"].items(), key=lambda kv: -kv[1])[:3])
    where = " &middot; ".join(x for x in (esc(it["floor"]),
                                          esc(it["building"])) if x)
    return ('<div class="st-c"><div class="h"><b style="color:%s">%s</b>'
            '<span style="color:%s">%s</span><span class="st-chip" style="'
            'background:%s;color:%s">%s</span></div>%s%s%s</div>'
            % (c["text"], esc(it["name"]), c["muted"], where, tone[0],
               tone[1], words, seat_bar(it, c), "".join(lines),
               ('<div class="st-line" style="color:%s;font-size:.68rem">%s'
                '</div>' % (c["faint"], team)) if team else ""))


def heat(rows, work, c, ramp):
    """Days down, office hours across: how full the watched desks were."""
    if not rows:
        return ""
    hours = list(range(int(work[0]), int(-(-work[1] // 1))))

    def h12(h):
        return "%d%s" % (h % 12 or 12, "a" if h < 12 else "p")
    head = '<tr><th class="d"></th>%s</tr>' % "".join(
        '<th>%s</th>' % (h12(h) if i % 2 == 0 else "")
        for i, h in enumerate(hours))
    body = []
    for label, seats, values in rows:
        cells = []
        # Today's row stops at now: the hours still to come are blank,
        # not "not watched".
        cells_later = ["<td></td>"] * max(0, len(hours) - len(values))
        for h, v in zip(hours, values):
            if v is None:
                cells.append('<td style="background:%s" title="%s %s: not '
                             'watched"></td>' % (c["unwatched"], label, h12(h)))
                continue
            share = v / float(seats) if seats else 0
            cells.append('<td style="background:%s;color:%s" title="%s %s:'
                         ' %d people, %s of %d desks">%s</td>'
                         % (shade(share, ramp),
                            c["cell_ink"][ink_index(share, ramp)], label,
                            h12(h), round(v), _pct(v, seats), seats,
                            "%d" % round(100 * share)))
        body.append('<tr><th class="d">%s</th>%s</tr>'
                    % (label, "".join(cells + cells_later)))
    key = ('0%%<i style="width:120px;background:linear-gradient(90deg,%s)">'
           '</i>%d%%+' % (",".join(ramp), round(100 * FULL)))
    return ('<table class="st-heat">%s%s</table><div class="st-key" '
            'style="color:%s">%s<i style="background:%s;margin-left:12px">'
            '</i>not watched &middot; each number is the %% of the desks'
            ' cameras see that had somebody at them, that hour</div>'
            % (head, "".join(body), c["muted"], key, c["unwatched"]))


def team_bars(pairs, free, c):
    if not pairs:
        return ""
    top = max([n for _, n in pairs] + [free, 1])
    rows = []
    for name, n in pairs + [("Not given to anyone", free)]:
        ink = c["peak"] if name != "Not given to anyone" else c["track_dark"]
        rows.append(
            '<div style="display:grid;grid-template-columns:9.5em 1fr 2.6em;'
            'gap:8px;align-items:center;font-size:.74rem;margin:3px 0">'
            '<span style="color:%s;white-space:nowrap;overflow:hidden;'
            'text-overflow:ellipsis">%s</span><span style="height:10px;'
            'border-radius:0 4px 4px 0;background:%s;width:%.1f%%"></span>'
            '<span style="color:%s;text-align:right">%d</span></div>'
            % (c["muted"], esc(name), ink, 100.0 * n / top, c["text"], n))
    return "".join(rows)


def campus_block(name, items, heat_rows, campus_fig, work, c, ramp):
    """One campus: four numbers, the hours, the rooms, what no camera sees."""
    t = campus_totals(items)
    watched = [i for i in items if i["rooms"]]
    unseen = [i for i in items if not i["rooms"]]
    out = ['<div class="st-sec" style="color:%s">%s <span style="font-weight:'
           '400;font-size:.78rem;color:%s">&middot; %d desks in %d rooms</span>'
           '</div>' % (c["text"], esc(name), c["muted"], t["seats"],
                       t["spaces"])]
    busiest = ("<b>%s</b>" % _n(campus_fig["peak"])) if campus_fig else "&ndash;"
    out.append('<div class="st-tiles">%s%s%s%s</div>' % (
        tile("desks given to somebody", _pct(t["allocated"], t["seats"]),
             "%d of %d &middot; %d free" % (t["allocated"], t["seats"],
                                            t["free"]), c),
        tile("at their desks, busiest moment", busiest,
             ("people at once on a usual day: %s of the %d desks cameras see"
              % (_pct(campus_fig["peak"], t["watched_seats"]),
                 t["watched_seats"])) if campus_fig else "not watched yet", c),
        tile("full, on average", _pct(campus_fig["mean"], t["watched_seats"])
             if campus_fig else "&ndash;",
             "of the watched desks, across office hours", c),
        tile("right now", _n(t["now"]),
             "people in the %d watched rooms (%s)" % (
                 t["watched"], _pct(t["now"] or 0, t["watched_seats"]))
             if t["now"] is not None else "no reading", c)))
    if heat_rows:
        out.append('<div class="st-sub" style="color:%s;margin-top:10px">'
                   'How full, hour by hour &mdash; every working day watched'
                   '</div>%s' % (c["muted"], heat(heat_rows, work, c, ramp)))
    if watched:
        watched = sorted(watched, key=lambda i: (
            ORDER.get(i["verdict"][0], 9),
            (i["summary"]["peak"] / float(i["seats"]))
            if i.get("summary") and i["seats"] else 9, -i["seats"]))
        out.append('<div class="st-sub" style="color:%s;margin-top:12px">'
                   'Rooms, emptiest first &mdash; the bar is the room\'s desks:'
                   ' <span style="color:%s">&#9632;</span> given to somebody,'
                   ' <span style="color:%s">&#9632;</span> people at once at the'
                   ' busiest, <span style="color:%s">&#9632;</span> on average'
                   '</div><div class="st-g">%s</div>'
                   % (c["muted"], c["given"], c["peak"], c["mean"],
                      "".join(card(i, c) for i in watched)))
    if unseen:
        rows = "".join(
            '<tr><td>%s</td><td>%s</td><td class="r">%d</td><td class="r">%d'
            '</td></tr>' % (esc(i["name"]), esc(" &middot; ".join(
                x for x in (i["floor"], i["building"]) if x)), i["seats"],
                i["allocated"])
            for i in sorted(unseen, key=lambda i: -i["seats"]))
        out.append(
            '<details style="margin-top:10px"><summary style="color:%s">%d desks'
            ' no camera sees yet, in %d rooms (counted from the sheet, not '
            'watched)</summary><table class="st-t" style="color:%s"><tr><th>'
            'Room</th><th>Where</th><th class="r">Desks</th><th class="r">Given'
            '</th></tr>%s</table></details>'
            % (c["muted"], sum(i["seats"] for i in unseen), len(unseen),
               c["text"], rows))
    pairs = teams(items)
    if pairs:
        out.append('<details style="margin-top:6px"><summary style="color:%s">'
                   'Desks by team</summary>%s</details>'
                   % (c["muted"], team_bars(pairs, t["free"], c)))
    return "".join(out)


def page(blocks, colours, ramp, work, as_of, source, days):
    """blocks: [(campus, items, heat_rows, campus_fig)]."""
    c = colours
    intro = ('<div class="st-sub" style="color:%s">Desks from the admin team\'s'
             ' seating sheet%s &mdash; an estimate; desks stay put when people'
             ' move. People from the cameras, office hours %s to %s, over the'
             ' last %d working day%s. "Busiest" is the most people present'
             ' for ten minutes running, on the median day. A room far below'
             ' its sheet means people away &mdash; or cameras that see only'
             ' part of it.</div>'
             % (c["muted"], (" (%s)" % esc(as_of)) if as_of else "",
                _clock(work[0]), _clock(work[1]), days,
                "" if days == 1 else "s"))
    return (CSS + '<div class="st" style="--stl:%s;--sts:%s">%s%s</div>'
            % (c["line"], c["surface"], intro, "".join(
                campus_block(n, i, h, f, work, c, ramp)
                for n, i, h, f in blocks)))


def _clock(hours):
    h = int(hours)
    m = int(round((hours - h) * 60))
    return "%d%s%s" % (h % 12 or 12, (":%02d" % m) if m else "",
                       "am" if h < 12 else "pm")
