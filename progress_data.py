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

# A note on the desk counts only at this score or more (the loop notes
# everything from 0.25). 24 Nov, against 105 frames checked by eye: 0.25
# and 0.35 both 95.2%, 0.30 96.2% -- it drops a turned, empty chair (P1's
# at 20:28, 0.29) and keeps a dim sitter (P5 at 19:41, 0.32).
DESK_MIN_SCORE = 0.30

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


def desk_notes(person, day_notes, min_score=None):
    """The notes that fall on this person's desk: within reach of the
    desk's point, and scoring at least `min_score` (DESK_MIN_SCORE).

    The reach is each note's own: a share of the frame's width, or of that
    box's height where that is more (as desk_activity.employee). 24 Nov,
    checked by eye: P1 leaning over his desk, near the camera, had a box
    300 px tall ending 71-78 px from the desk's point -- outside the 67 px
    the camera's middling box allowed, so four passes of him at work read
    "away"."""
    if day_notes is None or day_notes.empty:
        return day_notes.iloc[0:0] if day_notes is not None else None
    min_score = DESK_MIN_SCORE if min_score is None else min_score
    cam = day_notes[(day_notes["recorder"] == person["recorder"])
                    & (day_notes["channel"] == int(person["channel"]))]
    if "score" in cam.columns and min_score > 0:
        cam = cam[cam["score"] >= min_score]
    if cam.empty:
        return cam
    x, y = (float(v) for v in person["seat"])
    if person.get("reach"):
        r = float(person["reach"])
    else:
        width = float(cam["frame_w"].iloc[0])
        r = (SEAT_REACH * cam["h"]).clip(lower=SEAT_RADIUS * width)
    bottom = cam["cy"] + cam["h"] / 2.0
    hit = ((cam["cx"] - x) ** 2 + (bottom - y) ** 2) <= r * r
    return cam[hit]


def at_desk(person, day_notes, min_score=None):
    """The times of the notes that fall on this person's desk."""
    notes_ = desk_notes(person, day_notes, min_score)
    return [] if notes_ is None or notes_.empty else sorted(notes_["at"])


# Passes further apart than this have a hole between them (the loop or the
# laptop stopped): nothing is filled in across it.
JOINED = pd.Timedelta(minutes=2)
# A lone pass at the desk is let go as somebody passing or a chair in the
# changing light -- unless what was seen there was this sure of a person,
# and sitting: a box no taller than this for its width (24 Nov: P4 back
# at his desk, 0.90, 1.13; a man standing by P2's empty chair, 0.89, 2.46).
LONE_SURE = 0.6
SEATED_RATIO = 1.8


def timeline(person, day_notes, day_passes, min_score=None):
    """Pass by pass: [(start, end, "desk" | "away")], one-pass blips gone.

    A pass is "desk" when a note on the desk falls inside it. A single
    "away" pass with "desk" on both sides is the detector blinking, and is
    "desk". Then the reverse: a single "desk" pass with "away" on both
    sides is somebody passing, or a chair as the light changes at dawn (19
    Nov 07:01, a "first in" nobody made), and is "away" -- a sitter stays
    longer than one pass -- unless the person seen there was sure
    (LONE_SURE: 24 Nov, P4 back at his desk at 19:59 for one pass at 0.9).
    Nothing is filled in across a hole in the passes (24 Nov: the loop
    stopped 20:07-20:25, and the pass after the hole made P1's empty chair
    at 20:28 "desk" because the passes either side of the hole were).
    Passes the loop never made are not in the list."""
    if day_passes is None or day_passes.empty:
        return []
    seen_notes = desk_notes(person, day_notes, min_score)
    hits, sure = [], []
    if seen_notes is not None and not seen_notes.empty:
        ordered = seen_notes.sort_values("at")
        hits = list(ordered["at"])
        score = ordered["score"] if "score" in ordered.columns else 1.0
        seated = (ordered["h"] / ordered["w"].clip(lower=1.0)) <= SEATED_RATIO
        # How sure a pass is of a SEATED person: a standing one counts 0.
        sure = list((score * seated).astype(float))
    out = []
    i = 0
    for start, end in zip(day_passes["start"], day_passes["end"]):
        while i < len(hits) and hits[i] <= start:
            i += 1
        j, best = i, 0.0
        while j < len(hits) and hits[j] <= end:
            best = max(best, sure[j])
            j += 1
        out.append([start, end, "desk" if j > i else "away", best])

    def joined(a, b):
        return out[b][0] - out[a][1] <= JOINED

    for k in range(1, len(out) - 1):
        if (out[k][2] == "away" and out[k - 1][2] == "desk"
                and out[k + 1][2] == "desk" and joined(k - 1, k)
                and joined(k, k + 1)):
            out[k][2] = "desk"
    for k in range(len(out)):
        before = out[k - 1][2] if k > 0 and joined(k - 1, k) else "away"
        after = out[k + 1][2] if k + 1 < len(out) and joined(k, k + 1) \
            else "away"
        if (out[k][2] == "desk" and before == "away" and after == "away"
                and out[k][3] < LONE_SURE):
            out[k][2] = "blip"
    return [(p[0], p[1], "away" if p[2] == "blip" else p[2]) for p in out]


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


