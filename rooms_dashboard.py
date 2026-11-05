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
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
import psycopg2
import streamlit as st
import yaml
from streamlit_autorefresh import st_autorefresh

PKT = timezone(timedelta(hours=5))

# The loop beats every five minutes. Two missed beats is a real gap rather than
# a slow cycle, and past that nothing here should be acted on: the tiles would
# still be sitting in their last known state, looking perfectly current.
STALE_AFTER_MINUTES = 11

STRIP_HOURS = 8
STRIP_SLOTS = 96                      # five minutes each

INK = {
    "Red":   {"bg": "#FDF0F0", "fg": "#9B2C2C", "edge": "#E8B9B9"},
    "Amber": {"bg": "#FDF5E7", "fg": "#8A5209", "edge": "#EBD3A6"},
    "Green": {"bg": "#F1F7EA", "fg": "#3D6E15", "edge": "#CDE0B6"},
    "Fault": {"bg": "#F1F1F1", "fg": "#5A5A5A", "edge": "#D4D4D4"},
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
        if room["ac"] == "visible" and alerts:
            caption = "unit in frame"
        elif room["ac"] == "hidden" and alerts:
            caption = "unit out of frame"
        else:
            caption = "nothing to switch off"
        rows.append({
            "room": room["name"],
            "recorder": room["recorder"],
            "campus": recorders[room["recorder"]].get("campus", "unknown"),
            "zone": room.get("zone", "Other"),
            "cameras": len(room["channels"]),
            "ac": room["ac"],
            "alerts": alerts,
            "caption": caption,
            "empty_after": room.get("empty_after_minutes"),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=20)
def load_state():
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        latest = pd.read_sql_query(
            "SELECT DISTINCT ON (room) room, status, people, empty_since,"
            " ac_state, timestamp"
            " FROM room_events ORDER BY room, timestamp DESC", conn)
        recent = pd.read_sql_query(
            "SELECT timestamp, room, status FROM room_events"
            " WHERE timestamp >= now() - interval '%d hours'"
            " ORDER BY room, timestamp" % (STRIP_HOURS + 1), conn)
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


def crowd(count, colour, floor, left=44, step=19, room_width=248):
    """People standing on the floor of the drawn room.

    Past a point figures stop being countable and become a texture, so the rest
    become a number. The cut-off is how many fit rather than a round number: a
    crowded room should still look crowded.
    """
    if count <= 0:
        return ""
    room = max(1, int((room_width - left - 28) // step))
    shown = min(count, room)
    parts = [PERSON.format(x=left + i * step, y=floor - 26, c=colour)
             for i in range(shown)]
    if count > shown:
        parts.append('<text x="%d" y="%d" font-size="12" font-weight="700"'
                     ' fill="%s" opacity=".8">+%d</text>'
                     % (left + shown * step + 2, floor - 6, colour,
                        count - shown))
    return "".join(parts)


def wall_unit(state, colour, x=176, y=22):
    """The air conditioner, drawn on the wall where it actually hangs.

    Three states, and the third is the honest one today: nothing has been
    calibrated, so every unit is unknown. Drawing unknown the same as off would
    hang a confident claim on the wall with no measurement behind it.
    """
    if state == "on":
        return ('<g transform="translate(%d,%d)">'
                '<ellipse cx="29" cy="30" rx="34" ry="20" fill="#49A54B"'
                ' opacity=".10"/>'
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
        return ('<g transform="translate(%d,%d)" opacity=".75">'
                '<rect x="0" y="0" width="58" height="17" rx="4" fill="#FFFFFF"'
                ' stroke="#8E8E8E" stroke-width="2"/>'
                '<line x1="5" y1="12" x2="53" y2="12" stroke="#8E8E8E"'
                ' stroke-width="1.6"/>'
                '<circle cx="51" cy="5.5" r="2.1" fill="none" stroke="#8E8E8E"'
                ' stroke-width="1.4"/></g>' % (x, y))
    return ('<g transform="translate(%d,%d)" opacity=".45">'
            '<rect x="0" y="0" width="58" height="17" rx="4" fill="none"'
            ' stroke="%s" stroke-width="1.8" stroke-dasharray="4 3"/>'
            '<text x="24" y="13" font-size="12" font-weight="700" fill="%s">?'
            '</text></g>' % (x, y, colour, colour))


def drawn_room(row, ink):
    """A room with walls, a door, a unit on the wall, and whoever is inside."""
    people = int(row["people"]) if pd.notna(row["people"]) else 0
    if row["status"] != "occupied":
        people = 0
    state = row["ac_state"] if pd.notna(row["ac_state"]) else None
    floor = 96
    label = "" if people else (
        '<text x="46" y="%d" font-size="11.5" fill="%s" opacity=".40"'
        ' letter-spacing="1.6">EMPTY</text>' % (floor - 8, ink["fg"]))
    return """
<svg viewBox="0 0 260 112" style="width:100%%;height:auto;">
  <rect x="4" y="6" width="252" height="100" rx="11" fill="#FFFFFF"
        fill-opacity=".55" stroke="%s" stroke-width="1.6"/>
  <line x1="14" y1="%d" x2="246" y2="%d" stroke="%s" stroke-width="2.4"
        stroke-linecap="round"/>
  <path d="M20 %d V34 a13 13 0 0 1 13-13" fill="none" stroke="%s"
        stroke-width="1.8" stroke-linecap="round" opacity=".8"/>
  %s %s %s
</svg>""" % (ink["edge"], floor, floor, ink["edge"], floor, ink["edge"],
             wall_unit(state, ink["fg"]), crowd(people, ink["fg"], floor),
             label)


SLOT_INK = {"occupied": "#7BAE48", "empty": "#DEDEDE", "unknown": "#B4B4B4"}


def day_strip(recent, room, now, height=7):
    """The last eight hours as a band: where there were people, where not."""
    mine = recent[recent["room"] == room]
    if mine.empty:
        return ('<div style="height:%dpx;border-radius:3px;background:#F3F3F3;'
                '"></div>' % height)
    start = now - pd.Timedelta(hours=STRIP_HOURS)
    states = mine["status"].tolist()
    # Seconds from the start of the window, on both sides. Doing this in epoch
    # integers looks tidier and is a trap: in pandas 3 a Series of timestamps
    # converts to int64 in microseconds while Timestamp.value is nanoseconds,
    # so the two scales differ by a thousand. Nothing raises -- every mark
    # lands past every event, every slot takes the last known state, and the
    # strip comes out one convincing block of a single colour. A wrong picture
    # that looks right is worse than one that fails.
    stamps = (mine["timestamp"] - start).dt.total_seconds().to_numpy()
    span = (now - start).total_seconds()
    marks = np.linspace(0, span, STRIP_SLOTS, endpoint=False)
    where = np.searchsorted(stamps, marks, side="right") - 1
    rects = "".join(
        '<rect x="%d" y="0" width="1" height="6" fill="%s"/>'
        % (slot, "#F3F3F3" if i < 0 else SLOT_INK.get(states[i], "#F3F3F3"))
        for slot, i in enumerate(where))
    return ('<svg viewBox="0 0 %d 6" preserveAspectRatio="none" '
            'style="width:100%%;height:%dpx;border-radius:3px;">%s</svg>'
            % (STRIP_SLOTS, height, rects))


def big_card(row, recent, now):
    """A room that wants attention: drawn, with the reason spelled out."""
    ink = INK[row["level"]]
    return """
<div style="background:%s;border:1px solid %s;border-left:6px solid %s;
            border-radius:14px;padding:13px 15px 14px;margin-bottom:13px;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;">
    <span style="font-size:1.06rem;font-weight:680;color:%s;">%s</span>
    <span style="font-size:.62rem;letter-spacing:.1em;color:%s;opacity:.6;">%s</span>
  </div>
  %s
  <div style="display:flex;justify-content:space-between;align-items:baseline;
              margin-top:4px;">
    <span style="font-size:1.32rem;font-weight:750;color:%s;">%s</span>
    <span style="font-size:.72rem;color:%s;opacity:.62;">%s</span>
  </div>
  <div style="font-size:.79rem;color:%s;opacity:.85;margin-top:1px;">%s</div>
  <div style="margin-top:9px;">%s</div>
  <div style="font-size:.66rem;color:%s;opacity:.45;margin-top:5px;">
    last 8 hours &middot; %s &middot; %d cam</div>
</div>""" % (ink["bg"], ink["edge"], ink["fg"], ink["fg"], row["room"],
             ink["fg"], row["zone"].upper(), drawn_room(row, ink),
             ink["fg"], row["headline"], ink["fg"], row["age"],
             ink["fg"], row["sub"], day_strip(recent, row["room"], now),
             ink["fg"], row["recorder"], row["cameras"])


def chip(row, recent, now):
    """A room with nothing wrong. Small on purpose: it is not the news."""
    ink = INK[row["level"]]
    people = int(row["people"]) if pd.notna(row["people"]) else 0
    if row["status"] == "occupied" and people:
        shown = min(people, 5)
        figures = ('<svg width="%d" height="15" viewBox="0 0 %d 26">%s</svg>'
                   % (shown * 8 + 2, shown * 14 + 4,
                      "".join(PERSON.format(x=i * 14, y=0, c=ink["fg"])
                              for i in range(shown))))
        if people > shown:
            figures += ('<span style="font-size:.68rem;opacity:.75;">+%d</span>'
                        % (people - shown))
    else:
        figures = ('<span style="font-size:.7rem;opacity:.5;">%s</span>'
                   % row["headline"])
    return """
<div style="background:%s;border:1px solid %s;border-radius:9px;
            padding:7px 10px 8px;margin-bottom:7px;">
  <div style="display:flex;justify-content:space-between;align-items:center;
              gap:8px;">
    <span style="font-size:.82rem;font-weight:600;color:%s;white-space:nowrap;
                 overflow:hidden;text-overflow:ellipsis;">%s</span>
    <span style="display:flex;align-items:center;gap:3px;color:%s;">%s</span>
  </div>
  <div style="margin-top:6px;">%s</div>
</div>""" % (ink["bg"], ink["edge"], ink["fg"], row["room"], ink["fg"],
             figures, day_strip(recent, row["room"], now, height=5))


def building_bar(df):
    """Every room as one square: the whole campus before anyone scrolls."""
    squares = "".join(
        '<div title="%s &mdash; %s" style="width:19px;height:19px;'
        'border-radius:4px;background:%s;opacity:%s;"></div>'
        % (row["room"], row["headline"], INK[row["level"]]["fg"],
           ".92" if row["level"] != "Green" else ".30")
        for _, row in df.iterrows())
    return ('<div style="display:flex;flex-wrap:wrap;gap:4px;margin:2px 0 6px;">'
            '%s</div>' % squares)


def cards(df, recent, now, renderer, columns):
    for start in range(0, len(df), columns):
        slot = st.columns(columns)
        chunk = df.iloc[start:start + columns]
        for column, (_, row) in zip(slot, chunk.iterrows()):
            column.markdown(renderer(row, recent, now), unsafe_allow_html=True)


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
            " read room data \u2014 it can see the timestamp column and"
            " nothing else, so that a machine in a corridor cupboard cannot"
            " answer who was in which room.\n\nAdd the read-only role from"
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
df = df[df["campus"] == campus]

graded = df.apply(lambda r: grade(r, now), axis=1)
df["level"] = [g[0] for g in graded]
df["headline"] = [g[1] for g in graded]
df["sub"] = [g[2] for g in graded]
df["age"] = df["timestamp"].apply(
    lambda t: "never" if minutes_since(t, now) is None
    else "%s ago" % spell(minutes_since(t, now)))
df = df.sort_values(by=["level", "room"],
                    key=lambda c: c.map(RANK) if c.name == "level" else c)

head_col, status_col = st.columns([3, 2])
head_col.title("EnergyCam \u00b7 %s" % campus)
beat_age = minutes_since(last_beat, now)
if beat_age is None or beat_age > STALE_AFTER_MINUTES:
    status_col.error("Loop silent for %s \u2014 everything below is its last"
                     " known state, not live." % spell(beat_age))
else:
    status_col.success(
        "Live \u00b7 reported %s ago \u00b7 %d rooms \u00b7 %d cameras"
        % (spell(beat_age), len(df), int(df["cameras"].sum())))

st.markdown(building_bar(df), unsafe_allow_html=True)

counts = df["level"].value_counts()
a, b, c, d = st.columns(4)
a.metric("\U0001F534 Long empty", int(counts.get("Red", 0)))
b.metric("\U0001F7E0 Worth a check", int(counts.get("Amber", 0)))
c.metric("\u26AA Not answering", int(counts.get("Fault", 0)))
d.metric("\U0001F7E2 Fine", int(counts.get("Green", 0)))

st.divider()

attention = df[df["level"].isin(["Red", "Amber", "Fault"])]
if attention.empty:
    st.success("Nothing wants attention. Every room is either in use or has"
               " not been empty long enough to matter.")
else:
    st.subheader("Needs attention")
    cards(attention, recent, now, big_card, columns=3)

st.divider()
st.caption("Everything else, by zone. Small on purpose \u2014 these rooms are"
           " fine. The bar under each is the last %d hours, green where people"
           " were seen." % STRIP_HOURS)

rest = df[df["level"] == "Green"]
for zone in [z for z in ZONE_ORDER if z in set(rest["zone"])] + \
        sorted(set(rest["zone"]) - set(ZONE_ORDER)):
    st.markdown("**%s**" % zone)
    if zone == "Server rooms":
        st.caption("Cooled around the clock on purpose, and empty of people"
                   " nearly all of it. Watched and recorded, never flagged.")
    cards(rest[rest["zone"] == zone], recent, now, chip, columns=5)

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
