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
import hmac
import os
import time
import warnings
from datetime import timedelta, timezone
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.express as px
import psycopg2

# pandas prefers SQLAlchemy and says so once per query. Four lines every time
# the page refreshes is how a real message gets missed, and the connection
# works: these are plain SELECTs against psycopg2, which is what the loop
# uses too.
warnings.filterwarnings(
    "ignore", message="pandas only supports SQLAlchemy connectable",
    category=UserWarning)
import streamlit as st
import yaml
from streamlit_autorefresh import st_autorefresh

from schedule import (AFTER_HOURS, WEEKEND, WORKING, describe,
                      split_by_period, wait_before_reporting)
import overview  # noqa: E402  (the front pages: welcome and campus overview)

PKT = timezone(timedelta(hours=5))

# The loop beats every five minutes. Two missed beats is a real gap rather than
# a slow cycle, and past that nothing here should be acted on: the tiles would
# still be sitting in their last known state, looking perfectly current.
# The loop beats once a minute, so three missed beats is something to say
# out loud. This used to allow eleven, which was two missed beats when the
# loop beat every five minutes -- the same judgement, at the new cadence.
STALE_AFTER_MINUTES = 3

SNAPSHOT_DIR = "snapshots"

STRIP_HOURS = 8
STRIP_SLOTS = 96                      # five minutes each

# A day is the window a person actually reasons in: "nobody came in before
# eleven", "it emptied at seven". Eight hours is right for a tile at a glance,
# and far too short for the question of what a room's day looks like.
DETAIL_HOURS = 24
DETAIL_SLOTS = 288                    # five minutes each, again

# Two palettes, one set of meanings. The same red means the same thing in
# both; only the surface under it changes. They live together here because
# they were scattered through the file as literals, and a colour you cannot
# find is a colour you cannot change -- which is how a page ends up half dark
# and half white.
#
# Dark is the default: this page is read in the evening, when the rooms empty,
# and a mostly-white screen at nine at night is one people stop opening. Light
# is for daylight, a projector, and anyone printing it.

THEMES = {
    # The neutrals and the blue of the front pages (overview.TOKENS), so a
    # view opened from the overview does not change colour under the reader.
    # Blue is people; green is fine; red and amber are the two grades of
    # "go and check", always with words beside them.
    "dark": {
        "page": "#0d0d0d", "surface": "#171716", "sunken": "#1f1f1d",
        "line": "#2b2b29", "text": "#f0efec", "muted": "#9a998f",
        "faint": "#6b6a64",
        "band": "#121211", "band_line": "#232321", "band_text": "#f0efec",
        "room_fill": "#1b1b1a", "ac_on": "#0ca30c", "ac_off": "#6b6a64",
        "slot_occupied": "#3987e5", "slot_empty": "#2a2a28",
        "slot_unknown": "#4a4a46", "slot_none": "#1f1f1d",
        "rank_bar": "#d03b3b", "good_bg": "#132013", "good_line": "#1f3a1f",
        "good_fg": "#7fd67f",
        "ink": {
            "Red":   {"bg": "#241414", "fg": "#f0918f", "edge": "#4a2222",
                      "bar": "#d03b3b"},
            "Amber": {"bg": "#241d10", "fg": "#f2c46a", "edge": "#4a3a1a",
                      "bar": "#fab219"},
            "Green": {"bg": "#132013", "fg": "#7fd67f", "edge": "#1f3a1f",
                      "bar": "#0ca30c"},
            "Cool":  {"bg": "#101a24", "fg": "#86b6ef", "edge": "#1c3350",
                      "bar": "#3987e5"},
            "Fault": {"bg": "#1a1a19", "fg": "#a3a29a", "edge": "#2b2b29",
                      "bar": "#6b6a64"},
        },
    },
    "light": {
        "page": "#f4f4f1", "surface": "#fcfcfb", "sunken": "#f0efec",
        "line": "#e1e0d9", "text": "#0b0b0b", "muted": "#6b6a64",
        "faint": "#9a998f",
        "band": "#0b0b0b", "band_line": "#0b0b0b", "band_text": "#f0efec",
        "room_fill": "#ffffff", "ac_on": "#0ca30c", "ac_off": "#9a998f",
        "slot_occupied": "#2a78d6", "slot_empty": "#e1e0d9",
        "slot_unknown": "#c3c2b7", "slot_none": "#f0efec",
        "rank_bar": "#d03b3b", "good_bg": "#eef7ee", "good_line": "#c9e6c9",
        "good_fg": "#006300",
        "ink": {
            "Red":   {"bg": "#fdf0f0", "fg": "#9b2c2c", "edge": "#efc4c4",
                      "bar": "#d03b3b"},
            "Amber": {"bg": "#fdf6e7", "fg": "#8a5209", "edge": "#ecd6a6",
                      "bar": "#eda100"},
            "Green": {"bg": "#eef7ee", "fg": "#006300", "edge": "#c9e6c9",
                      "bar": "#0ca30c"},
            "Cool":  {"bg": "#edf3fa", "fg": "#184f95", "edge": "#bcd3e8",
                      "bar": "#2a78d6"},
            "Fault": {"bg": "#f0efec", "fg": "#52514e", "edge": "#d9d8d1",
                      "bar": "#9a998f"},
        },
    },
}

# Rebound by use_theme() before anything draws. Module level because Streamlit
# reruns the whole script on every interaction: there is no state to carry
# between runs, so the globals are set once per run and every drawing function
# reads whichever palette is in force.
PAGE = SURFACE = SUNKEN = LINE = TEXT = MUTED = FAINT = ""
BAND = BAND_LINE = BAND_TEXT = ROOM_FILL = AC_ON = AC_OFF = ""
RANK_BAR = GOOD_BG = GOOD_LINE = GOOD_FG = NO_DATA = ""
SLOT_INK = {}
INK = {}

# The campus and theme every internal link carries. Filled in by the page
# once it has read the address; empty while only the helpers are loaded.
LINK_BASE = {}


def use_theme(mode):
    global PAGE, SURFACE, SUNKEN, LINE, TEXT, MUTED, FAINT
    global BAND, BAND_LINE, BAND_TEXT, ROOM_FILL, AC_ON, AC_OFF
    global RANK_BAR, GOOD_BG, GOOD_LINE, GOOD_FG, SLOT_INK, NO_DATA, INK
    t = THEMES.get(mode, THEMES["dark"])
    PAGE, SURFACE, SUNKEN = t["page"], t["surface"], t["sunken"]
    LINE, TEXT, MUTED, FAINT = t["line"], t["text"], t["muted"], t["faint"]
    BAND, BAND_LINE, BAND_TEXT = t["band"], t["band_line"], t["band_text"]
    ROOM_FILL, AC_ON, AC_OFF = t["room_fill"], t["ac_on"], t["ac_off"]
    RANK_BAR, GOOD_BG = t["rank_bar"], t["good_bg"]
    GOOD_LINE, GOOD_FG = t["good_line"], t["good_fg"]
    SLOT_INK = {"occupied": t["slot_occupied"], "empty": t["slot_empty"],
                "unknown": t["slot_unknown"]}
    NO_DATA = t["slot_none"]
    INK = t["ink"]


use_theme("dark")

RANK = {"Red": 0, "Amber": 1, "Cool": 2, "Fault": 3, "Green": 4}

# How long somebody sits in a room with the unit off before it is worth
# mentioning. Short enough to matter, long enough that walking in and not
# having switched it on yet is not a fault.
COLD_AFTER_MINUTES = 30
# Inside first, outside last, and the channels that show nothing at the very
# end. A zone not listed here still appears, sorted after these, so adding a
# campus does not mean remembering to come back and edit this.
ZONE_ORDER = ["Offices", "H offices", "Entrance", "H entrance", "Basement",
              "Cafe & common", "H common", "Server rooms",
              "Outside & plant", "H perimeter", "Unused"]

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


def why_unreachable(e):
    """Name the cause from the driver's text, without repeating the text.

    Withholding the message entirely was the cautious choice and the wrong
    one. It carries the host, the user and the database name, so it cannot
    be printed -- but what it *says* is the only thing that separates a
    wrong password from a role that was never created from a host that does
    not resolve, and those have completely different answers. Three deploys
    were spent guessing between them.

    So the text is read and thrown away, and only the verdict is shown.
    """
    text = str(e).lower()
    if "password authentication failed" in text:
        return ("The password was refused. Either it is not the one this"
                " role has, or the role does not exist -- PostgreSQL"
                " answers both the same way, on purpose. Check with:"
                "\n\n    SELECT rolname FROM pg_roles"
                " WHERE rolname LIKE 'energycam%';")
    if "does not exist" in text:
        return ("The role or the database named in the connection string"
                " does not exist. If the roles were never created, that is"
                " sql/02_roles.sql, then sql/04_rooms.sql for the grants.")
    if "tenant or user not found" in text:
        return ("The pooler does not know this user. Through the pooler the"
                " user name is role.projectref -- the role, a dot, then the"
                " project's reference -- not the bare role name.")
    if "circuit breaker" in text:
        return ("The pooler has stopped accepting this login for a few"
                " minutes after too many failed attempts. Wait five minutes;"
                " if it comes back, the password is wrong.")
    if "could not translate host name" in text or "nodename nor" in text:
        return ("The host name does not resolve: either this machine is not"
                " on the internet right now, or the address is mistyped."
                " Check the internet first -- the camera cable carries no"
                " internet, only the Wi-Fi does.")
    if ("network is unreachable" in text or "no route to host" in text
            or "unreachable network" in text or "10051" in text
            or "10065" in text):
        return ("This machine cannot reach the internet right now. The camera"
                " cable carries no internet; check that the Wi-Fi is on and"
                " connected. The page tries again by itself every thirty"
                " seconds.")
    if ("max client" in text or "emaxconn" in text or "too many clients" in text
            or "remaining connection slots" in text):
        return ("The database has too many connections open at once. Close"
                " any extra copies of this page -- each open tab asks for its"
                " own -- and it clears within a minute.")
    if ("server closed the connection" in text or "connection reset" in text
            or "connection abort" in text or "could not receive data" in text
            or "eof detected" in text or "10053" in text or "10054" in text):
        return ("The connection dropped part way: the internet blinked, or the"
                " database restarted. It usually comes back by itself; this"
                " page tries again every thirty seconds.")
    if "timeout" in text or "timed out" in text:
        return ("Nothing answered in time. From a host, this is usually"
                " Supabase's direct address, which answers only on IPv6 --"
                " use the Session pooler string instead.")
    if "connection refused" in text:
        return ("The host answered and refused the port. Check the port in"
                " the string: the pooler is not always 5432.")
    if "pg_hba" in text or "ssl" in text:
        return ("The server refused the connection's settings. DB_SSLMODE"
                " should be \"require\".")
    return ("The driver gave no cause this page recognises. Running the"
            " same connection string from the office machine will show the"
            " message in full, where it is safe to read.")


