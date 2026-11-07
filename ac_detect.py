"""Read whether an air conditioner is running, from its own display.

The unit tells you itself: a lit display has bright strokes on a dark face,
an unlit one is a flat panel. Measuring the contrast inside a small box over
that display separates the two, and on the first room calibrated the gap was
thirty-six against one -- not a close call.

Everything this returns is one of three things, and the third matters as much
as the others:

    "on"    the display is lit
    "off"   the display is not
    None    we cannot say, and will not guess

None is returned when the room has no calibration, when the frame is not the
size the boxes were drawn on, or when the camera's lighting is not the kind
the measurement was taken in. Each of those would otherwise produce a
confident answer with nothing behind it, which is the one thing this system
must not do: a wrong "off" sends nobody to a running unit, and a wrong "on"
sends somebody to a room that is already fine.
"""
import os

import cv2
import numpy as np
import yaml

CONFIG = "ac_units.yaml"

# Below this spread between the colour channels the camera is in infrared,
# the same test ac_config.py uses, so the two agree about what night means.
INFRARED_CHANNEL_SPREAD = 3.0


def load_units(path=CONFIG):
    if not os.path.exists(path):
        return {}
    return (yaml.safe_load(open(path)) or {}).get("rooms", {}) or {}


def is_infrared(frame):
    """A greyscale picture from a colour camera means the infrared cut filter
    has swung in: the three channels carry the same values."""
    if frame.ndim < 3 or frame.shape[2] < 3:
        return True
    small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    small = small.astype(np.int16)
    blue, green, red = small[:, :, 0], small[:, :, 1], small[:, :, 2]
    spread = (np.abs(blue - green).mean() + np.abs(green - red).mean()) / 2
    return spread < INFRARED_CHANNEL_SPREAD


def contrast(frame, box):
    """Spread of brightness inside the box. Lit strokes on a dark face give a
    high number; a blank panel gives almost nothing."""
    x1, y1, x2, y2 = box
    patch = frame[y1:y2, x1:x2]
    if patch.size == 0:
        return None
    if patch.ndim == 3:
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    return float(patch.std())


def read_room(frame, room, units=None):
    """Is this room's unit running? Returns (state, why).

    `why` is there so a refusal can be read rather than puzzled over. A room
    that silently reports None looks identical to a room nobody calibrated.
    """
    units = load_units() if units is None else units
    config = units.get(room)
    if not config:
        return None, "not calibrated"

    height, width = frame.shape[:2]
    expected = config.get("frame_size")
    if expected and [width, height] != list(expected):
        return None, ("frame is %dx%d, the boxes were drawn on %dx%d"
                      % (width, height, expected[0], expected[1]))

    expect = config.get("expect")
    infrared = is_infrared(frame)
    if expect == "infrared" and not infrared:
        return None, "camera is in colour; calibrated in infrared"
    if expect == "colour" and infrared:
        return None, "camera is in infrared; calibrated in colour"

    lit = []
    for unit in config.get("units", []):
        box = unit.get("led_roi")
        threshold = unit.get("led_std_threshold")
        if not box or threshold is None:
            continue
        x1, y1, x2, y2 = box
        if x2 > width or y2 > height or x1 < 0 or y1 < 0:
            return None, "a box falls outside the frame"
        value = contrast(frame, box)
        if value is None:
            return None, "a box is empty"
        lit.append(value >= threshold)

    if not lit:
        return None, "no usable boxes"
    # Any unit running means the room is being cooled. A room with two units
    # and one of them on is not an off room.
    return ("on" if any(lit) else "off"), "%d unit(s) read" % len(lit)
