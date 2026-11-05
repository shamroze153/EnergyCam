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

INK = {
    "Red":   {"bg": "#FDF0F0", "fg": "#9B2C2C", "edge": "#E8B9B9",
              "bar": "#D04A4A"},
    "Amber": {"bg": "#FDF5E7", "fg": "#8A5209", "edge": "#EBD3A6",
              "bar": "#D89221"},
    "Green": {"bg": "#F1F7EA", "fg": "#3D6E15", "edge": "#CDE0B6",
              "bar": "#7BAE48"},
    "Fault": {"bg": "#F1F1F1", "fg": "#5A5A5A", "edge": "#D4D4D4",
              "bar": "#9AA3A8"},
}
RANK = {"Red": 0, "Amber": 1, "Fault": 2, "Green": 3}
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
def load_history(days=7):
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        df = pd.read_sql_query(
            "SELECT timestamp, room, people FROM room_events"
            " WHERE timestamp >= now() - interval '%d days'"
            " AND status = 'occupied' ORDER BY timestamp" % days, conn)
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


def grade(row, now):
    if row["status"] == "unknown" or pd.isna(row["status"]):
        if pd.isna(row["timestamp"]):
            return "Fault", "Not sampled", "the loop has not reached it"
        return "Fault", "No answer", "camera did not reply"
    if row["status"] == "occupied":
        people = int(row["people"]) if pd.notna(row["people"]) else 0
        return "Green", "%d in here" % people, row["caption"]
    empty = minutes_since(row["empty_since"], now)
    headline = "Empty %s" % spell(empty)
    threshold = row["empty_after"]
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

SLOT_INK = {"occupied": "#7BAE48", "empty": "#E0E0E0", "unknown": "#BDBDBD"}
NO_DATA = "#F4F4F4"


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
                '<ellipse cx="29" cy="31" rx="36" ry="21" fill="#49A54B"'
                ' opacity=".12"/>'
                '<rect x="0" y="0" width="58" height="17" rx="4" fill="#FFFFFF"'
                ' stroke="#2E7D32" stroke-width="2"/>'
                '<line x1="5" y1="12" x2="53" y2="12" stroke="#2E7D32"'
                ' stroke-width="1.6"/>'
                '<circle cx="51" cy="5.5" r="2.1" fill="#2E7D32"/>'
                '<path d="M12 25q5 5 10 0t10 0t10 0" fill="none"'
                ' stroke="#2E7D32" stroke-width="2" stroke-linecap="round"'
                ' opacity=".8"/>'
                '<path d="M16 33q5 4 10 0t10 0" fill="none" stroke="#2E7D32"'
                ' stroke-width="1.8" stroke-linecap="round" opacity=".45"/>'
                '</g>' % (x, y))
    if state == "off":
        return ('<g transform="translate(%d,%d)" opacity=".7">'
                '<rect x="0" y="0" width="58" height="17" rx="4" fill="#FFFFFF"'
                ' stroke="#8E8E8E" stroke-width="2"/>'
                '<line x1="5" y1="12" x2="53" y2="12" stroke="#8E8E8E"'
                ' stroke-width="1.6"/>'
                '<circle cx="51" cy="5.5" r="2.1" fill="none" stroke="#8E8E8E"'
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
  <rect x="4" y="6" width="252" height="100" rx="11" fill="#FFFFFF"
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
                        PERSON.format(x=i * 14, y=0, c="#3D6E15")
                        for i in range(shown))))
        if people > shown:
            now_cell += ('<span style="font-size:.68rem;color:#3D6E15;">+%d'
                         '</span>' % (people - shown))
    elif row["status"] == "unknown":
        now_cell = ('<span style="font-size:.68rem;color:#8A8A8A;">no answer'
                    '</span>')
    else:
        now_cell = ('<span style="font-size:.68rem;color:#9A9A9A;">%s</span>'
                    % row["headline"].replace("Empty ", ""))
    return """
<div style="display:flex;align-items:center;gap:12px;padding:5px 2px;
            border-bottom:1px solid #F0F0F0;">
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
            'color:#9A9A9A;">%s</span>'
            '<span style="flex:0 0 86px;text-align:right;font-size:.62rem;'
            'color:#9A9A9A;">now</span></div>'
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
    return ('<div style="display:flex;font-size:.64rem;color:#9A9A9A;'
            'margin-top:3px;">%s</div>' % ticks)


def building_bar(df):
    """Every room as one square: the campus settled before anyone scrolls."""
    return "".join(
        '<span title="%s &mdash; %s" style="width:17px;height:17px;'
        'border-radius:4px;background:%s;opacity:%s;display:inline-block;">'
        '</span>'
        % (row["room"], row["headline"], INK[row["level"]]["bar"],
           "1" if row["level"] != "Green" else ".34")
        for _, row in df.iterrows())


def header_band(campus, df, beat_age):
    live = (beat_age is not None and beat_age <= STALE_AFTER_MINUTES)
    pill = ('<span style="background:%s;color:%s;font-size:.73rem;'
            'padding:5px 12px;border-radius:20px;white-space:nowrap;">'
            '%s</span>'
            % ("#1F3B22" if live else "#4A2020",
               "#8FD48A" if live else "#F0A5A5",
               ("&#9679; live &middot; reported %s ago" % spell(beat_age))
               if live else ("&#9679; silent for %s" % spell(beat_age))))
    return """
