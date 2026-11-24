"""What an employee is doing at their own desk, from one camera picture.

Shamroze, 23 Nov: "how many hours on the computer, how many on the mobile,
how many talking". One frame of the employee's desk camera gives one of:

    "computer"  at the desk, nothing else seen: at the screen / desk work
    "phone"     at the desk with a phone in or by their hands
    "talking"   at the desk with somebody standing at it
    "away"      nobody at the desk

From the detector the loop already runs (YOLOv8, COCO): people, and the
small things -- a cell phone, a laptop, a screen. A phone is looked for
twice: in the whole picture, and again in the employee's own box blown up
to twice its size, where a phone of a few pixels becomes findable.

What it cannot tell, and does not pretend to: whether the screen shows
work, whether a call is about work, whether talking is a meeting. A
neighbour sitting at the next desk is not "talking" -- only somebody
standing at the desk is (a seated neighbour is the same height as the
employee in the picture; a standing visitor is taller). Each sample is a
moment; hours come from many moments (progress_watch.py, every few
minutes), never from one.
"""
import cv2
import numpy as np

PERSON = 0
LAPTOP = 63
TV = 62
KEYBOARD = 66
PHONE = 67
THINGS = [PERSON, TV, LAPTOP, KEYBOARD, PHONE]

STATES = ("computer", "phone", "talking", "away")

CONF = 0.15          # low: a phone is small and a visitor half hidden
PERSON_CONF = 0.30   # but a person needs more than that to be a person
# A box whose bottom is this far from the desk's point (as progress_data:
# a share of the frame's width, or of the box's own height) sits there.
SEAT_RADIUS = 0.035
SEAT_REACH = 0.3
# A visitor is somebody whose box touches the employee's, widened by this
# share of its size, and who stands: this much taller, head above theirs.
VISIT_PAD = 0.15
VISIT_TALLER = 1.15


def detect(frame, model, imgsz=1280, conf=CONF, classes=THINGS):
    """[(cls, conf, x1, y1, x2, y2)] in the frame's pixels."""
    out = []
    res = model(frame, classes=classes, conf=conf, imgsz=imgsz,
                verbose=False)
    for r in res:
        for b in r.boxes:
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
            out.append((int(b.cls[0]), float(b.conf[0]), x1, y1, x2, y2))
    return out


def employee(persons, seat, width):
    """The person box sitting at the desk: its bottom nearest the desk's
    point, within reach. None when nobody is there."""
    x, y = seat
    best = None
    for p in persons:
        _, _, x1, y1, x2, y2 = p
        h = y2 - y1
        reach = max(SEAT_RADIUS * width, SEAT_REACH * h)
        d = ((x1 + x2) / 2.0 - x) ** 2 + (y2 - y) ** 2
        if d <= reach * reach and (best is None or d < best[0]):
            best = (d, p)
    return best[1] if best else None


def _inside(point, box, widen=0.15):
    px, py = point
    _, _, x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return (x1 - widen * w <= px <= x2 + widen * w
            and y1 - widen * h <= py <= y2 + widen * h)


def phone_near(things, box):
    """A phone whose middle is in (or just round) the employee's box."""
    for t in things:
        if t[0] == PHONE and _inside(((t[2] + t[4]) / 2, (t[3] + t[5]) / 2),
                                     box):
            return t
    return None


POSE_MODEL = "yolov8s-pose.pt"
_pose = {"model": None, "failed": False}
# COCO keypoints: 0 nose, 1-2 eyes, 3-4 ears, 5-6 shoulders, 9-10 wrists.
KP_CONF = 0.4
EAR_REACH = 0.6          # a wrist this close to an ear or the nose, in
                         # face widths, is a hand held to the head: a call


def pose_model():
    """The pose network (yolov8s-pose, loaded once), or None."""
    if _pose["model"] is None and not _pose["failed"]:
        try:
            import os
            from ultralytics import YOLO
            if not os.path.exists(POSE_MODEL):
                raise FileNotFoundError(POSE_MODEL)
            _pose["model"] = YOLO(POSE_MODEL)
        except Exception:                                   # noqa: BLE001
            _pose["failed"] = True
    return _pose["model"]


