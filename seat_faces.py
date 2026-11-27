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

# 140-H's recorders and, from 27 Nov, 141-C/D's (desks_data.CAMPUS_141)
CAMPUS = {"nvr1", "nvr4", "dvr2", "xvr3", "cd_nvr1", "cd_nvr2", "cd_nvr3",
          "cd_nvr4", "cd_xvr1", "cd_xvr3"}
OUT = os.path.join("people", "seat_faces")
RESULT = os.path.join("people", "seats_identified.csv")
HOURS = ("08:00", "21:30")
KEEP_DAYS = 14
GRID = 25                 # px: a seat's key, so a day's spots line up
MIN_SAMPLES = 8
SAME = 0.45
MARGIN = 0.10
# 27 Nov: keep AdaFace's numbers beside SFace's at the seats (faces.py),
# switched on once face_bench.py showed it names our faces better
ADA_SEATS = False
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
    import desks_data
    if not desks_data.watched_room(room):
        return 0                         # the gym: never (NOT_DESKS)
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
        got = faces.of_person_both(frame, b[:4]) if ADA_SEATS \
            else ((faces.of_person(frame, b[:4]), None))
        if got is None or got[0] is None:
            continue
        v, a = got
        os.makedirs(folder, exist_ok=True)
        stem = os.path.join(folder, _key(key[0], key[1], *seat))
        with open(stem + ".f16", "ab") as fh:
            fh.write(np.asarray(v, np.float16).tobytes())
        if a is not None:
            # AdaFace's 512 beside (27 Nov), the same seat, the same order
            with open(stem + ".a16", "ab") as fh:
                fh.write(np.asarray(a, np.float16).tobytes())
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


def samples(days, base=None, ext=".f16", dim=128):
    """{seat key: (n, dim) unit vectors} over the given days -- SFace's
    (.f16, 128) or, with ext=".a16", dim=512, AdaFace's."""
    out = {}
    for day in days:
        for path in glob.glob(os.path.join(base or OUT, day, "*" + ext)):
            v = np.fromfile(path, np.float16).astype(np.float32)
            v = v[:len(v) // dim * dim].reshape(-1, dim)
            k = os.path.basename(path)[:-len(ext)]
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


DOUBT_SAME = 0.38        # below SAME, at least this: worth a look by eye
DOUBT_MARGIN = 0.05


def seat_desks(rows, desks, reach=40.0):
    """Each match row's desk: the found desk (desk_seats.find_desks) on the
    same camera whose seat is nearest its seat, within `reach` px.
    {seat key: desk dict}."""
    out = {}
    for r in rows:
        rec, ch, x, y = r["seat"].rsplit("_", 3)
        best, bd = None, reach
        for d in desks:
            if d["recorder"] != rec or int(d["channel"]) != int(ch):
                continue
            dist = ((float(d["seat"][0]) - float(x)) ** 2
                    + (float(d["seat"][1]) - float(y)) ** 2) ** 0.5
            if dist <= bd:
                best, bd = d, dist
        if best is not None:
            out[r["seat"]] = best
    return out


def name_plan(rows, desk_of, named, refused, roster_ids):
    """(sure, doubtful) from match rows (27 Nov, Shamroze: "review pdf tab
    bhejo jab tum confident na ho"): sure -- status "named" (8+ faces, far
    above the line and clear of the next), its desk not named yet, the
    person at no other desk, the pair never refused; doubtful -- the same
    but "unsure" yet close (DOUBT_SAME, DOUBT_MARGIN), for the review PDF.
    Each [(desk code, employee_id, score, margin, samples)], one desk per
    person (the strongest)."""
    def k(e):                                # "01289" and "1289" alike
        return str(e or "").strip().lstrip("0") or "0"
    taken = {k(eid) for eid, _ in named.values()}
    refused = {(c, k(e)) for c, e in refused}
    sure, doubt, used = [], [], set()
    rows = sorted(rows, key=lambda r: -r["score"])
    for r in rows:
        d = desk_of.get(r["seat"])
        eid = str(r.get("best") or "")
        if not d or not eid or eid not in roster_ids:
            continue
        code = d["code"]
        if code in named or k(eid) in taken or k(eid) in used \
                or (code, k(eid)) in refused:
            continue
        margin = r["score"] - r["second_score"]
        item = (code, eid, round(r["score"], 3), round(margin, 3),
                r["samples"])
        if r["status"] == "named":
            sure.append(item)
            used.add(k(eid))
        elif r["status"] == "unsure" and r["score"] >= DOUBT_SAME \
                and margin >= DOUBT_MARGIN:
            doubt.append(item)
            used.add(k(eid))
    return sure, doubt


def name_desks(days, apply=False, out_csv=None):
    """Match every seat over `days`, name the sure desks (apply=True writes
    people/desk_names.csv) and list the doubtful for the review PDF
    (people/follow/faces_doubtful.csv). Returns (sure, doubtful)."""
    import csv
    import desk_match
    import desk_seats
    import desks_data
    import staff_faces
    ids, vecs = staff_faces.load_faces()
    roster = {r["employee_id"]: r for r in staff_faces.load_roster()}
    rows = match(samples(days), ids, vecs)
    desks = desk_seats.find_desks(max(days), codes=desks_data.CODES)
    named = desks_data.load_desk_names()
    refused = desk_match.refused()
    sure, doubt = name_plan(rows, seat_desks(rows, desks), named, refused,
                            set(roster))
    if apply:
        for code, eid, _, _, _ in sure:
            desks_data.save_desk_name(code, eid, roster[eid].get("name", ""))
    out_csv = out_csv or os.path.join("people", "follow",
                                      "faces_doubtful.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "employee_id", "score", "margin", "samples"])
        w.writerows(doubt)
    return sure, doubt


def main(argv):
    import staff_faces
    days = argv[2:] or [datetime.now().strftime("%Y-%m-%d")]
    if len(argv) > 1 and argv[1] == "name":
        # python seat_faces.py name [--apply] <days...>
        apply = "--apply" in days
        days = [d for d in days if d != "--apply"]
        sure, doubt = name_desks(days, apply)
        print("sure: %d%s, doubtful (for the PDF): %d" % (
            len(sure), " named" if apply else " (dry run: add --apply)",
            len(doubt)))
        for item in sure:
            print("  sure", item[0], "score %.3f margin %.3f faces %d"
                  % item[2:])
        return
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
