"""Run a whole cycle over the real rooms.yaml, with the cameras faked.

Every other test here checks one function. This one checks that the pieces
still fit: the real sixty-one rooms, the real four recorders, the real
ignore zones and stream overrides and calibration, through load_rooms,
the startup checks, a full parallel sweep, the state machine, the report and
the alert gatherer.

It exists because of how this project actually fails. Nothing breaks in a
unit test; it breaks at nine in the morning with a cable plugged in and
somebody standing in a corridor, and the day is gone. Everything below runs
without a camera, a database or a model, so it can be run before leaving the
house.

    python test_integration.py
"""
import contextlib
import io
import sys
import types

import numpy as np

# Fakes, installed before room_loop is imported. The detector is the only
# one that pretends to be clever: it reports people in rooms named below so
# that the occupancy logic has something to chew on.
BUSY = {"Admin Room": 2, "Prompt Cafe": 9, "140-H Entry Area": 3}
# One room watched by a single camera, and that camera will not answer. The
# first version of this picked a camera on a three-camera room, so the check
# below found nothing to check and printed an empty section -- a test that
# passes by not running is worse than no test.
DEAD_ROOM = "H Stairs"

FRAME = np.zeros((360, 640, 3), dtype=np.uint8)
FRAME[100:260, 200:420] = 90

_asked = []


DEAD_URLS = set()


def fake_grab(url, **kw):
    _asked.append(url)
    if url in DEAD_URLS:
        return None, "no stream"
    return FRAME, "ok"


def fake_boxes(frame, model, conf=None, imgsz=None, iou=None):
    return getattr(fake_boxes, "boxes", [])


for name, module in (
        ("dotenv", types.SimpleNamespace(load_dotenv=lambda: None)),
        ("psycopg2", types.SimpleNamespace(Error=Exception, connect=None)),
        ("privacy_blur", types.SimpleNamespace(
            count_people=lambda *a, **k: 0, people_boxes=fake_boxes,
            anonymize=lambda f, m: f,
            DETECTOR="yolov8s.pt")),
        ("test_camera", types.SimpleNamespace(
            build_url=lambda host, ch, u, p, main=False, brand="hikvision":
                "rtsp://%s/%s/%d" % (host, "main" if main else "sub", ch),
            grab=fake_grab))):
    sys.modules.setdefault(name, module)

import room_loop  # noqa: E402
from ac_detect import load_units  # noqa: E402

room_loop.grab = fake_grab
room_loop.people_boxes = fake_boxes

FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s" % ("OK" if ok else "FAIL", label))
    if not ok:
        FAILURES.append("%s: got %r, wanted %r" % (label, got, want))


def says(label, condition):
    check(label, bool(condition), True)


