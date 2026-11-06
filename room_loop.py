"""Watch every room on every recorder, one camera at a time.

The single-room system holds one RTSP stream open and reads it continuously.
That does not survive being multiplied: forty-eight streams would saturate the
recorders, the network and the laptop all at once, to answer a question that
changes on the scale of three-quarters of an hour.

So this goes round instead. Open a channel, take a frame, close it, move on.
One pass over every room is a cycle, and a cycle takes a couple of minutes.
That is a sample every two minutes per room rather than a live view, which is
the right resolution for "has this room been empty for forty-five minutes" and
far kinder to the recorders the security team depends on.

    python room_loop.py --once                 one pass, then stop
    python room_loop.py --recorder dvr2        just the offices
    python room_loop.py --room "Admin Room"    just one room

Credentials come from .env, named by each recorder's user_env and pass_env in
rooms.yaml. Nothing is written to the database unless --db is passed, so the
first run against a live recorder changes nothing anywhere.
"""
import argparse
import contextlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

# Joining a stream part way through means ffmpeg decodes a few frames against a
# reference it never received, and it says so on stderr every single time. Those
# are the frames grab() throws away on purpose, so the complaints are correct
# and useless: over forty-eight cameras they ran to several times the length of
# the report underneath them, and a report nobody scrolls back through is a
# report nobody reads.
#
# Asking OpenCV to quieten ffmpeg did not work. The value for silence is -8, and
# the build here reads this setting as an unsigned number, so a negative one is
# not accepted. 0 is ffmpeg's next quietest level and does get through. It is
# left in because it costs nothing, but it is not what does the work: see
# muffled() below, which closes the door the messages actually come out of.
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "0")

import cv2  # noqa: E402  (must follow the env var above)
import psycopg2
import yaml
from dotenv import load_dotenv

from privacy_blur import anonymize, count_people
from schedule import describe, wait_before_reporting
from test_camera import build_url, grab

PKT = timezone(timedelta(hours=5))

# A Dahua recording in 1080N keeps half the horizontal detail and stretches it
# back on playback, so what arrives over RTSP is squashed sideways. A standing
# person in such a frame is a tall thin column, which is not a shape the
# detector was ever shown. Widening it first costs a resize and buys back the
# accuracy. Listed explicitly rather than guessed from the aspect ratio: a
# camera genuinely mounted in portrait would be ruined by the same correction.
ANAMORPHIC = {(960, 1080): (1920, 1080)}

STATE_FILE = "room_state.json"
SNAPSHOT_DIR = "snapshots"

# How often to record that the loop is alive. The single-room system beat every
# half hour, which it could afford: it wrote a row every thirty seconds, so a
# gap in those rows already said it had stopped. This one writes only when a
# room changes, and an office at 3am changes nothing for hours, so silence
# proves nothing on its own. The beat is the only thing separating "nothing
# changed" from "nothing was watching", and half an hour of either looking
# identical is too long when the dashboard is meant to show whether the system
# is up. A row is a timestamp; twelve an hour costs nothing.
HEARTBEAT_SECONDS = 300
RETENTION_DAYS = 90
RETENTION_SECONDS = 24 * 3600

# Same code unified_system uses, so run_system.bat can tell a misconfiguration
# apart from a crash and stop retrying instead of looping on it forever.
EXIT_CONFIG = 78

# The two errors here do not cost the same. Counting someone who is not there
# wastes nobody's time: the room reads occupied and no alert goes out, and the
# only loss is a saving not made. Missing someone who is there starts an empty
# clock in a room that is not empty, and three-quarters of an hour later sends
# somebody to switch off an air conditioner over an occupied desk. This system
# has already sent one alert calling an occupied room empty, and that is the
# kind of mistake people remember about a system rather than about an alert.
#
# So where the two trade off, take the more sensitive setting. 640 was chosen
# here to keep a forty-eight camera pass short, which optimised the wrong side
# of that trade: a person at the far end of a room, half behind a desk, is
# perhaps sixty pixels tall once the frame is scaled to 640. The single-room
# system this grew out of ran every detection at 1280 and did not have the
# problem. A pass takes a couple of minutes instead of one, against a question
# measured in forty-five.
DETECT_SIZE = 1280

