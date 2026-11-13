"""Room by room: how long the AC ran, what it used, and what it cost.

Asked for on 12 Nov: "for every room, how much electricity its ACs use in a
day -- the cafe at 141 has its ACs on camera, so you know how much it used
today and what it cost; and how long rooms sat empty while the AC could
have been off -- so we can show tomorrow is better than today".

Three kinds of room, and the page says which each figure is:

  read     the camera reads the unit(s): minutes the room's AC was on, with
           how many units where the count is recorded, times their kW.
           Measured.
  assumed  nobody can see the unit: it is taken to run from when somebody
           first stayed (the cleaner's round does not count) to when the
           last person left -- people switch the AC on when they settle and
           off when they go. Every unit in the room, at its rated kW.
  always   cooled around the clock on purpose (server rooms): 24 hours.

"Could have been off" is the AC's minutes inside that time with nobody in
the room. Prices are the marginal rate, peak and off-peak by the clock.

Only watched time is counted: a stretch the loop was not running is left
out, not assumed. No Streamlit and no database: frames in, figures out.
"""
from bisect import bisect_right

import pandas as pd

import analysis_view as av
import day_story as ds
import empty_view as evw
import energy_view as ev
import overview as ov
from overview import esc

READ, PART, ASSUMED, ALWAYS = "read", "part", "assumed", "always"

# A room nobody can read is taken to have its AC on from when somebody settles
# to when the last of them leaves. Two stays this far apart or more are two
# switch-ons: lunch out, gone for the day and back for the evening. That is
# the cautious reading -- a figure that goes in front of the CEO is never the
# inflated one -- and the empty minutes inside a stretch (a meeting
# elsewhere, a long break) are the "could have been off".
SESSION_GAP = pd.Timedelta(hours=2)


def _intervals(events, room, start, end):
    """The room's rows as (from, to, status, people, ac_state, units_on)."""
    rows = events[events["room"] == room].sort_values("timestamp")
    stamps = list(rows["timestamp"])
    out = []
    for i, (_, r) in enumerate(rows.iterrows()):
        a = max(stamps[i], start)
        b = min(stamps[i + 1] if i + 1 < len(stamps) else end, end)
        if b <= a:
            continue
        units = r.get("ac_units_on")
        units = (None if units is None or pd.isna(units) else int(units))
        out.append((a, b, r.get("status"), r.get("people"),
                    r.get("ac_state"), units))
    return out


def _text(value):
    """A label from the rooms table: NaN and None are no label at all."""
    return value.strip() if isinstance(value, str) else ""


def _alive_parts(a, b, alive):
    return [(max(a, x), min(b, y)) for x, y in alive if min(b, y) > max(a, x)]


def _price(a, b, kw, rates, window):
    """Rupees for kW over [a, b), peak minutes at the peak rate."""
    off, peak = av.split_peak(a, b, window)
    return kw * (off / 60.0 * rates[0] + peak / 60.0 * rates[1])


def sessions(day, start):
    """(from, to) a room's AC is taken to run, from its day's spells.

    Stays only: the office boy's few minutes and the cleaners' early round
    switch nothing on. Stays less than SESSION_GAP apart are one stretch.
    """
    found = ds.visits(day)
    s = ds.story(day, start)
    if s["early"]:
        found = [v for v in found if v[0] != s["early"]["from"]]
    _, stays = ds.kinds(found)
    out = []
    for a, b, _, _ in stays:
        if out and a - out[-1][1] < SESSION_GAP:
            out[-1] = (out[-1][0], max(b, out[-1][1]))
        else:
            out.append((a, b))
    return out


class _Sum:
    """Minutes, kWh and rupees, all of it and the part with nobody in."""

    def __init__(self):
        self.kwh = self.rs = self.waste_kwh = self.waste_rs = 0.0
        self.measured_kwh = 0.0

    def add(self, x, y, kw, status, rates, window, measured=False):
        m = (y - x).total_seconds() / 60.0
        money = _price(x, y, kw, rates, window)
        self.kwh += m / 60.0 * kw
        self.rs += money
        if measured:
            self.measured_kwh += m / 60.0 * kw
        if status == "empty":
            self.waste_kwh += m / 60.0 * kw
            self.waste_rs += money
        return m


