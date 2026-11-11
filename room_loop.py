"""Watch every room on every recorder, a frame at a time.

The single-room system holds one RTSP stream open and reads it continuously.
That does not survive being multiplied: ninety-six streams would saturate the
recorders, the network and the laptop all at once. So this goes round instead.
Open a channel, take a frame, close it, move on. One pass over every room is
a cycle.

Going round does not mean going round one camera at a time, which is what it
meant at first and what made a pass over ninety-six cameras take minutes.
Almost all of that was waiting: a camera takes seconds to answer and costs
nothing while it does. So the waiting is done several cameras at a time, and
only the counting -- which uses the processor, and which one model can only do
one of at a time -- is done in turn. A cycle is now about as long as its
slowest recorder rather than the sum of every camera on the site, which is the
difference between a dashboard that is live and one that is four minutes
behind.

Each recorder has its own cap on how many of its streams may be open at once.
That half is deliberate: a recorder will only serve so many, and asking for
too many at once is how a machine starts refusing this one altogether.

    python room_loop.py --once                 one pass, then stop
    python room_loop.py --recorder dvr2        just the offices
    python room_loop.py --room "Admin Room"    just one room
    python room_loop.py --workers 4            gentler on the recorders

Credentials come from .env, named by each recorder's user_env and pass_env in
rooms.yaml. --no-db watches and prints without recording anything, so a first
run against a live recorder changes nothing anywhere.
"""
import argparse
import contextlib
import threading
import json
import os
import sys
import time
import traceback
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

from ac_detect import load_units, read_room
from alerts import Alerter, compose, configured, deliver, why_not_configured
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402

from privacy_blur import anonymize, people_boxes
from schedule import (WORKING, describe, in_operations, period,  # noqa: F401
                      wait_before_reporting)
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
# is up. A row is a timestamp, so this costs almost nothing.
#
# It is also what the dashboard's "live" badge counts from. At five minutes
# the badge spent most of its life reporting a system that was working fine
# as having last spoken four minutes ago, which reads as stale however fresh
# the rooms underneath it are. Once a minute matches the cycle, so the badge
# says what is actually true.
# How many passes in a row must see nobody before a room is called empty.
#
# One is not enough. A seated person at the edge of what the detector can
# manage is found in some frames and not others -- measured at Admin Room,
# roughly half -- so a single blank frame flips an occupied room to empty
# and back again on the next pass. Two passes, about five minutes apart in
# practice, against a waste threshold measured in forty-fives.
CONFIRM_EMPTY = 2

HEARTBEAT_SECONDS = 60
RETENTION_DAYS = 90
RETENTION_SECONDS = 24 * 3600

# Same code unified_system uses, so run_system.bat can tell a misconfiguration
# apart from a crash and stop retrying instead of looping on it forever.
EXIT_CONFIG = 78

# How long to wait after a cycle blows up, and the ceiling it backs off to.
# A recorder that has gone away is not helped by being asked every second,
# and a loop that gives up entirely records nothing at all.
RETRY_SECONDS = 15
RETRY_CEILING = 300


def no_quick_edit():
    """Stop a stray click in the console window freezing the loop.

    Windows consoles ship with QuickEdit on. Clicking anywhere in the window
    starts a text selection, and from that moment every write to stdout
    blocks until somebody presses Escape or Enter. The loop has not crashed
    and has not exited; it is simply stopped, silently, and the rooms go
    unrecorded until whoever clicked happens to notice. From the outside
    this is indistinguishable from a hang, which is why it is worth a dozen
    lines to make impossible rather than a paragraph in a document nobody
    reads at the moment it matters.

    Only the console this process owns is touched, and only for as long as
    it runs. Nothing is written to the registry and no other window changes.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.GetStdHandle(-10)            # STD_INPUT_HANDLE
        mode = ctypes.c_uint()
        if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            return False                             # not a console at all
        quick_edit, extended = 0x0040, 0x0080
        # The extended flag has to be set for the quick-edit bit to be read.
        wanted = (mode.value & ~quick_edit) | extended
        return bool(kernel.SetConsoleMode(handle, wanted))
    except Exception:                                # noqa: BLE001
        return False


def stay_awake(on=True):
    """Ask Windows not to go to sleep while the loop is running.

    This covers the idle timer, which is what sends an unattended desk
    machine to sleep in the middle of the night -- the hours this system
    exists to measure. It covers nothing else, and the difference matters:
    closing a laptop lid, choosing Sleep from the menu, or a policy that
    suspends on lock will all still stop the machine, and this call will not
    argue. A laptop therefore still needs its lid action set to "do nothing"
    in Power Options; see docs/always_on.md.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        continuous, system_required = 0x80000000, 0x00000001
        flags = (continuous | system_required) if on else continuous
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except Exception:                                # noqa: BLE001
        return False

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
# How many cameras may be waited on at once, and how many of those may be on
# the same recorder. Waiting for a frame takes seconds and uses nothing, so
# doing it one camera at a time is what made a pass over ninety-six cameras
# take minutes. The per-recorder cap is the careful half: a recorder will only
# serve so many streams at once, and asking for too many is how a recorder
# starts refusing a machine altogether.
WORKERS = 8
PER_RECORDER = 4
# Rooms are fetched in batches rather than all at once: every frame held is
# several megabytes, and holding ninety-six of them buys nothing.
BATCH = 10