# Lowering this merges two boxes drawn on one person. It is the knob for an
# over-count, and confidence is not: see privacy_blur.DETECT_IOU.
DETECT_IOU = 0.7


@contextlib.contextmanager
def muffled():
    """Silence the decoder for the duration of one capture.

    These messages are written by ffmpeg itself, in C, straight to file
    descriptor 2. Nothing done in Python intercepts them: they are already past
    sys.stderr by the time they appear. So the descriptor itself is pointed at
    nowhere and put back afterwards.

    Deliberately wrapped around the capture alone, and not the whole cycle. A
    Python traceback also goes to stderr, and a loop that hides its own crash
    while continuing to print neat cycle reports would be far worse than a
    noisy one.
    """
    sys.stderr.flush()
    saved = os.dup(2)
    blackhole = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(blackhole, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(blackhole)
        os.close(saved)


def fail_config(message):
    print("\n>> CONFIGURATION PROBLEM\n>> %s\n" % message)
    sys.exit(EXIT_CONFIG)


def safe_error(e):
    """Describe a failure without repeating the driver's message.

    psycopg2 writes the host, port, user and database name into its error text,
    and this prints to a console that gets photographed and pasted into chats.
    The type and the standard error code are enough to act on.
    """
    code = getattr(e, "pgcode", None)
    return type(e).__name__ + (" [%s]" % code if code else "")


def connect():
    return psycopg2.connect(os.environ["DATABASE_URL"],
                            sslmode=os.getenv("DB_SSLMODE", "require"))


def verify_database():
    """Fail now, loudly, rather than silently recording nothing for a week."""
    if not os.getenv("DATABASE_URL"):
        fail_config("DATABASE_URL is not set in .env. Run with --no-db to"
                    " watch the rooms without recording anything.")
    try:
        conn = connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT to_regclass('public.room_events')")
            missing = cursor.fetchone()[0] is None
            cursor.close()
        finally:
            conn.close()
    except psycopg2.Error as e:
        fail_config("Cannot reach the database (%s). Check DATABASE_URL in"
                    " .env. The driver's own message is withheld because it"
                    " contains connection details." % safe_error(e))
    if missing:
        fail_config("The room_events table does not exist. An administrator"
                    " runs sql/04_rooms.sql once in the Supabase SQL editor;"
                    " this machine deliberately cannot create tables.")


def record(rows):
    """Insert one cycle's changes. False means they did not land."""
    if not rows:
        return True
    try:
        conn = connect()
        try:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO room_events (timestamp, recorder, room, status,"
                " people, empty_since, ac_state)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)", rows)
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        return True
    except psycopg2.Error as e:
        print(">> database write failed: %s" % safe_error(e))
        return False


def beat():
    try:
        conn = connect()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO heartbeat (timestamp) VALUES (%s)",
                           (datetime.now(PKT),))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        return True
    except psycopg2.Error as e:
        print(">> heartbeat failed: %s" % safe_error(e))
        return False


def sweep():
    try:
        conn = connect()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM room_events WHERE timestamp <"
                           " NOW() - make_interval(days => %s)",
                           (RETENTION_DAYS,))
            gone = cursor.rowcount
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        print(">> retention: %d row(s) older than %d days removed"
              % (gone, RETENTION_DAYS))
        return True
    except psycopg2.Error as e:
        print(">> retention sweep failed: %s" % safe_error(e))
        return False