def masked_text(e, url):
    """The driver's own words, with everything that identifies the database
    taken out.

    The verdict above is a guess from the text; this is the text. With the
    host, the user, the password and any address replaced by stars, what
    is left -- "Network is unreachable", "max clients reached" -- says what
    went wrong and nothing about where the database lives, so it can be
    shown, photographed and pasted into a chat.
    """
    import re
    from urllib.parse import unquote, urlparse

    text = " ".join(str(e).split())
    secrets = []
    try:
        parts = urlparse(url or "")
        for part in (parts.hostname, parts.username, parts.password,
                     (parts.path or "").lstrip("/")):
            if part:
                secrets += [part, unquote(part)]
        if parts.username:
            secrets += unquote(parts.username).split(".")
    except ValueError:
        pass
    keep = {"postgres"}          # the default database: it names nothing
    for secret in sorted({x for x in secrets if x and len(x) >= 3
                          and x not in keep}, key=len, reverse=True):
        text = text.replace(secret, "***")
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "*.*.*.*", text)
    text = re.sub(r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{0,4}\b", "*:*",
                  text)
    text = re.sub(r"[\w.-]+\.supabase\.(?:co|com)", "***", text)
    return text[:400]


def connection_hint(url):
    """Why this probably failed, without printing the credential.

    The message on its own is correct and useless: it withholds the
    driver's text because that text carries the host, the user and the
    database name, and this page gets photographed. But "unreachable" sends
    somebody hunting through firewall rules when the actual cause is
    usually one of two things, and both are visible from here without
    revealing anything.

    The first is a connection string that was never filled in -- the
    example from the documentation pasted whole, dots and all. The second
    only happens when hosted: Supabase's direct host answers on IPv6, and a
    host that is IPv4-only cannot reach it however correct the password is.
    The pooler address is the same database over IPv4.
    """
    if not url:
        return ("\n\nNo connection string is set at all. On this machine that"
                " is DASHBOARD_DATABASE_URL in .env; when hosted it goes in"
                " the host's secrets, never in the repository.")
    if "..." in url:
        return ("\n\nThe connection string still has `...` in it, so it is"
                " the example from the documentation rather than the real"
                " one. Copy the DASHBOARD_DATABASE_URL line out of .env on"
                " the office machine and paste that value instead.")
    if ".supabase.co" in url and "pooler" not in url:
        return ("\n\nIf this page is hosted rather than on the office"
                " machine: Supabase's direct host answers on IPv6 and most"
                " hosts only speak IPv4, which fails exactly like a wrong"
                " password. Use the Session pooler string from Supabase ->"
                " Project Settings -> Database instead, keeping the"
                " energycam_dashboard role.")
    return ""


def guard():
    """Ask for the shared word before any of this is drawn.

    On the office network the page needs no door: whoever is on the WiFi is
    already in the building. Put it somewhere reachable from home and that
    stops being true, and what is behind it is not a chart of kilowatts --
    it is which rooms people sat in, what time each of them arrived and what
    time they left, grouped by department. That is a record about identified
    people at work, and the whole of it is one URL away from anyone the URL
    reaches. It can also now be written to: the meter and solar readings go
    in from this page.

    So the door is here, in the application, rather than left to whatever
    the host offers. A host's own sharing settings may be the better lock
    where they exist, but they are not everywhere and they are not ours;
    this works wherever the page is put.

    Set DASHBOARD_PASSWORD -- in Streamlit's secrets when hosted, in .env on
    the laptop. Unset means no door, which is right for a machine on the
    office desk and wrong for anything with a public address, so the page
    says which one it is rather than being quietly open.

    What this is not: a login. There are no accounts and no record of who
    looked, so it keeps out passers-by and search engines, not a colleague
    who has been told the word. For anything stronger the host's own viewer
    list is the answer.
    """
    wanted = _setting("DASHBOARD_PASSWORD")
    if not wanted:
        return
    if st.session_state.get("let_in"):
        return

    st.markdown("### EnergyCam")
    st.caption("140-H · Disrupt")
    typed = st.text_input("Password", type="password",
                          label_visibility="collapsed",
                          placeholder="password")
    if typed:
        # compare_digest so the time taken does not vary with how much of
        # the word is right, which is the whole of a guessing attack.
        if hmac.compare_digest(str(typed), str(wanted)):
            st.session_state["let_in"] = True
            st.rerun()
        st.error("Not that.")
    st.stop()


guard()


# ----------------------------------------------------------------- loading

