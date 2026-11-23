"""Time at the desk, employee by employee, from the loop's seat notes.

Shamroze, 23 Nov: "employee productivity -- 4-5 people, how much of the day
at the computer, in meetings, in the cafeteria..." (HR approved monitoring
a handful of people). This is the first, honest part of it: a desk the
loop sees somebody at, pass by pass, and what that adds up to in a day.

What it knows and what it does not:

  * the loop notes every counted person's place in the picture
    (seats/<date>.csv, room_loop.note_seats). A note within a desk's reach
    in a pass is "at the desk" for that pass; no note is "away";
  * a pass the loop never made (the laptop asleep, the loop stopped) is
    "not watched" -- never "away";
  * one pass alone without a note, between two with one, is the detector
    missing a sitter for a moment (a head down, an arm across), not a
    break: it is counted at the desk. Two or more in a row are away;
  * each employee is followed at their own desk (Shamroze, 23 Nov:
    "particular employees, not departments"); the camera sees the desk,
    not a face, so a colleague sitting there would be counted too -- the
    frames checked by eye are what say it is the same person. It cannot
    yet say where somebody went when away -- that needs the same person
    found on the other cameras, the next stage.

Which employee, at which desk, under which code lives in progress.yaml --
on this machine only (git-ignored); a name, if one is ever given, stays
there and on the password-protected page. The results are worked out
when asked for and never written anywhere.

No Streamlit and no database here: notes and passes in, figures out.
"""
import os
from datetime import datetime

import pandas as pd
import yaml

CONFIG = "progress.yaml"
SEATS = "seats"
CYCLES = "cycles.csv"

# A note is at a desk when its box's bottom is this close to the desk's
# point: a share of the frame's width, or of the person's own box height
# where that is more (seat_map's rule, 13 Nov -- near a camera a sitter is
# big and the bottom of the box wanders with them).
SEAT_RADIUS = 0.035
SEAT_REACH = 0.3

# The day's span for first-in and last-out: a note before this is the
# night's or the cleaners' early round (a guard, a cleaner; Who comes when
# leaves those rounds out too), not the start of somebody's day. 23 Nov:
# from 7, one desk had "in" before 08:00 and then nobody for three hours.
DAY_FROM = 8

# An away stretch at least this long is a break worth listing.
BREAK_MIN = 15

# A pass longer than this is the laptop asleep in the middle of it (17 Nov
# 19:56 to 18 Nov 10:33 is one "pass" in cycles.csv), not a look at the
# desk: it is left out, unwatched. room_loop.stale_pass draws the same line.
MAX_PASS_MIN = 30


def load(path=CONFIG):
    """progress.yaml: {"people": [...], "stages": [...], ...}; {} if none."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as fh:    # a BOM from PowerShell
        return yaml.safe_load(fh) or {}


def passes(day, path=CYCLES):
    """The loop's passes on `day` (YYYY-MM-DD): a frame of start, end."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=["start", "end"])
    c = pd.read_csv(path)
    end = pd.to_datetime(c["time"])
    keep = end.dt.strftime("%Y-%m-%d") == day
    out = pd.DataFrame({"end": end[keep]})
    out["start"] = out["end"] - pd.to_timedelta(
        c.loc[keep, "seconds"].astype(float), unit="s")
    out = out[(out["end"] - out["start"])
              <= pd.Timedelta(minutes=MAX_PASS_MIN)]
    return out.sort_values("end").reset_index(drop=True)[["start", "end"]]


def notes(day, folder=SEATS):
    """The day's seat notes, with a timestamp column `at`."""
    path = os.path.join(folder, "%s.csv" % day)
    if not os.path.exists(path):
        return pd.DataFrame()
    d = pd.read_csv(path)
    d["at"] = pd.to_datetime(day + " " + d["time"])
    return d


def reach(person, cam_notes):
    """How far from the desk's point a note may be, in the camera's pixels."""
    if person.get("reach"):
        return float(person["reach"])
    width = float(cam_notes["frame_w"].iloc[0]) if len(cam_notes) else 1920.0
    height = float(cam_notes["h"].median()) if len(cam_notes) else 0.0
    return max(SEAT_RADIUS * width, SEAT_REACH * height)