# How much of a detection has to sit inside an ignore zone before it counts as
# one of the room's known false people. Not "touches it": a cardboard cutout
# sits inside its zone entirely, while a real person standing in front of that
# cutout is bigger and reaches outside it, and must still be counted.
IGNORE_OVERLAP = 0.8

# How much evidence to keep. Left alone the folder only grows: a room that
# invents a person once an hour writes a few hundred pictures a month, and
# they are not blurred. Enough to find a pattern, not enough to become an
# archive of the building that nobody meant to keep.
EVIDENCE_KEEP = 400
EVIDENCE_DAYS = 21

# The evidence folder exists to catch the chair that reads as a person at
# three in the morning. On 11 Nov it held nothing from the night at all:
# 10:00 is opening time, so 09:15 counts as after hours, everybody
# arriving between then and ten was photographed every two minutes on
# every camera, the folder hit its 400 cap in three quarters of an hour,
# and the oldest -- the whole night -- were pruned to make room. People
# arriving at work are not the question.
#
# So two limits. Nothing within this margin of the working day, either
# side, where people coming and going is expected and real. And no more
# than one picture per camera per EVIDENCE_EVERY, which is plenty to see
# what a ghost is and keeps one stuck camera from evicting the rest.
EVIDENCE_MARGIN_MINUTES = 60
EVIDENCE_EVERY = 600            # seconds between pictures from one camera
_last_evidence = {}

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

    Deliberately wrapped around the grab alone, and not the whole cycle. A
    Python traceback also goes to stderr, and a loop that hides its own crash
    while continuing to print neat cycle reports would be far worse than a
    noisy one.

    ONE THREAD ONLY. This swaps a file descriptor belonging to the whole
    process, so two overlapping calls interleave into leaving stderr pointed
    at nowhere permanently, or into closing a descriptor the other is still
    holding -- after which the interpreter cannot flush its own output and
    dies at shutdown with code 120, which looks like anything but this. It
    was for a while called from fetch(), which runs eight at a time. The
    caller now wraps the whole parallel grab instead, from one thread, and
    collects what wants printing until the descriptor is back.
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


