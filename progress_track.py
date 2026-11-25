"""Following the Progress employees round every 140-H camera, from the loop.

Shamroze, 23 Nov: "if they got up from the seat, where did they go? You
have every camera at 140-H -- track them on all of them. Where there is no
camera, that is the restroom. Make their whole 12-hour cycle."

The loop already looks at every camera every pass (about 4-5 minutes), so
this rides on it and opens no camera of its own. For each camera's people
(room_loop.examine, beside note_seats) it does two things:

  * on an employee's own desk camera: is somebody at the desk, and doing
    what (desk_activity: computer / phone / talking)? While they sit there
    it learns how they look today (reid.py: 512 numbers a picture, from a
    network trained to tell people apart across cameras), afresh each day;
  * on every other 140-H camera: is anybody there -- not sitting at a
    regular seat of an office -- most like one of the employees, by a
    clear margin? That is written down as a possible sighting, with a
    small picture, for somebody to confirm on the Progress tab.

No face is matched, and no name: "looks like P3 today". The day's
assembly (progress_data.day_activity) puts each pass together: at the
desk (and what doing), else at a confirmed sighting's place (meeting,
cafe, smoking, prayer, outside, corridors, another office, their own
room), else "not on any camera" -- the restroom or a room without one --
between first in and last out.

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
import pandas as pd

import desk_activity as da
import faces
import progress_data as pdx
import reid
# The day's assembly and the kinds of place live in progress_data, which
# the dashboard reads without OpenCV; this module is the loop's half.
from progress_data import (AT_DESK, CROPS, KINDS, PLACES,  # noqa: F401
                           place_of)

PKT = timezone(timedelta(hours=5))
OUT = pdx.ACTIVITY
KEEP_DAYS = 7
CAMPUS_RECORDERS = {"nvr1", "nvr4", "dvr2", "xvr3"}     # 140-H

# Following the employees to the other cameras. 23 Nov, first try, shirt
# colour: each employee matched themselves at the desk at 0.77-0.87, but
# a stranger in another department at 0.77, and their own second camera
# (another angle on the same desk, the same minute) at only 0.28-0.43 --
# turned down. Second try, OSNet-AIN (reid.py, trained to tell people
# apart across cameras), on the day's kept frames: an employee's own
# second camera 0.63-0.77, and the strangers above 0.70 were nearly all
# people sitting at their own regular desks elsewhere, or neighbours on
# the employee's own camera. So: nobody at a regular seat in an office
# and nobody on the employee's own desk camera is a candidate; the best
# employee must reach REID_MIN and beat the next by REID_MARGIN. Even
# then one stranger reached 0.80 -- so a sighting is only "possible"
# until somebody confirms it on the Progress tab, and only confirmed
# places are counted in the day's hours (progress_data.day_activity).
TRACK_ELSEWHERE = reid.available()
# Faces (faces.py; HR's permission for these five, 23 Nov): a face clearly
# one employee's names them on any camera and the sighting needs nobody's
# confirming; no face, or an unclear one, leaves the body re-ID to say
# "possible".
FACES_ON = faces.available()
_face_cache = {"stamp": None, "galleries": {}}
REID_MIN = 0.70
REID_MARGIN = 0.03
GALLERY_MAX = 40         # desk sightings kept per employee per day
MIN_BOX_H = reid.MIN_H   # px: smaller people are too few pixels to compare

# Told of every desk look -- f(code, present, at, room, key) -- and every
# sighting -- f(code, room, at, state, score): progress_follow.py, which
# moves the looking round an employee who has left the desk.
ON_DESK = []
ON_SEEN = []

_cfg = {"mtime": None, "people": []}
_gallery = {}            # (day, code) -> [unit vectors from the desk]
_seats = {"day": None, "spots": {}}


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


def learn(day, code, vec):
    """Keep a desk sighting's vector in the employee's gallery for today."""
    if vec is None or not np.any(vec):
        return
    g = _gallery.setdefault((day, code), [])
    g.append(np.asarray(vec, np.float32))
    del g[:-GALLERY_MAX]


def gallery(day, code):
    """The employee's look today: the mean of their desk vectors, as a
    unit vector, or None before they have sat down."""
    g = _gallery.get((day, code))
    if not g:
        return None
    m = np.mean(g, axis=0)
    n = float(np.linalg.norm(m))
    return m / n if n else None


def regular_seats(day):
    """Each camera's seats held on the last working days (seat_map): who
    sits there in an office is its owner, not a visitor."""
    if _seats["day"] == day:
        return _seats["spots"]
    spots = {}
    try:
        import seat_map
        days = [d for d in pdx.working_days(day, 4) if d < day][-3:]
        notes = seat_map.load(days, (9, 21)) if days else None
        if notes is not None and len(notes):
            found = seat_map.seats(
                notes, passes=seat_map.passes_in(days, (9, 21)),
                min_share=0.10)
            for (_, rec, ch), s in found.items():
                spots[(rec, int(ch))] = [(x, y) for x, y, _, _ in s]
    except Exception:                                       # noqa: BLE001
        spots = {}
    _seats.update(day=day, spots=spots)
    return spots


def at_regular_seat(key, box, width, spots):
    """A box whose bottom sits on one of the camera's regular seats."""
    pts = spots.get((key[0], int(key[1])))
    if not pts:
        return False
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    r = max(pdx.SEAT_RADIUS * width, pdx.SEAT_REACH * (y2 - y1))
    bx, by = (x1 + x2) / 2.0, y2
    return any((bx - x) ** 2 + (by - y) ** 2 <= r * r for x, y in pts)


