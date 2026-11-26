"""Where an employee's day went: the desk, meeting rooms, the cafe, smoking,
prayer, elsewhere in the building, out of it -- or not known.

Shamroze, 26 Nov 2026: not only at the desk / in / out, but how long in the
cafe or pantry, the smoking area, meeting rooms, prayer, the rest of the
building and out of it -- as an overview ("8.1 h in the building: 5.2 h at
the desk, 0.9 h meeting rooms, 0.6 h cafe, ...") and as the day in one
line, "from 13:05 to 13:40 in the cafe", the way a room's AC is drawn.

Nothing here opens a camera or writes a file: it reads what the loop and
the attendance machines have already recorded on this laptop. pandas and
yaml only -- the dashboard's side imports it.

    day_places(day, line, sightings, exits, machines)
        -> {"day", "span": (first, last) | None,
            "segments": [(start, end, kind, name, how)],
            "totals": {kind: minutes}, "by_place": {room: minutes},
            "away_min", "seen_min", "conflicts", "unsure", "cameras"}
    for_person(person, day, employee_id, ...)   the same, inputs gathered
    board(person, employee_id, days, focus, cache, lines=...)
        -> (places, places_days) for progress_data.build:
           places      {"day", "segments": [(start, end, kind, name)],
                        "totals": {kind: minutes}} for the focus day
           places_days {day: {kind: minutes}}
    overview(totals), describe(segment)          the words for the card
    python places_day.py [day ...]   how much time away from the desk
                                     gets a place (numbers, never names)

Kinds (KINDS): desk; meeting (board and meeting rooms); cafe (the cafe,
pantry, commons, gaming area); smoking; prayer (the mosque, ablution);
inside -- in the building, the place not seen, or seen somewhere that is
none of these (a lobby, the reception, another office: then its name);
out -- out of the building; unknown. A segment's name is the room it was
seen in ("141-D" at the other campus's machines), "" when nobody saw
where; `how` says what placed it: desk (the seat notes), face (a face on
the cameras), seen (a body match or a picture a person confirmed),
machines (attendance), gate, none (watched, nothing to say where),
unwatched (a hole in the passes).

The rules, in order -- each speaks only where those above it said nothing:

 1. The day runs from the first of (the first pass at the desk ending after
    08:00, the first IN punch from 06:00) to the last of (the last pass at
    the desk, the last OUT punch); a sighting inside the building up to an
    hour before or after widens it (one outside does not: after the last
    OUT it is the way home). Before and after is not drawn. Neither a pass
    at the desk nor a punch: no day.
 2. A pass at the desk is "desk" (progress_data.timeline: one pass missed
    between two at the desk is at the desk, a lone pass is not). A gap of
    up to two minutes between passes is closed, and a hole in the watching
    of up to HOLE_FILL between two passes alike. Nothing below overrides
    the desk.
 3. A sighting off the desk -- a face on the campus cameras (people/
    sightings at progress_data's CCTV_MIN / CCTV_MARGIN), a listed
    employee's face row or a body match confirmed on the tab (progress/
    <day>.csv; a "no" wins), a picture a person named (people/
    sighting_names.csv) -- covers SIGHT_HALF either side of it, cut to the
    time away from the desk it falls in; two of the same room in one such
    stretch (no pass at the desk between) up to SIGHT_JOIN apart are one
    stay, the gap between filled; where two rooms' windows meet, the
    nearer sighting has it. A sighting while the desk shows them sitting
    is not used (a conflict, counted) -- and when UNSURE_LEAST or more of
    one source's sightings of somebody in a day, and UNSURE_SHARE of them,
    fall while the desk shows them sitting, none of that source's that
    day is used (`unsure`): its face is being found on somebody else, or
    somebody else sits at the desk (24-25 Nov: two people's camera faces,
    ten of them a day in the cafe and the parking while their desks were
    taken).
 4. Out through the attendance machine and in again (an outing,
    attendance.py), or at the other campus's machines (141-D: "out", named
    so, from its first punch to the next one at 140-H), is "out" -- certain
    -- except where a sighting at a place outside the building (the
    smoking area, the street, a parking: building.yaml's `outside: true`)
    names where they were; a sighting at a place inside during it is not
    used (a conflict).
 5. A face named at the gate (Entry H sees faces on the way out) is "out"
    from then until the next sighting inside, the desk or the next IN
    punch -- not for a desk beside the gate (progress_data.GATE_BLIND).
 6. Away from the desk, watched, while the machines say inside: "inside"
    -- in the building, the place not seen (a restroom, a corridor, a room
    without a camera).
 7. Everything else is "unknown": a hole in the watching (at the desk or
    not is not known), or away with nothing to say where -- no punch that
    day, or past the end of the machines' export (HR's export of 25 Nov
    stops at 12:18).

The machines keep their own clock (25 Nov: the laptop 162-165 s ahead):
their times are moved onto the laptop's by attendance.clock_offset where
the gate lets it be measured.

Minutes are clock minutes from first in to last out, the small gaps and
holes between passes closed -- a little more desk time than the
history's desk_min, which counts the watched passes only.
"""
import os
import sys
import time

import pandas as pd

import progress_data as pdx

KINDS = ("desk", "meeting", "cafe", "smoking", "prayer", "inside", "out",
         "unknown")
