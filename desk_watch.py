"""Every desk at 140-H, pass by pass: what its sitter is doing.

Shamroze, 24 Nov 2026: "har employee ka P1-P5 jaisa -- seat par kya karte
hain". The five's own rules (desk_activity.py), for every desk that
desks_data.find_desks() finds on a camera: somebody standing over the
desk is "talking" (cheap, every pass); the phone is looked for in a close
crop (the costly part) every PHONE_EVERY-th pass of a desk -- the passes
in between are "desk", at the desk with the activity not read, which the
day's figures share out as the read passes were (progress_data's
estimate). Nobody there is "away".

Writes progress/desks_activity/<date>.csv (the five's columns) and, once
an hour, a picture of each occupied desk under frames/desks/ for checking
by eye -- both local, both let go after KEEP_DAYS. Called from
room_loop.examine; never raises.
"""
import os
import time
from datetime import datetime

import desk_activity as da

OUT = os.path.join("progress", "desks_activity")
CROPS = os.path.join("frames", "desks")
CAMPUS = {"nvr1", "nvr4", "dvr2", "xvr3"}
PHONE_EVERY = 3
HOURS = ("07:30", "22:00")
KEEP_DAYS = 14
_desks = {"day": None, "by_cam": {}}
_count = {}


def desks_for(day, finder=None):
    """{(recorder, channel): [desk]} for the day, found once a day."""
    if _desks["day"] != day:
        import desk_seats
        import desks_data
        found = finder(day) if finder else desk_seats.find_desks(
            day, codes=desks_data.CODES)   # codes kept by place
        by = {}
        for d in found:
            by.setdefault((d["recorder"], int(d["channel"])), []).append(d)
        _desks.update(day=day, by_cam=by)
    return _desks["by_cam"]


def observe(room, key, frame, boxes, model=None, now=None, out=None,
            crops=None, finder=None):
    try:
        return _observe(room, key, frame, boxes, model, now, out, crops,
                        finder)
    except Exception:                                       # noqa: BLE001
        return 0


def _observe(room, key, frame, boxes, model, now, out, crops, finder):
    if frame is None or key[0] not in CAMPUS:
        return 0
    from progress_track import PKT, desk_crop
    now = now or datetime.now(PKT)
    if not (HOURS[0] <= now.strftime("%H:%M") <= HOURS[1]):
        return 0
    day, hms = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    mine = desks_for(day, finder).get((key[0], int(key[1])))
    if not mine:
        return 0
    persons = [(da.PERSON, float(b[4]) if len(b) > 4 else 1.0,
                float(b[0]), float(b[1]), float(b[2]), float(b[3]))
               for b in boxes]
    rows = []
    # one person, one desk; a visitor stands and sits at no desk (24 Nov,
    # checked by eye: neighbours had been read at empty desks, and seated
    # neighbours as visitors)
    sat = da.assign_desks(persons, {d["code"]: tuple(d["seat"])
                                    for d in mine}, frame.shape[1])
    seated = [p for p in sat.values() if p is not None]
    for d in mine:
        me = sat.get(d["code"])
        state = "away"
        if me is not None:
            n = _count[d["code"]] = _count.get(d["code"], 0) + 1
            if da.standing_visitor(persons, me, seated):
                state = "talking"
            elif model is not None and n % PHONE_EVERY == 0:
                # one close look: a phone, and a screen; a hand held to the
                # head is a call (pose, 24 Nov)
                phone, screen = da.close_look(frame, me, model)
                if phone is None and da.hand_at_head(frame, me):
                    phone = "call"
                state = "phone" if phone else ("computer" if screen
                                               else "desk")
            else:
                state = "desk"
            path = os.path.join(crops or CROPS, day, "%s_%s.jpg"
                                % (d["code"], now.strftime("%H")))
            if not os.path.exists(path):
                desk_crop(frame, d["seat"], path)
                mark_seat(path, frame.shape, d["seat"], me[2:6])
        rows.append((hms, d["code"], "desk", state, room, key[0],
                     int(key[1]), 1.0 if me is not None else 0.0)
                    + (tuple(int(v) for v in me[2:]) if me is not None
                       else (0, 0, 0, 0)))
    _write(day, rows, out or OUT, crops or CROPS)
    return len(rows)