def at_desk(person, day_notes):
    """The times of the notes that fall on this person's desk."""
    if day_notes is None or day_notes.empty:
        return []
    cam = day_notes[(day_notes["recorder"] == person["recorder"])
                    & (day_notes["channel"] == int(person["channel"]))]
    if cam.empty:
        return []
    x, y = (float(v) for v in person["seat"])
    r = reach(person, cam)
    bottom = cam["cy"] + cam["h"] / 2.0
    hit = ((cam["cx"] - x) ** 2 + (bottom - y) ** 2) <= r * r
    return sorted(cam.loc[hit, "at"])


def timeline(person, day_notes, day_passes):
    """Pass by pass: [(start, end, "desk" | "away")], one-pass blips gone.

    A pass is "desk" when a note on the desk falls inside it. A single
    "away" pass with "desk" on both sides is the detector blinking, and is
    "desk". Then the reverse: a single "desk" pass with "away" on both
    sides is somebody passing, or a chair as the light changes at dawn (19
    Nov 07:01, a "first in" nobody made), and is "away" -- a sitter stays
    longer than one pass. Passes the loop never made are not in the
    list."""
    if day_passes is None or day_passes.empty:
        return []
    hits = at_desk(person, day_notes)
    out = []
    i = 0
    for start, end in zip(day_passes["start"], day_passes["end"]):
        while i < len(hits) and hits[i] <= start:
            i += 1
        seen = i < len(hits) and hits[i] <= end
        out.append([start, end, "desk" if seen else "away"])
    for k in range(1, len(out) - 1):
        if (out[k][2] == "away" and out[k - 1][2] == "desk"
                and out[k + 1][2] == "desk"):
            out[k][2] = "desk"
    for k in range(len(out)):
        before = out[k - 1][2] if k > 0 else "away"
        after = out[k + 1][2] if k + 1 < len(out) else "away"
        if out[k][2] == "desk" and before == "away" and after == "away":
            out[k][2] = "blip"
    for p in out:
        if p[2] == "blip":
            p[2] = "away"
    return [tuple(p) for p in out]


def _minutes(a, b):
    return max(0.0, (b - a).total_seconds() / 60.0)


def _clip(start, end, lo, hi):
    a, b = max(start, lo), min(end, hi)
    return _minutes(a, b) if b > a else 0.0


def day_summary(person, day, day_notes=None, day_passes=None,
                hours=(10, 20)):
    """One desk's day: the figures the Progress page shows.

    watched_min   minutes of office hours the loop was watching
    desk_min      of those, minutes at the desk
    share         desk_min / watched_min (None when nothing was watched)
    first, last   first and last pass at the desk from DAY_FROM on
    in_min        minutes from first to last (the day it kept)
    breaks        away stretches of BREAK_MIN+ between first and last,
                  [(start, end, minutes)], longest first
    late_min      minutes at the desk after office hours
    total_min     minutes at the desk from DAY_FROM to midnight
    """
    day_notes = notes(day) if day_notes is None else day_notes
    day_passes = passes(day) if day_passes is None else day_passes
    line = timeline(person, day_notes, day_passes)
    base = pd.Timestamp(day)
    lo, hi = base + pd.Timedelta(hours=hours[0]), \
        base + pd.Timedelta(hours=hours[1])
    start_of_day = base + pd.Timedelta(hours=DAY_FROM)
    watched = sum(_clip(s, e, lo, hi) for s, e, _ in line)
    desk = sum(_clip(s, e, lo, hi) for s, e, st in line if st == "desk")
    late = sum(_clip(s, e, hi, base + pd.Timedelta(days=1))
               for s, e, st in line if st == "desk")
    total = sum(_clip(s, e, start_of_day, base + pd.Timedelta(days=1))
                for s, e, st in line if st == "desk")
    at = [p for p in line if p[2] == "desk" and p[1] > start_of_day]
    first = at[0][0] if at else None
    last = at[-1][1] if at else None
    breaks = []
    if at:
        run = None
        for s, e, st in line:
            if s < first or e > last:
                continue
            if st == "away":
                run = [run[0] if run else s, e]
            elif run:
                breaks.append((run[0], run[1], _minutes(run[0], run[1])))
                run = None
        breaks = sorted([b for b in breaks if b[2] >= BREAK_MIN],
                        key=lambda b: -b[2])
    return {"day": day, "watched_min": watched, "desk_min": desk,
            "share": (desk / watched) if watched > 0 else None,
            "first": first, "last": last,
            "in_min": _minutes(first, last) if at else 0.0,
            "breaks": breaks, "late_min": late, "total_min": total,
            "line": line}


