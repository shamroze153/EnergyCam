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

SLOT_INK = {"occupied": "#7BAE48", "empty": "#E0E0E0", "unknown": "#BDBDBD"}
NO_DATA = "#F4F4F4"


def slot_states(recent, room, now):
    """What each five-minute slot of the window held, oldest first.

    One source of truth: the strip under a room and the hours counted up at
    the top are the same arithmetic, so they cannot drift apart and start
    telling different stories about the same afternoon.
    """
    mine = recent[recent["room"] == room]
    if mine.empty:
        return [None] * STRIP_SLOTS
    start = now - pd.Timedelta(hours=STRIP_HOURS)
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
    marks = np.linspace(0, span, STRIP_SLOTS, endpoint=False)
    where = np.searchsorted(stamps, marks, side="right") - 1
    return [None if i < 0 else states[i] for i in where]


def strip_svg(slots, height=7, radius=3):
    rects = "".join(
        '<rect x="%d" y="0" width="1" height="6" fill="%s"/>'
        % (slot, SLOT_INK.get(state, NO_DATA))
        for slot, state in enumerate(slots))
    return ('<svg viewBox="0 0 %d 6" preserveAspectRatio="none" '
            'style="width:100%%;height:%dpx;border-radius:%dpx;display:block;">'
            '%s</svg>' % (STRIP_SLOTS, height, radius, rects))


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
needing = int((df["level"].isin(["Red", "Amber"])).sum())
silent = int((df["level"] == "Fault").sum())

st.markdown(
    '<div style="display:flex;gap:11px;flex-wrap:wrap;margin-bottom:16px;">'
    '%s%s%s%s</div>' % (
        figure_row("Rooms wanting action", needing,
                   "empty past their own threshold",
                   "#A33434" if needing else "#14181B"),
        figure_row("Air-conditioned rooms", len(cooled),
                   "%d watched for occupancy only" % len(watched)),
        figure_row("Empty cooled-room time", spell(empty_slots * 5),
                   "added up across %d rooms, last %dh"
                   % (len(cooled), STRIP_HOURS)),
        figure_row("Cameras not answering", silent,
                   "rooms reported as unknown, not empty",
                   "#6A6A6A" if silent else "#14181B")),
    unsafe_allow_html=True)

st.markdown(
    '<div style="display:flex;align-items:baseline;gap:10px;margin:4px 0 9px;">'
    '<span style="font-size:1.12rem;font-weight:720;">Air-conditioned rooms'
    '</span><span style="font-size:.72rem;color:#8A949A;">%d rooms &middot;'
    ' these are the ones that can waste anything</span></div>' % len(cooled),
    unsafe_allow_html=True)
st.markdown(
    '<div style="display:flex;flex-wrap:wrap;gap:12px;">%s</div>'
    % "".join(room_card(row, recent, now) for _, row in cooled.iterrows()),
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
           "".join(lane(row) for _, row in here.iterrows()),
           hour_axis(now)),
        unsafe_allow_html=True)

st.caption("Bands show the last %d hours: green where people were seen, grey"
           " where the room was empty, pale where nothing was recorded yet."
           " Every air conditioner is drawn dashed with a question mark"
           " because none has been calibrated — that is unknown, not off."
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
