"""Each named person's face as OUR cameras see it.

Shamroze, 24 Nov 2026 ("cctv faces wala kaam bhi shuru karo"; HR's
approval for the campus, staff told). The directory photo is a studio
portrait, straight on; our cameras see the same face from above, from the
side, in their own light -- on 24 Nov a desk face matched its own photo at
best 0.53. Once a desk's sitter is known for certain -- named by hand on
the Progress tab, one of the five with a name, or a seat named by face and
confirmed -- the faces kept at that desk (seat_faces.py, and the five's
desk faces) ARE that person, in our cameras' own view. Those samples
become the person's CCTV gallery, which the gate (entrance_watch.py) and
the other cameras (observe(), below) compare with first.

    people/cctv_faces.npz   ids, vecs: up to KEEP samples a person
    people/sightings/<date>.csv   a named person seen off their own seat

All under people/ (git-ignored, this laptop only). build() is hourly
(desk_watch.rebuild); observe() runs in room_loop.examine.
"""
import csv
import glob
import os
import time
from datetime import datetime

import numpy as np

import faces

OUT = os.path.join("people", "cctv_faces.npz")
SIGHTINGS = os.path.join("people", "sightings")
# 140-H's recorders and, from 27 Nov, 141-C/D's (desks_data.CAMPUS_141)
CAMPUS = {"nvr1", "nvr4", "dvr2", "xvr3", "cd_nvr1", "cd_nvr2", "cd_nvr3",
          "cd_nvr4", "cd_xvr1", "cd_xvr3"}
KEEP = 80                # samples kept a person (the newest)
MIN_SAMPLES = 3          # a person with fewer is not compared
NEAR = 60.0              # px: a seat-face key this close is the desk's seat
SAME = 0.50              # cosine (mean of the best three samples)
MARGIN = 0.10
HOURS = ("08:00", "21:30")
REPEAT = 300             # s: the same person on the same camera again
KEEP_DAYS = 14
_cache = {"stamp": None, "ids": np.array([]), "vecs": np.zeros((0, 128))}
_seen = {}


def known_desks(desk_names, desks, people=None, seats_named=None,
                reviews=None):
    """[(employee_id, recorder, channel, x, y)]: the desks whose sitter is
    certain -- by hand, the five with a name, seats confirmed by face."""
    out = []
    by_code = {d["code"]: d for d in desks}
    for code, (eid, _) in (desk_names or {}).items():
        d = by_code.get(code)
        if d and eid:
            out.append((eid, d["recorder"], int(d["channel"]),
                        float(d["seat"][0]), float(d["seat"][1])))
    for p in people or []:
        if p.get("employee_id"):
            sx, sy = (float(v) for v in p.get("seat") or (0, 0))
            out.append((str(p["employee_id"]), p["recorder"],
                        int(p["channel"]), sx, sy))
    for r in seats_named or []:
        k = (r["recorder"], str(r["channel"]), str(r["x"]), str(r["y"]),
             r.get("employee_id", ""))
        if r.get("status") == "named" and (reviews or {}).get(k) == "yes":
            out.append((r["employee_id"], r["recorder"], int(r["channel"]),
                        float(r["x"]), float(r["y"])))
    return out