# A sighting stands for this long either side of it: the loop sees each
# camera every four to five minutes, and a named face on one camera is
# written at most every five (cctv_faces.REPEAT) -- so a stay is a run of
# sightings about ten minutes apart, and one look is about ten minutes.
SIGHT_HALF = pd.Timedelta(minutes=5)
# Two sightings of the same room this close, with no pass at the desk
# between them, are one stay. 24 Nov, a listed employee in the Basement
# Meeting Room from 13:15 to 14:21, by face 13 times: once 21 minutes went
# by without one (the face turned away).
SIGHT_JOIN = pd.Timedelta(minutes=30)
# A sighting inside the building this near the day widens it --
# progress_data.SEEN_WINDOW, the same hour. One outside (the street, the
# gate) does not: after the last OUT punch it is the way home.
SPAN_REACH = pdx.SEEN_WINDOW
# The machines' punches before this hour are the night's (a guard's round,
# the tail of a late night): they do not start the day.
MACHINE_FROM = 6
# A hole in the watching this short between two passes alike is taken as
# they are -- as timeline() takes one missed pass between two at the desk
# (24 Nov: the loop rested 4-5 minutes four times an evening, and every
# desk showed "not known" slivers between passes at it).
HOLE_FILL = pd.Timedelta(minutes=10)
# A piece shorter than this (not the desk) goes to its longer neighbour:
# the machines' clock and the laptop's leave slivers of seconds.
MIN_SEG = pd.Timedelta(seconds=60)
# A source of somebody's sightings is not used that day when this many of
# them, and this share, fall while their desk shows them sitting (rule 3).
# 24-25 Nov: the named people's camera faces at the desk were 3 of 13 for
# everybody else, but 8 of 34 and 10+ of the cafe's for two people.
UNSURE_LEAST = 3
UNSURE_SHARE = 0.25
# The kinds of place a sighting's room can be (progress_data.place_of).
NAMED_KINDS = ("meeting", "cafe", "smoking", "prayer")
OUTSIDE_KINDS = ("out", "smoking")

SIGHTINGS = pdx.CCTV_SIGHTINGS          # people/sightings/<day>.csv
GATE = pdx.GATE                         # people/entrance/<day>.csv
ACTIVITY = pdx.ACTIVITY                 # progress/<day>.csv (the listed)
NAMED = pdx.SIGHTING_NAMES              # people/sighting_names.csv

# Which claim wins where two say something of the same minutes.
_DESK, _SEEN_OUTSIDE, _OUTING, _SEEN, _GATE, _INSIDE, _NONE = \
    6, 5, 4, 3, 2, 1, 0

LABEL = {"desk": "at the desk", "meeting": "in a meeting room",
         "cafe": "in the cafe", "smoking": "in the smoking area",
         "prayer": "at prayer", "inside": "in the building, place not seen",
         "out": "out of the building", "unknown": "not known"}
SHORT = {"desk": "at the desk", "meeting": "meeting rooms", "cafe": "cafe",
         "smoking": "smoking", "prayer": "prayer",
         "inside": "elsewhere in the building", "out": "out",
         "unknown": "not known"}


# ------------------------------------------------------------ the kinds

def kind_of(room, own=None, plan=None):
    """The kind of place a sighting's room is: meeting, cafe, smoking,
    prayer; "out" outside the building (building.yaml's `outside: true`,
    a street, a parking, the gate); else "inside" -- a lobby, the
    reception, another office, their own room away from the desk."""
    k = pdx.place_of(room, own)
    if k in NAMED_KINDS:
        return k
    if k in ("left", "outside"):
        return "out"
    if ((((plan or {}).get("places") or {}).get(room)) or {}).get("outside"):
        return "out"
    return "inside"


# ------------------------------------------------------------ the core
#
# Times inside the core are whole nanoseconds (Timestamp.value): a day is
# a few hundred comparisons a claim, and ints compare fifty times faster.

def _runs(line, fill=HOLE_FILL):
    """The passes as [start, end, at_desk] runs (ns): a gap up to
    progress_data.JOINED closed, and one up to `fill` between two passes
    alike; passes of one kind in a row joined."""
    joined, fill = pdx.JOINED.value, fill.value
    runs = []
    for p in sorted(line or [], key=lambda p: p[0]):
        s, e, desk = p[0].value, p[1].value, p[2] in pdx.AT_DESK
        if runs:
            gap = s - runs[-1][1]
            if s < runs[-1][1]:
                s = runs[-1][1]               # an overlap: once only
            elif gap <= joined or (runs[-1][2] == desk and gap <= fill):
                s = runs[-1][1]               # a gap of seconds: closed
        if e <= s:
            continue
        if runs and runs[-1][2] == desk and runs[-1][1] == s:
            runs[-1][1] = e
        else:
            runs.append([s, e, desk])
    return runs


def _span(day, runs, machines, marks):
    """(first, last) of the day (rule 1) as ns, or None. marks: the
    sightings inside the building (ns)."""
    start_of_day = (pd.Timestamp(day)
                    + pd.Timedelta(hours=pdx.DAY_FROM)).value
    desk = [r for r in runs if r[2] and r[1] > start_of_day]
    lo, hi = [], []
    if desk:
        lo.append(desk[0][0])
        hi.append(desk[-1][1])
    first_in = machines.get("first_in")
    last_out = machines.get("last_out")
    if first_in is not None:
        lo.append(first_in.value)
        hi.append(first_in.value)
    if last_out is not None:
        hi.append(last_out.value)
        if not lo:
            lo.append(last_out.value)
    if not lo:
        return None
    a, z = min(lo), max(hi)
    reach = SPAN_REACH.value
    near = [t for t in marks if a - reach <= t <= z + reach]
    a, z = min([a] + near), max([z] + near)
    return (a, z) if z > a else None