def prune_old_rows():
    """Delete room_events older than the retention window.

    Named for what it does, because it used to be called sweep() -- and so
    did the pass over the cameras, defined four hundred lines further down.
    Python keeps the last definition, so `sweep()` here reached the camera
    pass with none of its eleven arguments and raised a TypeError on the
    first cycle of every single run, which is what had been stopping the
    loop all along. Two functions, one name, and the one that loses is the
    one defined first.
    """
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
        # A room is a list of cameras, and a camera is a recorder and a
        # channel together. It has to be the pair, not the channel alone:
        # two recorders both have a channel 16, and one place at 140-H is
        # watched by nvr1 and xvr3 at once. Before this, such a place had to
        # be two rooms -- and two rooms meant one of them could sit there
        # calling itself empty for forty-five minutes while the other
        # watched somebody sitting in it, which is a false alert waiting to
        # be sent.
        #
        # The old spelling still works and is what nearly every room uses:
        #   recorder: nvr1
        #   channels: [22]
        # The new one is for a place two recorders can see:
        #   cameras:
        #     - {recorder: nvr1, channel: 22}
        #     - {recorder: xvr3, channel: 16}
        # Which stream this room's cameras are read from, overriding the
        # recorder's own setting. nvr1 and nvr4 hand back 640x360 on the sub
        # stream, which is enough to see that somebody is in a corridor and
        # nowhere near enough to read an air conditioner's display: at that
        # size the display is a handful of pixels. So the rooms that matter
        # ask for the main stream and the car park does not.
        self.stream = cfg.get("stream")
        # A room nobody should spend time on. The three dead channels on
        # xvr3 cost six seconds each, every cycle, for a black frame.
        self.watch = cfg.get("watch", True)
        if cfg.get("cameras"):
            self.cameras = [(c["recorder"], int(c["channel"]))
                            for c in cfg["cameras"]]
        else:
            self.cameras = [(cfg["recorder"], int(ch))
                            for ch in cfg["channels"]]
        if not self.cameras:
            raise ValueError("%s has no cameras" % cfg["name"])
        # The recorder a room is filed under. Several things want one name
        # for a room -- the database column, the report, --recorder -- and
        # for the ninety-odd rooms on a single recorder this is simply it.
        self.recorder = self.cameras[0][0]
        self.channels = [ch for _, ch in self.cameras]
        self.ac = cfg["ac"]
        self.alerts = cfg.get("alert") != "never"
        # A room may need a stricter confidence than the rest of the building:
        # one camera's angle, lighting or clutter can produce a person out of
        # a coat on a chair while every other camera is fine. Raising it for
        # the whole building to fix one room would cost real people elsewhere.
        self.conf = cfg.get("conf")
        # Boxes where a camera reliably sees a person who is not there. On
        # this site that is mostly a doorway or a pane of glass: the camera
        # looks straight through into a corridor, and the people it finds are
        # perfectly real but in a different room. Keyed "16" for a room on
        # one recorder, or "xvr3:16" where it could be either's channel 16.
        self.ignore = {self.camera_key(ch):
                       [[int(v) for v in box] for box in boxes]
                       for ch, boxes in (cfg.get("ignore") or {}).items()}
        self.empty_after = cfg.get("empty_after_minutes")
        self.status = "unknown"         # occupied / empty / unknown
        self.people = None
        self.empty_since = None
        self.detail = "not sampled yet"
        self.ac_state = None            # on / off / None when unmeasured
        self.ac_detail = "not calibrated"
        self.recorded = None            # what the database last heard
        self.blank = 0                  # passes in a row with nobody seen
        self.first_blank = None         # when that run of passes began
        self.was_occupied = False       # somebody was seen, and not yet
                                        # disproved by CONFIRM_EMPTY passes

    def camera_key(self, spec):
        """Turn 16 or "xvr3:16" into the (recorder, channel) pair it means."""
        if isinstance(spec, str) and ":" in spec:
            recorder, channel = spec.split(":", 1)
            return (recorder.strip(), int(channel))
        return (self.recorder, int(spec))

    def state(self):
        # The air conditioner belongs in here. A unit coming on in a room that
        # was already empty changes nothing about the occupancy, and if state
        # were occupancy alone that moment -- the exact moment the waste
        # starts -- would never be written down.
        return (self.status, self.people, self.ac_state)

    @property
    def watched_for_waste(self):
        return self.ac in ("visible", "hidden") and self.alerts

    def observe(self, people, answered, now, ac_state=None,
                ac_detail="not calibrated"):
        """Fold one pass's readings into this room's state.

        The asymmetry here is deliberate. Seeing a person proves the room is
        occupied, and one camera is enough to prove it. Seeing nobody proves
        the room is empty only if every camera on it looked -- a room is not
        established as empty on the strength of the cameras that happened to
        answer. Getting that backwards is what produces an alert saying a room
        is empty while somebody sits in the part of it nobody could see.
        """
        self.ac_state, self.ac_detail = ac_state, ac_detail
        total = len(self.cameras)
        if answered == 0:
            self.status, self.people, self.empty_since = "unknown", None, None
            # The hold is not reset here. A pass that saw nothing because
            # no camera answered is not evidence that the room is empty,
            # and it is not evidence that it is occupied either: it says
            # nothing, so it changes nothing about what is being counted.
            # Resetting would let a camera blinking once undo a hold and
            # empty a room somebody is sitting in.
            #
            # The clock is a different matter. It may not be backdated
            # across a stretch nobody could see, so the run it would be
            # dated from ends here and the next full pass starts a new one.
            self.first_blank = None
            self.detail = "no camera answered"
            return
        if people > 0:
            self.status, self.people, self.empty_since = "occupied", people, None
            # first_blank too, or the next spell of emptiness is dated
            # from the one before it: the room then looks as though it has
            # been empty for hours, the alerter reads it as the same
            # episode it has already mentioned, and says nothing at all.
            self.blank, self.first_blank, self.was_occupied = 0, None, True
            self.detail = "%d %s" % (people, "person" if people == 1 else "people")
            return
        if answered < total:
            # Nobody in the frames that came back, but the room has not been
            # looked at in full, so the empty clock does not start or continue.
            self.status, self.people, self.empty_since = "unknown", 0, None
            self.first_blank = None     # see above: no backdating over a gap
            self.detail = "%d of %d cameras answered" % (answered, total)
            return

        # Every camera looked and nobody was in any of them. That is still
        # not proof on its own.
        #
        # Watched live, Admin Room scored a seated person at 0.40, 0.46,
        # 0.53, 0.31, 0.54 -- and nothing at all on four frames in between,
        # over ninety seconds, while he sat still. The detector finds that
        # person in roughly half the frames. Sampling once a cycle, the
        # room then flips between occupied and empty every few minutes: the
        # live view is wrong half the time, and first-seen and last-seen
        # become the first and last coin toss rather than the first and
        # last person.
        #
        # So the asymmetry above is extended one step. Seeing somebody once
        # proves the room is occupied. Seeing nobody once does not prove it
        # is empty; it takes CONFIRM_EMPTY consecutive passes with every
        # camera answering. A room that is genuinely empty reaches that in
        # a few minutes, against a threshold measured in forty-fives.
        #
        # The clock is backdated to the first of those passes, so nothing
        # is lost: a room empty since six o'clock is still empty since six
        # o'clock, it is simply not announced until the second pass agrees.
        self.blank += 1
        if self.first_blank is None:
            self.first_blank = now
        # was_occupied, not status == "occupied": a camera dropping out for
        # one pass turns the status to unknown, and keying the hold off the
        # status would let that blink end the hold and empty a room with
        # somebody sitting in it.
        if self.blank < CONFIRM_EMPTY and self.was_occupied:
            self.status, self.people = "occupied", self.people or 1
            self.detail = ("nobody seen, %d of %d passes \u2014 holding"
                           % (self.blank, CONFIRM_EMPTY))
            return
        if self.status != "empty" or self.empty_since is None:
            self.empty_since = self.first_blank or now
        self.status, self.people, self.was_occupied = "empty", 0, False
        self.detail = "%d min" % int(self.empty_minutes(now))

    def empty_minutes(self, now):
        if self.status != "empty" or self.empty_since is None:
            return 0.0
        return (now - self.empty_since).total_seconds() / 60.0

    def due_for_check(self, now, hours=None):
        if not self.watched_for_waste:
            return False
        if self.ac_state == "off":
            # Empty with the unit already off is the state we want rooms to be
            # in, not something to send anybody upstairs about. Only a room
            # that is empty with the unit running, or empty with the unit
            # unread, is worth a look.
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
    skipped = [r.name for r in rooms if not r.watch]
    rooms = [r for r in rooms if r.watch]
    if skipped:
        print(">> not watching %d room(s), as rooms.yaml asks: %s"
              % (len(skipped), ", ".join(skipped)))
    if only_recorders:
        # A room watched by two recorders belongs to both, so --recorder keeps
        # it but narrows it to that recorder's cameras. Fetching the others
        # would mean "just the offices" quietly opening streams on nvr1.
        kept = []
        for r in rooms:
            mine = [c for c in r.cameras if c[0] in only_recorders]
            if mine:
                r.cameras = mine
                r.channels = [ch for _, ch in mine]
                r.recorder = mine[0][0]
                kept.append(r)
        rooms = kept
    if only_rooms:
        wanted = {n.lower() for n in only_rooms}
        rooms = [r for r in rooms if r.name.lower() in wanted]
    if not rooms:
        sys.exit("no rooms matched")
    return cfg["recorders"], rooms


