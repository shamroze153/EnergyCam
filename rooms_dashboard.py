"""The building at a glance: one tile per room, read by shape and colour.

A table of thirty rows is accurate and nobody reads it. What someone opening
this wants to know is which rooms want attention, and they want to know it
before they have read a single word. So every room is a tile with three things
drawn on it rather than written:

  people     one figure per person, so four people look different from one at
             arm's length
  the unit   an air conditioner badge: lit when running, dim when off, and
             dashed with a question mark while nothing has measured it
  the day    a strip under each tile covering the last eight hours, green where
             the room was occupied and grey where it was not, so "empty since
             eleven" is a shape instead of a sentence

Rooms are grouped by zone and sorted by how much attention they want, and
anything needing action is lifted to the top as well.

    streamlit run rooms_dashboard.py

Connects as energycam_dashboard, which reads and cannot write, via
DASHBOARD_DATABASE_URL in .env. The camera machine's own credential will not
work here by design: it is granted the timestamp column and nothing more.
"""
import os
import time
from datetime import timedelta, timezone
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
import yaml
from streamlit_autorefresh import st_autorefresh

from schedule import (AFTER_HOURS, WEEKEND, WORKING, describe,
                      split_by_period, wait_before_reporting)

PKT = timezone(timedelta(hours=5))

# The loop beats every five minutes. Two missed beats is a real gap rather than
# a slow cycle, and past that nothing here should be acted on: the tiles would
# still be sitting in their last known state, looking perfectly current.
STALE_AFTER_MINUTES = 11

SNAPSHOT_DIR = "snapshots"

STRIP_HOURS = 8
STRIP_SLOTS = 96                      # five minutes each

# A day is the window a person actually reasons in: "nobody came in before
# eleven", "it emptied at seven". Eight hours is right for a tile at a glance,
# and far too short for the question of what a room's day looks like.
DETAIL_HOURS = 24
DETAIL_SLOTS = 288                    # five minutes each, again

# Dark. A room full of screens is dark, and a page that is ninety per cent
# white at nine at night is a page people stop opening. The hues carry over --
# the same red still means the same thing -- set on dark surfaces, with the
# text lightened enough to stay readable rather than merely visible.
SURFACE = "#151C22"       # a card
SUNKEN = "#1B2228"        # a track, a well, anything recessed
LINE = "#263139"          # a border
TEXT = "#E6EAED"
MUTED = "#8A949A"
FAINT = "#5E6A70"

INK = {
    "Red":   {"bg": "#1E1316", "fg": "#F0918F", "edge": "#3B2328",
              "bar": "#E05252"},
    "Amber": {"bg": "#1D1810", "fg": "#E8B562", "edge": "#3A2E1A",
              "bar": "#D89221"},
    "Green": {"bg": "#141A14", "fg": "#A4D463", "edge": "#253220",
              "bar": "#84CC16"},
    # People in a room with its unit off. The opposite of waste, and nobody
    # hears about it until somebody complains about the heat.
    "Cool":  {"bg": "#101A21", "fg": "#74B9E0", "edge": "#1F3341",
              "bar": "#4A90C2"},
    "Fault": {"bg": "#161B1F", "fg": "#9AA4AA", "edge": "#28323A",
              "bar": "#6B7780"},
}

RANK = {"Red": 0, "Amber": 1, "Cool": 2, "Fault": 3, "Green": 4}

# How long somebody sits in a room with the unit off before it is worth
# mentioning. Short enough to matter, long enough that walking in and not
# having switched it on yet is not a fault.
COLD_AFTER_MINUTES = 30
ZONE_ORDER = ["Offices", "Basement", "Cafe & common", "Server rooms",
              "Outside & plant"]

st.set_page_config(page_title="EnergyCam", layout="wide", page_icon="🏢")
st_autorefresh(interval=30000, key="rooms_refresh")


def _setting(name):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)


from dotenv import load_dotenv  # noqa: E402
load_dotenv()

# The dashboard reads with its own credential, not the camera machine's.
# energycam_app holds SELECT on the timestamp column alone -- enough to confirm
# its writes land, not enough to reconstruct who was in which room. That is the
# point of the split, so the answer to the permission error it raises here is a
# second credential, never a wider grant on the first.
DATABASE_URL = _setting("DASHBOARD_DATABASE_URL") or _setting("DATABASE_URL")
USING_APP_CREDENTIAL = not _setting("DASHBOARD_DATABASE_URL")
DB_SSLMODE = _setting("DB_SSLMODE") or "require"


# ----------------------------------------------------------------- loading

