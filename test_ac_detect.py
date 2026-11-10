"""Checks on reading an air conditioner's display.

The frames here are built, not filmed, so these are not a claim that the real
camera reads correctly -- that was established by measuring two real frames of
the Admin Room, and the numbers from that measurement are in ac_units.yaml.
What these checks defend is the part that can rot quietly: that the thresholds
in the file still separate a lit display from a dark one, and that every way of
not knowing returns "I do not know" instead of a confident wrong answer.

A wrong "off" means nobody is sent to a room that is cooling itself all night.
A wrong "on" means somebody walks upstairs for nothing and stops believing the
system. Refusing to answer costs neither.
"""
import os
import shutil
import sys

import numpy as np
import yaml

import ac_detect

ON_DISK = yaml.safe_load(open("ac_units.yaml"))["rooms"]

# The checks below read the real calibration against pictures drawn here --
# a grey frame with a lit box painted on. Those pictures are not of the
# room, so a calibration carrying an anchor rightly refuses them as "the
# camera has moved". The anchor is exercised on its own further down; for
# everything else the anchor is set aside, so these checks keep testing the
# box and the threshold rather than failing on a room they were never of.
UNITS = {room: dict(cfg, units=[{k: v for k, v in unit.items()
                                 if k != "anchor"}
                                for unit in cfg.get("units", [])])
         for room, cfg in ON_DISK.items()}
FAILED = []


def ok(label, condition):
    print("%s %s" % ("OK  " if condition else "FAIL", label))
    if not condition:
        FAILED.append(label)


def grey(width=1920, height=1080, level=60):
    """A frame with all three channels equal: what an infrared camera sends."""
    return np.full((height, width, 3), level, dtype=np.uint8)


def with_lit_display(room="Admin Room", level=60):
    """The same frame, with bright strokes inside the calibrated box."""
    cfg = UNITS[room]
    frame = grey(*cfg["frame_size"], level=level)
    x1, y1, x2, y2 = cfg["units"][0]["led_roi"]
    # Alternating columns: digits are strokes on a dark face, not a bright
    # rectangle, and it is that mixture which produces the contrast.
    frame[y1:y2, x1:x2:2] = 235
    return frame



def check_inverted(ok):
    """A unit that goes dark when it runs is still a unit.

    Marketing produced the same result twice, in the right order both
    times: nothing lights up when those five units start, something goes
    dark instead -- a vent flap opening onto a cavity, or a display that
    switches itself off once running. The tool only knew how to find
    things that light up, so it called the frames swapped and refused.

    Which side means "running" is read back off the two measurements
    rather than stored as a separate flag, so the numbers and the
    direction cannot drift apart.
    """
    bright = np.full((1080, 1920, 3), 60, np.uint8)
    bright[20:50, 10:40] = np.random.default_rng(3).integers(
        0, 255, (30, 30, 3), dtype=np.uint8)          # high contrast
    flat = np.full((1080, 1920, 3), 60, np.uint8)     # low contrast

    normal = {"R": {"frame_size": [1920, 1080], "units": [
        {"label": "glows", "led_roi": [10, 20, 40, 50],
         "led_std_threshold": 18.0,
         "measured": {"on_std": 36.8, "off_std": 1.1}}]}}
    ok("a unit that lights up reads on when the box is bright",
       ac_detect.read_room(bright, "R", normal)[0] == "on")
    ok("and off when it is flat",
       ac_detect.read_room(flat, "R", normal)[0] == "off")

    # The same box and threshold, with the measurements the other way round.
    inverted = {"R": {"frame_size": [1920, 1080], "units": [
        {"label": "goes dark", "led_roi": [10, 20, 40, 50],
         "led_std_threshold": 18.0,
         "measured": {"on_std": 1.1, "off_std": 36.8}}]}}
    ok("a unit that goes dark reads ON when the box is flat",
       ac_detect.read_room(flat, "R", inverted)[0] == "on")
    ok("and OFF when it is bright",
       ac_detect.read_room(bright, "R", inverted)[0] == "off")

    # A calibration written before any of this has no measurements to read
    # the direction from, and must keep behaving as it always did.
    older = {"R": {"frame_size": [1920, 1080], "units": [
        {"label": "old", "led_roi": [10, 20, 40, 50],
         "led_std_threshold": 18.0}]}}
    ok("a calibration with no measurements still reads the old way",
       ac_detect.read_room(bright, "R", older)[0] == "on")

    source = open("calibrate_room.py", encoding="utf-8").read()
    ok("the refusal offers --inverted rather than only blaming the order",
       "--inverted" in source and "goes dark rather than lighting up"
       in source)
    ok("and the gap is measured in whichever direction it runs",
       "gap = abs(on_std - off_std)" in source)

    # --inverted took its own branch and never set the box the rest of the
    # function works from, so it crashed on the line after announcing
    # itself. The branch that chooses a candidate has to choose one.
    branch = source.split("if args.inverted:")[1].split("else:")[0]
    ok("the inverted branch picks a box like every other path",
       "box = found[args.choice - 1][\"box\"]" in branch)
    ok("and honours --choice the same way",
       "--choice must be between 1 and" in branch)