def spell_cameras(room):
    """A room's cameras in words, named by recorder only where it helps."""
    if len({rec for rec, _ in room.cameras}) == 1:
        return ", ".join(str(ch) for _, ch in room.cameras)
    return ", ".join("%s:%d" % c for c in room.cameras)


def check_ac_units(units, rooms):
    """Make sure every calibrated room is somewhere the loop will actually look.

    A box measured on channel 9 is only ever read if channel 9 is one of that
    room's cameras. Get the number wrong and nothing errors: the room simply
    reports an unknown air conditioner forever, which looks exactly like a room
    nobody has calibrated yet. So it is checked once, out loud, at startup.
    """
    by_name = {r.name: r for r in rooms}
    problems = []
    for name, cfg in sorted(units.items()):
        room = by_name.get(name)
        if room is None:
            continue            # another recorder's room, not in this run
        channel = cfg.get("channel")
        recorder = cfg.get("recorder", room.recorder)
        if channel is None:
            problems.append("%s: no channel given" % name)
        elif (recorder, int(channel)) not in room.cameras:
            problems.append("%s: calibrated on %s channel %s, but the room's"
                            " cameras are %s"
                            % (name, recorder, channel, spell_cameras(room)))
    if problems:
        fail_config("ac_units.yaml does not match rooms.yaml:\n   - "
                    + "\n   - ".join(problems))
    return sum(1 for n in units if n in by_name)