class Room:
    """One room, and what the last pass over its cameras established."""

    def __init__(self, cfg):
        self.name = cfg["name"]
        self.recorder = cfg["recorder"]
        self.channels = list(cfg["channels"])
        self.ac = cfg["ac"]
        self.alerts = cfg.get("alert") != "never"
        self.empty_after = cfg.get("empty_after_minutes")
        self.status = "unknown"         # occupied / empty / unknown
        self.people = None
        self.empty_since = None
        self.detail = "not sampled yet"
        self.recorded = None            # what the database last heard

    def state(self):
        return (self.status, self.people)

    @property
    def watched_for_waste(self):
        return self.ac in ("visible", "hidden") and self.alerts

    def observe(self, people, answered, now):
        """Fold one pass's readings into this room's state.

        The asymmetry here is deliberate. Seeing a person proves the room is
        occupied, and one camera is enough to prove it. Seeing nobody proves
        the room is empty only if every camera on it looked -- a room is not
        established as empty on the strength of the cameras that happened to
        answer. Getting that backwards is what produces an alert saying a room
        is empty while somebody sits in the part of it nobody could see.
        """
        total = len(self.channels)
        if answered == 0:
            self.status, self.people, self.empty_since = "unknown", None, None
            self.detail = "no camera answered"
            return
        if people > 0:
            self.status, self.people, self.empty_since = "occupied", people, None
            self.detail = "%d %s" % (people, "person" if people == 1 else "people")
            return
        if answered < total:
            # Nobody in the frames that came back, but the room has not been
            # looked at in full, so the empty clock does not start or continue.
            self.status, self.people, self.empty_since = "unknown", 0, None
            self.detail = "%d of %d cameras answered" % (answered, total)
            return
        if self.status != "empty" or self.empty_since is None:
            self.empty_since = now
        self.status, self.people = "empty", 0
        self.detail = "%d min" % int(self.empty_minutes(now))

    def empty_minutes(self, now):
        if self.status != "empty" or self.empty_since is None:
            return 0.0
        return (now - self.empty_since).total_seconds() / 60.0

    def due_for_check(self, now, hours=None):
        if not self.watched_for_waste:
            return False
        wait = wait_before_reporting(self.empty_after, now, hours)
        return wait is not None and self.empty_minutes(now) >= wait


def widen(frame):
    """Undo an anamorphic recording mode before anything looks at the picture."""
    target = ANAMORPHIC.get((frame.shape[1], frame.shape[0]))
    if target is None:
        return frame
    return cv2.resize(frame, target, interpolation=cv2.INTER_LINEAR)


def load_rooms(path, only_recorders=None, only_rooms=None):
    cfg = yaml.safe_load(open(path))
    rooms = [Room(r) for r in cfg["rooms"]]
    if only_recorders:
        rooms = [r for r in rooms if r.recorder in only_recorders]
    if only_rooms:
        wanted = {n.lower() for n in only_rooms}
        rooms = [r for r in rooms if r.name.lower() in wanted]
    if not rooms:
        sys.exit("no rooms matched")
    return cfg["recorders"], rooms


def recorder_login(key, rec):
    user = os.getenv(rec.get("user_env", ""))
    password = os.getenv(rec.get("pass_env", ""))
    if not user or not password:
        sys.exit(
            "recorder %s needs %s and %s in .env.\n"
            "Put the view-only account there, not the administrator one, and\n"
            "keep .env out of git -- it is already in .gitignore."
            % (key, rec.get("user_env"), rec.get("pass_env")))
    return user, password


def sample(room, rec, model, imgsz, iou, timeout):
    """One frame from each of a room's cameras.

    Returns the count, how many cameras answered, and the frame worth keeping
    -- the one with the most people in it, since a room is best shown by the
    camera that can see somebody rather than the one that happens to be first.
    """
    people, answered, keep = 0, 0, None
    want_main = rec.get("stream", "sub") == "main"
    for channel in room.channels:
        url = build_url(rec["host"], channel, rec["user"], rec["password"],
                        want_main, rec.get("brand", "hikvision"))
        with muffled():
            frame, _ = grab(url, max_seconds=timeout)
        if frame is None:
            continue
        answered += 1
        wide = widen(frame)
        here = count_people(wide, model, imgsz=imgsz, iou=iou)
        if keep is None or here > people:
            keep = wide
        people = max(people, here)
    return people, answered, keep


