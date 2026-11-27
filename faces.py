"""Faces -- on this machine only. First (23 Nov) for the five Progress
employees; from 24 Nov for the campus's staff too (HR's approval, the
staff told; staff_faces.py, seat_faces.py) -- their numbers under people/.

Shamroze, 23 Nov 2026: "HR ne face recognition ki permission de di hai --
in 5 employees ki face recognition karke project proceed karo." The body
network (reid.py) could not tell a stranger in a dark T-shirt from an
employee in one; a face, where the camera sees it, can.

Two networks from OpenCV's own model zoo, run by OpenCV itself (no other
package): YuNet finds faces, SFace turns an aligned face into 128 numbers;
two faces are the same person when their numbers are close (cosine; OpenCV
puts the line at 0.363 for SFace, this uses SAME, a little stricter).

What is kept, and where:
  * models/  the two networks (git-ignored);
  * progress/faces/<code>.npy  the five employees' face numbers, learned
    from their own desks (git-ignored, this laptop only). Nobody else's
    face is kept: a face elsewhere is compared and forgotten.
  * no picture of a face is stored by this module.
To stop it: delete progress/faces/ (and models/face_*), and the loop goes
back to body re-ID alone.

On these cameras a face is often small, seen from above, or not seen at
all (a back, a bowed head): no face is simply no answer, never a "no".
"""
import os

import numpy as np

DETECTOR = os.path.join("models", "face_detection_yunet_2023mar.onnx")
RECOGNIZER = os.path.join("models", "face_recognition_sface_2021dec.onnx")
GALLERY_DIR = os.path.join("progress", "faces")

# 23 Nov, on the day's kept frames: faces at the desks were found in a
# third to a half of the frames; the same employee scored 0.46-0.66 where
# the camera faces them (P2, P3, P5) but only 0.12-0.41 where it sees them
# from above or the side (P1 bowed over the keyboard, P4) -- and strangers
# elsewhere scored up to 0.44 against them (a bearded man in DL "was" P1 at
# 0.44 while P1 sat at his desk). OpenCV's 0.363 would name strangers. So
# a face names an employee only far above that, by a wide margin; under it
# a face says nothing and the body re-ID's "possible" stands.
SAME = 0.55          # cosine at or above: the same person
MARGIN = 0.15        # ... and this much above any other employee
ADMIT = 0.30         # a desk face joins the gallery if this like the rest
FACE_SCORE = 0.75    # YuNet's own confidence in a face
MIN_FACE = 28        # px wide in the picture as searched: smaller is noise
GALLERY_MAX = 60     # face samples kept per employee

_nets = {"det": None, "rec": None, "failed": False}


def available():
    return os.path.exists(DETECTOR) and os.path.exists(RECOGNIZER)


def _load():
    if _nets["rec"] is not None or _nets["failed"]:
        return _nets["det"], _nets["rec"]
    try:
        import cv2
        _nets["det"] = cv2.FaceDetectorYN.create(DETECTOR, "", (320, 320),
                                                 FACE_SCORE, 0.3, 50)
        _nets["rec"] = cv2.FaceRecognizerSF.create(RECOGNIZER, "")
    except Exception:                                       # noqa: BLE001
        _nets["failed"] = True
    return _nets["det"], _nets["rec"]


def head_crop(frame, box, share=0.6, pad=0.15, long_side=320):
    """The top of a person's box (where a head is, standing or sitting),
    enlarged so a small face is big enough to find. Returns (crop, scale,
    (X1, Y1)) or None."""
    import cv2
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    w, h = x2 - x1, y2 - y1
    H, W = frame.shape[:2]
    X1, Y1 = int(max(0, x1 - pad * w)), int(max(0, y1 - pad * h))
    X2, Y2 = int(min(W, x2 + pad * w)), int(min(H, y1 + share * h))
    crop = frame[Y1:Y2, X1:X2]
    if crop.size == 0 or min(crop.shape[:2]) < 16:
        return None
    scale = max(1.0, long_side / float(max(crop.shape[:2])))
    if scale > 1.0:
        crop = cv2.resize(crop, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_CUBIC)
    return crop, scale, (X1, Y1)


def find(frame, box):
    """The best face inside a person's box: (crop, face row) or None. The
    face row is YuNet's: x, y, w, h, five landmarks, score -- in the crop."""
    det, _ = _load()
    if det is None:
        return None
    got = head_crop(frame, box)
    if got is None:
        return None
    crop, _, _ = got
    det.setInputSize((crop.shape[1], crop.shape[0]))
    ok, rows = det.detect(crop)
    if rows is None or not len(rows):
        return None
    rows = [r for r in rows if r[-1] >= FACE_SCORE and r[2] >= MIN_FACE]
    if not rows:
        return None
    best = max(rows, key=lambda r: r[-1] * r[2])
    return crop, best


