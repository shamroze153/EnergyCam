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
            imwrite=lambda path, img, *params:
                open(path, "wb").write(b"\xff\xd8") > 0)),
        ("dotenv", types.SimpleNamespace(load_dotenv=lambda: None)),
        # Stubbed so the state machine can be checked anywhere, including on a
        # machine with no database driver installed. Nothing here touches it.
        ("psycopg2", types.SimpleNamespace(Error=Exception, connect=None)),
        ("privacy_blur", types.SimpleNamespace(count_people=lambda *a, **k: 0,
                                               people_boxes=lambda *a, **k: [],
                                               anonymize=lambda f, m: f,
            DETECTOR="yolov8s.pt")),
        ("test_camera", types.SimpleNamespace(build_url=lambda *a, **k: "",
                                              grab=lambda *a, **k: (None, "")))):
    sys.modules.setdefault(name, module)

import room_loop  # noqa: E402
from room_loop import PKT, Room  # noqa: E402
import tempfile as _seat_tmp  # noqa: E402

# The stand-in people these tests count must not land in the real seat notes.
room_loop.SEATS_DIR = _seat_tmp.mkdtemp()
room_loop.AC_KEEP_DIR = _seat_tmp.mkdtemp()
room_loop.STILL_FILE = _seat_tmp.mktemp(suffix=".json")

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



# ---------------------------------------------------------------- staying up

def check_flicker(check, room, T0):
    """A detector that finds somebody in half the frames must not flip a room.

    Watched live, Admin Room scored a seated person at 0.40, 0.46, 0.53,
    0.31 and 0.54, with nothing at all on four frames in between, over
    ninety seconds, while he sat still. One blank frame used to be enough
    to call the room empty, so the room flipped every few minutes: the
    live view wrong half the time, and first-seen and last-seen reduced to
    the first and last coin toss.
    """
    import datetime as dt

    def later(minutes):
        return T0 + dt.timedelta(minutes=minutes)

    # Seen, then one blank pass: still occupied, and saying why.
    r = room()
    r.observe(people=1, answered=2, now=T0)
    r.observe(people=0, answered=2, now=later(2))
    check("one blank pass does not empty an occupied room", r.status,
          "occupied")
    check("and the room says it is holding", "holding" in r.detail, True)
    check("no empty clock has started", r.empty_since, None)

    # A second blank confirms it.
    r.observe(people=0, answered=2, now=later(4))
    check("a second blank pass does", r.status, "empty")

    # ...and the clock is backdated to the first blank, so nothing is lost.
    check("the empty clock runs from the first blank, not the second",
          r.empty_since, later(2))
    check("so the room is already 2 minutes empty, not 0",
          round(r.empty_minutes(later(4))), 2)

    # Somebody reappearing in between resets it: this is the flicker.
    r = room()
    r.observe(people=1, answered=2, now=T0)
    for minute in (2, 6, 10):
        r.observe(people=0, answered=2, now=later(minute))
        check("blank at %d min holds" % minute, r.status, "occupied")
        r.observe(people=1, answered=2, now=later(minute + 2))
        check("and the person at %d min keeps it occupied" % (minute + 2),
              r.status, "occupied")
    check("ninety seconds of flicker never calls the room empty",
          r.empty_since, None)

    # Somebody being seen must also end the previous run of blanks. Leaving
    # it in place dates the next spell of emptiness from the one before it:
    # the room reads as empty for hours, the alerter takes it for the same
    # episode it has already mentioned, and nobody is ever told.
    r = room()
    r.observe(people=0, answered=2, now=T0)
    check("empty from the start", r.empty_since, T0)
    r.observe(people=2, answered=2, now=later(60))
    r.observe(people=0, answered=2, now=later(62))
    r.observe(people=0, answered=2, now=later(64))
    check("the new empty spell is dated from after they left",
          r.empty_since, later(62))
    check("not from the spell before it",
          r.empty_minutes(later(64)), 2.0)

    # A room that really is empty still gets there, and promptly.
    r = room()
    r.observe(people=0, answered=2, now=T0)
    check("a room not previously occupied is empty at once", r.status,
          "empty")
    check("and dated from that first pass", r.empty_since, T0)

    # A camera dropping out mid-hold says nothing either way. It must not
    # count towards empty, and it must not undo the hold -- a camera
    # blinking once would otherwise empty a room somebody is sitting in.
    r = room()
    r.observe(people=1, answered=2, now=T0)
    r.observe(people=0, answered=1, now=later(2))
    check("a half-answered pass is unknown", r.status, "unknown")
    r.observe(people=0, answered=2, now=later(4))
    check("and it did not count as a blank, so one blank still holds",
          r.status, "occupied")
    r.observe(people=0, answered=2, now=later(6))
    check("the second real blank empties it", r.status, "empty")

    # The same, with no camera answering at all.
    r = room()
    r.observe(people=1, answered=2, now=T0)
    r.observe(people=0, answered=2, now=later(2))
    r.observe(people=0, answered=0, now=later(4))
    check("no camera answering reads as unknown", r.status, "unknown")
    r.observe(people=0, answered=2, now=later(6))
    check("and the hold survived it, so this is the second blank",
          r.status, "empty")