def save_snapshot(room, frame, model, folder=SNAPSHOT_DIR):
    """Keep one blurred still per room, overwritten each pass.

    Deliberately narrow. It is blurred with the same pass the alert snapshots
    use, so faces and screens are gone before it touches the disk; it is a
    still rather than a stream; only the rooms with a unit get one, because
    those are the ones somebody has a reason to look at before going home; it
    is overwritten rather than accumulated, so there is no archive of the
    building to lose; and it never goes near the database, which holds counts
    and nothing else by design.

    That design was reviewed. Pictures are a different kind of data from
    counts, so this stays off unless rooms.yaml turns it on.
    """
    os.makedirs(folder, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in room.name)
    path = os.path.join(folder, "%s.jpg" % safe)
    temp = path + ".tmp"
    cv2.imwrite(temp, anonymize(frame, model))
    os.replace(temp, path)   # never leave a half-written picture to be read


def save_state(rooms, path, now):
    """Update this run's rooms in the state file, leaving the others alone.

    A run is often a subset -- one recorder, or one room, while something is
    being checked. Writing only that subset would drop every other room's
    empty-since time, so a quick --room check would silently reset the clocks
    on twenty-nine rooms it never looked at.
    """
    known = {}
    if os.path.exists(path):
        try:
            known = json.load(open(path)).get("rooms", {})
        except (ValueError, json.JSONDecodeError):
            pass
    for room in rooms:
        known[room.name] = {
            "status": room.status,
            "people": room.people,
            "empty_since": (room.empty_since.isoformat()
                            if room.empty_since else None),
        }
    payload = {"saved_at": now.isoformat(), "rooms": known}
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, path)          # never leave a half-written state file


def load_state(rooms, path, max_gap_minutes):
    """Pick up where the last run left off, but only if it stopped recently.

    An empty-since time is a claim that nobody has been in the room since then,
    and that claim is only as good as the watching behind it. If the loop was
    down for an hour, nobody knows what happened in that hour, and carrying the
    old time forward would let a room come back claiming it has been empty all
    along -- possibly straight past its threshold and into an alert about a
    period nothing was watching. So a long gap starts the clocks again.
    """
    if not os.path.exists(path):
        return
    try:
        payload = json.load(open(path))
        saved_at = datetime.fromisoformat(payload["saved_at"])
    except (ValueError, KeyError, json.JSONDecodeError):
        print(">> state file unreadable; starting fresh")
        return
    gap = (datetime.now(PKT) - saved_at).total_seconds() / 60.0
    if gap > max_gap_minutes:
        print(">> last run ended %.0f min ago; nobody was watching in between,"
              " so the empty clocks start again" % gap)
        return
    restored = 0
    for room in rooms:
        saved = payload["rooms"].get(room.name)
        if not saved:
            continue
        room.status = saved["status"]
        room.people = saved["people"]
        room.empty_since = (datetime.fromisoformat(saved["empty_since"])
                            if saved["empty_since"] else None)
        restored += 1
    print(">> carried %d room(s) over from %.0f min ago" % (restored, gap))