def room_day(events, row, start, end, alive, read, rates, window, beats,
             duty=1.0):
    """One room over [start, end). None for a room with no unit.

    `read` is how many of its units a camera reads (0 for none). Those are
    measured, minute by minute; the rest of the room's units are assumed to
    run while people are in, as a room nobody reads is. `duty` is the share
    of its rated kW a unit that is on draws on average (the compressor
    cycles): rooms.yaml's ac_duty.
    """
    if not row.get("has_unit"):
        return None
    count = int(row.get("ac_count") or 1)
    rated = float(row.get("unit_kw") or 1.2)
    each = rated * float(duty)
    total_kw = count * each
    read = max(0, min(int(read or 0), count))
    acc = _Sum()
    on_min = empty_on_min = 0.0
    # In a part-read room, the minutes the units nobody reads are taken to
    # run, kept apart: their rupees are in the totals, and a page that showed
    # those rupees beside the read units' minutes alone would say "nobody in
    # under a minute, Rs 134 wasted" (the cafe, 13 Nov).
    part_on_min = part_empty_min = 0.0
    if not row.get("alerts", True):
        basis = ALWAYS
        for x, y in _alive_parts(start, end, alive):
            on_min += acc.add(x, y, total_kw, "occupied", rates, window)
    else:
        basis = READ if read >= count else (PART if read else ASSUMED)
        spans = _intervals(events, row["room"], start, end)
        if read:
            # Measured: the minutes a camera saw the unit running, at the
            # number of units it saw running (one where that was not yet
            # written down, the cautious count).
            for a, b, status, _, ac, units in spans:
                if ac != "on":
                    continue
                kw = min(units if units else 1, read) * each
                for x, y in _alive_parts(a, b, alive):
                    m = acc.add(x, y, kw, status, rates, window, True)
                    on_min += m
                    if status == "empty":
                        empty_on_min += m
        unseen = count - read
        if unseen:
            mine = events[events["room"] == row["room"]]
            day = ds.spells(mine, start, end, beats)
            kw = unseen * each
            for s_from, s_to in sessions(day, start):
                for a, b, status, _, _, _ in spans:
                    a, b = max(a, s_from), min(b, s_to)
                    if b <= a:
                        continue
                    for x, y in _alive_parts(a, b, alive):
                        m = acc.add(x, y, kw, status, rates, window)
                        if not read:
                            on_min += m
                            if status == "empty":
                                empty_on_min += m
                        else:
                            part_on_min += m
                            if status == "empty":
                                part_empty_min += m
    tons = row.get("tons_total")
    return {"room": row["room"], "floor": _text(row.get("floor")),
            "building": building(row), "campus": _text(row.get("campus")),
            "dept": _text(row.get("dept")), "units": count, "read": read,
            "kw": count * rated,
            "tons": None if tons is None or pd.isna(tons) else float(tons),
            "sizes": _text(row.get("ac_sizes")),
            "basis": basis,
            "on_h": on_min / 60.0, "empty_on_h": empty_on_min / 60.0,
            "assumed_on_h": part_on_min / 60.0,
            "assumed_empty_on_h": part_empty_min / 60.0,
            "kwh": acc.kwh, "rs": acc.rs, "waste_kwh": acc.waste_kwh,
            "waste_rs": acc.waste_rs, "measured_kwh": acc.measured_kwh}


# One room's day slot by slot, for the line under its people (Shamroze, 13
# Nov: "I can't tell whether the AC was running or off while the room sat
# empty -- how do I judge how long the power was wasted?").
ON, WASTE, OFF, UNREAD = "on", "waste", "off", "unread"
ASSUMED_ON, ASSUMED_WASTE, ASSUMED_OFF = ("assumed", "assumed_waste",
                                          "assumed_off")


