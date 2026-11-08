"""Check the room state machine without touching a recorder.

This exists because of one specific failure. The single-room system once sent
an alert saying a room was empty while two people were in the snapshot attached
to it. Multiplying that across thirty rooms multiplies the ways it can happen:
a camera that does not answer, a room watched by two cameras where only one
replies, a restart after an hour of downtime.

Every case below is one of those. Run it after changing anything in Room:

    python test_room_loop.py
"""
import datetime
import sys
import types

for name, module in (
        # Enough of OpenCV for the state machine and the evidence catcher.
        # imwrite really writes, because "did it save the frame" is one of
        # the things worth checking and a stub that lies about it would let
        # that break unnoticed.
        ("cv2", types.SimpleNamespace(
            resize=lambda *a, **k: None, INTER_LINEAR=1,
            FONT_HERSHEY_SIMPLEX=0,
            rectangle=lambda *a, **k: None, putText=lambda *a, **k: None,
            imwrite=lambda path, img: open(path, "wb").write(b"\xff\xd8") > 0)),
        ("dotenv", types.SimpleNamespace(load_dotenv=lambda: None)),
        # Stubbed so the state machine can be checked anywhere, including on a
        # machine with no database driver installed. Nothing here touches it.
        ("psycopg2", types.SimpleNamespace(Error=Exception, connect=None)),
        ("privacy_blur", types.SimpleNamespace(count_people=lambda *a, **k: 0,
                                               people_boxes=lambda *a, **k: [],
                                               anonymize=lambda f, m: f)),
        ("test_camera", types.SimpleNamespace(build_url=lambda *a, **k: "",
                                              grab=lambda *a, **k: (None, "")))):
    sys.modules.setdefault(name, module)

import room_loop  # noqa: E402
from room_loop import PKT, Room  # noqa: E402

T0 = datetime.datetime(2026, 11, 5, 18, 0, tzinfo=PKT)
FAILURES = []


def at(minutes):
    return T0 + datetime.timedelta(minutes=minutes)


def room(**overrides):
    cfg = dict(name="Marketing", recorder="dvr2", channels=[3, 13],
               ac="visible", empty_after_minutes=45)
    cfg.update(overrides)
    return Room(cfg)


def check(label, got, want):
    ok = got == want
    print("%-4s %s" % ("OK" if ok else "FAIL", label))
    if not ok:
        FAILURES.append("%s: got %r, wanted %r" % (label, got, want))


