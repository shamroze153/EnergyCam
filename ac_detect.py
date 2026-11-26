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


def brightness(frame, box):
    """Mean brightness inside the box, 0-255; None for an empty box."""
    x1, y1, x2, y2 = box
    patch = frame[y1:y2, x1:x2]
    if patch.size == 0:
        return None
    if patch.ndim == 3:
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    return float(patch.mean())


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


# The ring round a box that darkness() measures the box against, in pixels.
DARK_RING = 5


def darkness(frame, box, ring=DARK_RING, ref=None, pct=10):
    """The box's darkest tenth against the median of the ring round it.

    A louvre that opens shows the dark inside of the unit between its slats:
    near 0.1-0.5 against the tower round it. Shut, the box is the tower's own
    face: about 1. Unlike contrast() it does not rise when the light changes
    -- light falls on the box and its ring alike. 19 Nov: the 141-C Cafe's
    far tower read "running" 07:05-08:09 with its louvre shut, the ceiling
    lights off and the pink wash of the neon wall on its edge lifting the
    box's contrast into the range of a real open louvre (25-36 against
    31-39); its darkness was 0.86-0.91, open louvres' 0.13-0.47.

    `ref` ([x1, y1, x2, y2], a unit's `dark_ref`) measures the box against
    that region of the unit's own face instead of the ring. For a box at the
    unit's edge the ring is half whatever stands behind the unit. 23 Nov:
    the cafe's tower 6 ran all evening and read "off" 19:17-19:44 -- the
    doorway behind it went dark at nightfall, the ring fell from ~190 to
    ~95 and its open louvre read 0.71-0.76 against 0.60; somebody standing
    beside it at 19:57 lifted the ring and it read running again. By day
    the bright doorway did the reverse, a shut louvre down to 0.62.

    `pct` (a unit's `dark_pct`) is which part of the box is measured: the
    darkest tenth by default, the median (50) for a flap whose open slot
    fills the box. 26 Nov: 140-H Reception's split read "running" at 05:13
    on 24 Nov -- the lights switched on at dawn drew a one-pixel shadow line
    under the shut flap, and the darkest tenth of the box was that line
    (0.41; open reads 0.11-0.42). The box's median tells them apart: open
    0.40-0.62, shut 0.80-0.96, the dawn frame 0.88.
    """
    x1, y1, x2, y2 = box
    if frame.ndim == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    patch = frame[y1:y2, x1:x2].astype(np.float32)
    if patch.size == 0:
        return None
    if ref is not None:
        rx1, ry1, rx2, ry2 = (int(v) for v in ref)
        face = frame[max(0, ry1):ry2, max(0, rx1):rx2]
        if face.size == 0:
            return None
        return float(np.percentile(patch, pct)
                     / max(1.0, float(np.median(face))))
    ox1, oy1 = max(0, x1 - ring), max(0, y1 - ring)
    outer = frame[oy1:y2 + ring, ox1:x2 + ring].astype(np.float32)
    keep = np.ones(outer.shape, dtype=bool)
    keep[y1 - oy1:y2 - oy1, x1 - ox1:x2 - ox1] = False
    if not keep.any():
        return None
    return float(np.percentile(patch, pct)
                 / max(1.0, float(np.median(outer[keep]))))


def slats(frame, box):
    """How many slats show in the box: rows darker than the rows either side
    of them by a clear step (6 levels, or 6% of the box's median row),
    counted down the box.

    An open tower louvre is a ladder of dark gaps between its vanes: four or
    five down the 141-C Cafe's tower 3 and 6 boxes, five down tower 4's. A
    head in front of a tower is dark too, and contrasty at its edge, but it
    is one dark patch, not a ladder: 26 Nov, from the kept frames, a man's
    head in front of tower 3 (25 Nov 21:04) and of tower 6 (23:48) read
    0.43 and 0.45 dark with the louvres shut behind them, and the page said
    "running"; they count 1 and 0 here, every open louvre of those towers
    over 24-26 Nov 3 or more. A unit's `slats_min` asks for it.
    """
    x1, y1, x2, y2 = box
    if frame.ndim == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    patch = frame[y1:y2, x1:x2].astype(np.float32)
    if patch.size == 0 or patch.shape[0] < 5:
        return 0
    rows = patch.mean(axis=1)
    step = max(6.0, 0.06 * float(np.median(rows)))
    count = 0
    for i in range(1, len(rows) - 1):
        if rows[i] < rows[i - 1] and rows[i] <= rows[i + 1]:
            left = rows[max(0, i - 2):i].max()
            right = rows[i + 1:i + 3].max()
            if min(left, right) - rows[i] >= step:
                count += 1
    return count


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
    lit, astray, why = _read_block(frame, config)
    if why:
        return None, why, None
    return _verdict(lit, astray, int(config.get("unseen_units") or 0))