def check_people_masked(ok):
    """A change where a person stands is that person moving.

    Marketing's preview put all six candidates on people -- somebody bent
    over a desk, two at the back -- and none on the five units in plain
    view near the ceiling. Thirty seconds apart, in a room in use, the
    biggest differences between two frames are people, and one at the far
    end of an open-plan office is small enough to pass as a display.
    """
    import calibrate_room as cr

    off = np.full((1080, 1920, 3), 40, np.uint8)
    on = off.copy()
    # A "display" lights up near the ceiling...
    on[100:116, 1400:1440] = 240
    # ...and a person moves at a desk, which also lights pixels up.
    on[700:716, 500:540] = 240

    everything = cr.candidates(on, off)
    ok("without a mask the moving person is a candidate",
       any(b["box"][1] > 600 for b in everything))

    person = [(470, 650, 600, 900)]
    masked = cr.candidates(on, off, people=person)
    ok("with the person masked, they are not",
       not any(b["box"][1] > 600 for b in masked))
    ok("and the display near the ceiling still is",
       any(b["box"][1] < 200 for b in masked))

    ok("boxes that touch overlap", cr.overlaps((0, 0, 10, 10),
                                               [(5, 5, 20, 20)]))
    ok("boxes that do not, do not", not cr.overlaps((0, 0, 10, 10),
                                                    [(11, 11, 20, 20)]))