def seat_samples(rec, ch, x, y, base=None):
    """Every face kept at the seat nearest (x, y) on that camera, over the
    days seat_faces keeps: (n, 128)."""
    import seat_faces
    base = base or seat_faces.OUT
    vecs = []
    for path in glob.glob(os.path.join(base, "*", "%s_%d_*.f16" % (rec, ch))):
        parts = os.path.basename(path)[:-4].split("_")
        try:
            kx, ky = float(parts[-2]), float(parts[-1])
        except ValueError:
            continue
        if (kx - x) ** 2 + (ky - y) ** 2 > NEAR ** 2:
            continue
        v = np.fromfile(path, np.float16).astype(np.float32)
        vecs.append(v[:len(v) // 128 * 128].reshape(-1, 128))
    return np.vstack(vecs) if vecs else np.zeros((0, 128), np.float32)


GATE = os.path.join("people", "entrance")   # entrance_watch: <day>.csv, <day>/
GATE_DAYS = 5
GATE_SAME = 0.55         # a gate picture joins a gallery only this sure ...
GATE_MARGIN = 0.15       # ... and this clear of the next (faces.SAME, MARGIN)
_gate_vec = {}


def gate_samples(eids, days=None, folder=GATE, embed=None):
    """{employee_id: (n, 128)}: the gate's frontal faces of these people --
    entrance_watch keeps a small picture of each named passage -- only the
    passages named far above the line (24 Nov: the gate sees a face close
    and straight on, the desks from above; with the gate's pictures in it,
    a gallery knows the face the cafe and the lobby see)."""
    import cv2
    embed = embed or (lambda p: faces.of_photo(cv2.imread(p)))
    eids = {str(e) for e in eids}
    days = days or sorted(f[:-4] for f in os.listdir(folder)
                          if f.endswith(".csv"))[-GATE_DAYS:] \
        if os.path.isdir(folder) else []
    out = {}
    for day in days:
        path = os.path.join(folder, day + ".csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh)
                    if r.get("status") == "named"
                    and r.get("employee_id") in eids
                    and float(r.get("score") or 0) >= GATE_SAME
                    and float(r.get("margin") or 0) >= GATE_MARGIN]
        for r in rows:
            e = r["employee_id"]
            # 25 Nov: a passage kept since then has its own stem and its
            # live numbers -- stronger than the ones read again from its
            # 160-px picture (entrance_watch.live_face)
            if r.get("stem"):
                import entrance_watch
                live = entrance_watch.live_face(day, r["stem"], folder)
                if live is not None:
                    v = live[0].reshape(1, -1)
                    out[e] = np.vstack([out[e], v]) if e in out else v
                    continue
                pics = [p for p in [os.path.join(folder, day,
                                                 r["stem"] + ".jpg")]
                        if os.path.exists(p)]
            else:
                pics = glob.glob(os.path.join(folder, day, "%s_ch*_%s.jpg"
                                              % (r["time"].replace(":", ""),
                                                 e)))
            for p in pics[:1]:
                if p not in _gate_vec:
                    _gate_vec[p] = embed(p)
                v = _gate_vec[p]
                if v is not None:
                    v = np.asarray(v, np.float32).reshape(1, -1)
                    e = r["employee_id"]
                    out[e] = np.vstack([out[e], v]) if e in out else v
    return out


def build(known, five_galleries=None, out=OUT, base=None):
    """The CCTV galleries of the people in `known` (known_desks), plus the
    five's desk faces ({employee_id: (n,128)}). Returns {id: samples}."""
    per = {}
    for eid, rec, ch, x, y in known:
        v = seat_samples(rec, ch, x, y, base)
        if len(v):
            per[eid] = np.vstack([per[eid], v]) if eid in per else v
    for eid, g in (five_galleries or {}).items():
        if len(g):
            per[eid] = np.vstack([per[eid], g]) if eid in per else g
    ids, vecs = [], []
    for eid, v in per.items():
        v = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-6)
        v = v[-KEEP:]
        ids += [eid] * len(v)
        vecs.append(v)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez(out, ids=np.array(ids), vecs=np.vstack(vecs).astype(np.float32)
             if vecs else np.zeros((0, 128), np.float32))
    return per


def load(path=OUT):
    """(ids, vecs) of every sample kept, read again when the file changes."""
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return np.array([]), np.zeros((0, 128), np.float32)
    if _cache["stamp"] != stamp:
        d = np.load(path, allow_pickle=False)
        _cache.update(stamp=stamp, ids=d["ids"], vecs=d["vecs"])
    return _cache["ids"], _cache["vecs"]


def scores(vec, ids, vecs, min_samples=MIN_SAMPLES):
    """{employee_id: mean of the best three samples' cosines}."""
    out = {}
    if vec is None or not len(ids):
        return out
    s = vecs @ vec
    for eid in set(ids.tolist()):
        mine = np.sort(s[ids == eid])[::-1]
        if len(mine) >= min_samples:
            out[eid] = float(mine[:3].mean())
    return out


def best(vec, ids=None, vecs=None, same=SAME, margin=MARGIN):
    """(employee_id, score, margin) when a face is clearly one named
    person's in our cameras' view, else None."""
    if ids is None:
        ids, vecs = load()
    sc = sorted(scores(vec, ids, vecs).items(), key=lambda kv: -kv[1])
    if not sc:
        return None
    top = sc[0]
    second = sc[1][1] if len(sc) > 1 else -1.0
    if top[1] < same or top[1] - second < margin:
        return None
    return top[0], top[1], top[1] - second


# ---------------------------------------------- AdaFace sightings (27 Nov)
#
# Shamroze, 27 Nov night: "in the building, place not seen 7 hours -- sab
# camera se check karo". The SFace galleries named 40-70 sightings a day on
# both campuses. Each person's AdaFace reference (adaface.py) -- the
# directory photo and their own gate faces (named there by face or by
# their OUT punch), people/ada_refs.npz, written by the naming rounds
# (people/session_handoff/desk_ada.py refs) -- named the right person for
# 94% of gate looks at 0.45 by 0.10, never with the same day's pictures in
# the reference (sight_calib.py). A camera's look is harder than the
# gate's, so that bar is the one used.
ADA_REFS = os.path.join("people", "ada_refs.npz")
ADA_SAME = 0.45
ADA_MARGIN = 0.10
ADA_BUDGET = 8.0          # s of SCRFD + AdaFace a minute here, at most
_ada_refs = {"stamp": None, "ids": np.array([]),
             "vecs": np.zeros((0, 512), np.float32)}
_ada_clock = {"minute": 0, "spent": 0.0}


def ada_refs(path=ADA_REFS):
    """(ids, unit vectors) of the AdaFace references, read again when the
    file changes; empty where there is none."""
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return np.array([]), np.zeros((0, 512), np.float32)
    if _ada_refs["stamp"] != stamp:
        d = np.load(path, allow_pickle=False)
        v = d["vecs"].astype(np.float32)
        v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-6)
        _ada_refs.update(stamp=stamp, ids=d["ids"], vecs=v)
    return _ada_refs["ids"], _ada_refs["vecs"]