def blocks(config, recorder=None):
    """A room's calibration camera by camera: ((recorder, channel), block).

    The room's own block first, then any `also:` -- 141-C Cafe reads towers
    1-5 on ch 14 and tower 6, which ch 14 sees only side on, on ch 2
    (Shamroze, 13 Nov). Each block carries its own frame size, lighting and
    units, because each is a different camera's picture.
    """
    main = {k: v for k, v in config.items() if k != "also"}
    out = [((main.get("recorder", recorder), int(main.get("channel", -1))),
            main)]
    for extra in config.get("also") or []:
        out.append(((extra.get("recorder", main.get("recorder", recorder)),
                     int(extra["channel"])), extra))
    return out


def all_units(config):
    """Every unit a room's calibration reads, on whichever camera."""
    return [u for _, b in blocks(config) for u in (b.get("units") or [])]


def read_cameras(frames, room, units=None, recorder=None):
    """read_units over every camera a room's calibration names.

    frames: {(recorder, channel): frame or None}. A camera that sent
    nothing, or whose reading was refused, leaves its units unread -- they
    join the room's unseen ones -- and the others still count. Any unit
    running is the room on; off needs every unit in the room read off.
    """
    units = load_units() if units is None else units
    config = units.get(room)
    if not config:
        return None, "not calibrated", None
    lit, astray, unread, notes = [], [], 0, []
    for key, block in blocks(config, recorder):
        count = len(block.get("units") or [])
        frame = frames.get(key)
        if frame is None:
            unread += count
            notes.append("ch %d sent nothing" % key[1])
            continue
        got, off_view, why = _read_block(frame, block)
        if why:
            unread += count
            notes.append("ch %d: %s" % (key[1], why))
            continue
        lit += got
        astray += off_view
    if not lit and not astray:
        return None, "; ".join(notes) or "no usable boxes", None
    state, why, running = _verdict(
        lit, astray, int(config.get("unseen_units") or 0) + unread)
    if notes:
        why += "; " + "; ".join(notes)
    return state, why, running


