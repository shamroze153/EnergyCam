"""The rooms, and what their air conditioners cost, without Streamlit.

The page (rooms_dashboard.py) and the weekly mail (weekly_report.py) read
rooms.yaml and the database through this one file, so a figure in the mail
is the figure on the page. Until 18 Nov all of it lived inside the page,
which a script cannot import without drawing the page.
"""
import pandas as pd
import yaml

import analysis_view as av
import campus_view
import energy_rooms as er


def unit_rating(room, assumptions):
    """kW one of this room's units draws while it cools, and a room's load.

    A unit with its size written down (`ac_tons` in rooms.yaml, one unit's
    tons) draws tons x kw_per_ton; any other is the site's typical split
    unit, unit_kw. The load is the room's units in typical-unit terms --
    what every money figure multiplies by. Until 12 Nov it was the plain
    count, and 141-C Cafe's six 2-ton towers cost the same as six small
    splits.
    """
    base = float(assumptions.get("unit_kw", 1.2) or 1.2)
    per_ton = float(assumptions.get("kw_per_ton", 1.0) or 1.0)
    tons = room.get("ac_tons")
    if isinstance(tons, (list, tuple)) and tons:
        # Each unit's own size, as surveyed: Room 17 is 1.5 + 1.5 + 1 + 1.
        total = sum(float(t) for t in tons) * per_ton
        return total / len(tons), total / base
    kw = float(tons) * per_ton if tons else base
    count = int(room.get("ac_count", 1) or 1)
    return kw, count * kw / base


def unit_count(room):
    """How many units a room has: its list of sizes, else ac_count, else 1."""
    tons = room.get("ac_tons")
    if isinstance(tons, (list, tuple)) and tons:
        return len(tons)
    return int(room.get("ac_count", 1) or 1)


def sizes_text(room):
    """Each unit's tons as "2+1", where rooms.yaml has them; else ""."""
    tons = room.get("ac_tons")
    if isinstance(tons, (list, tuple)) and tons:
        return "+".join("%g" % float(t) for t in tons)
    if tons:
        return "+".join(["%g" % float(tons)] * unit_count(room))
    return ""


def tons_of(room):
    """A room's cooling in tons, where its units' sizes are written down."""
    tons = room.get("ac_tons")
    if isinstance(tons, (list, tuple)) and tons:
        return sum(float(t) for t in tons)
    return float(tons) * unit_count(room) if tons else None


def rooms_frame(path="rooms.yaml"):
    """Every room in rooms.yaml, one row each, as the page reads them."""
    cfg = yaml.safe_load(open(path, encoding="utf-8"))
    recorders = cfg["recorders"]
    site = cfg.get("assumptions", {}) or {}
    rows = []
    for room in cfg["rooms"]:
        # A room is a list of cameras, and one place at 140-H is watched by
        # two recorders at once. Spelled either way in rooms.yaml, and read
        # the same way here as the loop reads it -- the page and the loop
        # disagreeing about which cameras a room has is the kind of thing
        # nobody notices until a figure is wrong.
        if room.get("cameras"):
            cameras = [(c["recorder"], int(c["channel"]))
                       for c in room["cameras"]]
        else:
            cameras = [(room["recorder"], int(ch)) for ch in room["channels"]]
        recorder = cameras[0][0]
        alerts = room.get("alert") != "never"
        has_unit = room["ac"] in ("visible", "hidden")
        if room["ac"] == "visible":
            unit_note = "unit in frame"
        elif room["ac"] == "hidden":
            unit_note = "unit out of frame"
        else:
            unit_note = "no unit"
        caption = unit_note if has_unit else "nothing to switch off"
        unit_kw, load = unit_rating(room, site) if has_unit else (0.0, 0.0)
        rows.append({
            "room": room["name"],
            "recorder": recorder,
            "campus": recorders[recorder].get("campus", "unknown"),
            "zone": room.get("zone", "Other"),
            "floor": room.get("floor"),
            # Which of 141's buildings, where the name does not say: 141-D's
            # ground-floor rooms are "141 Room 3 (ground floor)" and the
            # like, named before the survey placed them (13 Nov). A name is
            # the key of every row in the database, so it stays.
            "building": room.get("building") or "",
            # Whose space it is. Empty when nobody has said; a blank rather
            # than None so that "dept or something" reads the same on every
            # row, and never NaN, which is true.
            "dept": room.get("dept") or "",
            "cameras": len(cameras),
            "ac": room["ac"],
            "ac_count": 0 if not has_unit else unit_count(room),
            # How many of them some camera shows, read yet or not (`in_view`,
            # 19 Nov audit): the follow-up of in camera -> calibrated.
            "in_view": 0 if not has_unit else int(room.get("in_view") or 0),
            # One unit's size where they are all alike; the room's total
            # where they differ is in tons_total.
            "ac_tons": (None if isinstance(room.get("ac_tons"), list)
                        else room.get("ac_tons")),
            "tons_total": tons_of(room) if has_unit else None,
            # Each unit's tons, "1.5+1.5+1+1", for overview.ac_size to say
            # in full. Text, not a list: a list in a cell breaks hashing.
            "ac_sizes": sizes_text(room) if has_unit else "",
            "unit_kw": unit_kw,
            # How many people one of its units is there for: more units
            # running than the people in need is waste too (Shamroze, 17
            # Nov: the cafe ran four towers for three people).
            "people_per_unit": room.get("people_per_unit"),
            "ac_load": load,
            "meter": room.get("meter"),
            "alerts": alerts,
            "caption": caption,
            "has_unit": has_unit,
            "unit_note": unit_note if alerts else "cooled on purpose",
            "empty_after": room.get("empty_after_minutes"),
            # Hours its cameras are not opened on purpose (the 141 gym,
            # ladies' hours): "private_now" is worked out per page view.
            "private_hours": ",".join(room.get("private_hours") or []),
        })
    return pd.DataFrame(rows)


