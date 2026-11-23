"""Following the Progress employees round every 140-H camera, from the loop.

Shamroze, 23 Nov: "if they got up from the seat, where did they go? You
have every camera at 140-H -- track them on all of them. Where there is no
camera, that is the restroom. Make their whole 12-hour cycle."

The loop already looks at every camera every pass (about 4-5 minutes), so
this rides on it and opens no camera of its own. For each camera's people
(room_loop.examine, beside note_seats) it does two things:

  * on an employee's own desk camera: is somebody at the desk, and doing
    what (desk_activity: computer / phone / talking)? While they sit there
    it learns what they are wearing today -- a colour signature of the
    shirt and of the trousers -- afresh each day;
  * on every other 140-H camera: does anybody there look like an employee
    who has a signature today? The closest look-alike above MATCH_MIN is
    written down with its score.

No face is used, nothing is recognised beyond "dressed like P3 today".
progress_day() later puts each pass together: at the desk (and what
doing), else seen somewhere (the place's kind: meeting, cafe, smoking,
prayer, outside, corridors, another office, their own room), else "not on
any camera" -- the restroom or a room without one -- between first in and
last out.

Written: progress/<date>.csv (numbers) and, for checking by eye and for
the day's video, small crops in frames/progress/<date>/<code>/ -- this
machine only, both git-ignored, both let go after KEEP_DAYS. Never a room
in its private hours (no frame of it reaches the loop), never 141.
"""
import os
import time
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np

import desk_activity as da
import progress_data as pdx
# The day's assembly and the kinds of place live in progress_data, which
# the dashboard reads without OpenCV; this module is the loop's half.
from progress_data import (AT_DESK, CROPS, KINDS, PLACES,  # noqa: F401
                           SEEN_MIN, place_of)

PKT = timezone(timedelta(hours=5))
OUT = pdx.ACTIVITY
KEEP_DAYS = 7
CAMPUS_RECORDERS = {"nvr1", "nvr4", "dvr2", "xvr3"}     # 140-H

# Looking for the employees on the other cameras is OFF. 23 Nov, tested on
# the day's kept frames before turning it on: by shirt colour each
# employee matched themselves at their desk at 0.77-0.87 -- but one
# matched a stranger in another department at 0.77, two in dark T-shirts
# each other at 0.84, and one their own second camera (another angle on
# the same desk, the same minute, side on in dim light) at only
# 0.28-0.43. A place found that way would be invented as often as found.
# The plumbing stays (sightings, kinds of place, the day's assembly) for a
# re-identification model trained for it, checked by eye before it is
# switched on.
TRACK_ELSEWHERE = False
# A look-alike this close or closer is written down as a sighting; the
# day's assembly takes, per pass, the closest one over SEEN_MIN.
MATCH_MIN = 0.55
SAVE_MIN = 0.62          # sightings worth a crop to check by eye
MIN_BOX_H = 70           # px: smaller people are too few pixels to compare

_cfg = {"mtime": None, "people": []}
_sig = {}            # (day, code) -> {"up": hist, "n": int}


def _people():
    """progress.yaml's people, read again when the file changes."""
    try:
        m = os.path.getmtime(pdx.CONFIG)
    except OSError:
        return []
    if m != _cfg["mtime"]:
        _cfg["mtime"] = m
        _cfg["people"] = (pdx.load() or {}).get("people") or []
    return _cfg["people"]


def _hist(hsv):
    """Colour of a patch, little moved by how bright the room is: hue and
    saturation of the coloured pixels, and for the grey ones (dark shirts,
    white shirts -- most of an office) only light, mid or dark."""
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    ok = ((v > 30) & (v < 240)).astype(np.uint8)
    colour = (ok & (s >= 50)).astype(np.uint8)
    grey = (ok & (s < 50)).astype(np.uint8)
    hc = cv2.calcHist([hsv], [0, 1], colour, [12, 3], [0, 180, 50, 256])
    hg = cv2.calcHist([hsv], [2], grey, [3], [30, 240])
    h = np.concatenate([hc.ravel(), hg.ravel()]).astype(np.float32)
    total = float(h.sum())
    return h / total if total > 0 else None