def ac_slots(events, row, read, since, now, until, slots, alive, beats=None):
    """The room's AC in each of `slots` equal slots of [since, until).

    Where a camera reads a unit: ON (running, people in), WASTE (running,
    nobody in), OFF, or UNREAD (no reading). Where none does: ASSUMED_ON /
    ASSUMED_WASTE inside the stretch it is taken to run (as room_day takes
    it), ASSUMED_OFF outside it. A room cooled round the clock is ON. None
    where the loop was not watching, "later" for a slot still to come, and
    [] for a room with no unit at all.
    """
    if not row.get("has_unit"):
        return []
    mine = events[events["room"] == row["room"]].sort_values("timestamp")
    stamps = mine["timestamp"].tolist()
    status = mine["status"].tolist()
    ac = (mine["ac_state"].tolist() if "ac_state" in mine
          else [None] * len(stamps))
    # The units seen running. In a part-read room the loop writes the room's
    # state as unknown when every unit it reads is off (the rest might be
    # running) but still writes 0 here: those slots are the read units off,
    # not "not read" -- the cafe drew a whole morning of five towers read off
    # as not read (Shamroze, 13 Nov).
    seen_on = (mine["ac_units_on"].tolist() if "ac_units_on" in mine
               else [None] * len(stamps))
    always = not row.get("alerts", True)
    runs = []
    if not always and not read:
        runs = sessions(ds.spells(mine, since, min(now, until), beats), since)
    step = (until - since) / slots
    out = []
    for k in range(slots):
        t = since + step * k
        if t >= now:
            out.append("later")
            continue
        i = bisect_right(stamps, t) - 1
        if i < 0 or not any(a <= t < b for a, b in alive):
            out.append(None)
            continue
        if always:
            out.append(ON)
            continue
        empty = status[i] == "empty"
        if read:
            state = ac[i] if isinstance(ac[i], str) else None
            n = seen_on[i]
            if state is None and n is not None and n == n and int(n) == 0:
                state = "off"
            out.append((WASTE if empty else ON) if state == "on"
                       else OFF if state == "off" else UNREAD)
        elif status[i] not in ("occupied", "empty"):
            out.append(None)
        elif any(a <= t < b for a, b in runs):
            out.append(ASSUMED_WASTE if empty else ASSUMED_ON)
        else:
            out.append(ASSUMED_OFF)
    return out


def building(row):
    """140-H, or which of 141's three buildings: the CEO's first question."""
    name = str(row.get("room") or "")
    if _text(row.get("building")):
        return _text(row.get("building"))      # rooms.yaml says (13 Nov)
    if name.startswith("141-C"):
        return "141-C"
    if name.startswith("141-D"):
        return "141-D"
    if name.startswith("141") or _text(row.get("campus")).startswith("141"):
        return "141 main"
    return _text(row.get("campus")) or "140-H"


def _window_rows(rows, start, end):
    """A room's rows inside [start, end), and the one before that opens it."""
    before = rows[rows["timestamp"] < start].tail(1)
    inside = rows[(rows["timestamp"] >= start) & (rows["timestamp"] < end)]
    return pd.concat([before, inside])


def ledger(events, rooms, start, end, beats, read_rooms, rates, window,
           duty=1.0):
    """Every room with a unit over [start, end), costliest first.

    `read_rooms` is {room: units a camera reads}, as
    campus_view.calibrated_counts() gives it. `events` may be a month of
    every room: it is split once and trimmed to the window, not filtered a
    hundred times over.
    """
    alive = evw.watched(beats, start, end)
    watched_h = sum((b - a).total_seconds() for a, b in alive) / 3600.0
    split = {name: rows.sort_values("timestamp")
             for name, rows in events.groupby("room")}
    none = events.iloc[0:0]
    out = []
    for _, row in rooms.iterrows():
        if not row.get("has_unit"):
            continue
        mine = _window_rows(split.get(row["room"], none), start, end)
        r = room_day(mine, row, start, end, alive,
                     read_rooms.get(row["room"], 0), rates, window, beats,
                     duty)
        if r is not None:
            r["watched_h"] = watched_h
            out.append(r)
    out.sort(key=lambda r: (-r["rs"], r["room"]))
    return out


