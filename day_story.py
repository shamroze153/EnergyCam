"""One room's day, told in the order it happened.

The first version of "who comes when" drew one bar per room from the first
person seen to the last, averaged over every day on record. That answers
"roughly when is this room used" and hides everything else -- in
particular the thing everybody who has watched the building already knows:
the first person in a room at 7am is usually the cleaner, the room then
sits empty for an hour or two, and the day proper starts at nine. An
average of first-seen times smears the cleaner and the staff into one
meaningless 8:10.

So each day is read as a sequence of spells, and the story pulls out:

  first in      the first person seen that day
  early visit   a short first spell followed by a long empty gap --
                housekeeping, a guard's round -- and how long the room
                then sat empty
  day starts    the first spell that is not an early visit
  peak          the most people seen at once, and when
  busy          share of the watched time somebody was there
  last out      when the last person left

Only changes are recorded, so a spell runs from one row to the next. The
state at midnight is carried in from the last row before it. Time the loop
was not running is not counted as empty or as busy: given the heartbeats,
unwatched time is set aside, so "busy 60%" means 60% of the time anybody
was looking.
"""
from datetime import timedelta

import pandas as pd

# Two occupied spells this close together are one visit with a flicker in
# it -- a seated person the detector loses for a frame or two. Without
# merging them, one person at a desk all morning reads as a dozen visits.
MERGE_GAP = timedelta(minutes=10)

# A first spell no longer than this, followed by an empty stretch at least
# as long as EARLY_GAP, is an early visit rather than the start of the day.
EARLY_MAX = timedelta(minutes=45)
EARLY_GAP = timedelta(minutes=30)

# Heartbeats further apart than this mean the loop was not running between.
BEAT_GAP = timedelta(minutes=10)


def watched(beats, start, end):
    """The stretches of [start, end) the loop was running for."""
    if beats is None:
        return [(start, end)]
    stamps = sorted(b for b in beats if start - BEAT_GAP <= b <= end + BEAT_GAP)
    out = []
    for stamp in stamps:
        a, b = max(start, stamp - BEAT_GAP / 2), min(end, stamp + BEAT_GAP / 2)
        if a >= b:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def spells(events, start, end, beats=None):
    """(status, people, from, to) covering [start, end), unwatched as unknown.

    `events` is one room's rows, any range; the last row before `start`
    supplies the state the day began in.
    """
    if events.empty:
        # Never written down: not empty, not busy -- nobody knows.
        return [("unknown", 0, start, end)]
    rows = events.sort_values("timestamp")
    before = rows[rows["timestamp"] < start].tail(1)
    inside = rows[(rows["timestamp"] >= start) & (rows["timestamp"] < end)]
    rows = pd.concat([before, inside])
    raw = []
    for i in range(len(rows)):
        r = rows.iloc[i]
        a = max(r["timestamp"], start)
        b = rows.iloc[i + 1]["timestamp"] if i + 1 < len(rows) else end
        b = min(b, end)
        if a < b:
            people = r["people"] if pd.notna(r["people"]) else 0
            raw.append([r["status"], int(people), a, b])
    if not raw or raw[0][2] > start:
        raw.insert(0, ["unknown", 0, start, raw[0][2] if raw else end])

    # Lay the watched stretches over it: outside them, nobody was looking.
    seen = watched(beats, start, end)
    out = []
    for status, people, a, b in raw:
        cursor = a
        for wa, wb in seen:
            if wb <= cursor or wa >= b:
                continue
            if wa > cursor:
                out.append(["unknown", 0, cursor, wa])
            out.append([status, people, max(cursor, wa), min(b, wb)])
            cursor = min(b, wb)
        if cursor < b:
            out.append(["unknown", 0, cursor, b])
    return [tuple(s) for s in out]


