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
    if (len(found) > 1 and not result["carried"]
            and first[1] - first[0] <= EARLY_MAX
            and found[1][0] - first[1] >= EARLY_GAP):
        result["early"] = {"from": first[0], "to": first[1],
                           "people": first[2],
                           "empty_after_min":
                               (found[1][0] - first[1]).total_seconds() / 60}
        result["starts"] = found[1][0]
    else:
        result["starts"] = first[0]
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


def clock(ts):
    """9:05 AM -- twelve-hour, no leading zero, which is how it is said.

    In Karachi time whatever the timestamp arrives in. The database hands
    back UTC, and the first render of this page put the cleaner at 2:08 AM
    instead of 7:08 -- five hours out, on every time on the page. The
    checks had built their timestamps in Karachi time already, so they
    could not see it; they now also feed it UTC.
    """
    if ts is None:
        return "—"
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(LOCAL)
    h, m = ts.hour, ts.minute
    return "%d:%02d %s" % (h % 12 or 12, m, "AM" if h < 12 else "PM")


def spell(minutes):
    minutes = int(round(minutes))
    if minutes < 60:
        return "%dm" % minutes
    h, m = divmod(minutes, 60)
    return "%dh" % h if not m else "%dh %02dm" % (h, m)