def signature(frame, box):
    """The colour of a person's shirt: the middle of the top of their box
    (the bottom of a seated person's box is chair and desk, 23 Nov), or
    None for a box too small to tell."""
    x1, y1, x2, y2 = (int(round(float(v))) for v in box[:4])
    h, w = y2 - y1, x2 - x1
    if h < MIN_BOX_H or w < 20:
        return None
    H, W = frame.shape[:2]
    cx1, cx2 = max(0, x1 + int(0.22 * w)), min(W, x2 - int(0.22 * w))
    ya, yb = max(0, y1 + int(0.15 * h)), min(H, y1 + int(0.45 * h))
    patch = frame[ya:yb, cx1:cx2]
    if patch.size == 0:
        return None
    up = _hist(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV))
    return None if up is None else {"up": up}


def similarity(a, b):
    """0-1: how alike two shirts are (1 - Bhattacharyya distance)."""
    if not a or not b:
        return 0.0
    return float(max(0.0, 1.0 - cv2.compareHist(
        a["up"], b["up"], cv2.HISTCMP_BHATTACHARYYA)))


def learn(day, code, sig, weight=0.2):
    """Fold a desk sighting into the employee's signature for the day."""
    if sig is None:
        return
    cur = _sig.get((day, code))
    if cur is None:
        _sig[(day, code)] = {"up": sig["up"].copy(), "n": 1}
        return
    cur["up"] = (1 - weight) * cur["up"] + weight * sig["up"]
    cur["n"] += 1


def _write(day, rows, folder=None):
    folder = folder or OUT
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, day + ".csv")
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as fh:
        if new:
            fh.write("time,code,kind,state,room,recorder,channel,score,"
                     "x1,y1,x2,y2\n")
        for r in rows:
            fh.write("%s,%s,%s,%s,\"%s\",%s,%d,%.3f,%d,%d,%d,%d\n" % r)
    if new:
        _forget_old(folder)


def _forget_old(folder):
    cutoff = time.time() - KEEP_DAYS * 86400
    for base in (folder, CROPS):
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            p = os.path.join(base, name)
            try:
                if os.path.getmtime(p) < cutoff:
                    if os.path.isdir(p):
                        import shutil
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        os.remove(p)
            except OSError:
                pass


def _crop(frame, box, path, pad=0.25, height=320):
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    w, h = x2 - x1, y2 - y1
    H, W = frame.shape[:2]
    X1, Y1 = int(max(0, x1 - pad * w)), int(max(0, y1 - pad * h))
    X2, Y2 = int(min(W, x2 + pad * w)), int(min(H, y2 + pad * h))
    c = frame[Y1:Y2, X1:X2]
    if c.size == 0:
        return
    c = cv2.resize(c, (max(1, int(height * c.shape[1] / c.shape[0])), height))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, c, [cv2.IMWRITE_JPEG_QUALITY, 80])