def best_match(vec, galleries):
    """(code, score, margin) of the employee this vector is most like, or
    None when no employee reaches REID_MIN by REID_MARGIN."""
    if vec is None or not np.any(vec) or not galleries:
        return None
    scores = sorted(((float(np.dot(vec, g)), c) for c, g in galleries.items()),
                    reverse=True)
    top, code = scores[0]
    second = scores[1][0] if len(scores) > 1 else -1.0
    if top < REID_MIN or top - second < REID_MARGIN:
        return None
    return code, top, top - second


# Desks outside the offices that somebody works at all day: their sitter is
# that desk's, never a visiting employee. 24 Nov: the receptionist, at her
# desk in 140-H Reception, was matched to P2 twice (0.73, 0.75) -- a
# reception is not an office, so its regular seat was not left out. A share
# of the day cannot tell it from a cafe table (reception 0.29, the cafes'
# busiest tables 0.37), so the rooms are named.
STAFFED = ("140-H Reception",)


def candidates(room, key, persons, width, taken, spots):
    """The people on this camera who may be a visiting employee: not
    already an employee at their desk, big enough to tell, and not
    sitting at a regular seat of an office or a staffed desk (STAFFED)."""
    office = place_of(room) == "office" or room in STAFFED
    out = []
    for b in persons:
        if id(b) in taken or (b[5] - b[3]) < MIN_BOX_H:
            continue
        if office and at_regular_seat(key, b[2:], width, spots):
            continue
        out.append(b)
    return out


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
            if pdx.presence_only(p):
                # The Basement (25 Nov): at the desk is all that is read.
                state = "desk"
            else:
                # One close look finds a phone and a screen (24 Nov); a hand
                # held to the head is a call the phone detector cannot see
                # (pose); with no screen in sight it is "desk", not
                # "computer".
                phone, screen = da.phone_near([], me), True
                if phone is None and model is not None:
                    phone, screen = da.close_look(frame, me, model)
                    if phone is None and da.hand_at_head(frame, me):
                        phone = "call"
                guest = da.visitor(persons, me)
                state = "phone" if phone else ("talking" if guest else (
                    "computer" if screen else "desk"))
            if TRACK_ELSEWHERE:
                learn(day, p["code"], reid.embed(frame, [me[2:]])[0])
            if FACES_ON:
                faces.add_to_gallery(p["code"], faces.of_person(frame,
                                                                me[2:]))
        rows.append((hms, p["code"], "desk", state, room, key[0],
                     int(key[1]), 1.0 if me is not None else 0.0)
                    + (tuple(int(v) for v in me[2:]) if me is not None
                       else (0, 0, 0, 0)))
        desk_crop(frame, p["seat"], os.path.join(
            CROPS, day, p["code"], "%s_desk_%s.jpg"
            % (hms.replace(":", ""), state)))
    # Everybody else on this camera who may be a visiting employee -- not
    # for the employees whose own desk camera this is (their neighbours).
    if TRACK_ELSEWHERE or FACES_ON:
        visitors = [p for p in people
                    if (p["recorder"], int(p["channel"]))
                    != (key[0], int(key[1]))]
        rows += sightings(room, key, frame, persons, taken, day, hms,
                          visitors)
    if rows:
        _write(day, rows)
    _tell(rows, now, key)