def combine(days):
    """One department's day, from the days of each of its rooms.

    Squat Wolf is five rooms and Finance is one, and both asked to be read
    the same way: when did the department start, when did it finish, how
    many of its people were in at once. So the department is busy whenever
    any of its rooms is, and its people are the rooms' people added up --
    added, not the largest, because these are different rooms with
    different people in them. (Several cameras on one room are the other
    case, and the loop already takes the largest for those.)

    Unknown only where every room is unknown. A department with one room
    unwatched and the rest empty is reported empty; with one room busy it
    is busy whatever the others were doing.

    Every day in `days` must cover the same stretch, as spells() makes them.
    """
    days = [d for d in days if d]
    if not days:
        return []
    if len(days) == 1:
        return list(days[0])
    cuts = sorted({t for day in days for _, _, a, b in day for t in (a, b)})
    at = [0] * len(days)
    out = []
    for a, b in zip(cuts, cuts[1:]):
        known, busy, people = None, False, 0
        for i, day in enumerate(days):
            while at[i] < len(day) and day[at[i]][3] <= a:
                at[i] += 1
            if at[i] >= len(day) or day[at[i]][2] > a:
                continue
            status, n = day[at[i]][0], day[at[i]][1]
            if status == "unknown":
                continue
            known = known or status
            if status == "occupied":
                busy, people = True, people + n
        status = "occupied" if busy else (known or "unknown")
        people = people if busy else 0
        if out and out[-1][0] == status and out[-1][1] == people \
                and out[-1][3] == a:
            out[-1][3] = b
        else:
            out.append([status, people, a, b])
    return [tuple(s) for s in out]


def visits(day):
    """Occupied spells, with flickers shorter than MERGE_GAP joined up.

    Returns (from, to, most_people, when_most).
    """
    out = []
    for status, people, a, b in day:
        if status != "occupied":
            continue
        if out and a - out[-1][1] <= MERGE_GAP:
            f, t, most, when = out[-1]
            if people > most:
                most, when = people, a
            out[-1] = (f, b, most, when)
        else:
            out.append((a, b, people, a))
    return out


def story(day, start):
    """The numbers for one room's day. None where there is nothing to say."""
    seen = sum((b - a for s, _, a, b in day if s != "unknown"), timedelta())
    busy = sum((b - a for s, _, a, b in day if s == "occupied"), timedelta())
    found = visits(day)
    result = {
        "watched_min": seen.total_seconds() / 60,
        "busy_pct": (100.0 * busy / seen) if seen else None,
        "first_in": None, "carried": False, "early": None,
        "starts": None, "peak": 0, "peak_at": None, "last_out": None,
        "visits": len(found),
    }
    if not found:
        return result

    result["first_in"] = found[0][0]
    result["carried"] = found[0][0] <= start
    result["last_out"] = found[-1][1]
    most = max(found, key=lambda v: (v[2], -v[3].timestamp()))
    result["peak"], result["peak_at"] = most[2], most[3]

    first = found[0]
    rest = found
    if (len(found) > 1 and not result["carried"]
            and first[1] - first[0] <= EARLY_MAX
            and found[1][0] - first[1] >= EARLY_GAP):
        result["early"] = {"from": first[0], "to": first[1],
                           "people": first[2],
                           "empty_after_min":
                               (found[1][0] - first[1]).total_seconds() / 60}
        rest = found[1:]
    # The day starts with the first visit somebody stayed for. A room that
    # only saw the office boy twice has not started a day at all: the
    # first version called his second cup of tea at 11:00 the start of
    # HR's day, with a "busy stretch" round it.
    brief, _ = kinds(rest)
    stays = [v for v in rest if v not in brief]
    if result["carried"]:
        result["starts"] = first[0]
    elif stays:
        result["starts"] = stays[0][0]
    else:
        result["starts"] = None
        result["early"] = None
    return result


def hourly(day, start):
    """Average people in each of the 24 hours; None for an hour nobody saw."""
    out = []
    for h in range(24):
        a, b = start + timedelta(hours=h), start + timedelta(hours=h + 1)
        total, looked = 0.0, 0.0
        for status, people, sa, sb in day:
            lo, hi = max(a, sa), min(b, sb)
            if lo >= hi or status == "unknown":
                continue
            minutes = (hi - lo).total_seconds() / 60
            looked += minutes
            if status == "occupied":
                total += people * minutes
        out.append(total / looked if looked >= 5 else None)
    return out


LOCAL = "Asia/Karachi"


# Parts of the day, as they are said. AM and PM were asked to go: "9:05
# AM" against "9:05 PM" is one letter apart and was being misread, where
# "9:05 morning" and "9:05 night" are not.
PARTS = [("night", 0, 5), ("morning", 5, 12), ("afternoon", 12, 17),
         ("evening", 17, 21), ("night", 21, 24)]