def report(rooms, now, cycle, seconds, hours=None):
    print("\n>> cycle %d  %s  (%.0fs)  %s"
          % (cycle, now.strftime("%H:%M:%S"), seconds, describe(now, hours)))
    for room in sorted(rooms, key=lambda r: (r.status != "unknown", r.name)):
        flag = "  "
        if room.due_for_check(now, hours):
            flag = "!!"
        elif room.status == "unknown":
            flag = " ?"
        print("   %s %-9s %-26s %s"
              % (flag, room.status, room.name[:26], room.detail))
    due = [r for r in rooms if r.due_for_check(now, hours)]
    if due:
        print(">> %d room(s) worth checking: %s"
              % (len(due), ", ".join(r.name for r in due)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms.yaml")
    ap.add_argument("--recorder", action="append",
                    help="only this recorder (repeatable)")
    ap.add_argument("--room", action="append",
                    help="only this room (repeatable)")
    ap.add_argument("--once", action="store_true", help="one cycle, then stop")
    ap.add_argument("--imgsz", type=int, default=DETECT_SIZE,
                    help="detector input size (default %d); lower is faster"
                         % DETECT_SIZE)
    ap.add_argument("--iou", type=float, default=DETECT_IOU,
                    help="box overlap allowed (default %s); lower merges"
                         " duplicates" % DETECT_IOU)
    ap.add_argument("--timeout", type=float, default=5.0,
                    help="seconds to wait for a frame (default 5)")
    ap.add_argument("--min-cycle", type=float, default=60.0,
                    help="shortest gap between cycles, seconds (default 60)")
    ap.add_argument("--state", default=STATE_FILE)
    ap.add_argument("--no-db", action="store_true",
                    help="watch and print, but record nothing")
    args = ap.parse_args()

    load_dotenv()
    recorders, rooms = load_rooms(args.config, args.recorder, args.room)

    if args.no_db:
        print(">> --no-db: nothing will be recorded")
    else:
        verify_database()

    used = {r.recorder for r in rooms}
    for key in used:
        if key not in recorders:
            sys.exit("rooms.yaml has rooms on recorder %r but no such recorder"
                     % key)
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password

    hours = yaml.safe_load(open(args.config)).get("hours")
    print(">> %s" % describe(datetime.now(PKT), hours))

    snapshots = bool(yaml.safe_load(open(args.config))
                     .get("snapshots", {}).get("enabled", False))
    if snapshots:
        print(">> snapshots on: one blurred still per air-conditioned room,"
              " in %s/, overwritten each pass" % SNAPSHOT_DIR)

    cameras = sum(len(r.channels) for r in rooms)
    print(">> %d rooms, %d cameras, %d recorder(s): %s"
          % (len(rooms), cameras, len(used), ", ".join(sorted(used))))
    watched = [r for r in rooms if r.watched_for_waste]
    print(">> %d room(s) can raise an air-conditioner check; the rest are"
          " counted but never alert" % len(watched))

    from ultralytics import YOLO          # slow import, so not at module level
    model = YOLO("yolov8n.pt")

    load_state(rooms, args.state, max_gap_minutes=max(10.0,
                                                      args.min_cycle / 60 * 3))

    cycle = 0
    # Sweep on the first pass rather than a day in: a machine restarted daily
    # would otherwise never reach the interval and never delete anything.
    last_beat, last_sweep = 0.0, 0.0
    while True:
        cycle += 1
        started = time.time()
        for room in rooms:
            now = datetime.now(PKT)
            people, answered, frame = sample(room, recorders[room.recorder],
                                             model, args.imgsz, args.iou,
                                             args.timeout)
            room.observe(people, answered, now)
            if snapshots and frame is not None and room.ac in ("visible",
                                                               "hidden"):
                save_snapshot(room, frame, model)
        now = datetime.now(PKT)
        elapsed = time.time() - started
        report(rooms, now, cycle, elapsed, hours)
        save_state(rooms, args.state, now)

        if not args.no_db:
            changed = [r for r in rooms if r.state() != r.recorded]
            if record([(now, r.recorder, r.name, r.status, r.people,
                        r.empty_since, None) for r in changed]):
                # Only once the insert has landed. Marking them recorded on a
                # failed write would drop the change silently, and the next
                # cycle, seeing no difference, would never write it either:
                # the room would simply go missing from its own history.
                for room in changed:
                    room.recorded = room.state()
                if changed:
                    print(">> recorded %d change(s)" % len(changed))
            if time.time() - last_beat >= HEARTBEAT_SECONDS and beat():
                last_beat = time.time()
            if time.time() - last_sweep >= RETENTION_SECONDS and sweep():
                last_sweep = time.time()

        if args.once:
            return
        spare = args.min_cycle - elapsed
        if spare > 0:
            time.sleep(spare)


if __name__ == "__main__":
    main()
