"""Names for the desks, suggested -- for a person to answer yes or no.

Shamroze, 24 Nov 2026: naming the desks from their pictures was confusing
-- he does not know most people's names, the directory did not help, and
the desk pictures are blurred. But the gate (entrance_watch) sees faces
close and frontal, on the way out, and names them against the directory;
and each desk's face (seat_faces) is the same people on the same days,
seen by our own cameras. So a desk's face is matched against the gate's
faces -- camera against camera, the same days -- and a name is suggested
only when the desk and the person pick each other (each the other's best),
SAME or more and MARGIN clear of the next. Tried on 24 Nov's faces: the
receptionist's and an Admin Room desk came out right (0.58 by 0.14, 0.49
by 0.12) -- the two of five known desks whose sitter faces the camera; the
three seen from above were left unsuggested rather than wrong. A person
with many gate pictures (the receptionist, beside the gate) was every
desk's best before "each the other's best".

Each suggestion is shown as one picture -- the desk's sitter as our
camera sees them, the gate's picture of the person, the directory photo
-- for "the same person? yes / no": no name to know. A yes names the desk
(desks_data.save_desk_name); a no is kept so it is not asked again.

    python name_suggest.py [days...]   -> people/name_suggestions.csv and
                                          one picture each in frames/suggest/

Everything here is local: people/ and frames/ are git-ignored.
"""
import csv
import glob
import os
import sys
from datetime import datetime

import numpy as np

GATE_PICS = os.path.join("people", "entrance")       # <day>/<HHMMSS>_ch.._<eid>.jpg
SEAT_FACES = os.path.join("people", "seat_faces")    # <day>/<seat key>.f16/.jpg
PHOTOS = os.path.join("people", "photos")            # <eid>.jpg (directory)
OUT = os.path.join("people", "name_suggestions.csv")
ANSWERS = os.path.join("people", "name_answers.csv")
SHEETS = os.path.join("frames", "suggest")
SAME = 0.45
MARGIN = 0.10
MIN_FACES = 5            # a desk's faces over the days, at least
GATE_MAX = 8             # a person's gate pictures used, at most (newest)
CODE_REACH = 60          # px from a seat key to its desk (desk_seats)


def gate_gallery(days, folder=GATE_PICS, embed=None):
    """(ids, unit mean vectors (n, 128), {eid: [picture paths]}) from the
    gate's named pictures on the given days."""
    if embed is None:
        import cv2
        import faces

        def embed(path):
            return faces.of_photo(cv2.imread(path))
    pics = {}
    for day in days:
        for path in sorted(glob.glob(os.path.join(folder, day, "*.jpg"))):
            eid = os.path.splitext(os.path.basename(path))[0].split("_")[-1]
            if eid != "unknown":
                pics.setdefault(eid, []).append(path)
    ids, vecs, used = [], [], {}
    for eid, paths in sorted(pics.items()):
        got = []
        for p in paths[-GATE_MAX:]:
            v = embed(p)
            if v is not None:
                v = np.asarray(v, np.float32)
                got.append(v / max(np.linalg.norm(v), 1e-6))
        if got:
            m = np.mean(got, axis=0)
            ids.append(eid)
            vecs.append(m / max(np.linalg.norm(m), 1e-6))
            used[eid] = paths[-GATE_MAX:]
    return ids, (np.array(vecs, np.float32) if vecs
                 else np.zeros((0, 128), np.float32)), used


def suggest(seat_means, ids, G, same=SAME, margin=MARGIN):
    """seat_means: {seat key: (unit vector, faces)}. Each desk against every
    person at the gate; suggested where the desk's best person has that
    desk as their own best too, `same` or more and `margin` clear of the
    desk's next person: [{seat, faces, employee_id, score, clear}], the
    clearest first."""
    keys = [k for k in sorted(seat_means)]
    if not keys or not len(ids):
        return []
    S = np.array([seat_means[k][0] for k in keys], np.float32) @ G.T
    out = []
    for i, k in enumerate(keys):
        order = np.argsort(-S[i])
        j = int(order[0])
        nxt = float(S[i, order[1]]) if len(order) > 1 else 0.0
        if S[i, j] < same or S[i, j] - nxt < margin:
            continue
        if int(np.argmax(S[:, j])) != i:
            continue                     # the person's own best is elsewhere
        out.append({"seat": k, "faces": int(seat_means[k][1]),
                    "employee_id": ids[j], "score": float(S[i, j]),
                    "clear": float(S[i, j] - nxt)})
    return sorted(out, key=lambda r: -r["clear"])