def check_one_stream_rule(check):
    """Everything that grabs a frame must grab the one the loop reads.

    tune_detect and calibrate_room --live chose the stream from the
    recorder alone and ignored the room's own `stream: main`. A room the
    loop reads at 2560x1440 was then calibrated on 640x360, and the loop
    refused every reading from it for ever as a size mismatch -- a
    calibration that looks finished and can never be used. tune_detect
    also fetched a cross-recorder room's second camera from its first
    recorder, so "H First Floor Lobby ch16" came back as Reception.
    """
    import glob
    import re
    import types

    room = types.SimpleNamespace(stream="main")
    check("a room's own main stream wins over a sub-stream recorder",
          room_loop.wants_main(room, {"stream": "sub"}), True)
    room = types.SimpleNamespace(stream=None)
    check("with no room setting the recorder decides",
          room_loop.wants_main(room, {"stream": "main"}), True)
    check("and the default is the sub-stream",
          room_loop.wants_main(room, {}), False)

    offenders = []
    for path in glob.glob("*.py"):
        if path.startswith("test_"):
            continue
        text = open(path, encoding="utf-8").read()
        # Reading the recorder's stream setting is the decision; reading a
        # room's own setting into room.stream is just loading config.
        body = text.split("def wants_main(")[0] + \
            text.split("def wants_main(")[-1].split("\ndef ", 1)[-1] \
            if "def wants_main(" in text else text
        if re.search(r'rec(?:orders\[[^]]+\])?\.get\("stream"', body):
            offenders.append(path)
    check("no file decides the stream for itself", offenders, [])

    tune = open("tune_detect.py", encoding="utf-8").read()
    check("tune_detect walks every camera, recorder included",
          "for rec_name, channel in room.cameras" in tune, True)


def check_evidence_keeps_the_night(check):
    """The night's pictures must survive the morning.

    On 11 Nov the evidence folder held nothing from the night. Opening is
    10:00, so 09:15 counted as after hours; everybody arriving was
    photographed every two minutes on every camera, the 400-picture cap
    filled in three quarters of an hour, and the night -- the only part
    anybody wanted -- was pruned to make room.
    """
    import datetime as dt
    from schedule import PKT

    hours = {"operations": {"days": ["mon", "tue", "wed", "thu", "fri"],
                            "start": "10:00", "end": "20:00"}}
    def at(h, m=0, day=11):                       # 11 Nov 2026 is a Wednesday
        return dt.datetime(2026, 11, day, h, m, tzinfo=PKT)

    worthy = room_loop.evidence_worthy
    check("three in the morning is worth a picture", worthy(at(3), hours), True)
    check("half past nine is people arriving", worthy(at(9, 30), hours), False)
    check("so is nine o'clock", worthy(at(9, 0), hours), False)
    check("ten to nine is still the night", worthy(at(8, 50), hours), True)
    check("half past eight in the evening is people leaving",
          worthy(at(20, 30), hours), False)
    check("ten past nine at night is the night again",
          worthy(at(21, 10), hours), True)
    check("working hours never are", worthy(at(14), hours), False)
    check("a Saturday afternoon is", worthy(at(15, day=14), hours), True)

    # One picture per camera per EVIDENCE_EVERY, so one stuck camera cannot
    # evict every other camera's night.
    import tempfile
    import types
    import numpy as np

    folder = tempfile.mkdtemp()
    room_loop._last_evidence.clear()
    fake_room = types.SimpleNamespace(name="Lobby", cameras=[("dvr2", 12)],
                                      conf=None, ignore={})
    frame = np.zeros((1080, 1920, 3), np.uint8)
    saved_boxes = room_loop.people_boxes
    room_loop.people_boxes = lambda *a, **k: [(10, 10, 60, 160, 0.9)]
    try:
        first = room_loop.keep_evidence(fake_room, {("dvr2", 12): frame},
                                        None, 1280, 0.7, folder, at(3, 0))
        again = room_loop.keep_evidence(fake_room, {("dvr2", 12): frame},
                                        None, 1280, 0.7, folder, at(3, 2))
        later = room_loop.keep_evidence(fake_room, {("dvr2", 12): frame},
                                        None, 1280, 0.7, folder, at(3, 11))
    finally:
        room_loop.people_boxes = saved_boxes
        room_loop._last_evidence.clear()
    check("the first sighting is kept", len(first), 1)
    check("two minutes later the same camera is not photographed again",
          len(again), 0)
    check("ten minutes later it is", len(later), 1)