def check_several_units(ok):
    """A room with five air conditioners is not five rooms.

    calibrate_room.py wrote one unit and refused a second; the only way to
    record another was --replace, which deleted the first. On a room with
    five units that is one switch-on by a technician and four measurements
    silently lost -- and the only way to discover it was to do it.
    """
    import tempfile

    import calibrate_room as cr

    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "ac_units.yaml")
    cr.write_config(path, "Marketing", "dvr2", 13, (1920, 1080), False,
                    "unit 1, left", (10, 20, 40, 50), 18.0,
                    36.0, 1.0, 240, 120, "2026-11-10T17:00+0500",
                    anchor="AAA")
    cr.write_config(path, "Wellows", "dvr2", 15, (1920, 1080), False,
                    "only unit", (60, 70, 90, 100), 15.0,
                    30.0, 2.0, 230, 110, "2026-11-10T17:05+0500",
                    anchor="BBB")
    for n in (2, 3):
        cr.add_unit(path, "Marketing", "unit %d, right" % n,
                    (100 * n, 20, 100 * n + 30, 50), 17.0,
                    35.0, 1.5, 238, 118, "2026-11-10T17:10+0500",
                    anchor="CCC")

    loaded = yaml.safe_load(open(path))["rooms"]
    ok("a room can hold more than one unit",
       len(loaded["Marketing"]["units"]) == 3)
    ok("and they are told apart by label",
       [u["label"] for u in loaded["Marketing"]["units"]]
       == ["unit 1, left", "unit 2, right", "unit 3, right"])
    ok("the first unit is not overwritten",
       loaded["Marketing"]["units"][0]["led_roi"] == [10, 20, 40, 50])
    ok("another room is left alone",
       loaded["Wellows"]["units"][0]["led_roi"] == [60, 70, 90, 100])
    ok("the room's own settings are kept",
       loaded["Marketing"]["channel"] == 13)

    # The comments are the reasoning behind each threshold. A reload-and-dump
    # would produce valid YAML and delete all of them.
    ok("the reasoning in the file survives an append",
       "# The lighting the measurement" in open(path).read())

    # Two units with the same label cannot be told apart in an alert.
    try:
        cr.add_unit(path, "Marketing", "unit 1, left", (1, 2, 3, 4), 9.0,
                    20.0, 1.0, 200, 100, "x")
        ok("a repeated label is refused", False)
    except SystemExit as e:
        ok("a repeated label is refused", "already has a unit" in str(e))
    try:
        cr.add_unit(path, "Nowhere", "u", (1, 2, 3, 4), 9.0, 20.0, 1.0,
                    200, 100, "x")
        ok("adding to a room not in the file is refused", False)
    except SystemExit as e:
        ok("adding to a room not in the file is refused",
           "not in" in str(e))

    # And the detector must read all of them: any one running means the
    # room is being cooled, so one unit on is not an off room.
    frame = np.full((1080, 1920, 3), 60, np.uint8)
    frame[20:50, 10:40] = np.random.default_rng(1).integers(
        0, 255, (30, 30, 3), dtype=np.uint8)          # unit 1 lit
    config = {"Marketing": {"frame_size": [1920, 1080], "units": [
        {"label": "a", "led_roi": [10, 20, 40, 50], "led_std_threshold": 18.0},
        {"label": "b", "led_roi": [200, 20, 230, 50], "led_std_threshold": 17.0},
        {"label": "c", "led_roi": [300, 20, 330, 50], "led_std_threshold": 17.0},
    ]}}
    state, why = ac_detect.read_room(frame, "Marketing", config)
    ok("one unit of three running reads as on", state == "on")
    ok("and the reason says how many were read", why == "3 unit(s) read")

    dark = np.full((1080, 1920, 3), 60, np.uint8)
    ok("all three dark reads as off",
       ac_detect.read_room(dark, "Marketing", config)[0] == "off")

    shutil.rmtree(folder)