def average(days):
    """Several days' ledgers as one average day, room by room."""
    days = [d for d in days if d is not None]
    if not days:
        return []
    n = float(len(days))
    keep = {}
    for rows in days:
        for r in rows:
            k = keep.setdefault(r["room"], dict(r, on_h=0.0, empty_on_h=0.0,
                                                kwh=0.0, rs=0.0,
                                                waste_kwh=0.0, waste_rs=0.0,
                                                measured_kwh=0.0))
            for f in ("on_h", "empty_on_h", "kwh", "rs", "waste_kwh",
                      "waste_rs", "measured_kwh"):
                k[f] += r.get(f, 0.0) / n
    out = list(keep.values())
    out.sort(key=lambda r: (-r["rs"], r["room"]))
    return out


def totals(rows):
    keys = ("kwh", "rs", "waste_kwh", "waste_rs", "measured_kwh",
            "empty_on_h")
    out = {k: sum(r.get(k, 0.0) for r in rows) for k in keys}
    # The same for every row of one ledger: how much of it was watched.
    out["watched_h"] = max([r.get("watched_h", 0.0) for r in rows] or [0.0])
    return out


# A day counts as a whole day for comparing only when the loop watched
# nearly all of it: on 12 Nov the first version said Wednesday was "764%
# worse" than three days the loop had watched a few hours of.
WHOLE_DAY_H = 20


def meter_window(readings, codes, solar, tz="Asia/Karachi"):
    """The latest stretch between two readings of every meter, and what the
    building used over it: the grid on each meter plus the panels.

    The check on the ledger: whatever the ACs are estimated at has to fit
    inside this, with the lights and the computers. None until every meter
    has been read on two days.
    """
    codes = list(codes or [])
    if readings is None or not len(readings) or not codes:
        return None
    r = readings[readings["meter"].isin(codes)].dropna(subset=["reading"])
    if not len(r):
        return None
    r = r.assign(taken=pd.to_datetime(r["taken"], utc=True))
    r = r.assign(day=r["taken"].dt.tz_convert(tz).dt.date)
    # The last save of a day is the reading: Save is pressed several times.
    last = r.sort_values("taken").groupby(["meter", "day"]).tail(1)
    days = sorted(d for d, g in last.groupby("day")
                  if set(codes) <= set(g["meter"]))
    if len(days) < 2:
        return None
    a = last[last["day"] == days[-2]].set_index("meter")
    b = last[last["day"] == days[-1]].set_index("meter")
    grid = sum(float(b.loc[c, "reading"]) - float(a.loc[c, "reading"])
               for c in codes)
    sun = None
    if solar is not None and len(solar):
        s = solar.assign(taken=pd.to_datetime(solar["taken"], utc=True))
        s = s[s["taken"].dt.tz_convert(tz).dt.date == days[-1]]
        if len(s):
            # The form asks for yesterday's whole figure: near enough the
            # same stretch as the two readings either side of it.
            sun = float(s.sort_values("taken")["kwh"].iloc[-1])
    return {"from": a["taken"].max(), "to": b["taken"].max(), "grid": grid,
            "sun": sun, "total": grid + (sun or 0.0)}


BUILDINGS = ["140-H", "141 main", "141-C", "141-D"]


def by_building(rows):
    """{building: totals} in a fixed order, buildings with no unit left out."""
    out = {}
    for b in BUILDINGS + sorted({r["building"] for r in rows} - set(BUILDINGS)):
        mine = [r for r in rows if r["building"] == b]
        if mine:
            out[b] = dict(totals(mine), rooms=len(mine))
    return out


# ===================================================================== drawing