<div style="background:#14181B;border-radius:14px;padding:16px 20px 14px;
            margin-bottom:14px;">
  <div style="display:flex;justify-content:space-between;align-items:center;
              flex-wrap:wrap;gap:10px;">
    <div>
      <span style="color:#6E7B82;font-size:.64rem;letter-spacing:.22em;">
        ENERGYCAM</span>
      <div style="color:#F2F4F5;font-size:1.72rem;font-weight:760;
                  line-height:1.1;">%s</div>
    </div>%s
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:13px;">%s</div>
  <div style="color:#5E6A70;font-size:.63rem;margin-top:9px;">
    one square per room &middot; %d rooms &middot; %d cameras</div>
</div>""" % (campus, pill, building_bar(df), len(df),
             int(df["cameras"].sum()))


def figure_row(label, value, note, tone="#14181B"):
    return """
<div style="flex:1 1 180px;background:#FAFAFA;border:1px solid #ECECEC;
            border-radius:11px;padding:11px 14px;">
  <div style="font-size:.68rem;color:#78848A;letter-spacing:.04em;">%s</div>
  <div style="font-size:1.62rem;font-weight:760;color:%s;line-height:1.25;">
    %s</div>
  <div style="font-size:.66rem;color:#99A3A8;">%s</div>
</div>""" % (label, tone, value, note)


# --------------------------------------------------------------------------

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
df = rooms.merge(latest, on="room", how="left")
df["status"] = df["status"].fillna("unknown")

campuses = sorted(df["campus"].unique())
campus = st.selectbox("Campus", campuses) if len(campuses) > 1 else campuses[0]
df = df[df["campus"] == campus].copy()

graded = df.apply(lambda r: grade(r, now), axis=1)
df["level"] = [g[0] for g in graded]
df["headline"] = [g[1] for g in graded]
df["sub"] = [g[2] for g in graded]
df["age"] = df["timestamp"].apply(
    lambda t: "never" if minutes_since(t, now) is None
    else "%s ago" % spell(minutes_since(t, now)))
df["slots"] = df["room"].apply(lambda r: slot_states(recent, r, now))
df = df.sort_values(by=["level", "room"],
                    key=lambda c: c.map(RANK) if c.name == "level" else c)

beat_age = minutes_since(last_beat, now)
st.markdown(header_band(campus, df, beat_age), unsafe_allow_html=True)

cooled = df[df["has_unit"]]
watched = df[~df["has_unit"]]

# ---- the only question this page exists to answer -------------------------
#
# Which room should somebody walk to, right now. Everything else here is
# background: how the building has been, what it might be worth, what one room
# did yesterday. That is all worth having and none of it is the job, so it
# comes after. A page whose first screen is a summary makes the reader find
# the task; a page whose first screen is the task does not.
acting = df[df["level"].isin(["Red", "Amber"])]
silent_rooms = df[df["level"] == "Fault"]

# Two different jobs, and they stop being the same job the moment a unit is
# calibrated. Where the unit is in frame, this will become "running in an empty
# room" -- waste, stated, with nobody sent anywhere. Where it is out of frame,
# it will always need a person to walk past and look, however good the
# detection gets. Today both read "go and check", so saying which is which is
# also saying which of these rooms is worth re-aiming a camera for.
in_frame = acting[acting["ac"] == "visible"]
out_of_frame = acting[acting["ac"] == "hidden"]

if acting.empty:
    st.markdown(
        '<div style="background:#F1F7EA;border:1px solid #CDE0B6;'
        'border-left:6px solid #3D6E15;border-radius:13px;padding:17px 20px;'
        'margin-bottom:14px;">'
        '<div style="font-size:1.16rem;font-weight:740;color:#3D6E15;">'
        'Nothing to do right now</div>'
        '<div style="font-size:.8rem;color:#3D6E15;opacity:.8;margin-top:3px;">'
        'Every air-conditioned room is either in use or has not been empty'
        ' long enough to be worth a walk.</div></div>',
        unsafe_allow_html=True)
else:
    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:10px;'
        'margin:2px 0 9px;">'
        '<span style="font-size:1.34rem;font-weight:780;color:#9B2C2C;">'
        'Go and check %d room%s</span>'
        '<span style="font-size:.74rem;color:#8A949A;">empty past its own'
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
            '<div style="font-size:.68rem;letter-spacing:.13em;color:#8A949A;'
            'margin:10px 0 5px;">%s &middot; <span style="letter-spacing:0;'
            'text-transform:none;">%s</span></div>'
            '<div style="display:flex;flex-wrap:wrap;gap:12px;">%s</div>'
            % (title.upper(), note,
               "".join(linked(room_card(row, recent, now), row["room"])
                       for _, row in group.iterrows())),
            unsafe_allow_html=True)

if not silent_rooms.empty:
    # Not the same job, and not for the same person: a camera that stopped
    # answering is for whoever looks after cameras. Kept off the walking list
    # so it cannot be mistaken for a room to go and stand in.
    st.markdown(
        '<div style="background:#F3F3F3;border:1px solid #DCDCDC;'
        'border-radius:10px;padding:10px 14px;margin:8px 0 16px;'
        'font-size:.8rem;color:#5A5A5A;">'
        '<b>%d camera%s not answering</b> &mdash; %s. These rooms are reported'
        ' as unknown rather than empty, because nobody looked.</div>'
        % (len(silent_rooms), "" if len(silent_rooms) == 1 else "s",
           ", ".join(silent_rooms["room"])),
        unsafe_allow_html=True)

st.divider()

# Room-hours, not hours: the empty time of every air-conditioned room added
# together, so fourteen rooms over eight hours can and should exceed eight.
# The note under the figure says so, because "61h over the last 8h" reads like
# a mistake otherwise.
#
# Counted from the same slots the strips are drawn from, so the figure and the
# pictures cannot drift apart. And it is not a saving: nothing has measured
# whether any unit was running, and claiming otherwise is the one thing this
# page must not do. It is the size of the question -- how much empty cooled
# room there is to ask about -- from real readings, available today.
empty_slots = sum(1 for _, row in cooled.iterrows()
                  for state in row["slots"] if state == "empty")

st.markdown(
    '<div style="display:flex;gap:11px;flex-wrap:wrap;margin-bottom:16px;">'
    '%s%s%s%s</div>' % (
        figure_row("Air-conditioned rooms", len(cooled),
                   "%d more watched for occupancy only" % len(watched)),
        figure_row("In use right now",
                   int((df["status"] == "occupied").sum()),
                   "of %d rooms watched" % len(df)),
        figure_row("Empty cooled-room time", spell(empty_slots * 5),
                   "added up across %d rooms, last %dh"
                   % (len(cooled), STRIP_HOURS)),
        figure_row("Cameras not answering", len(silent_rooms),
                   "reported as unknown, not empty",
                   "#6A6A6A" if len(silent_rooms) else "#14181B")),
    unsafe_allow_html=True)

st.markdown(
    '<div style="display:flex;align-items:baseline;gap:10px;margin:4px 0 9px;">'
    '<span style="font-size:1.12rem;font-weight:720;">Every air-conditioned'
    ' room</span><span style="font-size:.72rem;color:#8A949A;">%d rooms'
    ' &middot; the ones above appear here too</span></div>' % len(cooled),
    unsafe_allow_html=True)
st.markdown(
    '<div style="display:flex;flex-wrap:wrap;gap:12px;">%s</div>'
    % "".join(linked(room_card(row, recent, now), row["room"])
              for _, row in cooled.iterrows()),
    unsafe_allow_html=True)

st.markdown(
    '<div style="display:flex;align-items:baseline;gap:10px;'
    'margin:26px 0 2px;"><span style="font-size:1.12rem;font-weight:720;">'
    'Everywhere else</span><span style="font-size:.72rem;color:#8A949A;">'
    '%d rooms &middot; nothing in them to switch off, so the question is when'
    ' they are used</span></div>' % len(watched),
    unsafe_allow_html=True)

for zone in [z for z in ZONE_ORDER if z in set(watched["zone"])] + \
        sorted(set(watched["zone"]) - set(ZONE_ORDER)):
    here = watched[watched["zone"] == zone]
    note = ""
    if zone == "Server rooms":
        note = (' &middot; <span style="color:#A5AEB3;">cooled around the clock'
                ' on purpose; never flagged</span>')
    st.markdown(
        '<div style="font-size:.66rem;letter-spacing:.14em;color:#8A949A;'
        'margin:15px 0 3px;">%s%s</div>%s%s'
        % (zone.upper(), note,
           "".join(linked(lane(row), row["room"])
                   for _, row in here.iterrows()),
           hour_axis(now)),
        unsafe_allow_html=True)

st.caption("Bands show the last %d hours: green where people were seen, grey"
           " where the room was empty, pale where nothing was recorded yet."
           " Every air conditioner is drawn dashed with a question mark"
           " because none has been calibrated — that is unknown, not off."
           % STRIP_HOURS)

# ---- one room, in detail --------------------------------------------------
#
# Placed here, under the action list, because it is where a click lands. Any
# card on the page is a link carrying its room name in the query string, so
# clicking one reloads the page with that room open right where the reader was
# already looking, rather than somewhere they have to go and find.

picked = st.query_params.get("room")
names = list(df["room"])
if picked not in names:
    picked = list(acting["room"])[0] if not acting.empty else names[0]

st.markdown(
    '<div id="roomdetail" style="font-size:1.12rem;font-weight:720;'
    'margin:2px 0 2px;">One room, close up</div>'
    '<div style="font-size:.72rem;color:#8A949A;margin-bottom:6px;">'
    'click any room on this page, or pick one</div>', unsafe_allow_html=True)

chosen = st.selectbox("Room", names, index=names.index(picked),
                      label_visibility="collapsed")
if chosen != picked:
    st.query_params["room"] = chosen

row = df[df["room"] == chosen].iloc[0]

# Midnight, not twenty-four hours back. "When does the first person arrive"
# is a question about a day, and a rolling window answered it with yesterday
# evening: first seen 18:07, last seen 15:48, which reads backwards and was.
# Early in the morning this band is short, which is honest -- the day is short.
midnight = (now.tz_convert("Asia/Karachi").normalize()).tz_convert("UTC")
hours_today = max(1.0, (now - midnight).total_seconds() / 3600.0)
day = status_minutes(recent, chosen, midnight, now)
mine = recent[(recent["room"] == chosen) & (recent["timestamp"] >= midnight)]
busy = mine[mine["status"] == "occupied"]

if busy.empty:
    peak, peak_at, first_at, last_at = "\u2014", "nobody seen", "\u2014", "\u2014"
else:
    top = busy["people"].idxmax()
    peak = int(busy.loc[top, "people"])
    peak_at = "at %s" % to_local(busy.loc[[top], "timestamp"]).iloc[0].strftime("%H:%M")
    first_at = to_local(busy["timestamp"]).min().strftime("%H:%M")

    # Only changes are recorded, so the last "occupied" row is when the count
    # last moved, not when the room emptied. Someone who arrived at 09:25 and
    # left at 17:40 leaves one occupied row, at 09:25 -- and reporting that as
    # "last seen" cuts eight hours off their day and makes the room look
    # deserted by mid-morning. What is wanted is the row after it: the moment
    # the room went empty. If nothing follows, they are still there.
    ordered = mine.sort_values("timestamp").reset_index(drop=True)
    last_busy = ordered.index[ordered["status"] == "occupied"].max()
    if last_busy + 1 < len(ordered):
        last_at = to_local(ordered.loc[[last_busy + 1], "timestamp"]).iloc[0] \
            .strftime("%H:%M")
    else:
        last_at = "still in use"

st.markdown(
    '<div style="display:flex;gap:11px;flex-wrap:wrap;margin:6px 0 12px;">'
    '%s%s%s%s%s</div>' % (
        figure_row("First seen", first_at, "earliest person since midnight"),
        figure_row("Emptied at", last_at, "after the last person left"),
        figure_row("Most at once", peak, peak_at),
        figure_row("Used today", spell(day.get("occupied", 0.0)),
                   "empty %s" % spell(day.get("empty", 0.0))),
        figure_row("Unaccounted", spell(day.get("unknown", 0.0)),
                   "camera did not answer")),
    unsafe_allow_html=True)

st.markdown(
    strip_svg(slot_states(recent, chosen, now, slots=int(hours_today * 12),
                          since=midnight), height=26, radius=5)
    + day_axis(now, midnight), unsafe_allow_html=True)

if not busy.empty:
    by_hour = busy.copy()
    by_hour["hour"] = to_local(by_hour["timestamp"]).dt.strftime("%H:00")
    peaks = by_hour.groupby("hour")["people"].max().reset_index()
    figure = px.bar(peaks, x="hour", y="people",
                    labels={"hour": "", "people": "people"},
                    color_discrete_sequence=["#7BAE48"])
    figure.update_layout(height=220, margin=dict(l=0, r=0, t=14, b=0),
                         plot_bgcolor="#FFFFFF", showlegend=False,
                         yaxis=dict(gridcolor="#F0F0F0"))
    st.plotly_chart(figure, use_container_width=True)
    st.caption("The most people seen at once in each hour. Readings are a"
               " couple of minutes apart, so a visit shorter than that can"
               " fall between two of them and leave no mark.")

# ---- and the same room's habits, over a week -----------------------------
#
# One day is an anecdote. The useful question about a room is not when it
# filled today but when it usually fills, because that is what a cleaning
# round, a switch-off time or an argument about a thermostat gets planned
# against. It needs several days before it means anything, and says so until
# it has them.
try:
    week = load_history()
except psycopg2.Error:
    week = pd.DataFrame()

if not week.empty:
    theirs = week[week["room"] == chosen].copy()
    if not theirs.empty:
        theirs["when"] = to_local(theirs["timestamp"])
        theirs["day"] = theirs["when"].dt.date
        theirs["minute"] = theirs["when"].dt.hour * 60 + theirs["when"].dt.minute
        by_day = theirs.groupby("day").agg(
            arrives=("minute", "min"), leaves=("minute", "max"),
            busiest=("people", "max")).reset_index()
        clock = lambda m: "%02d:%02d" % divmod(int(round(m)), 60)
        if len(by_day) < 2:
            st.caption("Only one day recorded so far \u2014 a usual pattern"
                       " needs a few more before it means anything.")
        else:
            st.markdown(
                '<div style="font-size:.84rem;font-weight:650;margin:14px 0 6px;">'
                'On a usual day <span style="font-weight:400;color:#8A949A;">'
                '(%d days recorded)</span></div>'
                '<div style="display:flex;gap:11px;flex-wrap:wrap;">%s%s%s</div>'
                % (len(by_day),
                   figure_row("First arrival", clock(by_day["arrives"].mean()),
                              "earliest %s" % clock(by_day["arrives"].min())),
                   figure_row("Last to leave", clock(by_day["leaves"].mean()),
                              "latest %s" % clock(by_day["leaves"].max())),
                   figure_row("Busiest it gets",
                              int(by_day["busiest"].max()),
                              "typically %d" % round(by_day["busiest"].mean()))),
                unsafe_allow_html=True)

st.divider()

# ---- the walk round, without the walk ------------------------------------
#
# The use for this is concrete: it is ten past seven, the office is emptying,
# and somebody wants to see the rooms before they go home rather than walk the
# floor. A still from each one answers that; a video stream would not answer it
# any better and would be a far larger thing to have built.
#
# Blurred before it was written, one per air-conditioned room, overwritten each
# pass, never in the database. The loop only produces these when rooms.yaml
# turns them on, so this section simply is not there otherwise.

shots = []
if os.path.isdir(SNAPSHOT_DIR):
    for _, room in cooled.iterrows():
        safe = "".join(c if c.isalnum() else "_" for c in room["room"])
        path = os.path.join(SNAPSHOT_DIR, "%s.jpg" % safe)
        if os.path.exists(path):
            shots.append((room, path, (time.time() - os.path.getmtime(path)) / 60))

if shots:
    with st.expander("Look at the rooms (%d blurred stills)" % len(shots)):
        st.caption(
            "Faces, screens, keyboards and phones are blurred before the file"
            " is written \u2014 the same pass that blurs an alert snapshot."
            " One still per room, overwritten every pass, kept on this machine"
            " and never sent to the database.")
        for start in range(0, len(shots), 4):
            for column, (room, path, age) in zip(
                    st.columns(4), shots[start:start + 4]):
                column.image(path, use_container_width=True)
                column.markdown(
                    '<div style="font-size:.78rem;font-weight:600;color:%s;'
                    'margin-top:-6px;">%s</div>'
                    '<div style="font-size:.66rem;color:#9AA3A8;">%s'
                    ' &middot; %s</div>'
                    % (INK[room["level"]]["fg"], room["room"],
                       room["headline"], "%d min old" % age if age >= 1
                       else "just now"),
                    unsafe_allow_html=True)
    st.divider()

# ---- what the empty cooled-room time would amount to ----------------------
#
# Every number here is conditional and the page says so out loud. We know how
# long each air-conditioned room stood empty, because that is measured. We do
# not know whether its unit was running, because nothing has measured that yet.
# So this answers "if they were running, how much is sitting on the table" --
# which is the question worth asking before anyone spends a Saturday moving
# cameras, and is not the same claim as a saving.
#
# It becomes a saving only when two things exist: a calibrated unit, so the
# state is measured rather than supposed, and a record of somebody acting on an
# alert, so the difference belongs to this system rather than to the weather.

assumptions = load_assumptions()
day_start = now - pd.Timedelta(hours=DETAIL_HOURS)
empty_minutes = sum(
    status_minutes(recent, room, day_start, now).get("empty", 0.0)
    for room in cooled["room"])
kwh = empty_minutes / 60.0 * assumptions.get("unit_kw", 1.2)
rupees = kwh * assumptions.get("tariff_rs_per_kwh", 55)
co2 = kwh * assumptions.get("co2_kg_per_kwh", 0.45)
# Tree-YEARS, and no multiplying by 365. Projecting one day's carbon across a
# year turned 89 kg into "1,544 trees", a number nobody would believe and
# nobody should: it extrapolates a single day, overnight included, into an
# annual rate. This day's carbon is simply what that many trees take up in a
# year, which is a comparison rather than a forecast.
trees = co2 / max(assumptions.get("co2_kg_per_tree_year", 21), 1)

st.markdown(
    '<div style="display:flex;align-items:baseline;gap:10px;margin:4px 0 3px;">'
    '<span style="font-size:1.12rem;font-weight:720;">What that empty time is'
    ' worth</span><span style="font-size:.72rem;color:#8A949A;">last %dh'
    '</span></div>'
    '<div style="font-size:.76rem;color:#8A949A;margin-bottom:10px;">'
    'An upper bound, not a saving, and a loose one. The empty time is'
    ' measured; whether any unit was running is not, because none is'
    ' calibrated. It covers the night as well, when the units are presumably'
    ' already off, so the real figure is well below this. Read it as'
    ' <b>if every unit in those rooms had run through all of it</b>, at %s kW'
    ' each and Rs %s a unit.</div>'
    % (DETAIL_HOURS, assumptions.get("unit_kw", 1.2),
       assumptions.get("tariff_rs_per_kwh", 55)),
    unsafe_allow_html=True)

st.markdown(
    '<div style="display:flex;gap:11px;flex-wrap:wrap;margin-bottom:6px;">'
    '%s%s%s%s</div>' % (
        figure_row("Empty cooled-room time", spell(empty_minutes),
                   "%d rooms added together" % len(cooled)),
        figure_row("Electricity at stake", "%s kWh" % format(round(kwh), ","),
                   "at %s kW per unit" % assumptions.get("unit_kw", 1.2)),
        figure_row("Rupees at stake", "Rs %s" % format(round(rupees), ","),
                   "at Rs %s a unit" % assumptions.get("tariff_rs_per_kwh", 55)),
        figure_row("Carbon at stake", "%s kg" % format(round(co2), ","),
                   "what about %d trees take up in a year" % max(round(trees), 1))),
    unsafe_allow_html=True)

st.caption("Change any of these assumptions in the `assumptions` block of"
           " rooms.yaml \u2014 they are kept there, not in the code, so they"
           " can be argued with.")

st.divider()

with st.expander("When rooms fill and empty"):
    st.caption("Built from the recorded changes, so it covers only the time"
               " the loop was actually running.")
    try:
        history = load_history()
    except psycopg2.Error as e:
        st.error("Could not load history (%s)." % type(e).__name__)
        history = pd.DataFrame()
    if history.empty:
        st.info("No history yet.")
    else:
        history["day"] = to_local(history["timestamp"]).dt.date
        day = st.selectbox("Day", sorted(history["day"].unique(), reverse=True))
        chosen = history[history["day"] == day]
        summary = chosen.groupby("room").agg(
            first_seen=("timestamp", "min"),
            last_seen=("timestamp", "max"),
            most_at_once=("people", "max")).reset_index()
        for column in ("first_seen", "last_seen"):
            summary[column] = to_local(summary[column]).dt.strftime("%H:%M")
        st.dataframe(summary.rename(columns={
            "room": "Room", "first_seen": "First seen",
            "last_seen": "Last seen", "most_at_once": "Most at once"}),
            hide_index=True, use_container_width=True)
        st.caption("First and last seen are when people were detected, not"
                   " when the building opened: a room nobody entered before"
                   " 11am reports 11am.")
