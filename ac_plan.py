"""Recommended AC timings for a room, from its usual days.

Asked for on 13 Nov (Shamroze): under Who comes when, one line a room --
"the cafe: all off until 9:30, one AC 9:30-12, all six 12-3, five 3-6, then
off" -- worked out from when people are really there. The office runs 10 to
8; after that it is mostly office boys, now and then somebody working late.

How a line is made:

  * The day in half hours. For each watched day, the average number of
    people in each half hour; across days, a busy-day figure (the 75th
    percentile, so an ordinary busy day is covered and one crowded lunch is
    not the rule) and how many of the days anybody was there at all.
  * A half hour needs the AC when people are usually there: on at least
    ON_SHARE of the days in working hours. Outside them only when it is
    the rule (LATE_SHARE of days) and then one unit -- the office boy's
    round and the occasional late worker do not cool a hall.
  * How many units: in proportion to the room's own busiest half hour.
    Half the people of a full room, half the units -- at least one, never
    more than the room has.
  * Smoothed: a dip shorter than an hour keeps the units of the hour
    around it (switching a unit off for twenty minutes saves nothing and
    nobody does it), and the result is said as a few stretches.

No Streamlit and no database: minutes in, stretches out.
"""
import math
from datetime import timedelta

DAY, MINUTE = timedelta(days=1), timedelta(minutes=1)
SLOT = 30                     # minutes
SLOTS = 1440 // SLOT
ON_SHARE = 0.4                # of days somebody was there, in working hours
LATE_SHARE = 0.6              # the same, outside them
MIN_PEOPLE = 0.5              # people on average in the half hour
# One watched day is enough for a first guess: 141 was mapped on 11 Nov and
# Shamroze wants its cafe now. Each line says how many days it is from, and
# every working day makes it firmer. A half hour no day watched is "not
# watched yet", never "off" -- the first cut called the cafe off until 2 pm
# because 11 Nov's morning, before it was mapped, had no data.
MIN_DAYS = 1


