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

# The day the strips cover, in the campus's own hours rather than midnight to
# midnight: nobody wants four hours of empty corridor at either end.
DAY_START_HOUR = 6
DAY_END_HOUR = 22
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


def day_slots(recent, room, now):
    """One mark per quarter hour from 06:00 to 22:00: 1 occupied, 0 not.

    Returns the marks, and the first and last slot anybody was seen in, which
    is what "first in, last out" means on this page. None where the loop was
    not running, so an unwatched hour is not drawn as an empty room.
    """
    count = (DAY_END_HOUR - DAY_START_HOUR) * 60 // SLOT_MINUTES
    start = now.normalize() + pd.Timedelta(hours=DAY_START_HOUR)
    mine = recent[recent["room"] == room].sort_values("timestamp")
    if mine.empty:
        return [None] * count, None, None
    stamps = mine["timestamp"].tolist()
    states = mine["status"].tolist()
    slots, first, last = [], None, None
    for i in range(count):
        at = start + pd.Timedelta(minutes=i * SLOT_MINUTES)
        if at > now:
            slots.append(None)
            continue
        # The state in force at that moment is the last event before it.
        prior = [j for j, t in enumerate(stamps) if t <= at]
        if not prior:
            slots.append(None)
            continue
        state = states[prior[-1]]
        on = 1 if state == "occupied" else 0
        slots.append(on)
        if on:
            first = i if first is None else first
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


def rows(df, recent, now, grade, spell, minutes_since, hours=None,
         calibrated=None):
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
        slots, first, last = day_slots(recent, room, now)

        note = None
        kind = {"Red": "act", "Amber": "act", "Green": "good",
                "Cool": "cold", "Fault": "unknown"}.get(level, "watch")
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
        if level == "Fault":
            kind = "unknown"
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
