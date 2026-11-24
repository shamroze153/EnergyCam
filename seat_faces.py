"""Who sits where, by face: every regular seat on 140-H's cameras, the
face of whoever sits there, pass after pass, matched to the staff roster.

Shamroze, 24 Nov 2026 (HR's approval for the campus, staff told): "pehle
picture, naam, ID lo, phir dhoondo woh kahan baithe hue hain; camera mein
sabko match karte rehna". The double check is in the method:

  1. a face counts only at a regular seat of the camera (seat_map's seats
     of the last working days) -- so it is somebody's desk, not a passer-by;
  2. a seat is named only from many faces over the day(s) (at least
     MIN_SAMPLES), their mean against each directory photo
     (staff_faces.py), and only when the best photo is far above the line
     (SAME, 0.45) and clear of the next (MARGIN, 0.10). On 24 Nov's desk
     faces this named P3's seat right (0.53, by 0.12) and left the four
     others -- seen from above, or blurred -- unnamed rather than wrong;
  3. every named seat comes with a picture beside the directory photo for
     a person to look at (the Progress tab), before anything is built on it.

Faces are kept only as numbers, per seat and day, under people/seat_faces/
(git-ignored, this laptop only), and let go after KEEP_DAYS.
"""
import glob
import os
import time
from datetime import datetime

import numpy as np

import faces

CAMPUS = {"nvr1", "nvr4", "dvr2", "xvr3"}
OUT = os.path.join("people", "seat_faces")
RESULT = os.path.join("people", "seats_identified.csv")
HOURS = ("08:00", "21:30")
KEEP_DAYS = 14
GRID = 25                 # px: a seat's key, so a day's spots line up
MIN_SAMPLES = 8
SAME = 0.45
MARGIN = 0.10
OUTLIER = 0.20            # a sample this unlike the seat's mean is dropped


def _key(rec, ch, x, y):
    return "%s_%d_%d_%d" % (rec, int(ch), int(round(x / GRID)) * GRID,
                            int(round(y / GRID)) * GRID)


def seat_of(box, spots, width):
    """The regular seat (x, y) a person's box sits on, or None."""
    import progress_data as pdx
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    r = max(pdx.SEAT_RADIUS * width, pdx.SEAT_REACH * (y2 - y1))
    bx, by = (x1 + x2) / 2.0, y2
    best = None
    for x, y in spots or []:
        d = (bx - x) ** 2 + (by - y) ** 2
        if d <= r * r and (best is None or d < best[0]):
            best = (d, (x, y))
    return best[1] if best else None


def observe(room, key, frame, boxes, now=None, spots=None, out=None):
    """One camera's counted people this pass (room_loop.examine): the face
    of each one at a regular seat, kept as numbers for that seat. Never
    raises."""
    try:
        return _observe(room, key, frame, boxes, now, spots, out)
    except Exception:                                       # noqa: BLE001
        return 0


def _observe(room, key, frame, boxes, now, spots, out):
    if frame is None or key[0] not in CAMPUS or not faces.available():
        return 0
    from progress_track import PKT, regular_seats
    now = now or datetime.now(PKT)
    if not (HOURS[0] <= now.strftime("%H:%M") <= HOURS[1]):
        return 0
    day = now.strftime("%Y-%m-%d")
    if spots is None:
        spots = regular_seats(day).get((key[0], int(key[1])))
    if not spots:
        return 0
    folder = os.path.join(out or OUT, day)
    kept = 0
    for b in boxes:
        seat = seat_of(b, spots, frame.shape[1])
        if seat is None:
            continue
        v = faces.of_person(frame, b[:4])
        if v is None:
            continue
        os.makedirs(folder, exist_ok=True)
        stem = os.path.join(folder, _key(key[0], key[1], *seat))
        with open(stem + ".f16", "ab") as fh:
            fh.write(np.asarray(v, np.float16).tobytes())
        _thumb(frame, b, stem + ".jpg")
        kept += 1
    if kept:
        _forget_old(out or OUT)
    return kept


THUMB_EVERY = 3600        # s: a seat's picture for the check, renewed hourly