def part_of(hour):
    for name, a, b in PARTS:
        if a <= hour < b:
            return name
    return "night"


def clock(ts):
    """9:05 morning, 7:40 evening, 2:30 night -- the way a time is said.

    Twelve-hour, in Karachi time whatever the timestamp arrives in. The
    database hands back UTC, and the first render of this page put the
    cleaner at 2:08 instead of 7:08 -- five hours out, on every time on the
    page. The checks build their timestamps both ways now.
    """
    if ts is None:
        return "\u2014"
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(LOCAL)
    h, m = ts.hour, ts.minute
    return "%d:%02d %s" % (h % 12 or 12, m, part_of(h))


def spell(minutes):
    minutes = int(round(minutes))
    if minutes < 60:
        return "%dm" % minutes
    h, m = divmod(minutes, 60)
    return "%dh" % h if not m else "%dh %02dm" % (h, m)


# A visit this short, by one or two people, is somebody passing through --
# an office boy with tea, the cleaner, a guard on a round -- rather than
# somebody working there. A visit shorter than one pass of the loop (two
# or three minutes) is usually not seen at all, so these are a floor.
BRIEF = timedelta(minutes=15)
BRIEF_PEOPLE = 2
BREAK_MIN = 5          # an empty stretch shorter than this is not a break