def set_gates(recorders, per_recorder=PER_RECORDER):
    """Cap how many streams may be open on each recorder at once.

    Each recorder gets its own. Without it, every worker could land on one
    recorder while the other three sit idle -- both slower, and the way to
    get a machine locked out, which happened once already.
    """
    for rec in recorders.values():
        rec["gate"] = threading.Semaphore(per_recorder)


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


def overlap_fraction(box, zone):
    """How much of `box` lies inside `zone`, from 0 to 1."""
    bx1, by1, bx2, by2 = box[:4]
    zx1, zy1, zx2, zy2 = zone
    width = max(0, min(bx2, zx2) - max(bx1, zx1))
    height = max(0, min(by2, zy2) - max(by1, zy1))
    area = (bx2 - bx1) * (by2 - by1)
    return 0.0 if area <= 0 else (width * height) / float(area)


def ignored(box, zones):
    """Is this detection one of the room's known false people?

    Judged by how much of the box lies inside the zone, not by whether it
    touches it. Blanking the pixels instead would be simpler and wrong: a real
    person who walks in front of the poster would vanish with it.
    """
    for zone in zones or []:
        if overlap_fraction(box, zone) >= IGNORE_OVERLAP:
            return True
    return False


def wants_main(room, rec):
    """Whether this room is read from the recorder's main stream.

    One answer, used by everything that grabs a frame. The room's own
    `stream:` wins over the recorder's, because some rooms on a sub-stream
    recorder are too far from their camera to be read at 640x360.

    This used to be worked out separately in three places, and two of them
    -- tune_detect and calibrate_room --live -- looked only at the
    recorder. So a room the loop reads at 2560x1440 was calibrated on a
    640x360 frame, and the loop refused every reading from it for ever,
    quietly, as "frame size does not match". A calibration that can never
    be used is worse than none: it looks finished.
    """
    return (room.stream or rec.get("stream", "sub")) == "main"


def fetch(room, recorders, timeout):
    """Every one of a room's cameras, as {(recorder, channel): frame or None}.

    Only the waiting happens here. No detector is run, because this is called
    from several threads at once and one model cannot be asked two things at
    the same time.
    """
    frames = {}
    for key in room.cameras:
        name, channel = key
        rec = recorders[name]
        want_main = wants_main(room, rec)
        gate = rec.get("gate")
        url = build_url(rec["host"], channel, rec["user"], rec["password"],
                        want_main, rec.get("brand", "hikvision"))
        if gate is not None:
            gate.acquire()
        try:
            # No muffled() here. It swaps file descriptor 2 for the whole
            # process, and this function runs in eight threads at once: two
            # threads overlapping would leave stderr pointed at nowhere for
            # good, or close a descriptor the other still held. The caller
            # muffles once, around the whole grab, from one thread.
            frame, _ = grab(url, max_seconds=timeout)
        finally:
            if gate is not None:
                gate.release()
        frames[key] = widen(frame) if frame is not None else None
    return frames


def examine(room, frames, model, imgsz, iou, ac_units=None):
    """Count the people in a room's frames and read its air conditioner.

    Returns the count, how many cameras answered, the frame worth keeping --
    the one with the most people in it, since a room is best shown by the
    camera that can see somebody rather than the one that happens to be first
    -- and what the unit's own display said.

    The unit is read from one named channel, not from whichever frame
    arrives. Its box is a position in one camera's picture, so measuring it
    on another camera's would give a number with nothing behind it.
    """
    people, answered, keep = 0, 0, None
    ac_config = (ac_units or {}).get(room.name) or {}
    ac_channel = ac_config.get("channel")
    ac_recorder = ac_config.get("recorder", room.recorder)
    ac_state = None
    ac_detail = "not calibrated" if not ac_config else "camera did not answer"
    for key in room.cameras:
        wide = frames.get(key)
        if wide is None:
            continue
        answered += 1
        if key[1] == ac_channel and key[0] == ac_recorder:
            ac_state, ac_detail = read_room(wide, room.name, ac_units)
        boxes = people_boxes(wide, model, conf=room.conf, imgsz=imgsz, iou=iou)
        here = sum(1 for b in boxes if not ignored(b, room.ignore.get(key)))
        if keep is None or here > people:
            keep = wide
        people = max(people, here)
    return people, answered, keep, ac_state, ac_detail