def check_xmeye(check):
    """XMeye recorders want the login inside the path, and it must not leak.

    141-C/D's XVR2 is a white-label XMeye/Xiongmai DVR, which none of the
    three known makes describes. Its RTSP path carries user= and password=
    itself, so the console mask that hid "user:pass@" would have printed
    that password in full on every failed grab.
    """
    # The real module, by path: this file puts a stand-in for test_camera
    # in sys.modules so the loop can be run without cameras.
    import importlib.util
    spec = importlib.util.spec_from_file_location("real_test_camera",
                                                  "test_camera.py")
    tc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tc)
    url = tc.build_url("192.168.67.59", 3, "admin", "p@ss#1", False, "xmeye")
    check("the XMeye path carries channel and sub-stream",
          "channel=3&stream=1.sdp" in url, True)
    check("and the login, escaped", "password=p%40ss%231" in url, True)
    masked = tc.mask(url)
    check("the mask hides the password in the path too",
          "p%40ss" in masked or "p@ss" in masked, False)
    check("and still shows which recorder and channel",
          "192.168.67.59" in masked and "channel=3" in masked, True)
    hik = tc.mask(tc.build_url("192.168.67.70", 1, "admin", "p@ss", True))
    check("the other makes are masked as before",
          hik, "rtsp://***@192.168.67.70:554/Streaming/Channels/101")

    # The newer XMeye firmware: fields joined by _, and the password sent as
    # the recorder's scramble of it rather than as typed.
    check("the scramble of the empty password is the one in the manuals",
          tc.sofia_hash(""), "tlJwpbo6")
    new = tc.build_url("192.168.67.59", 2, "ad_min", "pa_ss", True,
                       "xmeye-hash")
    check("the newer path carries the scramble, not the password",
          "password=%s_channel=2_stream=0.sdp" % tc.sofia_hash("pa_ss")
          in new, True)
    masked = tc.mask(new)
    check("and the mask hides both, underscores and all",
          "ad_min" in masked.split("@", 1)[1]
          or tc.sofia_hash("pa_ss") in masked, False)
    check("asking for xmeye tries both firmwares",
          tc.FAMILIES["xmeye"], ["xmeye", "xmeye-hash"])
    moved = tc.build_url("192.168.67.59:5540", 1, "a", "b", False, "xmeye")
    check("a recorder whose RTSP was moved keeps its port",
          "@192.168.67.59:5540/" in moved, True)