def _read_block(frame, config):
    """One camera's boxes: (lit, astray, None), or (None, None, why) when
    the picture itself cannot be read -- wrong size, wrong lighting, a box
    off the edge. lit is True/False per unit read; astray the anchor scores
    of the units whose surroundings no longer match."""
    height, width = frame.shape[:2]
    expected = config.get("frame_size")
    if expected and [width, height] != list(expected):
        return None, None, ("frame is %dx%d, the boxes were drawn on %dx%d"
                            % (width, height, expected[0], expected[1]))

    expect = config.get("expect")
    infrared = is_infrared(frame)
    # The other lighting's own calibration, where there is one: a block
    # measured in colour may carry `infrared:` for the night (13 Nov: Finance
    # Room, Room 32 and Room 27 go infrared when the lights go off, and their
    # nights went unread), one measured in infrared `colour:` for the day
    # (Admin Room). Same units, same order, measured in that light.
    if expect in ("colour", "infrared") and infrared != (expect == "infrared"):
        other = "infrared" if infrared else "colour"
        alt = config.get(other)
        if alt:
            alt = dict(alt, expect=other)
            alt.setdefault("frame_size", config.get("frame_size"))
            return _read_block(frame, alt)
    if expect == "infrared" and not infrared:
        return None, None, "camera is in colour; calibrated in infrared"
    if expect == "colour" and infrared:
        return None, None, "camera is in infrared; calibrated in colour"

    lit = []
    # Units whose surroundings no longer match are left unread one by one,
    # and the room is refused only when none of them matches. The cafe on 12
    # Nov: at 20:45 the lights changed, towers 2 and 3 matched 0.17 and 0.31
    # and the whole room went unread all night as "the camera has moved",
    # while towers 1, 4 and 5 still matched 0.70-0.88 and read off plainly.
    # A camera that really moved fails every unit, and is still refused.
    astray = []
    for unit in config.get("units", []):
        # A unit that cannot be read reliably is not read at all (19 Nov:
        # Prompt Cafe's Kenwood on ch 20, side on, no gap between its open
        # and shut readings, "running" a whole night it may not have run).
        # Its camera's frames are still kept for a new calibration, and the
        # room counts it among its unseen units, so it is unknown -- never
        # a guessed on, never an off it did not see.
        if unit.get("unread"):
            continue
        box = unit.get("led_roi")
        threshold = unit.get("led_std_threshold")
        if not box or threshold is None:
            continue
        x1, y1, x2, y2 = box
        if x2 > width or y2 > height or x1 < 0 or y1 < 0:
            return None, None, "a box falls outside the frame"
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
                return None, None, "the view round the box cannot be compared"
            if score < ANCHOR_MATCH:
                astray.append(score)
                continue
        # A face the light has washed out (20 Nov: Marketing's M2 from about
        # 16:30, the unit one flat bright shade, mean ~205, its light unseen
        # whether it runs or not) is left unread -- None, counted among the
        # unseen -- never an "off" nobody saw.
        bright_max = unit.get("bright_max")
        if bright_max is not None:
            mean = brightness(frame, box)
            if mean is not None and mean >= float(bright_max):
                lit.append(None)
                continue
        value = contrast(frame, box)
        if value is None:
            return None, None, "a box is empty"
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
        # A louvre read by its darkness (19 Nov, `dark_max` in
        # ac_units.yaml): running only when the inside shows dark between
        # the slats -- a change of light lifts contrast but not darkness --
        # and the box is not one flat shade (half the contrast threshold at
        # least: a shadow over the whole box is dark too, but even).
        # Measured against the unit's own face (`dark_ref`) where the ring
        # round the box takes in what stands behind the unit.
        dark_max = unit.get("dark_max")
        if dark_max is not None and higher_is_on:
            ref = unit.get("dark_ref")
            if ref is not None:
                rx1, ry1, rx2, ry2 = ref
                if rx2 > width or ry2 > height or rx1 < 0 or ry1 < 0:
                    return None, None, "a box falls outside the frame"
            dark = darkness(frame, box, ref=ref,
                            pct=float(unit.get("dark_pct", 10)))
            # How contrasty the box must be as well: half the threshold,
            # unless the unit names its own (`min_std`, 26 Nov: 141 Room
            # 32's shut flap under a new night light read 0.62 dark, a
            # hair over its line, at contrast 41; open is 52-57).
            need = unit.get("min_std")
            need = threshold / 2.0 if need is None else float(need)
            running = (dark is not None and dark <= float(dark_max)
                       and value >= need)
            # And, for a tower's louvre, a ladder of slats, not one dark
            # patch: somebody's head in front of it (slats() above).
            slats_min = unit.get("slats_min")
            if running and slats_min is not None:
                running = slats(frame, box) >= int(slats_min)
            lit.append(running)
            continue
        lit.append(value >= threshold if higher_is_on
                   else value <= threshold)
    return lit, astray, None


def _verdict(lit, astray, unseen):
    """The room's (state, why, running) from the units read, the ones left
    unread as astray, and the ones no camera reads at all. A None in lit
    is a unit washed out by the light: unread, like an unseen one."""
    blind = sum(1 for x in lit if x is None)
    lit = [x for x in lit if x is not None]
    if not lit:
        if astray:
            return None, ("the camera has moved: the view round the box"
                          " matches the calibrated one only %.2f"
                          % max(astray)), None
        if blind:
            return None, ("the light washes the unit out; unread"
                          if blind == 1 else "the light washes the units out;"
                          " unread"), None
        return None, "no usable boxes", None
    skipped = ("; %d left unread, the view round %s not as calibrated (%s)"
               % (len(astray), "it" if len(astray) == 1 else "them",
                  ", ".join("%.2f" % s for s in astray)) if astray else "")
    if blind:
        skipped += "; %d washed out by the light, unread" % blind
    unseen += blind
    running = sum(1 for x in lit if x)
    # Any unit running means the room is being cooled. A room with two units
    # and one of them on is not an off room.
    if running:
        return "on", "%d unit(s) read%s" % (len(lit), skipped), running
    # The converse does not hold. 141 Learning Center has three units and
    # its camera can read one of them: that one off says nothing about the
    # other two, and calling the room "off" would quietly drop every empty
    # hour they ran from the waste and the alerts. Off is only known when
    # every unit in the room was read.
    unseen += len(astray)
    if unseen:
        return None, ("%d unit(s) read off; %d more in the room cannot be"
                      " seen, so the room is not known to be off%s"
                      % (len(lit), unseen, skipped)), 0
    return "off", "%d unit(s) read" % len(lit), 0