# ------------------------------------------------- what they did all day
#
# The loop's half (progress_track.py, with OpenCV) writes, every pass, what
# each employee was doing at the desk to ACTIVITY/<date>.csv, and the
# desk's picture under CROPS. This half reads them -- pandas only, so the
# dashboard reaches it without the detector's libraries.

ACTIVITY = "progress"
CROPS = os.path.join("frames", "progress")
# A sighting elsewhere this close (progress_track.REID_MIN) is a possible
# place for that pass; it names the place only once confirmed by a person
# (review_<date>.csv, from the Progress tab), and only within an hour of
# the day at the desk.
SEEN_MIN = 0.70
SEEN_WINDOW = pd.Timedelta(minutes=60)
# Where a camera's room is, by kind. First match wins; anything else is an
# office (their own room if it is their department's).
PLACES = [
    ("meeting", ("board room", "meeting room")),
    ("smoking", ("smoking",)),
    ("prayer", ("mosque", "ablution")),
    ("cafe", ("cafe", "pantry", "commons", "gaming")),
    ("outside", ("street", "outside", "parking", "backside", "solar",
                 "genset", "ro plant", "emergency", "outdoor", "inverter",
                 "atrium")),
    ("corridor", ("lobby", "stairs", "entry", "entrance", "attendance",
                  "reception", "sitting area")),
]
KINDS = ["computer", "phone", "talking", "desk", "meeting", "own room",
         "office", "cafe", "smoking", "prayer", "corridor", "outside",
         "unseen"]
AT_DESK = ("computer", "phone", "talking", "desk")
# An activity read this close to a pass at the desk is that pass's.
ACTIVITY_REACH = pd.Timedelta(minutes=8)


def place_of(room, own=None):
    """The kind of place a room is."""
    name = (room or "").lower()
    if own and name == str(own).lower():
        return "own room"
    for kind, words in PLACES:
        if any(w in name for w in words):
            return kind
    return "office"


