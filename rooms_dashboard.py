"""Live view of every room across the recorders.

Three pages, because the rooms are not all answerable to the same question:

  Monitored    the unit is in frame, so once the units are calibrated this page
               can say a room is empty AND still cooling -- waste, stated
               outright, with nobody sent to check.
  Check round  the room has a unit this camera cannot see. The page can only
               say how long it has been empty; somebody walks past and looks.
  Faults       cameras that did not answer, and rooms whose reading is too old
               to act on.

Everything else -- stairs, corridors, the car park, the server rooms -- is
counted and kept, and never shown as needing anything, because there is nothing
in those rooms to switch off.

    streamlit run rooms_dashboard.py
"""
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import psycopg2
import streamlit as st
import yaml
from streamlit_autorefresh import st_autorefresh

PKT = timezone(timedelta(hours=5))

# The loop beats every five minutes. Two missed beats is a real gap rather than
# a slow cycle, and after that nothing on this page should be trusted: the rooms
# would still be sitting there in their last known state, looking current.
STALE_AFTER_MINUTES = 11

st.set_page_config(page_title="EnergyCam — Rooms", layout="wide", page_icon="🏢")
st_autorefresh(interval=30000, key="rooms_refresh")

try:
    DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")


@st.cache_data(ttl=20)
def load_rooms_config(path="rooms.yaml"):
    cfg = yaml.safe_load(open(path))
    rows = []
    for room in cfg["rooms"]:
        alerts = room.get("alert") != "never"
        if room["ac"] == "visible" and alerts:
            page = "Monitored"
        elif room["ac"] == "hidden" and alerts:
            page = "Check round"
        else:
            page = "Counted only"
        rows.append({"room": room["name"], "recorder": room["recorder"],
                     "cameras": len(room["channels"]), "ac": room["ac"],
                     "page": page,
                     "empty_after": room.get("empty_after_minutes")})
    return pd.DataFrame(rows)


@st.cache_data(ttl=20)
def load_state():
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        latest = pd.read_sql_query(
            "SELECT DISTINCT ON (room) room, recorder, status, people,"
            " empty_since, ac_state, timestamp"
            " FROM room_events ORDER BY room, timestamp DESC", conn)
        beat = pd.read_sql_query(
            "SELECT max(timestamp) AS last_beat FROM heartbeat", conn)
    finally:
        conn.close()
    for frame, columns in ((latest, ("empty_since", "timestamp")),
                           (beat, ("last_beat",))):
        for column in columns:
            frame[column] = pd.to_datetime(frame[column], utc=True)
    return latest, beat["last_beat"].iloc[0]


@st.cache_data(ttl=60)
def load_history(days=7):
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        df = pd.read_sql_query(
            "SELECT timestamp, room, status, people FROM room_events"
            " WHERE timestamp >= now() - interval '%d days'"
            " ORDER BY timestamp" % days, conn)
    finally:
        conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def local(series_or_value):
    return series_or_value.tz_convert("Asia/Karachi")


def minutes_since(when, now):
    if pd.isna(when):
        return None
    return (now - when).total_seconds() / 60.0


def grade(row, now):
    """Green, Amber, Red or Fault -- and the sentence that goes with it."""
    if row["status"] == "unknown" or pd.isna(row["status"]):
        return "Fault", "camera did not answer"
    if row["status"] == "occupied":
        people = int(row["people"]) if pd.notna(row["people"]) else 0
        return "Green", "%d %s" % (people, "person" if people == 1 else "people")
    empty = minutes_since(row["empty_since"], now)
    if empty is None:
        return "Green", "empty"
    threshold = row.get("empty_after")
    if not threshold:
        return "Green", "empty %d min" % empty
    if empty >= threshold * 2:
        return "Red", "empty %d min" % empty
    if empty >= threshold:
        return "Amber", "empty %d min" % empty
    return "Green", "empty %d min" % empty


BADGE = {"Red": "🔴", "Amber": "🟠", "Green": "🟢", "Fault": "⚪"}
ORDER = {"Red": 0, "Amber": 1, "Fault": 2, "Green": 3}


def show_page(df, now, empty_message, note=None):
    if df.empty:
        st.info(empty_message)
        return
    if note:
        st.caption(note)
    df = df.copy()
    graded = df.apply(lambda r: grade(r, now), axis=1)
    df["level"] = [g[0] for g in graded]
    df["detail"] = [g[1] for g in graded]
    df["age"] = df["timestamp"].apply(
        lambda t: "%d min ago" % minutes_since(t, now))
    df = df.sort_values(by=["level", "room"],
                        key=lambda c: c.map(ORDER) if c.name == "level" else c)
    st.dataframe(
        pd.DataFrame({
            "": df["level"].map(BADGE),
            "Room": df["room"],
            "Recorder": df["recorder"],
            "Cameras": df["cameras"],
            "State": df["detail"],
            "Last change": df["age"],
        }),
        hide_index=True, use_container_width=True)