CSS = """<style>
.er-cmp{display:inline-block;font-size:12px;font-weight:650;padding:2px 9px;
border-radius:99px;margin-top:8px;border:1px solid var(--line2)}
.er-cmp.good{color:var(--good);border-color:var(--good)}
.er-cmp.bad{color:var(--crit);border-color:var(--crit)}
.er-row{display:grid;grid-template-columns:minmax(150px,1.4fr) 92px 1fr 96px 96px;
gap:10px;align-items:center;padding:9px 2px;border-bottom:1px solid var(--line)}
.er-row.h{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
color:var(--t3);padding-top:4px}
.er-row .nm{display:block;min-width:0}
.er-row .nm b{display:block;font-size:13.5px;font-weight:650;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.er-row .nm span{font-size:11.5px;color:var(--t3)}
.er-badge{font-size:10.5px;font-weight:700;letter-spacing:.04em;border-radius:99px;
padding:2px 8px;white-space:nowrap;text-align:center}
.er-badge.read,.er-badge.part{background:rgba(42,157,99,.16);color:#2a9d63}
.er-badge.assumed{background:var(--pill-bg);color:var(--pill-fg)}
.er-badge.always{background:var(--s2);color:var(--t3)}
.er-bar{height:10px;border-radius:99px;background:var(--meter);overflow:hidden;
display:flex}
.er-bar i{display:block;height:100%%}
.er-row .n{text-align:right;font-weight:650;font-variant-numeric:tabular-nums;
font-size:13.5px}
.er-row .n span{display:block;font-size:11px;color:var(--t3);font-weight:400}
.er-bld{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
gap:10px;margin-top:10px}
.er-bld .ec-card{padding:12px 14px}
.er-bld .k{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
color:var(--t3);font-weight:650}
.er-bld .v{font-size:22px;font-weight:720;margin-top:2px;
font-variant-numeric:tabular-nums}
.er-bld .s{font-size:12px;color:var(--t3);margin-top:2px}
@media (max-width:760px){.er-row{grid-template-columns:1fr 84px 84px}
.er-row .bd,.er-row .br{display:none}}
</style>""".replace("\n", "")


def _rs(v):
    return "Rs %s" % format(int(round(v)), ",")


def _h(v):
    return ov.ago(int(round(v * 60))) if v >= 1 / 60.0 else "0m"


def _when(t):
    """"Tue 10, 5:46 evening": a reading's day and time, Karachi clock."""
    local = pd.Timestamp(t).tz_convert("Asia/Karachi")
    return "%s, %s" % (local.strftime("%a %d").replace(" 0", " "),
                       ov.clock(t))


def badge(r):
    if r["basis"] == PART:
        return "read %d of %d" % (r["read"], r["units"])
    return {READ: "read", ASSUMED: "assumed", ALWAYS: "24 h"}[r["basis"]]


def trend(theme, days):
    """Is it getting better: the AC's rupees a day, the part with nobody in
    on top, for the last week.

    `days` is [(date, totals(ledger), so_far)], oldest first; so_far marks
    today, which is not a whole day and is labelled so. Asked for on 12 Nov
    ("so we can show tomorrow is better than today").
    """
    days = [d for d in days if d[1].get("kwh")]
    if len(days) < 2:
        return ""
    waste_colour = "#e8a21a" if theme == "dark" else "#d18a00"
    on_colour = "#2a9d63" if theme == "dark" else "#1f8a55"
    labels, stacks, tips, marks = [], [], [], []

    def full(d):
        # Not today, and watched nearly all day. A ledger with no
        # watched_h (an older caller) is taken as whole.
        return not d[2] and d[1].get("watched_h", 24) >= WHOLE_DAY_H

    whole_i = [i for i, d in enumerate(days) if full(d)]
    worst = (max(whole_i, key=lambda i: days[i][1]["waste_rs"])
             if len(whole_i) > 1 else None)
    for i, (day, t, so_far) in enumerate(days):
        labels.append(pd.Timestamp(day).strftime("%a %d").replace(" 0", " "))
        stacks.append([max(0.0, t["rs"] - t["waste_rs"]), t["waste_rs"]])
        part = (not so_far and not full(days[i]))
        tips.append("%s%s · AC %s (%s kWh) · with nobody in %s%s"
                    % (pd.Timestamp(day).strftime("%a %d %b"),
                       " so far" if so_far else "", _rs(t["rs"]),
                       format(int(round(t["kwh"])), ","),
                       _rs(t["waste_rs"]),
                       (" · cameras watched %.0f of 24 hours"
                        % t.get("watched_h", 0)) if part else ""))
        marks.append("so far" if so_far else
                     ("%.0fh watched" % t.get("watched_h", 0)) if part else
                     ("most wasted" if i == worst else None))
    whole = [days[i] for i in whole_i]
    said = ("Comparing starts once two whole days have been watched; "
            "a short column is a day the cameras saw only part of.")
    if len(whole) >= 2:
        last = whole[-1][1]["waste_rs"]
        before = [d[1]["waste_rs"] for d in whole[:-1]]
        usual = sum(before) / len(before)
        if usual:
            change = 100.0 * (last / usual - 1)
            said = ('<b>%s</b>: %s ran with nobody in, <b style="color:%s">'
                    '%.0f%% %s</b> than the %d day%s before it on average.'
                    % (esc(pd.Timestamp(whole[-1][0]).strftime("%A")),
                       _rs(last), "var(--good)" if change < 0 else
                       "var(--crit)", abs(change),
                       "less" if change < 0 else "more", len(before),
                       "" if len(before) == 1 else "s"))
    return "".join([
        ev.css(theme), '<div class="ec">',
        '<div class="ec-h" style="margin-top:22px"><span class="t">Is it '
        'getting better?</span><span class="c">the ACs\' rupees each day, '
        'the part with nobody in on top · hover a day</span></div>',
        '<div class="ec-card" style="padding:14px 16px">',
        ev.legend([(on_colour, "with people in"),
                   (waste_colour, "with nobody in")]),
        ev.columns(labels, stacks, [on_colour, waste_colour], tips,
                   height=200, marks=marks),
        '<div class="en-note" style="margin-top:8px">%s Each day is '
        'midnight to midnight, the same estimate as the rooms above; a day '
        'the cameras watched only part of counts only that part.</div>'
        % said, '</div></div>'])