def desk_crop(frame, seat, path, share=0.30, size=480):
    """The same square round the desk every pass, sitter or not -- the
    frames of the day's video (progress_video.py)."""
    H, W = frame.shape[:2]
    side = int(share * W)
    x, y = (int(float(v)) for v in seat)
    X1 = int(min(max(0, x - side // 2), max(0, W - side)))
    Y1 = int(min(max(0, y - int(0.75 * side)), max(0, H - side)))
    c = frame[Y1:Y1 + side, X1:X1 + side]
    if c.size == 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, cv2.resize(c, (size, size)),
                [cv2.IMWRITE_JPEG_QUALITY, 80])


def observe(room, key, frame, boxes, model=None, now=None):
    """One camera's counted people this pass (room_loop.examine). Never
    raises: a pass must not stop for this."""
    try:
        _observe(room, key, frame, boxes, model, now)
    except Exception:                                       # noqa: BLE001
        pass


def _observe(room, key, frame, boxes, model, now):
    if frame is None or key[0] not in CAMPUS_RECORDERS:
        return
    people = _people()
    if not people:
        return
    now = now or datetime.now(PKT)
    day, hms = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    persons = [(da.PERSON, float(b[4]) if len(b) > 4 else 1.0,
                float(b[0]), float(b[1]), float(b[2]), float(b[3]))
               for b in boxes]
    rows = []
    taken = set()
    for p in people:
        if (p["recorder"], int(p["channel"])) != (key[0], int(key[1])):
            continue
        me = da.employee(persons, [float(v) for v in p["seat"]],
                         frame.shape[1])
        state = "away"
        if me is not None:
            taken.add(id(me))
            phone = da.phone_near([], me)
            if phone is None and model is not None:
                phone = da.phone_close_look(frame, me, model)
            guest = da.visitor(persons, me)
            state = "phone" if phone else ("talking" if guest
                                           else "computer")
            learn(day, p["code"], signature(frame, me[2:]))
        rows.append((hms, p["code"], "desk", state, room, key[0],
                     int(key[1]), 1.0 if me is not None else 0.0)
                    + (tuple(int(v) for v in me[2:]) if me is not None
                       else (0, 0, 0, 0)))
        desk_crop(frame, p["seat"], os.path.join(
            CROPS, day, p["code"], "%s_desk_%s.jpg"
            % (hms.replace(":", ""), state)))
    # Everybody else on this camera, against every employee with a
    # signature today.
    known = {p["code"]: _sig.get((day, p["code"])) for p in people}
    known = {c: s for c, s in known.items() if s is not None}
    if known and TRACK_ELSEWHERE:
        for b in persons:
            if id(b) in taken:
                continue
            sig = signature(frame, b[2:])
            if sig is None:
                continue
            for code, s in known.items():
                score = similarity(sig, s)
                if score < MATCH_MIN:
                    continue
                rows.append((hms, code, "seen", "", room, key[0],
                             int(key[1]), score)
                            + tuple(int(v) for v in b[2:]))
                if score >= SAVE_MIN:
                    _crop(frame, b[2:], os.path.join(
                        CROPS, day, code, "%s_seen_%.0f_%s_%s%02d.jpg"
                        % (hms.replace(":", ""), 100 * score,
                           "".join(ch if ch.isalnum() else "_"
                                   for ch in room)[:28],
                           key[0], int(key[1]))))
    if rows:
        _write(day, rows)


# The day's assembly is progress_data.day_activity (the dashboard reads
# it without OpenCV); these names are kept for the loop's side.
load_day = pdx.load_activity
progress_day = pdx.day_activity


def backfill(day, people, model, frames_dir=None, folder=None):
    """Activity rows (and desk crops) for a day from the frames kept every
    ten minutes (frames/ac_keep), for days before the loop wrote its own.
    Returns how many frames were read."""
    import glob
    frames_dir = frames_dir or os.path.join("frames", "ac_keep", day)
    rows, n = [], 0
    for p in people:
        pat = os.path.join(frames_dir, "*", "*__%s_ch%02d.jpg"
                           % (p["recorder"], int(p["channel"])))
        for path in sorted(glob.glob(pat)):
            frame = cv2.imread(path)
            if frame is None:
                continue
            stamp = datetime.fromtimestamp(os.path.getmtime(path), PKT)
            if stamp.strftime("%Y-%m-%d") != day:
                continue
            hms = stamp.strftime("%H:%M:%S")
            r = da.classify(frame, p, model)
            n += 1
            me = r["employee"]
            rows.append((hms, p["code"], "desk", r["state"], p["department"],
                         p["recorder"], int(p["channel"]),
                         1.0 if me is not None else 0.0)
                        + (tuple(int(v) for v in me[2:]) if me is not None
                           else (0, 0, 0, 0)))
            desk_crop(frame, p["seat"], os.path.join(
                CROPS, day, p["code"], "%s_desk_%s.jpg"
                % (hms.replace(":", ""), r["state"])))
    rows.sort()
    if rows:
        _write(day, rows, folder)
    return n