st.title("EnergyCam — Rooms")

try:
    rooms = load_rooms_config()
    latest, last_beat = load_state()
except FileNotFoundError:
    st.error("rooms.yaml not found. Run this from the project folder.")
    st.stop()
except psycopg2.Error as e:
    st.error("Database unreachable (%s). The driver's message is withheld"
             " because it contains connection details." % type(e).__name__)
    st.stop()

now = pd.Timestamp.now(tz="UTC")

if latest.empty:
    st.warning("No readings yet. Start room_loop.py.")
    st.stop()

beat_age = minutes_since(last_beat, now)
if beat_age is None or beat_age > STALE_AFTER_MINUTES:
    st.error(
        "The room loop has not reported for %s. Everything below is its last"
        " known state and is no longer live -- an empty room on this page may"
        " have filled up since."
        % ("%d minutes" % beat_age if beat_age else "an unknown time"))
else:
    st.caption("Loop reported %d min ago." % beat_age)

df = rooms.merge(latest, on="room", how="left")
df["status"] = df["status"].fillna("unknown")

counts = df.apply(lambda r: grade(r, now)[0], axis=1)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Rooms", len(df))
col2.metric("🔴 Long empty", int((counts == "Red").sum()))
col3.metric("🟠 Worth a check", int((counts == "Amber").sum()))
col4.metric("⚪ Not answering", int((counts == "Fault").sum()))

monitored, check, counted, faults = st.tabs(
    ["Monitored", "Check round", "Counted only", "Faults"])

with monitored:
    st.caption(
        "The unit is in frame in these rooms. Once each one is calibrated this"
        " page will say whether it is still running in an empty room. Until"
        " then it reports occupancy only -- the AC column is blank because"
        " nothing has measured it, not because the unit is off.")
    show_page(df[(df["page"] == "Monitored") & (df["status"] != "unknown")],
              now, "No rooms on this page.")

with check:
    st.caption(
        "These rooms have a unit the camera cannot see, so the most this page"
        " can say is how long the room has been empty. Somebody walks past and"
        " looks.")
    show_page(df[(df["page"] == "Check round") & (df["status"] != "unknown")],
              now, "No rooms on this page.")

with counted:
    show_page(df[(df["page"] == "Counted only") & (df["status"] != "unknown")],
              now, "No rooms on this page.",
              note="Stairs, corridors, outdoor areas and the server rooms."
                   " Watched and recorded, never flagged: there is nothing in"
                   " them to switch off, and the server rooms are cooled"
                   " around the clock on purpose.")

with faults:
    broken = df[df["status"] == "unknown"]
    if broken.empty:
        st.success("Every camera answered on the last pass.")
    else:
        st.caption(
            "A room lands here when a camera did not answer. It is not being"
            " reported as empty, because nobody looked -- that is the point of"
            " this page rather than a quiet zero.")
        show_page(broken, now, "")

st.divider()

with st.expander("When rooms fill and empty", expanded=False):
    st.caption(
        "The reason for recording all of this. Built from the changes, so it"
        " only covers the time the loop was actually running.")
    try:
        history = load_history()
    except psycopg2.Error as e:
        st.error("Could not load history (%s)." % type(e).__name__)
        history = pd.DataFrame()

    if history.empty:
        st.info("No history yet.")
    else:
        history["day"] = local(history["timestamp"]).dt.date
        days = sorted(history["day"].unique(), reverse=True)
        day = st.selectbox("Day", days)
        chosen = history[history["day"] == day]
        busy = chosen[chosen["status"] == "occupied"]
        if busy.empty:
            st.info("Nobody was seen anywhere on that day.")
        else:
            summary = busy.groupby("room").agg(
                first_seen=("timestamp", "min"),
                last_seen=("timestamp", "max"),
                most_at_once=("people", "max")).reset_index()
            summary["first_seen"] = local(summary["first_seen"]).dt.strftime("%H:%M")
            summary["last_seen"] = local(summary["last_seen"]).dt.strftime("%H:%M")
            st.dataframe(
                summary.rename(columns={
                    "room": "Room",
                    "first_seen": "First seen",
                    "last_seen": "Last seen",
                    "most_at_once": "Most at once"}),
                hide_index=True, use_container_width=True)
            st.caption(
                "First and last seen are when people were detected, not when"
                " the building opened: a room nobody entered before 11am"
                " reports 11am.")
