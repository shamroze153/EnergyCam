"""The campus page: one view of every room, drawn from the real figures.

The layout was settled from mock-ups rather than argued about in code, so
this file does not lay anything out. campus_view.html is the page; this turns
the database and rooms.yaml into the one block of data it reads.

Keeping them apart matters for a reason that has already bitten this project:
the page and the loop must not disagree about what a room is. Everything here
that decides something -- whether a room counts as needing action, how long
it has been empty, when somebody first arrived -- is computed from the same
helpers the rest of the dashboard uses, not reimplemented in JavaScript.
"""
import json
import os

import pandas as pd

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "campus_view.html")

# A room's zone says where it is; a department says whose it is. Nobody has
# walked the building to record the second, so it is derived from the first
# and can be overridden per room with a dept: line in rooms.yaml.
DEPT_BY_ZONE = {
    "Offices": "Product & design", "H offices": "Engineering",
    "H common": "Shared", "Cafe & common": "Cafe",
    "H entrance": "Front of house", "Basement": "Facilities",
    "Server rooms": "IT", "H perimeter": "Security",
    "Outside & plant": "Facilities",
}

# The whole day, midnight to midnight.
#
# This used to run 06:00 to 22:00, on the reasoning that nobody wants four
# hours of empty corridor at either end. That reasoning was wrong for this
# system in particular: the hours it exists to measure are the ones after
# everybody goes home, and a chart that stops at ten at night leaves out
# every one of them. A room cooled from eight in the evening until morning
# appeared on that strip as two hours of waste.
DAY_START_HOUR = 0
DAY_END_HOUR = 24
SLOT_MINUTES = 15


def switched_off_while_empty(recent, room, empty_since):
    """Did somebody go and switch this unit off during this empty period?

    This is the one piece of praise the system can hand out, and it has to be
    earned rather than assumed: the room must have been seen with its unit
    ON at some point since it emptied, and OFF now. A unit that was already
    off when the room emptied is a room nobody had to visit.
    """
    if empty_since is None or pd.isna(empty_since):
        return None
    mine = recent[(recent["room"] == room)
                  & (recent["timestamp"] >= empty_since)]
    if mine.empty or "ac_state" not in mine.columns:
        return None
    states = [s for s in mine["ac_state"].tolist() if s]
    if not states or states[-1] != "off" or "on" not in states:
        return None
    # When it went off, and how long it had been running into the empty period.
    went = mine[mine["ac_state"] == "off"]
    if went.empty:
        return None
    at = went["timestamp"].iloc[0]
    ran = (at - empty_since).total_seconds() / 60.0
    return {"at": at, "ran": max(0.0, ran)}


BEAT_GRACE_SECONDS = 180