def on_a_call(keypoints):
    """A hand held to the head (one person's 17 COCO keypoints, rows of
    x, y, conf): a phone at the ear, often hidden by the hand itself --
    the call the phone detector cannot see (24 Nov)."""
    kp = keypoints
    head = [kp[i] for i in (0, 3, 4) if kp[i][2] >= KP_CONF]
    hands = [kp[i] for i in (9, 10) if kp[i][2] >= KP_CONF]
    if not head or not hands:
        return False
    if kp[3][2] >= KP_CONF and kp[4][2] >= KP_CONF:
        face = abs(kp[3][0] - kp[4][0])
    elif kp[5][2] >= KP_CONF and kp[6][2] >= KP_CONF:
        face = 0.45 * abs(kp[5][0] - kp[6][0])
    else:
        return False
    face = max(face, 8.0)
    for hx, hy, _ in hands:
        for px, py, _ in head:
            if ((hx - px) ** 2 + (hy - py) ** 2) ** 0.5 <= EAR_REACH * face:
                return True
    return False


def hand_at_head(frame, box, scale=2.0):
    """The employee's box, blown up, through the pose network: True when a
    hand is held to the head (on_a_call). None without the network."""
    model = pose_model()
    if model is None:
        return None
    _, _, x1, y1, x2, y2 = box
    h, w = frame.shape[:2]
    pad_x, pad_y = 0.15 * (x2 - x1), 0.1 * (y2 - y1)
    X1, Y1 = int(max(0, x1 - pad_x)), int(max(0, y1 - pad_y))
    X2, Y2 = int(min(w, x2 + pad_x)), int(min(h, y2 + pad_y))
    crop = frame[Y1:Y2, X1:X2]
    if crop.size == 0:
        return None
    import cv2
    crop = cv2.resize(crop, None, fx=scale, fy=scale)
    res = model(crop, conf=0.3, verbose=False)
    best = None
    for r in res:
        if r.keypoints is None or r.boxes is None or not len(r.boxes):
            continue
        confs = r.boxes.conf.tolist()
        i = max(range(len(confs)), key=lambda k: confs[k])
        best = r.keypoints.data[i].tolist()
    return on_a_call(best) if best else None


def close_look(frame, box, model, scale=2.0):
    """The employee's box, blown up, searched once for a phone AND for a
    screen (laptop, monitor, keyboard): (phone box or None, screen seen).
    The same one inference the phone look took before (24 Nov)."""
    _, _, x1, y1, x2, y2 = box
    h, w = frame.shape[:2]
    pad_x, pad_y = 0.15 * (x2 - x1), 0.1 * (y2 - y1)
    X1, Y1 = int(max(0, x1 - pad_x)), int(max(0, y1 - pad_y))
    X2, Y2 = int(min(w, x2 + pad_x)), int(min(h, y2 + pad_y))
    crop = frame[Y1:Y2, X1:X2]
    if crop.size == 0:
        return None, False
    import cv2
    big = cv2.resize(crop, None, fx=scale, fy=scale,
                     interpolation=cv2.INTER_CUBIC)
    found = detect(big, model, imgsz=max(320, min(1280, max(big.shape[:2]))),
                   conf=0.25, classes=[PHONE, LAPTOP, TV, KEYBOARD])
    phones = [t for t in found if t[0] == PHONE]
    screen = any(t[0] in (LAPTOP, TV, KEYBOARD) for t in found)
    if not phones:
        return None, screen
    c, s, a, b, cc, d = max(phones, key=lambda t: t[1])
    return (c, s, X1 + a / scale, Y1 + b / scale, X1 + cc / scale,
            Y1 + d / scale), screen


def phone_close_look(frame, box, model, scale=2.0):
    """The employee's box, blown up, searched for a phone alone."""
    _, _, x1, y1, x2, y2 = box
    h, w = frame.shape[:2]
    pad_x, pad_y = 0.15 * (x2 - x1), 0.1 * (y2 - y1)
    X1, Y1 = int(max(0, x1 - pad_x)), int(max(0, y1 - pad_y))
    X2, Y2 = int(min(w, x2 + pad_x)), int(min(h, y2 + pad_y))
    crop = frame[Y1:Y2, X1:X2]
    if crop.size == 0:
        return None
    big = cv2.resize(crop, None, fx=scale, fy=scale,
                     interpolation=cv2.INTER_CUBIC)
    found = detect(big, model, imgsz=max(320, min(1280, max(big.shape[:2]))),
                   conf=0.25, classes=[PHONE])
    if not found:
        return None
    c, s, a, b, cc, d = max(found, key=lambda t: t[1])
    return (c, s, X1 + a / scale, Y1 + b / scale, X1 + cc / scale,
            Y1 + d / scale)