@st.cache_data(ttl=20)
def load_rooms_config(path="rooms.yaml"):
    cfg = yaml.safe_load(open(path))
    recorders = cfg["recorders"]
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
        rows.append({
            "room": room["name"],
            "recorder": recorder,
            "campus": recorders[recorder].get("campus", "unknown"),
            "zone": room.get("zone", "Other"),
            # Whose space it is. Empty when nobody has said; a blank rather
            # than None so that "dept or something" reads the same on every
            # row, and never NaN, which is true.
            "dept": room.get("dept") or "",
            "cameras": len(cameras),
            "ac": room["ac"],
            "ac_count": (0 if not has_unit
                         else int(room.get("ac_count", 1) or 1)),
            "meter": room.get("meter"),
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
        # Only changes are written, so "no event" means "no change", not
        # "nobody looked". A room empty since Friday has no row inside a
        # twenty-five hour window at all, and the day strip drew its whole
        # night as unwatched -- which is the opposite of the truth, and
        # precisely the hours this system exists to watch. So each room also
        # brings the last event before the window: the state it was in when
        # the window opened. One extra row per room, and the night reads as
        # the empty building it was.
        recent = pd.read_sql_query(
            "(SELECT timestamp, room, status, people, ac_state"
            "   FROM room_events"
            "  WHERE timestamp >= now() - interval '%d hours')"
            " UNION ALL "
            "(SELECT DISTINCT ON (room) timestamp, room, status, people,"
            "        ac_state"
            "   FROM room_events"
            "  WHERE timestamp < now() - interval '%d hours'"
            "  ORDER BY room, timestamp DESC)"
            " ORDER BY room, timestamp"
            % (DETAIL_HOURS + 1, DETAIL_HOURS + 1), conn)
        beat = pd.read_sql_query(
            "SELECT max(timestamp) AS last_beat FROM heartbeat", conn)
        # Every beat in the window, not only the last one. The last beat
        # says whether the loop is alive now; these say which quarter hours
        # it was alive for, which is what separates "the building was empty"
        # from "nobody was looking". Timestamps only -- the table holds
        # nothing else.
        beats = pd.read_sql_query(
            "SELECT timestamp FROM heartbeat"
            " WHERE timestamp >= now() - interval '%d hours'"
            " ORDER BY timestamp" % (DETAIL_HOURS + 1), conn)
    finally:
        conn.close()
    for column in ("empty_since", "timestamp"):
        latest[column] = pd.to_datetime(latest[column], utc=True)
    recent["timestamp"] = pd.to_datetime(recent["timestamp"], utc=True)
    beats["timestamp"] = pd.to_datetime(beats["timestamp"], utc=True)
    return (latest, recent, pd.to_datetime(beat["last_beat"].iloc[0], utc=True),
            beats["timestamp"].tolist())


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
def load_daily_coverage(days=28):
    """Hours watched on each day, from the heartbeat.

    A day with no coverage and a day with nothing wrong look identical on a
    calendar, and only one of them is good news. Counted in distinct
    ten-minute windows so a loop restarting in circles cannot inflate it, and
    in elapsed seconds rather than epoch integers -- pandas 3 hands back
    microseconds where this file has twice assumed nanoseconds.
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
        return {}
    local = to_local(pd.to_datetime(beats["timestamp"], utc=True))
    frame = pd.DataFrame({"day": local.dt.date,
                          "slot": (local.dt.hour * 6 + local.dt.minute // 10)})
    return (frame.drop_duplicates().groupby("day").size() / 6.0).to_dict()


@st.cache_data(ttl=60)
def load_history(days=28):
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        df = pd.read_sql_query(
            "SELECT timestamp, room, status, people, ac_state"
            " FROM room_events"
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
    # "reported -1 min ago". The heartbeat is written by the machine at
    # 140-H and this page may be running somewhere else entirely, so the
    # two clocks are not the same clock and a minute of disagreement is
    # ordinary. A negative age is that disagreement, not a reading from
    # the future, and printing it as one makes the whole badge look broken.
    if minutes <= 0:
        return "under a min"
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
                '<ellipse cx="29" cy="31" rx="36" ry="21" fill="%s"'
                ' opacity=".12"/>'
                '<rect x="0" y="0" width="58" height="17" rx="4" fill="%s"'
                ' stroke="%s" stroke-width="2"/>'
                '<line x1="5" y1="12" x2="53" y2="12" stroke="%s"'
                ' stroke-width="1.6"/>'
                '<circle cx="51" cy="5.5" r="2.1" fill="%s"/>'
                '<path d="M12 25q5 5 10 0t10 0t10 0" fill="none"'
                ' stroke="%s" stroke-width="2" stroke-linecap="round"'
                ' opacity=".8"/>'
                '<path d="M16 33q5 4 10 0t10 0" fill="none" stroke="%s"'
                ' stroke-width="1.8" stroke-linecap="round" opacity=".45"/>'
                '</g>' % (x, y, AC_ON, ROOM_FILL, AC_ON, AC_ON, AC_ON,
                          AC_ON, AC_ON))
    if state == "off":
        return ('<g transform="translate(%d,%d)" opacity=".7">'
                '<rect x="0" y="0" width="58" height="17" rx="4" fill="%s"'
                ' stroke="%s" stroke-width="2"/>'
                '<line x1="5" y1="12" x2="53" y2="12" stroke="%s"'
                ' stroke-width="1.6"/>'
                '<circle cx="51" cy="5.5" r="2.1" fill="none" stroke="%s"'
                ' stroke-width="1.4"/></g>'
                % (x, y, ROOM_FILL, AC_OFF, AC_OFF, AC_OFF))
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
  <rect x="4" y="6" width="252" height="100" rx="11" fill="%s"
        fill-opacity=".6" stroke="%s" stroke-width="1.6"/>
  <line x1="14" y1="%d" x2="246" y2="%d" stroke="%s" stroke-width="2.4"
        stroke-linecap="round"/>
  <path d="M20 %d V34 a13 13 0 0 1 13-13" fill="none" stroke="%s"
        stroke-width="1.8" stroke-linecap="round" opacity=".75"/>
  %s %s %s
</svg>""" % (ROOM_FILL, ink["edge"], floor, floor, ink["edge"], floor,
             ink["edge"],
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
    # And the campus and theme: since the front page came in, a link that
    # carried only the room landed on the welcome page, in the dark theme.
    return ('<a href="%s#roomdetail" target="_self" '
            'style="text-decoration:none;'
            'display:contents;">%s</a>'
            % (overview.link(LINK_BASE, room=room), html))


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
                        PERSON.format(x=i * 14, y=0,
                                      c=INK["Green"]["fg"])
                        for i in range(shown))))
        if people > shown:
            now_cell += ('<span style="font-size:.68rem;color:%s;">+%d'
                         '</span>' % (INK["Green"]["fg"], people - shown))
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
        "on": ("AC ON", SURFACE, AC_ON, AC_ON, "solid"),
        "off": ("AC OFF", SURFACE, AC_OFF, AC_OFF, "solid"),
    }.get(state, ("AC ?", SURFACE, FAINT, MUTED, "dashed"))
    label, ink, border, text, style = look
    fill = AC_ON if state == "on" else SURFACE
    return ('<span style="font-size:.6rem;font-weight:800;letter-spacing:.04em;'
            'padding:2px 6px;border-radius:9px;border:1.3px %s %s;'
            'background:%s;color:%s;white-space:nowrap;">%s</span>'
            % (style, border, fill,
               THEMES["dark"]["band_text"] if state == "on" else text, label))


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
</div>""" % (ink["bg"],
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


def head_count_parts(df, beat_age):
    """How many people the cameras can see in the campus, right now.

    This was already on the campus page and nowhere else, under a label that
    said "the cameras can see inside" -- true, but it never says the word
    people, so sitting between two rupee figures it read as a third money
    number and the one figure everybody actually wants was invisible. It now
    says what it is, in words, and it says it on every view.

    Three honesty rules, because a headcount is the easiest number on this
    page to believe without thinking:

      * A room nobody looked at contributes nobody. So the count is a floor,
        not a total, and when any indoor room failed to answer it says so and
        calls itself "at least".
      * Outside is not inside. The gate and the car park are counted, but
        separately -- a guard at the gate is not somebody leaving an air
        conditioner running in a room.
      * If the loop has gone quiet the figure is the last thing it saw, not
        the present, and saying "right now" over a stale number would be a
        lie the page tells on its own.
    """
    import campus_view

    # Two headcounts: the office, which is everything indoors, and the
    # perimeter. The street, the car parks and the smoking area used to be
    # added into the one figure, which read 35 at night with a dozen people
    # actually inside.
    where = [campus_view.place(r, z) for r, z in zip(df["room"], df["zone"])]
    df = df.assign(_place=where)
    busy = df[df["status"] == "occupied"]
    office = int(busy[busy["_place"] == "office"]["people"].fillna(0).sum())
    outside = int(busy[busy["_place"] == "outside"]["people"].fillna(0).sum())
    rooms_busy = int((busy["_place"] == "office").sum())
    indoors = df[df["_place"] == "office"]
    quiet = int((indoors["status"].isna()
                 | (indoors["status"] == "unknown")).sum())

    live = (beat_age is not None and beat_age <= STALE_AFTER_MINUTES)
    label = "IN OFFICE RIGHT NOW" if live else "IN OFFICE WHEN LAST SEEN"
    value = ("at least %d" % office) if quiet else str(office)

    bits = ["%d room%s busy" % (rooms_busy, "" if rooms_busy == 1 else "s"),
            "%d outside, not counted" % outside]
    if quiet:
        bits.append("%d room%s did not answer"
                    % (quiet, "" if quiet == 1 else "s"))
    return label, value, " \u00b7 ".join(bits)


def head_count(df, beat_age):
    """The same figure as a tile for the band at the top of the other views."""
    label, value, note = head_count_parts(df, beat_age)
    note = note.replace("\u00b7", "&#183;")

    return """
<div style="text-align:right;">
  <div style="color:#6E7B82;font-size:.56rem;letter-spacing:.14em;">
    %s</div>
  <div style="color:#8FC7F0;font-size:1.34rem;font-weight:760;
              line-height:1.15;">%s <span style="font-size:.78rem;
              font-weight:600;color:#6E7B82;">people</span></div>
  <div style="color:#5E6A70;font-size:.58rem;">%s</div>