def _square(shape, seat, share=0.30):
    """progress_track.desk_crop's square in the frame: (X1, Y1, side)."""
    H, W = shape[:2]
    side = int(share * W)
    x, y = (float(v) for v in seat)
    X1 = min(max(0, x - side // 2), max(0, W - side))
    Y1 = min(max(0, y - int(0.75 * side)), max(0, H - side))
    return X1, Y1, side


def seat_in_crop(shape, seat, share=0.30, size=480):
    """Where a desk's seat falls in progress_track.desk_crop's square --
    not always its middle: at a frame's edge the square is held inside the
    frame (24 Nov: 32 of 72 desk pictures had the seat well off-centre)."""
    X1, Y1, side = _square(shape, seat, share)
    x, y = (float(v) for v in seat)
    return (int((x - X1) / side * size), int((y - Y1) / side * size))


def box_in_crop(shape, seat, box, share=0.30, size=480):
    """A person's box (frame pixels) in the desk picture's pixels, held
    inside the picture."""
    X1, Y1, side = _square(shape, seat, share)

    def f(v, o):
        return int(min(size - 1, max(0, (float(v) - o) / side * size)))
    return f(box[0], X1), f(box[1], Y1), f(box[2], X1), f(box[3], Y1)


def mark_seat(path, shape, seat, box=None):
    """On the desk's picture: a box round the person sitting at the desk
    (24 Nov: naming the desks, Shamroze could not tell which person a
    picture was for) and a small ring where its seat is."""
    try:
        import cv2
        img = cv2.imread(path)
        if img is None:
            return
        size = img.shape[0]
        if box is not None:
            x1, y1, x2, y2 = box_in_crop(shape, seat, box, size=size)
            if x2 - x1 > 4 and y2 - y1 > 4:
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 3)
        cv2.circle(img, seat_in_crop(shape, seat, size=size), 14,
                   (0, 255, 255), 2)
        cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    except Exception:                                       # noqa: BLE001
        pass


REBUILD_EVERY = 3600
_rebuilt = {"at": 0.0}


def rebuild(clock=time.time, now=None, build=None):
    """progress/desks.csv worked out again (desks_data.build), at most
    every REBUILD_EVERY seconds. True when it ran."""
    t = clock()
    if t - _rebuilt["at"] < REBUILD_EVERY:
        return False
    _rebuilt["at"] = t
    from progress_track import PKT
    day = (now or datetime.now(PKT)).strftime("%Y-%m-%d")
    if build is not None:
        build(day)
        return True
    import desk_seats
    import desks_data
    import progress_data as pdx
    import seat_faces
    # the seats' faces matched again first (the names "Every desk" shows),
    # over today and the working day before
    try:
        seat_faces.refresh(pdx.working_days(day, 2) or [day])
    except Exception:                                       # noqa: BLE001
        pass
    desks_data.build(day, desks=desk_seats.find_desks(
        day, codes=desks_data.CODES), codes=desks_data.CODES)
    try:
        cctv_rebuild()
    except Exception:                                       # noqa: BLE001
        pass
    return True


def cctv_rebuild():
    """The named people's CCTV galleries (cctv_faces.py), from the desks
    whose sitter is certain and the five's desk faces."""
    import cctv_faces
    import desks_data
    import faces
    import progress_data as pdx
    df = desks_data.load()
    desks = [{"code": c, "recorder": g["recorder"].iloc[0],
              "channel": int(g["channel"].iloc[0]),
              "seat": [float(g["x"].iloc[0]), float(g["y"].iloc[0])]}
             for c, g in df.groupby("code")] if len(df) else []
    people = [p for p in (pdx.load() or {}).get("people") or []
              if p.get("employee_id")]
    five = {str(p["employee_id"]): faces.load_gallery(p["code"])
            for p in people}
    known = cctv_faces.known_desks(desks_data.load_desk_names(), desks,
                                   people, desks_data.load_seats_named(),
                                   desks_data.load_reviews())
    return cctv_faces.build(known, five)


def _write(day, rows, folder, crops):
    if not rows:
        return
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
        cutoff = time.time() - KEEP_DAYS * 86400
        for base in (folder, crops):
            for name in os.listdir(base) if os.path.isdir(base) else []:
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