def check_stays_up():
    """The loop must survive the night, not just start it.

    Three ways it used to stop without crashing -- each of which loses the
    hours this system exists to measure, and none of which announces itself:
    a cycle throwing, a click in the console window, and the machine going to
    sleep. The first is structure, so it is read out of the source; the other
    two only do anything on Windows, so what is checked here is that they are
    safe to call anywhere and never become the reason the loop will not start.
    """
    source = open("room_loop.py", encoding="utf-8").read()

    check("a failing cycle is caught rather than ending the loop",
          "except Exception as e:" in source and "RETRY_CEILING" in source,
          True)
    check("and a hand on Ctrl+C still stops it",
          "except KeyboardInterrupt:\n            raise" in source, True)
    check("the retry backs off rather than hammering the recorders",
          "wait = min(wait * 2, RETRY_CEILING)" in source, True)
    check("and one good cycle clears the count",
          "trouble, wait = 0, RETRY_SECONDS" in source, True)

    check("turning off click-to-select is safe to call anywhere",
          room_loop.no_quick_edit() in (True, False), True)
    check("so is asking the machine to stay awake",
          room_loop.stay_awake() in (True, False), True)
    check("and handing the sleep timer back",
          room_loop.stay_awake(False) in (True, False), True)
    check("the sleep timer is handed back on the way out",
          "stay_awake(False)" in source.split('__main__')[-1], True)

    # Two functions called sweep() -- the camera pass and the retention
    # delete -- and Python keeps the last one. The retention call therefore
    # reached the camera pass with none of its arguments and raised a
    # TypeError on the first cycle of every run. That was what had been
    # stopping the loop. Names are checked, not behaviour, because the
    # behaviour was perfectly fine in isolation; it was the collision that
    # did it, and a collision is invisible to any test of either half.
    names = [line.split("(")[0][4:] for line in source.splitlines()
             if line.startswith("def ")]
    check("no two top-level functions share a name",
          len(names), len(set(names)))
    check("the retention delete still exists under its own name",
          callable(getattr(room_loop, "prune_old_rows", None)), True)

    # muffled() swaps file descriptor 2 for the whole process. fetch() runs
    # in eight threads, so calling it there raced stderr into /dev/null for
    # good and took the interpreter's own shutdown with it.
    fetch_src = source.split("def fetch(")[1].split("\ndef ")[0]
    # The call, not the word: fetch() carries a comment saying why muffled()
    # must not be used there, and a check that cannot tell the two apart
    # would go green the moment somebody deleted the comment.
    check("the grab does not muffle from inside a worker thread",
          "with muffled():" in fetch_src, False)
    sweep_src = source.split("\ndef sweep(")[1].split("\ndef ")[0]
    check("the camera pass muffles once, around the whole grab",
          "with muffled():" in sweep_src, True)
    check("and failures are printed after the descriptor is back",
          sweep_src.index("with muffled():")
          < sweep_src.index("could not be read"), True)