def _quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    pos = (len(values) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def slots(minutes_by_day):
    """Per half hour: (busy-day people, share of days anybody was there,
    days watched). minutes_by_day: one 1440-list a day, people per minute
    and None where nobody watched (day_story.by_minute)."""
    out = []
    for s in range(SLOTS):
        means, present = [], 0
        for mins in minutes_by_day:
            part = [v for v in mins[s * SLOT:(s + 1) * SLOT] if v is not None]
            if len(part) < SLOT // 2:
                continue                       # this half hour not watched
            means.append(sum(part) / float(len(part)))
            # Somebody there for five minutes or more, not a passer-by.
            if sum(1 for v in part if v) >= 5:
                present += 1
        out.append((_quantile(means, 0.75) if means else None,
                    (present / float(len(means))) if means else None,
                    len(means)))
    return out


def plan(minutes_by_day, units, work=(10.0, 20.0), cap=None):
    """[(from minute, to minute, units on)] over the whole day -- units None
    for a half hour no day watched -- or None where no day was watched.

    cap: the most units the room was seen running, where a camera reads
    them all. The busiest half hour then gets that many, not every unit:
    the cafe ran two or three towers through its fullest lunch, and a plan
    that asked for six was asking for more than the room has ever needed.
    """
    if units < 1:
        return None
    if cap:
        units = max(1, min(units, int(cap)))
    table = slots(minutes_by_day)
    if max((n for _, _, n in table), default=0) < MIN_DAYS:
        return None
    full = max((p for p, _, n in table if p is not None and n >= MIN_DAYS),
               default=0.0)
    want = []
    for s, (people, share, n) in enumerate(table):
        hour = s * SLOT / 60.0
        inside = work[0] <= hour < work[1]
        if n < MIN_DAYS:
            want.append(None)                  # nobody watched: not known
        elif people is None or people < MIN_PEOPLE:
            want.append(0)
        elif inside and share >= ON_SHARE:
            want.append(max(1, min(units, int(math.ceil(
                units * people / full - 1e-9)) if full else 1)))
        elif not inside and share >= LATE_SHARE and n >= 2:
            # After hours only as a habit: one day's 1 am round by the guard
            # put the IT Sub Store "on 1am-1:30am" in the first cut.
            want.append(1)
        else:
            want.append(0)
    # A dip of under an hour between two higher stretches keeps their units.
    smooth = list(want)
    known = [-1 if w is None else w for w in want]
    for s in range(1, SLOTS - 1):
        if want[s] is None:
            continue
        left = max(known[max(0, s - 2):s])
        right = max(known[s + 1:s + 3])
        if want[s] < min(left, right):
            smooth[s] = min(left, right)
    # And an "on" of under an hour with nothing either side is a visit, not
    # a routine: whoever is there switches it on.
    s = 0
    while s < SLOTS:
        if smooth[s]:
            e = s
            while e < SLOTS and smooth[e]:
                e += 1
            if e - s < 60 // SLOT:
                for k in range(s, e):
                    smooth[k] = 0
            s = e
        else:
            s += 1
    bands = []
    for s, n in enumerate(smooth):
        a, b = s * SLOT, (s + 1) * SLOT
        if bands and bands[-1][2] == n:
            bands[-1] = (bands[-1][0], b, n)
        else:
            bands.append((a, b, n))
    return bands


def units_minutes(stamps, values, start, alive):
    """1440 minutes of units running from one room's rows: each row's value
    (units on, 0 for off, None for not read) holds until the next row; a
    minute the loop was not running is None. stamps/values in time order,
    the row before start included; alive: [(from, to)] the loop ran."""
    out = [None] * 1440
    for i, t in enumerate(stamps):
        b = stamps[i + 1] if i + 1 < len(stamps) else start + DAY
        lo = max(0, int((t - start).total_seconds() // 60))
        hi = min(1440, int(-(-(b - start).total_seconds() // 60)))
        for m in range(lo, hi):
            out[m] = values[i]
    for m in range(1440):
        at = start + MINUTE * m
        if not any(a <= at < b for a, b in alive):
            out[m] = None
    return out


def ran(units_by_day):
    """What the read units usually did, half hour by half hour, as bands
    like plan()'s: the median across days of each half hour's average units
    running, None where no day read it. Shamroze, 13 Nov: for the rooms a
    camera reads, show what was observed beside what is recommended."""
    want = []
    for s in range(SLOTS):
        means = []
        for mins in units_by_day:
            part = [v for v in mins[s * SLOT:(s + 1) * SLOT] if v is not None]
            if len(part) >= SLOT // 2:
                means.append(sum(part) / float(len(part)))
        want.append(int(round(_quantile(means, 0.5))) if means else None)
    if all(w is None for w in want):
        return None
    bands = []
    for s, n in enumerate(want):
        a, b = s * SLOT, (s + 1) * SLOT
        if bands and bands[-1][2] == n:
            bands[-1] = (bands[-1][0], b, n)
        else:
            bands.append((a, b, n))
    return bands


def unit_hours(bands):
    return sum((b - a) / 60.0 * n for a, b, n in bands or [] if n)


def _clock(minute):
    h, m = divmod(int(minute) % 1440, 60)
    half = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return ("%d%s" % (h12, half)) if not m else ("%d:%02d%s" % (h12, m, half))


PHASES = [("&#127769;", "Night", 0, 6), ("&#127749;", "Arriving", 6, 10),
          ("&#9728;&#65039;", "Working hours", 10, 18),
          ("&#127751;", "Going home", 18, 20),
          ("&#127747;", "After hours", 20, 24)]


def _units_word(n, units):
    if n is None:
        return "not watched yet"
    if not n:
        return "off"
    if n >= units and units > 1:
        return "all %d AC" % units
    return "%d AC" % n


def phase_lines(bands, units):
    """The day in five parts, each said plainly: [(icon, name, from hour,
    to hour, text)]. Shamroze, 13 Nov: "first say early morning run it till
    this time, then from here to here this many"."""
    out = []
    for icon, name, a, b in PHASES:
        lo, hi = a * 60, b * 60
        parts = []
        for x, y, n in bands or []:
            x2, y2 = max(x, lo), min(y, hi)
            if y2 <= x2:
                continue
            if parts and parts[-1][2] == n:
                parts[-1] = (parts[-1][0], y2, n)
            else:
                parts.append((x2, y2, n))
        if not parts or all(n is None for _, _, n in parts):
            text = "not watched yet"
        elif len(parts) == 1:
            n = parts[0][2]
            text = "off" if not n else "%s the whole time" % _units_word(
                n, units)
        else:
            text = " &rarr; ".join(
                "%s %s&ndash;%s" % (_units_word(n, units), _clock(x), _clock(y))
                for x, y, n in parts)
        out.append((icon, name, a, b, text))
    return out


CARD_CSS = (
    "<style>.acg{display:grid;grid-template-columns:repeat(auto-fill,"
    "minmax(310px,1fr));gap:14px;margin:10px 0 6px}"
    ".acc{border-radius:16px;padding:14px 16px 12px;border:1px solid var(--acl);"
    "background:var(--acs);box-shadow:0 1px 0 rgba(0,0,0,.03)}"
    ".acc-h{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}"
    ".acc-h b{font-size:1.02rem}.acc-h span{font-size:.72rem;opacity:.7}"
    ".acc-save{font-size:.8rem;margin:3px 0 8px}"
    ".acc-ph{display:grid;grid-template-columns:1.6em 7.4em 1fr;gap:2px 6px;"
    "align-items:baseline;font-size:.8rem;padding:4px 0;border-top:1px dashed "
    "var(--acl)}"
    ".acc-ph .n{opacity:.75;font-size:.74rem;line-height:1.25}"
    ".acc-ph .n small{display:block;opacity:.75;font-size:.66rem}"
    ".acc-ph .v b{font-weight:700}"
    ".acc details{margin-top:8px}.acc summary{cursor:pointer;font-size:.76rem;"
    "opacity:.8;list-style:none}.acc summary::-webkit-details-marker"
    "{display:none}"
    ".acc summary:before{content:'\\25B8 ';}"
    ".acc details[open] summary:before{content:'\\25BE ';}"
    "@media (max-width:520px){.acg{grid-template-columns:1fr}}</style>")


def page(items, colours, days, work=(10.0, 20.0), rate=67.0, heading=True):
    """Every room a card (Shamroze, 13 Nov: "blocks, all on one page, the
    day said in parts; click a block for its detail").

    items: [{"room", "units", "bands", "saving_rs"}, and where a camera
    reads the units "ran" (bands seen running), "read" and "cap"], best
    saving first. colours: {"text", "muted", "faint", "line", "off", "on",
    "surface"}, and "ran" for the observed bar (amber by default).
    heading=False gives the cards alone.
    """
    if not items:
        return ""
    c = colours

    def bar(bands, units, ink, label, height=12):
        segs = []
        for a, b, n in bands:
            share = n / float(units) if units and n else 0
            if n is None:
                fill, op, what = c["surface"], 1.0, "not watched yet"
            elif not n:
                fill, op, what = c["off"], 1.0, "off"
            else:
                fill, op = ink, 0.35 + 0.65 * min(1.0, share)
                what = "%d of %d" % (n, units)
            segs.append(
                '<span title="%s · %s–%s: %s" style="position:absolute;'
                'left:%.3f%%;width:%.3f%%;top:0;bottom:0;background:%s;'
                'opacity:%.2f;border-right:1px solid %s"></span>'
                % (label, _clock(a), _clock(b), what, a / 14.4,
                   (b - a) / 14.4, fill, op, c["surface"]))
        return ('<div style="font-size:.64rem;color:%s;margin:6px 0 2px">%s'
                '</div><div style="position:relative;height:%dpx;'
                'border-radius:4px;overflow:hidden;background:%s;border:1px '
                'solid %s">%s</div>'
                % (c["muted"], label, height, c["off"], c["line"],
                   "".join(segs)))

    ticks = ('<div style="position:relative;height:13px;font-size:.6rem;'
             'color:%s;margin-top:2px">%s</div>'
             % (c["faint"], "".join(
                 '<span style="position:absolute;left:%.3f%%;transform:'
                 'translateX(%s)">%s</span>'
                 % (h / 24.0 * 100, "0" if h == 0 else "-100%" if h == 24
                    else "-50%", _clock(h * 60))
                 for h in (0, 6, 12, 18, 24))))
    cards = []
    for it in items:
        units, bands = it["units"], it["bands"]
        saving = it.get("saving_rs") or 0
        save = ('Saves about <b style="color:%s">Rs %s a day</b> against %s'
                ' from %s to %s' % (
                    c["text"], format(int(round(saving)), ","),
                    "all %d" % units if units > 1 else "running it",
                    _clock(work[0] * 60), _clock(work[1] * 60))
                if saving >= 1 else "No saving against %s from %s to %s"
                % ("all %d" % units if units > 1 else "running it",
                   _clock(work[0] * 60), _clock(work[1] * 60)))
        phases = "".join(
            '<div class="acc-ph"><span>%s</span><span class="n">%s<small>'
            '%s&ndash;%s</small></span><span class="v" style="color:%s">%s'
            '</span></div>'
            % (icon, name, _clock(a * 60), _clock(b * 60),
               c["muted"] if text in ("off", "not watched yet") else c["text"],
               text.replace(" AC", " <b>AC</b>") if text not in
               ("off", "not watched yet") else text.capitalize())
            for icon, name, a, b, text in phase_lines(bands, units))
        detail = bar(bands, units, c["on"], "Recommended")
        ran_bands = it.get("ran")
        observed = ""
        if ran_bands:
            seen = it.get("read") or units
            detail += bar(ran_bands, seen, c.get("ran", "#e8a21a"),
                          "What ran &mdash; the %d unit%s a camera reads"
                          % (seen, "" if seen == 1 else "s"))
            cap = it.get("cap")
            observed = ('<div style="font-size:.72rem;color:%s;margin-top:4px">'
                        'Ran about <b>%.0f unit-hours a day</b> where read'
                        ' &middot; recommended %.0f%s</div>'
                        % (c["muted"], unit_hours(ran_bands),
                           unit_hours(bands),
                           (" &middot; never more than %d at once: the most"
                            " ever seen running, and it was enough" % cap)
                           if cap and cap < units else ""))
        days_txt = ("from %d working day%s" % (it["days"], "" if it["days"] == 1
                                              else "s")) if it.get("days") \
            else ""
        cards.append(
            '<div class="acc"><div class="acc-h"><b style="color:%s">%s</b>'
            '<span style="color:%s">%d AC%s%s</span></div>'
            '<div class="acc-save" style="color:%s">%s</div>%s'
            '<details><summary style="color:%s">Details: the whole day, and'
            ' what really ran</summary>%s%s<div style="font-size:.72rem;'
            'color:%s;margin-top:4px;line-height:1.45">%s</div>%s</details>'
            '</div>'
            % (c["text"], it["room"], c["muted"], units,
               " &middot; " + it["campus"] if it.get("campus") else "",
               " &middot; " + days_txt if days_txt else "",
               c["muted"], save, phases, c["muted"], detail, ticks,
               c["muted"], say(bands, units), observed))
    grid = ('<div class="acg" style="--acl:%s;--acs:%s">%s</div>'
            % (c["line"], c["surface"], "".join(cards)))
    if not heading:
        return CARD_CSS + grid
    return (
        CARD_CSS +
        '<div style="margin:26px 0 2px;font-size:1.1rem;font-weight:720;'
        'color:%s">Recommended AC timings</div>'
        '<div style="font-size:.74rem;color:%s;line-height:1.5">When people'
        ' are usually in each room, from up to the last %d working day%s, and'
        ' how many of its units that needs. The office runs %s to %s; after'
        ' that one unit only where people are usually still there. Open a'
        ' card for its whole day. Rs %.0f a unit.</div>%s'
        % (c["text"], c["muted"], days, "" if days == 1 else "s",
           _clock(work[0] * 60), _clock(work[1] * 60), rate, grid))

def say(bands, units):
    """The stretches in words: "off until 9:30am · 1 AC 9:30am-12pm · ..."."""
    if not bands:
        return ""
    if all(not n for _, _, n in bands):
        return "nobody is usually here: keep it off"
    bits = []
    for i, (a, b, n) in enumerate(bands):
        span = ("until %s" % _clock(b) if a == 0 else
                "after %s" % _clock(a) if b == 1440 else
                "%s–%s" % (_clock(a), _clock(b)))
        if n is None:
            what = "not watched yet"
        elif n == 0:
            what = "off"
        elif n >= units:
            what = "all %d" % units if units > 1 else "on"
        else:
            what = "%d of %d" % (n, units)
        bits.append("%s %s" % (what, span))
    return " · ".join(bits)