def _cut(spans, lo, hi):
    """Each (a, b) of spans cut to [lo, hi]; empty ones left out."""
    return [(max(a, lo), min(b, hi)) for a, b in spans
            if min(b, hi) > max(a, lo)]


def _between(a, b, others):
    """The parts of [a, b) that are in none of `others` [(s, e)]."""
    out, t = [], a
    for s, e in sorted(others):
        if e <= t or s >= b:
            continue
        if s > t:
            out.append((t, s))
        t = max(t, e)
    if t < b:
        out.append((t, b))
    return out


def _claim(s, e, prio, kind, name="", how="none", anchor=None, cams=()):
    return {"s": s, "e": e, "p": prio, "kind": kind, "name": name,
            "how": how, "anchor": anchor, "cams": list(cams)}


def _dist(anchor, t):
    """How far t is from a sighting stay (t0, tn); 0 inside it or none."""
    if anchor is None:
        return 0
    a, z = anchor
    if a <= t <= z:
        return 0
    return min(abs(t - a), abs(t - z))


def _resolve(claims, lo, hi):
    """One line from lo to hi: in each piece the highest priority wins; of
    two sightings' windows, the nearer sighting. [[start, end, claim]]."""
    cuts = {lo, hi}
    for c in claims:
        for t in (c["s"], c["e"]):
            if lo < t < hi:
                cuts.add(t)
    # halfway between one sighting stay and the next: where windows meet
    stays = sorted(c["anchor"] for c in claims if c["anchor"] is not None)
    for (_, a1), (b0, _) in zip(stays, stays[1:]):
        if lo < (a1 + b0) // 2 < hi:
            cuts.add((a1 + b0) // 2)
    cuts = sorted(cuts)
    claims = sorted(claims, key=lambda c: c["s"])
    out = []
    for a, b in zip(cuts, cuts[1:]):
        mid = (a + b) // 2
        best, key = None, None
        for c in claims:
            if c["s"] > a:
                break
            if c["e"] >= b:
                k = (c["p"], -_dist(c["anchor"], mid))
                if key is None or k > key:
                    best, key = c, k
        if best is None:
            continue
        if out and out[-1][2] is best and out[-1][1] == a:
            out[-1][1] = b
        else:
            out.append([a, b, best])
    return out


def _absorb(pieces, least):
    """A piece shorter than `least` that is not the desk goes to its
    longer touching neighbour that is not the desk either."""
    out = [list(p) for p in pieces]
    changed = True
    while changed:
        changed = False
        for i, p in enumerate(out):
            if p[2]["kind"] == "desk" or p[1] - p[0] >= least:
                continue
            prev = out[i - 1] if i > 0 and out[i - 1][1] == p[0] \
                and out[i - 1][2]["kind"] != "desk" else None
            nxt = out[i + 1] if i + 1 < len(out) and out[i + 1][0] == p[1] \
                and out[i + 1][2]["kind"] != "desk" else None
            take = max([q for q in (prev, nxt) if q is not None],
                       key=lambda q: q[1] - q[0], default=None)
            if take is None:
                continue
            if take is prev:
                prev[1] = p[1]
            else:
                nxt[0] = p[0]
            del out[i]
            changed = True
            break
    return out


def _minutes(a, b):
    """Minutes from a to b: Timestamps, or ns."""
    d = b - a
    s = d.total_seconds() if hasattr(d, "total_seconds") else d / 1e9
    return max(0.0, s / 60.0)


def _ns_spans(spans):
    return [(a.value, b.value) for a, b in spans or []]


def day_places(day, line, sightings=(), exits=(), machines=None):
    """An employee's day as places, by the rules above.

    line       the passes at their desk: [(start, end, kind, ...)] --
               progress_data.timeline's ("desk" / "away") or day_activity's
               (computer, phone, talking, desk = at the desk)
    sightings  [{"t", "room", "kind", "how", "src", "camera"}]
               (sightings_for; src: cctv, listed, named)
    exits      [Timestamp]: named at the gate on the way out (exits_for)
    machines   machines_for(): first_in, last_out, inside, outings,
               campus, ins (the laptop's clock), or None

    Returns {"day", "span", "segments": [(start, end, kind, name, how)],
    "totals": {kind: minutes} (every kind), "by_place": {room: minutes},
    "away_min" (the day not at the desk), "seen_min" (of it, placed by a
    sighting), "conflicts": {"desk", "outing"} (sightings not used),
    "unsure": [sources not used that day], "cameras": {"recorder:channel":
    [sightings used, minutes placed]}}."""
    m = machines or {}
    runs = _runs(line)
    sightings = sorted(sightings or [], key=lambda g: g["t"])
    span = _span(day, runs, m, [g["t"].value for g in sightings
                                if g["kind"] not in OUTSIDE_KINDS])
    result = {"day": day, "span": None, "segments": [],
              "totals": {k: 0.0 for k in KINDS}, "by_place": {},
              "away_min": 0.0, "seen_min": 0.0,
              "conflicts": {"desk": 0, "outing": 0}, "unsure": [],
              "cameras": {}}
    if span is None:
        return result
    lo, hi = span
    runs = [(max(s, lo), min(e, hi), d) for s, e, d in runs
            if min(e, hi) > max(s, lo)]
    desk = [(s, e) for s, e, d in runs if d]
    away = [(s, e) for s, e, d in runs if not d]
    holes = _between(lo, hi, [(s, e) for s, e, _ in runs])
    stretches = _between(lo, hi, desk)        # away and unwatched alike
    claims = [_claim(s, e, _DESK, "desk", "", "desk") for s, e in desk]
    claims += [_claim(s, e, _NONE, "unknown", "", "none") for s, e in away]
    claims += [_claim(s, e, _NONE, "unknown", "", "unwatched")
               for s, e in holes]
    outings = _cut(_ns_spans(m.get("outings")), lo, hi)
    claims += [_claim(a, b, _OUTING, "out", "", "machines")
               for a, b in outings]
    # at the other campus by its machines (141-D's punches): out of 140-H
    for a, b, where in m.get("campus") or []:
        for s, e in _cut([(a.value, b.value)], lo, hi):
            claims.append(_claim(s, e, _OUTING, "out", where, "machines"))
            outings.append((s, e))
    # rule 6: inside by the machines, while away and watched
    for a, b in _cut(_ns_spans(m.get("inside")), lo, hi):
        for s, e in _cut(away, a, b):
            claims.append(_claim(s, e, _INSIDE, "inside", "", "machines"))

    def at_desk(t):
        return any(s <= t < e for s, e in desk)
    # rule 3: a source that keeps finding them while they sit is not used
    marks = [(g["t"].value, g.get("src", "cctv"), g) for g in sightings]
    marks += [(x.value, "gate", None) for x in sorted(exits or [])]
    per, conflicts = {}, {"desk": 0, "outing": 0}
    for t, src, _ in marks:
        if lo <= t <= hi:
            n = per.setdefault(src, [0, 0])
            n[0] += 1
            if at_desk(t):
                n[1] += 1
                conflicts["desk"] += 1
    unsure = sorted(src for src, (n, k) in per.items()
                    if src != "named"          # a person's own word stands
                    and k >= UNSURE_LEAST and k >= UNSURE_SHARE * n)
    groups = {}
    for t, src, g in marks:
        if g is None or src in unsure or not lo <= t <= hi or at_desk(t):
            continue
        st = next((x for x in stretches if x[0] <= t <= x[1]), None)
        if st is None:
            continue
        if g["kind"] not in OUTSIDE_KINDS and any(a <= t <= b
                                                  for a, b in outings):
            conflicts["outing"] += 1
            continue
        groups.setdefault((st, g["kind"], g["room"]), []).append((t, g))
    half, join = SIGHT_HALF.value, SIGHT_JOIN.value
    for (st, kind, room), gs in groups.items():
        stay = [gs[0]]
        for item in gs[1:] + [None]:
            if item is not None and item[0] - stay[-1][0] <= join:
                stay.append(item)
                continue
            t0, tn = stay[0][0], stay[-1][0]
            how = "face" if any(g["how"] == "face" for _, g in stay) \
                else "seen"
            claims.append(_claim(
                max(t0 - half, st[0]), min(tn + half, st[1]),
                _SEEN_OUTSIDE if kind in OUTSIDE_KINDS else _SEEN, kind,
                room, how, (t0, tn), [g.get("camera", "") for _, g in stay]))
            stay = [item] if item is not None else []
    # rule 5: out through the gate, until seen inside, the desk, or an IN
    if "gate" not in unsure:
        inside_seen = [t for t, src, g in marks if g is not None
                       and src not in unsure
                       and g["kind"] not in OUTSIDE_KINDS]
        ins = sorted(t.value for t in m.get("ins") or [])
        for x, src, g in marks:
            if g is not None or not lo <= x <= hi or at_desk(x):
                continue
            st = next((y for y in stretches if y[0] <= x <= y[1]), None)
            if st is None:
                continue
            end = min([st[1]] + [t for t in inside_seen if t > x]
                      + [t for t in ins if t > x])
            if end > x:
                claims.append(_claim(x, end, _GATE, "out", "", "gate"))
    pieces = _absorb(_resolve(claims, lo, hi), MIN_SEG.value)
    segs = []
    for a, b, c in pieces:
        if segs and segs[-1][1] == a and (segs[-1][2], segs[-1][3],
                                          segs[-1][4]) == (
                c["kind"], c["name"], c["how"]):
            segs[-1][1] = b
        else:
            segs.append([a, b, c["kind"], c["name"], c["how"]])
    totals = {k: 0.0 for k in KINDS}
    by_place = {}
    for a, b, kind, name, how in segs:
        totals[kind] += _minutes(a, b)
        if name:
            by_place[name] = by_place.get(name, 0.0) + _minutes(a, b)
    cams = {}
    for a, b, c in pieces:
        if c["how"] in ("face", "seen") and c["cams"]:
            share = _minutes(a, b) / len(c["cams"])
            for cam in c["cams"]:
                cams.setdefault(cam, [0, 0.0])[1] += share
    for c in claims:
        for cam in c["cams"]:
            if cam in cams:
                cams[cam][0] += 1

    def ts(x):                                   # to the second, as ns
        return pd.Timestamp(x - x % 1000000000)
    result.update(
        span=(ts(lo), ts(hi)),
        segments=[(ts(a), ts(b), k, n, h) for a, b, k, n, h in segs],
        totals=totals, by_place=by_place,
        away_min=sum(v for k, v in totals.items() if k != "desk"),
        seen_min=sum(_minutes(a, b) for a, b, _, _, h in segs
                     if h in ("face", "seen")),
        conflicts=conflicts, unsure=unsure, cameras=cams)
    return result


# ----------------------------------------------------- what is recorded

_files = {}
_FILES_KEPT = 48
# A file's stamp is looked at again at most this often: a build reads the
# same few files for every person in a few seconds (Windows' stat is slow).
RECHECK = 3.0
_stamps = {}


def _stamp(path):
    """os.path.getmtime(path), or None -- asked of the disk at most every
    RECHECK seconds."""
    now = time.monotonic()
    hit = _stamps.get(path)
    if hit is not None and now - hit[1] < RECHECK:
        return hit[0]
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    if len(_stamps) > 512:
        _stamps.clear()
    _stamps[path] = (stamp, now)
    return stamp


def forget():
    """Drop every file, export and plan read so far (tests; a new day)."""
    _files.clear()
    _stamps.clear()
    _kinds.clear()
    _machines.update(data=None, index={}, offsets={}, last=None,
                     loaded=None, loaded_at=None)
    _rooms.update(stamp=None, cams={})


def _entry(path):
    """{"df", "idx"} of a CSV as text columns, read again only when it
    changes; None when it is missing or will not read."""
    stamp = _stamp(path)
    if stamp is None:
        return None
    hit = _files.get(path)
    if hit is not None and hit["stamp"] == stamp:
        return hit
    try:
        d = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, ValueError, pd.errors.ParserError):
        return None
    if len(_files) >= _FILES_KEPT:
        _files.pop(next(iter(_files)))
    hit = {"stamp": stamp, "df": d, "idx": {}}
    _files[path] = hit
    return hit