def load_activity(day, folder=None):
    """The day's activity rows (progress_track), with a timestamp `at`."""
    path = os.path.join(folder or ACTIVITY, day + ".csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    d = pd.read_csv(path)
    d["at"] = pd.to_datetime(day + " " + d["time"])
    return d


def load_reviews(day, folder=None):
    """What a person said about the day's possible sightings:
    {(time, code, room): "yes" | "no"}, the latest word for each."""
    path = os.path.join(folder or ACTIVITY, "review_%s.csv" % day)
    if not os.path.exists(path):
        return {}
    d = pd.read_csv(path, dtype=str).fillna("")
    return {(r["time"], r["code"], r["room"]): r["verdict"]
            for _, r in d.iterrows()}


def seen_picture(day, code, time_, recorder, channel, crops=None):
    """The small picture progress_track kept of a possible sighting, or
    None (pictures are on this laptop only, and let go after a week)."""
    import glob
    hits = glob.glob(os.path.join(
        crops or CROPS, day, code, "%s_seen_*_%s%02d.jpg"
        % (str(time_).replace(":", ""), recorder, int(channel))))
    return sorted(hits)[0] if hits else None


def desk_picture(day, code, crops=None):
    """The latest picture of the employee's desk with them at it."""
    import glob
    hits = []
    for state in ("computer", "phone", "talking"):
        hits += glob.glob(os.path.join(crops or CROPS, day, code,
                                       "*_desk_%s.jpg" % state))
    return sorted(hits)[-1] if hits else None


def save_review(day, time_, code, room, verdict, folder=None):
    """Write one yes/no about a possible sighting (the Progress tab)."""
    import csv
    folder = folder or ACTIVITY
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "review_%s.csv" % day)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["time", "code", "room", "verdict", "at"])
        w.writerow([time_, code, room, verdict,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")])


def day_activity(person, day, rows=None, notes=None, passes=None,
                 seen_min=SEEN_MIN, reviews=None):
    """An employee's whole day, pass by pass, and its figures.

    At the desk or not comes from the seat notes (timeline(): every pass,
    checked by eye at 93 of 99). What they were doing there comes from the
    activity read nearest the pass (from the loop, or from kept frames); a
    pass at the desk with none near is "desk" -- at the desk, activity not
    read. Away from the desk, a sighting elsewhere names the place (only
    once progress_track.TRACK_ELSEWHERE is on); otherwise "unseen". Before
    first in and after last out: "out".

    Returns {"line": [(start, end, kind, room)], "minutes": {kind: min},
    "estimate": {computer, phone, talking: min} (the unread desk minutes
    shared out as the read ones were), "read": passes with an activity,
    "first_in", "last_out", "last_seen", "last_seen_where"}."""
    rows = load_activity(day) if rows is None else rows
    notes = globals()["notes"](day) if notes is None else notes
    passes = globals()["passes"](day) if passes is None else passes
    reviews = load_reviews(day) if reviews is None else reviews
    code = person["code"]
    own = person.get("department")
    mine = rows[rows["code"] == code] if len(rows) else rows
    acts = mine[(mine["kind"] == "desk") & (mine["state"] != "away")] \
        if len(mine) else mine
    seen = mine[(mine["kind"] == "seen") & (mine["score"] >= seen_min)] \
        if len(mine) else mine
    start_of_day = pd.Timestamp(day) + pd.Timedelta(hours=DAY_FROM)
    line, read = [], 0
    for start, end, state in timeline(person, notes, passes):
        if state == "desk":
            kind, room = "desk", own
            if len(acts):
                mid = start + (end - start) / 2
                gap = (acts["at"] - mid).abs()
                if gap.min() <= ACTIVITY_REACH:
                    kind = str(acts.loc[gap.idxmin(), "state"])
                    read += 1
            line.append([start, end, kind, room])
        else:
            line.append([start, end, "unseen", ""])
    at = [i for i, p in enumerate(line)
          if p[2] in AT_DESK and p[1] > start_of_day]
    # Away from the desk: the best sighting in each pass within an hour of
    # the day at the desk. A confirmed one names the place; a possible one
    # is listed for somebody to look at; a rejected one is forgotten.
    possible = []
    if at and len(seen):
        lo = line[at[0]][0] - SEEN_WINDOW
        hi = line[at[-1]][1] + SEEN_WINDOW
        for p in line:
            if p[2] != "unseen" or p[0] < lo or p[1] > hi:
                continue
            inside = seen[(seen["at"] > p[0]) & (seen["at"] <= p[1])]
            if not len(inside):
                continue
            inside = inside.assign(verdict=[
                reviews.get((r["time"], code, str(r["room"])), "")
                for _, r in inside.iterrows()])
            yes = inside[inside["verdict"] == "yes"]
            if len(yes):
                best = yes.loc[yes["score"].idxmax()]
                p[2], p[3] = place_of(best["room"], own), str(best["room"])
                continue
            open_ = inside[inside["verdict"] == ""]
            if len(open_):
                best = open_.loc[open_["score"].idxmax()]
                possible.append({
                    "time": str(best["time"]), "room": str(best["room"]),
                    "kind": place_of(best["room"], own),
                    "score": float(best["score"]),
                    "recorder": str(best["recorder"]),
                    "channel": int(best["channel"])})
    for i, p in enumerate(line):
        if p[2] == "unseen" and (not at or i < at[0] or i > at[-1]):
            p[2] = "out"
    minutes = {k: 0.0 for k in KINDS}
    for s, e, k, _ in line:
        if k in minutes:
            minutes[k] += (e - s).total_seconds() / 60.0
    done = {k: minutes[k] for k in ("computer", "phone", "talking")}
    total_read = sum(done.values())
    estimate = dict(done)
    if total_read > 0:
        for k in estimate:
            estimate[k] += minutes["desk"] * done[k] / total_read
    anywhere = [p for p in line if p[2] not in ("out", "unseen")
                and p[1] > start_of_day]
    return {
        "day": day, "line": [tuple(p) for p in line], "minutes": minutes,
        "estimate": estimate, "read": read,
        "first_in": line[at[0]][0] if at else None,
        "last_out": line[at[-1]][1] if at else None,
        "last_seen": anywhere[-1][1] if anywhere else None,
        "last_seen_where": anywhere[-1][3] if anywhere else "",
        "possible": possible,
        "places": {k: minutes[k] for k in KINDS
                   if k not in AT_DESK and k != "unseen" and minutes[k] > 0},
    }


# ------------------------------------------------ every day, and right now
#
# Shamroze, 23 Nov: "first in kab, last out kab, poore din kya kiya, kitne
# percent productivity -- bahut saare dinon ka" and "status jaise AC ka
# status jaata hai". Two figures a day, said apart because they are not
# the same claim:
#   desk %      time at the desk / time in the office (first in -> last out)
#   computer %  time at the computer / time in the office -- only on days
#               the activity at the desk was read (from 23 Nov)

HISTORY = os.path.join("progress", "history.csv")
HISTORY_COLS = ["day", "code", "first", "last", "in_min", "span_min",
                "part", "desk_min", "away_min", "desk_pct", "computer_min",
                "phone_min", "talking_min", "computer_pct", "breaks",
                "longest_break", "read"]
# A loop silent this long is not watching: the status says so.
STALE = pd.Timedelta(minutes=15)


def day_record(person, day, n=None, p=None, rows=None, reviews=None):
    """One employee's day as the history keeps it (see above)."""
    a = day_activity(person, day, rows=rows, notes=n, passes=p,
                     reviews=reviews)
    first, last = a["first_in"], a["last_out"]
    # Time in the office is the WATCHED time between first in and last
    # out: 23 Nov the laptop slept 12:05-19:01, and counting those seven
    # hours as "in the office, not at the desk" made a full day look 14%.
    in_min, desk, breaks, run, prev_end = 0.0, 0.0, [], None, None
    for s, e, k, _ in a["line"]:
        if first is None or s < first or e > last:
            continue
        if prev_end is not None and s - prev_end > JOINED:
            run = None              # a hole in the watching: no break known
        prev_end = e
        in_min += _minutes(s, e)
        if k in AT_DESK:
            desk += _minutes(s, e)
            if run:
                breaks.append(_minutes(run, s))
                run = None
        elif run is None:
            run = s
    span = _minutes(first, last) if first is not None else 0.0
    breaks = [b for b in breaks if b >= BREAK_MIN]
    read = a["read"] > 0
    est = a["estimate"]
    # The computer share is of the desk time that was read, applied to all
    # of the desk time; minutes away are the watched ones not at the desk.
    return {
        "day": day, "first": first, "last": last, "in_min": in_min,
        "span_min": span, "part": span - in_min > 30,
        "desk_min": desk, "away_min": max(0.0, in_min - desk),
        "desk_pct": desk / in_min if in_min > 0 else None,
        "computer_min": est["computer"] if read else None,
        "phone_min": est["phone"] if read else None,
        "talking_min": est["talking"] if read else None,
        "computer_pct": est["computer"] / in_min if read and in_min > 0
        else None,
        "breaks": len(breaks), "longest_break": max(breaks, default=0.0),
        "read": int(a["read"]),
    }, a


def load_history(path=None):
    """The days the history file keeps: {(day, code): record}."""
    path = path or HISTORY
    if not os.path.exists(path):
        return {}
    d = pd.read_csv(path, dtype=str).fillna("")
    out = {}
    for _, r in d.iterrows():
        rec = {}
        for c in HISTORY_COLS:
            v = r.get(c, "")
            if c in ("day", "code"):
                rec[c] = v
            elif c in ("first", "last"):
                rec[c] = pd.Timestamp("%s %s" % (r["day"], v)) if v else None
            elif c == "part":
                rec[c] = v == "True"
            else:
                rec[c] = float(v) if v not in ("", "None") else None
        out[(rec["day"], rec["code"])] = rec
    return out


def store_history(records, path=None):
    """Write (or rewrite) days in the history file -- this machine only
    (progress/ is git-ignored): the seat notes behind them are let go after
    two weeks, the days are kept."""
    path = path or HISTORY
    kept = load_history(path)
    for rec in records:
        kept[(rec["day"], rec["code"])] = rec
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    rows = []
    for key in sorted(kept):
        rec = kept[key]
        row = []
        for c in HISTORY_COLS:
            v = rec.get(c)
            if c in ("first", "last"):
                v = v.strftime("%H:%M") if v is not None else ""
            elif isinstance(v, float):
                v = "%.4f" % v
            row.append("" if v is None else str(v))
        rows.append(row)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        import csv
        w = csv.writer(fh)
        w.writerow(HISTORY_COLS)
        w.writerows(rows)
    os.replace(tmp, path)


def history(person, upto, count=20, folder=SEATS, cache=None, stored=None,
            reviews_for=None):
    """The employee's working days up to `upto`, newest last: worked out
    from the seat notes where they are still kept, else as the history
    file kept them."""
    cache = {} if cache is None else cache
    since = str(person.get("since") or "")
    code = person.get("code", "?")
    days = working_days(upto, count, folder)
    out = {}
    for day in days:
        if since and day < since:
            continue
        if day not in cache:
            cache[day] = (notes(day), passes(day))
        n, p = cache[day]
        rec, _ = day_record(person, day, n, p,
                            reviews=(reviews_for or {}).get(day))
        rec["code"] = code
        out[day] = rec
    for (day, c), rec in (stored or {}).items():
        if c == code and day not in out and day <= upto and not (
                since and day < since):
            out[day] = rec
    return [out[d] for d in sorted(out)][-count:]


def live(day_act, now, hours=(10, 20)):
    """What the employee is doing right now, from today's passes:
    {"state": desk | away | out | gone | unwatched, "label", "since",
    "minutes", "place"} -- the way the campus page says a room's AC is on."""
    line = [p for p in day_act.get("line") or [] if p[1] <= now]
    day = day_act.get("day")
    if not line:
        return {"state": "unwatched", "label": "Not watched yet today",
                "since": None, "minutes": None, "place": ""}
    if now - line[-1][1] > STALE:
        return {"state": "unwatched", "label": "Not being watched",
                "since": line[-1][1], "minutes": _minutes(line[-1][1], now),
                "place": ""}

    def group(k):
        return "desk" if k in AT_DESK else "away"
    kind = line[-1][2]
    g = group(kind)
    i = len(line) - 1
    while (i > 0 and group(line[i - 1][2]) == g
           and line[i][0] - line[i - 1][1] <= JOINED):
        i -= 1
    since = line[i][0]
    place = ""
    start_of_day = pd.Timestamp(day) + pd.Timedelta(hours=DAY_FROM)
    came = [p for p in line if p[2] in AT_DESK and p[1] > start_of_day]
    if g == "desk":
        state = "desk"
        label = {"computer": "At the computer", "phone": "On the phone",
                 "talking": "Talking at the desk"}.get(kind, "At the desk")
    elif not came:
        # Not at the desk yet today -- by now, not by the end of the day.
        state, label, since = "out", "Not in yet", None
    else:
        end = pd.Timestamp(day) + pd.Timedelta(hours=hours[1])
        if now >= end and _minutes(since, now) >= 30:
            state, label, since = "gone", "Gone for the day", came[-1][1]
        else:
            state, label = "away", "Away from the desk"
            confirmed = [p for p in line[i:] if p[2] not in ("unseen", "out")
                         and p[2] not in AT_DESK]
            if confirmed:
                place = confirmed[-1][3]
            else:
                possible = [s for s in day_act.get("possible") or []
                            if since <= pd.Timestamp("%s %s" % (day, s["time"]))
                            <= now]
                if possible:
                    place = "possibly %s" % possible[-1]["room"]
    return {"state": state, "label": label, "since": since,
            "minutes": _minutes(since, now) if since is not None else None,
            "place": place}


def build(cfg, today, hours=(10, 20), count=5, folder=SEATS, frm=8, to=24,
          now=None, history_days=20):
    """Everything the Progress page draws, desk by desk: the last `count`
    working days up to `today` (YYYY-MM-DD), each day's summary and slots,
    and a usual day over the whole ones (80% of office hours watched);
    the day in focus (`focus`), what is happening now (`live`), and every
    day kept (`history`)."""
    days = working_days(today, count, folder)
    whole = 0.8 * 60 * (hours[1] - hours[0])
    cache = {}
    out = []
    focus = days[-1] if days else today
    now = now if now is not None else pd.Timestamp.now()
    stored = load_history()
    for person in cfg.get("people") or []:
        summaries = week(person, days, hours, cache)
        state = {"state": "out", "label": "Not in today", "since": None,
                 "minutes": None, "place": ""}
        try:
            n, p = cache.get(focus) or (notes(focus), passes(focus))
            the_day = day_activity(person, focus, notes=n, passes=p)
            if focus == now.strftime("%Y-%m-%d"):
                state = live(the_day, now, hours)
            the_day["slots"] = kind_slots(the_day, frm, to)
            the_day.pop("line", None)
        except Exception:                                   # noqa: BLE001
            the_day = None
        try:
            past = history(person, today, history_days, folder, cache, stored)
        except Exception:                                   # noqa: BLE001
            past = []
        out.append({
            "focus": the_day,
            "live": state,
            "history": past,
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


# ------------------------------------------------- the hosted page's copy
#
# The hosted dashboard has none of this machine's files, so the loop sends
# it the numbers (progress_track.publish -> progress_days, sql/11): codes,
# departments, times and hours -- never a name, never a picture.

def office_hours(path="rooms.yaml"):
    """The office day from rooms.yaml's hours, as (10.0, 20.0)."""
    try:
        with open(path, encoding="utf-8") as fh:
            op = ((yaml.safe_load(fh) or {}).get("hours") or {}).get(
                "operations") or {}
    except OSError:
        op = {}

    def h(t, default):
        try:
            a, b = str(t).split(":")[:2]
            return int(a) + int(b) / 60.0
        except (ValueError, AttributeError):
            return default
    return h(op.get("start", "10:00"), 10.0), h(op.get("end", "20:00"), 20.0)


def _jsonable(x):
    """A build() result as plain JSON: times as "ts:<iso>", tuples as
    lists, numpy numbers as Python ones."""
    import datetime as _dt
    if x is pd.NaT or x is None:
        return None
    if isinstance(x, pd.Timestamp):
        return "ts:" + x.isoformat()
    if isinstance(x, (_dt.datetime, _dt.date)):
        return x.isoformat()          # a stage's start or end, from YAML
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        try:
            return x.item()
        except (ValueError, AttributeError):
            pass
    return x


def _restore(x):
    if isinstance(x, str) and x.startswith("ts:"):
        return pd.Timestamp(x[3:])
    if isinstance(x, dict):
        return {k: _restore(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_restore(v) for v in x]
    return x


def to_payloads(cfg, people, hours, made):
    """progress_days rows for one day: [(code, json)], one an employee and
    one "_project" (the stages). Names are blanked: they stay here."""
    import json
    rows = []
    for p in people:
        q = dict(p)
        q["name"] = ""
        rows.append((str(p.get("code", "?")), json.dumps(_jsonable(q))))
    project = {"campus": cfg.get("campus", ""),
               "stages": cfg.get("stages") or [],
               "needs": cfg.get("needs") or [],
               "hours": list(hours), "made": made}
    rows.append(("_project", json.dumps(_jsonable(project))))
    return rows


def from_payloads(rows):
    """(cfg, people, made, hours) back from progress_days rows
    [(code, payload)] -- payload a dict (psycopg2 reads JSONB so) or text."""
    import json
    cfg, people, made, hours = {}, [], "", (10.0, 20.0)
    for code, payload in rows:
        data = payload if isinstance(payload, dict) else json.loads(payload)
        data = _restore(data)
        if code == "_project":
            cfg = {"campus": data.get("campus", ""),
                   "stages": data.get("stages") or [],
                   "needs": data.get("needs") or []}
            made = data.get("made", "")
            hours = tuple(data.get("hours") or (10.0, 20.0))
        else:
            people.append(data)
    people.sort(key=lambda p: str(p.get("code", "")))
    return cfg, people, made, hours


def kind_slots(day_summary_, frm=8, to=24, step=10):
    """progress_track.progress_day's line as `step`-minute slots: the kind
    that held most of each slot, or "unwatched"."""
    base = pd.Timestamp(day_summary_["day"])
    line = day_summary_["line"]
    out = []
    t = base + pd.Timedelta(hours=frm)
    end = base + pd.Timedelta(hours=to)
    width = pd.Timedelta(minutes=step)
    while t < end:
        u = t + width
        share = {}
        for s, e, k, _ in line:
            a, b = max(s, t), min(e, u)
            if b > a:
                share[k] = share.get(k, 0.0) + (b - a).total_seconds()
        out.append(max(share, key=share.get) if share else "unwatched")
        t = u
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