def _thumb(frame, box, path):
    """The seat's sitter's head, small, for the double check by eye beside
    the directory photo -- one per seat, renewed every THUMB_EVERY."""
    try:
        if os.path.exists(path) and \
                time.time() - os.path.getmtime(path) < THUMB_EVERY:
            return
        got = faces.head_crop(frame, box[:4])
        if got is None:
            return
        import cv2
        crop = got[0]
        side = 200.0 / max(crop.shape[:2])
        cv2.imwrite(path, cv2.resize(crop, None, fx=side, fy=side),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
    except Exception:                                       # noqa: BLE001
        pass


def _forget_old(base, days=KEEP_DAYS):
    cutoff = time.time() - days * 86400
    for path in glob.glob(os.path.join(base, "*")):
        try:
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                import shutil
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def samples(days, base=None):
    """{seat key: (n, 128) unit vectors} over the given days."""
    out = {}
    for day in days:
        for path in glob.glob(os.path.join(base or OUT, day, "*.f16")):
            v = np.fromfile(path, np.float16).astype(np.float32)
            v = v[:len(v) // 128 * 128].reshape(-1, 128)
            k = os.path.basename(path)[:-4]
            out[k] = np.vstack([out[k], v]) if k in out else v
    return out


def seat_face(vecs):
    """A seat's face: the mean of its samples, unlike ones left out."""
    v = vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-6)
    m = v.mean(axis=0)
    m /= max(np.linalg.norm(m), 1e-6)
    keep = v[v @ m >= OUTLIER]
    if len(keep) >= max(3, len(v) // 2):
        m = keep.mean(axis=0)
        m /= max(np.linalg.norm(m), 1e-6)
    return m, len(keep)


def match(seat_vecs, ids, photo_vecs, min_samples=MIN_SAMPLES, same=SAME,
          margin=MARGIN):
    """Each seat against every directory photo: [{seat, samples, best,
    score, second, second_score, status}], status "named" (far above the
    line and clear of the next), "unsure" (best shown, not named) or "few
    faces"."""
    out = []
    for k, vecs in sorted(seat_vecs.items()):
        row = {"seat": k, "samples": len(vecs), "best": "", "score": 0.0,
               "second": "", "second_score": 0.0, "status": "few faces"}
        if len(vecs) >= min_samples and len(ids):
            m, used = seat_face(vecs)
            s = photo_vecs @ m
            order = np.argsort(-s)
            row.update(best=str(ids[order[0]]), score=float(s[order[0]]),
                       samples=used)
            if len(order) > 1:
                row.update(second=str(ids[order[1]]),
                           second_score=float(s[order[1]]))
            clear = row["score"] - row["second_score"] >= margin
            row["status"] = "named" if (row["score"] >= same and clear) \
                else "unsure"
        out.append(row)
    return out


def refresh(days, result=RESULT):
    """Match every seat again over `days` and write the result (the loop,
    hourly: desk_watch.rebuild). Returns the rows."""
    import staff_faces
    ids, vecs = staff_faces.load_faces()
    rows = match(samples(days), ids, vecs)
    write_result(rows, staff_faces.load_roster(), result)
    return rows


def write_result(rows, roster, path=RESULT):
    """The seats, named or not, to people/seats_identified.csv (local)."""
    import csv
    names = {r["employee_id"]: r for r in roster}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["recorder", "channel", "x", "y", "samples", "status",
                    "employee_id", "name", "designation", "score", "margin"])
        for r in rows:
            rec, ch, x, y = r["seat"].rsplit("_", 3)
            p = names.get(r["best"], {})
            w.writerow([rec, ch, x, y, r["samples"], r["status"], r["best"],
                        p.get("name", "") if r["status"] == "named" else "",
                        p.get("designation", "") if r["status"] == "named"
                        else "", "%.3f" % r["score"],
                        "%.3f" % (r["score"] - r["second_score"])])


def main(argv):
    import staff_faces
    days = argv[2:] or [datetime.now().strftime("%Y-%m-%d")]
    if len(argv) > 1 and argv[1] == "match":
        ids, vecs = staff_faces.load_faces()
        rows = match(samples(days), ids, vecs)
        write_result(rows, staff_faces.load_roster())
        n = {s: sum(1 for r in rows if r["status"] == s)
             for s in ("named", "unsure", "few faces")}
        print("seats:", len(rows), n, "->", RESULT)
    else:
        print(__doc__)


if __name__ == "__main__":
    import sys
    main(sys.argv)
