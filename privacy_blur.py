import cv2

from ac_config import AC_UNITS

# YOLOv8 (COCO) class IDs
PERSON = 0
TV_MONITOR = 62
LAPTOP = 63
KEYBOARD = 66
CELL_PHONE = 67
BLUR_CLASSES = [PERSON, TV_MONITOR, LAPTOP, KEYBOARD, CELL_PHONE]

DETECT_CONF = 0.25     # lower = blur more (but more false boxes)

# Which weights find the people: the "small" model, not the "nano" one, since
# 11 November. On that day's field audit, run over the same frames: Creative
# Room under its purple light, 0 people found by nano and 3 by small; Squat
# Wolf Room 0, 1 and 2 (there were 2); Room 4, 1 and 4; Marketing, 3 and 6.
# Small also stopped seeing the cafe's shoe rack as a person. It is about two
# and a half times the work per frame, which on the laptop is seconds a
# cycle, not minutes. Set ENERGYCAM_DETECTOR=yolov8n.pt in .env to go back
# if a slower machine cannot keep up. Downloads itself once (22 MB).
import os as _os
DETECTOR = _os.getenv("ENERGYCAM_DETECTOR", "yolov8s.pt")

# How much two boxes of the same class may overlap before one is thrown away.
# This is the knob for a person counted twice, and it is not the confidence
# knob. Confidence decides how faint a detection may be, so raising it to clear
# a duplicate also discards the far-off, half-hidden person the room most needs
# seen -- trading a harmless over-count for the one error that matters. This
# only ever removes a box sitting on top of another box.
DETECT_IOU = 0.7       # ultralytics' own default
DETECT_IMGSZ = 1280    # high resolution catches small/far screens (snapshots are rare, so speed is fine)

# Fixed areas to ALWAYS blur (x1, y1, x2, y2) in full-resolution pixels.
# Use zone_picker.py to draw them (e.g. wall TV, whiteboard, glass door).
FIXED_ZONES = []

PADDING = 15        # box ke charon taraf thoda extra blur
BLOCKS_ACROSS = 8   # jitna kam number, utna strong blur

# OPTIONAL strict privacy: also pixelate the WHOLE picture lightly so text on any
# screen/whiteboard the AI missed is unreadable (AC units stay sharp). Off by
# default because the snapshot becomes hard to read; use FIXED_ZONES instead.
BACKGROUND_PIXELATE = False
BACKGROUND_BLOCKS_ACROSS = 96   # lower = blurrier picture
KEEP_AC_SHARP = True
AC_SHARP_PADDING = 40


def _pixelate(img, blocks_across):
    h, w = img.shape[:2]
    bx = max(1, min(blocks_across, w))
    by = max(1, round(bx * h / w))
    small = cv2.resize(img, (bx, by), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def _blur_region(frame, x1, y1, x2, y2):
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1 - PADDING), max(0, y1 - PADDING)
    x2, y2 = min(w, x2 + PADDING), min(h, y2 + PADDING)
    if x2 - x1 <= 0 or y2 - y1 <= 0:
        return
    frame[y1:y2, x1:x2] = _pixelate(frame[y1:y2, x1:x2], BLOCKS_ACROSS)


def _ac_zones(frame):
    """Rectangles around each AC (LED + flap) that stay sharp."""
    h, w = frame.shape[:2]
    zones = []
    for cfg in AC_UNITS.values():
        xs = [cfg["led_roi"][0], cfg["led_roi"][2], cfg["flap_roi"][0], cfg["flap_roi"][2]]
        ys = [cfg["led_roi"][1], cfg["led_roi"][3], cfg["flap_roi"][1], cfg["flap_roi"][3]]
        x1, y1 = max(0, min(xs) - AC_SHARP_PADDING), max(0, min(ys) - AC_SHARP_PADDING)
        x2, y2 = min(w, max(xs) + AC_SHARP_PADDING), min(h, max(ys) + AC_SHARP_PADDING)
        if x2 > x1 and y2 > y1:
            zones.append((x1, y1, x2, y2))
    return zones


def _mostly_inside_ac(x1, y1, x2, y2, ac_zones, ratio=0.5):
    area = max(1, (x2 - x1) * (y2 - y1))
    for (ax1, ay1, ax2, ay2) in ac_zones:
        ix = max(0, min(x2, ax2) - max(x1, ax1))
        iy = max(0, min(y2, ay2) - max(y1, ay1))
        if ix * iy / area >= ratio:
            return True
    return False


def count_people(frame, model, conf=None, imgsz=None, iou=None):
    """How many people this frame contains, at the same confidence used for blurring.

    The blur step and the occupancy step used to disagree: anything detected at
    DETECT_CONF was blurred, but the room only counted as occupied at a higher
    threshold, so a person could be pixelated in a snapshot captioned 'room empty'.
    unified_system calls this before sending such an alert. If a person is visible
    enough to need blurring, the room is not empty.

    imgsz trades accuracy for speed. The default is high because snapshots are
    rare and a small far-off screen has to be caught. The room loop passes a
    lower one: it is looking for people, not phone screens, and it has tens of
    cameras to get through before any of the counts mean anything.
    """
    return len(people_boxes(frame, model, conf, imgsz, iou))


def people_boxes(frame, model, conf=None, imgsz=None, iou=None):
    """The same detections, as (x1, y1, x2, y2, confidence) instead of a count.

    A count tells you a room has somebody in it. It does not tell you WHERE
    the somebody is, which is the only thing that helps when a room insists it
    has one person in it all night: a count cannot be argued with, a box drawn
    on the picture can. Rooms that need a false detection filtered out, and
    check_room.py which draws them, both work from this.
    """
    results = model(frame, classes=[PERSON], conf=conf or DETECT_CONF,
                    imgsz=imgsz or DETECT_IMGSZ, iou=iou or DETECT_IOU,
                    verbose=False)
    boxes = results[0].boxes
    out = []
    for xyxy, score in zip(boxes.xyxy.tolist(), boxes.conf.tolist()):
        x1, y1, x2, y2 = (int(round(v)) for v in xyxy)
        out.append((x1, y1, x2, y2, float(score)))
    return out



def anonymize(frame, model, conf=None):
    """Returns a COPY of the frame with people, screens, keyboards, phones and
    fixed zones blurred. The rest of the room stays clear."""
    out = frame.copy()
    results = model(out, classes=BLUR_CLASSES, conf=conf or DETECT_CONF, imgsz=DETECT_IMGSZ, verbose=False)
    ac_zones = _ac_zones(out)
    for box, cls in zip(results[0].boxes.xyxy.tolist(), results[0].boxes.cls.tolist()):
        x1, y1, x2, y2 = map(int, box)
        # The AI sometimes mistakes an AC unit for a TV/monitor. Never blur an AC
        # because of a non-person box; people are always blurred.
        if int(cls) != PERSON and _mostly_inside_ac(x1, y1, x2, y2, ac_zones):
            continue
        _blur_region(out, x1, y1, x2, y2)
    for (x1, y1, x2, y2) in FIXED_ZONES:
        _blur_region(out, x1, y1, x2, y2)

    if not BACKGROUND_PIXELATE:
        return out
    final = _pixelate(out, BACKGROUND_BLOCKS_ACROSS)
    if KEEP_AC_SHARP:
        for (x1, y1, x2, y2) in ac_zones:
            final[y1:y2, x1:x2] = out[y1:y2, x1:x2]   # people over an AC stay strongly blurred
    return final