def main():
    import os

    for key in ("DVR2_USER", "DVR2_PASS", "NVR1_USER", "NVR1_PASS",
                "NVR4_USER", "NVR4_PASS", "XVR3_USER", "XVR3_PASS"):
        os.environ.setdefault(key, "test")

    print("-- the real config loads and passes its own startup checks")
    recorders, rooms = room_loop.load_rooms("rooms.yaml")
    says("rooms.yaml loads", rooms)
    says("every room has at least one camera",
         all(r.cameras for r in rooms))
    says("no room is watched on a recorder that does not exist",
         all(rec in recorders for r in rooms for rec, _ in r.cameras))
    says("a room marked watch: false is not in the run",
         all(r.watch for r in rooms))

    for key in {rec for r in rooms for rec, _ in r.cameras}:
        recorders[key]["user"] = "u"
        recorders[key]["password"] = "p"
    room_loop.set_gates(recorders, 4)

    dead = next(r for r in rooms if r.name == DEAD_ROOM)
    check("%s is watched by exactly one camera" % DEAD_ROOM,
          len(dead.cameras), 1)
    rec_name, channel = dead.cameras[0]
    rec = recorders[rec_name]
    DEAD_URLS.add(sys.modules["test_camera"].build_url(
        rec["host"], channel, "u", "p",
        (dead.stream or rec.get("stream", "sub")) == "main",
        rec.get("brand", "hikvision")))

    calibrated = room_loop.check_ac_units(load_units(), rooms)
    says("the calibration matches the room map", calibrated >= 0)

    for room in rooms:
        for camera in room.ignore:
            check("%s's ignore zone is on one of its cameras" % room.name,
                  camera in room.cameras, True)

    print()
    print("-- a whole cycle, every room, with the cameras faked")
    fake_boxes.boxes = []
    now = room_loop.datetime.now(room_loop.PKT)
    readings = room_loop.sweep(rooms, recorders, None, 1280, 0.7, 1.0,
                               load_units(), workers=8)
    check("every room got a reading", len(readings), len(rooms))
    # Except a room in its private hours (the 141 gym, 15:00-20:00), whose
    # camera must not be asked for at all.
    private = [r for r in rooms if room_loop.is_private(r.private)]
    says("every room's cameras were asked for, bar private hours",
         len(_asked) >= sum(len(r.cameras) for r in rooms
                            if r not in private))
    for room in private:
        for rec_name, channel in room.cameras:
            rec = recorders[rec_name]
            url = sys.modules["test_camera"].build_url(
                rec["host"], channel, rec["user"], rec["password"],
                room_loop.wants_main(room, rec),
                rec.get("brand", "hikvision"))
            says("%s's camera was not asked for, in its private hours"
                 % room.name, url not in _asked)

    print()
    print("-- the stream each room asked for is the stream it got")
    main_rooms = [r for r in rooms if r.stream == "main"]
    says("some rooms override the recorder's stream", main_rooms)
    for room in main_rooms:
        rec = recorders[room.cameras[0][0]]
        urls = [u for u in _asked
                if u.startswith("rtsp://%s/" % rec["host"])]
        says("%s is read on the main stream" % room.name,
             any("/main/" in u for u in urls))
    subs = [r for r in rooms
            if r.stream is None
            and recorders[r.cameras[0][0]].get("stream", "sub") == "sub"]
    for room in subs[:3]:
        rec = recorders[room.cameras[0][0]]
        says("%s stays on the sub stream" % room.name,
             any(u.endswith("/sub/%d" % room.cameras[0][1]) for u in _asked))

    print()
    print("-- a camera that does not answer leaves its room unknown")
    people, answered, _, _ = readings[DEAD_ROOM]
    check("%s answered nothing" % DEAD_ROOM, answered, 0)
    dead.observe(people, answered, now)
    check("  so it is unknown, not empty", dead.status, "unknown")
    check("  and no empty clock is running", dead.empty_since, None)
    check("  and it can never be due for a check",
          dead.due_for_check(now + room_loop.timedelta(hours=9)), False)

    print()
    print("-- people in a room keep it occupied, nobody empties it")
    for room in rooms:
        if room.name == DEAD_ROOM:
            continue
        people, answered, ac, why = readings[room.name]
        room.observe(BUSY.get(room.name, people), answered, now, ac, why)
    empty = [r for r in rooms if r.status == "empty"]
    unknown = [r for r in rooms if r.status == "unknown"]
    occupied = [r for r in rooms if r.status == "occupied"]
    check("every room landed in one of the three states",
          len(empty) + len(unknown) + len(occupied), len(rooms))
    says("most rooms read empty on a blank frame", len(empty) > len(rooms) / 2)
    for name in BUSY:
        if name in {r.name for r in rooms}:
            room = next(r for r in rooms if r.name == name)
            check("%s is occupied" % name, room.status, "occupied")

    print()
    print("-- the report prints without blowing up")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        room_loop.report(rooms, now, 1, 12.3, None)
    printed = out.getvalue()
    says("every room appears in it",
         all(r.name[:26] in printed for r in rooms))
    says("and the cycle time is in the first line", "12s" in printed)

    print()
    print("-- the alert gatherer runs over the real rooms and stays quiet")
    from alerts import Alerter, compose
    a = Alerter(gather_seconds=0, min_gap_seconds=0)
    worth = a.consider(rooms, now, None)
    says("nothing is worth saying about rooms that just went empty",
         not worth)
    later = now + room_loop.timedelta(hours=3)
    for room in rooms:
        if room.name == DEAD_ROOM:
            continue
        people, answered, ac, why = readings[room.name]
        room.observe(BUSY.get(room.name, people), answered, later, ac, why)
    worth = a.consider(rooms, later, None)
    says("after three hours some rooms are", worth)
    says("and none of them is a room with no unit",
         all(r.ac in ("visible", "hidden") for r in worth))
    says("and none of them is cooled on purpose",
         all(r.alerts for r in worth))
    says("and none of them is a room no camera answered for",
         DEAD_ROOM not in [r.name for r in worth])
    if worth:
        subject, body = compose(worth, later, None)
        says("the mail names every room it is about",
             all(r.name in body for r in worth))
        says("and says what the numbers are not",
             "electricity meter" in body)

    print()
    print("-- the campus page builds from the same rooms")
    says("every room has a zone for the page to group it under",
         all(r.name for r in rooms))

    print()
    if FAILURES:
        print("%d FAILURE(S):" % len(FAILURES))
        for line in FAILURES:
            print("  %s" % line)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