def _indexed(path, name, make):
    """make(frame) -> {key: [rows]} for a CSV, made once per change of it;
    {} when it is missing, will not read or has not the columns."""
    hit = _entry(path)
    if hit is None:
        return {}
    if name not in hit["idx"]:
        try:
            hit["idx"][name] = make(hit["df"])
        except (KeyError, ValueError, TypeError):
            hit["idx"][name] = {}
    return hit["idx"][name]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _cctv_rows(d):
    """people/sightings: {employee_id: [(time, room, recorder, channel,
    score, margin)]}."""
    out = {}
    for row in zip(d["employee_id"], d["time"], d["room"], d["recorder"],
                   d["channel"], d["score"], d["margin"]):
        out.setdefault(row[0], []).append(
            row[1:5] + (_num(row[5]), _num(row[6])))
    return out


def _listed_rows(d):
    """progress/<day>.csv: {code: [(time, state, room, recorder, channel,
    score)]} of the sightings (kind "seen")."""
    d = d[d["kind"] == "seen"]
    out = {}
    for row in zip(d["code"], d["time"], d["state"], d["room"],
                   d["recorder"], d["channel"], d["score"]):
        out.setdefault(row[0], []).append(row[1:6] + (_num(row[6]),))
    return out


def _named_rows(d):
    """people/sighting_names.csv: {(day, employee_id): [(time, room,
    recorder, channel)]}."""
    out = {}
    for row in zip(d["day"], d["employee_id"], d["time"], d["room"],
                   d["recorder"], d["channel"]):
        out.setdefault((row[0], row[1]), []).append(row[2:])
    return out