SHOWN = 25          # rows listed before the rest are folded into one line


def empty_page(theme, rows, base, span_text, links=True, rates=(67, 81),
               duty=1.0):
    """Who comes when's "empty, with the AC on": every building, then rooms.

    12 Nov, Shamroze: most units cannot be read until cameras are re-aimed,
    so meanwhile show how long each room sat empty while its AC ran -- or,
    where nobody can see the unit, while it would have, people having been
    in either side -- across all of 140-H and 141's three buildings.
    """
    waste_colour = "#e8a21a" if theme == "dark" else "#d18a00"
    on_colour = "#2a9d63" if theme == "dark" else "#1f8a55"
    t = totals(rows)
    h = [ev.css(theme), CSS % {}, '<div class="ec">',
         '<div class="ec-h" style="margin-top:6px"><span class="t">Empty, with '
         'the AC on</span><span class="c">%s · when a switch-off would have '
         'saved money</span></div>' % esc(span_text)]
    h.append('<div class="er-bld">')
    for b, s in by_building(rows).items():
        # Hours added across rooms: "2d" for 52 of them read as two days.
        hours = (("%d h" % round(s["empty_on_h"])) if s["empty_on_h"] >= 10
                 else _h(s["empty_on_h"]))
        h.append('<div class="ec-card"><div class="k">%s</div><div class="v"'
                 ' style="color:%s">%s</div><div class="s">%s empty with the '
                 'AC on, added across %d rooms with a unit</div></div>'
                 % (esc(b), "var(--crit)" if s["waste_rs"] >= 1 else
                    "var(--t1)", _rs(s["waste_rs"]), hours, s["rooms"]))
    h.append('</div>')
    wasted = [r for r in rows if r["empty_on_h"] >= 5 / 60.0]
    wasted.sort(key=lambda r: (-r["waste_rs"], -r["empty_on_h"], r["room"]))
    if not wasted:
        h.append('<div class="en-note">No room with a unit sat empty with its '
                 'AC on. %s</div></div>' % ("" if t["kwh"] else
                                             "(Nothing was watched yet.)"))
        return "".join(h)
    h.append('<div class="ec-card" style="margin-top:12px;padding:8px 16px">'
             '<div class="er-row h"><span>room</span><span class="bd">how'
             '</span><span class="br">AC on &middot; <b style="color:%s">'
             'nobody in</b></span><span class="n">empty</span><span class="n">'
             'could save</span></div>' % waste_colour)
    for r in wasted[:SHOWN]:
        busy = max(0.0, r["on_h"] - r["empty_on_h"])
        top = max(r["on_h"], 1e-9)
        where = " · ".join(x for x in (r["building"], r["floor"]) if x)
        name = '<b>%s</b><span>%s</span>' % (esc(ov.short(r["room"])),
                                            esc(where))
        h.append(
            '<div class="er-row">%s<span class="er-badge %s bd">%s</span>'
            '<div class="br"><div class="er-bar"><i style="width:%.1f%%;'
            'background:%s"></i><i style="width:%.1f%%;background:%s"></i>'
            '</div><span style="font-size:11px;color:var(--t3)">%s of %s on'
            '</span></div><div class="n">%s<span>%d AC</span></div>'
            '<div class="n" style="color:var(--crit)">%s<span>%.0f kWh</span>'
            '</div></div>'
            % (('<a class="nm" target="_self" href="%s#roomdetail">%s</a>'
                % (esc(ov.link(base, room=r["room"],
                               campus=r.get("campus") or base.get("campus"))),
                   name)) if links else
               '<span class="nm">%s</span>' % name,
               r["basis"], badge(r), 100.0 * busy / top, on_colour,
               100.0 * r["empty_on_h"] / top, waste_colour,
               _h(r["empty_on_h"]), _h(r["on_h"]), _h(r["empty_on_h"]),
               r["units"], _rs(r["waste_rs"]), r["waste_kwh"]))
    rest = wasted[SHOWN:]
    if rest:
        h.append('<div class="er-row"><span class="nm"><span>and %d more '
                 'rooms</span></span><span class="bd"></span><span class="br">'
                 '</span><div class="n">%s</div><div class="n">%s</div></div>'
                 % (len(rest), _h(sum(r["empty_on_h"] for r in rest)),
                    _rs(sum(r["waste_rs"] for r in rest))))
    h.append('</div><div class="en-note">%s in all: %s of AC time with nobody '
             'in. <b>read</b> rooms are measured by the camera; <b>assumed</b> '
             'rooms count the empty minutes between people settling in and '
             'the last leaving, as if the AC had stayed on (a gap of two hours '
             'or more counts as switched off). A unit that is on draws %.0f%% '
             'of its rated kW on average (the compressor cycles). Prices by '
             'the clock: Rs %g a unit in the peak, Rs %g outside it.</div>'
             '</div>'
             % (_rs(t["waste_rs"]), _h(t["empty_on_h"]), 100.0 * duty,
                rates[1], rates[0]))
    return "".join(h)