def ada_best(vec, ids, vecs, same=ADA_SAME, margin=ADA_MARGIN):
    """(employee_id, score, margin) when one AdaFace look is clearly one
    person's reference, else None."""
    if vec is None or not len(ids):
        return None
    v = np.asarray(vec, np.float32)
    v = v / max(float(np.linalg.norm(v)), 1e-6)
    s = vecs @ v
    o = np.argsort(-s)
    top = float(s[o[0]])
    second = float(s[o[1]]) if len(o) > 1 else -1.0
    if top < same or top - second < margin:
        return None
    return str(ids[o[0]]), top, top - second


def _ada_ok(now_s=None):
    now_s = time.time() if now_s is None else now_s
    m = int(now_s // 60)
    if m != _ada_clock["minute"]:
        _ada_clock.update(minute=m, spent=0.0)
    return _ada_clock["spent"] < ADA_BUDGET


def observe(room, key, frame, boxes, now=None, spots=None, out=None):
    """A pass's people on one camera who are NOT at a regular seat (the
    cafe, a lobby, a meeting room, the stairs): each clear face against the
    named people's CCTV galleries; a clear one is written as a sighting.
    Never raises."""
    try:
        return _observe(room, key, frame, boxes, now, spots, out)
    except Exception:                                       # noqa: BLE001
        return 0


def _observe(room, key, frame, boxes, now, spots, out):
    if frame is None or key[0] not in CAMPUS or not faces.available():
        return 0
    if "gym" in str(room or "").lower():
        return 0                         # the 141 gym: never looked at
    ids, vecs = load()
    a_ids, a_vecs = ada_refs()
    if not len(ids) and not len(a_ids):
        return 0
    from progress_track import PKT, STAFFED, place_of, regular_seats
    import seat_faces
    now = now or datetime.now(PKT)
    if not (HOURS[0] <= now.strftime("%H:%M") <= HOURS[1]):
        return 0
    day = now.strftime("%Y-%m-%d")
    if spots is None:
        spots = regular_seats(day).get((key[0], int(key[1]))) or []
    # Only an office's (or a staffed desk's) regular seat is its owner's
    # (seat_faces names that one). A cafe table, the smoking area's bench or
    # a meeting room's chair is a "regular seat" too -- people sit there
    # every day -- and leaving those out put under 1% of the named people's
    # away time in a place (26 Nov, places_day): the same rule as
    # progress_track.candidates.
    office = place_of(room) == "office" or room in STAFFED
    n = 0
    for b in boxes:
        if office and seat_faces.seat_of(b, spots, frame.shape[1]) is not None:
            continue                     # somebody at a seat: seat_faces'
        m = None
        if len(a_ids) and _ada_ok():
            # SCRFD finds the face, AdaFace reads it (faces.of_person_both)
            t0 = time.time()
            got = faces.of_person_both(frame, b[:4])
            _ada_clock["spent"] += time.time() - t0
            v = got[0] if got is not None else None
            if got is not None and got[1] is not None:
                m = ada_best(got[1], a_ids, a_vecs)
        else:
            v = faces.of_person(frame, b[:4])
        if m is None and v is not None and len(ids):
            m = best(v, ids, vecs)
        if m is None:
            continue
        eid, score, margin = m
        k = (eid, key[0], int(key[1]))
        t = now.timestamp()
        if t - _seen.get(k, 0.0) < REPEAT:
            continue
        _seen[k] = t
        write(day, (now.strftime("%H:%M:%S"), eid, room, key[0], int(key[1]),
                    score, margin), out)
        n += 1
    return n


def write(day, row, out=None):
    folder = out or SIGHTINGS
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, day + ".csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["time", "employee_id", "room", "recorder", "channel",
                        "score", "margin"])
        w.writerow(list(row[:5]) + ["%.3f" % row[5], "%.3f" % row[6]])