def _gate_rows(d):
    """people/entrance: {employee_id: [time]} of the named passages."""
    d = d[d["status"] == "named"]
    out = {}
    for eid, t in zip(d["employee_id"], d["time"]):
        out.setdefault(eid, []).append(t)
    return out


def _at(day, hms):
    hms = str(hms or "").strip()
    if not hms:
        return None
    try:
        return pd.Timestamp("%s %s" % (day, hms))
    except (ValueError, TypeError):
        return None


_kinds = {}


def _sighting(day, hms, room, recorder, channel, how, src, cams, own, plan):
    t = _at(day, hms)
    if t is None:
        return None
    try:
        ch = int(float(channel))
    except (TypeError, ValueError):
        ch = None
    room = str((cams or {}).get((recorder, ch), room) or room)
    key = (room, own, id(plan))
    if key not in _kinds:
        if len(_kinds) > 4096:
            _kinds.clear()
        _kinds[key] = kind_of(room, own, plan)
    return {"t": t, "room": room, "kind": _kinds[key], "how": how,
            "src": src, "camera": "%s:%s" % (recorder, ch)}


def sightings_for(code, day, employee_id="", cams=None, plan=None, own=None,
                  reviews=None, least=None, margin=None, possible=False):
    """[{"t", "room", "kind", "how", "src", "camera"}], oldest first: where
    the employee was seen off the desk that day --

      * src "cctv": a face on the campus cameras (people/sightings,
        cctv_faces), at least `least` and clear of the next person by
        `margin` (progress_data.CCTV_MIN, CCTV_MARGIN);
      * src "listed": their own rows (progress/<day>.csv, the listed
        employees): a face counts unless somebody said no on the tab; a
        body match only once somebody said yes (and at progress_data.
        SEEN_MIN) -- every "possible" with `possible` (for measuring only);
      * src "named": a sighting's picture a person said is them (people/
        sighting_names.csv).
    cams: {(recorder, channel): room} (building.cameras) names the room."""
    least = pdx.CCTV_MIN if least is None else least
    margin = pdx.CCTV_MARGIN if margin is None else margin
    eid = str(employee_id or "")
    out = []

    def add(hms, room, recorder, channel, how, src):
        g = _sighting(day, hms, room, recorder, channel, how, src, cams,
                      own, plan)
        if g is not None:
            out.append(g)
    if eid:
        rows = _indexed(os.path.join(SIGHTINGS, day + ".csv"), "cctv",
                        _cctv_rows).get(eid) or []
        for hms, room, rec, ch, score, mg in rows:
            if score >= least and mg >= margin:
                add(hms, room, rec, ch, "face", "cctv")
    if code:
        rows = _indexed(os.path.join(ACTIVITY, day + ".csv"), "listed",
                        _listed_rows).get(str(code)) or []
        said = None
        for hms, state, room, rec, ch, score in rows:
            if said is None:
                said = pdx.load_reviews(day) if reviews is None else reviews
            verdict = said.get((hms, str(code), room), "")
            if verdict == "no":
                continue
            if state == "face":
                add(hms, room, rec, ch, "face", "listed")
            elif score >= pdx.SEEN_MIN and (verdict == "yes" or possible):
                add(hms, room, rec, ch, "seen", "listed")
    if eid:
        for hms, room, rec, ch in _indexed(NAMED, "named", _named_rows).get(
                (day, eid)) or []:
            add(hms, room, rec, ch, "seen", "named")
    return sorted(out, key=lambda g: g["t"])