def feature(crop, face):
    """128 numbers for an aligned face, as a unit vector."""
    _, rec = _load()
    if rec is None:
        return None
    aligned = rec.alignCrop(crop, face)
    f = rec.feature(aligned).astype(np.float32).ravel()
    n = float(np.linalg.norm(f))
    return f / n if n else None


def of_person(frame, box):
    """A person's face numbers, or None where no good face is seen."""
    got = find(frame, box)
    if got is None:
        return None
    return feature(*got)


# --------------------------------------------------- AdaFace (27 Nov, beside)
#
# Shamroze, 27 Nov: "face recognition bahut kamzor hai -- GitHub se koi
# model lo". AdaFace IR-101 (adaface.py), made for low-quality faces, is
# run beside SFace on the same aligned face: 512 numbers more. It is used
# where it was measured to help (people/session_handoff/face_bench.py);
# SFace's 128 stay what every stored file holds.
_ada = {"net": None, "failed": False}


def ada_available():
    import adaface
    return os.path.exists(adaface.WEIGHTS) and not _ada["failed"]


def _ada_net():
    if _ada["net"] is None and not _ada["failed"]:
        try:
            import adaface
            _ada["net"] = adaface.AdaFace(threads=2)
        except Exception:                                   # noqa: BLE001
            _ada["failed"] = True
    return _ada["net"]


def aligned(crop, face):
    """The face aligned to the 112x112 template (SFace's alignCrop)."""
    _, rec = _load()
    if rec is None:
        return None
    return rec.alignCrop(crop, face)


def ada_feature(face112):
    """AdaFace's 512 numbers for an aligned face, or None."""
    net = _ada_net() if face112 is not None else None
    return net.embed(face112) if net is not None else None


def of_person_both(frame, box):
    """(SFace's 128, AdaFace's 512 or None) of a person's face, or None
    where no good face is seen."""
    got = find(frame, box)
    if got is None:
        return None
    v = feature(*got)
    if v is None:
        return None
    a = ada_feature(aligned(*got)) if ada_available() else None
    return v, a


def of_photo(img, long_side=640):
    """The face numbers of a portrait (the members directory's photos,
    staff_faces.py): the largest clear face in the whole picture, or
    None."""
    det, _ = _load()
    if det is None or img is None or img.size == 0:
        return None
    import cv2
    scale = long_side / float(max(img.shape[:2]))
    if scale > 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_CUBIC)
    det.setInputSize((img.shape[1], img.shape[0]))
    ok, rows = det.detect(img)
    if rows is None or not len(rows):
        return None
    rows = [r for r in rows if r[-1] >= FACE_SCORE]
    if not rows:
        return None
    best = max(rows, key=lambda r: r[2] * r[3])
    return feature(img, best)


# --------------------------------------------------------------- galleries

def load_gallery(code, folder=None):
    path = os.path.join(folder or GALLERY_DIR, "%s.npy" % code)
    if not os.path.exists(path):
        return np.zeros((0, 128), np.float32)
    try:
        g = np.load(path, allow_pickle=False)
        return g.astype(np.float32).reshape(-1, 128)
    except (OSError, ValueError):
        return np.zeros((0, 128), np.float32)


def add_to_gallery(code, vec, folder=None, keep=GALLERY_MAX):
    """Keep one more face of an employee seen at their own desk -- once
    there are five, only one at least ADMIT like the ones kept (a stranger
    in the chair is not learned as the employee)."""
    if vec is None:
        return False
    folder = folder or GALLERY_DIR
    g = load_gallery(code, folder)
    if len(g) >= 5:
        if score(vec, g) < ADMIT:
            return False          # not this employee's face
    g = np.vstack([g, vec[None, :]])[-keep:]
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, "%s.tmp.npy" % code)
    np.save(tmp, g)
    os.replace(tmp, os.path.join(folder, "%s.npy" % code))
    return True


def score(vec, gallery):
    """How alike a face is to an employee's: the mean of the best three
    of their kept faces (one lucky look-alike sample is not enough)."""
    if vec is None or gallery is None or not len(gallery):
        return 0.0
    sims = np.sort(gallery @ vec)[::-1]
    return float(np.mean(sims[:3]))


def best_match(vec, galleries):
    """(code, score, margin) when a face is clearly one employee's, else
    None."""
    if vec is None:
        return None
    scores = sorted(((score(vec, g), c) for c, g in galleries.items()
                     if len(g)), reverse=True)
    if not scores:
        return None
    top, code = scores[0]
    second = scores[1][0] if len(scores) > 1 else -1.0
    if top < SAME or top - second < MARGIN:
        return None
    return code, top, top - second