def main():
    room = "Admin Room"
    cfg = UNITS[room]
    box = cfg["units"][0]["led_roi"]
    threshold = cfg["units"][0]["led_std_threshold"]

    print("-- the calibrated numbers still separate the two states")
    lit, dark = with_lit_display(room), grey(*cfg["frame_size"])
    ok("a lit display reads on", ac_detect.read_room(lit, room, UNITS)[0] == "on")
    ok("a blank display reads off",
       ac_detect.read_room(dark, room, UNITS)[0] == "off")
    ok("the measured on figure is above the threshold",
       cfg["units"][0]["measured"]["on_std"] > threshold)
    ok("the measured off figure is below it",
       cfg["units"][0]["measured"]["off_std"] < threshold)
    gap = (cfg["units"][0]["measured"]["on_std"]
           - cfg["units"][0]["measured"]["off_std"])
    ok("and the two are far apart, not a coin toss (%.1f)" % gap, gap > 10)

    print("-- a room nobody has measured says so")
    state, why = ac_detect.read_room(lit, "Some Room Never Calibrated", UNITS)
    ok("state is unknown", state is None)
    ok("and the reason names it", "not calibrated" in why)

    print("-- a frame of the wrong size is refused, not measured")
    small = grey(960, 540)
    state, why = ac_detect.read_room(small, room, UNITS)
    ok("state is unknown", state is None)
    ok("and the reason gives both sizes", "960x540" in why and "1920x1080" in why)

    print("-- the wrong lighting is refused")
    colour = with_lit_display(room)
    colour[:, :, 0] = 20          # push blue away from green and red
    colour[:, :, 2] = 160
    state, why = ac_detect.read_room(colour, room, UNITS)
    ok("a colour frame does not answer an infrared calibration", state is None)
    ok("and the reason says why", "colour" in why)

    print("-- a box that falls outside the picture is refused")
    moved = {room: dict(cfg, units=[dict(cfg["units"][0],
                                         led_roi=[1900, 34, 2200, 67])])}
    state, why = ac_detect.read_room(grey(*cfg["frame_size"]), room, moved)
    ok("state is unknown", state is None)
    ok("and the reason says outside", "outside" in why)

    print("-- two units: one running means the room is being cooled")
    pair = {room: dict(cfg, units=[cfg["units"][0],
                                   dict(cfg["units"][0],
                                        label="second unit",
                                        led_roi=[800, 34, 831, 67])])}
    one_on = grey(*cfg["frame_size"])
    x1, y1, x2, y2 = box
    one_on[y1:y2, x1:x2:2] = 235          # only the first unit lit
    ok("reads on", ac_detect.read_room(one_on, room, pair)[0] == "on")
    ok("both dark reads off",
       ac_detect.read_room(grey(*cfg["frame_size"]), room, pair)[0] == "off")

    print("-- every calibrated room carries what it needs to be read")
    for name, entry in sorted(UNITS.items()):
        units = entry.get("units") or []
        ok("%s: has a channel" % name, entry.get("channel") is not None)
        ok("%s: has a frame size" % name, len(entry.get("frame_size", [])) == 2)
        ok("%s: has at least one unit" % name, bool(units))
        for unit in units:
            where = "%s / %s" % (name, unit.get("label", "unnamed"))
            ok("%s: box is four numbers" % where, len(unit.get("led_roi", [])) == 4)
            ok("%s: threshold is set" % where,
               isinstance(unit.get("led_std_threshold"), (int, float)))
            measured = unit.get("measured") or {}
            ok("%s: the measurement behind the threshold is recorded" % where,
               "on_std" in measured and "off_std" in measured
               and "taken" in measured)
            if "on_std" in measured and "off_std" in measured:
                ok("%s: threshold sits between the two readings" % where,
                   measured["off_std"] < unit["led_std_threshold"]
                   < measured["on_std"])

    print("-- the calibration tool finds the box and writes a readable file")
    # The whole round trip in one go: two frames in, a box found, a threshold
    # written, and that written file used to read the same two frames back.
    # Every piece of this works on its own; what this checks is that they
    # still agree with each other.
    import tempfile

    import calibrate_room

    noise = np.random.RandomState(0).randint(0, 4, (1080, 1920, 3))
    dark = (grey() + noise).astype(np.uint8)
    bright = dark.copy()
    bright[36:66, 354:381:2] = 238          # digits: strokes, with gaps
    bright[36:66, 355:382:3] = 210

    boxes = calibrate_room.candidates(bright, dark)
    ok("one box, not one per stroke of the digits", len(boxes) == 1)
    if boxes:
        x1, y1, x2, y2 = boxes[0]["box"]
        ok("and it sits over the display", x1 <= 354 and x2 >= 381
           and y1 <= 36 and y2 >= 66)
        ok("and it is not most of the frame", (x2 - x1) * (y2 - y1) < 20000)

        path = os.path.join(tempfile.mkdtemp(), "written.yaml")
        on_std = ac_detect.contrast(bright, boxes[0]["box"])
        off_std = ac_detect.contrast(dark, boxes[0]["box"])
        calibrate_room.write_config(
            path, "Test Room", "dvr2", 9, (1920, 1080), True, "unit",
            boxes[0]["box"], (on_std + off_std) / 2, on_std, off_std,
            238, 61, "2026-11-07T12:00+0500")
        written = ac_detect.load_units(path)
        ok("the written file loads", "Test Room" in written)
        ok("the lit frame reads on through it",
           ac_detect.read_room(bright, "Test Room", written)[0] == "on")
        ok("the dark frame reads off through it",
           ac_detect.read_room(dark, "Test Room", written)[0] == "off")

        # Writing a second room must not take the first one out.
        calibrate_room.write_config(
            path, "Another Room", "nvr1", 4, (1920, 1080), True, "unit",
            boxes[0]["box"], (on_std + off_std) / 2, on_std, off_std,
            238, 61, "2026-11-07T12:00+0500")
        both = ac_detect.load_units(path)
        ok("writing a second room keeps the first",
           "Test Room" in both and "Another Room" in both)

    print("-- two frames of the same state produce nothing to write")
    ok("no boxes", calibrate_room.candidates(dark, dark) == [])

    print("-- a camera that has been nudged is refused, not read")
    # The failure this guards against is the quiet one. A bumped camera puts
    # the box on blank wall, where it reads low contrast for ever and calls a
    # running unit off -- and a unit never reported as on sends nobody
    # anywhere, so nobody finds out.
    import cv2 as _cv2

    import calibrate_room

    rs = np.random.RandomState(7)
    wall = np.full((1080, 1920, 3), 58, dtype=np.uint8)
    wall += rs.randint(0, 4, (1080, 1920, 3)).astype(np.uint8)
    _cv2.rectangle(wall, (150, 10), (520, 95), (96, 96, 96), -1)
    _cv2.rectangle(wall, (150, 10), (520, 95), (140, 140, 140), 2)
    for x in range(160, 515, 9):
        _cv2.line(wall, (x, 70), (x, 90), (72, 72, 72), 1)
    _cv2.rectangle(wall, (345, 28), (390, 72), (34, 34, 34), -1)
    off_frame = wall.copy()
    on_frame = wall.copy()
    on_frame[36:66, 354:381:2] = 238
    on_frame[36:66, 355:382:3] = 210

    found = calibrate_room.candidates(on_frame, off_frame)
    ok("the display is found on a textured frame", len(found) == 1)
    if found:
        the_box = found[0]["box"]
        on_std = ac_detect.contrast(on_frame, the_box)
        off_std = ac_detect.contrast(off_frame, the_box)
        anchored = os.path.join(tempfile.mkdtemp(), "anchored.yaml")
        calibrate_room.write_config(
            anchored, "Nudge Room", "dvr2", 9, (1920, 1080), True, "unit",
            the_box, (on_std + off_std) / 2, on_std, off_std, 238, 58,
            "2026-11-07T12:00+0500",
            anchor=ac_detect.pack(ac_detect.fingerprint(
                off_frame, ac_detect.anchor_box(the_box, (1920, 1080)),
                hide=the_box)))
        kept = ac_detect.load_units(anchored)
        ok("an anchor was written",
           bool(kept["Nudge Room"]["units"][0].get("anchor")))

        ok("the lit frame still reads on",
           ac_detect.read_room(on_frame, "Nudge Room", kept)[0] == "on")
        ok("the dark frame still reads off",
           ac_detect.read_room(off_frame, "Nudge Room", kept)[0] == "off")

        # Brightness must not be mistaken for movement: a camera that gains
        # down at dusk is the same camera.
        dim = (on_frame.astype(np.int16) * 0.55 + 20).clip(0, 255)
        ok("a much dimmer picture of the same view still reads on",
           ac_detect.read_room(dim.astype(np.uint8), "Nudge Room",
                               kept)[0] == "on")

        for dx, dy in ((30, 0), (0, 25), (60, 40)):
            shifted = _cv2.warpAffine(
                on_frame, np.float32([[1, 0, dx], [0, 1, dy]]), (1920, 1080))
            state, why = ac_detect.read_room(shifted, "Nudge Room", kept)
            ok("shifted %dpx,%dpx is refused" % (dx, dy), state is None)
            ok("  and the reason says the camera moved", "moved" in why)

    print("-- a calibration with no anchor still works")
    # Admin Room was measured before anchors existed. It must go on being
    # read rather than refused, or adding a safeguard would have broken the
    # one room the system can actually see.
    plain = {"Old Room": dict(UNITS["Admin Room"])}
    plain["Old Room"]["units"] = [{k: v for k, v in
                                   UNITS["Admin Room"]["units"][0].items()
                                   if k != "anchor"}]
    ok("it reads", ac_detect.read_room(with_lit_display("Admin Room"),
                                       "Old Room", plain)[0] == "on")

    # The one calibration in use carries its anchor, so a nudged camera
    # refuses itself instead of reading a running unit as off for ever.
    ok("Admin Room's calibration on disk carries an anchor",
       bool(ON_DISK["Admin Room"]["units"][0].get("anchor")))
    check_inverted(ok)
    check_people_masked(ok)
    check_several_units(ok)

    print()
    if FAILED:
        print("%d check(s) failed:" % len(FAILED))
        for label in FAILED:
            print("   - %s" % label)
        sys.exit(1)

    print("all checks passed")


if __name__ == "__main__":
    main()
