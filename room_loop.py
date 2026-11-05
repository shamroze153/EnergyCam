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
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

# Joining a stream part way through means ffmpeg decodes a few frames against a
# reference it never received, and it says so on stderr every single time. Those
# are the frames grab() is deliberately throwing away, so the complaints are
# correct and useless: on a pass over forty-eight cameras they ran to roughly
# five times the length of the output anyone wanted to read, which is its own
# kind of failure -- a report nobody scrolls back through is a report nobody
# reads. Set OPENCV_FFMPEG_LOGLEVEL yourself to see them again when diagnosing.
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")

import cv2  # noqa: E402  (must follow the env var above)
import yaml
from dotenv import load_dotenv

from privacy_blur import count_people
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

    def due_for_check(self, now):
        if not self.watched_for_waste or not self.empty_after:
            return False
        return self.empty_minutes(now) >= self.empty_after


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
    """Take one frame from each of a room's cameras. Returns (people, answered)."""
    people, answered = 0, 0
    want_main = rec.get("stream", "sub") == "main"
    for channel in room.channels:
        url = build_url(rec["host"], channel, rec["user"], rec["password"],
                        want_main, rec.get("brand", "hikvision"))
        frame, _ = grab(url, max_seconds=timeout)
        if frame is None:
            continue
        answered += 1
        people = max(people, count_people(widen(frame), model,
                                          imgsz=imgsz, iou=iou))
    return people, answered


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


def report(rooms, now, cycle, seconds):
    print("\n>> cycle %d  %s  (%.0fs)"
          % (cycle, now.strftime("%H:%M:%S"), seconds))
    for room in sorted(rooms, key=lambda r: (r.status != "unknown", r.name)):
        flag = "  "
        if room.due_for_check(now):
            flag = "!!"
        elif room.status == "unknown":
            flag = " ?"
        print("   %s %-9s %-26s %s"
              % (flag, room.status, room.name[:26], room.detail))
    due = [r for r in rooms if r.due_for_check(now)]
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
    args = ap.parse_args()

    load_dotenv()
    recorders, rooms = load_rooms(args.config, args.recorder, args.room)

    used = {r.recorder for r in rooms}
    for key in used:
        if key not in recorders:
            sys.exit("rooms.yaml has rooms on recorder %r but no such recorder"
                     % key)
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password

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
    while True:
        cycle += 1
        started = time.time()
        for room in rooms:
            now = datetime.now(PKT)
            people, answered = sample(room, recorders[room.recorder], model,
                                      args.imgsz, args.iou, args.timeout)
            room.observe(people, answered, now)
        now = datetime.now(PKT)
        elapsed = time.time() - started
        report(rooms, now, cycle, elapsed)
        save_state(rooms, args.state, now)

        if args.once:
            return
        spare = args.min_cycle - elapsed
        if spare > 0:
            time.sleep(spare)


if __name__ == "__main__":
    main()
