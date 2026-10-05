import cv2

from ac_config import AC_UNITS

# YOLOv8 (COCO) class IDs
PERSON = 0
TV_MONITOR = 62
LAPTOP = 63
KEYBOARD = 66
CELL_PHONE = 67
BLUR_CLASSES = [PERSON, TV_MONITOR, LAPTOP, KEYBOARD, CELL_PHONE]

# Detection for blurring is deliberately MORE sensitive than for counting:
# blurring a chair by mistake is fine, missing a screen is not.
DETECT_CONF = 0.15     # low = blur more
DETECT_IMGSZ = 1280    # high resolution catches small/far screens (snapshots are rare, so speed is fine)

# Fixed areas to ALWAYS blur (x1, y1, x2, y2) in full-resolution pixels.
# Use zone_picker.py to draw them (e.g. wall TV, whiteboard, glass door).
FIXED_ZONES = []

PADDING = 15        # box ke charon taraf thoda extra blur
BLOCKS_ACROSS = 8   # jitna kam number, utna strong blur

# STRICT PRIVACY: after the strong blur above, pixelate the WHOLE picture lightly
# so text on any screen/whiteboard/paper the AI missed is unreadable. The room
# layout stays visible (enough to see it is empty) and the AC units stay sharp
# so the receiver can see the AC is on.
BACKGROUND_PIXELATE = True
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


def anonymize(frame, model, conf=None):
    """Returns a COPY of the frame with people, screens, keyboards, phones and
    fixed zones strongly blurred, and (strict mode) everything else lightly
    pixelated except the AC units."""
    out = frame.copy()
    results = model(out, classes=BLUR_CLASSES, conf=conf or DETECT_CONF, imgsz=DETECT_IMGSZ, verbose=False)
    for box in results[0].boxes.xyxy.tolist():
        x1, y1, x2, y2 = map(int, box)
        _blur_region(out, x1, y1, x2, y2)
    for (x1, y1, x2, y2) in FIXED_ZONES:
        _blur_region(out, x1, y1, x2, y2)

    if not BACKGROUND_PIXELATE:
        return out
    final = _pixelate(out, BACKGROUND_BLOCKS_ACROSS)
    if KEEP_AC_SHARP:
        for (x1, y1, x2, y2) in _ac_zones(out):
            final[y1:y2, x1:x2] = out[y1:y2, x1:x2]   # people over an AC stay strongly blurred
    return final