def by_minute(day, start):
    """1440 values: people in the room each minute, None where unwatched."""
    out = [None] * 1440
    for status, people, a, b in day:
        if status == "unknown":
            continue
        i = max(0, int((a - start).total_seconds() // 60))
        j = min(1440, int(-(-(b - start).total_seconds() // 60)))
        for k in range(i, j):
            out[k] = people if status == "occupied" else 0
    return out


def runs(values, test):
    """(first, last+1) for every run of minutes where test(value) holds."""
    found, begin = [], None
    for i, v in enumerate(values + [None]):
        if v is not None and test(v):
            begin = i if begin is None else begin
        elif begin is not None:
            found.append((begin, i))
            begin = None
    return found


def peak_stretch(mins):
    """The busy part of the day, and how people came and went inside it.

    The stretch runs from the first minute the room reached half its peak
    to the last minute it still held that many -- for a one-person room,
    simply from first in to last out. Inside it: how often the room
    emptied completely for at least BREAK_MIN minutes, for how long in
    total, the longest such break, and the longest unbroken stay. Its end
    is when people started leaving for good.
    """
    seen = [v for v in mins if v]
    if not seen:
        return None
    peak = max(seen)
    half = max(1, -(-peak // 2))
    hits = [i for i, v in enumerate(mins) if v is not None and v >= half]
    a, b = hits[0], hits[-1] + 1
    inside = mins[a:b]
    gaps = [r for r in runs(inside, lambda v: v == 0) if r[1] - r[0] >= BREAK_MIN]
    stays = runs(inside, lambda v: v > 0)
    return {"from": a, "to": b, "half": half,
            "breaks": len(gaps),
            "away_min": sum(g[1] - g[0] for g in gaps),
            "longest_break": max([g[1] - g[0] for g in gaps] or [0]),
            "longest_stay": max([s_[1] - s_[0] for s_ in stays] or [0])}


def kinds(found):
    """Split visits into brief ones and stays."""
    brief = [v for v in found if v[1] - v[0] <= BRIEF and v[2] <= BRIEF_PEOPLE]
    return brief, [v for v in found if v not in brief]


def parts(day, start):
    """Per part of the day: busy share, brief visits, stays, most people."""
    mins = by_minute(day, start)
    found = visits(day)
    out = []
    for name, a, b in PARTS:
        span = mins[a * 60:b * 60]
        watched = sum(1 for v in span if v is not None)
        busy = sum(1 for v in span if v)
        lo, hi = start + timedelta(hours=a), start + timedelta(hours=b)
        here = [v for v in found if lo <= v[0] < hi]
        brief, stays = kinds(here)
        out.append({"part": name, "from": a, "to": b,
                    "watched": watched,
                    "busy_pct": (100.0 * busy / watched) if watched else None,
                    "brief": len(brief), "stays": len(stays),
                    "most": max([v for v in span if v] or [0])})
    return out


def window(day, start, a_hours, b_hours):
    """One room inside a stretch of the day -- the peak tariff, usually.

    18:30 to 22:30 is when every unit costs the most, and it falls after
    most people have gone home, which is exactly when a room is most
    likely to be empty with its cooling left on. So: how much of the
    window somebody was there, how many on average and at most, how long
    it sat empty, any brief visits, and when the last person left if they
    left inside it.
    """
    mins = by_minute(day, start)
    a, b = int(round(a_hours * 60)), int(round(b_hours * 60))
    span = mins[a:b]
    watched = [v for v in span if v is not None]
    lo, hi = start + timedelta(minutes=a), start + timedelta(minutes=b)
    here = [v for v in visits(day) if v[1] > lo and v[0] < hi]
    brief, _ = kinds([v for v in here if v[0] >= lo])
    left = None
    if watched and span[-1] == 0:
        busy_idx = [i for i, v in enumerate(span) if v]
        if busy_idx:
            left = lo + timedelta(minutes=busy_idx[-1] + 1)
    return {
        "watched_min": len(watched),
        "busy_pct": (100.0 * sum(1 for v in watched if v) / len(watched))
                    if watched else None,
        "avg": (sum(watched) / float(len(watched))) if watched else None,
        "most": max(watched or [0]),
        "empty_min": sum(1 for v in watched if v == 0),
        "brief": len(brief),
        "at_start": span[0] if span else None,
        "at_end": span[-1] if span else None,
        "left_at": left,
    }


def minute_of_day(ts):
    """Minutes past local midnight, so times on different days can be averaged."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(LOCAL)
    return ts.hour * 60 + ts.minute


def _mean(values):
    values = [v for v in values if v is not None]
    return (sum(values) / float(len(values))) if values else None


def average_days(stories, windows=None):
    """One room over several days: the usual day, and how often things happen.

    Times are averaged as minutes past midnight, and only over the days
    they happened on: a day the room was busy from the night before has no
    arrival, a day nobody came has no start, and neither is counted as
    midnight. Counts that matter as frequencies -- an early visit, a room
    used at all -- are given as "on n of m days" rather than averaged away.
    """
    days = len(stories)
    used = [s for s in stories if s["first_in"] is not None]
    arrived = [s for s in used if not s["carried"]]
    out = {
        "days": days,
        "days_used": len(used),
        "first_in": _mean([minute_of_day(s["first_in"]) for s in arrived]),
        "starts": _mean([minute_of_day(s["starts"]) for s in used
                         if s["starts"] is not None and not s["carried"]]),
        "early_days": sum(1 for s in used if s["early"]),
        "early_empty": _mean([s["early"]["empty_after_min"] for s in used
                              if s["early"]]),
        "peak": max([s["peak"] for s in used] or [0]),
        "peak_avg": _mean([s["peak"] for s in used]),
        "peak_at": _mean([minute_of_day(s["peak_at"]) for s in used
                          if s["peak_at"] is not None]),
        "busy_pct": _mean([s["busy_pct"] for s in stories]),
        "last_out": _mean([minute_of_day(s["last_out"]) for s in used
                           if s["last_out"] is not None
                           and s.get("left") is not False]),
        "brief": _mean([s.get("brief", 0) for s in stories]),
    }
    if windows is not None:
        seen = [w for w in windows if w["busy_pct"] is not None]
        out["window"] = {
            "days": len(seen),
            "busy_pct": _mean([w["busy_pct"] for w in seen]),
            "avg": _mean([w["avg"] for w in seen]),
            "most": max([w["most"] for w in seen] or [0]),
            "empty_min": _mean([w["empty_min"] for w in seen]),
            "brief": _mean([w["brief"] for w in seen]),
            "left_at": _mean([minute_of_day(w["left_at"]) for w in seen
                              if w["left_at"] is not None]),
            "busy_days": sum(1 for w in seen if w["most"]),
        }
    return out


def clock_minutes(minutes):
    """A minute-of-day average as a time, said the same way as clock()."""
    if minutes is None:
        return "\u2014"
    m = int(round(minutes)) % 1440
    h, m = divmod(m, 60)
    return "%d:%02d %s" % (h % 12 or 12, m, part_of(h))