def page(theme, title, rows, base, compare=None, compare_label="",
         unwatched_units=0, check=None, duty=1.0):
    """The ledger: tiles, then a row a room.

    `check` is meter_window()'s stretch with "ac_kwh" added: the ledger
    over the same hours, shown against what the meters say the whole
    building used.
    """
    t = totals(rows)
    waste_colour = "#e8a21a" if theme == "dark" else "#d18a00"
    on_colour = "#2a9d63" if theme == "dark" else "#1f8a55"
    h = [ev.css(theme), CSS % {}, '<div class="ec">',
         '<div class="ec-h" style="margin-top:22px"><span class="t">%s</span>'
         '<span class="c">what each room\'s AC ran, used and cost</span></div>'
         % esc(title), '<div class="en-tiles">']
    cmp_html = ""
    if compare is not None and compare.get("rs"):
        change = 100.0 * (t["rs"] / compare["rs"] - 1)
        cmp_html = ('<span class="er-cmp %s">%s%.0f%% on %s</span>'
                    % ("good" if change < 0 else "bad",
                       "+" if change >= 0 else "−", abs(change),
                       esc(compare_label)))
    h.append(ev.tile("AC electricity", "%s kWh" % format(int(round(t["kwh"])),
                                                           ","),
                     "%s worth%s" % (_rs(t["rs"]), cmp_html)))
    h.append(ev.tile("Ran with nobody in", _rs(t["waste_rs"]),
                     "%s kWh that could have been saved" % format(
                         int(round(t["waste_kwh"])), ","), "crit"))
    read_share = (100.0 * t["measured_kwh"] / t["kwh"]) if t["kwh"] else 0
    h.append(ev.tile("Measured by camera", "%.0f%%" % read_share,
                     "of these kWh; the rest is assumed from when people "
                     "were in"))
    if check and check.get("total"):
        share = 100.0 * check["ac_kwh"] / check["total"]
        h.append(ev.tile(
            "Against the meters", "%.0f%%" % share,
            "of the %s kWh the whole building used (%s), %s to %s, was these "
            "ACs by this estimate" % (
                format(int(round(check["total"])), ","),
                "grid %s + solar %s" % (format(int(round(check["grid"])), ","),
                                        format(int(round(check["sun"])), ","))
                if check.get("sun") else "grid",
                esc(_when(check["from"])), esc(_when(check["to"]))),
            "crit" if share > 100 else ""))
    h.append("</div>")
    # 141 is three buildings (main, 141-C, 141-D): which one used what,
    # as Who comes when's "Empty, with the AC on" already splits it.
    blds = by_building(rows)
    if len(blds) > 1:
        h.append('<div class="er-bld">')
        for b, s in blds.items():
            h.append('<div class="ec-card"><div class="k">%s</div>'
                     '<div class="v">%s</div><div class="s">%s kWh · %d '
                     'rooms with a unit%s</div></div>'
                     % (esc(b), _rs(s["rs"]),
                        format(int(round(s["kwh"])), ","), s["rooms"],
                        (' · <b style="color:var(--crit)">%s with nobody '
                         'in</b>' % _rs(s["waste_rs"]))
                        if s["waste_rs"] >= 1 else ""))
        h.append("</div>")
    h.append('<div class="ec-card" style="margin-top:14px;padding:8px 16px">'
             '<div class="er-row h"><span>room</span><span class="bd">how'
             '</span><span class="br">AC on &middot; '
             '<b style="color:%s">nobody in</b></span><span class="n">kWh'
             '</span><span class="n">rupees</span></div>' % waste_colour)
    top = max([r["on_h"] for r in rows] or [1]) or 1
    for r in rows:
        busy = max(0.0, r["on_h"] - r["empty_on_h"])
        h.append(
            '<div class="er-row"><a class="nm" target="_self" '
            'href="%s#roomdetail"><b>%s</b><span>%s%s</span></a>'
            '<span class="er-badge %s bd">%s</span>'
            '<div class="br"><div class="er-bar"><i style="width:%.1f%%;'
            'background:%s"></i><i style="width:%.1f%%;background:%s"></i>'
            '</div><span style="font-size:11px;color:var(--t3)">%s on'
            '%s</span></div><div class="n">%s<span>%s</span></div>'
            '<div class="n">%s<span>%s</span></div></div>'
            % (esc(ov.link(base, room=r["room"])), esc(ov.short(r["room"])),
               esc(" · ".join(x for x in (
                   r.get("building") if str(r.get("building", ""))
                   .startswith("141") else "", r["floor"]) if x) + " · ")
               if r["floor"] or str(r.get("building", "")).startswith("141")
               else "",
               esc(ov.ac_size(r["units"], r.get("sizes"), r["tons"])),
               r["basis"], badge(r),
               100.0 * busy / top, on_colour,
               100.0 * r["empty_on_h"] / top, waste_colour,
               _h(r["on_h"]),
               (" · %s with nobody in" % _h(r["empty_on_h"]))
               if r["empty_on_h"] >= 1 / 60.0 else "",
               format(int(round(r["kwh"])), ","),
               ("%.1f kW" % r["kw"]),
               _rs(r["rs"]),
               ("%s wasted" % _rs(r["waste_rs"])) if r["waste_rs"] >= 1
               else ""))
    h.append('</div><div class="en-note"><b>read</b>: a camera reads the '
             'unit, so its minutes are measured. <b>read 1 of 3</b>: one unit '
             'measured, the others assumed. <b>assumed</b>: no camera sees '
             'the unit, so it is taken to run from when somebody settled in '
             'to when the last person left (a gap of two hours or more counts '
             'as switched off). <b>24 h</b>: cooled around the clock on '
             'purpose. A unit that is on is taken to draw %.0f%% of its rated '
             'kW on average, since the compressor cycles (rooms.yaml '
             'ac_duty, checked against the meters). Only time the cameras '
             'were watching is counted.%s</div></div>'
             % (100.0 * duty,
                (" %d units in rooms no camera watches are not in these "
                 "figures." % unwatched_units) if unwatched_units else ""))
    return "".join(h)