def check_furniture_at_night(check, room):
    """At night a box that never moves is furniture; anything that moves
    is counted. 14 Nov: empty black chairs in infrared scored 0.35-0.67
    while real people at night scored 0.28-0.57, so no bar could tell
    them apart -- but a chair's pixels do not change between passes, and
    a person's do, even asleep, within every half hour or so."""
    import numpy as np
    rng = np.random.default_rng(1)
    base = rng.integers(40, 200, size=(360, 640, 3)).astype(np.uint8)
    chair = (100, 100, 180, 260, 0.5)
    key = ("dvr2", 3)

    def night(r, frame, minutes, boxes=(chair,), after=True):
        return room_loop.drop_still(r, key, frame, list(boxes), after,
                                    now=at(minutes))

    r = room()
    seen = [len(night(r, base, m)) for m in range(0, 61, 4)]
    check("a chair that never moves is counted for the first 40 minutes",
          seen[:10], [1] * 10)
    check("  and from then on left out as furniture", seen[11:], [0] * 5)
    check("  and the loop says which box it is leaving out",
          room_loop.still_now(r), {key: [[100, 100, 180, 260]]})

    r = room()
    seen = []
    for n, m in enumerate(range(0, 121, 4)):
        frame = base.copy()
        if n % 6 == 5:                       # every 24 minutes he shifts
            frame[120:240, 110:170] = 255 - frame[120:240, 110:170]
        seen.append(len(night(r, frame, m)))
    check("somebody asleep who stirs every 24 minutes is always counted",
          min(seen), 1)

    r = room()
    check("by day nothing is left out, however still",
          [len(night(r, base, m, after=False)) for m in range(0, 81, 4)],
          [1] * 21)
    check("  and nothing is kept about the day", r.still, {})

    r = room()
    for m in range(0, 37, 4):
        night(r, base, m)
    check("a pass missed for longer than the gap starts the clock again",
          len(night(r, base, 37 + room_loop.STILL_GAP + 1)), 1)

    r = room()
    for m in range(0, 37, 4):
        night(r, base, m)
    bright = np.clip(base.astype(np.int16) + 60, 0, 255).astype(np.uint8)
    check("a light switching neither starts nor stops a chair's clock",
          len(night(r, bright, 44)), 0)

    r = room()
    for m in range(0, 37, 4):
        night(r, base, m)
    # A lamp on the far side (half the picture brighter) while somebody
    # sits up in the chair: the box changed far beyond the picture around.
    moved = base.copy()
    moved[:, 320:] = np.clip(base[:, 320:].astype(np.int16) + 60, 0,
                             255).astype(np.uint8)
    moved[100:260, 100:180] = 255 - base[100:260, 100:180]
    check("  but a box that moved beyond the light's change is counted",
          len(night(r, moved, 44)), 1)

    r = room()
    for m in range(0, 45, 4):
        night(r, base, m)
    check("somebody new in a different place is counted at once",
          len(night(r, base, 48, boxes=(chair, (400, 50, 470, 250, 0.8)))),
          1)

    r = room()
    check("a frame that is not a picture is left alone",
          room_loop.drop_still(r, key, "frame", [chair], True, now=at(0)),
          [chair])

    import json
    import os
    import tempfile
    r = room()
    for m in range(0, 49, 4):
        night(r, base, m)
    path = os.path.join(tempfile.mkdtemp(), "still.json")
    room_loop.write_still([r], path=path, now=at(48))
    written = json.load(open(path, encoding="utf-8"))
    check("the furniture is written down for verify_live, numbers only",
          written["rooms"], {"Marketing": {"dvr2:3": [[100, 100, 180, 260]]}})


