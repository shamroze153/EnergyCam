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
LOCAL_TZ = "Asia/Karachi"

# A room nobody can read is taken to have its AC on from when somebody settles
# to when the last of them leaves. Two stays this far apart or more are two
# switch-ons: lunch out, gone for the day and back for the evening. That is
# the cautious reading -- a figure that goes in front of the CEO is never the
# inflated one -- and the empty minutes inside a stretch (a meeting
# elsewhere, a long break) are the "could have been off".
SESSION_GAP = pd.Timedelta(hours=2)
# Two stretches of too many units this close are told as one.
OVER_JOIN = pd.Timedelta(minutes=15)


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
        # Rupees by the Karachi clock's hour, [all, with nobody in]: which
        # hours the money went in (Shamroze, 16 Nov: "from which hour to
        # which hour, and a chart to keep tracking it").
        self.hours = [[0.0, 0.0] for _ in range(24)]
        # The peak tariff's hours on their own (Shamroze, 18 Nov: "every
        # room's cost in the peak hours, in a tab of its own").
        self.peak_kwh = self.peak_rs = self.peak_waste_rs = 0.0

    def add(self, x, y, kw, status, rates, window, measured=False):
        # On Karachi-clock seconds, not Timestamps: this runs thousands of
        # times a day of rooms (18 Nov: the same figures, twice as fast).
        sx, sy = av.local_seconds(x), av.local_seconds(y)
        m = (sy - sx) / 60.0
        off, peak = av.split_seconds(sx, sy, window)
        money = kw * (off / 60.0 * rates[0] + peak / 60.0 * rates[1])
        self.kwh += m / 60.0 * kw
        self.rs += money
        if measured:
            self.measured_kwh += m / 60.0 * kw
        if status == "empty":
            self.waste_kwh += m / 60.0 * kw
            self.waste_rs += money
        if peak:
            self.peak_kwh += peak / 60.0 * kw
            self.peak_rs += peak / 60.0 * kw * rates[1]
            if status == "empty":
                self.peak_waste_rs += peak / 60.0 * kw * rates[1]
        a = sx
        while a < sy:
            nxt = min(sy, (a // 3600.0 + 1) * 3600.0)
            o, p = av.split_seconds(a, nxt, window)
            piece = kw * (o / 60.0 * rates[0] + p / 60.0 * rates[1])
            hour = int((a % av.DAY_SECONDS) // 3600)
            self.hours[hour][0] += piece
            if status == "empty":
                self.hours[hour][1] += piece
            a = nxt
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
    # More units running than the people in need (people_per_unit in
    # rooms.yaml): the rupees of the extra units, and when.
    per = row.get("people_per_unit")
    per = float(per) if per is not None and per == per and per else None
    over_rs = over_kwh = over_min = 0.0
    over = []
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
            for a, b, status, people, ac, units in spans:
                if ac != "on":
                    continue
                people = (0 if people is None or pd.isna(people)
                          else int(people))
                seen = min(units if units else 1, read)
                kw = seen * each
                need = (units_needed(people, per, count)
                        if status == "occupied" and per else seen)
                extra = max(0, seen - need)
                for x, y in _alive_parts(a, b, alive):
                    m = acc.add(x, y, kw, status, rates, window, True)
                    on_min += m
                    if status == "empty":
                        empty_on_min += m
                    elif extra:
                        rs = _price(x, y, extra * each, rates, window)
                        over_rs += rs
                        over_kwh += m / 60.0 * extra * each
                        over_min += m
                        # One stretch while it lasts (a pass or two apart);
                        # its most people and units, the cautious need.
                        if over and x - over[-1]["to"] <= OVER_JOIN:
                            o = over[-1]
                            o["to"] = y
                            o["rs"] += rs
                            o["people"] = max(o["people"], people)
                            o["units"] = max(o["units"], seen)
                            o["need"] = max(o["need"], need)
                        else:
                            over.append({"from": x, "to": y, "units": seen,
                                         "need": need, "people": people,
                                         "rs": rs})
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
            "waste_rs": acc.waste_rs, "measured_kwh": acc.measured_kwh,
            "peak_kwh": acc.peak_kwh, "peak_rs": acc.peak_rs,
            "peak_waste_rs": acc.peak_waste_rs,
            "hourly": acc.hours,
            "over_rs": over_rs, "over_kwh": over_kwh, "over_h": over_min / 60.0,
            "over": over, "people_per_unit": per}


def units_needed(people, per, count):
    """Units a room needs for `people`: one for every `per` people, and one
    more for the sun and the door -- the cautious count, so a figure in front
    of the CEO is never the inflated one. Never more than the room has."""
    try:
        p = max(0, int(people or 0))
    except (TypeError, ValueError):
        p = 0
    # 28 Nov (the hosted One room page, opened from the Management Preview's
    # "Inspect evidence": "ValueError" -- a room's people-per-unit came as
    # NaN, and round(NaN) cannot be an int): no usable figure, no claim --
    # the room is taken to need every unit it has, so nothing is "over".
    try:
        per = float(per)
    except (TypeError, ValueError):
        per = float("nan")
    if per != per or per <= 0 or per == float("inf"):
        return count
    return min(count, -(-p // int(max(1, round(per)))) + 1)


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


def unit_slots(events, row, since, now, until, slots, alive):
    """Units seen running and people in, slot by slot (Shamroze, 18 Nov:
    "under the people line, a line of how many units were running").

    Each slot is (units, people): units the cameras saw running (None where
    no unit was read), people the loop counted (None where it could not
    tell). None where the loop was not watching, "later" for a slot still
    to come.
    """
    mine = events[events["room"] == row["room"]].sort_values("timestamp")
    stamps = mine["timestamp"].tolist()
    status = mine["status"].tolist()
    people = (mine["people"].tolist() if "people" in mine
              else [None] * len(stamps))
    seen_on = (mine["ac_units_on"].tolist() if "ac_units_on" in mine
               else [None] * len(stamps))
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
        n = seen_on[i]
        units = int(n) if n is not None and n == n else None
        p = people[i]
        if status[i] == "occupied":
            folk = int(p) if p is not None and p == p and p > 0 else 1
        elif status[i] == "empty":
            folk = 0
        else:
            folk = None
        out.append((units, folk))
    return out


def unit_spans(slots, since, until):
    """unit_slots joined where the units running stay the same: [{from, to,
    units, least, most}] -- least and most the people in it -- oldest first.
    Not-watched and still-to-come slots are left out and break a span."""
    if not slots:
        return []
    step = (until - since) / len(slots)
    spans, cur = [], None
    for k, s in enumerate(slots):
        if s is None or s == "later" or s[0] is None:
            cur = None
            continue
        units, folk = s
        if cur is not None and cur["units"] == units and cur["end"] == k:
            cur["end"] = k + 1
        else:
            cur = {"units": units, "start": k, "end": k + 1, "people": []}
            spans.append(cur)
        if folk is not None:
            cur["people"].append(folk)
    return [{"from": since + step * c["start"], "to": since + step * c["end"],
             "units": c["units"],
             "least": min(c["people"]) if c["people"] else None,
             "most": max(c["people"]) if c["people"] else None}
            for c in spans]


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
    # The peak hours watched, apart: 17 Nov was watched twenty hours, but
    # the laptop slept at 19:56 and saw an hour and a half of the peak.
    watched_peak_h = sum(av.split_peak(a, b, window)[1]
                         for a, b in alive) / 60.0
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
            r["watched_peak_h"] = watched_peak_h
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
                                                measured_kwh=0.0,
                                                peak_kwh=0.0, peak_rs=0.0,
                                                peak_waste_rs=0.0))
            for f in ("on_h", "empty_on_h", "kwh", "rs", "waste_kwh",
                      "waste_rs", "measured_kwh", "peak_kwh", "peak_rs",
                      "peak_waste_rs"):
                k[f] += r.get(f, 0.0) / n
    out = list(keep.values())
    out.sort(key=lambda r: (-r["rs"], r["room"]))
    return out


def totals(rows):
    keys = ("kwh", "rs", "waste_kwh", "waste_rs", "measured_kwh",
            "empty_on_h", "over_rs", "over_kwh", "peak_kwh", "peak_rs",
            "peak_waste_rs")
    out = {k: sum(r.get(k, 0.0) for r in rows) for k in keys}
    # The same for every row of one ledger: how much of it was watched.
    out["watched_h"] = max([r.get("watched_h", 0.0) for r in rows] or [0.0])
    # None for an older ledger that did not keep it: taken as whole.
    peak = [r["watched_peak_h"] for r in rows if "watched_peak_h" in r]
    out["watched_peak_h"] = max(peak) if peak else None
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


def _hour_name(h):
    """0 -> "12 am", 13 -> "1 pm"."""
    return "%d %s" % (h % 12 or 12, "am" if h < 12 else "pm")


def hourly(rows):
    """[[rupees, rupees with nobody in]] by hour, summed over `rows`."""
    out = [[0.0, 0.0] for _ in range(24)]
    for r in rows:
        for h, (rs, waste) in enumerate(r.get("hourly") or []):
            out[h][0] += rs
            out[h][1] += waste
    return out


def waste_stretches(hours, least=1.0, share=1 / 3.0):
    """The hours the AC ran mostly with nobody in -- at least `share` of that
    hour's rupees -- joined into stretches, the costliest first:
    [(from hour, to hour, rupees)]. A campus has a little waste in nearly
    every hour; a tip of "12 am to 12 pm" helps nobody (17 Nov)."""
    runs, cur = [], None
    for h, (spent, waste) in enumerate(hours):
        if waste >= least and waste >= share * spent:
            if cur and cur[1] == h:
                cur = (cur[0], h + 1, cur[2] + waste)
            else:
                if cur:
                    runs.append(cur)
                cur = (h, h + 1, waste)
    if cur:
        runs.append(cur)
    return sorted(runs, key=lambda r: -r[2])


def hours_page(theme, rows, name, week=None, so_far=True):
    """One room's (or the campus's) AC day hour by hour, the stretches it
    ran with nobody in as tips, and its last days one line each.

    `rows` is the day's ledger; `name` a room in it, or None for every room.
    `week` is [(date, ledger, so_far)] oldest first, as the trend draws.
    Asked for by Shamroze, 16 Nov: for each room and each campus, what its
    ACs cost that day, how much of it was waste, and from which hour to
    which hour -- with a chart to track it.
    """
    mine = [r for r in rows if name is None or r["room"] == name]
    if not mine:
        return ""
    hours = hourly(mine)
    total = sum(h[0] for h in hours)
    waste = sum(h[1] for h in hours)
    waste_colour = "#e8a21a" if theme == "dark" else "#d18a00"
    on_colour = "#2a9d63" if theme == "dark" else "#1f8a55"
    labels = [("%d%s" % (h % 12 or 12, "a" if h < 12 else "p"))
              if h % 3 == 0 else "" for h in range(24)]
    stacks = [[max(0.0, a - w), w] for a, w in hours]
    tips = ["%s-%s · AC %s · with nobody in %s" % (
        _hour_name(h), _hour_name((h + 1) % 24), _rs(a), _rs(w))
        for h, (a, w) in enumerate(hours)]
    who = esc(name) if name else "every room with a unit"
    basis = ""
    if name and len(mine) == 1:
        basis = " · %s" % badge(mine[0])
    tips_html = []
    for a, b, rs in waste_stretches(hours)[:3]:
        tips_html.append(
            '<li><b>%s to %s</b>: the AC ran with nobody in, <b style="color:'
            'var(--crit)">%s</b>. Switch it off then.</li>'
            % (_hour_name(a), _hour_name(b % 24), _rs(rs)))
    busiest = max(range(24), key=lambda h: hours[h][0])
    if hours[busiest][0] > 0:
        tips_html.append('<li>Its dearest hour: <b>%s</b> (%s).</li>'
                         % (_hour_name(busiest), _rs(hours[busiest][0])))
    if not tips_html:
        tips_html.append("<li>No hour with the AC on and nobody in.</li>")
    out = [ev.css(theme), '<div class="ec">',
           '<div class="ec-h" style="margin-top:22px"><span class="t">Hour by '
           'hour</span><span class="c">%s%s · the ACs\' rupees each hour, '
           'the part with nobody in on top · hover an hour</span></div>'
           % (who, basis),
           '<div class="ec-card" style="padding:14px 16px">',
           '<div class="en-note" style="margin:0 0 8px 0">%s: <b>%s</b>, of '
           'which <b style="color:var(--crit)">%s</b> with nobody in.</div>'
           % ("So far today" if so_far else "That day", _rs(total),
              _rs(waste)),
           ev.legend([(on_colour, "with people in"),
                      (waste_colour, "with nobody in")]),
           ev.columns(labels, stacks, [on_colour, waste_colour], tips,
                      height=170),
           '<ul class="en-note" style="margin:10px 0 0 18px;padding:0">%s'
           '</ul>' % "".join(tips_html), '</div>']
    if week:
        lines = []
        for day, ledger, part in week:
            got = [r for r in ledger if name is None or r["room"] == name]
            if not got:
                continue
            t = totals(got)
            lines.append(
                '<tr style="border-top:1px solid var(--line)"><td style="'
                'padding:5px 6px 5px 0">%s%s</td><td style="text-align:right">'
                '%s</td><td style="text-align:right">%s</td><td style="'
                'text-align:right">%s</td><td style="text-align:right;color:'
                'var(--crit)">%s</td></tr>'
                % (esc(pd.Timestamp(day).strftime("%a %d").replace(" 0", " ")),
                   " so far" if part else "",
                   "%.0f h" % sum(r["on_h"] for r in got),
                   format(int(round(t["kwh"])), ","), _rs(t["rs"]),
                   _rs(t["waste_rs"])))
        if lines:
            out.append(
                '<div class="ec-card" style="padding:10px 16px;margin-top:10px;'
                'overflow-x:auto"><table style="width:100%%;border-collapse:'
                'collapse;font-size:13px;color:var(--t1);white-space:nowrap"><tr style="color:'
                'var(--t2);font-size:12px"><th style="text-align:left">Day'
                '</th><th style="text-align:right">%s</th><th style="'
                'text-align:right">kWh</th><th style="text-align:right">Cost'
                '</th><th style="text-align:right">Nobody in</th></tr>%s'
                "</table></div>"
                % ("AC hours" if name is None else "AC on",
                   "".join(reversed(lines))))
    out.append("</div>")
    return "".join(out)


# ------------------------------------------------------- one room's report card

AC_CSS = """<style>
.ac-card{padding:18px 20px 16px}
.ac-head{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;
align-items:flex-start}
.ac-head .n{font-size:18px;font-weight:750;letter-spacing:-.01em}
.ac-head .s{font-size:12.5px;color:var(--t3);margin-top:3px;line-height:1.45}
.ac-head .big{text-align:right;margin-left:auto}
.ac-head .big b{font-size:28px;font-weight:760;letter-spacing:-.02em;
font-variant-numeric:tabular-nums;line-height:1.1}
.ac-head .big span{display:block;font-size:12px;color:var(--t3);margin-top:2px}
.ac-vs{display:inline-block;font-size:12px;font-weight:650;padding:3px 10px;
border-radius:10px;margin-top:6px;border:1px solid var(--line2);line-height:1.35}
.ac-vs.good{color:var(--good);border-color:var(--good)}
.ac-vs.bad{color:var(--crit);border-color:var(--crit)}
.ac-figs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;
margin:16px 0 12px}
.ac-figs>div{background:var(--s2);border-radius:12px;padding:10px 12px;min-width:0}
.ac-figs span{display:block;font-size:11.5px;color:var(--t3)}
.ac-figs b{display:block;font-size:19px;font-weight:720;margin-top:2px;
font-variant-numeric:tabular-nums}
.ac-figs b.crit{color:var(--crit)}
.ac-figs small{display:block;font-size:11.5px;color:var(--t3);margin-top:2px}
.ac-tip{display:flex;gap:10px;align-items:flex-start;font-size:13.5px;
line-height:1.5;margin-top:12px;padding:10px 12px;border-radius:12px;
background:var(--crit-bg);border:1px solid var(--crit-line)}
.ac-tip.ok{background:var(--s2);border-color:var(--line)}
.ac-tip i{flex:none;font-style:normal;font-weight:800;width:20px;height:20px;
border-radius:50%;display:flex;align-items:center;justify-content:center;
font-size:12px;color:#fff;background:var(--crit)}
.ac-tip.ok i{background:var(--good)}
.ac-foot{font-size:12px;color:var(--t3);margin-top:10px;line-height:1.5}
@media (max-width:760px){.ac-figs{grid-template-columns:repeat(2,minmax(0,1fr))}
.ac-head .big{text-align:left;margin-left:0}}
</style>""".replace("\n", "")


def room_usual(week, name, skip=None):
    """A room's usual whole day over `week` ([(date, ledger, so_far)], as
    trend() takes): {on_h, empty_on_h, kwh, rs, save_rs, hourly, days}, the
    days the loop watched nearly whole (WHOLE_DAY_H) and not `skip`; or
    None."""
    got = []
    for day, ledger, so_far in week or []:
        if so_far or (skip is not None and
                      pd.Timestamp(day).date() == pd.Timestamp(skip).date()):
            continue
        r = next((x for x in ledger or [] if x["room"] == name), None)
        if r is None or r.get("watched_h", 24) < WHOLE_DAY_H:
            continue
        got.append(r)
    if not got:
        return None
    n = float(len(got))
    out = {f: sum(r.get(f, 0.0) for r in got) / n
           for f in ("on_h", "empty_on_h", "kwh", "rs")}
    out["save_rs"] = sum(r.get("waste_rs", 0.0) + r.get("over_rs", 0.0)
                         for r in got) / n
    hours = [[0.0, 0.0] for _ in range(24)]
    for r in got:
        for h, (a, w) in enumerate(r.get("hourly") or []):
            hours[h][0] += a / n
            hours[h][1] += w / n
    out["hourly"] = hours
    out["days"] = len(got)
    return out


HOW_MEASURED = {
    READ: "A camera reads its unit%s (the display or the louvre), minute by "
          "minute: measured.",
    PART: "A camera reads %d of its %d units; the others are taken to run "
          "while people are in.",
    ASSUMED: "No camera sees its unit%s: taken to run from when somebody "
             "settles to when the last person leaves.",
    ALWAYS: "Cooled round the clock on purpose: 24 hours.",
}


def ac_card(theme, r, week=None, so_far=True, upto_h=None, day=None):
    """One room's AC report card (Shamroze, 25 Nov: "AC ke report card bhi
    ... bahut detailed nahi, lekin bahut acha, munasib"): what its ACs cost
    against a usual day -- by this hour, for today -- the hours on, the
    hours with nobody in, the units, what could have been saved; the day
    hour by hour; one thing to do. `r` is the room's ledger row, `week` the
    last days' ledgers (room_usual), `upto_h` the hour of the day now."""
    if not r:
        return ""
    u = room_usual(week, r["room"], skip=day)
    save = r.get("waste_rs", 0.0) + r.get("over_rs", 0.0)
    on_h, empty_h = r.get("on_h", 0.0), r.get("empty_on_h", 0.0)
    # Against a usual day: by this hour today (the usual day's own hours up
    # to now), the whole day for a day that is over.
    vs = ""
    if u:
        if so_far and upto_h is not None:
            whole = int(upto_h)
            base = sum(h[0] for h in u["hourly"][:whole])
            if whole < 24:
                base += u["hourly"][whole][0] * (upto_h - whole)
            what = "a usual day by this hour"
        else:
            base, what = u["rs"], "a usual day"
        if base >= 1:
            change = 100.0 * (r["rs"] / base - 1)
            if abs(change) < 5:
                vs = '<span class="ac-vs">about the same as %s (%s)</span>' % (
                    what, _rs(base))
            else:
                vs = ('<span class="ac-vs %s">%s %.0f%% %s than %s (%s)</span>'
                      % ("good" if change < 0 else "bad",
                         "&#9660;" if change < 0 else "&#9650;", abs(change),
                         "less" if change < 0 else "more", what, _rs(base)))
    sizes = r.get("sizes") or ""
    units = "%d unit%s" % (r["units"], "" if r["units"] == 1 else "s")
    if r.get("tons"):
        units += ", %s ton" % ("%g" % r["tons"])
    sub = " · ".join(x for x in (r.get("floor"), units,
                                 sizes if sizes and len(sizes) < 40 else "",
                                 badge(r)) if x)

    def usual(f, fmt):
        # a usual WHOLE day, beside today's hours so far: said so
        return ("usual day %s" % fmt(u[f])) if u else "no usual day yet"
    share = (100.0 * empty_h / on_h) if on_h > 0 else 0.0
    figs = [
        ("AC on", _h(on_h), usual("on_h", _h), ""),
        ("With nobody in", _h(empty_h),
         "%.0f%% of the time on" % share if on_h > 0 else "--",
         "crit" if empty_h >= 0.25 else ""),
        ("Electricity", "%s kWh" % format(int(round(r.get("kwh", 0.0))), ","),
         usual("kwh", lambda v: "%s kWh" % format(int(round(v)), ",")), ""),
        ("Could have saved", _rs(save),
         usual("save_rs", _rs) if u else "nobody in, or too many units",
         "crit" if save >= 1 else ""),
    ]
    fig_html = "".join(
        '<div><span>%s</span><b class="%s">%s</b><small>%s</small></div>'
        % (esc(k), cls, esc(v), esc(s)) for k, v, s, cls in figs)
    waste_colour = "#e8a21a" if theme == "dark" else "#d18a00"
    on_colour = "#2a9d63" if theme == "dark" else "#1f8a55"
    hours = r.get("hourly") or [[0.0, 0.0] for _ in range(24)]
    labels = [("%d%s" % (h % 12 or 12, "a" if h < 12 else "p"))
              if h % 3 == 0 else "" for h in range(24)]
    stacks = [[max(0.0, a - w), w] for a, w in hours]
    tips = ["%s-%s · AC %s · with nobody in %s%s" % (
        _hour_name(h), _hour_name((h + 1) % 24), _rs(a), _rs(w),
        (" · usual %s" % _rs(u["hourly"][h][0])) if u else "")
        for h, (a, w) in enumerate(hours)]
    runs = waste_stretches(hours)
    if runs:
        a, b, rs = runs[0]
        tip = ('<div class="ac-tip"><i>!</i><div>From <b>%s to %s</b> the AC '
               'ran with nobody in: <b style="color:var(--crit)">%s</b>. '
               'Switch it off then.</div></div>'
               % (_hour_name(a), _hour_name(b % 24), _rs(rs)))
    elif r.get("over_rs", 0.0) >= 1:
        tip = ('<div class="ac-tip"><i>!</i><div>More units ran than the '
               'people in needed: <b style="color:var(--crit)">%s</b> over %s. '
               'Fewer people, fewer units.</div></div>'
               % (_rs(r["over_rs"]), _h(r.get("over_h", 0.0))))
    else:
        tip = ('<div class="ac-tip ok"><i>&#10003;</i><div>No hour with the AC '
               'running and nobody in.</div></div>')
    plural = "" if r["units"] == 1 else "s"
    how = HOW_MEASURED.get(r["basis"], "")
    how = (how % (r["read"], r["units"]) if r["basis"] == PART else
           how % plural if "%s" in how else how)
    foot = ("%s Rupees at the marginal rate, the peak tariff by the clock%s."
            % (how, ("; usual: the average of the last %d whole day%s"
                     % (u["days"], "" if u["days"] == 1 else "s")) if u
               else ""))
    return "".join([
        ev.css(theme), AC_CSS, '<div class="ec"><div class="ec-card ac-card">',
        '<div class="ac-head"><div><div class="n">%s</div><div class="s">%s'
        '</div></div><div class="big"><b>%s</b><span>%s</span>%s</div></div>'
        % (esc(r["room"]), esc(sub), _rs(r["rs"]),
           "the ACs so far today" if so_far else "the ACs that day", vs),
        '<div class="ac-figs">%s</div>' % fig_html,
        ev.legend([(on_colour, "with people in"),
                   (waste_colour, "with nobody in")]),
        ev.columns(labels, stacks, [on_colour, waste_colour], tips,
                   height=120),
        tip, '<div class="ac-foot">%s</div>' % esc(foot),
        "</div></div>"])


def glance(theme, today, yesterday, read_units, all_units, base=None,
           in_view=None):
    """The campus page's first row (17 Nov, Envoy's look): today's AC
    rupees, the part with nobody in, yesterday, how many units a camera
    reads -- and one tip, the costliest stretch with nobody in.

    `in_view`: units some camera shows, read or not (rooms.yaml's
    `in_view`). Shamroze, 19 Nov, to follow up: how many are in camera,
    how many calibrated -- the tile says both."""
    t, y = totals(today), totals(yesterday)
    share = (100.0 * t["waste_rs"] / t["rs"]) if t["rs"] else 0.0
    runs = waste_stretches(hourly(today))
    when = ("most at %s to %s" % (_hour_name(runs[0][0]),
                                  _hour_name(runs[0][1] % 24))
            if runs else "no hour mostly empty")
    tiles = [
        ev.tile("AC today so far", _rs(t["rs"]),
                "every room with a unit, from midnight"),
        ev.tile("With nobody in", _rs(t["waste_rs"]),
                "%.0f%% of it · %s" % (share, when), "crit"),
        ev.tile("Yesterday", _rs(y["rs"]),
                "%s of it in empty rooms" % _rs(y["waste_rs"])),
        ev.tile("Units a camera reads", "%d of %d" % (read_units, all_units),
                ("%d more in camera, waiting to be calibrated; the rest "
                 "estimated from people" % (in_view - read_units))
                if in_view is not None and in_view > read_units
                else "the rest are estimated from people"),
    ]
    if runs:
        a, b, rs = runs[0]
        tip = ("From <b>%s to %s</b> the ACs ran in empty rooms: <b style="
               '"color:var(--crit)">%s</b>. Switch them off until people '
               "settle." % (_hour_name(a), _hour_name(b % 24), _rs(rs)))
    else:
        tip = "No hour today with the ACs running mostly in empty rooms."
    return "".join([
        ev.css(theme), '<div class="ec">',
        # en-tiles, not a grid of its own: on a phone the four go two by
        # two (19 Nov: one a row, they filled the first screen and a half).
        '<div class="en-tiles" style="margin:6px 0 14px 0">',
        "".join(tiles), "</div>",
        '<div class="ec-card" style="padding:16px 18px;display:flex;gap:14px;'
        'align-items:flex-start;margin-bottom:8px"><div aria-hidden="true" '
        'style="flex:none;width:40px;height:40px;border-radius:50%%;'
        'background:var(--s2);display:flex;align-items:center;'
        'justify-content:center"><svg width="20" height="20" viewBox="0 0 24 '
        '24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 '
        '21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 '
        '0 0 0 12 3z"/></svg></div><div><div style="font-weight:700;'
        'font-size:16px;margin-bottom:4px">Today\'s tip</div><div '
        'style="font-size:14px;line-height:1.5;color:var(--t2)">%s</div>'
        "</div></div>" % tip, "</div>"])


def rooms_week(theme, week, base=None, shown=12):
    """Every room, every day: what its ACs cost each of the last days and how
    much of it could have been saved (the part with nobody in).

    `week` is [(date, ledger, so_far)] oldest first, as trend() takes.
    Shamroze, 17 Nov: "kal kitne ka, parson kitne ka, roz kitne ka -- 141
    Cafe pura din kitne rupay, kitne bach sakte the".
    """
    week = [w for w in week if w[1]]
    if not week:
        return ""
    days = [pd.Timestamp(d) for d, _, _ in week]
    names = {}
    for i, (_, ledger, _) in enumerate(week):
        for r in ledger:
            cell = names.setdefault(r["room"], [None] * len(week))
            cell[i] = (r["rs"], r["waste_rs"] + r.get("over_rs", 0.0))
    whole = [i for i, w in enumerate(week) if not w[2]]

    def total(cells, k):
        return sum(cells[i][k] for i in whole if cells[i])

    order = sorted(names, key=lambda n: (-total(names[n], 0), n))
    top = max([c[0] for n in order for c in names[n] if c] or [1]) or 1
    rgb = "42,157,99" if theme == "dark" else "31,138,85"
    link = None
    if base is not None:
        link = lambda n: ov.link(base, room=n) + "#roomdetail"  # noqa: E731

    head = "".join(
        '<th style="text-align:right;padding:6px 8px;font-weight:600">%s%s'
        "</th>" % (esc(d.strftime("%a %d").replace(" 0", " ")),
                   '<br><span style="font-weight:400;color:var(--t3)">so far'
                   "</span>" if week[i][2] else "")
        for i, d in reversed(list(enumerate(days))))
    body = []
    for n in order[:shown]:
        cells = []
        for c in reversed(names[n]):
            if not c or c[0] < 0.5:
                cells.append('<td style="text-align:right;padding:6px 8px;'
                             'color:var(--t3)">&middot;</td>')
                continue
            cells.append(
                '<td style="text-align:right;padding:6px 8px;background:'
                'rgba(%s,%.2f)">%s%s</td>'
                % (rgb, 0.06 + 0.30 * c[0] / top,
                   format(int(round(c[0])), ","),
                   '<div style="font-size:11px;color:var(--crit)">%s</div>'
                   % format(int(round(c[1])), ",") if c[1] >= 0.5 else ""))
        spent, saved = total(names[n], 0), total(names[n], 1)
        label = esc(ov.short(n))
        if link:
            label = ('<a href="%s" target="_self" style="color:inherit;'
                     'text-decoration:none">%s</a>' % (esc(link(n)), label))
        body.append(
            '<tr style="border-top:1px solid var(--line)"><td style="padding:'
            '6px 10px 6px 0;position:sticky;left:0;background:var(--s1);'
            'font-weight:600;white-space:normal;min-width:110px">%s</td><td '
            'style="text-align:right;padding:6px 8px;font-weight:700">%s</td>'
            '<td style="text-align:right;padding:6px 8px;font-weight:700;'
            'color:var(--crit);border-right:1px solid var(--line)">%s</td>%s'
            "</tr>" % (label, _rs(spent), _rs(saved), "".join(cells)))
    rest = order[shown:]
    if rest:
        body.append(
            '<tr style="border-top:1px solid var(--line);color:var(--t2)"><td '
            'colspan="%d" style="padding:6px 0">%d more room%s, %s together'
            "</td></tr>" % (len(days) + 3, len(rest),
                            "" if len(rest) == 1 else "s",
                            _rs(sum(total(names[n], 0) for n in rest))))

    # The summary line: yesterday, the day before, a usual day.
    sums = [(sum(r["rs"] for r in w[1]),
             sum(r["waste_rs"] + r.get("over_rs", 0.0) for r in w[1]))
            for w in week]
    said = []
    for back, word in ((1, "Yesterday"), (2, "The day before")):
        i = len(week) - 1 - back if week[-1][2] else len(week) - back
        if 0 <= i < len(week) and not week[i][2]:
            said.append('%s (%s) <b>%s</b>, of which <b style="color:'
                        'var(--crit)">%s</b> could have been saved'
                        % (word, esc(days[i].strftime("%a")), _rs(sums[i][0]),
                           _rs(sums[i][1])))
    # A usual day: only days the cameras watched nearly whole.
    full = [i for i in whole
            if totals(week[i][1]).get("watched_h", 24) >= WHOLE_DAY_H]
    if full:
        said.append("a usual day <b>%s</b>, of which <b style=\"color:"
                    "var(--crit)\">%s</b> could have been saved"
                    % (_rs(sum(sums[i][0] for i in full) / len(full)),
                       _rs(sum(sums[i][1] for i in full) / len(full))))
    return "".join([
        ev.css(theme), '<div class="ec">',
        '<div class="ec-h" style="margin-top:22px"><span class="t">Every room,'
        ' every day</span><span class="c">the ACs\' rupees each day; in red, '
        "what could have been saved: units running with nobody in, or more "
        "units than the people in needed</span></div>",
        '<div class="ec-card" style="padding:14px 16px">',
        '<div class="en-note" style="margin:0 0 10px 0;line-height:1.6">%s.'
        "</div>" % ".<br>".join(s[0].upper() + s[1:] for s in said),
        '<div style="overflow-x:auto"><table style="width:100%%;'
        "border-collapse:collapse;font-size:13px;color:var(--t1);"
        'white-space:nowrap;font-variant-numeric:tabular-nums"><tr style="'
        'color:var(--t2);font-size:12px"><th style="text-align:left;'
        'position:sticky;left:0;background:var(--s1)">Room</th><th style="'
        'text-align:right;padding:6px 8px">%d days</th><th style="text-align:'
        'right;padding:6px 8px;border-right:1px solid var(--line)">Could save'
        "</th>%s</tr>%s</table></div>"
        % (len(whole), head, "".join(body)),
        '<div class="en-note" style="margin-top:8px">Rupees, midnight to '
        "midnight, the same estimate as the rooms above. The totals leave out "
        "today, which is not over. Darker green, a dearer day.</div>",
        "</div></div>"])


def too_many(theme, rows, so_far=True, shown=4):
    """More units running than the people in needed, room by room.

    Shamroze, 17 Nov: "the cafe has few people except at the peak, and we
    ran six at once -- show where it is run wrong: fewer people, fewer
    units". Only rooms with people_per_unit in rooms.yaml and a camera
    reading how many units run.
    """
    mine = [r for r in rows if r.get("over")]
    if not mine:
        return ""
    mine.sort(key=lambda r: -r.get("over_rs", 0.0))
    cards = []
    for r in mine:
        spells = sorted(r["over"], key=lambda s: -s["rs"])[:shown]
        spells.sort(key=lambda s: s["from"])
        lines = "".join(
            '<li><b>%s to %s</b>: %d running for %d %s, %d would do '
            '&middot; <b style="color:var(--crit)">%s</b></li>'
            % (ov.clock(s["from"]), ov.clock(s["to"]), s["units"],
               s["people"], "person" if s["people"] == 1 else "people",
               s["need"], _rs(s["rs"]))
            for s in spells)
        more = len(r["over"]) - len(spells)
        cards.append(
            '<div class="ec-card" style="padding:14px 16px;margin-bottom:10px">'
            '<div style="display:flex;justify-content:space-between;gap:10px;'
            'flex-wrap:wrap"><b style="font-size:15px">%s</b><span style="'
            'color:var(--crit);font-weight:700">%s more than needed</span>'
            '</div><div class="en-note" style="margin:4px 0 6px 0">%s units, '
            "one for about %d people, plus one spare &middot; %s</div>"
            '<ul class="en-note" style="margin:0 0 0 18px;padding:0">%s</ul>%s'
            "</div>"
            % (esc(r["room"]), _rs(r["over_rs"]), r["units"],
               int(round(r["people_per_unit"])), _h(r["over_h"]) + " too many",
               lines, ('<div class="en-note" style="margin-top:4px">and %d '
                       "more stretch%s</div>" % (more, "" if more == 1
                                                 else "es")) if more else ""))
    return "".join([
        ev.css(theme), '<div class="ec">',
        '<div class="ec-h" style="margin-top:22px"><span class="t">More ACs '
        'than people</span><span class="c">%s: units running beyond what '
        "the people in needed</span></div>"
        % ("today so far" if so_far else "that day"),
        "".join(cards), "</div>"])


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