@st.cache_data(ttl=20)
def load_rooms_config(path="rooms.yaml"):
    cfg = yaml.safe_load(open(path))
    recorders = cfg["recorders"]
    rows = []
    for room in cfg["rooms"]:
        alerts = room.get("alert") != "never"
        has_unit = room["ac"] in ("visible", "hidden")
        if room["ac"] == "visible":
            unit_note = "unit in frame"
        elif room["ac"] == "hidden":
            unit_note = "unit out of frame"
        else:
            unit_note = "no unit"
        caption = unit_note if has_unit else "nothing to switch off"
        rows.append({
            "room": room["name"],
            "recorder": room["recorder"],
            "campus": recorders[room["recorder"]].get("campus", "unknown"),
            "zone": room.get("zone", "Other"),
            "cameras": len(room["channels"]),
            "ac": room["ac"],
            "alerts": alerts,
            "caption": caption,
            "has_unit": has_unit,
            "unit_note": unit_note if alerts else "cooled on purpose",
            "empty_after": room.get("empty_after_minutes"),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=20)
def load_assumptions(path="rooms.yaml"):
    return yaml.safe_load(open(path)).get("assumptions", {})


@st.cache_data(ttl=20)
def load_hours(path="rooms.yaml"):
    return yaml.safe_load(open(path)).get("hours")


@st.cache_data(ttl=20)
def load_state():
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        latest = pd.read_sql_query(
            "SELECT DISTINCT ON (room) room, status, people, empty_since,"
            " ac_state, timestamp"
            " FROM room_events ORDER BY room, timestamp DESC", conn)
        recent = pd.read_sql_query(
            "SELECT timestamp, room, status, people FROM room_events"
            " WHERE timestamp >= now() - interval '%d hours'"
            " ORDER BY room, timestamp" % (DETAIL_HOURS + 1), conn)
        beat = pd.read_sql_query(
            "SELECT max(timestamp) AS last_beat FROM heartbeat", conn)
    finally:
        conn.close()
    for column in ("empty_since", "timestamp"):
        latest[column] = pd.to_datetime(latest[column], utc=True)
    recent["timestamp"] = pd.to_datetime(recent["timestamp"], utc=True)
    return latest, recent, pd.to_datetime(beat["last_beat"].iloc[0], utc=True)


@st.cache_data(ttl=60)
def load_coverage(days=7):
    """How much of the last week anything was actually watching.

    Every pattern on this page is drawn from recorded changes, and a change is
    only recorded while the loop is running. A laptop that goes home at seven
    produces a heatmap whose nights are blank -- and a blank night looks
    exactly like an empty one. The figure is read from the heartbeat, which is
    the only thing that says "something was awake", and is shown next to the
    patterns so nobody reads a gap as a finding.
    """
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        beats = pd.read_sql_query(
            "SELECT timestamp FROM heartbeat"
            " WHERE timestamp >= now() - interval '%d days'"
            " ORDER BY timestamp" % days, conn)
    finally:
        conn.close()
    if beats.empty:
        return 0.0, days * 24.0
    stamps = pd.to_datetime(beats["timestamp"], utc=True)
    # The loop beats every five minutes, so each beat vouches for the ten
    # minutes around it and no more. Counting distinct ten-minute windows
    # rather than beats means a loop restarting in circles cannot inflate it.
    #
    # Counted in elapsed seconds, not in epoch integers. That shortcut has now
    # produced a wrong answer three times in this file: pandas 3 converts a
    # timestamp series to int64 in MICROseconds while Timestamp.value is
    # nanoseconds, so dividing by a nanosecond constant silently collapses
    # everything into one bucket. Seventy hours of coverage came out as
    # eighteen minutes, and nothing raised.
    elapsed = (stamps - stamps.min()).dt.total_seconds()
    windows = (elapsed // 600).nunique()
    return windows * 10.0 / 60.0, days * 24.0


@st.cache_data(ttl=60)
def load_history(days=28):
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        df = pd.read_sql_query(
            "SELECT timestamp, room, status, people FROM room_events"
            " WHERE timestamp >= now() - interval '%d days'"
            " ORDER BY room, timestamp" % days, conn)
    finally:
        conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


# ------------------------------------------------------------------ wording

def to_local(series):
    """Series.tz_convert converts the index; the values need .dt."""
    return series.dt.tz_convert("Asia/Karachi")


def minutes_since(when, now):
    if pd.isna(when):
        return None
    return (now - when).total_seconds() / 60.0


def spell(minutes):
    """Forty-five minutes reads as a number; three hours should not."""
    if minutes is None:
        return "—"
    minutes = int(minutes)
    if minutes < 60:
        return "%d min" % minutes
    hours, rest = divmod(minutes, 60)
    return "%dh" % hours if rest == 0 else "%dh %02dm" % (hours, rest)


def run_started(recent, room, now):
    """When the room's present state began.

    Every change is a row, including a change in how many people are in the
    room, so a room occupied all afternoon has many consecutive occupied rows.
    The start of the state is the first of that run, not the last.
    """
    mine = recent[recent["room"] == room].sort_values("timestamp")
    if mine.empty:
        return pd.NaT
    statuses = mine["status"].tolist()
    stamps = mine["timestamp"].tolist()
    started, current = stamps[-1], statuses[-1]
    for index in range(len(statuses) - 2, -1, -1):
        if statuses[index] != current:
            break
        started = stamps[index]
    return started


def grade(row, now, hours=None):
    """Colour, headline and the line under it, from occupancy and the unit.

    Four outcomes rather than three once a unit has been calibrated:

      unit on, people           in use, nothing to do
      unit on, empty a while    waste, and that is the whole point
      unit off, empty           ideal -- and emphatically not a room to send
                                anybody to, which the old rule did
      unit off, people a while  the opposite problem: somebody sitting in a
                                room whose cooling is off, which nobody hears
                                about until they complain

    Where the unit has not been calibrated its state is None and the first
    pair collapse into the old behaviour, which is what every room does today.
    """
    if row["status"] == "unknown" or pd.isna(row["status"]):
        if pd.isna(row["timestamp"]):
            return "Fault", "Not sampled", "the loop has not reached it"
        return "Fault", "No answer", "camera did not reply"

    unit = row["ac_state"] if pd.notna(row.get("ac_state")) else None

    if row["status"] == "occupied":
        people = int(row["people"]) if pd.notna(row["people"]) else 0
        headline = "%d in here" % people
        if unit == "off" and row.get("has_unit"):
            sitting = minutes_since(row.get("occupied_since"), now)
            if sitting is not None and sitting >= COLD_AFTER_MINUTES:
                return "Cool", headline, ("unit off for %s \u2014 faulty, or"
                                          " nobody switched it on"
                                          % spell(sitting))
        return "Green", headline, row["caption"]

    empty = minutes_since(row["empty_since"], now)
    if unit == "off":
        # Empty and already off. Sending somebody to check this room is the
        # one thing this system must not do: it is the room that got it right.
        return "Green", "Empty %s" % spell(empty), "unit already off"
    headline = "Empty %s" % spell(empty)
    # The same wait the loop uses, from the same file, so this page and the
    # alerts can never disagree about which rooms want attention.
    threshold = wait_before_reporting(row["empty_after"], now, hours)
    if not threshold or empty is None:
        return "Green", headline, row["caption"]
    if empty >= threshold * 2:
        return "Red", headline, "long past %d min — check the AC" % threshold
    if empty >= threshold:
        return "Amber", headline, "past %d min — check the AC" % threshold
    return "Green", headline, row["caption"]


# ------------------------------------------------------------------ drawing

PERSON = ('<g transform="translate({x},{y})" fill="{c}">'
          '<circle cx="5" cy="5" r="4.6"/>'
          '<path d="M5 11C1.7 11 0 13.6 0 17.2V26h10v-8.8C10 13.6 8.3 11 5 11z"/>'
          '</g>')

SLOT_INK = {"occupied": "#84CC16", "empty": "#2B343B", "unknown": "#49555D"}
NO_DATA = "#1B2228"


def slot_states(recent, room, now, hours=STRIP_HOURS, slots=STRIP_SLOTS,
                since=None):
    """What each five-minute slot of the window held, oldest first.

    One source of truth: the strip under a room and the hours counted up at
    the top are the same arithmetic, so they cannot drift apart and start
    telling different stories about the same afternoon.
    """
    mine = recent[recent["room"] == room]
    if mine.empty:
        return [None] * slots
    start = since if since is not None else now - pd.Timedelta(hours=hours)
    states = mine["status"].tolist()
    # Seconds from the window start on both sides. Doing this in epoch
    # integers looks tidier and is a trap: in pandas 3 a Series of timestamps
    # converts to int64 in microseconds while Timestamp.value is nanoseconds,
    # so the two scales differ by a thousand. Nothing raises -- every mark
    # lands past every event, every slot takes the last known state, and the
    # strip comes out one convincing block of a single colour. A wrong picture
    # that looks right is worse than one that fails.
    stamps = (mine["timestamp"] - start).dt.total_seconds().to_numpy()
    span = (now - start).total_seconds()
    marks = np.linspace(0, span, slots, endpoint=False)
    where = np.searchsorted(stamps, marks, side="right") - 1
    return [None if i < 0 else states[i] for i in where]


def strip_svg(slots, height=7, radius=3):
    rects = "".join(
        '<rect x="%d" y="0" width="1" height="6" fill="%s"/>'
        % (slot, SLOT_INK.get(state, NO_DATA))
        for slot, state in enumerate(slots))
    return ('<svg viewBox="0 0 %d 6" preserveAspectRatio="none" '
            'style="width:100%%;height:%dpx;border-radius:%dpx;display:block;">'
            '%s</svg>' % (len(slots), height, radius, rects))


def status_minutes(recent, room, start, now):
    """Minutes spent in each state inside a window, by the clock.

    The strips count five-minute slots, which is right for drawing and wrong
    for arithmetic: a room occupied for seven minutes rounds to five or ten
    depending on where the boundaries fall, and that error accumulates across
    thirty rooms and a day. Figures that get multiplied into kilowatt-hours and
    rupees are measured from the events themselves.
    """
    mine = recent[recent["room"] == room].sort_values("timestamp")
    if mine.empty:
        return {}
    edges = list(mine["timestamp"]) + [now]
    totals = {}
    for index, state in enumerate(mine["status"]):
        began, ended = max(edges[index], start), edges[index + 1]
        if ended <= began:
            continue
        totals[state] = totals.get(state, 0.0) + \
            (ended - began).total_seconds() / 60.0
    return totals


def crowd(count, colour, floor, left=44, step=19, room_width=248):
    """People standing on the floor of a drawn room.

    Past a point figures stop being countable and become a texture, so the
    rest become a number. The cut-off is how many fit rather than a round
    number: a crowded room should still look crowded.
    """
    if count <= 0:
        return ""
    fits = max(1, int((room_width - left - 28) // step))
    shown = min(count, fits)
    parts = [PERSON.format(x=left + i * step, y=floor - 26, c=colour)
             for i in range(shown)]
    if count > shown:
        parts.append('<text x="%d" y="%d" font-size="12" font-weight="700"'
                     ' fill="%s" opacity=".8">+%d</text>'
                     % (left + shown * step + 2, floor - 6, colour,
                        count - shown))
    return "".join(parts)


def wall_unit(state, colour, x=176, y=22):
    """The air conditioner, on the wall where it actually hangs.

    Three states, and the third is the honest one today: nothing has been
    calibrated, so every unit is unknown. Drawing unknown the same as off would
    hang a confident claim on the wall with no measurement behind it.
    """
    if state == "on":
        return ('<g transform="translate(%d,%d)">'
                '<ellipse cx="29" cy="31" rx="36" ry="21" fill="#84CC16"'
                ' opacity=".12"/>'
                '<rect x="0" y="0" width="58" height="17" rx="4" fill="#1A222A"'
                ' stroke="#84CC16" stroke-width="2"/>'
                '<line x1="5" y1="12" x2="53" y2="12" stroke="#84CC16"'
                ' stroke-width="1.6"/>'
                '<circle cx="51" cy="5.5" r="2.1" fill="#84CC16"/>'
                '<path d="M12 25q5 5 10 0t10 0t10 0" fill="none"'
                ' stroke="#84CC16" stroke-width="2" stroke-linecap="round"'
                ' opacity=".8"/>'
                '<path d="M16 33q5 4 10 0t10 0" fill="none" stroke="#84CC16"'
                ' stroke-width="1.8" stroke-linecap="round" opacity=".45"/>'
                '</g>' % (x, y))
    if state == "off":
        return ('<g transform="translate(%d,%d)" opacity=".7">'
                '<rect x="0" y="0" width="58" height="17" rx="4" fill="#1A222A"'
                ' stroke="#6B7780" stroke-width="2"/>'
                '<line x1="5" y1="12" x2="53" y2="12" stroke="#6B7780"'
                ' stroke-width="1.6"/>'
                '<circle cx="51" cy="5.5" r="2.1" fill="none" stroke="#6B7780"'
                ' stroke-width="1.4"/></g>' % (x, y))
    return ('<g transform="translate(%d,%d)" opacity=".42">'
            '<rect x="0" y="0" width="58" height="17" rx="4" fill="none"'
            ' stroke="%s" stroke-width="1.8" stroke-dasharray="4 3"/>'
            '<text x="24" y="13" font-size="12" font-weight="700" fill="%s">?'
            '</text></g>' % (x, y, colour, colour))


def drawn_room(row, ink):
    people = int(row["people"]) if pd.notna(row["people"]) else 0
    if row["status"] != "occupied":
        people = 0
    state = row["ac_state"] if pd.notna(row["ac_state"]) else None
    floor = 96
    empty_label = "" if people else (
        '<text x="46" y="%d" font-size="11.5" fill="%s" opacity=".38"'
        ' letter-spacing="1.8">EMPTY</text>' % (floor - 8, ink["fg"]))
    return """
<svg viewBox="0 0 260 112" style="width:100%%;height:auto;display:block;">
  <rect x="4" y="6" width="252" height="100" rx="11" fill="#1A222A"
        fill-opacity=".6" stroke="%s" stroke-width="1.6"/>
  <line x1="14" y1="%d" x2="246" y2="%d" stroke="%s" stroke-width="2.4"
        stroke-linecap="round"/>
  <path d="M20 %d V34 a13 13 0 0 1 13-13" fill="none" stroke="%s"
        stroke-width="1.8" stroke-linecap="round" opacity=".75"/>
  %s %s %s
</svg>""" % (ink["edge"], floor, floor, ink["edge"], floor, ink["edge"],
             wall_unit(state, ink["fg"]), crowd(people, ink["fg"], floor),
             empty_label)


def linked(html, room):
    """Make a card open that room below.

    Streamlit cannot attach a click handler to raw HTML, but it does read the
    query string, so the card becomes a link to this same page carrying the
    room's name. Clicking reloads and the detail panel opens on it, which is
    what clicking a room is supposed to do.
    """
    # The anchor matters as much as the query string. Without it the page
    # reloads with the room selected and the reader sees nothing happen,
    # because the panel that changed is further down than they are looking.
    return ('<a href="?room=%s#roomdetail" style="text-decoration:none;'
            'display:contents;">%s</a>' % (quote(room), html))


def room_card(row, recent, now):
    """A room with a unit in it. These are the ones that can cost money."""
    ink = INK[row["level"]]
    badge = ""
    if row["level"] in ("Red", "Amber"):
        badge = ('<span style="background:%s;color:#fff;font-size:.58rem;'
                 'font-weight:800;letter-spacing:.09em;padding:3px 8px;'
                 'border-radius:10px;">ACTION</span>' % ink["fg"])
    return """
<div style="flex:1 1 280px;max-width:340px;background:%s;border:1px solid %s;
            border-top:4px solid %s;border-radius:13px;padding:13px 15px 14px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:1.02rem;font-weight:680;color:%s;">%s</span>%s
  </div>
  <div style="font-size:.6rem;letter-spacing:.11em;color:%s;opacity:.55;
              margin-bottom:2px;">%s &middot; %s</div>
  %s
  <div style="display:flex;justify-content:space-between;align-items:baseline;
              margin-top:5px;">
    <span style="font-size:1.3rem;font-weight:760;color:%s;">%s</span>
    <span style="font-size:.7rem;color:%s;opacity:.6;">%s</span>
  </div>
  <div style="font-size:.78rem;color:%s;opacity:.85;">%s</div>
  <div style="margin-top:9px;">%s</div>
</div>""" % (ink["bg"], ink["edge"], ink["fg"], ink["fg"], row["room"], badge,
             ink["fg"], row["zone"].upper(), row["unit_note"],
             drawn_room(row, ink), ink["fg"], row["headline"], ink["fg"],
             row["age"], ink["fg"], row["sub"],
             strip_svg(row["slots"]))


def lane(row):
    """A room with no unit. The question is when it is used, not what it is now.

    So the eight-hour band is the content here rather than a footnote, and no
    room is drawn: a picture of an empty corridor answers nothing anybody
    would ask about a corridor.
    """
    ink = INK[row["level"]]
    people = int(row["people"]) if pd.notna(row["people"]) else 0
    if row["status"] == "occupied" and people:
        shown = min(people, 6)
        now_cell = ('<svg width="%d" height="14" viewBox="0 0 %d 26">%s</svg>'
                    % (shown * 8, shown * 14, "".join(
                        PERSON.format(x=i * 14, y=0, c="#A4D463")
                        for i in range(shown))))
        if people > shown:
            now_cell += ('<span style="font-size:.68rem;color:#A4D463;">+%d'
                         '</span>' % (people - shown))
    elif row["status"] == "unknown":
        now_cell = ('<span style="font-size:.68rem;color:#8A8A8A;">no answer'
                    '</span>')
    else:
        now_cell = ('<span style="font-size:.68rem;color:#7E888E;">%s</span>'
                    % row["headline"].replace("Empty ", ""))
    return """
<div style="display:flex;align-items:center;gap:12px;padding:5px 2px;
            border-bottom:1px solid #263139;">
  <span style="flex:0 0 160px;font-size:.81rem;color:%s;white-space:nowrap;
               overflow:hidden;text-overflow:ellipsis;">%s</span>
  <span style="flex:1 1 auto;">%s</span>
  <span style="flex:0 0 86px;text-align:right;display:flex;
               justify-content:flex-end;align-items:center;gap:3px;">%s</span>
</div>""" % (ink["fg"], row["room"], strip_svg(row["slots"], height=11,
                                              radius=2), now_cell)


def hour_axis(now):
    """Hour marks under the lanes, so a band can be read as a time of day."""
    start = (now - pd.Timedelta(hours=STRIP_HOURS)).tz_convert("Asia/Karachi")
    ticks = []
    for step in range(0, STRIP_HOURS + 1, 2):
        when = start + pd.Timedelta(hours=step)
        ticks.append('<span style="flex:1 1 0;text-align:%s;">%s</span>'
                     % ("left" if step == 0 else
                        ("right" if step == STRIP_HOURS else "center"),
                        when.strftime("%H:%M")))
    return ('<div style="display:flex;align-items:center;gap:12px;'
            'padding:2px 2px 0;">'
            '<span style="flex:0 0 160px;"></span>'
            '<span style="flex:1 1 auto;display:flex;font-size:.62rem;'
            'color:#7E888E;">%s</span>'
            '<span style="flex:0 0 86px;text-align:right;font-size:.62rem;'
            'color:#7E888E;">now</span></div>'
            % "".join(ticks))


def day_axis(now, since, step=4):
    start = since.tz_convert("Asia/Karachi")
    hours = max(1, int(round((now - since).total_seconds() / 3600)))
    step = max(1, step if hours > step * 2 else max(1, hours // 4))
    marks = list(range(0, hours, step)) + [hours]
    ticks = "".join(
        '<span style="flex:1 1 0;text-align:%s;">%s</span>'
        % ("left" if at == 0 else ("right" if at == hours else "center"),
           (start + pd.Timedelta(hours=at)).strftime("%H:%M"))
        for at in marks)
    return ('<div style="display:flex;font-size:.64rem;color:#7E888E;'
            'margin-top:3px;">%s</div>' % ticks)


def ac_pill(row):
    """The unit's state in the width of a word.

    A room with no unit gets a blank rather than "OFF": there is nothing in it
    to be off, and a column of OFF against the stairwells would read as
    thirteen units somebody had remembered to switch off.
    """
    if not row["has_unit"]:
        return '<span style="color:#4A555C;font-size:.66rem;">\u2014</span>'
    state = row["ac_state"] if pd.notna(row["ac_state"]) else None
    look = {
        "on": ("AC ON", "#1A222A", "#84CC16", "#84CC16", "solid"),
        "off": ("AC OFF", "#1A222A", "#6B7780", "#6B7780", "solid"),
    }.get(state, ("AC ?", "#1A222A", "#AEB4B8", "#AEB4B8", "dashed"))
    label, ink, border, text, style = look
    fill = "#84CC16" if state == "on" else "#1A222A"
    return ('<span style="font-size:.6rem;font-weight:800;letter-spacing:.04em;'
            'padding:2px 6px;border-radius:9px;border:1.3px %s %s;'
            'background:%s;color:%s;white-space:nowrap;">%s</span>'
            % (style, border, fill, ink if state == "on" else text, label))


def status_row(row):
    """One room, one line: who is in it, what its unit is doing, its day."""
    ink = INK[row["level"]]
    people = int(row["people"]) if pd.notna(row["people"]) else 0
    if row["status"] == "occupied" and people:
        shown = min(people, 5)
        who = ('<svg width="%d" height="13" viewBox="0 0 %d 26">%s</svg>'
               '<span style="font-size:.72rem;font-weight:700;color:%s;">'
               '&nbsp;%d</span>'
               % (shown * 7, shown * 13, "".join(
                   PERSON.format(x=i * 13, y=0, c=ink["fg"])
                   for i in range(shown)), ink["fg"], people))
    elif row["status"] == "unknown":
        who = '<span style="font-size:.7rem;color:#8A8A8A;">no answer</span>'
    else:
        who = ('<span style="font-size:.72rem;color:%s;">%s</span>'
               % (ink["fg"], row["headline"].replace("Empty ", "")))
    return """
<div style="display:flex;align-items:center;gap:9px;padding:5px 8px;
            border-radius:7px;background:%s;margin-bottom:4px;">
  <span style="flex:0 0 7px;height:7px;border-radius:50%%;background:%s;
               display:inline-block;"></span>
  <span style="flex:0 0 150px;font-size:.78rem;color:%s;white-space:nowrap;
               overflow:hidden;text-overflow:ellipsis;">%s</span>
  <span style="flex:0 0 78px;display:flex;align-items:center;">%s</span>
  <span style="flex:0 0 58px;">%s</span>
  <span style="flex:1 1 auto;min-width:60px;">%s</span>
</div>""" % (ink["bg"] if row["level"] != "Green" else "#141A14",
             ink["bar"], ink["fg"], row["room"], who, ac_pill(row),
             strip_svg(row["slots"], height=9, radius=2))


def building_bar(df):
    """Every room as one square: the campus settled before anyone scrolls."""
    return "".join(
        '<span title="%s &mdash; %s" style="width:17px;height:17px;'
        'border-radius:4px;background:%s;opacity:%s;display:inline-block;">'
        '</span>'
        % (row["room"], row["headline"], INK[row["level"]]["bar"],
           "1" if row["level"] != "Green" else ".34")
        for _, row in df.iterrows())


def money_strip(at_stake, saved, span, enough):
    """Two figures, in the corner, with what each one actually is.

    The left is an upper bound and says so on the tile: the empty time is
    measured, whether the units ran is not. The right is a real difference or
    it is nothing, and when it is nothing it says how many days short it is
    rather than printing a zero that could be read as "we saved nothing".
    """
    if enough:
        right = ("Rs %s" % format(abs(round(saved)), ","),
                 "less than the first fortnight" if saved >= 0
                 else "MORE than the first fortnight")
    else:
        right = ("%d more days" % max(1, round(BASELINE_DAYS * 2 - span)),
                 "before a fortnight can be compared")
    return """
<div style="display:flex;gap:18px;">
  <div style="text-align:right;">
    <div style="color:#6E7B82;font-size:.56rem;letter-spacing:.14em;">
      AT STAKE TODAY</div>
    <div style="color:#F0C98B;font-size:1.34rem;font-weight:760;
                line-height:1.15;">Rs %s</div>
    <div style="color:#5E6A70;font-size:.58rem;">upper bound, not a bill</div>
  </div>
  <div style="width:1px;background:#2A3034;"></div>
  <div style="text-align:right;">
    <div style="color:#6E7B82;font-size:.56rem;letter-spacing:.14em;">
      SAVED SO FAR</div>
    <div style="color:%s;font-size:1.34rem;font-weight:760;line-height:1.15;">
      %s</div>
    <div style="color:#5E6A70;font-size:.58rem;">%s</div>
  </div>
</div>""" % (format(round(at_stake), ","),
             "#8FD48A" if enough and saved >= 0 else "#6E7B82",
             right[0], right[1])


def header_band(campus, df, beat_age, mode="", money_html=""):
    live = (beat_age is not None and beat_age <= STALE_AFTER_MINUTES)
    pill = ('<span style="background:%s;color:%s;font-size:.73rem;'
            'padding:5px 12px;border-radius:20px;white-space:nowrap;">'
            '%s</span>'
            % ("#1F3B22" if live else "#4A2020",
               "#8FD48A" if live else "#F0A5A5",
               ("&#9679; live &middot; reported %s ago" % spell(beat_age))
               if live else ("&#9679; silent for %s" % spell(beat_age))))
    return """
<div style="background:#0F1418;border:1px solid #1E262C;border-radius:14px;
            padding:16px 20px 14px;margin-bottom:14px;">
  <div style="display:flex;justify-content:space-between;align-items:center;
              flex-wrap:wrap;gap:10px;">
    <div>
      <span style="color:#6E7B82;font-size:.64rem;letter-spacing:.22em;">
        ENERGYCAM</span>
      <div style="color:#F2F4F5;font-size:1.72rem;font-weight:760;
                  line-height:1.1;">%s</div>
    </div>
    <div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap;">
      %s%s</div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:13px;">%s</div>
  <div style="color:#5E6A70;font-size:.63rem;margin-top:9px;">
    one square per room &middot; %d rooms &middot; %d cameras%s</div>
</div>""" % (campus, money_html, pill, building_bar(df), len(df),
             int(df["cameras"].sum()),
             (" &middot; %s" % mode) if mode else "")


def figure_row(label, value, note, tone="#E6EAED"):
    return """
<div style="flex:1 1 180px;background:#151C22;border:1px solid #263139;
            border-radius:11px;padding:11px 14px;">
  <div style="font-size:.68rem;color:#8A949A;letter-spacing:.04em;">%s</div>
  <div style="font-size:1.62rem;font-weight:760;color:%s;line-height:1.25;">
    %s</div>
  <div style="font-size:.66rem;color:#7E888E;">%s</div>
</div>""" % (label, tone, value, note)


# ------------------------------------------------------------------- views

def hour_pattern(week, room, now, days=7):
    """For each hour of the day, on what share of days was this room in use?

    Sampled at the middle of every hour of every day rather than counted from
    events, because only changes are recorded: a room occupied from nine to six
    leaves two rows, and counting rows would call it busy twice and idle for
    the other seven hours. Sampling asks the state, which is the question.
    """
    mine = week[week["room"] == room]
    if mine.empty:
        return [None] * 24, 0
    start = (now - pd.Timedelta(days=days)).normalize()
    stamps = (mine["timestamp"] - start).dt.total_seconds().to_numpy()
    states = mine["status"].tolist()
    local_offset = 5 * 3600          # Pakistan, fixed, no daylight saving
    counted = [0] * 24
    busy = [0] * 24
    for day in range(days):
        for hour in range(24):
            # middle of that hour, in local time, expressed as seconds since
            # the window began
            at = day * 86400 + hour * 3600 + 1800 - local_offset
            if at < 0 or at > (now - start).total_seconds():
                continue
            index = int(np.searchsorted(stamps, at, side="right")) - 1
            if index < 0:
                continue
            counted[hour] += 1
            if states[index] == "occupied":
                busy[hour] += 1
    share = [None if counted[h] == 0 else busy[h] / counted[h]
             for h in range(24)]
    return share, max(counted)


def pattern_row(name, share, fg):
    cells = "".join(
        '<span title="%02d:00" style="flex:1 1 0;height:15px;border-radius:2px;'
        'background:%s;"></span>'
        % (hour, "#1B2228" if value is None else
           "rgba(107,163,61,%.2f)" % (0.10 + 0.90 * value))
        for hour, value in enumerate(share))
    return ('<div style="display:flex;align-items:center;gap:8px;'
            'margin-bottom:3px;">'
            '<span style="flex:0 0 140px;font-size:.74rem;color:%s;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">%s'
            '</span><span style="flex:1 1 auto;display:flex;gap:1px;">%s</span>'
            '</div>' % (fg, name, cells))


def settles_at(share, from_hour=12):
    """The hour after which a room is reliably empty, or None if it never is.

    "Reliably" is under one day in five. A room used on two afternoons out of
    seven has no switch-off time worth setting, and saying otherwise would get
    somebody's air conditioning turned off while they were sitting under it.
    """
    last = None
    for hour in range(23, from_hour - 1, -1):
        if share[hour] is None:
            continue
        if share[hour] >= 0.2:
            return hour + 1 if hour < 23 else None
        last = hour
    return last if last is not None else None


BASELINE_DAYS = 14          # a fortnight before, a fortnight after


def wasted_minutes(events, rooms, since, until):
    """Empty minutes across a set of rooms, between two moments."""
    return sum(status_minutes(events, room, since, until).get("empty", 0.0)
               for room in rooms)


def money(minutes, assumptions):
    kwh = minutes / 60.0 * assumptions.get("unit_kw", 1.2)
    return kwh, kwh * assumptions.get("tariff_rs_per_kwh", 55)


def against_baseline(history, rooms, now, assumptions):
    """Compare the last fortnight with the fortnight before it.

    This is the only honest route to a saving. A saving is a difference, and a
    difference needs a before: without one, any figure put under the word
    "saved" is a guess wearing a number's clothes. So the first fortnight
    becomes the baseline and every fortnight after is measured against it.

    Returns (rupees, days_of_history, enough). Until there are two fortnights
    it returns how far off that is, and the page says so rather than showing a
    zero that looks like failure or a figure that looks like success.
    """
    if history.empty:
        return 0.0, 0, False
    span = (now - history["timestamp"].min()).total_seconds() / 86400.0
    if span < BASELINE_DAYS * 2:
        return 0.0, span, False
    cut = now - pd.Timedelta(days=BASELINE_DAYS)
    before = wasted_minutes(history, rooms, cut - pd.Timedelta(days=BASELINE_DAYS), cut)
    after = wasted_minutes(history, rooms, cut, now)
    return money(before - after, assumptions)[1], span, True


def show_room_day(df, recent, chosen, now):
    """One room: today in detail, then its habits over the week."""
    row = df[df["room"] == chosen].iloc[0]

    # Midnight, not twenty-four hours back. "When does the first person
    # arrive" is a question about a day, and a rolling window answered it with
    # yesterday evening. Early in the morning the band is short, which is
    # honest: the day is short.
    midnight = now.tz_convert("Asia/Karachi").normalize().tz_convert("UTC")
    hours_today = max(1.0, (now - midnight).total_seconds() / 3600.0)
    day = status_minutes(recent, chosen, midnight, now)
    mine = recent[(recent["room"] == chosen) & (recent["timestamp"] >= midnight)]
    busy = mine[mine["status"] == "occupied"]

    if busy.empty:
        peak, peak_at, first_at, last_at = "—", "nobody seen", "—", "—"
    else:
        top = busy["people"].idxmax()
        peak = int(busy.loc[top, "people"])
        peak_at = "at %s" % to_local(
            busy.loc[[top], "timestamp"]).iloc[0].strftime("%H:%M")
        first_at = to_local(busy["timestamp"]).min().strftime("%H:%M")

        # Only changes are recorded, so the last "occupied" row is when the
        # count last moved, not when the room emptied. Somebody who arrived at
        # 09:25 and left at 17:40 leaves one occupied row, at 09:25, and
        # reporting that as "last seen" takes eight hours off their day. What
        # is wanted is the row after it. If nothing follows, they are still in.
        ordered = mine.sort_values("timestamp").reset_index(drop=True)
        last_busy = ordered.index[ordered["status"] == "occupied"].max()
        last_at = (to_local(ordered.loc[[last_busy + 1], "timestamp"])
                   .iloc[0].strftime("%H:%M")
                   if last_busy + 1 < len(ordered) else "still in use")

    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:10px;'
        'margin-bottom:8px;"><span style="font-size:1.1rem;font-weight:720;">'
        '%s</span><span style="font-size:.72rem;color:#8A949A;">%s &middot; %s'
        ' &middot; %d camera%s</span></div>'
        % (chosen, row["zone"], row["unit_note"], row["cameras"],
           "" if row["cameras"] == 1 else "s"), unsafe_allow_html=True)

    st.markdown(
        '<div style="display:flex;gap:11px;flex-wrap:wrap;margin:2px 0 12px;">'
        '%s%s%s%s%s</div>' % (
            figure_row("First seen", first_at, "earliest person since midnight"),
            figure_row("Emptied at", last_at, "after the last person left"),
            figure_row("Most at once", peak, peak_at),
            figure_row("Used today", spell(day.get("occupied", 0.0)),
                       "empty %s" % spell(day.get("empty", 0.0))),
            figure_row("Unaccounted", spell(day.get("unknown", 0.0)),
                       "camera did not answer")), unsafe_allow_html=True)

    st.markdown(
        strip_svg(slot_states(recent, chosen, now, slots=int(hours_today * 12),
                              since=midnight), height=26, radius=5)
        + day_axis(now, midnight), unsafe_allow_html=True)

    if not busy.empty:
        by_hour = busy.copy()
        by_hour["hour"] = to_local(by_hour["timestamp"]).dt.strftime("%H:00")
        peaks = by_hour.groupby("hour")["people"].max().reset_index()
        chart = px.bar(peaks, x="hour", y="people",
                       labels={"hour": "", "people": "people"},
                       color_discrete_sequence=["#84CC16"])
        chart.update_layout(height=215, margin=dict(l=0, r=0, t=16, b=0),
                            plot_bgcolor="#1A222A", showlegend=False,
                            yaxis=dict(gridcolor="#263139"))
        st.plotly_chart(chart, use_container_width=True)
        st.caption("The most people seen at once in each hour. Readings are a"
                   " couple of minutes apart, so a visit shorter than that can"
                   " fall between two and leave no mark.")

    # ---- and the same room's habits ---------------------------------------
    # One day is an anecdote. A switch-off time or a cleaning round gets
    # planned against when a room usually empties, not against yesterday.
    try:
        week = load_history()
    except psycopg2.Error:
        week = pd.DataFrame()
    if week.empty:
        return
    theirs = week[(week["room"] == chosen) &
                  (week["status"] == "occupied")].copy()
    if theirs.empty:
        return
    theirs["when"] = to_local(theirs["timestamp"])
    theirs["day"] = theirs["when"].dt.date
    theirs["minute"] = theirs["when"].dt.hour * 60 + theirs["when"].dt.minute
    by_day = theirs.groupby("day").agg(
        arrives=("minute", "min"), leaves=("minute", "max"),
        busiest=("people", "max")).reset_index()
    if len(by_day) < 2:
        st.caption("Only one day recorded so far — a usual pattern needs"
                   " a few more before it means anything.")
        return
    clock = lambda m: "%02d:%02d" % divmod(int(round(m)), 60)
    st.markdown(
        '<div style="font-size:.84rem;font-weight:650;margin:16px 0 6px;">'
        'On a usual day <span style="font-weight:400;color:#8A949A;">'
        '(%d days recorded)</span></div>'
        '<div style="display:flex;gap:11px;flex-wrap:wrap;">%s%s%s</div>'
        % (len(by_day),
           figure_row("First arrival", clock(by_day["arrives"].mean()),
                      "earliest %s" % clock(by_day["arrives"].min())),
           figure_row("Last to leave", clock(by_day["leaves"].mean()),
                      "latest %s" % clock(by_day["leaves"].max())),
           figure_row("Busiest it gets", int(by_day["busiest"].max()),
                      "typically %d" % round(by_day["busiest"].mean()))),
        unsafe_allow_html=True)


def daily_spans(month, wanted, now):
    """Per room and day: when the first person arrived and when it emptied.

    The departure cannot come from the occupied rows. Only changes are
    recorded, so a room used from ten to six leaves one occupied row at ten,
    and taking the last of those as the departure collapses the whole day to a
    single minute. It has to be the row AFTER the last occupied one -- the
    moment the room went empty.

    Spotted because the bars on this page came out a pixel wide. The same
    mistake was already fixed on one room's own page and not here, which is
    what happens when the same idea is written twice.
    """
    spans = []
    wanted = set(wanted)
    for room, events in month[month["room"].isin(wanted)].groupby("room"):
        events = events.sort_values("timestamp").reset_index(drop=True)
        local = to_local(events["timestamp"])
        days = local.dt.date
        for day, rows in events.groupby(days.values).groups.items():
            rows = sorted(rows)
            busy = [i for i in rows if events.loc[i, "status"] == "occupied"]
            if not busy:
                continue
            arrives = local.iloc[busy[0]]
            after = busy[-1] + 1
            if after < len(events):
                left = local.iloc[after]
            else:
                # Nothing recorded after it: still in use as far as we know.
                left = min(to_local(pd.Series([now])).iloc[0],
                           arrives.normalize() + pd.Timedelta(hours=23,
                                                              minutes=59))
            # Somebody staying past midnight belongs to the day they arrived,
            # but the bar is drawn on a 24-hour scale, so it stops at the end
            # of it rather than wrapping round to the start.
            end_of_day = arrives.normalize() + pd.Timedelta(hours=23, minutes=59)
            left = min(left, end_of_day)
            spans.append({
                "room": room, "day": day,
                "arrives": arrives.hour * 60 + arrives.minute,
                "leaves": max(left.hour * 60 + left.minute,
                              arrives.hour * 60 + arrives.minute),
                "busiest": int(events.loc[busy, "people"].max())})
    return pd.DataFrame(spans)


def show_arrivals(df, now):
    """When each room fills and empties, on a usual day.

    Asked for as "which department comes when". It is the same arithmetic as
    one room's weekly habit, run across all of them and sorted, and it is the
    thing that makes a switch-off time arguable rather than asserted: a room
    whose last person leaves at 18:40 four days out of five does not need a
    debate about when to set the timer.
    """
    try:
        month = load_history()
    except psycopg2.Error as e:
        st.error("Could not load history (%s)." % type(e).__name__)
        return
    if month.empty:
        st.info("No history yet.")
        return

    per_day = daily_spans(month, set(df["room"]), now)
    if per_day.empty:
        st.info("Nobody has been seen in any room yet.")
        return
    usual = per_day.groupby("room").agg(
        days=("day", "nunique"),
        first=("arrives", "mean"), earliest=("arrives", "min"),
        last=("leaves", "mean"), latest=("leaves", "max"),
        busiest=("busiest", "max")).reset_index()
    usual = usual.merge(df[["room", "zone", "has_unit", "level"]], on="room")
    usual = usual.sort_values("first")

    clock = lambda m: "%02d:%02d" % divmod(int(round(m)), 60)
    st.markdown(
        '<div style="font-size:1.1rem;font-weight:720;margin-bottom:2px;">'
        'Who comes when</div>'
        '<div style="font-size:.74rem;color:#8A949A;margin-bottom:10px;">'
        'averaged over the days each room has been watched, earliest first'
        '</div>', unsafe_allow_html=True)

    # Each room as a bar from its usual arrival to its usual departure, so the
    # shape of the building's day is visible before any of the times are read.
    rows_html = ""
    for _, r in usual.iterrows():
        left = 100.0 * r["first"] / 1440.0
        width = max(1.2, 100.0 * (r["last"] - r["first"]) / 1440.0)
        rows_html += (
            '<div style="display:flex;align-items:center;gap:9px;'
            'margin-bottom:4px;">'
            '<span style="flex:0 0 146px;font-size:.76rem;color:%s;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">%s'
            '</span>'
            '<span style="flex:0 0 46px;font-size:.72rem;color:#8A949A;'
            'text-align:right;">%s</span>'
            '<span style="flex:1 1 auto;height:14px;background:#1B2228;'
            'border-radius:3px;position:relative;">'
            '<span style="position:absolute;left:%.2f%%;width:%.2f%%;top:0;'
            'height:14px;background:%s;border-radius:3px;"></span></span>'
            '<span style="flex:0 0 46px;font-size:.72rem;color:#8A949A;">%s'
            '</span>'
            '<span style="flex:0 0 74px;font-size:.68rem;color:#7E888E;'
            'text-align:right;">%d day%s</span></div>'
            % (INK[r["level"]]["fg"], r["room"], clock(r["first"]),
               left, width, "#84CC16" if r["has_unit"] else "#3B464D",
               clock(r["last"]), r["days"], "" if r["days"] == 1 else "s"))
    ticks = "".join('<span style="flex:1 1 0;text-align:center;">%s</span>'
                    % (("%02d" % h) if h % 3 == 0 else "") for h in range(24))
    st.markdown(
        rows_html +
        '<div style="display:flex;align-items:center;gap:9px;margin-top:2px;">'
        '<span style="flex:0 0 146px;"></span><span style="flex:0 0 46px;">'
        '</span><span style="flex:1 1 auto;display:flex;font-size:.6rem;'
        'color:#7E888E;">%s</span><span style="flex:0 0 46px;"></span>'
        '<span style="flex:0 0 74px;"></span></div>' % ticks,
        unsafe_allow_html=True)
    st.caption("Green bars are rooms with an air conditioner. Grey ones have"
               " none, so their hours are worth knowing and cost nothing.")

    st.markdown(
        '<div style="font-size:.84rem;font-weight:650;margin:18px 0 6px;">'
        'The same thing as numbers</div>', unsafe_allow_html=True)
    table = pd.DataFrame({
        "Room": usual["room"], "Zone": usual["zone"],
        "Usually in": usual["first"].map(clock),
        "Earliest": usual["earliest"].map(clock),
        "Usually out": usual["last"].map(clock),
        "Latest": usual["latest"].map(clock),
        "Most at once": usual["busiest"].astype(int),
        "Days watched": usual["days"].astype(int)})
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption("\u201cUsually out\u201d is when the room went empty, taken"
               " from the reading after the last person was seen. A few days"
               " of history make these averages worth reading; one day does"
               " not.")


def show_cameras(df, now):
    """Which cameras answer, and which ones do not.

    Measured from the one thing that actually says so: a room goes to
    "unknown" when a camera it depends on did not reply, and that state is
    recorded like any other. Nothing here is inferred from whether anyone was
    seen -- an empty room and a blind one look identical from the outside, and
    treating them as the same is how a dead camera turns into a quiet month of
    "nobody uses that room".
    """
    try:
        month = load_history()
    except psycopg2.Error as e:
        st.error("Could not load history (%s)." % type(e).__name__)
        return

    week_start = now - pd.Timedelta(days=7)
    rows = []
    for _, room in df.iterrows():
        mine = month[month["room"] == room["room"]].sort_values("timestamp")
        blind = status_minutes(month, room["room"], week_start, now).get(
            "unknown", 0.0)
        # Times it went silent, not rows: a camera that flaps produces a row
        # each way, and counting rows would double every outage.
        drops = 0
        previous = None
        for state in mine["status"]:
            if state == "unknown" and previous != "unknown":
                drops += 1
            previous = state
        answered = mine[mine["status"] != "unknown"]
        rows.append({
            "room": room["room"], "zone": room["zone"],
            "cameras": room["cameras"], "level": room["level"],
            "silent_now": room["status"] == "unknown",
            "blind_minutes": blind, "drops": drops,
            "last_answer": (answered["timestamp"].max()
                            if not answered.empty else pd.NaT)})
    health = pd.DataFrame(rows)

    silent = health[health["silent_now"]]
    flaky = health[(~health["silent_now"]) & (health["drops"] > 0)]
    week_minutes = 7 * 24 * 60.0
    worst = health["blind_minutes"].max()

    st.markdown(
        '<div style="display:flex;gap:11px;flex-wrap:wrap;margin-bottom:14px;">'
        '%s%s%s%s</div>' % (
            figure_row("Cameras", int(df["cameras"].sum()),
                       "across %d rooms" % len(df)),
            figure_row("Silent right now", len(silent),
                       "rooms whose camera did not reply",
                       INK["Fault"]["fg"] if len(silent) else TEXT),
            figure_row("Dropped out this week", int(health["drops"].sum()),
                       "separate outages, not readings",
                       INK["Amber"]["fg"] if health["drops"].sum() else TEXT),
            figure_row("Worst room", spell(worst) if worst else "\u2014",
                       "longest unanswered in seven days")),
        unsafe_allow_html=True)

    if not silent.empty:
        st.markdown(
            '<div style="background:%s;border:1px solid %s;border-left:5px '
            'solid %s;border-radius:11px;padding:12px 16px;margin-bottom:14px;">'
            '<div style="font-weight:680;color:%s;margin-bottom:4px;">'
            'Not answering now</div>'
            '<div style="font-size:.8rem;color:%s;">%s</div>'
            '<div style="font-size:.72rem;color:%s;margin-top:5px;">These'
            ' rooms are reported as unknown, never as empty. A camera that'
            ' stopped looking is not a room that stopped being used.</div>'
            '</div>'
            % (INK["Fault"]["bg"], INK["Fault"]["edge"], INK["Fault"]["bar"],
               INK["Fault"]["fg"], INK["Fault"]["fg"],
               ", ".join("%s (last answered %s)"
                         % (r["room"],
                            "never" if pd.isna(r["last_answer"]) else
                            "%s ago" % spell(minutes_since(r["last_answer"], now)))
                         for _, r in silent.iterrows()),
               MUTED), unsafe_allow_html=True)

    st.markdown(
        '<div style="font-size:1.1rem;font-weight:720;margin-bottom:2px;">'
        'Time unanswered, last seven days</div>'
        '<div style="font-size:.74rem;color:%s;margin-bottom:9px;">'
        'every room, worst first. A bar that is barely there is a camera doing'
        ' its job.</div>' % MUTED, unsafe_allow_html=True)

    health = health.sort_values("blind_minutes", ascending=False)
    bars = ""
    for _, r in health.iterrows():
        share = 100.0 * r["blind_minutes"] / week_minutes
        colour = (INK["Fault"]["bar"] if r["silent_now"]
                  else INK["Amber"]["bar"] if r["drops"]
                  else INK["Green"]["bar"])
        bars += (
            '<div style="display:flex;align-items:center;gap:9px;'
            'margin-bottom:4px;">'
            '<span style="flex:0 0 150px;font-size:.76rem;color:%s;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">%s'
            '</span>'
            '<span style="flex:1 1 auto;height:12px;background:%s;'
            'border-radius:3px;overflow:hidden;">'
            '<span style="display:block;height:12px;width:%.2f%%;background:%s;'
            'border-radius:3px;"></span></span>'
            '<span style="flex:0 0 86px;text-align:right;font-size:.72rem;'
            'color:%s;">%s</span>'
            '<span style="flex:0 0 78px;text-align:right;font-size:.68rem;'
            'color:%s;">%s</span></div>'
            % (INK[r["level"]]["fg"], r["room"], SUNKEN, max(share, 0.4),
               colour, MUTED,
               spell(r["blind_minutes"]) if r["blind_minutes"] else "\u2014",
               FAINT,
               "%d drop%s" % (r["drops"], "" if r["drops"] == 1 else "s")
               if r["drops"] else "steady"))
    st.markdown(bars, unsafe_allow_html=True)
    st.caption("Measured from the rooms' own recorded state, not guessed at"
               " from whether anybody was seen. Counted as separate outages"
               " rather than readings, so a camera that flaps in and out is"
               " one drop per outage. Only covers time the loop was running:"
               " a camera cannot be found silent while nothing was asking.")


def show_stills(cooled, now):
    """The walk round, without the walk.

    Ten past seven, the office emptying, somebody wants to see the rooms
    before going home. A still answers that; a video stream would not answer
    it any better and would be a far larger thing to have built.
    """
    shots = []
    if os.path.isdir(SNAPSHOT_DIR):
        for _, room in cooled.iterrows():
            safe = "".join(c if c.isalnum() else "_" for c in room["room"])
            path = os.path.join(SNAPSHOT_DIR, "%s.jpg" % safe)
            if os.path.exists(path):
                shots.append((room, path,
                              (time.time() - os.path.getmtime(path)) / 60))
    if not shots:
        st.info("No stills yet. Turn them on in rooms.yaml — set"
                " `snapshots: enabled: true` — and restart the loop."
                " Pictures are a different kind of data from counts, so this"
                " is off until somebody decides otherwise.")
        return
    st.caption("Faces, screens, keyboards and phones are blurred before the"
               " file is written — the same pass that blurs an alert"
               " snapshot. One still per room, overwritten every pass, kept on"
               " this machine and never sent to the database.")
    for start in range(0, len(shots), 4):
        for column, (room, path, age) in zip(st.columns(4),
                                             shots[start:start + 4]):
            column.image(path, use_container_width=True)
            column.markdown(
                '<div style="font-size:.78rem;font-weight:600;color:%s;'
                'margin-top:-6px;">%s</div><div style="font-size:.66rem;'
                'color:#7E888E;">%s &middot; %s</div>'
                % (INK[room["level"]]["fg"], room["room"], room["headline"],
                   "%d min old" % age if age >= 1 else "just now"),
                unsafe_allow_html=True)


def show_numbers(df, cooled, recent, now):
    """What the empty cooled-room time would amount to, and the week behind it.

    Every figure here is conditional and the page says so out loud. How long
    each air-conditioned room stood empty is measured. Whether its unit was
    running is not, because none is calibrated. So this answers "if they were
    running, how much is sitting on the table", which is the question worth
    asking before anyone spends a Saturday moving cameras, and is not the same
    claim as a saving.
    """
    assumptions = load_assumptions()
    day_start = now - pd.Timedelta(hours=DETAIL_HOURS)

    # Rooms whose cooling is a choice. The server rooms have units and are
    # empty of people nearly always, so counting their empty hours here put
    # them at the top of the waste list and inflated every figure under it --
    # with time that is not waste at all, but the thing keeping the equipment
    # alive. A number that goes into a business case cannot include it.
    discretionary = cooled[cooled["alerts"]]
    empty_minutes = sum(
        status_minutes(recent, room, day_start, now).get("empty", 0.0)
        for room in discretionary["room"])
    kwh = empty_minutes / 60.0 * assumptions.get("unit_kw", 1.2)
    rupees = kwh * assumptions.get("tariff_rs_per_kwh", 55)
    co2 = kwh * assumptions.get("co2_kg_per_kwh", 0.45)

    # Tree-YEARS, with no multiplying by 365. Projecting one day's carbon
    # across a year turned 89 kg into "1,544 trees" -- a number nobody would
    # believe and nobody should.
    trees = co2 / max(assumptions.get("co2_kg_per_tree_year", 21), 1)

    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:10px;'
        'margin:0 0 3px;"><span style="font-size:1.1rem;font-weight:720;">'
        'What that empty time is worth</span>'
        '<span style="font-size:.72rem;color:#8A949A;">last %dh</span></div>'
        '<div style="font-size:.76rem;color:#8A949A;margin-bottom:10px;'
        'max-width:980px;">An upper bound, not a saving, and a loose one. The'
        ' empty time is measured; whether any unit was running is not, because'
        ' none is calibrated. It covers the night as well, when the units are'
        ' presumably already off, so the real figure is well below this. Read'
        ' it as <b>if every unit in those rooms had run through all of it</b>,'
        ' at %s kW each and Rs %s a unit.</div>'
        % (DETAIL_HOURS, assumptions.get("unit_kw", 1.2),
           assumptions.get("tariff_rs_per_kwh", 55)), unsafe_allow_html=True)

    # ---- which hours the money is actually in -----------------------------
    #
    # A room left cooling through a lunch break costs about fifty rupees. The
    # same room left cooling from eight at night until ten the next morning
    # costs about nine hundred, and across a weekend about four thousand. One
    # night is worth eighteen lunch breaks and one weekend eighty-three.
    #
    # A single total hides that completely, and a total that hides where the
    # money is sends people to chase the wrong thing -- walking the floor at
    # lunchtime while the real figure is made overnight by nobody.
    by_period = {WORKING: 0.0, AFTER_HOURS: 0.0, WEEKEND: 0.0}
    week_start = now - pd.Timedelta(days=7)
    for room in discretionary["room"]:
        mine = month[month["room"] == room].sort_values("timestamp")
        if mine.empty:
            continue
        edges = list(mine["timestamp"]) + [now]
        for index, state in enumerate(mine["status"]):
            if state != "empty":
                continue
            began, ended = max(edges[index], week_start), edges[index + 1]
            if ended <= began:
                continue
            for bucket, minutes in split_by_period(began, ended, hours).items():
                by_period[bucket] += minutes

    if sum(by_period.values()) > 0:
        st.divider()
        biggest = max(by_period, key=by_period.get)
        tiles = "".join(
            figure_row(name.title(), "Rs %s" % format(round(money(mins, assumptions)[1]), ","),
                       "%s empty" % spell(mins),
                       "#A33434" if name == biggest else "#E6EAED")
            for name, mins in ((WORKING, by_period[WORKING]),
                               (AFTER_HOURS, by_period[AFTER_HOURS]),
                               (WEEKEND, by_period[WEEKEND])))
        st.markdown(
            '<div style="font-size:1.1rem;font-weight:720;margin-bottom:2px;">'
            'Which hours it happens in</div>'
            '<div style="font-size:.74rem;color:#8A949A;margin-bottom:9px;">'
            'the last seven days, split by the kind of time &mdash; same upper'
            ' bound, same assumptions</div>'
            '<div style="display:flex;gap:11px;flex-wrap:wrap;">%s</div>'
            % tiles, unsafe_allow_html=True)
        st.caption("One night left running is worth about eighteen lunch"
                   " breaks, and one weekend about eighty-three. If the"
                   " largest figure here is not working hours, walking the"
                   " floor at lunchtime is not where the money is \u2014"
                   " timers and an evening sweep are.")

    st.markdown(
        '<div style="display:flex;gap:11px;flex-wrap:wrap;margin-bottom:6px;">'
        '%s%s%s%s</div>' % (
            figure_row("Empty cooled-room time", spell(empty_minutes),
                       "%d rooms added together" % len(discretionary)),
            figure_row("Electricity at stake", "%s kWh" % format(round(kwh), ","),
                       "at %s kW per unit" % assumptions.get("unit_kw", 1.2)),
            figure_row("Rupees at stake", "Rs %s" % format(round(rupees), ","),
                       "at Rs %s a unit"
                       % assumptions.get("tariff_rs_per_kwh", 55)),
            figure_row("Carbon at stake", "%s kg" % format(round(co2), ","),
                       "what about %d trees take up in a year"
                       % max(round(trees), 1))), unsafe_allow_html=True)
    st.caption("Change any of these in the `assumptions` block of rooms.yaml"
               " — they are kept there, not in the code, so they can be"
               " argued with.")

    # ---- where the empty cooled-room time actually goes -------------------
    #
    # The total says there is something to look at. It does not say where, and
    # thirty rooms is too many to work through evenly. Ranked, it usually turns
    # out that three or four rooms carry most of it, and those are the ones
    # worth a timer, a word with whoever uses them, or a camera moved.
    st.divider()
    ranked = sorted(
        ((room, status_minutes(recent, room, day_start, now).get("empty", 0.0))
         for room in discretionary["room"]), key=lambda pair: -pair[1])[:8]
    if ranked and ranked[0][1] > 0:
        worst = ranked[0][1]
        bars = "".join(
            '<div style="display:flex;align-items:center;gap:9px;'
            'margin-bottom:4px;">'
            '<span style="flex:0 0 150px;font-size:.78rem;white-space:nowrap;'
            'overflow:hidden;text-overflow:ellipsis;">%s</span>'
            '<span style="flex:1 1 auto;height:13px;background:#1B2228;'
            'border-radius:3px;overflow:hidden;">'
            '<span style="display:block;height:13px;width:%.1f%%;'
            'background:#C05B45;border-radius:3px;"></span></span>'
            '<span style="flex:0 0 72px;text-align:right;font-size:.74rem;'
            'color:#8A949A;">%s</span></div>'
            % (room, 100.0 * minutes / worst, spell(minutes))
            for room, minutes in ranked)
        st.markdown(
            '<div style="font-size:1.1rem;font-weight:720;margin-bottom:2px;">'
            'Where that time goes</div>'
            '<div style="font-size:.74rem;color:#8A949A;margin-bottom:8px;">'
            'air-conditioned rooms, longest empty first, last %dh</div>%s'
            % (DETAIL_HOURS, bars), unsafe_allow_html=True)
        st.caption("Three or four rooms usually carry most of it. Those are"
                   " the ones worth a timer, a word with whoever uses them, or"
                   " a camera moved — rather than working evenly through"
                   " thirty.")

    # ---- the week as a picture --------------------------------------------
    st.divider()
    try:
        watched, possible = load_coverage()
    except psycopg2.Error:
        watched, possible = 0.0, 1.0
    share = watched / possible if possible else 0.0
    if share < 0.9:
        st.warning(
            "**The last seven days were only watched for %s of %s hours"
            " (%d%%).** Everything below is drawn from recorded changes, and"
            " nothing is recorded while the loop is stopped \u2014 so a pale"
            " patch may mean the room was empty, or it may mean nobody was"
            " looking. The gaps are the nights and weekends, which is exactly"
            " where the money is."
            % (spell(watched * 60), int(possible), round(100 * share)))
    try:
        week = load_history()
    except psycopg2.Error:
        week = pd.DataFrame()
    if not week.empty:
        st.markdown(
            '<div style="font-size:1.1rem;font-weight:720;margin-bottom:2px;">'
            'When each room is used</div>'
            '<div style="font-size:.74rem;color:#8A949A;margin-bottom:8px;">'
            'each square is an hour of the day; darker means the room was in'
            ' use on more of the last seven days</div>', unsafe_allow_html=True)
        rows_html, advice = "", []
        for _, room in df.iterrows():
            share, days_seen = hour_pattern(week, room["room"], now)
            if days_seen == 0:
                continue
            rows_html += pattern_row(room["room"], share,
                                     INK[room["level"]]["fg"])
            if room["has_unit"] and room["alerts"]:
                hour = settles_at(share)
                if hour is not None and days_seen >= 3:
                    advice.append((room["room"], hour, days_seen))
        ticks = "".join('<span style="flex:1 1 0;text-align:center;">%s</span>'
                        % (("%02d" % h) if h % 3 == 0 else "")
                        for h in range(24))
        st.markdown(
            rows_html +
            '<div style="display:flex;align-items:center;gap:8px;'
            'margin-top:2px;"><span style="flex:0 0 140px;"></span>'
            '<span style="flex:1 1 auto;display:flex;font-size:.6rem;'
            'color:#7E888E;">%s</span></div>' % ticks,
            unsafe_allow_html=True)

        if advice:
            # The point of the picture. A room reliably empty after six does
            # not need an alert at all -- it needs a timer, and then it stops
            # being a problem instead of being reported as one every evening.
            lines = "".join(
                '<li style="margin-bottom:2px;"><b>%s</b> is reliably empty'
                ' after %02d:00 &mdash; a timer at %02d:15 would stop it being'
                ' reported at all <span style="color:#7E888E;">(%d days'
                ' seen)</span></li>' % (room, hour, hour, days)
                for room, hour, days in sorted(advice, key=lambda a: a[1]))
            st.markdown(
                '<div style="background:#141E14;border:1px solid #2A3A22;'
                'border-radius:11px;padding:12px 16px;margin-top:14px;">'
                '<div style="font-weight:680;color:#A4D463;margin-bottom:5px;">'
                'Worth setting a timer for</div>'
                '<ul style="margin:0;padding-left:18px;font-size:.82rem;'
                'color:#A4D463;">%s</ul></div>' % lines,
                unsafe_allow_html=True)
            st.caption("Reliably means used on fewer than one day in five"
                       " after that hour. A room used on two afternoons out of"
                       " seven gets no suggestion, because switching it off"
                       " would catch somebody sitting under it.")

    st.divider()
    st.markdown('<div style="font-size:1.1rem;font-weight:720;">When rooms'
                ' fill and empty</div>', unsafe_allow_html=True)
    st.caption("Built from the recorded changes, so it covers only the time"
               " the loop was actually running.")
    try:
        history = load_history()
    except psycopg2.Error as e:
        st.error("Could not load history (%s)." % type(e).__name__)
        return
    if history.empty:
        st.info("No history yet.")
        return
    history = history[history["room"].isin(set(df["room"]))]
    busy_only = history[history["status"] == "occupied"].copy()
    history = busy_only
    history["day"] = to_local(history["timestamp"]).dt.date
    day = st.selectbox("Day", sorted(history["day"].unique(), reverse=True))
    chosen = history[history["day"] == day]
    summary = chosen.groupby("room").agg(
        first_seen=("timestamp", "min"), last_seen=("timestamp", "max"),
        most_at_once=("people", "max")).reset_index()
    for column in ("first_seen", "last_seen"):
        summary[column] = to_local(summary[column]).dt.strftime("%H:%M")
    st.dataframe(summary.rename(columns={
        "room": "Room", "first_seen": "First seen", "last_seen": "Last seen",
        "most_at_once": "Most at once"}), hide_index=True,
        use_container_width=True)
    st.caption("First and last seen are when people were detected, not when"
               " the building opened: a room nobody entered before 11am"
               " reports 11am.")


# --------------------------------------------------------------------------
# One job on screen at all times, everything else behind a chooser.
#
# Written for three campuses and a hundred and fifty rooms rather than for the
# thirty there are today. A single scrolling page works at thirty and stops
# working somewhere around sixty: the action list gets pushed up out of sight
# by the sheer length of everything under it, which is exactly backwards.
#
# So the header and the walking list are always rendered, and the rest -- the
# room board, one room close up, the stills, the figures and history -- are
# views you pick. Nothing that matters is ever more than one screen away, and
# adding a campus adds an entry to a dropdown rather than another page length.

try:
    rooms = load_rooms_config()
    latest, recent, last_beat = load_state()
except FileNotFoundError:
    st.error("rooms.yaml not found. Run this from the project folder.")
    st.stop()
except psycopg2.Error as e:
    if getattr(e, "pgcode", None) == "42501" and USING_APP_CREDENTIAL:
        st.error(
            "This is connecting as the camera machine, which is not allowed to"
            " read room data — it can see the timestamp column and nothing"
            " else, so that a machine in a corridor cupboard cannot answer who"
            " was in which room.\n\nAdd the read-only role from"
            " sql/02_roles.sql to .env as `DASHBOARD_DATABASE_URL`. Do not"
            " widen the camera machine's grants to make this page work.")
    else:
        st.error("Database unreachable (%s). The driver's message is withheld"
                 " because it contains connection details." % type(e).__name__)
    st.stop()

now = pd.Timestamp.now(tz="UTC")
everything = rooms.merge(latest, on="room", how="left")
everything["status"] = everything["status"].fillna("unknown")

VIEWS = ["Rooms", "One room", "Who comes when", "Camera health",
         "Look at the rooms", "Numbers & history"]

# A click on a room is a request to see that room, so it carries the name in
# the query string and lands on the view that shows it. Tracked rather than
# set every run, or picking another view with a room still in the URL would
# bounce straight back.
clicked = st.query_params.get("room")
if clicked and st.session_state.get("_came_from") != clicked:
    st.session_state["_came_from"] = clicked
    st.session_state["view"] = "One room"

with st.sidebar:
    st.markdown(
        '<div style="font-size:.62rem;letter-spacing:.22em;color:#8A949A;">'
        'ENERGYCAM</div>', unsafe_allow_html=True)
    campuses = sorted(everything["campus"].unique())
    campus = (st.selectbox("Campus", campuses) if len(campuses) > 1
              else campuses[0])
    if len(campuses) == 1:
        st.markdown('<div style="font-size:1.2rem;font-weight:740;'
                    'margin-bottom:8px;">%s</div>' % campus,
                    unsafe_allow_html=True)
    view = st.radio("View", VIEWS, key="view", label_visibility="collapsed")
    hunt = st.text_input("Find a room", placeholder="name or part of one")
    st.markdown(
        '<div style="font-size:.68rem;color:#8A949A;line-height:1.9;'
        'margin-top:12px;">'
        '<span style="color:#D04A4A;">●</span> long empty<br>'
        '<span style="color:#D89221;">●</span> worth a check<br>'
        '<span style="color:#7E888E;">●</span> camera silent<br>'
        '<span style="color:#84CC16;">●</span> fine</div>',
        unsafe_allow_html=True)

df = everything[everything["campus"] == campus].copy()
hours = load_hours()
df["occupied_since"] = df["room"].apply(lambda r: run_started(recent, r, now))
graded = df.apply(lambda r: grade(r, now, hours), axis=1)
df["level"] = [g[0] for g in graded]
df["headline"] = [g[1] for g in graded]
df["sub"] = [g[2] for g in graded]
df["age"] = df["timestamp"].apply(
    lambda t: "never" if minutes_since(t, now) is None
    else "%s ago" % spell(minutes_since(t, now)))
df["slots"] = df["room"].apply(lambda r: slot_states(recent, r, now))
df = df.sort_values(by=["level", "room"],
                    key=lambda c: c.map(RANK) if c.name == "level" else c)

cooled = df[df["has_unit"]]
# Rooms whose cooling is a choice. The server rooms have units and sit empty
# nearly always, and their empty hours are what keeps the equipment alive, so
# counting them here would put money against something nobody should switch
# off.
discretionary = cooled[cooled["alerts"]]
assumptions = load_assumptions()

at_stake = money(
    wasted_minutes(recent, discretionary["room"],
                   now - pd.Timedelta(hours=DETAIL_HOURS), now),
    assumptions)[1]
try:
    month = load_history()
except psycopg2.Error:
    month = pd.DataFrame()
saved, span, enough = against_baseline(month, discretionary["room"], now,
                                       assumptions)

beat_age = minutes_since(last_beat, now)
st.markdown(header_band(campus, df, beat_age, describe(now, hours),
                        money_strip(at_stake, saved, span, enough)),
            unsafe_allow_html=True)

# ---- always on screen: the job -------------------------------------------
acting = df[df["level"].isin(["Red", "Amber"])]
silent_rooms = df[df["level"] == "Fault"]
in_frame = acting[acting["ac"] == "visible"]
out_of_frame = acting[acting["ac"] == "hidden"]

if acting.empty:
    st.markdown(
        '<div style="background:#141E14;border:1px solid #2A3A22;'
        'border-left:6px solid #A4D463;border-radius:13px;padding:15px 19px;'
        'margin-bottom:12px;">'
        '<div style="font-size:1.1rem;font-weight:740;color:#A4D463;">'
        'Nothing to do right now</div>'
        '<div style="font-size:.78rem;color:#A4D463;opacity:.8;margin-top:2px;">'
        'Every air-conditioned room is either in use or has not been empty long'
        ' enough to be worth a walk.</div></div>', unsafe_allow_html=True)
else:
    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:10px;'
        'margin:2px 0 8px;">'
        '<span style="font-size:1.3rem;font-weight:780;color:#9B2C2C;">'
        'Go and check %d room%s</span>'
        '<span style="font-size:.73rem;color:#8A949A;">empty past its own'
        ' threshold, with a unit in it</span></div>'
        % (len(acting), "" if len(acting) == 1 else "s"),
        unsafe_allow_html=True)
    for group, title, note in (
            (in_frame, "Unit is in frame",
             "the camera can see this one; once it is calibrated these will"
             " say whether it was actually running"),
            (out_of_frame, "Unit is out of frame",
             "the camera cannot see it, so somebody has to walk past and"
             " look")):
        if group.empty:
            continue
        st.markdown(
            '<div style="font-size:.66rem;letter-spacing:.13em;color:#8A949A;'
            'margin:9px 0 5px;">%s &middot; <span style="letter-spacing:0;'
            'text-transform:none;">%s</span></div>'
            '<div style="display:flex;flex-wrap:wrap;gap:12px;">%s</div>'
            % (title.upper(), note,
               "".join(linked(room_card(row, recent, now), row["room"])
                       for _, row in group.iterrows())),
            unsafe_allow_html=True)

if not silent_rooms.empty:
    # A different job for a different person. A room nobody could see is not a
    # room to go and stand in, so it stays off the walking list.
    st.markdown(
        '<div style="background:#171E24;border:1px solid #2B343B;'
        'border-radius:10px;padding:9px 13px;margin:9px 0 4px;font-size:.78rem;'
        'color:#9AA4AA;"><b>%d camera%s not answering</b> &mdash; %s. Reported'
        ' as unknown rather than empty, because nobody looked.</div>'
        % (len(silent_rooms), "" if len(silent_rooms) == 1 else "s",
           ", ".join(silent_rooms["room"])), unsafe_allow_html=True)

st.divider()

# ---- the chosen view ------------------------------------------------------

if hunt:
    found = df[df["room"].str.contains(hunt, case=False, na=False)]
    if found.empty:
        st.info("No room here matches %r." % hunt)
    else:
        st.markdown(
            '<div style="font-size:.8rem;color:#8A949A;margin-bottom:6px;">'
            '%d room%s matching “%s”</div>%s'
            % (len(found), "" if len(found) == 1 else "s", hunt,
               "".join(linked(status_row(row), row["room"])
                       for _, row in found.iterrows())),
            unsafe_allow_html=True)
    st.divider()

if view == "Rooms":
    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:10px;'
        'margin:0 0 6px;"><span style="font-size:1.1rem;font-weight:720;">'
        'Every room</span><span style="font-size:.72rem;color:#8A949A;">'
        '%d rooms &middot; who is in it, what its unit is doing, and its last'
        ' %d hours</span></div>' % (len(df), STRIP_HOURS),
        unsafe_allow_html=True)
    zones = [z for z in ZONE_ORDER if z in set(df["zone"])] + \
        sorted(set(df["zone"]) - set(ZONE_ORDER))
    halves = st.columns(2)

    # Zones go to whichever column is shorter, counted in rooms rather than in
    # zones. Alternating them left-right looks even and is not: here it put
    # Offices, Cafe and Outside on one side and Basement and Server rooms on
    # the other -- twenty-six rows against four, with half the page empty. It
    # gets worse with each campus added, because a campus is more zones of
    # wildly different sizes.
    filled = [0, 0]
    for zone in zones:
        here = df[df["zone"] == zone]
        index = 0 if filled[0] <= filled[1] else 1
        filled[index] += len(here)
        note = ""
        if zone == "Server rooms":
            note = (' <span style="letter-spacing:0;text-transform:none;">'
                    '&middot; cooled on purpose, never flagged</span>')
        halves[index % 2].markdown(
            '<div style="font-size:.63rem;letter-spacing:.14em;color:#8A949A;'
            'margin:11px 0 4px;">%s &middot; %d%s</div>%s'
            % (zone.upper(), len(here), note,
               "".join(linked(status_row(row), row["room"])
                       for _, row in here.iterrows())),
            unsafe_allow_html=True)
    st.caption("The bar on each row is the last %d hours: green where people"
               " were seen, grey where the room was empty, pale where nothing"
               " was recorded. Every AC badge reads “?” because no"
               " unit has been calibrated yet — that is unknown, not off."
               " Rooms with no unit show a dash, because there is nothing in"
               " them to be off." % STRIP_HOURS)

elif view == "One room":
    names = list(df["room"])
    picked = clicked if clicked in names else (
        list(acting["room"])[0] if not acting.empty else names[0])
    chosen = st.selectbox("Room", names, index=names.index(picked))
    if chosen != clicked:
        st.query_params["room"] = chosen
    show_room_day(df, recent, chosen, now)

elif view == "Who comes when":
    show_arrivals(df, now)

elif view == "Camera health":
    show_cameras(df, now)

elif view == "Look at the rooms":
    show_stills(cooled, now)

else:
    show_numbers(df, cooled, recent, now)