def exits_for(employee_id, day):
    """[Timestamp]: the gate (entrance_watch, Entry H) named them on the way
    out that day, oldest first."""
    eid = str(employee_id or "")
    if not eid:
        return []
    times = _indexed(os.path.join(GATE, day + ".csv"), "gate",
                     _gate_rows).get(eid) or []
    return sorted(t for t in (_at(day, x) for x in times) if t is not None)


_machines = {"data": None, "index": {}, "offsets": {}, "last": None,
             "loaded": None, "loaded_at": None}


def _export():
    """attendance.load() -- asked at most every RECHECK seconds (it looks
    for new export files on every call)."""
    now = time.monotonic()
    at = _machines["loaded_at"]
    if at is not None and now - at < RECHECK:
        return _machines["loaded"]
    import attendance
    data = attendance.load()
    _machines.update(loaded=data, loaded_at=now)
    return data


def _index(data):
    """{(employee code, machine day): [(at, kind, place)]}, oldest first --
    made once per export."""
    if _machines["data"] is not data:
        days = data["at"].dt.strftime("%Y-%m-%d")
        idx = {}
        for eid, d, at, kind, place in zip(data["eid"], days, data["at"],
                                           data["kind"], data["place"]):
            idx.setdefault((eid, d), []).append((at, kind, str(place)))
        for v in idx.values():
            v.sort(key=lambda r: r[0])
        _machines.update(data=data, index=idx, offsets={},
                         last=data["at"].max())
    return _machines["index"]


def _offset(day, data):
    """attendance.clock_offset(day) in seconds (laptop minus machines), or
    0 where it cannot be measured; once per day and gate file."""
    key = (day, _stamp(os.path.join(GATE, day + ".csv")))
    if key not in _machines["offsets"]:
        try:
            import attendance
            off = attendance.clock_offset(day, data=data)
        except Exception:                                   # noqa: BLE001
            off = None
        _machines["offsets"][key] = float(off or 0.0)
    return _machines["offsets"][key]


def punch_day(rows, campus, blip, midnight):
    """attendance.day's and attendance.inside's reading of one day's
    punches [(at, kind, place)], oldest first, on a plain list (the same
    rules, checked against them in test_places): (first_in, last_out,
    inside [(in, out)], outings [(out, back)])."""
    here = [(t, k) for t, k, p in rows if str(p).startswith(campus)]
    ins = [t for t, k in here if k == "in"]
    outs = [t for t, k in here if k == "out"]
    first_in = ins[0] if ins else None
    last_out = outs[-1] if outs and (not ins or outs[-1] > ins[0]) else None
    inside, outings, t_in, out_at = [], [], None, None
    for t, k in here:
        if k == "in":
            if out_at is not None and t - out_at > blip:
                outings.append((out_at, t))
            out_at = None
            if t_in is None:
                t_in = t
        else:
            if t_in is not None:
                inside.append((t_in, t))
                t_in = None
            out_at = t
    if t_in is not None:
        inside.append((t_in, midnight))
    return first_in, last_out, inside, outings


def _other_campus(rows, campus):
    """[(first punch, back, place)]: runs of punches at another campus's
    machines (141-D's) with none at `campus` between -- from the run's first
    punch to the next punch at `campus` (or the run's last)."""
    out, cur = [], None
    for at, _, place in rows:
        if not str(place).startswith(campus):
            if cur is None:
                cur = [at, at, str(place).split(" ")[0]]
            else:
                cur[1] = at
        elif cur is not None:
            cur[1] = at
            out.append(tuple(cur))
            cur = None
    if cur is not None:
        out.append(tuple(cur))
    return [v for v in out if v[1] > v[0]]


def machines_for(employee_id, day, data=None):
    """What the attendance machines say of the employee's day at 140-H, on
    the laptop's clock: {"first_in", "last_out", "inside": [(in, out)],
    "outings": [(out, back)], "campus": [(from, to, "141-D")] (at the
    other campus's machines), "ins": [IN punches], "known_until",
    "offset_s"} -- None with no employee ID, no export, no punch that day,
    or anything wrong (the page never stops for it). Punches before
    MACHINE_FROM are the night's and left out; inside is cut where they
    punched at the other campus, and at the export's last punch: after it
    the machines say nothing."""
    eid = str(employee_id or "")
    if not eid:
        return None
    try:
        import attendance
        data = _export() if data is None else data
        if data is None or not len(data):
            return None
        start = pd.Timestamp(day) + pd.Timedelta(hours=MACHINE_FROM)
        rows = [r for r in _index(data).get((attendance.code(eid), day))
                or [] if r[0] >= start]
        if not rows:
            return None
        end = pd.Timestamp(day) + pd.Timedelta(days=1)
        first_in, last_out, inside, outings = punch_day(
            rows, attendance.CAMPUS, attendance.BLIP, end)
        if first_in is None and last_out is None:
            return None
        shift = pd.Timedelta(seconds=_offset(day, data))
        last = _machines["last"]
        known = (end if last >= end else last) + shift
        away = [(a + shift, b + shift, where) for a, b, where
                in _other_campus(rows, attendance.CAMPUS)]
        cut = []
        for a, b in inside:
            a, b = a + shift, min(b + shift, known)
            if b > a:
                cut += _between(a, b, [(s, e) for s, e, _ in away])
        return {"first_in": None if first_in is None else first_in + shift,
                "last_out": None if last_out is None else last_out + shift,
                "inside": cut,
                "outings": [(a + shift, b + shift) for a, b in outings],
                "campus": away,
                "ins": [t + shift for t, k, p in rows if k == "in"
                        and str(p).startswith(attendance.CAMPUS)],
                "known_until": known,
                "offset_s": shift.total_seconds()}
    except Exception:                                       # noqa: BLE001
        return None