def main():
    # Seeing a person settles it. One camera is enough to prove occupancy.
    r = room()
    r.observe(people=1, answered=1, now=T0)
    check("a person on one of two cameras means occupied", r.status, "occupied")

    # Seeing nobody settles nothing unless every camera looked.
    r = room()
    r.observe(0, 1, T0)
    check("nobody, on one camera of two, is not empty", r.status, "unknown")
    check("  and starts no empty clock", r.empty_since, None)

    r = room()
    r.observe(0, 2, T0)
    check("nobody, on both cameras, is empty", r.status, "empty")
    check("  and starts the clock", r.empty_since, T0)
    r.observe(0, 2, at(44))
    check("44 minutes is not yet 45", r.due_for_check(at(44)), False)
    r.observe(0, 2, at(46))
    check("46 minutes is", r.due_for_check(at(46)), True)

    # A camera dropping out mid-count must stop the clock, not freeze it.
    r = room()
    r.observe(0, 2, T0)
    r.observe(0, 1, at(20))
    check("a camera dropping out clears the clock", r.empty_since, None)
    r.observe(0, 2, at(21))
    check("  and the clock restarts when it returns", r.empty_since, at(21))
    check("  so no alert inherits the earlier minutes",
          r.due_for_check(at(30)), False)

    r = room()
    r.observe(0, 2, T0)
    r.observe(2, 2, at(30))
    check("somebody walking in clears the clock", r.empty_since, None)

    r = room()
    r.observe(0, 2, T0)
    r.observe(0, 0, at(10))
    check("a recorder going away leaves the room unknown", r.status, "unknown")
    check("  with no clock running", r.empty_since, None)

    # The server rooms are cooled on purpose and are empty nearly always.
    r = room(name="UPS Room", channels=[5], alert="never",
             empty_after_minutes=None)
    r.observe(0, 1, T0)
    r.observe(0, 1, at(600))
    check("ten hours empty never makes a server room due",
          r.due_for_check(at(600)), False)

    r = room(name="Cafe Stairs", channels=[1], ac="none",
             empty_after_minutes=None)
    r.observe(0, 1, T0)
    check("a room with no unit is never due", r.due_for_check(at(600)), False)
    check("  but is still counted", r.status, "empty")

    # Operating hours. A room empty for half an hour in the afternoon has
    # somebody in a meeting; the same room empty for half an hour at midnight
    # has nobody coming back, and should not wait the same forty-five minutes.
    afternoon = datetime.datetime(2026, 11, 5, 14, 0, tzinfo=PKT)   # Thursday
    night = datetime.datetime(2026, 11, 5, 23, 30, tzinfo=PKT)
    saturday = datetime.datetime(2026, 11, 7, 14, 0, tzinfo=PKT)
    for label, start in (("a weekday afternoon", afternoon),
                         ("a weekday night", night),
                         ("a Saturday afternoon", saturday)):
        r = room()
        r.observe(0, 2, start)
        r.observe(0, 2, start + datetime.timedelta(minutes=20))
        due = r.due_for_check(start + datetime.timedelta(minutes=20))
        check("20 min empty on %s%s" % (label,
                                        " is due" if due else " is not due"),
              due, label != "a weekday afternoon")

    # The air conditioner. Four states matter, not two: the alert the whole
    # system exists to send is "empty AND still running", and a room that is
    # empty with its unit already off is the outcome we want, not a fault.
    r = room()
    r.observe(0, 2, T0, "off", "1 unit(s) read")
    r.observe(0, 2, at(60), "off", "1 unit(s) read")
    check("empty an hour with the unit off is not due",
          r.due_for_check(at(60)), False)

    r = room()
    r.observe(0, 2, T0, "on", "1 unit(s) read")
    r.observe(0, 2, at(60), "on", "1 unit(s) read")
    check("empty an hour with the unit running is due",
          r.due_for_check(at(60)), True)

    r = room()
    r.observe(0, 2, T0, None, "not calibrated")
    r.observe(0, 2, at(60), None, "not calibrated")
    check("empty an hour with the unit unread is still due",
          r.due_for_check(at(60)), True)

    r = room()
    r.observe(3, 2, T0, "on", "1 unit(s) read")
    check("somebody in the room with the unit on is never due",
          r.due_for_check(at(0)), False)

    # A unit coming on in a room that is already empty has to be written down.
    # If state carried occupancy alone, that moment -- the moment the waste
    # begins -- would look like no change at all and never reach the database.
    r = room()
    r.observe(0, 2, T0, "off", "1 unit(s) read")
    before = r.state()
    r.observe(0, 2, at(5), "on", "1 unit(s) read")
    check("the unit switching on in an empty room is a change",
          r.state() != before, True)

    r = room()
    r.observe(0, 2, T0, "off", "1 unit(s) read")
    before = r.state()
    r.observe(0, 2, at(5), "off", "1 unit(s) read")
    check("nothing changing is not a change", r.state(), before)

    # A calibration pointing at a channel the room does not have would never be
    # read, and a room whose unit is never read looks exactly like a room
    # nobody has calibrated. So it is caught at startup instead.
    from room_loop import check_ac_units
    rooms = [room(name="Admin Room", recorder="dvr2", channels=[9])]
    check("a calibration on a channel the room has is counted",
          check_ac_units({"Admin Room": {"recorder": "dvr2", "channel": 9}},
                         rooms), 1)
    for label, bad in (
            ("a channel the room does not have",
             {"Admin Room": {"recorder": "dvr2", "channel": 11}}),
            ("no channel at all", {"Admin Room": {"recorder": "dvr2"}}),
            ("the wrong recorder",
             {"Admin Room": {"recorder": "nvr4", "channel": 9}})):
        try:
            check_ac_units(bad, rooms)
            check("%s is refused" % label, "accepted", "refused")
        except SystemExit:
            check("%s is refused" % label, "refused", "refused")
    check("a calibrated room not in this run is ignored",
          check_ac_units({"Somewhere Else": {"recorder": "nvr1", "channel": 4}},
                         rooms), 0)

    # Ignore zones. A camera that sees a person in a poster, a mannequin or a
    # reflection reports that room occupied for ever, and the room quietly
    # stops being watched for waste. The cure must not be worse: a real person
    # standing in front of the same poster still has to be counted.
    poster = [100, 100, 200, 300]
    check("a box sitting exactly on the poster is ignored",
          room_loop.ignored((100, 100, 200, 300, 0.4), [poster]), True)
    check("a box well inside it is ignored",
          room_loop.ignored((120, 140, 180, 260, 0.4), [poster]), True)
    check("a person standing in front of it is not",
          room_loop.ignored((90, 60, 210, 420, 0.8), [poster]), False)
    check("somebody elsewhere in the room is not",
          room_loop.ignored((600, 100, 700, 300, 0.9), [poster]), False)
    check("a room with no zones ignores nothing",
          room_loop.ignored((100, 100, 200, 300, 0.4), None), False)
    check("a box with no area is not ignored",
          room_loop.ignored((100, 100, 100, 100, 0.4), [poster]), False)
    check("half in, half out is kept",
          room_loop.ignored((100, 100, 300, 300, 0.4), [poster]), False)

    # And the same rule where it actually runs.
    seen = []

    def fake_boxes(frame, model, conf=None, imgsz=None, iou=None):
        seen.append(conf)
        return [(100, 100, 200, 300, 0.4),      # the poster
                (600, 100, 700, 300, 0.9)]      # a real person

    real = room_loop.people_boxes
    room_loop.people_boxes = fake_boxes
    try:
        r = room(channels=[10], ignore={10: [poster]})
        people, answered, _, _, _ = room_loop.examine(
            r, {("dvr2", 10): "frame"}, model=None, imgsz=1280, iou=0.7)
        check("the poster is not counted, the person is", people, 1)
        check("and the camera still counts as having answered", answered, 1)

        plain = room(channels=[10])
        people, _, _, _, _ = room_loop.examine(
            plain, {("dvr2", 10): "frame"}, model=None, imgsz=1280, iou=0.7)
        check("without a zone both are counted", people, 2)

        # A room's own confidence has to reach the detector, or setting it
        # does nothing at all and the room goes on miscounting.
        seen[:] = []
        strict = room(channels=[10], conf=0.55)
        room_loop.examine(strict, {("dvr2", 10): "frame"}, model=None,
                          imgsz=1280, iou=0.7)
        check("a room's own confidence reaches the detector", seen, [0.55])

        seen[:] = []
        room_loop.examine(plain, {("dvr2", 10): "frame"}, model=None,
                          imgsz=1280, iou=0.7)
        check("and a room without one leaves it alone", seen, [None])

        # A camera that did not answer must not be counted as having answered
        # with nobody in it -- that is the reading that empties a room nobody
        # looked at.
        people, answered, _, _, _ = room_loop.examine(
            room(channels=[10, 14]),
            {("dvr2", 10): "frame", ("dvr2", 14): None}, model=None,
            imgsz=1280, iou=0.7)
        check("a camera that sent nothing does not answer", answered, 1)

        # A place two recorders can see. Before this it had to be two rooms,
        # and two rooms meant one could call itself empty for forty-five
        # minutes while the other watched somebody sitting in it. That is
        # exactly what nvr1 ch22 and xvr3 ch16 were doing at 140-H: the same
        # lobby, the same person, and only one of them saw him.
        lobby = Room(dict(name="H First Floor Lobby", ac="visible",
                          empty_after_minutes=45,
                          cameras=[{"recorder": "nvr1", "channel": 22},
                                   {"recorder": "xvr3", "channel": 16}]))
        check("both cameras belong to the room", lobby.cameras,
              [("nvr1", 22), ("xvr3", 16)])
        check("and it is filed under the first", lobby.recorder, "nvr1")

        room_loop.people_boxes = lambda f, m, **k: (
            [(600, 100, 700, 300, 0.9)] if f == "has him" else [])
        people, answered, _, _, _ = room_loop.examine(
            lobby, {("nvr1", 22): "has him", ("xvr3", 16): "empty"},
            model=None, imgsz=1280, iou=0.7)
        check("one camera seeing him is enough", people, 1)
        check("and both answered", answered, 2)

        lobby.observe(people, answered, T0)
        check("so the room is occupied, not empty", lobby.status, "occupied")

        # And the other half of the asymmetry still holds across recorders.
        lobby.observe(0, 1, T0)
        check("one of two recorders answering cannot prove it empty",
              lobby.status, "unknown")
        lobby.observe(0, 2, T0)
        check("both answering can", lobby.status, "empty")

        # An ignore zone on a shared room has to say which recorder.
        split = Room(dict(name="Split", ac="none",
                          cameras=[{"recorder": "nvr1", "channel": 16},
                                   {"recorder": "xvr3", "channel": 16}],
                          ignore={"xvr3:16": [poster]}))
        check("a zone written xvr3:16 lands on xvr3",
              list(split.ignore), [("xvr3", 16)])
    finally:
        room_loop.people_boxes = real

    # Speed, because "live" is a claim and claims get checked. Waiting on
    # ninety-six cameras one at a time is what put the dashboard minutes
    # behind; this is the fix, so it has to be shown to work rather than
    # asserted in a commit message.
    import threading
    import time

    import numpy as np

    stub_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    live = {"now": 0, "most": 0}
    guard = threading.Lock()

    def slow_grab(url, **kw):
        with guard:
            live["now"] += 1
            live["most"] = max(live["most"], live["now"])
        time.sleep(0.2)
        with guard:
            live["now"] -= 1
        return stub_frame, "ok"

    real_grab = room_loop.grab
    room_loop.grab = slow_grab
    try:
        many = [room(name="Room %d" % i, channels=[i]) for i in range(12)]
        recs = {"dvr2": {"host": "x", "user": "u", "password": "p"}}

        started = time.time()
        one = room_loop.sweep(many, recs, None, 1280, 0.7, 5.0, None,
                              workers=1)
        serial = time.time() - started

        started = time.time()
        eight = room_loop.sweep(many, recs, None, 1280, 0.7, 5.0, None,
                                workers=8)
        parallel = time.time() - started

        check("every room is read either way",
              (len(one), len(eight)), (12, 12))
        check("and reads the same", one, eight)
        check("eight at a time beats one at a time by more than half"
              " (%.1fs vs %.1fs)" % (serial, parallel),
              parallel < serial / 2, True)

        # The cap is the careful half. A recorder will only serve so many
        # streams at once, and asking for more is how a machine starts
        # refusing this one altogether -- which already happened once.
        live["most"] = 0
        capped = {"dvr2": dict(recs["dvr2"], gate=threading.Semaphore(2))}
        room_loop.sweep(many, capped, None, 1280, 0.7, 5.0, None, workers=8)
        check("never more than 2 streams open on a capped recorder",
              live["most"] <= 2, True)

        # A camera that throws must not take the other sixty-two with it.
        def angry_grab(url, **kw):
            raise RuntimeError("recorder said no")

        room_loop.grab = angry_grab
        out = room_loop.sweep(many, recs, None, 1280, 0.7, 5.0, None,
                              workers=4)
        check("a recorder refusing still returns every room", len(out), 12)
        check("and each reads as nobody having answered",
              {people for people, answered, _, _ in out.values()}
              | {answered for _, answered, _, _ in out.values()}, {0})
    finally:
        room_loop.grab = real_grab

    # The evidence catcher. Its whole point is that it stays quiet while
    # people are in the building and only speaks outside working hours, so
    # that is the part worth checking -- a catcher that fired all day would
    # bury the one frame that mattered under a thousand that did not.
    import os
    import tempfile

    import numpy as np

    shot = np.zeros((120, 200, 3), dtype=np.uint8)
    room_loop.people_boxes = lambda f, m, **k: [(10, 10, 60, 100, 0.33)]
    folder = tempfile.mkdtemp()
    try:
        night = datetime.datetime(2026, 11, 5, 23, 30, tzinfo=PKT)
        got = room_loop.keep_evidence(room(channels=[10]),
                                      {("dvr2", 10): shot}, None, 1280, 0.7,
                                      folder, night)
        check("a counted person at night is written down", len(got), 1)
        check("and the file is really there",
              os.path.exists(os.path.join(folder, got[0])), True)
        check("named so the room and the moment are both in it",
              got[0].startswith("Marketing_dvr2_ch10_20261105_2330"), True)

        # A detection the room already knows about is not evidence of
        # anything -- that is the zone doing its job.
        quiet = room(channels=[10], ignore={10: [[5, 5, 70, 110]]})
        check("a filtered detection is not written down",
              room_loop.keep_evidence(quiet, {("dvr2", 10): shot}, None, 1280,
                                      0.7, folder, night), [])

        room_loop.people_boxes = lambda f, m, **k: []
        check("nor is a camera that saw nobody",
              room_loop.keep_evidence(room(channels=[10]),
                                      {("dvr2", 10): shot}, None, 1280, 0.7,
                                      folder, night), [])
    finally:
        room_loop.people_boxes = real

    # The evidence folder only grows unless something takes things out of
    # it, and what it holds are unblurred pictures of the building.
    # Its own folder: the one above already has a frame in it, and counting
    # against a folder somebody else wrote to proves nothing.
    folder = tempfile.mkdtemp()
    old = time.time() - 40 * 86400
    for n in range(6):
        p = os.path.join(folder, "old_%d.jpg" % n)
        open(p, "wb").write(b"x")
        os.utime(p, (old, old))
    for n in range(4):
        open(os.path.join(folder, "new_%d.jpg" % n), "wb").write(b"x")
    gone = room_loop.prune_evidence(folder, keep=100, days=21)
    left = sorted(f for f in os.listdir(folder) if f.endswith(".jpg"))
    check("everything older than three weeks goes", gone, 6)
    check("and nothing recent does", len(left), 4)

    # And a camera gone wrong, writing all night, is capped by count.
    for n in range(30):
        open(os.path.join(folder, "flood_%02d.jpg" % n), "wb").write(b"x")
    room_loop.prune_evidence(folder, keep=12, days=365)
    check("a flood is capped at the count",
          len([f for f in os.listdir(folder) if f.endswith(".jpg")]), 12)
    check("pruning a folder that is not there does not raise",
          room_loop.prune_evidence(os.path.join(folder, "nope")), 0)

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