def prune_evidence(folder, keep=EVIDENCE_KEEP, days=EVIDENCE_DAYS):
    """Throw away the oldest, so the folder stops growing.

    Two limits, because they fail differently. The age limit is the one that
    matters: a picture of a corridor from a month ago is nobody's business
    and answers no question anybody is still asking. The count is the
    backstop for a camera that goes wrong and writes a picture every cycle
    all night.
    """
    try:
        names = [n for n in os.listdir(folder) if n.endswith(".jpg")]
    except OSError:
        return 0
    paths = []
    for name in names:
        path = os.path.join(folder, name)
        try:
            paths.append((os.path.getmtime(path), path))
        except OSError:
            continue
    paths.sort()
    cutoff = time.time() - days * 86400
    doomed = [p for when, p in paths if when < cutoff]
    spare = len(paths) - len(doomed) - keep
    if spare > 0:
        doomed += [p for _, p in paths if p not in set(doomed)][:spare]
    gone = 0
    for path in doomed:
        try:
            os.remove(path)
            gone += 1
        except OSError:
            pass
    return gone


def evidence_worthy(now, hours=None):
    """Is a person counted now worth photographing?

    Only when the building is well away from its working day on both
    sides: an hour before opening is people arriving, an hour after
    closing is people leaving, and neither is a ghost.
    """
    margin = timedelta(minutes=EVIDENCE_MARGIN_MINUTES)
    return not (in_operations(now, hours)
                or in_operations(now - margin, hours)
                or in_operations(now + margin, hours))


def keep_evidence(room, frames, model, imgsz, iou, folder, now):
    """Write down what was counted as a person, when nobody should be there.

    An intermittent false person cannot be caught by hand. By the time
    anybody looks at the room it is empty again, the camera agrees it is
    empty, and the only trace is a number on a page that nobody can argue
    with. A chair that reads as a person once an hour, in one light, is
    invisible to every check that runs when somebody is watching.

    So the loop keeps the frame itself, with the boxes and scores drawn on,
    and only outside working hours -- when a counted person is worth
    explaining. During the day they are simply people.

    These frames are NOT blurred, because the whole question they answer is
    whether the thing in the box is a person at all. They stay on this
    machine.
    """
    os.makedirs(folder, exist_ok=True)
    written = []
    for key in room.cameras:
        last = _last_evidence.get((room.name, key))
        if last is not None and (now - last).total_seconds() < EVIDENCE_EVERY:
            continue
        wide = frames.get(key)
        if wide is None:
            continue
        boxes = [b for b in people_boxes(wide, model, conf=room.conf,
                                         imgsz=imgsz, iou=iou)
                 if not ignored(b, room.ignore.get(key))]
        if not boxes:
            continue
        shot = wide.copy()
        for n, (x1, y1, x2, y2, score) in enumerate(boxes, 1):
            cv2.rectangle(shot, (x1, y1), (x2, y2), (80, 220, 90), 2)
            cv2.putText(shot, "%d: %.2f" % (n, score), (x1, max(14, y1 - 7)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 220, 90), 2)
        name = "%s_%s_ch%02d_%s.jpg" % (room.name.replace(" ", "_"), key[0],
                                        key[1], now.strftime("%Y%m%d_%H%M%S"))
        cv2.imwrite(os.path.join(folder, name), shot)
        written.append(name)
        _last_evidence[(room.name, key)] = now
    return written


