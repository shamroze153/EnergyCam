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

def figures(count, colour):
    """One figure per person. Past ten they stop being countable anyway."""
    if count <= 0:
        return ('<div style="height:20px;opacity:.28;font-size:.72rem;'
                'letter-spacing:.14em;color:%s;">NOBODY</div>' % colour)
    shown = min(count, 10)
    person = (
        '<svg width="11" height="16" viewBox="0 0 9 14" fill="%s" '
        'style="margin-right:3px;"><circle cx="4.5" cy="3.1" r="3.1"/>'
        '<path d="M4.5 7.5C1.9 7.5 0 9.4 0 11.8V14h9v-2.2c0-2.4-1.9-4.3-4.5-4.3z"/>'
        '</svg>' % colour)
    more = ('<span style="font-size:.74rem;color:%s;opacity:.8;">+%d</span>'
            % (colour, count - shown)) if count > shown else ""
    return ('<div style="height:20px;display:flex;align-items:center;">%s%s</div>'
            % (person * shown, more))


def ac_badge(state, colour):
    """Lit, dim, or dashed with a question mark while nothing has measured it.

    The third one matters most right now. Nothing is calibrated, so every unit
    is unknown, and drawing unknown the same as off would put a confident claim
    on the screen that no measurement stands behind -- the exact claim this
    system exists to make honestly.
    """
    if state == "on":
        return ('<svg width="40" height="22" viewBox="0 0 40 22">'
                '<rect x="1" y="3" width="26" height="10" rx="2.5" fill="none"'
                ' stroke="#2E7D32" stroke-width="1.7"/>'
                '<line x1="4" y1="10" x2="24" y2="10" stroke="#2E7D32"'
                ' stroke-width="1.1"/>'
                '<circle cx="23.5" cy="6" r="1.6" fill="#2E7D32"/>'
                '<path d="M8 17q3 3 6 0t6 0" fill="none" stroke="#2E7D32"'
                ' stroke-width="1.5" stroke-linecap="round" opacity=".75"/>'
                '<text x="30" y="11" font-size="7" fill="#2E7D32"'
                ' font-weight="700">ON</text></svg>')
    if state == "off":
        return ('<svg width="40" height="22" viewBox="0 0 40 22">'
                '<rect x="1" y="3" width="26" height="10" rx="2.5" fill="none"'
                ' stroke="#9A9A9A" stroke-width="1.7"/>'
                '<line x1="4" y1="10" x2="24" y2="10" stroke="#9A9A9A"'
                ' stroke-width="1.1"/>'
                '<circle cx="23.5" cy="6" r="1.6" fill="none"'
                ' stroke="#9A9A9A" stroke-width="1"/>'
                '<text x="29" y="11" font-size="7" fill="#9A9A9A"'
                ' font-weight="700">OFF</text></svg>')
    return ('<svg width="40" height="22" viewBox="0 0 40 22" opacity=".5">'
            '<rect x="1" y="3" width="26" height="10" rx="2.5" fill="none"'
            ' stroke="%s" stroke-width="1.5" stroke-dasharray="3 2.5"/>'
            '<text x="10" y="11.5" font-size="8" fill="%s"'
            ' font-weight="700">?</text></svg>' % (colour, colour))


SLOT_INK = {"occupied": "#7BAE48", "empty": "#DCDCDC", "unknown": "#B4B4B4"}


def day_strip(recent, room, now):
    """The last eight hours as a band: where there were people, where not."""
    mine = recent[recent["room"] == room]
    if mine.empty:
        return ('<div style="height:7px;border-radius:3px;background:#F3F3F3;'
                'margin-top:8px;"></div>')
    start = now - pd.Timedelta(hours=STRIP_HOURS)
    states = mine["status"].tolist()
    # Seconds from the start of the window, on both sides. Doing this in epoch
    # integers instead looks tidier and is a trap: in pandas 3 a Series of
    # timestamps converts to int64 in microseconds while Timestamp.value is
    # nanoseconds, so the two scales differ by a thousand. Nothing raises --
    # every mark simply lands past every event, every slot takes the last known
    # state, and the strip comes out a single convincing block of one colour.
    # A wrong picture that looks right is worse than one that fails.
    stamps = (mine["timestamp"] - start).dt.total_seconds().to_numpy()
    span = (now - start).total_seconds()
    marks = np.linspace(0, span, STRIP_SLOTS, endpoint=False)
    # The state at each mark is whatever the last change before it said. -1
    # means the loop had not recorded this room yet that far back, which is
    # left blank rather than guessed at.
    where = np.searchsorted(stamps, marks, side="right") - 1
    rects = []
    for slot, index in enumerate(where):
        colour = "#F3F3F3" if index < 0 else SLOT_INK.get(states[index], "#F3F3F3")
        rects.append('<rect x="%d" y="0" width="1" height="6" fill="%s"/>'
                     % (slot, colour))
    return ('<svg viewBox="0 0 %d 6" preserveAspectRatio="none" '
            'style="width:100%%;height:7px;margin-top:8px;border-radius:3px;">'
            '%s</svg>' % (STRIP_SLOTS, "".join(rects)))