def check_units_count(check, room):
    """How many units run is recorded, with or without the column for it."""
    r = room()
    r.ac_units_on = 2
    before = r.state()
    r.ac_units_on = 6
    check("two towers to six is a change worth writing",
          before != r.state(), True)

    class Cursor:
        def __init__(self, log, fail):
            self.log, self.fail = log, fail

        def executemany(self, sql, rows):
            if self.fail and "ac_units_on" in sql:
                err = Exception("column does not exist")
                err.pgcode = "42703"
                raise err
            self.log.append((sql, list(rows)))

        def close(self):
            pass

    class Conn:
        def __init__(self, log, fail):
            self.c = Cursor(log, fail)

        def cursor(self):
            return self.c

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    row = (T0, "dvr2", "Cafe", "occupied", 3, None, "on", 5)
    for fail, want_cols, want_len in ((False, 8, 8), (True, 7, 7)):
        log = []
        room_loop.UNITS_COLUMN["present"] = None
        saved = room_loop.connect
        room_loop.connect = lambda: Conn(log, fail)
        try:
            ok = room_loop.record([row])
        finally:
            room_loop.connect = saved
        sql, rows = log[-1]
        check("%s the column: the write lands" % ("without" if fail
                                                    else "with"), ok, True)
        check("  and carries %d values" % want_len, len(rows[0]), want_len)
        check("  and remembers whether the column is there",
              room_loop.UNITS_COLUMN["present"], not fail)
    room_loop.UNITS_COLUMN["present"] = None


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

        # Creative Room: strict at night, when its chairs score like people;
        # the normal bar by day, when its people score like chairs.
        nightly = room(channels=[10], conf_after_hours=0.40)
        seen[:] = []
        room_loop.examine(nightly, {("dvr2", 10): "frame"}, model=None,
                          imgsz=1280, iou=0.7, after_hours=True)
        room_loop.examine(nightly, {("dvr2", 10): "frame"}, model=None,
                          imgsz=1280, iou=0.7, after_hours=False)
        check("a night-only bar applies at night and not by day", seen,
              [0.40, None])

        # A night bar for one camera only: Room 17's chairs are on ch 3,
        # and a person working late on its ch 8 scored 0.37-0.57.
        one = room(channels=[3, 8], conf=0.30, conf_after_hours={3: 0.60})
        seen[:] = []
        room_loop.examine(one, {("dvr2", 3): "frame", ("dvr2", 8): "frame"},
                          model=None, imgsz=1280, iou=0.7, after_hours=True)
        check("a camera's own night bar holds for that camera only",
              sorted(seen), [0.30, 0.60])
        seen[:] = []
        room_loop.examine(one, {("dvr2", 3): "frame", ("dvr2", 8): "frame"},
                          model=None, imgsz=1280, iou=0.7, after_hours=False)
        check("and not by day", seen, [0.30, 0.30])
        two = room(channels=[3], conf_after_hours={"dvr2:3": 0.6})
        check("keyed by recorder too", two.conf_for(True, ("dvr2", 3)), 0.6)
        check("a camera it does not name keeps the normal bar",
              two.conf_for(True, ("dvr2", 4)), None)
        check("the start-up line shows it",
              room_loop.bar_text(one.conf_after_hours), "dvr2:3 0.60")

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
        check("both answering holds once, because one blank frame is not"
              " proof", lobby.status, "occupied")
        lobby.observe(0, 2, T0)
        check("and a second blank pass with both answering does prove it",
              lobby.status, "empty")

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

        # 12 Nov: passes of four to seven minutes, each batch's cameras
        # waited on and only then counted. The next batch is now fetched
        # while this one is counted. Three batches, 0.3s of waiting and
        # 0.3s of counting each: one after the other is 1.8s; overlapped,
        # 0.3s of waiting shows and the rest hides behind the counting.
        def steady_grab(url, **kw):
            time.sleep(0.3)
            return stub_frame, "ok"

        real_examine, real_batch = room_loop.examine, room_loop.BATCH

        def slow_examine(room, frames, *a, **k):
            time.sleep(0.075)
            return 0, len(frames), None, None, ""

        room_loop.grab, room_loop.examine = steady_grab, slow_examine
        room_loop.BATCH = 4
        try:
            started = time.time()
            out = room_loop.sweep(many, recs, None, 1280, 0.7, 5.0, None,
                                  workers=8)
            took = time.time() - started
        finally:
            room_loop.examine, room_loop.BATCH = real_examine, real_batch
        check("every room still read with the fetching overlapped",
              len(out), 12)
        check("the next batch is fetched while this one is counted"
              " (%.2fs, one after the other would be 1.8s)" % took,
              took < 1.55, True)
        check("and the pass says where its time went",
              room_loop.PASS_TIMES["counting"] > 0.8
              and room_loop.PASS_TIMES["waiting"] < 0.7, True)

        # 12 Nov: 151s of a 211s pass was waiting. rooms.yaml lists rooms
        # recorder by recorder, so each batch sat on one recorder, two or
        # four streams at a time, while the other workers idled. Taking
        # turns, eight rooms on two recorders capped at two streams each
        # are fetched four at a time, not two.
        live["most"] = 0
        room_loop.grab = slow_grab
        two = {"nvr1": {"host": "a", "user": "u", "password": "p",
                        "gate": threading.Semaphore(2)},
               "dvr2": {"host": "b", "user": "u", "password": "p",
                        "gate": threading.Semaphore(2)}}
        grouped = ([room(name="A%d" % i, recorder="nvr1", channels=[i])
                    for i in range(4)]
                   + [room(name="B%d" % i, recorder="dvr2", channels=[i])
                      for i in range(4)])
        check("rooms take turns between recorders",
              [r.name for r in room_loop.interleaved(grouped)],
              ["A0", "B0", "A1", "B1", "A2", "B2", "A3", "B3"])
        room_loop.BATCH = 4
        try:
            out = room_loop.sweep(grouped, two, None, 1280, 0.7, 5.0, None,
                                  workers=4)
        finally:
            room_loop.BATCH = real_batch
        check("every room read", len(out), 8)
        # 12 Nov: the page said "silent for 3 min" every pass, because the
        # loop only beat at the end of a four-minute pass. The pass now
        # calls back after each batch, and the loop beats from there.
        calls = []
        room_loop.BATCH = 4
        try:
            room_loop.sweep(grouped, two, None, 1280, 0.7, 5.0, None,
                            workers=4, on_batch=lambda: calls.append(1))
        finally:
            room_loop.BATCH = real_batch
        check("the pass calls back after every batch, for the heartbeat",
              len(calls), 2)
        source = open(room_loop.__file__, encoding="utf-8").read()
        check("and the loop passes its heartbeat in",
              "on_batch=pulse" in source, True)
        check("a batch uses both recorders at once (%d streams open)"
              % live["most"], live["most"] >= 3, True)
    finally:
        room_loop.grab = real_grab

    # 12 Nov, Shamroze: the 141 gym is ladies-only 3 to 8 in the afternoon;
    # take no data from there then. The camera is not opened at all.
    gym = room(name="141 Gym", recorder="cd_nvr2", channels=[7],
               private_hours=["15:00", "20:00"])
    pk = lambda h, m=0: datetime.datetime(2026, 11, 12, h, m, tzinfo=PKT)  # noqa: E731
    check("private at 3 in the afternoon", room_loop.is_private(gym.private,
                                                                pk(15)), True)
    check("private at 7:59", room_loop.is_private(gym.private, pk(19, 59)),
          True)
    check("not at 8 in the evening", room_loop.is_private(gym.private,
                                                          pk(20)), False)
    check("not at 2:59", room_loop.is_private(gym.private, pk(14, 59)),
          False)
    check("a window over midnight works too",
          room_loop.is_private(room_loop.parse_private(["22:00", "06:00"]),
                               pk(2)), True)
    check("a room with no private hours never is",
          room_loop.is_private(room().private, pk(16)), False)
    opened = []
    real_grab, real_private = room_loop.grab, room_loop.is_private
    room_loop.grab = lambda url, **k: opened.append(url) or (None, "x")
    try:
        room_loop.is_private = lambda w, now=None: bool(w)
        got = room_loop.fetch(gym, {"cd_nvr2": {"host": "h", "user": "u",
                                                "password": "p"}}, 1.0)
    finally:
        room_loop.grab, room_loop.is_private = real_grab, real_private
    check("in its private hours no stream is opened, nothing comes back",
          (opened, got), ([], {}))
    import os as _os2
    import tempfile as _tf2
    cfg = _os2.path.join(_tf2.mkdtemp(), "rooms.yaml")
    with open(cfg, "w", encoding="utf-8") as fh:
        fh.write("recorders:\n  cd_nvr2: {host: '192.168.67.168'}\n"
                 "rooms:\n  - {name: 141 Gym, recorder: cd_nvr2,"
                 " channels: [7], ac: none,"
                 " private_hours: ['15:00', '20:00']}\n"
                 "  - {name: Lobby, recorder: cd_nvr2, channels: [8],"
                 " ac: none}\n")
    check("the tools that open a channel directly get the gym's camera",
          room_loop.private_cameras(cfg, pk(16)), {("cd_nvr2", 7)})
    check("  by address, for scan_channels",
          room_loop.private_cameras(cfg, pk(16), by_host=True),
          {("192.168.67.168", 7)})
    check("  and nothing outside the hours",
          room_loop.private_cameras(cfg, pk(21)), set())
    for tool in ("scan_channels.py", "doctor.py", "ac_survey.py",
                 "calibrate_room.py", "tune_detect.py"):
        text = open(tool, encoding="utf-8").read()
        check("%s keeps private cameras closed" % tool,
              "private_cameras" in text or "is_private" in text, True)

    # 12 Nov: where people sit, as numbers, for a seat map.
    import os as _os3
    import tempfile as _tf3
    seat_dir = _tf3.mkdtemp()
    at_noon = datetime.datetime(2026, 11, 12, 12, 0, tzinfo=PKT)
    room_loop.note_seats("Marketing", ("dvr2", 3),
                         [(100, 200, 160, 360, 0.81)], (1080, 1920, 3),
                         folder=seat_dir, now=at_noon)
    room_loop.note_seats("Marketing", ("dvr2", 3), [], (1080, 1920, 3),
                         folder=seat_dir, now=at_noon)
    with open(_os3.path.join(seat_dir, "2026-11-12.csv"),
              encoding="utf-8") as fh:
        seat_lines = fh.read().splitlines()
    check("a counted person is noted as numbers: centre, size, score, frame",
          seat_lines[1], '12:00:00,"Marketing",dvr2,3,130,280,60,160,0.81,'
                         '1920,1080')
    check("and nobody seen notes nothing", len(seat_lines), 2)
    check("the seat notes stay off git",
          "seats/" in open(".gitignore", encoding="utf-8").read(), True)

    # 13 Nov: the AC cameras' frames, every ten minutes, for calibrating
    # units from the data -- night ones too.
    import numpy as _np
    keep_dir = _tf3.mkdtemp()
    room_loop._last_ac_keep.clear()
    cafe = room(name="141-C Cafe", recorder="cd_nvr1", channels=[2, 14, 9],
                ac="visible")
    units = {"141-C Cafe": {"recorder": "cd_nvr1", "channel": 14,
                            "units": [{}],
                            "also": [{"channel": 2, "units": [{}]}]}}
    check("a calibrated room keeps the cameras its calibration names",
          room_loop.ac_cameras(cafe, units),
          [("cd_nvr1", 14), ("cd_nvr1", 2)])
    check("a visible unit not calibrated yet keeps all its cameras",
          room_loop.ac_cameras(cafe, {}), cafe.cameras)
    check("a room with no unit in view keeps none",
          room_loop.ac_cameras(room(ac="hidden"), {}), [])
    pic = _np.zeros((576, 704, 3), _np.uint8)
    shots = {("cd_nvr1", 14): pic, ("cd_nvr1", 2): pic, ("cd_nvr1", 9): pic}
    check("a pass keeps one frame per AC camera",
          room_loop.keep_ac_frames(cafe, shots, units, folder=keep_dir,
                                   now=at_noon), 2)
    check("  in <date>/<HHMM>/<room>__<rec>_chNN.jpg",
          sorted(_os3.listdir(_os3.path.join(keep_dir, "2026-11-12", "1200"))),
          ["141_C_Cafe__cd_nvr1_ch02.jpg", "141_C_Cafe__cd_nvr1_ch14.jpg"])
    check("and not again within ten minutes",
          room_loop.keep_ac_frames(
              cafe, shots, units, folder=keep_dir,
              now=at_noon + datetime.timedelta(minutes=5)), 0)
    check("a camera that sent nothing keeps nothing",
          room_loop.keep_ac_frames(
              cafe, {}, units, folder=keep_dir,
              now=at_noon + datetime.timedelta(minutes=30)), 0)
    _os3.makedirs(_os3.path.join(keep_dir, "2026-11-08"))
    check("days older than three go",
          (room_loop.prune_ac_keep(folder=keep_dir,
                                   today=datetime.date(2026, 11, 12)),
           sorted(_os3.listdir(keep_dir))), (1, ["2026-11-12"]))
    check("and they stay off git",
          "frames/" in open(".gitignore", encoding="utf-8").read(), True)

    # cycles.csv gained two columns; a file with the old header is set
    # aside rather than mixed into one table with rows of two shapes.
    import os as _os
    import tempfile as _tf
    folder = _tf.mkdtemp()
    log = _os.path.join(folder, "cycles.csv")
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("time,cycle,seconds,rooms,occupied,empty,unknown\n"
                 "2026-11-12 14:00:00,1,250,105,50,55,0\n")
    when = datetime.datetime(2026, 11, 12, 15, 0, tzinfo=PKT)
    room_loop.log_cycle([room()], when, 1, 120.0, path=log)
    with open(log, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    check("cycles.csv starts afresh with the new columns",
          lines[0], room_loop.CYCLE_HEADER)
    check("one row, as wide as its header",
          (len(lines), len(lines[1].split(","))),
          (2, len(room_loop.CYCLE_HEADER.split(","))))
    check("the old one is kept beside it",
          _os.path.exists(_os.path.join(folder,
                                        "cycles_before_20261112_1500.csv")),
          True)

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

    check_xmeye(check)
    check_evidence_keeps_the_night(check)
    check_one_stream_rule(check)
    check_flicker(check, room, T0)
    check_stays_up()
    check_units_count(check, room)
    check_furniture_at_night(check, room)

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
