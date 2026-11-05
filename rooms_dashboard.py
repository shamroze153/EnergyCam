"""One page per campus: every room, colour first.

The first version put the rooms behind four tabs, which buried the only thing
this page exists to show. A room that has been empty for an hour with the unit
running is the reason to open it at all, and it was three clicks away on a tab
nobody had reason to press. Tabs sort rooms by what kind of room they are;
whoever opens this wants them sorted by whether anything is wrong.

So: one page, one card per room, ordered by how much attention it wants, and
the colour carries the answer before any of the words are read.

    streamlit run rooms_dashboard.py

Connects as energycam_dashboard, which reads and cannot write, via
DASHBOARD_DATABASE_URL in .env. The camera machine's own credential will not
work here by design: it is granted the timestamp column and nothing more.
"""
import os
from datetime import timedelta, timezone

import pandas as pd
import psycopg2
import streamlit as st
import yaml
from streamlit_autorefresh import st_autorefresh

PKT = timezone(timedelta(hours=5))

# The loop beats every five minutes. Two missed beats is a real gap rather than
# a slow cycle, and past that nothing here should be acted on: the rooms would
# still be sitting in their last known state, looking perfectly current.
STALE_AFTER_MINUTES = 11

LOOKS = {
    "Red":   {"bg": "#FCEBEB", "fg": "#A32D2D", "edge": "#E5B4B4", "dot": "🔴"},
    "Amber": {"bg": "#FAEEDA", "fg": "#854F0B", "edge": "#E8CFA3", "dot": "🟠"},
    "Green": {"bg": "#EAF3DE", "fg": "#3B6D11", "edge": "#C9DFB0", "dot": "🟢"},
    "Fault": {"bg": "#EDEDED", "fg": "#555555", "edge": "#D2D2D2", "dot": "⚪"},
}
ORDER = {"Red": 0, "Amber": 1, "Fault": 2, "Green": 3}

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