def _tell(rows, now, key):
    """progress_follow (and anything else listening) hears of the looks."""
    for r in rows:
        for f in (ON_DESK if r[2] == "desk" else ON_SEEN):
            try:
                if r[2] == "desk":
                    f(r[1], r[3] != "away", now, r[4], key)
                else:
                    f(r[1], r[4], now, r[3], r[7])
            except Exception:                               # noqa: BLE001
                pass


def seen_name(hms, score, room, key):
    """The file name of a possible sighting's picture."""
    return "%s_seen_%.0f_%s_%s%02d.jpg" % (
        hms.replace(":", ""), 100 * score,
        "".join(ch if ch.isalnum() else "_" for ch in room)[:28],
        key[0], int(key[1]))


def face_galleries(codes, folder=None):
    """The employees' kept faces (faces.GALLERY_DIR), read again only when
    one of the files changes."""
    folder = folder or faces.GALLERY_DIR
    stamp = []
    for c in codes:
        path = os.path.join(folder, "%s.npy" % c)
        stamp.append(os.path.getmtime(path) if os.path.exists(path) else 0)
    stamp = (folder, tuple(codes), tuple(stamp))
    if _face_cache["stamp"] != stamp:
        loaded = {c: faces.load_gallery(c, folder) for c in codes}
        _face_cache.update(stamp=stamp, galleries={
            c: g for c, g in loaded.items() if len(g) >= 3})
    return _face_cache["galleries"]


def sightings(room, key, frame, persons, taken, day, hms, people):
    """Rows (and pictures) for the people on this camera most like one of
    `people`: "face" where a face clearly names them (counted as seen),
    else "possible" by the body until somebody confirms it."""
    galleries = {p["code"]: gallery(day, p["code"]) for p in people}
    galleries = {c: g for c, g in galleries.items() if g is not None}
    face_g = face_galleries([p["code"] for p in people]) if FACES_ON else {}
    if not galleries and not face_g:
        return []
    cand = candidates(room, key, persons, frame.shape[1], taken,
                      regular_seats(day))
    if not cand:
        return []
    vecs = reid.embed(frame, [b[2:] for b in cand]) if galleries else \
        [None] * len(cand)
    rows = []
    for b, v in zip(cand, vecs):
        m, state = None, "possible"
        if face_g:
            m = faces.best_match(faces.of_person(frame, b[2:]), face_g)
            state = "face" if m is not None else state
        if m is None and galleries:
            m = best_match(v, galleries)
        if m is None:
            continue
        code, score, _ = m
        rows.append((hms, code, "seen", state, room, key[0],
                     int(key[1]), score) + tuple(int(x) for x in b[2:]))
        _crop(frame, b[2:], os.path.join(CROPS, day, code,
                                         seen_name(hms, score, room, key)))
    return rows


# ------------------------------------------------------ the hosted page
#
# Shamroze, 23 Nov: "send the dashboard to somebody and the progress should
# go the way the AC status goes -- all the data stays on this computer".
# Every PUBLISH_EVERY seconds the loop sends the day's NUMBERS to
# progress_days (sql/11_progress.sql): codes, departments, times, hours.
# Never a camera picture. Names, employee IDs and the directory-photo icon
# only where progress.yaml says `cloud_names: true` (24 Nov: Shamroze,
# "teeno bhjdo ... pw protected h"; progress_data.to_payloads).

PUBLISH_EVERY = 300
_published = {"at": 0.0, "missing": False, "told": False}

