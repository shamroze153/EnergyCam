import cv2

# YOLOv8 (COCO) class IDs
PERSON = 0
TV_MONITOR = 62
LAPTOP = 63
CELL_PHONE = 67
BLUR_CLASSES = [PERSON, TV_MONITOR, LAPTOP, CELL_PHONE]

# Fixed areas to ALWAYS blur (x1, y1, x2, y2) - baad mein bharenge
FIXED_ZONES = []

PADDING = 15        # box ke charon taraf thoda extra blur
BLOCKS_ACROSS = 8   # jitna kam number, utna strong blur


def _blur_region(frame, x1, y1, x2, y2):
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1 - PADDING), max(0, y1 - PADDING)
    x2, y2 = min(w, x2 + PADDING), min(h, y2 + PADDING)
    bw, bh = x2 - x1, y2 - y1
    if bw <= 0 or bh <= 0:
        return
    roi = frame[y1:y2, x1:x2]
    bx = BLOCKS_ACROSS
    by = max(1, round(BLOCKS_ACROSS * bh / bw))
    small = cv2.resize(roi, (bx, by), interpolation=cv2.INTER_LINEAR)
    frame[y1:y2, x1:x2] = cv2.resize(small, (bw, bh), interpolation=cv2.INTER_NEAREST)


def anonymize(frame, model, conf=0.25):
    """Returns a COPY of the frame with people, screens and fixed zones blurred."""
    out = frame.copy()
    results = model(out, classes=BLUR_CLASSES, conf=conf, imgsz=640, verbose=False)
    for box in results[0].boxes.xyxy.tolist():
        x1, y1, x2, y2 = map(int, box)
        _blur_region(out, x1, y1, x2, y2)
    for (x1, y1, x2, y2) in FIXED_ZONES:
        _blur_region(out, x1, y1, x2, y2)
    return out