def strip(summary, frm=8, to=24, step=10):
    """The day in `step`-minute slots from `frm` to `to` o'clock:
    "desk", "away" (between first in and last out), "out" (before or
    after), or "unwatched"."""
    base = pd.Timestamp(summary["day"])
    line = summary["line"]
    slots = []
    t = base + pd.Timedelta(hours=frm)
    end = base + pd.Timedelta(hours=to)
    width = pd.Timedelta(minutes=step)
    while t < end:
        u = t + width
        here = [p for p in line if p[0] < u and p[1] > t]
        if not here:
            slots.append("unwatched")
        elif any(p[2] == "desk" for p in here):
            slots.append("desk")
        elif summary["first"] is not None and summary["first"] <= t \
                and u <= summary["last"]:
            slots.append("away")
        else:
            slots.append("out")
        t = u
    return slots


def working_days(upto, count=5, folder=SEATS, skip=(5, 6)):
    """The last `count` days (Mon-Fri) up to and including `upto` that have
    seat notes, newest last."""
    have = sorted(f[:-4] for f in os.listdir(folder)
                  if f.endswith(".csv")) if os.path.isdir(folder) else []
    days = [d for d in have if d <= upto
            and datetime.strptime(d, "%Y-%m-%d").weekday() not in skip]
    return days[-count:]


def week(person, days, hours=(10, 20), cache=None):
    """day_summary over `days`. `cache` ({day: (notes, passes)}) shares the
    reading of each day's files between people."""
    cache = {} if cache is None else cache
    since = str(person.get("since") or "")
    out = []
    for day in days:
        if since and day < since:
            # The camera pointed elsewhere before `since` (the camera team
            # re-aimed several on 19 Nov): the desk's pixels meant another
            # place.
            empty = pd.DataFrame(columns=["start", "end"])
            s = day_summary(person, day, pd.DataFrame(), empty, hours)
            s["before"] = True
            out.append(s)
            continue
        if day not in cache:
            cache[day] = (notes(day), passes(day))
        n, p = cache[day]
        out.append(day_summary(person, day, n, p, hours))
    return out


def build(cfg, today, hours=(10, 20), count=5, folder=SEATS, frm=8, to=24):
    """Everything the Progress page draws, desk by desk: the last `count`
    working days up to `today` (YYYY-MM-DD), each day's summary and slots,
    and a usual day over the whole ones (80% of office hours watched)."""
    days = working_days(today, count, folder)
    whole = 0.8 * 60 * (hours[1] - hours[0])
    cache = {}
    out = []
    for person in cfg.get("people") or []:
        summaries = week(person, days, hours, cache)
        out.append({
            "code": person.get("code", "?"),
            "name": person.get("name") or "",
            "department": person.get("department", ""),
            "why": person.get("why", ""),
            "check": person.get("check") or {},
            "days": [{k: v for k, v in s.items() if k != "line"}
                     for s in summaries],
            "slots": [strip(s, frm, to) for s in summaries],
            "usual": usual([s for s in summaries if not s.get("before")],
                           whole),
        })
    return out


def usual(summaries, whole_min=0.0):
    """A usual day over the days watched for at least `whole_min` minutes of
    office hours (a morning the laptop slept through is not a short day at
    the desk): desk hours, share, first in and last out (as hours of the
    day), and the longest break."""
    seen = [s for s in summaries
            if s["watched_min"] > 0 and s["watched_min"] >= whole_min]
    if not seen:
        return None
    came = [s for s in seen if s["first"] is not None]

    def hour(t):
        return t.hour + t.minute / 60.0

    def mean(xs):
        return sum(xs) / len(xs) if xs else None

    # Desk time over the days they came in: a day off is not a short day
    # at the desk (P4, 18 Nov). How many days they came is said beside it.
    return {
        "days": len(seen),
        "days_in": len(came),
        "desk_h": mean([s["desk_min"] / 60.0 for s in came]),
        "share": mean([s["share"] for s in came if s["share"] is not None]),
        "first_h": mean([hour(s["first"]) for s in came]),
        "last_h": mean([hour(s["last"]) for s in came]),
        "late_h": mean([s["late_min"] / 60.0 for s in seen]),
        "longest_break": max((b[2] for s in came for b in s["breaks"]),
                             default=0.0),
        "breaks_a_day": mean([len(s["breaks"]) for s in came]),
    }