def watched_slots(beats, now):
    """Which quarter hours the loop was actually running for.

    The two ways a slot can be blank look identical in room_events and mean
    opposite things: the room did not change (so it was whatever it was), or
    nothing was watching (so nobody knows). Carrying each room's state in
    from before the window fixed the first and, on its own, would have
    answered the second wrongly -- a night when the laptop was shut would
    have been drawn as a peacefully empty building.

    The heartbeat is what tells them apart. The loop writes one every minute
    it is alive, so a quarter hour with no beat in it is a quarter hour
    nobody was looking, and it is drawn as unknown however much is known
    about the rooms either side of it.

    `beats` of None means the caller has nothing to say about coverage, and
    every slot is treated as watched -- the old behaviour, kept so that the
    helper can be used without a database.
    """
    count = (DAY_END_HOUR - DAY_START_HOUR) * 60 // SLOT_MINUTES
    if beats is None:
        return [True] * count
    start = now.normalize() + pd.Timedelta(hours=DAY_START_HOUR)
    covered = [False] * count
    grace = pd.Timedelta(seconds=BEAT_GRACE_SECONDS)
    for stamp in beats:
        if pd.isna(stamp):
            continue
        # The grace lets a beat vouch for the slot it has just entered. A
        # cycle takes over two minutes, so the quarter hour we are standing
        # in may hold no beat yet and is not therefore unwatched.
        offset = (stamp + grace - start).total_seconds()
        for index in {int(offset // (SLOT_MINUTES * 60)),
                      int((stamp - start).total_seconds()
                          // (SLOT_MINUTES * 60))}:
            if 0 <= index < count:
                covered[index] = True
    return covered


def day_slots(recent, room, now, beats=None):
    """One mark per quarter hour, midnight to midnight: 1 occupied, 0 not.

    Returns the marks, and the first and last slot anybody was seen in, which
    is what "first in, last out" means on this page. None where the loop was
    not running, so an unwatched hour is not drawn as an empty room -- the
    caller is expected to hand in each room's last event from before the day
    as well, or every quiet night reads as unwatched rather than as empty.
    """
    count = (DAY_END_HOUR - DAY_START_HOUR) * 60 // SLOT_MINUTES
    start = now.normalize() + pd.Timedelta(hours=DAY_START_HOUR)
    watched = watched_slots(beats, now)
    mine = recent[recent["room"] == room].sort_values("timestamp")
    if mine.empty:
        return [None] * count, None, None
    stamps = mine["timestamp"].tolist()
    states = mine["status"].tolist()
    slots, first, last = [], None, None
    for i in range(count):
        at = start + pd.Timedelta(minutes=i * SLOT_MINUTES)
        if at > now or not watched[i]:
            slots.append(None)
            continue
        # The state in force at that moment is the last event before it.
        prior = [j for j, t in enumerate(stamps) if t <= at]
        if not prior:
            slots.append(None)
            continue
        state = states[prior[-1]]
        on = 1 if state == "occupied" else 0
        # Somebody already in the room when the day began did not arrive at
        # midnight; they were carried in from the night before. Reporting
        # the first slot as an arrival would put the same time against every
        # such room and make it look like a shift start.
        carried = (stamps[prior[-1]] < start)
        slots.append(on)
        if on and not carried:
            first = i if first is None else first
        if on:
            last = i
    return slots, first, last


def calibrated_counts(path="ac_units.yaml"):
    """How many units in each room have actually been measured.

    A room with three units and one calibrated is not a calibrated room, and
    the page has to be able to say so rather than reporting the one it can
    read as though it spoke for the room.
    """
    if not os.path.exists(path):
        return {}
    import yaml
    data = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("rooms", {})
    return {name: len(cfg.get("units") or []) for name, cfg in (data or {}).items()}


# Where somebody counted is somebody in the building. A street, a car park
# and the smoking area all have cameras and all catch people who are passing
# rather than working, so the headline figure counts the inside and the rest
# is reported separately instead of being quietly added in.
OUTSIDE_ZONES = {"H perimeter", "Outside & plant", "Unused"}

def place(room, zone):
    """office or outside -- which of the two headcounts a room is in.

    Outside is the street, the car parks, the smoking area and the plant:
    the H perimeter and Outside & plant zones. Everything else is the
    office, lobbies and cafe included, because that is how the campus is
    run and how the figure is read. At night the total said 35 with a
    dozen indoors; the rest were the perimeter, and that is the split that
    matters.
    """
    return "outside" if zone in OUTSIDE_ZONES else "office"
    if zone in OFFICE_ZONES:
        return "office"
    return "common"


def building_curve(recent, df, now, beats=None):
    """How many people the cameras could see, through the day.

    This is not a headcount and the page must not call it one. Two cameras
    watching one place count the same person twice; somebody at a desk no
    camera covers is not counted at all; and a corridor camera counts
    whoever walks past. What it is good for is shape -- when the building
    fills, when it empties, whether today looks like yesterday.
    """
    count = (DAY_END_HOUR - DAY_START_HOUR) * 60 // SLOT_MINUTES
    start = now.normalize() + pd.Timedelta(hours=DAY_START_HOUR)
    watched = watched_slots(beats, now)
    inside_rooms = set(df[~df["zone"].isin(OUTSIDE_ZONES)]["room"])
    inside = [None] * count
    outside = [None] * count
    for i in range(count):
        at = start + pd.Timedelta(minutes=i * SLOT_MINUTES)
        if at > now or not watched[i]:
            continue
        seen_in = seen_out = 0
        answered = False
        for room, rows_ in recent.groupby("room"):
            prior = rows_[rows_["timestamp"] <= at]
            if prior.empty:
                continue
            answered = True
            last = prior.iloc[-1]
            if last["status"] != "occupied" or pd.isna(last["people"]):
                continue
            if room in inside_rooms:
                seen_in += int(last["people"])
            else:
                seen_out += int(last["people"])
        if answered:
            inside[i], outside[i] = seen_in, seen_out
    return inside, outside


def rows(df, recent, now, grade, spell, minutes_since, hours=None,
         calibrated=None, beats=None):
    """Every room, as the page wants it.

    `grade` and `spell` are passed in rather than imported so that this view
    cannot start grading rooms differently from the rest of the dashboard.
    """
    calibrated = calibrated_counts() if calibrated is None else calibrated
    out = []
    for _, row in df.iterrows():
        room = row["room"]
        level, headline, caption = grade(row, now, hours)
        empty = minutes_since(row.get("empty_since"), now)
        people = int(row["people"]) if pd.notna(row.get("people")) else 0
        ac = row["ac_state"] if pd.notna(row.get("ac_state")) else None
        has_unit = bool(row.get("has_unit"))
        alerts = bool(row.get("alerts", True))
        slots, first, last = day_slots(recent, room, now, beats)

        note = None
        kind = {"Red": "act", "Amber": "act", "Green": "good",
                "Cool": "cold", "Fault": "silent"}.get(level, "watch")
        if row["status"] == "occupied":
            kind = "cold" if (has_unit and ac == "off") else "busy"
        elif not has_unit:
            kind = "watch"
        elif not alerts:
            kind = "onpurpose"
        elif ac == "on":
            kind = "act"
        elif ac == "off":
            done = switched_off_while_empty(recent, room, row.get("empty_since"))
            if done:
                kind = "sorted"
                note = ("switched off %s — had been running %s into an"
                        " empty room"
                        % (done["at"].tz_convert(now.tz).strftime("%H:%M"),
                           spell(done["ran"])))
            else:
                kind = "good"
        else:
            kind = "unknown"
        if level == "Fault" or row["status"] == "unknown" \
                or pd.isna(row["status"]):
            # Nobody looked. That is not the same as a unit nobody has
            # calibrated, and calling both "unknown" would hide a camera
            # that stopped answering behind a sentence about air
            # conditioners. One is a job for whoever walks the building;
            # the other is a job for whoever fixes cameras.
            kind = "silent"
            note = caption
        if kind == "cold":
            note = caption

        total = int(row.get("ac_count") or (1 if has_unit else 0))
        out.append({
            "units_total": total,
            "units_read": calibrated.get(room, 0) if has_unit else 0,
            "name": room, "zone": row.get("zone", "Other"),
            "dept": row.get("dept") or DEPT_BY_ZONE.get(row.get("zone"), "—"),
            "unit": has_unit, "alerts": alerts,
            "state": row["status"] if pd.notna(row["status"]) else "unknown",
            "people": people,
            "empty": None if empty is None else round(empty),
            "ac": ac, "note": note, "grade": kind,
            "slots": slots, "first": first, "last": last,
        })
    return out


def page(rooms, meta, banner=""):
    """The finished HTML, ready to hand to Streamlit."""
    with open(TEMPLATE, encoding="utf-8") as fh:
        html = fh.read()
    data = json.dumps({"rooms": rooms, "meta": meta}, separators=(",", ":"),
                      default=str)
    # The data goes in as a JSON literal inside a script tag, so the one
    # sequence that could end that tag early has to be broken up.
    data = data.replace("</", "<\\/")
    return html.replace("__DATA__", data).replace("__BANNER__", banner)


def height(rooms):
    """Roughly how tall the page wants to be, so the frame does not clip it.

    Streamlit's iframe has no idea what is inside it, and a page cut off at
    the fold is the kind of fault nobody reports because it looks deliberate.
    """
    cards = len(rooms)
    return 760 + 150 * ((cards + 5) // 6)