def load_answers(path=ANSWERS):
    """{(seat key, employee_id): "yes" | "no"}, the latest word for each."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return {(r["seat"], r["employee_id"]): r["answer"]
                for r in csv.DictReader(fh)}


def save_answer(seat, employee_id, answer, code="", name="", path=ANSWERS):
    """Somebody's yes or no to a suggestion; a yes names the desk."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["seat", "employee_id", "answer", "code", "at"])
        w.writerow([seat, employee_id, answer, code,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    if answer == "yes" and code:
        import desks_data
        desks_data.save_desk_name(code, employee_id, name)


def desk_code(seat, codes=None):
    """The desk (desk_seats' code kept by place) a seat key sits on, or ""."""
    import json
    import desks_data
    rec, ch, x, y = seat.rsplit("_", 3)
    try:
        with open(codes or desks_data.CODES, encoding="utf-8") as fh:
            known = (json.load(fh).get("desks") or {}).get("%s.%s" % (rec, ch))
    except (OSError, ValueError):
        known = None
    best = None
    for n, kx, ky in known or []:
        d = (float(x) - kx) ** 2 + (float(y) - ky) ** 2
        if d <= CODE_REACH ** 2 and (best is None or d < best[0]):
            best = (d, "%s.%s-%d" % (rec, ch, n))
    return best[1] if best else ""


def sheet(s, gate_pics, roster, day, out, size=220):
    """One picture: the desk's sitter (our camera), the gate's pictures of
    the suggested person, the directory photo -- and who that is."""
    import cv2

    def tile(path, label):
        img = cv2.imread(path) if path and os.path.exists(path) else None
        if img is None:
            img = np.full((size, size, 3), 40, np.uint8)
        h, w = img.shape[:2]
        k = size / float(max(h, w))
        img = cv2.resize(img, (max(1, int(w * k)), max(1, int(h * k))))
        canvas = np.full((size + 28, size, 3), 0, np.uint8)
        y0, x0 = (size - img.shape[0]) // 2, (size - img.shape[1]) // 2
        canvas[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
        cv2.putText(canvas, label, (6, size + 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 255, 255), 1, cv2.LINE_AA)
        return canvas
    eid = s["employee_id"]
    seat_pic = os.path.join(SEAT_FACES, day, s["seat"] + ".jpg")
    photo = next(iter(glob.glob(os.path.join(PHOTOS, eid + ".*"))), "")
    tiles = [tile(seat_pic, "at the desk (our camera)")]
    tiles += [tile(p, "at the gate %s:%s" % (os.path.basename(p)[:2],
                                             os.path.basename(p)[2:4]))
              for p in gate_pics[-2:]]
    tiles.append(tile(photo, "directory photo"))
    body = np.hstack(tiles)
    r = roster.get(eid, {})
    head = np.zeros((64, body.shape[1], 3), np.uint8)
    cv2.putText(head, "%s - same person?" % s["label"], (8, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(head, "%s  (%s)  ID %s" % (r.get("name", ""),
                                           r.get("designation", ""), eid),
                (8, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
                cv2.LINE_AA)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, np.vstack([head, body]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out


def run(days, out=OUT, sheets=SHEETS):
    import seat_faces
    import staff_faces
    ids, G, pics = gate_gallery(days)
    means = {}
    for k, vecs in seat_faces.samples(days).items():
        if len(vecs) >= MIN_FACES:
            m, used = seat_faces.seat_face(vecs)
            if used >= MIN_FACES:
                means[k] = (m, used)
    said = load_answers()
    named = {}
    try:
        import desks_data
        named = desks_data.load_desk_names()
    except Exception:                                       # noqa: BLE001
        pass
    roster = {r["employee_id"]: r for r in staff_faces.load_roster()}
    rows = []
    for s in suggest(means, ids, G):
        s["code"] = desk_code(s["seat"])
        if (s["seat"], s["employee_id"]) in said:
            continue                     # asked and answered
        if s["code"] and named.get(s["code"], ("",))[0] == s["employee_id"]:
            continue                     # already named so
        s["label"] = "S%d" % (len(rows) + 1)
        s["sheet"] = sheet(s, pics.get(s["employee_id"], []), roster,
                           days[-1], os.path.join(sheets, "%s.jpg"
                                                  % s["label"]))
        rows.append(s)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["label", "seat", "code", "employee_id", "score", "clear",
                    "faces", "sheet"])
        for s in rows:
            w.writerow([s["label"], s["seat"], s["code"], s["employee_id"],
                        "%.3f" % s["score"], "%.3f" % s["clear"], s["faces"],
                        s["sheet"]])
    return rows


def main(argv):
    days = argv[1:] or [datetime.now().strftime("%Y-%m-%d")]
    rows = run(days)
    print("suggested:", len(rows), "->", OUT)
    for s in rows:
        print(s["label"], s["code"] or s["seat"], s["employee_id"],
              "%.2f by %.2f" % (s["score"], s["clear"]))


if __name__ == "__main__":
    main(sys.argv)