def _plan():
    try:
        import building
        return building.load() or {}
    except Exception:                                       # noqa: BLE001
        return {}


_rooms = {"stamp": None, "cams": {}}


def _cams(path="rooms.yaml"):
    """{(recorder, channel): room} (building.cameras), read again only when
    rooms.yaml changes."""
    stamp = _stamp(path)
    if stamp is None:
        return {}
    if _rooms["stamp"] != stamp:
        try:
            import building
            _rooms.update(stamp=stamp, cams=building.cameras(path))
        except Exception:                                   # noqa: BLE001
            return {}
    return _rooms["cams"]


def for_person(person, day, employee_id=None, notes=None, passes=None,
               line=None, cams=None, plan=None, machines=True, **seen):
    """One board person's day as places (day_places), the inputs gathered
    from this laptop's files: the passes at their desk (`line`, else
    progress_data.timeline over notes and passes), their sightings, the
    gate, the machines. None before the desk's `since` (the camera looked
    elsewhere). `seen` goes to sightings_for (least, margin, possible --
    for measuring)."""
    since = str(person.get("since") or "")
    if since and day < since:
        return None
    if line is None:
        n = pdx.notes(day) if notes is None else notes
        p = pdx.passes(day) if passes is None else passes
        line = pdx.timeline(person, n, p)
    eid = str(employee_id or person.get("employee_id") or "")
    own = person.get("department")
    cams = _cams() if cams is None else cams
    plan = _plan() if plan is None else plan
    sightings = sightings_for(person.get("code"), day, eid, cams, plan, own,
                              **seen)
    exits = [] if own in pdx.GATE_BLIND else exits_for(eid, day)
    return day_places(day, line, sightings, exits,
                      machines_for(eid, day) if machines else None)


def _round(totals):
    return {k: round(float(totals.get(k) or 0.0), 1) for k in KINDS}


def board(person, employee_id, days, focus, cache=None, cams=None,
          lines=None):
    """For progress_data.build, one board person: (places, places_days) --
    places {"day": focus, "segments": [(start, end, kind, name)],
    "totals": {kind: minutes}} (None when the focus day has none),
    places_days {day: {kind: minutes}} over `days` and the focus day.
    Codes, rooms and minutes: never a name, an ID or a picture. cache:
    build()'s {day: (notes, passes)}; lines: {day: the desk's timeline},
    where build() has it already (week()'s summaries)."""
    cache = {} if cache is None else cache
    lines = lines or {}
    cams = _cams() if cams is None else cams
    plan = _plan()
    places, per_day = None, {}
    for day in sorted(set(days or []) | {focus}):
        line = lines.get(day)
        if line is None:
            if day not in cache:
                cache[day] = (pdx.notes(day), pdx.passes(day))
            n, p = cache[day]
            line = pdx.timeline(person, n, p)
        r = for_person(person, day, employee_id, line=line, cams=cams,
                       plan=plan)
        if r is None or r["span"] is None:
            continue
        per_day[day] = _round(r["totals"])
        if day == focus:
            segs = []
            for a, b, kind, name, _ in r["segments"]:
                if segs and segs[-1][1] == a and segs[-1][2:] == [kind, name]:
                    segs[-1][1] = b
                else:
                    segs.append([a, b, kind, name])
            places = {"day": day, "segments": [tuple(s) for s in segs],
                      "totals": per_day[day]}
    return places, per_day


# ------------------------------------------------------------- the words

def _h(minutes):
    return "%.1f h" % (float(minutes or 0.0) / 60.0)


def overview(totals, least=3.0):
    """"8.1 h in the building: 5.2 h at the desk, 0.9 h meeting rooms, 0.6 h
    cafe, 1.4 h elsewhere in the building; 0.4 h out" -- in the building is
    every kind but out and unknown; a kind under `least` minutes is left
    out of the words, not of the sums."""
    t = totals or {}
    inside = ("desk", "meeting", "cafe", "smoking", "prayer", "inside")
    total = sum(float(t.get(k) or 0.0) for k in inside)
    parts = ["%s %s" % (_h(t.get(k)), SHORT[k]) for k in inside
             if float(t.get(k) or 0.0) >= least]
    text = "%s in the building" % _h(total)
    if parts:
        text += ": " + ", ".join(parts)
    rest = ["%s %s" % (_h(t.get(k)), SHORT[k]) for k in ("out", "unknown")
            if float(t.get(k) or 0.0) >= least]
    return text + ("; " + ", ".join(rest) if rest else "")