</div>
<div style="width:1px;background:#2A3034;"></div>""" % (label, value, note)


def money_strip(at_stake, saved, span, enough, people_html="",
                stake_note="upper bound, not a bill"):
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
<div style="display:flex;gap:18px;align-items:flex-start;">
  %s
  <div style="text-align:right;">
    <div style="color:#6E7B82;font-size:.56rem;letter-spacing:.14em;">
      AT STAKE TODAY</div>
    <div style="color:#F0C98B;font-size:1.34rem;font-weight:760;
                line-height:1.15;">Rs %s</div>
    <div style="color:#5E6A70;font-size:.58rem;">%s</div>
  </div>
  <div style="width:1px;background:#2A3034;"></div>
  <div style="text-align:right;">
    <div style="color:#6E7B82;font-size:.56rem;letter-spacing:.14em;">
      SAVED SO FAR</div>
    <div style="color:%s;font-size:1.34rem;font-weight:760;line-height:1.15;">
      %s</div>
    <div style="color:#5E6A70;font-size:.58rem;">%s</div>
  </div>
</div>""" % (people_html, format(round(at_stake), ","), stake_note,
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
<div style="background:%s;border:1px solid %s;border-radius:14px;
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
</div>""" % (BAND, BAND_LINE, campus, money_html, pill,
             building_bar(df), len(df),
             int(df["cameras"].sum()),
             (" &middot; %s" % mode) if mode else "")


def figure_row(label, value, note, tone=None):
    """A number with its label under it, not over it.

    Reworked after looking at a dashboard that reads well: the number is the
    thing, so it gets the size and the top line, the label gets out of the way
    underneath, and the card gets room to breathe instead of a hard border.
    Borders everywhere make a page look like a spreadsheet; a faint surface
    and space between does the same job quietly.
    """
    return """
<div style="flex:1 1 184px;background:%s;border:1px solid %s;
            border-radius:14px;padding:16px 18px 14px;">
  <div style="font-size:1.92rem;font-weight:720;color:%s;line-height:1.1;
              letter-spacing:-.02em;">%s</div>
  <div style="font-size:.72rem;color:%s;letter-spacing:.04em;margin-top:5px;">
    %s</div>
  <div style="font-size:.67rem;color:%s;margin-top:2px;">%s</div>
</div>""" % (SURFACE, LINE, tone or TEXT, value, MUTED, label, FAINT, note)


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
        % (hour, NO_DATA if value is None else
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
                       color_discrete_sequence=[AC_ON])
        chart.update_layout(height=215, margin=dict(l=0, r=0, t=16, b=0),
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(color=MUTED), showlegend=False,
                            yaxis=dict(gridcolor=LINE))
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


def wordmark(mode):
    """The company mark, taken from the letterhead.

    Drawn inline rather than through st.image: it is vector, and inlining
    keeps it crisp at any size and lets the dark and light cuts be swapped
    with the theme. Two files because the mark is solid black on the
    letterhead, which disappears on a dark page -- same paths, different fill.

    If the files are missing the name is set in type instead. That is a
    deliberate fallback rather than a guess at artwork: it is obviously
    standing in.
    """
    path = os.path.join("assets", "logo-%s.svg"
                        % ("dark" if mode == "dark" else "light"))
    if os.path.exists(path):
        svg = open(path).read()
        return svg.replace("<svg", "<svg style=\"height:26px;width:auto;"
                                   "display:block;\"", 1)
    return ('<span style="font-size:1.06rem;font-weight:650;color:%s;'
            'letter-spacing:-.02em;">Disrupt<span style="opacity:.55;">.com'
            '</span></span>' % (TEXT or "#E6EAED"))


@st.cache_data(ttl=120)
def load_meters(days=120):
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE,
                            connect_timeout=10)
    try:
        import meters_view
        return meters_view.load(conn, days)
    finally:
        conn.close()


def write_reading(meter, taken, reading, units, temp, note):
    """One reading, from the page rather than from a command line."""
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE,
                            connect_timeout=10)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO meter_readings (meter, taken, reading, units,"
            " max_temp, note) VALUES (%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT (meter, taken) DO UPDATE SET reading ="
            " EXCLUDED.reading, units = EXCLUDED.units,"
            " max_temp = EXCLUDED.max_temp, note = EXCLUDED.note",
            (meter, taken, reading, units, temp, note))
        conn.commit()
        cur.close()
    finally:
        conn.close()


def write_solar(taken, kwh, note):
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE,
                            connect_timeout=10)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO solar_daily (taken, kwh, note) VALUES (%s,%s,%s)"
            " ON CONFLICT (taken) DO UPDATE SET kwh = EXCLUDED.kwh,"
            " note = EXCLUDED.note", (taken, kwh, note))
        conn.commit()
        cur.close()
    finally:
        conn.close()


def reading_form(now, meters, readings, solar):
    """Three numbers, once a day, by whoever is in the building.

    Each box says what to type and shows the last number typed into it, so
    a slip of a digit is caught by the person typing rather than by a chart
    a week later.
    """
    last = {}
    for code in meters["code"]:
        mine = readings[readings["meter"] == code].sort_values("taken")
        if len(mine):
            row = mine.iloc[-1]
            last[code] = "last: %s, %s" % (
                format(int(float(row["reading"])), ",")
                if pd.notna(row["reading"]) else "\u2014",
                row["taken"].tz_convert(PKT).strftime("%d %b %H:%M"))
    if len(solar):
        row = solar.sort_values("taken").iloc[-1]
        last["solar"] = "last: %s, %s" % (
            format(int(float(row["kwh"])), ","),
            pd.Timestamp(row["taken"]).tz_convert(PKT).strftime(
                "%d %b %H:%M"))
    st.markdown(
        '<div style="font-size:1.05rem;font-weight:700;margin:6px 0 2px;">'
        'Today\u2019s readings</div>'
        '<div style="font-size:.8rem;color:%s;margin-bottom:10px;">'
        'Once a day, at about the same hour. Anybody can fill this in.</div>'
        % MUTED, unsafe_allow_html=True)
    labels = {"gf_basement": "Ground floor + basement meter (TY75237)",
              "first_cafe": "First floor + cafe meter (TU09825)"}
    with st.form("readings"):
        cols = st.columns(len(meters) + 2)
        typed = {}
        for i, code in enumerate(meters["code"]):
            typed[code] = cols[i].number_input(
                labels.get(code, code), min_value=0.0, step=1.0,
                format="%.0f", key="reading_" + code,
                help="The number on the face of the meter, all of it.")
            cols[i].caption(last.get(code, "no reading yet"))
        solar_kwh = cols[-2].number_input(
            "Solar made yesterday, kWh", min_value=0.0, step=1.0,
            format="%.0f", key="solar_units",
            help="The inverter's figure for yesterday -- a full day. Not"
                 " today's so far, and not its lifetime total.")
        cols[-2].caption(last.get("solar", "no solar figure yet"))
        temp = cols[-1].number_input("Today\u2019s high, \u00b0C",
                                     min_value=0.0, max_value=60.0, step=1.0,
                                     format="%.0f", key="max_temp")
        note = st.text_input("Anything worth noting (optional)", key="r_note")
        sent = st.form_submit_button("Save today\u2019s readings")
    if not sent:
        return
    taken = now.tz_convert(PKT)
    wrote = []
    try:
        for code, value in typed.items():
            if value:
                write_reading(code, taken, value, None, temp or None,
                              note or None)
                wrote.append(labels.get(code, code))
        if solar_kwh:
            write_solar(taken, solar_kwh, note or None)
            wrote.append("solar")
    except psycopg2.Error as e:
        if getattr(e, "pgcode", None) == "42501":
            st.error("This page is connected read-only. An administrator runs"
                     " `sql/08_readings_from_the_page.sql` once to let it"
                     " write meter readings \u2014 and nothing else.")
        else:
            st.error("Could not save (%s)." % type(e).__name__)
        return
    if wrote:
        load_meters.clear()
        load_solar.clear()
        st.success("Saved: %s." % ", ".join(wrote))
    else:
        st.info("Nothing entered, so nothing was saved.")


def show_analysis(df, recent, now):
    """Where the empty, cooled hours are, and what they would cost.

    The three sources are not equal and the page says so. The bills are
    settled; the meter readings are ours and measured; what the cameras give
    becomes money only through an assumption that has not been replaced
    yet. This page is the third, kept honest, and ends with the rooms to
    fix first -- which is what it is for.
    """
    import analysis_view as av
    import energy_view as ev

    assumptions = load_assumptions()
    window = av.peak_window(assumptions)
    try:
        meters, readings, bills = load_meters()
    except psycopg2.Error:
        meters = bills = pd.DataFrame()
    try:
        history = load_history()
    except psycopg2.Error:
        history = recent
    # Seven days of events, not the last day's: this said "last 7 days"
    # over twenty-five hours of history.
    since = now - pd.Timedelta(days=7)
    rows = ev.top_rooms(history, df, since, now, window, assumptions)
    peak_h = sum(r["peak_hours"] for r in rows)
    off_h = sum(r["hours"] for r in rows) - peak_h
    rupees = sum(r["rupees"] for r in rows)
    cooled = df[df["has_unit"] & df["alerts"]]
    known = int(cooled["ac_state"].notna().sum()) if len(cooled) else 0
    bill_rate, months = (av.tariff_from_bills(bills, True, meters)
                         if len(bills) and len(meters) else (None, 0))
    rates = (float(assumptions.get("tariff_rs_per_kwh", 67)),
             float(assumptions.get("peak_rs_per_kwh", 81)),
             "%s\u2013%s" % (assumptions.get("peak_start", "?"),
                             assumptions.get("peak_end", "?")))
    st.markdown(ev.analysis_page(
        LINK_BASE.get("theme") or "dark", rows, off_h, peak_h, rupees,
        float(assumptions.get("unit_kw", 1.2)), known, len(cooled), rates,
        bill_rate, months), unsafe_allow_html=True)

    if "gf_basement" in set(df.get("meter", pd.Series(dtype=object))
                            .dropna()):
        st.warning(
            "October's ground-floor bill charged fixed charges on a **maximum"
            " demand of 38 kW** against a **sanctioned 19**: Rs 47,500 where"
            " 19 kW would cost Rs 23,750. **Rs 285,000 a year.**\n\nA"
            " different lever from everything above: not fewer units, but"
            " fewer things drawing at the same instant. Starting the units"
            " floor by floor instead of all at ten would cut it with nothing"
            " used less.", icon="\u26a1")


def show_meters(df, recent, now):
    """The readings, day by day, and the bills, month by month.

    The form is at the top because it is the daily job. Under it, what the
    building used each day and where it came from -- the grid on each meter
    and the panels -- then the hours rooms on those meters sat empty with a
    unit, over the same days, then the bills. Only this campus's meters.
    """
    import analysis_view as av
    import energy_view as ev

    try:
        meters, readings, bills = load_meters()
    except psycopg2.Error:
        st.info("The meter tables are not there yet. An administrator runs"
                " `sql/06_meters.sql` and `sql/07_bills_and_solar.sql` once"
                " in the Supabase SQL editor.")
        return
    solar = load_solar()
    codes = set(df["meter"].dropna()) if "meter" in df.columns else set()
    mine = meters[meters["code"].isin(codes)] if len(meters) else meters
    mode = LINK_BASE.get("theme") or "dark"
    if not len(mine):
        st.markdown(ev.meters_page(mode, None, "daily", mine, bills, None, 0,
                                   [], False, LINK_BASE.get("campus") or ""),
                    unsafe_allow_html=True)
        return

    reading_form(now, mine, readings, solar)
    readings = readings[readings["meter"].isin(codes)]
    table, kind = ev.daily_table(readings, mine, solar)
    cooled_hours = None
    if len(table):
        assumptions = load_assumptions()
        try:
            history = load_history()
        except psycopg2.Error:
            history = recent
        on_meters = list(df[df["has_unit"] & df["alerts"]
                            & df["meter"].isin(codes)]["room"])
        windows = [(pd.Timestamp(d), min(pd.Timestamp(d) + pd.Timedelta(days=1),
                                         now)) for d in table["day"]]
        cooled_hours = ev.cooled_in_windows(history, on_meters, windows,
                                            av.peak_window(assumptions))
    rate = float(load_assumptions().get("tariff_rs_per_kwh", 67))
    st.markdown(ev.meters_page(
        mode, table, kind, mine, bills[bills["meter"].isin(codes)]
        if len(bills) else bills, cooled_hours, rate,
        ev.suspicious(readings, mine), True, LINK_BASE.get("campus") or ""),
        unsafe_allow_html=True)
    with st.expander("Every reading, as entered"):
        if len(readings):
            shown = readings.copy()
            shown["taken"] = shown["taken"].dt.tz_convert(PKT).dt.strftime(
                "%d %b %H:%M")
            st.dataframe(shown, hide_index=True)
        if len(solar):
            sun = solar.copy()
            sun["taken"] = pd.to_datetime(sun["taken"], utc=True) \
                .dt.tz_convert(PKT).dt.strftime("%d %b %H:%M")
            st.dataframe(sun, hide_index=True)


@st.cache_data(ttl=120)
def load_solar(days=120):
    """What the panels made, as typed into the form; empty if no table."""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE,
                                connect_timeout=10)
    except psycopg2.Error:
        return pd.DataFrame(columns=["taken", "kwh", "note"])
    try:
        return pd.read_sql_query(
            "SELECT taken, kwh, note FROM solar_daily"
            " WHERE taken >= now() - interval '%d days' ORDER BY taken"
            % days, conn)
    except Exception:                                       # noqa: BLE001
        return pd.DataFrame(columns=["taken", "kwh", "note"])
    finally:
        conn.close()


@st.cache_data(ttl=30)
def load_beats_since(hours):
    """Every heartbeat in the last so many hours.

    The front pages need yesterday evening as well as today -- when the last
    person left -- and the beats load_state brings cover twenty-five hours,
    which at eleven at night no longer reaches back to yesterday's ten.
    """
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        beats = pd.read_sql_query(
            "SELECT timestamp FROM heartbeat"
            " WHERE timestamp >= now() - interval '%d hours'"
            " ORDER BY timestamp" % int(hours), conn)
    finally:
        conn.close()
    return pd.to_datetime(beats["timestamp"], utc=True).tolist()


def stretch(widget, *args, **kwargs):
    """A widget as wide as its column, on old Streamlit and new alike.

    use_container_width is on its way out and width="stretch" is how newer
    versions say it; the laptop and the cloud do not run the same version,
    and a TypeError on either takes the whole page down.
    """
    try:
        return widget(*args, width="stretch", **kwargs)
    except TypeError:
        return widget(*args, use_container_width=True, **kwargs)


def app_chrome(mode):
    """Streamlit's own surfaces, set to the page's palette.

    config.toml sets them once at start-up and cannot follow a theme switch,
    so they are set here on every run. The sidebar is gone -- the views are
    a row along the top now -- and the page is held to a readable width.
    """
    t = THEMES[mode]
    return (
        "<style>"
        ".stApp { background: %(page)s; color: %(text)s;"
        " font-family: system-ui,-apple-system,'Segoe UI',Roboto,sans-serif; }"
        "header[data-testid='stHeader'], div[data-testid='stToolbar'],"
        " div[data-testid='stDecoration'] { background: transparent !important; }"
        "section[data-testid='stSidebar'],"
        " div[data-testid='stSidebarCollapsedControl'],"
        " div[data-testid='collapsedControl'] { display: none !important; }"
        "div[data-testid='stMainBlockContainer'], .block-container"
        " { max-width: 1260px; padding-top: 1.1rem; padding-bottom: 3rem; }"
        # Every text colour Streamlit sets, set to the palette's -- except
        # inside the front pages (.ec), which carry their own greys and lose
        # them to a rule this broad.
        ":where(.stApp) :is(div, p, span, label, li, h1, h2, h3)"
        ":not(.ec, .ec *) { color: %(text)s; }"
        ".stApp [data-testid='stCaptionContainer'],"
        " .stApp [data-testid='stCaptionContainer'] * { color: %(muted)s; }"
        "div[data-testid='stMetricValue'] { color: %(text)s; }"
        "div[data-testid='stMetricLabel'], div[data-testid='stMetricLabel'] *"
        " { color: %(muted)s; }"
        "hr { border-color: %(line)s; }"
        # Streamlit's own bar -- deploy button and menu -- is for whoever
        # runs the server, not for the people reading the page.
        "header[data-testid='stHeader'] { display: none !important; }"
        # The view switch: a row of pills in one tray, the chosen one lifted,
        # like the nav on the drawn option.
        " div[data-testid='stButtonGroup'] [role='radiogroup']"
        " { background: %(surface)s; border: 1px solid %(line)s;"
        " border-radius: 12px; padding: 4px; gap: 2px; flex-wrap: wrap; }"
        " div[data-testid='stButtonGroup'] button { border: none !important;"
        " background: transparent !important; box-shadow: none !important;"
        " border-radius: 9px !important; min-height: 34px; }"
        " div[data-testid='stButtonGroup'] button p { color: %(muted)s"
        " !important; font-weight: 550; font-size: 13.5px; }"
        " div[data-testid='stButtonGroup'] button:hover p"
        " { color: %(text)s !important; }"
        " div[data-testid='stButtonGroup'] button[aria-checked='true']"
        " { background: %(sunken)s !important; }"
        " div[data-testid='stButtonGroup'] button[aria-checked='true'] p"
        " { color: %(text)s !important; }"
        " div[data-testid='stPopover'] button { background: %(surface)s"
        " !important; border: 1px solid %(line)s !important;"
        " border-radius: 12px !important; min-height: 44px; }"
        " div[data-baseweb='input'], div[data-baseweb='select'] > div,"
        " div[data-baseweb='base-input'] { background: %(surface)s; }"
        "</style>" % t)


def load_beats(start, end):
    """Every heartbeat in a window: when the loop was running."""
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE, connect_timeout=10)
    try:
        beats = pd.read_sql_query(
            "SELECT timestamp FROM heartbeat WHERE timestamp >= %s"
            " AND timestamp < %s ORDER BY timestamp", conn,
            params=(start.to_pydatetime(), end.to_pydatetime()))
    finally:
        conn.close()
    return list(pd.to_datetime(beats["timestamp"], utc=True))


def show_arrivals(df, now):
    """Each room's day, in the order it happened -- one day, or many averaged.

    Controls: a range of days (one day shows that day in full; several
    show each room's usual day, averaged), whether to include the street
    and car parks, and a time window -- the peak tariff by default, since
    that is where the money is, or any stretch of the day. The arithmetic
    is in day_story.py, where it is tested; this only lays it out.
    """
    import analysis_view as av
    import campus_view
    import day_story as ds

    local_now = now.tz_convert(PKT)
    today = local_now.date()
    try:
        month = load_history()
    except psycopg2.Error as e:
        st.error("Could not load history (%s)." % type(e).__name__)
        return
    if month.empty:
        st.info("No history yet.")
        return
    first_day = min(t.date() for t in to_local(month["timestamp"]))

    assumptions = load_assumptions()
    pk_a, pk_b = av.peak_window(assumptions)

    c1, c2, c3, c4 = st.columns([1.6, 1.5, 1.0, 1.0])
    picked = c1.date_input("Days", value=(today, today),
                           min_value=first_day, max_value=today)
    if isinstance(picked, (list, tuple)):
        d_from, d_to = (picked[0], picked[-1]) if picked else (today, today)
    else:
        d_from = d_to = picked
    presets = {
        "Peak tariff, 6:30–10:30 evening": (pk_a, pk_b),
        "Working day, 10 morning–8 evening": (10.0, 20.0),
        "Morning arrivals, 6–11 morning": (6.0, 11.0),
        "Night, 9 night–6 morning (to midnight)": (21.0, 24.0),
        "Whole day": (0.0, 24.0),
        "Custom": None,
    }
    choice = c2.selectbox("Time window", list(presets))
    if presets[choice] is None:
        t_a = c3.time_input("From", value=pd.Timestamp("18:30").time())
        t_b = c4.time_input("To", value=pd.Timestamp("22:30").time())
        w_a = t_a.hour + t_a.minute / 60.0
        w_b = t_b.hour + t_b.minute / 60.0 or 24.0
        if w_b <= w_a:
            st.warning("The window has to end after it starts, within one"
                       " day. For a night across midnight, use two windows.")
            return
    else:
        w_a, w_b = presets[choice]
        with_outside = c3.checkbox("Include outside", value=False,
                                   help="The street, the car parks, the"
                                        " smoking area and the plant.")
    if presets[choice] is None:
        with_outside = False

    # A department is several rooms read as one: Squat Wolf is five rooms,
    # and the question about it is when the department started and finished,
    # not when Room 3 did. Offered first wherever departments have been
    # written down; a campus with none opens on rooms as before.
    named = bool((df["dept"].astype(str) != "").any()) if "dept" in df else False
    by_dept = st.radio(
        "Show", ["By department", "By room"], index=0 if named else 1,
        horizontal=True, key="arrivals_group",
        label_visibility="collapsed") == "By department"
    noun = "Department" if by_dept else "Room"

    day_starts = [pd.Timestamp(d).tz_localize(PKT)
                  for d in pd.date_range(d_from, d_to, freq="D")]
    try:
        beats = load_beats(day_starts[0] - pd.Timedelta(days=1, minutes=15),
                           min(day_starts[-1] + pd.Timedelta(days=1),
                               local_now) + pd.Timedelta(minutes=15))
    except psycopg2.Error:
        beats = None

    # The time window is only worth reading on days it has happened. At
    # eleven in the morning today's peak tariff is seven hours away, and the
    # first version showed an empty table at the top of the page for it.
    win_days = [d for d in day_starts
                if d + pd.Timedelta(hours=w_a) < local_now]
    win_note = ""
    if not win_days:
        win_days = [day_starts[0] - pd.Timedelta(days=1)]
        win_note = "today's has not started yet, so this is yesterday's"
    # Split once. Filtering the month for every room on every day, twice
    # over now that departments are worked out beside rooms, was thousands
    # of passes over the same table for a four-week range.
    by_room = {name: rows for name, rows in month.groupby("room")}
    none_yet = month.iloc[0:0]

    def day_for(names, start, end):
        # One room's day, or a department's: its rooms' days laid together.
        return ds.combine([ds.spells(by_room.get(n, none_yet), start, end,
                                     beats) for n in names])

    def entity_rows(entities):
        out = []
        for room in entities:
            stories, windows, last = [], [], None
            for start in day_starts:
                end = min(start + pd.Timedelta(days=1), local_now)
                if end <= start:
                    continue
                day = day_for(room["members"], start, end)
                story = ds.story(day, start)
                story["brief"] = len(ds.kinds(ds.visits(day))[0])
                # Still busy when the day ended -- at midnight, or now for
                # today -- is not a departure. The first cut only checked
                # today, and a room busy round the clock averaged a "last
                # out" of midnight.
                story["left"] = not (
                    story["last_out"] is not None
                    and story["last_out"] >= end - pd.Timedelta(minutes=1))
                stories.append(story)
                last = (start, end, day, story)
            for start in win_days:
                end = min(start + pd.Timedelta(days=1), local_now)
                windows.append(ds.window(day_for(room["members"], start, end),
                                         start, w_a, w_b))
            if stories:
                out.append((room, stories, windows, last))
        return out

    singles = []
    for _, room in df.iterrows():
        if campus_view.place(room["room"], room.get("zone")) == "outside" \
                and not with_outside:
            continue
        singles.append(dict(room, members=[room["room"]],
                            work=room.get("zone") in overview.WORK_ZONES))
    room_rows = entity_rows(singles)

    if by_dept:
        # A working room nobody has given a department to is its own
        # department, under its own name (Marketing, HR Room); a lobby or a
        # cafe is grouped by its zone. Nothing is filed under a department
        # somebody would have had to guess.
        groups = {}
        for room in singles:
            # The same rule as the overview's department cards, so a
            # department is the same set of rooms on both pages.
            name = overview.department_of(room["room"], room.get("zone"),
                                          room.get("dept")) or room.get("zone")
            groups.setdefault(name or "Other", []).append(room)
        depts = []
        for name, members in sorted(groups.items()):
            units = sum(int(m.get("ac_count") or 0) for m in members
                        if m.get("has_unit"))
            depts.append({
                "room": name if len(members) == 1 else
                "%s \u00b7 %d rooms" % (name, len(members)),
                "members": [m["room"] for m in members],
                "has_unit": bool(units), "ac_count": units,
                "alerts": any(m.get("alerts", True) for m in members),
                "work": any(m["work"] for m in members),
            })
        rows = entity_rows(depts)
    else:
        rows = room_rows

    single = len(day_starts) == 1
    span_text = (("Today" if d_from == today else d_from.strftime("%a %d %b"))
                 if single else "%s – %s, %d days, averaged"
                 % (d_from.strftime("%d %b"), d_to.strftime("%d %b"),
                    len(day_starts)))

    cell = ('padding:5px 8px;border-bottom:1px solid %s;font-size:.76rem;'
            'white-space:nowrap;' % LINE)

    def table(head, body, aligns=None):
        aligns = aligns or ["left"] * len(head)
        html = ('<div style="overflow-x:auto;"><table style="border-collapse:'
                'collapse;width:100%%;"><tr>%s</tr>'
                % "".join('<th style="%stext-align:%s;color:%s;font-weight:600;'
                          'font-size:.7rem;">%s</th>' % (cell, al, MUTED, h)
                          for h, al in zip(head, aligns)))
        for r in body:
            html += "<tr>%s</tr>" % "".join(
                '<td style="%stext-align:%s;">%s</td>' % (cell, al, v)
                for v, al in zip(r, aligns))
        return html + "</table></div>"

    dash = '<span style="color:%s">—</span>' % FAINT

    def muted(text):
        return '<span style="color:%s">%s</span>' % (MUTED, text)

    later = []
    # ---- the time window: what happened inside it, per room -------------
    rate_frac = max(0.0, min(w_b, pk_b) - max(w_a, pk_a)) / max(1e-9, w_b - w_a)
    rate = (assumptions.get("peak_rs_per_kwh", 81) * rate_frac
            + assumptions.get("tariff_rs_per_kwh", 67) * (1 - rate_frac))
    kw = assumptions.get("unit_kw", 1.2)
    # Money is worked out room by room whichever way the page is grouped:
    # a department with one room busy is "busy", but the empty room next
    # door is still cooling nobody, and that is the money.
    win_rows, at_stake, empty_units_h, room_money = [], 0.0, 0.0, {}
    for room, stories, windows, last in room_rows:
        a = ds.average_days(stories, windows)["window"]
        if a["busy_pct"] is None:
            continue
        units = int(room.get("ac_count") or 0) if room.get("has_unit") else 0
        money = (a["empty_min"] / 60.0 * kw * units * rate
                 if units and room.get("alerts", True) else None)
        if money:
            at_stake += money
            empty_units_h += a["empty_min"] / 60.0 * units
            room_money[room["room"]] = money
    for room, stories, windows, last in rows:
        a = ds.average_days(stories, windows)["window"]
        if a["busy_pct"] is None:
            continue
        units = int(room.get("ac_count") or 0) if room.get("has_unit") else 0
        money = sum(room_money.get(m, 0.0) for m in room["members"])
        win_rows.append((money or 0, a["busy_pct"], [
            room["room"],
            "<b>%d%%</b>" % round(a["busy_pct"]),
            "%.1f" % a["avg"] if a["avg"] else muted("0"),
            str(a["most"]) if a["most"] else muted("0"),
            ds.spell(a["empty_min"]) if a["empty_min"] else muted("0"),
            ("%.1f" % a["brief"] if not single else "%d" % a["brief"])
            if a["brief"] else muted("0"),
            ds.clock_minutes(a["left_at"]) if a["left_at"] is not None
            else dash,
            ("Rs %s" % format(int(round(money)), ",")) if money else
            (muted("no unit") if not units else dash),
        ]))
    win_rows.sort(key=lambda r: (-r[0], -r[1]))
    label = ("%s – %s" % (ds.clock_minutes(w_a * 60),
                               ds.clock_minutes(w_b * 60 - 1)
                               if w_b >= 24 else ds.clock_minutes(w_b * 60)))
    later.append(lambda: st.markdown(
        '<div style="font-size:1.1rem;font-weight:720;margin:6px 0 2px;">'
        '%s</div><div style="font-size:.74rem;color:%s;margin-bottom:8px;">'
        '%s · %s. Busy is the share of the window somebody was there;'
        ' <b>empty</b> is per day; <b>Rs at stake</b> is that empty time'
        ' multiplied by each room\'s units at %.1f kW and Rs %.0f a unit'
        '%s -- an upper bound, because for most rooms nobody can see'
        ' whether the unit was actually running.%s</div>'
        % (choice if presets[choice] else "Custom window", MUTED, label,
           win_note or span_text, kw, rate,
           " (the peak rate)" if rate_frac >= 0.999 else
           " (blended with the peak rate)" if rate_frac > 0 else "",
           " A department is busy while any of its rooms is, with its"
           " people added up across them; its Rs is still added up room by"
           " room, so an empty room beside a busy one still counts."
           if by_dept else ""),
        unsafe_allow_html=True))
    if at_stake:
        later.append(lambda: st.markdown(
            '<div style="font-size:.85rem;margin-bottom:8px;">Rooms with a'
            ' unit sat empty for <b>%.1f unit-hours</b> a day in this window'
            ' — up to <b>Rs %s a day</b>, Rs %s over 30 days.</div>'
            % (empty_units_h, format(int(round(at_stake)), ","),
               format(int(round(at_stake * 30)), ",")),
            unsafe_allow_html=True))
    later.append(lambda: st.markdown(table(
        [noun, "Busy", "Avg people", "Most", "Empty", "Brief visits",
         "Last left", "Rs at stake"],
        [r[2] for r in win_rows],
        ["left", "right", "right", "right", "right", "right", "left",
         "right"]), unsafe_allow_html=True))

    # ---- who comes when ----------------------------------------------------
    st.markdown(
        '<div style="font-size:1.1rem;font-weight:720;margin:22px 0 2px;">'
        'Who comes when</div><div style="font-size:.74rem;color:%s;'
        'margin-bottom:8px;">%s, earliest start first. An <b>early visit</b>'
        ' is a short first spell followed by at least half an hour empty --'
        ' usually housekeeping -- and the day starts after it. <b>Brief'
        ' visits</b> are fifteen minutes or less, one or two people: an'
        ' office boy, the cleaner, a guard.</div>' % (MUTED, span_text),
        unsafe_allow_html=True)

    if not single:
        body = []
        for room, stories, windows, last in rows:
            a = ds.average_days(stories)
            if not a["days_used"]:
                continue
            body.append((a["starts"] if a["starts"] is not None else 9e9, [
                room["room"],
                "%d of %d" % (a["days_used"], a["days"]),
                ds.clock_minutes(a["first_in"]) if a["first_in"] is not None
                else dash,
                ("%d of %d days" % (a["early_days"], a["days_used"])
                 + muted(", then empty %s" % ds.spell(a["early_empty"])))
                if a["early_days"] else dash,
                "<b>%s</b>" % ds.clock_minutes(a["starts"])
                if a["starts"] is not None else dash,
                "%d %s" % (a["peak"], muted("usually ~%s" %
                                            ds.clock_minutes(a["peak_at"])))
                if a["peak"] else dash,
                "%d%%" % round(a["busy_pct"]) if a["busy_pct"] is not None
                else dash,
                "%.1f" % a["brief"] if a["brief"] else muted("0"),
                ds.clock_minutes(a["last_out"]) if a["last_out"] is not None
                else dash,
            ]))
        body.sort(key=lambda b: b[0])
        st.markdown(table(
            [noun, "Days used", "First in", "Early visit", "Day starts",
             "Peak", "Busy", "Brief / day", "Last out"],
            [b[1] for b in body],
            ["left", "right", "left", "left", "left", "left", "right",
             "right", "left"]), unsafe_allow_html=True)
        for show in later:
            show()
        return

    # One day: four numbers, then the timeline, then the detail for anyone
    # who wants it.
    import day_timeline as dt

    mode = st.session_state.get("theme", "dark")
    mode = mode if mode in ("light", "dark") else "dark"
    # Who opened the place is a question about where people work: the
    # cafe's breakfast and the guard at the gate are not the day starting,
    # and the overview already says so -- the two pages name the same room.
    stayed = [(room, s) for room, _, _, (_, _, _, s) in rows
              if s["starts"] is not None and not s["carried"]
              and room.get("work", True)]
    totals = []
    for i in range(24):
        hour = [ds.hourly(day, st_)[i] for _, _, _, (st_, _, day, _) in rows]
        hour = [h for h in hour if h is not None]
        totals.append(sum(hour) if hour else None)
    busiest = max(range(24), key=lambda i: totals[i] or 0)
    tiles = [
        ("First to arrive",
         ds.clock(min(s["starts"] for _, s in stayed)) if stayed else "\u2014",
         min(stayed, key=lambda r: r[1]["starts"])[0]["room"] if stayed else ""),
        ("The day started",
         ds.clock_minutes(sorted(ds.minute_of_day(s["starts"])
                                 for _, s in stayed)[len(stayed) // 2])
         if stayed else "\u2014", "median across rooms"),
        ("Busiest hour",
         "~%d people" % round(totals[busiest]) if totals[busiest] else "\u2014",
         "around %s" % ds.clock(day_starts[0] + pd.Timedelta(hours=busiest))
         if totals[busiest] else ""),
        ("Empty rooms in the peak tariff",
         ("up to Rs %s" % format(int(round(at_stake)), ",")) if at_stake
         else "\u2014",
         ("%.1f unit-hours%s" % (empty_units_h,
                                 ", yesterday" if win_note else ""))
         if at_stake else "no room with a unit sat empty"),
    ]
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:12px;margin:4px 0 16px;">'
        + "".join(
            '<div style="flex:1 1 180px;padding:12px 14px;border:1px solid %s;'
            'border-radius:10px;background:%s;"><div style="font-size:.7rem;'
            'color:%s;">%s</div><div style="font-size:1.55rem;font-weight:700;'
            'color:%s;line-height:1.2;margin-top:2px;">%s</div>'
            '<div style="font-size:.7rem;color:%s;margin-top:2px;">%s</div>'
            '</div>' % (LINE, SURFACE, MUTED, k, TEXT, v, MUTED, n)
            for k, v, n in tiles) + "</div>", unsafe_allow_html=True)

    ordered = sorted(rows, key=lambda r: (
        r[3][3]["first_in"] is None, r[3][3]["starts"] is None,
        r[3][3]["starts"] or r[3][3]["first_in"] or r[3][0], r[0]["room"]))
    st.markdown(dt.render(
        [(r[0]["room"], r[3][2], r[3][3], r[3][3]["left"]) for r in ordered],
        day_starts[0], local_now, (pk_a, pk_b), mode), unsafe_allow_html=True)

    for show in later:
        show()

    detail = st.expander("Every number for this day, as tables")
    body, strips = [], []
    for room, stories, windows, (start, end, day, s) in rows:
        stretch = (ds.peak_stretch(ds.by_minute(day, start))
                   if s["starts"] is not None else None)
        if s["first_in"] is None:
            first_in = muted("nobody" if s["busy_pct"] is not None
                             else "not watched")
        elif s["carried"]:
            first_in = muted("from last night")
        else:
            first_in = ds.clock(s["first_in"]) + (
                '<br><span style="color:%s;font-size:.7rem">brief visits'
                ' only</span>' % MUTED if s["starts"] is None else "")
        early = ("%s–%s %s" % (ds.clock(s["early"]["from"]),
                                    ds.clock(s["early"]["to"]),
                                    muted("then empty %s" % ds.spell(
                                        s["early"]["empty_after_min"])))
                 if s["early"] else dash)
        if stretch:
            def at_min(m):
                return ds.clock(start + pd.Timedelta(minutes=m))
            out = ("nobody left" if not stretch["breaks"] else
                   "out %d×, %s in all" % (stretch["breaks"],
                                               ds.spell(stretch["away_min"])))
            stretch_html = ('%s → %s<br><span style="color:%s;'
                            'font-size:.7rem">%s · longest stay %s</span>'
                            % (at_min(stretch["from"]), at_min(stretch["to"]),
                               MUTED, out, ds.spell(stretch["longest_stay"])))
        else:
            stretch_html = dash
        hours = ds.hourly(day, start)
        top = max([v for v in hours if v] or [1])
        strip = "".join(
            '<span title="%s: %s" style="display:inline-block;width:4.1%%;'
            'height:12px;margin-right:.07%%;border-radius:1px;background:%s;'
            'opacity:%.2f;"></span>'
            % (ds.clock(start + pd.Timedelta(hours=i)),
               "not watched" if v is None else "%.1f people" % v,
               SUNKEN if v is None or v == 0 else SLOT_INK["occupied"],
               0.35 if v is None else 1.0 if v == 0 else
               0.25 + 0.75 * min(1.0, v / top))
            for i, v in enumerate(hours))
        strip = ('<span style="display:inline-block;min-width:260px;'
                 'width:100%%;">%s</span>' % strip)
        body.append((s["starts"] is None, s["starts"] or start, [
            room["room"], first_in, early,
            muted("from last night") if s["carried"] else
            "<b>%s</b>" % ds.clock(s["starts"]) if s["starts"] else dash,
            "%d %s" % (s["peak"], muted("at %s" % ds.clock(s["peak_at"])))
            if s["peak_at"] is not None else dash,
            stretch_html,
            str(s["brief"]) if s["brief"] else muted("0"),
            "%d%%" % round(s["busy_pct"]) if s["busy_pct"] is not None
            else dash,
            muted("still in") if not s["left"] else
            ds.clock(s["last_out"]) if s["last_out"] else dash,
            strip]))
        strips.append((room["room"], s, ds.parts(day, start)))
    body.sort(key=lambda b: (b[0], b[1]))
    axis = ('<span style="display:inline-block;min-width:260px;width:100%%;">'
            + "".join('<span style="display:inline-block;width:25%%;">%s</span>'
                      % lab for lab in ("12 night", "6 morn", "noon", "6 eve"))
            + "</span>")
    body.append((True, None, [""] * 9 + [
        '<span style="font-size:.64rem;color:%s">%s</span>' % (FAINT, axis)]))
    detail.markdown(table(
        [noun, "First in", "Early visit", "Day starts", "Peak",
         "Busy stretch", "Brief visits", "Busy", "Last out", ""],
        [b[2] for b in body],
        ["left", "left", "left", "left", "left", "left", "center", "right",
         "left", "left"]), unsafe_allow_html=True)

    titles = ["After midnight<br>12–5", "Morning<br>5–12",
              "Afternoon<br>12–5", "Evening<br>5–9",
              "Night<br>9–12"]
    part_rows = []
    for name, s, parts in strips:
        if s["first_in"] is None:
            continue
        cells = [name]
        for part in parts:
            if part["busy_pct"] is None:
                cells.append(muted("not watched"))
            elif not part["busy_pct"] and not part["brief"]:
                cells.append(muted("empty"))
            else:
                bits = ["<b>%d%%</b>" % round(part["busy_pct"])]
                if part["most"]:
                    bits.append("max %d" % part["most"])
                if part["brief"]:
                    bits.append(muted("%d brief" % part["brief"]))
                cells.append(" · ".join(bits))
        part_rows.append(cells)
    detail.markdown(
        '<div style="font-size:1rem;font-weight:700;margin:22px 0 2px;">'
        'Parts of the day</div><div style="font-size:.74rem;color:%s;'
        'margin-bottom:8px;">one person in and out is an office boy or a'
        ' guard; one person sitting there all evening is somebody working'
        ' late.</div>' % MUTED, unsafe_allow_html=True)
    detail.markdown(table([noun] + titles, part_rows),
                    unsafe_allow_html=True)


def split_by_day(start, end):
    """Minutes between two moments, split across the local days they fall in."""
    out = {}
    if end <= start:
        return out
    cursor = start
    while cursor < end:
        local = to_local(pd.Series([cursor])).iloc[0]
        midnight = (local.normalize() + pd.Timedelta(days=1)).tz_convert("UTC")
        step = min(midnight, end)
        out[local.date()] = out.get(local.date(), 0.0) + \
            (step - cursor).total_seconds() / 60.0
        cursor = step
    return out


def day_calendar(month, rooms, now, coverage, days=28):
    """A square per day: how much air-conditioned room sat empty that day.

    Weeks as columns, weekdays as rows, so a habit shows up as a stripe --
    every Saturday dark, or every evening after a particular change. A day
    nothing was watching is drawn differently from a day nothing happened,
    because on a calendar those two look the same and only one is good news.
    """
    per_day = {}
    for room in rooms:
        mine = month[month["room"] == room].sort_values("timestamp")
        if mine.empty:
            continue
        edges = list(mine["timestamp"]) + [now]
        for index, state in enumerate(mine["status"]):
            if state != "empty":
                continue
            for day, minutes in split_by_day(edges[index], edges[index + 1]).items():
                per_day[day] = per_day.get(day, 0.0) + minutes

    today = to_local(pd.Series([now])).iloc[0].date()
    first = today - pd.Timedelta(days=days - 1)
    # Start the grid on the Monday on or before the first day, so the rows
    # line up as weekdays rather than drifting.
    first = first - pd.Timedelta(days=first.weekday())
    weeks = ((today - first).days // 7) + 1
    worst = max(per_day.values()) if per_day else 1.0

    rows = ""
    for weekday in range(7):
        cells = ""
        for week in range(weeks):
            day = first + pd.Timedelta(days=week * 7 + weekday)
            if day > today:
                cells += '<span style="width:15px;height:15px;"></span>'
                continue
            watched = coverage.get(day, 0.0)
            if watched < 1.0:
                fill, title = SUNKEN, "%s - nothing was watching" % day
            else:
                share = min(1.0, (per_day.get(day, 0.0) / worst) if worst else 0)
                fill = ("rgba(192,91,69,%.2f)" % (0.16 + 0.84 * share)
                        if share > 0.02 else SUNKEN)
                title = ("%s - %s of empty cooled room, %s watched"
                         % (day, spell(per_day.get(day, 0.0)),
                            spell(watched * 60)))
            cells += ('<span title="%s" style="width:15px;height:15px;'
                      'border-radius:3px;background:%s;display:inline-block;'
                      '"></span>' % (title, fill))
        rows += ('<div style="display:flex;gap:3px;margin-bottom:3px;'
                 'align-items:center;">'
                 '<span style="flex:0 0 30px;font-size:.6rem;color:%s;">%s'
                 '</span>%s</div>'
                 % (FAINT, ["Mon", "", "Wed", "", "Fri", "", "Sun"][weekday],
                    cells))
    return rows


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

    # ---- a month of days ---------------------------------------------------
    st.divider()
    try:
        coverage = load_daily_coverage()
    except psycopg2.Error:
        coverage = {}
    st.markdown(
        '<div style="font-size:1.1rem;font-weight:720;margin-bottom:2px;">'
        'Day by day</div>'
        '<div style="font-size:.74rem;color:%s;margin-bottom:10px;">'
        'a square per day, darker where more air-conditioned room sat empty.'
        ' Flat grey means nothing was watching that day, which is not the same'
        ' as nothing happening.</div>%s'
        % (MUTED, day_calendar(month, discretionary["room"], now, coverage)),
        unsafe_allow_html=True)

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
                '<div style="background:%s;border:1px solid %s;'
                'border-radius:11px;padding:12px 16px;margin-top:14px;">'
                '<div style="font-weight:680;color:%s;margin-bottom:5px;">'
                'Worth setting a timer for</div>'
                '<ul style="margin:0;padding-left:18px;font-size:.82rem;'
                'color:%s;">%s</ul></div>'
                % (GOOD_BG, GOOD_LINE, GOOD_FG, GOOD_FG, lines),
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
    latest, recent, last_beat, beats = load_state()
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
        st.error("Database unreachable (%s).\n\n%s%s\n\nWhat the database"
                 " said, with its address and the user hidden:\n\n`%s`"
                 % (type(e).__name__, why_unreachable(e),
                    connection_hint(DATABASE_URL),
                    masked_text(e, DATABASE_URL).replace("`", "'")))
    st.stop()

now = pd.Timestamp.now(tz="UTC")
everything = rooms.merge(latest, on="room", how="left")
everything["status"] = everything["status"].fillna("unknown")

# ---- where we are: the address says which campus and which theme ----------
#
# Both live in the query string rather than only in the session, because the
# welcome page and the room chips are links, and a link that dropped the
# theme would turn the page white halfway through somebody's evening.
mode = st.query_params.get("theme", "dark")
mode = mode if mode in THEMES else "dark"
use_theme(mode)
st.markdown(app_chrome(mode), unsafe_allow_html=True)

campuses = sorted(everything["campus"].unique())
campus = st.query_params.get("campus")
if campus not in campuses:
    campus = None
LINK_BASE.clear()
LINK_BASE.update({"campus": campus, "theme": None if mode == "dark" else mode})

hours = load_hours()
assumptions = load_assumptions()
beat_age = minutes_since(last_beat, now)
healthy = beat_age is not None and beat_age <= STALE_AFTER_MINUTES
live_text = (("live · reported %s ago" % spell(beat_age)) if healthy
             else ("silent for %s" % spell(beat_age)) if beat_age is not None
             else "never reported")
when = "%s · %s" % (now.tz_convert(PKT).strftime("%A %d %B"),
                         overview.clock(now))

# Every room graded once, on every campus: the welcome page needs both, and
# grading is the same arithmetic the alerts use, so no page can disagree with
# them about which rooms want a walk.
everything["occupied_since"] = everything["room"].apply(
    lambda r: run_started(recent, r, now))
graded = everything.apply(lambda r: grade(r, now, hours), axis=1)
everything["level"] = [g[0] for g in graded]
everything["headline"] = [g[1] for g in graded]
everything["sub"] = [g[2] for g in graded]
everything["age"] = everything["timestamp"].apply(
    lambda t: "never" if minutes_since(t, now) is None
    else "%s ago" % spell(minutes_since(t, now)))
everything["slots"] = everything["room"].apply(
    lambda r: slot_states(recent, r, now))
everything = everything.sort_values(
    by=["level", "room"],
    key=lambda c: c.map(RANK) if c.name == "level" else c)


def stake_caveat(rooms_in_figure):
    """What the money figure is resting on, in one line.

    The figure is empty room-hours multiplied by an assumed 1.2 kW and the
    off-peak rate. The empty hours are measured. Everything else is not: it
    assumes every one of these rooms had its unit running for every empty
    minute, and for a room whose unit nobody has calibrated that is an
    assumption, not a reading. With one unit measured out of forty-one, the
    figure is almost entirely assumption -- which is fine for an upper bound
    and dishonest as a headline, so the page says which it is and how far
    the assumption reaches.
    """
    import campus_view

    known = campus_view.calibrated_counts()
    unread = sum(1 for r in rooms_in_figure if not known.get(r))
    total = len(list(rooms_in_figure))
    if not total:
        return "nothing to count"
    if unread:
        return ("upper bound · %d of %d units unread, assumed running"
                % (unread, total))
    return "upper bound, not a bill"


try:
    month = load_history()
except psycopg2.Error:
    month = pd.DataFrame()
try:
    two_days = load_beats_since(50)
except psycopg2.Error:
    two_days = None
today_start = now.tz_convert(PKT).normalize()


def front_figures(name):
    """One campus, as the welcome card and the overview tell it."""
    here = everything[everything["campus"] == name]
    paid = here[here["has_unit"] & here["alerts"]]
    events = month if not month.empty else recent
    stake = money(wasted_minutes(events, paid["room"], today_start, now),
                  assumptions)[1]
    return overview.campus_summary(
        name, here, events, two_days, now, stake=stake,
        stake_note=stake_caveat(list(paid["room"])), live=healthy)


if campus is None:
    # ---- the front door: both campuses, each a way in --------------------
    # st.markdown, not st.html: st.html sanitises every SVG away, which
    # took the charts, the strips and the company mark with it.
    st.markdown(overview.welcome([front_figures(c) for c in campuses], mode,
                                 wordmark(mode), live_text, healthy, when,
                                 dict(LINK_BASE, campus=None)),
                unsafe_allow_html=True)
    st.stop()

df = everything[everything["campus"] == campus].copy()
st.markdown(overview.campus_head({"name": campus}, campuses, mode,
                                 wordmark(mode), live_text, healthy, when,
                                 LINK_BASE), unsafe_allow_html=True)

# ---- the views -------------------------------------------------------------
#
# Five in a row across the top -- the ones people open -- and the rest behind
# "More". A click on a room anywhere is a link carrying its name, and lands on
# One room.
PRIMARY = ["Overview", "Who comes when", "Rooms", "Meters", "Analysis"]
SECONDARY = ["One room", "Camera health", "Look at the rooms",
             "Numbers & history"]
VIEWS = PRIMARY + SECONDARY
if st.session_state.get("view") not in VIEWS:
    st.session_state["view"] = "Overview"
clicked = st.query_params.get("room")
if clicked and st.session_state.get("_came_from") != clicked:
    st.session_state["_came_from"] = clicked
    st.session_state["view"] = "One room"


def _picked_primary():
    picked = st.session_state.get("nav_primary")
    if picked:
        st.session_state["view"] = picked


def _go(target):
    st.session_state["view"] = target


current = st.session_state["view"]
st.session_state["nav_primary"] = current if current in PRIMARY else None
nav_col, more_col = st.columns([6, 1], vertical_alignment="center")
with nav_col:
    if hasattr(st, "segmented_control"):
        st.segmented_control("View", PRIMARY, key="nav_primary",
                             on_change=_picked_primary,
                             label_visibility="collapsed")
    else:
        if st.session_state["nav_primary"] is None:
            st.session_state["nav_primary"] = PRIMARY[0]
        st.radio("View", PRIMARY, key="nav_primary", horizontal=True,
                 on_change=_picked_primary, label_visibility="collapsed")
with more_col:
    label = current if current in SECONDARY else "More"
    with stretch(st.popover, label):
        for target in SECONDARY:
            stretch(st.button, target, key="go_" + target, on_click=_go,
                    args=(target,),
                    type="primary" if target == current else "secondary")
view = st.session_state["view"]

if view == "Overview":
    import analysis_view as av

    st.markdown(overview.campus_body(front_figures(campus), mode, LINK_BASE,
                                     tariff=av.peak_window(assumptions)),
                unsafe_allow_html=True)
    st.stop()

cooled = df[df["has_unit"]]
# Rooms whose cooling is a choice. The server rooms have units and sit empty
# nearly always, and their empty hours are what keeps the equipment alive, so
# counting them here would put money against something nobody should switch
# off.
discretionary = cooled[cooled["alerts"]]
at_stake = money(
    wasted_minutes(recent, discretionary["room"],
                   now - pd.Timedelta(hours=DETAIL_HOURS), now),
    assumptions)[1]
stake_note = stake_caveat(list(discretionary["room"]))
saved, span, enough = against_baseline(month, discretionary["room"], now,
                                       assumptions)
acting = df[df["level"].isin(["Red", "Amber"])]

if view == "Rooms":
    hunt = st.text_input("Find a room", placeholder="name or part of one")
    if hunt:
        found = df[df["room"].str.contains(hunt, case=False, na=False)]
        if found.empty:
            st.info("No room here matches %r." % hunt)
        else:
            st.markdown(
                '<div style="font-size:.8rem;color:%s;margin-bottom:6px;">'
                '%d room%s matching “%s”</div>%s'
                % (MUTED, len(found), "" if len(found) == 1 else "s", hunt,
                   "".join(linked(status_row(row), row["room"])
                           for _, row in found.iterrows())),
                unsafe_allow_html=True)
        st.divider()
    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:10px;'
        'margin:0 0 6px;"><span style="font-size:1.1rem;font-weight:720;">'
        'Every room</span><span style="font-size:.72rem;color:%s;">'
        '%d rooms &middot; who is in it, what its unit is doing, and its last'
        ' %d hours</span></div>' % (MUTED, len(df), STRIP_HOURS),
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
            '<div style="font-size:.63rem;letter-spacing:.14em;color:%s;'
            'margin:11px 0 4px;">%s &middot; %d%s</div>%s'
            % (MUTED, zone.upper(), len(here), note,
               "".join(linked(status_row(row), row["room"])
                       for _, row in here.iterrows())),
            unsafe_allow_html=True)
    # Counted, not asserted. This line used to say flatly that no unit had
    # been calibrated, which stayed on the page after the first one was --
    # so the page was telling the reader to disregard the very badge it had
    # just started filling in.
    known = int(cooled["ac_state"].notna().sum()) if len(cooled) else 0
    if known == 0:
        units = ("Every AC badge reads “?” because no unit has been"
                 " calibrated yet — that is unknown, not off.")
    elif known < len(cooled):
        units = ("%d of %d units are calibrated and read on or off; the rest"
                 " show “?”, which is unknown, not off."
                 % (known, len(cooled)))
    else:
        units = "Every unit is calibrated, so each badge is a reading."
    st.caption("The bar on each row is the last %d hours: blue where people"
               " were seen, grey where the room was empty, pale where nothing"
               " was recorded. %s Rooms with no unit show a dash, because"
               " there is nothing in them to be off." % (STRIP_HOURS, units))

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

elif view == "Meters":
    show_meters(df, recent, now)

elif view == "Analysis":
    show_analysis(df, recent, now)

elif view == "Camera health":
    show_cameras(df, now)

elif view == "Look at the rooms":
    show_stills(cooled, now)

else:
    show_numbers(df, cooled, recent, now)
