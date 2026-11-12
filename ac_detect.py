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
import base64
import os

import cv2
import numpy as np
import yaml

CONFIG = "ac_units.yaml"

# A box is a position, and a position only means something while the camera
# is pointing where it was. Nudge the camera and the box lands on blank wall,
# where it will read low contrast for ever and report a running unit as off
# -- silently, and in the one direction nobody notices, because an air
# conditioner that is never reported as on never sends anybody anywhere.
#
# So a calibration also keeps a thumbnail of the unit and the wall around it.
# Those do not change; the room in front of them does. Before each reading
# the same patch is compared against it, after both are levelled for
# brightness and contrast so that a dimmer picture is not mistaken for a
# different one. Below this, the view is not the one that was measured.
ANCHOR_MATCH = 0.55
ANCHOR_SIZE = 48

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


def fingerprint(frame, box, hide=None):
    """A small, brightness-independent thumbnail of one part of the picture.

    `hide` is painted over before the thumbnail is taken, and it is always
    the display. The display is the one thing in this region that is meant
    to change -- it is lit half the time by design -- so leaving it in would
    make an anchor taken with the unit off disagree with every frame where
    the unit is on, and refuse exactly the readings it exists to protect.
    """
    x1, y1, x2, y2 = box
    patch = frame[y1:y2, x1:x2]
    if patch.size == 0:
        return None
    if patch.ndim == 3:
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    patch = patch.copy()
    if hide is not None:
        hx1, hy1, hx2, hy2 = (hide[0] - x1, hide[1] - y1,
                              hide[2] - x1, hide[3] - y1)
        hx1, hy1 = max(0, hx1), max(0, hy1)
        hx2, hy2 = min(patch.shape[1], hx2), min(patch.shape[0], hy2)
        if hx2 > hx1 and hy2 > hy1:
            keep = np.ones(patch.shape, dtype=bool)
            keep[hy1:hy2, hx1:hx2] = False
            if not keep.any():
                return None
            patch[hy1:hy2, hx1:hx2] = int(np.median(patch[keep]))
    small = cv2.resize(patch, (ANCHOR_SIZE, ANCHOR_SIZE),
                       interpolation=cv2.INTER_AREA).astype(np.float32)
    small -= small.mean()
    spread = small.std()
    if spread < 1e-6:
        return None                     # a blank patch matches anything
    return small / spread


def anchor_box(box, frame_size, grow=4.0):
    """The region a fingerprint is taken from: the box, and its surroundings.

    Wider than the display on purpose. The display itself changes -- that is
    the whole point of it -- while the unit around it and the wall behind do
    not, so they are what says whether the camera still looks where it did.
    """
    x1, y1, x2, y2 = box
    width, height = frame_size
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    half_w = max(40.0, (x2 - x1) * grow / 2)
    half_h = max(40.0, (y2 - y1) * grow / 2)
    return (max(0, int(cx - half_w)), max(0, int(cy - half_h)),
            min(width, int(cx + half_w)), min(height, int(cy + half_h)))


def anchor_match(frame, box, stored, hide=None):
    """How well the view round the box still matches the one calibrated."""
    here = fingerprint(frame, box, hide)
    if here is None or stored is None:
        return None
    if here.shape != stored.shape:
        return None
    return float((here * stored).mean())


def pack(thumb):
    """A fingerprint as one line of text, for keeping in the YAML."""
    scaled = np.clip(thumb * 48 + 128, 0, 255).astype(np.uint8)
    return base64.b64encode(scaled.tobytes()).decode("ascii")


def unpack(text):
    raw = np.frombuffer(base64.b64decode(text), dtype=np.uint8)
    if raw.size != ANCHOR_SIZE * ANCHOR_SIZE:
        return None
    small = raw.reshape(ANCHOR_SIZE, ANCHOR_SIZE).astype(np.float32)
    small -= small.mean()
    spread = small.std()
    return None if spread < 1e-6 else small / spread


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
    state, why, _ = read_units(frame, room, units)
    return state, why


def read_units(frame, room, units=None):
    """The room's state, why, and how many of its units were seen running.

    The count is what the dashboard draws as "5 of 6 running" and turns
    into kilowatts; it is None whenever the reading was refused, because a
    refusal knows nothing about any unit. 141-C Cafe has six towers and
    five in view: four lit is (on, "...", 4), all five dark is (None, ...,
    0) -- unknown for the room, but still nothing seen running.
    """
    units = load_units() if units is None else units
    config = units.get(room)
    if not config:
        return None, "not calibrated", None

    height, width = frame.shape[:2]
    expected = config.get("frame_size")
    if expected and [width, height] != list(expected):
        return None, ("frame is %dx%d, the boxes were drawn on %dx%d"
                      % (width, height, expected[0], expected[1])), None

    expect = config.get("expect")
    infrared = is_infrared(frame)
    if expect == "infrared" and not infrared:
        return None, "camera is in colour; calibrated in infrared", None
    if expect == "colour" and infrared:
        return None, "camera is in infrared; calibrated in colour", None

    lit = []
    for unit in config.get("units", []):
        box = unit.get("led_roi")
        threshold = unit.get("led_std_threshold")
        if not box or threshold is None:
            continue
        x1, y1, x2, y2 = box
        if x2 > width or y2 > height or x1 < 0 or y1 < 0:
            return None, "a box falls outside the frame", None
        stored = unit.get("anchor")
        if stored:
            # The region round the box, unless the unit names its own: 141
            # Finance Room's default took in the window under the unit, and
            # the afternoon sun through it read as "the camera has moved".
            region = unit.get("anchor_roi")
            region = (tuple(int(v) for v in region) if region
                      else anchor_box(box, (width, height)))
            score = anchor_match(frame, region, unpack(stored), hide=box)
            if score is None:
                return None, "the view round the box cannot be compared", None
            if score < ANCHOR_MATCH:
                return None, ("the camera has moved: the view round the box"
                              " matches the calibrated one only %.2f"
                              % score), None
        value = contrast(frame, box)
        if value is None:
            return None, "a box is empty", None
        # Which side of the threshold means "running" is taken from the
        # measurements themselves, not assumed.
        #
        # Most units glow: the display lights up and contrast inside the
        # box goes up with it. Marketing does the opposite -- nothing lights
        # up when those units start, something goes dark instead, twice
        # over, on two separate attempts. Whether that is the vent flap
        # opening onto a dark cavity or a display that switches itself off
        # once the unit is running does not matter here: it is a real and
        # repeatable difference between the two states, and the direction
        # of it is already written down in on_std and off_std.
        measured = unit.get("measured") or {}
        on_std, off_std = measured.get("on_std"), measured.get("off_std")
        higher_is_on = (on_std is None or off_std is None
                        or on_std >= off_std)
        lit.append(value >= threshold if higher_is_on
                   else value <= threshold)

    if not lit:
        return None, "no usable boxes", None
    running = sum(1 for x in lit if x)
    # Any unit running means the room is being cooled. A room with two units
    # and one of them on is not an off room.
    if running:
        return "on", "%d unit(s) read" % len(lit), running
    # The converse does not hold. 141 Learning Center has three units and
    # its camera can read one of them: that one off says nothing about the
    # other two, and calling the room "off" would quietly drop every empty
    # hour they ran from the waste and the alerts. Off is only known when
    # every unit in the room was read.
    unseen = int(config.get("unseen_units") or 0)
    if unseen:
        return None, ("%d unit(s) read off; %d more in the room cannot be"
                      " seen, so the room is not known to be off"
                      % (len(lit), unseen)), 0
    return "off", "%d unit(s) read" % len(lit), 0