def describe(segment):
    """"from 13:05 to 13:40 in the cafe (Prompt Cafe)"."""
    a, b, kind, name = segment[:4]
    where = LABEL.get(kind, kind)
    if name:
        where = "in %s" % name if kind == "inside" else "%s (%s)" % (where,
                                                                     name)
    return "from %s to %s %s" % (pd.Timestamp(a).strftime("%H:%M"),
                                 pd.Timestamp(b).strftime("%H:%M"), where)


# ---------------------------------------------------------- how much is known

def named_people(cfg=None):
    """[(person, employee_id)]: the board's people who have an employee ID
    -- progress.yaml's, and the desks named on the tab -- the way
    progress_data.build finds them. This laptop only."""
    cfg = pdx.load() if cfg is None else cfg
    hand, seats, rooms, roster = {}, {}, {}, {}
    try:
        import desks_data
        hand = desks_data.load_desk_names()
        dd = desks_data.load() if hand else pd.DataFrame()
        for c, g in (dd.groupby("code") if len(dd) else []):
            seats[c] = (g["recorder"].iloc[0], int(g["channel"].iloc[0]),
                        float(g["x"].iloc[0]), float(g["y"].iloc[0]))
            rooms[c] = str(g["room"].iloc[0])
        roster = {r["employee_id"]: r for r in desks_data.load_roster()}
    except Exception:                                       # noqa: BLE001
        pass
    everyone = list(cfg.get("people") or [])
    if cfg.get("auto_desks", True):
        everyone += pdx.desk_people(everyone, hand, seats, rooms, roster,
                                    pdx.by_attendance())
    out = []
    for p in everyone:
        eid = str(p.get("employee_id") or "")
        if not eid:
            for code, (e, _) in hand.items():
                s = seats.get(code)
                if s and (s[0], s[1]) == (p.get("recorder"),
                                          int(p.get("channel") or 0)):
                    px, py = (float(v) for v in p.get("seat") or (0, 0))
                    if (s[2] - px) ** 2 + (s[3] - py) ** 2 <= 60.0 ** 2:
                        eid = str(e)
                        break
        if eid:
            out.append((p, eid))
    return out


def coverage(days, people=None, **seen):
    """How much of the time away from the desk gets a place, over `days`,
    for the named people (minutes): {"people", "days_in", "span", "desk",
    "away", "seen", "people_seen", "kinds": {kind: min}, "how": {how:
    min} (away only), "cameras": {camera: [sightings, minutes]},
    "conflicts", "unsure": person-days with a source set aside}."""
    people = named_people() if people is None else people
    cams, plan = _cams(), _plan()
    tot = {"people": len(people), "days_in": 0, "span": 0.0, "desk": 0.0,
           "away": 0.0, "seen": 0.0, "kinds": {k: 0.0 for k in KINDS},
           "how": {}, "cameras": {}, "conflicts": {"desk": 0, "outing": 0},
           "people_seen": 0, "unsure": 0}
    for day in days:
        n, p = pdx.notes(day), pdx.passes(day)
        for person, eid in people:
            r = for_person(person, day, eid, n, p, cams=cams, plan=plan,
                           **seen)
            if r is None or r["span"] is None:
                continue
            tot["days_in"] += 1
            tot["span"] += _minutes(*r["span"])
            tot["desk"] += r["totals"]["desk"]
            tot["away"] += r["away_min"]
            tot["seen"] += r["seen_min"]
            tot["people_seen"] += 1 if r["seen_min"] > 0 else 0
            tot["unsure"] += 1 if r["unsure"] else 0
            for k in KINDS:
                tot["kinds"][k] += r["totals"][k]
            for a, b, kind, _, how in r["segments"]:
                if kind != "desk":
                    tot["how"][how] = tot["how"].get(how, 0.0) + \
                        _minutes(a, b)
            for cam, (k, mins) in r["cameras"].items():
                c = tot["cameras"].setdefault(cam, [0, 0.0])
                c[0] += k
                c[1] += mins
            for k, v in r["conflicts"].items():
                tot["conflicts"][k] += v
    return tot


def _print_coverage(days):
    t = coverage(days)
    away = t["away"] or 1.0
    print("%d named people, %d person-days in, %s: %.0f h from first in to "
          "last out, %.0f h at the desk, %.0f h away from it"
          % (t["people"], t["days_in"], ", ".join(days), t["span"] / 60,
             t["desk"] / 60, t["away"] / 60))
    print("away from the desk, by kind:")
    for k in KINDS[1:]:
        print("  %-8s %6.1f h  %4.1f%%" % (k, t["kinds"][k] / 60,
                                          100 * t["kinds"][k] / away))
    print("away from the desk, by what placed it:")
    for how, v in sorted(t["how"].items(), key=lambda kv: -kv[1]):
        print("  %-10s %6.1f h  %4.1f%%" % (how, v / 60, 100 * v / away))
    print("a place seen by a camera: %.1f%% of the time away (%d of the "
          "person-days have one)" % (100 * t["seen"] / away,
                                     t["people_seen"]))
    print("cameras, by minutes placed:")
    for cam, (k, v) in sorted(t["cameras"].items(), key=lambda kv: -kv[1][1]):
        print("  %-10s %3d sightings  %6.1f min" % (cam, k, v))
    print("sightings not used: %(desk)d while at the desk, %(outing)d inside "
          "during an outing" % t["conflicts"]
          + "; %d person-days with a source set aside" % t["unsure"])


if __name__ == "__main__":
    _print_coverage(sys.argv[1:] or [pd.Timestamp.now().strftime("%Y-%m-%d")])