# The payload is given twice rather than read back as EXCLUDED.payload:
# reading an EXCLUDED column needs SELECT on that column of the table, and
# the camera machine may read only (day, code) -- 23 Nov, the first real
# write was "permission denied for table progress_days".
UPSERT = ("INSERT INTO progress_days (day, code, payload, updated_at)"
          " VALUES (%s, %s, %s::jsonb, now())"
          " ON CONFLICT (day, code) DO UPDATE SET payload = %s::jsonb,"
          " updated_at = now()")


def publish(connect, now=None, clock=time.time, force=False):
    """The day's numbers to progress_days, at most every PUBLISH_EVERY
    seconds (every hour while the table is missing). True when sent."""
    t = clock()
    wait = 3600 if _published["missing"] else PUBLISH_EVERY
    if not force and t - _published["at"] < wait:
        return False
    _published["at"] = t
    cfg = pdx.load() or {}
    if not cfg.get("people"):
        return False
    # A person added to progress.yaml (24 Nov: Shamroze names them one by
    # one) belongs on the days already sent too: send the fortnight again.
    try:
        stamp = os.path.getmtime(pdx.CONFIG)
    except OSError:
        stamp = None
    if stamp != _published.get("cfg"):
        _published["cfg"] = stamp
        _past_sent.clear()
    now = now or datetime.now(PKT)
    day = now.strftime("%Y-%m-%d")
    hours = pdx.office_hours()
    people = pdx.build(cfg, day, hours,
                       now=pd.Timestamp(now.replace(tzinfo=None)))
    # Keep every day worked out, here, before the seat notes behind it
    # are let go (two weeks): progress/history.csv.
    try:
        pdx.store_history([dict(r, code=p["code"]) for p in people
                           for r in p.get("history") or []])
    except OSError:
        pass
    rows = pdx.to_payloads(cfg, people, hours, now.strftime("%d %b %H:%M"))
    # Every desk, room by room (desks_data.room_summary): rooms and numbers
    # only, never a name or a desk's code (24 Nov).
    try:
        import json
        import desks_data
        rooms = desks_data.room_summary(desks_data.load(), day)
        if rooms:
            rows.append(("_desks", json.dumps(pdx._jsonable(
                {"day": day, "rooms": rooms}))))
    except Exception:                                       # noqa: BLE001
        pass
    # Every employee through the attendance machines (25 Nov: "cloud pe add
    # karte raho") -- names only where cloud_names allows, never a picture.
    try:
        import json
        att = pdx.attendance_payload(cfg, start=float(hours[0]))
        if att:
            rows.append(("_attendance", json.dumps(pdx._jsonable(att))))
    except Exception:                                       # noqa: BLE001
        pass
    import psycopg2
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.executemany(UPSERT, [(day, code, j, j) for code, j in rows])
            conn.commit()
            cur.close()
        finally:
            conn.close()
    except psycopg2.Error as e:
        missing = (getattr(e, "pgcode", None) in ("42P01", "42501")
                   or isinstance(e, (psycopg2.errors.UndefinedTable,
                                     psycopg2.errors.InsufficientPrivilege)))
        if not missing:
            raise
        # No table yet, or no grant: an administrator runs sql/11 once.
        _published["missing"] = True
        if not _published["told"]:
            _published["told"] = True
            print(">> progress_days is not there yet: the hosted Progress tab"
                  " stays empty until an administrator runs"
                  " sql/11_progress.sql once (the laptop's tab is unaffected)")
        return False
    _published["missing"] = False
    # And one earlier day each time, until the last fortnight is all there
    # (Shamroze, 23 Nov: "kal, parson dekhna chahun" on the hosted page):
    # each worked out to its own end, then never again this run.
    try:
        _publish_past(connect, cfg, day, hours)
    except Exception:                                       # noqa: BLE001
        pass
    return True


PAST_DAYS = 14
_past_sent = set()