def sweep(rooms, recorders, model, imgsz, iou, timeout, ac_units=None,
          workers=WORKERS, on_frame=None, evidence=None, hours=None):
    """One pass over every room, waiting on many cameras at once.

    This is the difference between a dashboard that is live and one that is
    four minutes behind. Waiting for a camera costs seconds and no effort;
    counting people costs effort and no waiting. So the waiting is done many
    rooms at a time and the counting one room at a time, and the pass takes
    about as long as its slowest recorder rather than the sum of every camera
    on the site.

    A kept frame is handed to on_frame and then let go, rather than collected
    and returned: holding one per room is most of a gigabyte for no reason.
    """
    out = {}
    for i in range(0, len(rooms), BATCH):
        batch = rooms[i:i + BATCH]
        frames = {}
        failures = []
        # Muffle once, here, around the whole grab -- not inside fetch(),
        # which runs in several threads and would race itself into leaving
        # stderr permanently pointed at nowhere. Nothing inside this block
        # is meant to print; what wants saying is collected and said after
        # the descriptor is back.
        with muffled():
            with ThreadPoolExecutor(max_workers=workers) as pool:
                jobs = {pool.submit(fetch, r, recorders, timeout): r
                        for r in batch}
                for job in as_completed(jobs):
                    room = jobs[job]
                    try:
                        frames[room.name] = job.result()
                    except Exception as e:              # noqa: BLE001
                        # One camera misbehaving must not take the pass down
                        # with it: the room reports nothing, which already
                        # means "unknown", and the rest are still counted.
                        failures.append((room.name, e))
                        frames[room.name] = {}
        for name, e in failures:
            print(">> %s: could not be read (%s)" % (name, e))
        for room in batch:
            people, answered, keep, ac, why = examine(
                room, frames.get(room.name, {}), model, imgsz, iou, ac_units)
            if on_frame is not None and keep is not None:
                on_frame(room, keep)
            now = datetime.now(PKT)
            if evidence and people and evidence_worthy(now, hours):
                for name in keep_evidence(room, frames.get(room.name, {}),
                                          model, imgsz, iou, evidence, now):
                    print(">> kept %s" % name)
                gone = prune_evidence(evidence)
                if gone:
                    print(">> and removed %d older than %d days"
                          % (gone, EVIDENCE_DAYS))
            out[room.name] = (people, answered, ac, why)
        frames.clear()
    return out


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
            "ac_state": room.ac_state,
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
        # .get, because a state file written before air conditioners were read
        # has no such key and should still load.
        room.ac_state = saved.get("ac_state")
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
        air = {"on": "AC on ", "off": "AC off"}.get(room.ac_state, "      ")
        print("   %s %-9s %-26s %s  %s"
              % (flag, room.status, room.name[:26], air, room.detail))
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
    ap.add_argument("--workers", type=int, default=WORKERS,
                    help="cameras waited on at once (default %d); lower this"
                         " if a recorder starts refusing" % WORKERS)
    ap.add_argument("--per-recorder", type=int, default=PER_RECORDER,
                    help="of those, how many on one recorder (default %d)"
                         % PER_RECORDER)
    ap.add_argument("--min-cycle", type=float, default=60.0,
                    help="shortest gap between cycles, seconds (default 60)")
    ap.add_argument("--state", default=STATE_FILE)
    ap.add_argument("--no-db", action="store_true",
                    help="watch and print, but record nothing")
    ap.add_argument("--alerts", action="store_true",
                    help="email when a room is empty past its threshold."
                         " Without it the loop prints what it would have"
                         " sent and sends nothing")
    ap.add_argument("--evidence", nargs="?", const="evidence", default=None,
                    metavar="DIR",
                    help="outside working hours, save a frame of anyone"
                         " counted, boxes and scores drawn on (default"
                         " evidence/). For catching a room that reports a"
                         " person at three in the morning. NOT blurred, and"
                         " kept for %d days or %d pictures, whichever comes"
                         " first: keep the folder on this machine"
                         % (EVIDENCE_DAYS, EVIDENCE_KEEP))
    args = ap.parse_args()

    load_dotenv()
    recorders, rooms = load_rooms(args.config, args.recorder, args.room)

    if args.no_db:
        print(">> --no-db: nothing will be recorded")
    else:
        verify_database()

    used = {rec for r in rooms for rec, _ in r.cameras}
    for key in used:
        if key not in recorders:
            sys.exit("rooms.yaml has rooms on recorder %r but no such recorder"
                     % key)
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password
    set_gates(recorders, args.per_recorder)

    ac_units = load_units()
    calibrated = check_ac_units(ac_units, rooms)
    if calibrated:
        print(">> %d room(s) have a calibrated air conditioner; the rest"
              " report its state as unknown" % calibrated)
    else:
        print(">> no air conditioner is calibrated yet, so every unit's state"
              " stays unknown. To calibrate one:"
              " python calibrate_room.py --help")

    muted = 0
    for room in rooms:
        for key in room.ignore:
            if key not in room.cameras:
                fail_config("%s has an ignore zone on %s channel %d, which is"
                            " not one of its cameras (%s). Nothing would ever"
                            " be filtered."
                            % (room.name, key[0], key[1], spell_cameras(room)))
        muted += sum(len(b) for b in room.ignore.values())
    if muted:
        print(">> %d ignore zone(s) in place: detections that sit inside one"
              " are known false people and are not counted" % muted)
    strict = [r for r in rooms if r.conf]
    if strict:
        print(">> %d room(s) use their own confidence: %s"
              % (len(strict), ", ".join("%s %.2f" % (r.name, r.conf)
                                        for r in strict)))

    alerter = Alerter(send=args.alerts)
    if args.alerts:
        if not configured():
            fail_config("--alerts needs %s in .env. SENDER_EMAIL is the"
                        " account that sends, APP_PASSWORD is a Google app"
                        " password for it (not the account password), and"
                        " ALERT_TO is who receives -- several addresses"
                        " separated by commas." % why_not_configured())
        print(">> alerts ON: mail goes to %s"
              % ", ".join(__import__("alerts").recipients()))
    else:
        print(">> alerts off. The loop will print what it would have sent;"
              " add --alerts to send it")

    hours = yaml.safe_load(open(args.config)).get("hours")
    print(">> %s" % describe(datetime.now(PKT), hours))

    snapshots = bool(yaml.safe_load(open(args.config))
                     .get("snapshots", {}).get("enabled", False))
    if snapshots:
        print(">> snapshots on: one blurred still per air-conditioned room,"
              " in %s/, overwritten each pass" % SNAPSHOT_DIR)

    cameras = sum(len(r.cameras) for r in rooms)
    print(">> %d rooms, %d cameras, %d recorder(s): %s"
          % (len(rooms), cameras, len(used), ", ".join(sorted(used))))
    watched = [r for r in rooms if r.watched_for_waste]
    print(">> %d room(s) can raise an air-conditioner check; the rest are"
          " counted but never alert" % len(watched))

    # Two Windows habits that stop this loop without stopping the process,
    # and without saying anything. Both are turned off for this console and
    # this process only.
    if no_quick_edit():
        print(">> click-to-select is off in this window; a stray click"
              " cannot freeze the loop now")
    if not args.once and stay_awake():
        print(">> asked Windows not to idle-sleep while this runs (a closed"
              " lid or a chosen Sleep will still stop it)")

    from ultralytics import YOLO          # slow import, so not at module level
    model = YOLO("yolov8n.pt")

    load_state(rooms, args.state, max_gap_minutes=max(10.0,
                                                      args.min_cycle / 60 * 3))

    def keeper(room, frame):
        if room.ac in ("visible", "hidden"):
            save_snapshot(room, frame, model)

    keeper = keeper if snapshots else None

    cycle = 0
    # Sweep on the first pass rather than a day in: a machine restarted daily
    # would otherwise never reach the interval and never delete anything.
    last_beat, last_sweep = 0.0, 0.0
    # A cycle that throws used to end the process, and with it the night. A
    # recorder rebooting, a switch dropping a packet, the database refusing a
    # connection for ten seconds -- any of them was the whole building
    # unrecorded until somebody noticed the window had closed. None of those
    # is a reason to stop watching; they are reasons to wait and look again.
    # Configuration errors still exit, because they are caught before the
    # loop and restarting cannot fix them.
    trouble, wait = 0, RETRY_SECONDS
    while True:
        try:
            cycle += 1
            started = time.time()
            readings = sweep(rooms, recorders, model, args.imgsz, args.iou,
                             args.timeout, ac_units, args.workers, keeper,
                             args.evidence, hours)
            now = datetime.now(PKT)
            for room in rooms:
                people, answered, ac, why = readings[room.name]
                room.observe(people, answered, now, ac, why)
            elapsed = time.time() - started
            report(rooms, now, cycle, elapsed, hours)
            save_state(rooms, args.state, now)

            if not args.no_db:
                changed = [r for r in rooms if r.state() != r.recorded]
                if record([(now, r.recorder, r.name, r.status, r.people,
                            r.empty_since, r.ac_state) for r in changed]):
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
                if (time.time() - last_sweep >= RETENTION_SECONDS
                        and prune_old_rows()):
                    last_sweep = time.time()

            worth = alerter.consider(rooms, now, hours)
            if worth:
                subject, body = compose(worth, now, hours)
                if args.alerts:
                    try:
                        sent_to = deliver(subject, body)
                        print(">> alert sent to %d address(es): %s"
                              % (sent_to, subject))
                    except Exception as e:                  # noqa: BLE001
                        # A mail server refusing is not a reason to stop
                        # watching the building. It is a reason to say so and
                        # to let the room be mentioned again, rather than
                        # marking it told when nobody was told.
                        print(">> COULD NOT SEND ALERT: %s" % safe_error(e))
                        for room in worth:
                            alerter.episode.pop(room.name, None)
                            alerter.last_said.pop(room.name, None)
                else:
                    print(">> would have sent: %s" % subject)
                    for line in body.splitlines()[2:2 + len(worth)]:
                        print("   %s" % line)

            if args.once:
                return
            spare = args.min_cycle - elapsed
            if spare > 0:
                time.sleep(spare)


        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception as e:                      # noqa: BLE001
            trouble += 1
            print("\n>> CYCLE %d FAILED (%s). Waiting %ds, then looking"
                  " again. This is failure %d in a row."
                  % (cycle, safe_error(e), wait, trouble))
            traceback.print_exc()
            if args.once:
                return 1          # a crash, not a misconfiguration
            time.sleep(wait)
            wait = min(wait * 2, RETRY_CEILING)
            continue
        trouble, wait = 0, RETRY_SECONDS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n>> stopped by hand. Nothing is watching the rooms now.")
        sys.exit(0)
    finally:
        # Hand the sleep timer back. Leaving a machine unable to sleep
        # because a loop exited badly is somebody else's problem later.
        stay_awake(False)