def assumptions(path="rooms.yaml"):
    return yaml.safe_load(open(path, encoding="utf-8")).get("assumptions", {})


def rates_of(a):
    """(off-peak, peak) rupees a unit, from rooms.yaml's assumptions."""
    return (float(a.get("tariff_rs_per_kwh", 67) or 67),
            float(a.get("peak_rs_per_kwh", 81) or 81))


def units_column(conn):
    """The column holding how many units run, or NULL where there is none.

    sql/09_ac_units.sql adds room_events.ac_units_on; until an administrator
    runs it the page asks for a NULL in its place, and reads exactly as it
    did before.
    """
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM information_schema.columns"
                    " WHERE table_name = 'room_events'"
                    " AND column_name = 'ac_units_on'")
        found = cur.fetchone() is not None
    finally:
        cur.close()
    return "ac_units_on" if found else "NULL::smallint AS ac_units_on"


def events_between(conn, start, end):
    """Every change in a window, plus each room's state as it opened.

    Only changes are written, so a room empty since last night has no row
    in today at all; the one row before the window says what it was doing
    when the window opened, and the morning reads empty rather than blank.
    """
    units = units_column(conn).replace("%", "%%")
    events = pd.read_sql_query(
        "(SELECT timestamp, room, status, people, ac_state, " + units +
        "   FROM room_events WHERE timestamp >= %s AND timestamp < %s)"
        " UNION ALL "
        "(SELECT DISTINCT ON (room) timestamp, room, status, people,"
        "        ac_state, " + units +
        "   FROM room_events WHERE timestamp < %s"
        "  ORDER BY room, timestamp DESC)"
        " ORDER BY room, timestamp", conn,
        params=(start.to_pydatetime(), end.to_pydatetime(),
                start.to_pydatetime()))
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True)
    return events


def beats_between(conn, start, end):
    """Every heartbeat in a window: when the loop was running."""
    beats = pd.read_sql_query(
        "SELECT timestamp FROM heartbeat WHERE timestamp >= %s"
        " AND timestamp < %s ORDER BY timestamp", conn,
        params=(start.to_pydatetime(), end.to_pydatetime()))
    return list(pd.to_datetime(beats["timestamp"], utc=True))


def floor_level(row):
    """The floor inside its building, for pages that name the building."""
    import floors_view
    fl = floors_view.floor_of(row)
    if fl in ("Main building", "141-C", "141-D", "Not placed on a floor yet"):
        return ""
    return fl.partition(" · ")[2] if " · " in fl else fl


def ledger_for(rooms, events, beats, a, start, end, campus=None):
    """energy_rooms.ledger over [start, end) for one campus, or all (None),
    from rooms_frame(), a window's events and beats, and the assumptions."""
    rooms = rooms[rooms["has_unit"].astype(bool)]
    if campus:
        rooms = rooms[rooms["campus"] == campus]
    rooms = rooms.copy()
    rooms["floor"] = [floor_level(r) for _, r in rooms.iterrows()]
    return er.ledger(events, rooms, start, end, beats,
                     campus_view.calibrated_counts(), rates_of(a),
                     av.peak_window(a), float(a.get("ac_duty", 1.0) or 1.0))