def _publish_past(connect, cfg, today, hours):
    days = [d for d in pdx.working_days(today, PAST_DAYS + 1)
            if d < today and d not in _past_sent]
    if not days:
        return None
    d = days[-1]
    end = pd.Timestamp(d) + pd.Timedelta(hours=23, minutes=59)
    people = pdx.build(cfg, d, hours, now=end)
    rows = pdx.to_payloads(cfg, people, hours, "%s (the day's end)" % d)
    conn = connect()
    try:
        cur = conn.cursor()
        cur.executemany(UPSERT, [(d, code, j, j) for code, j in rows])
        conn.commit()
        cur.close()
    finally:
        conn.close()
    _past_sent.add(d)
    return d


# The day's assembly is progress_data.day_activity (the dashboard reads
# it without OpenCV); these names are kept for the loop's side.
load_day = pdx.load_activity
progress_day = pdx.day_activity


def _kept_camera(path):
    """(room, (recorder, channel)) from a kept frame's file name, e.g.
    'Prompt_Cafe__nvr4_ch14.jpg' -> ('Prompt Cafe', ('nvr4', 14))."""
    name = os.path.basename(path)[:-4]
    room, cam = name.rsplit("__", 1)
    rec, ch = cam.rsplit("_ch", 1)
    return room.replace("_", " ").strip(), (rec, int(ch))


def backfill(day, people, model, frames_dir=None, folder=None,
             elsewhere=True, hours=("08:00", "21:30"), desk_rows=True):
    """Activity rows (and desk crops) for a day from the frames kept every
    ten minutes (frames/ac_keep), for days before the loop wrote its own.
    Then, with every desk sighting of the day as each employee's look,
    the possible sightings on every other kept 140-H frame in `hours`.
    Returns how many frames were read."""
    import glob
    frames_dir = frames_dir or os.path.join("frames", "ac_keep", day)
    rows, n = [], 0

    def stamp_of(path):
        s = datetime.fromtimestamp(os.path.getmtime(path), PKT)
        return s if s.strftime("%Y-%m-%d") == day else None

    for p in people:
        pat = os.path.join(frames_dir, "*", "*__%s_ch%02d.jpg"
                           % (p["recorder"], int(p["channel"])))
        for path in sorted(glob.glob(pat)):
            frame = cv2.imread(path)
            stamp = stamp_of(path)
            if frame is None or stamp is None:
                continue
            hms = stamp.strftime("%H:%M:%S")
            r = da.classify(frame, p, model)
            n += 1
            me = r["employee"]
            if me is not None and TRACK_ELSEWHERE:
                learn(day, p["code"], reid.embed(frame, [me[2:]])[0])
            if me is not None and FACES_ON:
                faces.add_to_gallery(p["code"], faces.of_person(frame,
                                                                me[2:]))
            if not desk_rows:
                continue          # the day's desk rows are written already
            rows.append((hms, p["code"], "desk", r["state"], p["department"],
                         p["recorder"], int(p["channel"]),
                         1.0 if me is not None else 0.0)
                        + (tuple(int(v) for v in me[2:]) if me is not None
                           else (0, 0, 0, 0)))
            desk_crop(frame, p["seat"], os.path.join(
                CROPS, day, p["code"], "%s_desk_%s.jpg"
                % (hms.replace(":", ""), r["state"])))
    if elsewhere and (TRACK_ELSEWHERE or FACES_ON):
        for path in sorted(glob.glob(os.path.join(frames_dir, "*", "*.jpg"))):
            try:
                room, key = _kept_camera(path)
            except ValueError:
                continue
            stamp = stamp_of(path)
            if key[0] not in CAMPUS_RECORDERS or stamp is None or not (
                    hours[0] <= stamp.strftime("%H:%M") <= hours[1]):
                continue
            frame = cv2.imread(path)
            if frame is None:
                continue
            n += 1
            persons = da.detect(frame, model, classes=[da.PERSON],
                                conf=da.PERSON_CONF)
            taken = set()
            for p in people:
                if (p["recorder"], int(p["channel"])) == key:
                    me = da.employee(persons, p["seat"], frame.shape[1])
                    if me is not None:
                        taken.add(id(me))
            visitors = [p for p in people
                        if (p["recorder"], int(p["channel"])) != key]
            rows += sightings(room, key, frame, persons, taken, day,
                              stamp.strftime("%H:%M:%S"), visitors)
    rows.sort()
    if rows:
        _write(day, rows, folder)
    return n