@st.cache_data(ttl=20)
def load_rooms_config(path="rooms.yaml"):
    cfg = yaml.safe_load(open(path))
    recorders = cfg["recorders"]
    rows = []
    for room in cfg["rooms"]:
        alerts = room.get("alert") != "never"
        if room["ac"] == "visible" and alerts:
            kind, caption = "Unit in frame", "AC not calibrated yet"
        elif room["ac"] == "hidden" and alerts:
            kind, caption = "Unit out of frame", "someone has to look"
        else:
            kind, caption = "No unit", "counted only"
        rows.append({
            "room": room["name"],
            "recorder": room["recorder"],
            "campus": recorders[room["recorder"]].get("campus", "unknown"),
            "cameras": len(room["channels"]),
            "kind": kind,
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
        beat = pd.read_sql_query(
            "SELECT max(timestamp) AS last_beat FROM heartbeat", conn)
    finally:
        conn.close()
    for column in ("empty_since", "timestamp"):
        latest[column] = pd.to_datetime(latest[column], utc=True)
    return latest, pd.to_datetime(beat["last_beat"].iloc[0], utc=True)


@st.cache_data(ttl=60)
def load_history(days=7):
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        df = pd.read_sql_query(
            "SELECT timestamp, room, status, people FROM room_events"
            " WHERE timestamp >= now() - interval '%d days'"
            " AND status = 'occupied' ORDER BY timestamp" % days, conn)
    finally:
        conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def to_local(series):
    """Series.tz_convert works on the index; the values need .dt."""
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
    """Colour, headline, and the line underneath it."""
    if row["status"] == "unknown" or pd.isna(row["status"]):
        if pd.isna(row["timestamp"]):
            return "Fault", "Not sampled", "the loop has not reached it"
        return "Fault", "No answer", "camera did not reply"

    if row["status"] == "occupied":
        people = int(row["people"]) if pd.notna(row["people"]) else 0
        return "Green", "%d %s" % (people, "person" if people == 1 else "people"), \
            row["caption"]

    empty = minutes_since(row["empty_since"], now)
    threshold = row["empty_after"]
    headline = "Empty %s" % spell(empty)
    if not threshold or empty is None:
        return "Green", headline, row["caption"]
    if empty >= threshold * 2:
        return "Red", headline, "well past %d min — check the AC" % threshold
    if empty >= threshold:
        return "Amber", headline, "past %d min — check the AC" % threshold
    return "Green", headline, row["caption"]


def card(row):
    look = LOOKS[row["level"]]
    return """
<div style="background:{bg};border:1px solid {edge};border-radius:10px;
            padding:12px 14px;margin-bottom:10px;min-height:118px;">
  <div style="font-size:0.78rem;color:{fg};opacity:0.75;">{dot} {kind}</div>
  <div style="font-size:1.02rem;font-weight:600;color:{fg};margin:2px 0 6px;">
    {room}</div>
  <div style="font-size:1.28rem;font-weight:700;color:{fg};">{headline}</div>
  <div style="font-size:0.78rem;color:{fg};opacity:0.8;margin-top:4px;">
    {caption}</div>
  <div style="font-size:0.72rem;color:{fg};opacity:0.55;margin-top:6px;">
    {recorder} · {cameras} cam · {age}</div>
</div>""".format(room=row["room"], headline=row["headline"],
                 caption=row["sub"], kind=row["kind"],
                 recorder=row["recorder"], cameras=row["cameras"],
                 age=row["age"], **look)


def grid(df, columns=4):
    for start in range(0, len(df), columns):
        slot = st.columns(columns)
        for column, (_, row) in zip(slot, df.iloc[start:start + columns].iterrows()):
            column.markdown(card(row), unsafe_allow_html=True)


# --------------------------------------------------------------------------

try:
    rooms = load_rooms_config()
    latest, last_beat = load_state()
except FileNotFoundError:
    st.error("rooms.yaml not found. Run this from the project folder.")
    st.stop()
except psycopg2.Error as e:
    if getattr(e, "pgcode", None) == "42501" and USING_APP_CREDENTIAL:
        st.error(
            "This is connecting as the camera machine, which is not allowed to"
            " read room data — it can see the timestamp column and nothing"
            " else, so that a machine in a corridor cupboard cannot answer who"
            " was in which room.\n\n"
            "Add the read-only role from sql/02_roles.sql to .env as"
            " `DASHBOARD_DATABASE_URL`. Do not widen the camera machine's"
            " grants to make this page work.")
    else:
        st.error("Database unreachable (%s). The driver's message is withheld"
                 " because it contains connection details." % type(e).__name__)
    st.stop()

now = pd.Timestamp.now(tz="UTC")
df = rooms.merge(latest, on="room", how="left")
df["status"] = df["status"].fillna("unknown")

campuses = sorted(df["campus"].unique())
if len(campuses) > 1:
    campus = st.selectbox("Campus", campuses)
else:
    campus = campuses[0]
df = df[df["campus"] == campus]

graded = df.apply(lambda r: grade(r, now), axis=1)
df["level"] = [g[0] for g in graded]
df["headline"] = [g[1] for g in graded]
df["sub"] = [g[2] for g in graded]
df["age"] = df["timestamp"].apply(
    lambda t: "never" if minutes_since(t, now) is None
    else "%s ago" % spell(minutes_since(t, now)))
df = df.sort_values(by=["level", "room"],
                    key=lambda c: c.map(ORDER) if c.name == "level" else c)

head, status = st.columns([3, 2])
head.title("EnergyCam · %s" % campus)

beat_age = minutes_since(last_beat, now)
if beat_age is None or beat_age > STALE_AFTER_MINUTES:
    status.error("Loop silent for %s — everything below is its last known"
                 " state, not live." % spell(beat_age))
else:
    status.success("Live · loop reported %s ago · %d rooms · %d cameras"
                   % (spell(beat_age), len(df), int(df["cameras"].sum())))

counts = df["level"].value_counts()
attention = df[df["level"].isin(["Red", "Amber", "Fault"])]

a, b, c, d = st.columns(4)
a.metric("🔴 Long empty", int(counts.get("Red", 0)))
b.metric("🟠 Worth a check", int(counts.get("Amber", 0)))
c.metric("⚪ Not answering", int(counts.get("Fault", 0)))
d.metric("🟢 Fine", int(counts.get("Green", 0)))

st.divider()

if attention.empty:
    st.success("Nothing needs attention. Every room is either in use or has"
               " not been empty long enough to matter.")
else:
    st.subheader("Needs attention")
    grid(attention)
    st.divider()

st.subheader("All rooms")
st.caption("Ordered by how much attention each one wants. Stairs, corridors,"
           " outdoor areas and the server rooms are counted and kept but never"
           " flagged — there is nothing in them to switch off, and the server"
           " rooms are cooled around the clock on purpose.")
grid(df)

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