STANDING = 2.0          # a box this much taller than wide is standing


def assign_desks(persons, seats, width, reach_of=None):
    """One person, one desk (24 Nov, checked by eye on 62 desk pictures:
    17 empty desks read as sat at, a neighbour counted at two desks).
    persons: [(cls, conf, x1, y1, x2, y2)]; seats: {key: (x, y)}. Each
    person goes to the nearest seat within its reach (SEAT_RADIUS of the
    width or SEAT_REACH of the box's height), nearest pairs first; a seat
    with nobody left near is empty. Returns {key: person or None}."""
    import progress_data as pdx
    pairs = []
    for i, p in enumerate(persons):
        _, _, x1, y1, x2, y2 = p
        r = max(pdx.SEAT_RADIUS * width, pdx.SEAT_REACH * (y2 - y1))
        bx, by = (x1 + x2) / 2.0, y2
        for k, (sx, sy) in seats.items():
            d = ((bx - sx) ** 2 + (by - sy) ** 2) ** 0.5
            if d <= r:
                pairs.append((d / r, i, k))
    out = {k: None for k in seats}
    used = set()
    for _, i, k in sorted(pairs):
        if i in used or out[k] is not None:
            continue
        out[k] = persons[i]
        used.add(i)
    return out


def standing_visitor(persons, box, seated):
    """A visitor at a desk among many: somebody standing (STANDING) who is
    not sitting at another desk (seated: the people assign_desks gave a
    desk), touching the desk's sitter and head above (visitor())."""
    free = [p for p in persons if p is box or (
        not any(p is s for s in seated)
        and (p[5] - p[3]) >= STANDING * max(1.0, p[4] - p[2]))]
    return visitor(free, box)


def visitor(persons, box):
    """Somebody standing at the employee's desk: their box touches the
    employee's (widened a little), they are taller in the picture, and
    their head is above the employee's. 23 Nov, checked by eye: a rule
    of "anybody tall within 60% either side" called P1 "talking" four
    frames running while he typed alone -- a colleague sitting nearer the
    camera looks tall too. Touching, taller and head above is somebody
    standing over the desk."""
    _, _, x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    pad_x, pad_y = VISIT_PAD * w, VISIT_PAD * h
    for p in persons:
        if p is box:
            continue
        _, _, a, b, c, d = p
        touches = (c >= x1 - pad_x and a <= x2 + pad_x
                   and d >= y1 - pad_y and b <= y2 + pad_y)
        if touches and (d - b) >= VISIT_TALLER * h and b < y1:
            return p
    return None


def classify(frame, person, model, things=None):
    """{"state", "employee", "phone", "visitor"} for one frame of the
    employee's desk camera. `person`: a progress.yaml entry (seat)."""
    things = detect(frame, model) if things is None else things
    persons = [t for t in things if t[0] == PERSON and t[1] >= PERSON_CONF]
    width = frame.shape[1]
    me = employee(persons, [float(v) for v in person["seat"]], width)
    out = {"state": "away", "employee": me, "phone": None, "visitor": None}
    if me is None:
        return out
    phone = phone_near(things, me) or phone_close_look(frame, me, model)
    guest = visitor(persons, me)
    out["phone"], out["visitor"] = phone, guest
    out["state"] = "phone" if phone else ("talking" if guest else "computer")
    return out


def draw(frame, result, seat):
    """The frame with what classify() saw drawn on it (for checking by eye;
    such pictures stay on this machine)."""
    img = frame.copy()
    colours = {"employee": (80, 220, 120), "phone": (0, 0, 255),
               "visitor": (255, 160, 0)}
    for key, colour in colours.items():
        t = result.get(key)
        if t:
            cv2.rectangle(img, (int(t[2]), int(t[3])), (int(t[4]), int(t[5])),
                          colour, 3)
    cv2.circle(img, (int(seat[0]), int(seat[1])), 12, (0, 255, 255), 3)
    return img


def crop_around(img, seat, size=520):
    """A square round the desk, for a contact sheet."""
    x, y = (int(v) for v in seat)
    h, w = img.shape[:2]
    X1, Y1 = max(0, x - size // 2), max(0, y - int(size * 0.8))
    X2, Y2 = min(w, X1 + size), min(h, Y1 + size)
    out = img[Y1:Y2, X1:X2]
    return cv2.resize(out, (300, 300)) if out.size else np.zeros(
        (300, 300, 3), np.uint8)