def tile(row, recent, now):
    ink = INK[row["level"]]
    people = int(row["people"]) if pd.notna(row["people"]) else 0
    flag = ""
    if row["level"] in ("Red", "Amber"):
        flag = ('<span style="background:%s;color:#fff;font-size:.6rem;'
                'font-weight:700;padding:2px 6px;border-radius:9px;'
                'letter-spacing:.06em;">ACTION</span>' % ink["fg"])
    return """
<div style="background:{bg};border:1px solid {edge};border-left:5px solid {fg};
            border-radius:11px;padding:11px 13px 12px;margin-bottom:11px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:.63rem;letter-spacing:.09em;color:{fg};
                 opacity:.65;">{zone}</span>{flag}
  </div>
  <div style="display:flex;justify-content:space-between;align-items:flex-start;
              margin-top:3px;">
    <span style="font-size:1rem;font-weight:650;color:{fg};">{room}</span>
    {ac}
  </div>
  <div style="margin:9px 0 6px;">{figures}</div>
  <div style="font-size:1.2rem;font-weight:700;color:{fg};">{headline}</div>
  <div style="font-size:.75rem;color:{fg};opacity:.78;">{sub}</div>
  {strip}
  <div style="font-size:.67rem;color:{fg};opacity:.5;margin-top:5px;">
    {recorder} · {cameras} cam · {age}</div>
</div>""".format(
        bg=ink["bg"], fg=ink["fg"], edge=ink["edge"], flag=flag,
        zone=row["zone"].upper(), room=row["room"],
        ac=ac_badge(row["ac_state"] if pd.notna(row["ac_state"]) else None,
                    ink["fg"]),
        figures=figures(people if row["status"] == "occupied" else 0, ink["fg"]),
        headline=row["headline"], sub=row["sub"],
        strip=day_strip(recent, row["room"], now),
        recorder=row["recorder"], cameras=row["cameras"], age=row["age"])


def grid(df, recent, now, columns=4):
    for start in range(0, len(df), columns):
        slot = st.columns(columns)
        chunk = df.iloc[start:start + columns]
        for column, (_, row) in zip(slot, chunk.iterrows()):
            column.markdown(tile(row, recent, now), unsafe_allow_html=True)


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
df = df[df["campus"] == campus]

graded = df.apply(lambda r: grade(r, now), axis=1)
df["level"] = [g[0] for g in graded]
df["headline"] = [g[1] for g in graded]
df["sub"] = [g[2] for g in graded]
df["age"] = df["timestamp"].apply(
    lambda t: "never" if minutes_since(t, now) is None
    else "%s ago" % spell(minutes_since(t, now)))

head, status = st.columns([3, 2])
head.title("EnergyCam · %s" % campus)
beat_age = minutes_since(last_beat, now)
if beat_age is None or beat_age > STALE_AFTER_MINUTES:
    status.error("Loop silent for %s — everything below is its last known"
                 " state, not live." % spell(beat_age))
else:
    status.success("Live · reported %s ago · %d rooms · %d cameras"
                   % (spell(beat_age), len(df), int(df["cameras"].sum())))

counts = df["level"].value_counts()
a, b, c, d = st.columns(4)
a.metric("🔴 Long empty", int(counts.get("Red", 0)))
b.metric("🟠 Worth a check", int(counts.get("Amber", 0)))
c.metric("⚪ Not answering", int(counts.get("Fault", 0)))
d.metric("🟢 Fine", int(counts.get("Green", 0)))

st.divider()

attention = df[df["level"].isin(["Red", "Amber", "Fault"])].sort_values(
    by=["level", "room"],
    key=lambda c: c.map(RANK) if c.name == "level" else c)
if attention.empty:
    st.success("Nothing wants attention. Every room is either in use or has"
               " not been empty long enough to matter.")
else:
    st.subheader("Needs attention")
    grid(attention, recent, now)

st.divider()

for zone in [z for z in ZONE_ORDER if z in set(df["zone"])] + \
        sorted(set(df["zone"]) - set(ZONE_ORDER)):
    here = df[df["zone"] == zone].sort_values(
        by=["level", "room"],
        key=lambda c: c.map(RANK) if c.name == "level" else c)
    st.subheader(zone)
    if zone == "Server rooms":
        st.caption("Cooled around the clock on purpose, and empty of people"
                   " nearly all of it. Watched and recorded, never flagged.")
    grid(here, recent, now)

st.caption("Strip under each tile: the last %d hours. Green where people were"
           " seen, grey where the room was empty, blank where nothing was"
           " recorded yet. The AC badge is dashed because no unit has been"
           " calibrated — that is unknown, not off."
           % STRIP_HOURS)

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
