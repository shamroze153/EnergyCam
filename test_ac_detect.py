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
import sys

import numpy as np
import yaml

import ac_detect

UNITS = yaml.safe_load(open("ac_units.yaml"))["rooms"]
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

    print()
    if FAILED:
        print("%d check(s) failed:" % len(FAILED))
        for label in FAILED:
            print("   - %s" % label)
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
