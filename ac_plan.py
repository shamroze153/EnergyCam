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


def plan(minutes_by_day, units, work=(10.0, 20.0)):
    """[(from minute, to minute, units on)] over the whole day -- units None
    for a half hour no day watched -- or None where no day was watched."""
    if units < 1:
        return None
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


def unit_hours(bands):
    return sum((b - a) / 60.0 * n for a, b, n in bands or [] if n)


def _clock(minute):
    h, m = divmod(int(minute) % 1440, 60)
    half = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return ("%d%s" % (h12, half)) if not m else ("%d:%02d%s" % (h12, m, half))


def page(items, colours, days, work=(10.0, 20.0), rate=67.0, heading=True):
    """The section under Who comes when.

    items: [{"room", "units", "bands", "saving_rs"}], best saving first.
    colours: {"text", "muted", "faint", "line", "off", "on", "surface"}.
    heading=False gives the rows alone, for the rest of the rooms.
    """
    if not items:
        return ""
    c = colours
    rows = []
    for it in items:
        units, bands = it["units"], it["bands"]
        segs = []
        for a, b, n in bands:
            share = n / float(units) if units and n else 0
            if n is None:
                fill, op, what = c["surface"], 1.0, "not watched yet"
            elif not n:
                fill, op, what = c["off"], 1.0, "off"
            else:
                fill, op = c["on"], 0.35 + 0.65 * share
                what = "%d of %d" % (n, units)
            segs.append(
                '<span title="%s–%s: %s" style="position:absolute;left:%.3f%%;'
                'width:%.3f%%;top:0;bottom:0;background:%s;opacity:%.2f;'
                'border-right:1px solid %s"></span>'
                % (_clock(a), _clock(b), what, a / 14.4, (b - a) / 14.4,
                   fill, op, c["surface"]))
        ticks = "".join(
            '<span style="position:absolute;left:%.3f%%;transform:translateX('
            '%s);">%s</span>' % (h / 24.0 * 100, "0" if h == 0 else "-100%"
                                  if h == 24 else "-50%", _clock(h * 60))
            for h in (0, 6, 12, 18, 24))
        saving = it.get("saving_rs")
        note = ('<span style="color:%s">· about <b>Rs %s a day</b> less than'
                ' %s from %s to %s</span>' % (
                    c["muted"], format(int(round(saving)), ","),
                    "all %d" % units if units > 1 else "running it",
                    _clock(work[0] * 60), _clock(work[1] * 60))
                if saving and saving >= 1 else "")
        rows.append(
            '<div style="padding:10px 0;border-bottom:1px solid %s">'
            '<div style="display:flex;flex-wrap:wrap;gap:4px 10px;'
            'align-items:baseline;margin-bottom:6px"><b style="color:%s">%s'
            '</b><span style="color:%s;font-size:.72rem">%d AC%s</span></div>'
            '<div style="position:relative;height:14px;border-radius:4px;'
            'overflow:hidden;background:%s;border:1px solid %s">%s</div>'
            '<div style="position:relative;height:14px;font-size:.62rem;'
            'color:%s;margin-top:2px">%s</div>'
            '<div style="font-size:.8rem;color:%s;margin-top:2px;line-height:'
            '1.45">%s %s</div></div>'
            % (c["line"], c["text"], it["room"], c["muted"], units,
               (" · from %d working day%s" % (it["days"], "" if it["days"] == 1
                                              else "s")) if it.get("days")
               else "",
               c["off"], c["line"], "".join(segs), c["faint"], ticks,
               c["text"], say(bands, units), note))
    if not heading:
        return "".join(rows)
    return (
        '<div style="margin:26px 0 4px;font-size:1.1rem;font-weight:720;'
        'color:%s">Recommended AC timings</div>'
        '<div style="font-size:.74rem;color:%s;margin-bottom:6px;line-height:'
        '1.5">From up to the last %d working day%s: when people are usually in each'
        ' room, and how many of its units that needs -- half the people of'
        ' its busiest half hour, half the units. The office runs %s to %s;'
        ' after that one unit only where people are usually still there,'
        ' not for the office boy\'s round. The darker the blue, the more'
        ' units. Savings at Rs %.0f a unit.%s</div>%s'
        % (c["text"], c["muted"], days, "" if days == 1 else "s",
           _clock(work[0] * 60), _clock(work[1] * 60), rate,
           " Each room says how many it is from; a few days only is a first"
           " guess, firmer with every working day.", "".join(rows)))


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
