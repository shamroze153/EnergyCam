"""The turnstiles' faces: who passed the gates, and when.

Shamroze, 24 Nov 2026 (HR's approval for the campus, staff told): "turnstile
wala camera on karke sabki picture lo -- kaun aaya, kaun gaya -- phir wahan se
follow karo." Entry H (nvr1 ch5) stands at eye height by the outer
turnstile; Attendance Machine H (nvr1 ch17) looks down on the building
door's. Both see a passer's back on the way in and the face on the way
OUT -- lunch, a smoke, home -- which is when a gate names somebody.

How: one thread a camera keeps the camera's main stream (2560x1440) open
in office hours and, every LOOK seconds, finds faces in the newest frame
(OpenCV's YuNet, its own instance -- the loop's thread has the shared
one), turns each clear face into numbers (SFace, aligned on the full
picture) and compares it with every directory photo (staff_faces.py). A
face far above the line and clear of the next photo (SAME, MARGIN) names
the passer; the rest are kept as "unknown" with their best guess, for
the calibration. The same person twice within REPEAT seconds is one
passage.

Writes people/entrance/<date>.csv and, per passage, under
people/entrance/<date>/: <stem>.jpg (a small face picture), <stem>.f16 (the
face's live numbers) and, for a named passer, <stem>_body.jpg (the clothes)
-- the row's "stem" column names them. Git-ignored, this laptop only, let
go after KEEP_DAYS. Never touches a recorder's settings; a stream that
will not open is tried again after a growing wait, never in a hurry.
"""
import os
import threading
import time
from datetime import datetime

import numpy as np

# Entry H only: on 24 Nov's trial Attendance Machine H (ch17) gave no face
# in 90 s (it looks down on backs), and a second 2560x1440 stream doubled
# the decoding (179% of a core for the two, ~90% for ch5 alone).
CAMERAS = [("nvr1", 5)]
OUT = os.path.join("people", "entrance")
LOOK = 0.4               # s between looks at the newest frame
HOURS = ("07:00", "22:30")
FACE_SCORE = 0.85
MIN_FACE = 40            # px wide in the full picture
DETECT_WIDTH = 1280      # the picture is searched at this width
# Stricter than a seat's: 24 Nov's playback of 23 Nov named two passers at
# 0.48-0.53 whose faces, bowed, did not plainly match their photos by eye,
# and one photo was the best guess for several bearded men -- so a gate
# names only at 0.50, by 0.10; gate_match.py's votes over days do the rest.
SAME = 0.50
MARGIN = 0.10
# Only a face turned to the camera is compared (24 Nov trial: the frontal
# face of a passer, yaw -0.16, matched one photo at 0.52 by 0.16, and the
# near-frontal one, 0.28, the same photo; his profiles, yaw 0.6-4.7,
# matched nobody, 0.21-0.32). Yaw: the nose's offset from between the
# eyes, in eye distances.
MAX_YAW = 0.3
MIN_EYES = 25            # px between the eyes in the full picture


def yaw(row):
    """How far a YuNet face is turned: 0 straight on, about 0.5+ turned."""
    rx, lx, nx = float(row[4]), float(row[6]), float(row[8])
    d = abs(lx - rx)
    return 9.9 if d < 1.0 else (nx - (rx + lx) / 2.0) / d


def frontal(row, min_eyes=MIN_EYES, max_yaw=MAX_YAW):
    """A face to compare: turned to the camera, eyes far enough apart."""
    return abs(float(row[6]) - float(row[4])) >= min_eyes and \
        abs(yaw(row)) <= max_yaw
REPEAT = 90              # s: the same person again is the same passage
UNKNOWN_REPEAT = 20      # s: an unknown face this alike again is the same
KEEP_DAYS = 14
COLUMNS = "time,recorder,channel,status,employee_id,best,score,margin,face_w"
# 25 Nov (the face study): 2,277 of 12,978 rows (17.5%) had no picture --
# two faces the same second with the same label (two "unknown"s in one
# frame, or two looks in one second) wrote one file name, the later over
# the earlier. Each passage now has a stem of its own, <HHMMSS>_ch.._<id>
# and then <HHMMSS>-2_ch.._<id>, ..., kept in the row's "stem" column (in
# a day's file begun with it; an older file keeps its nine columns).
# Also 25 Nov: rescored from the 160-px picture, a named face loses ~0.065
# and only 87-91% keep their best photo -- so the live numbers are kept,
# <stem>.f16: the SFace unit vector (128), then YuNet's row in the full
# picture's pixels (15: x, y, w, h, the five landmarks' x y, score).
FACE_LEN = 128 + 15
_lock = threading.Lock()     # the backfill writes from several threads
_taken = {}                  # day folder -> stems given out
_threads = []


def decide(vec, ids, vecs, recent, t, same=SAME, margin=MARGIN, cctv=None):
    """One face against the directory: ("named" | "unknown" | None,
    best_id, score, margin). None when it is the same passage as a recent
    one (recent: [(t, id_or_None, vec)], newest last; updated here).
    cctv: (ids, vecs) of the named people's faces in our own cameras
    (cctv_faces.py) -- a person's score is the better of the photo's and
    their CCTV gallery's."""
    if vec is None or not len(ids):
        return None, "", 0.0, 0.0
    s = vecs @ vec
    sc = {str(i): float(v) for i, v in zip(ids, s)}
    if cctv is not None and len(cctv[0]):
        import cctv_faces
        for eid, v in cctv_faces.scores(vec, cctv[0], cctv[1]).items():
            sc[eid] = max(sc.get(eid, -1.0), v)
    ranked = sorted(sc.items(), key=lambda kv: -kv[1])
    best, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else -1.0
    named = top >= same and top - second >= margin
    while recent and t - recent[0][0] > max(REPEAT, UNKNOWN_REPEAT):
        recent.pop(0)
    for rt, rid, rvec in recent:
        if named and rid == best and t - rt <= REPEAT:
            return None, best, top, top - second
        if not named and rid is None and t - rt <= UNKNOWN_REPEAT and \
                float(np.dot(rvec, vec)) >= 0.6:
            return None, best, top, top - second
    recent.append((t, best if named else None, vec))
    return ("named" if named else "unknown"), best, top, top - second


def body_box(face, w, h):
    """Where a passer's clothes are, from their face (x, y, fw, fh): from
    just above the face down six and a half faces, three faces wide --
    the shirt and what shows below it, as the gate sees them."""
    x, y, fw, fh = (float(v) for v in face[:4])
    return (int(max(0, x - 1.0 * fw)), int(max(0, y - 0.2 * fh)),
            int(min(w, x + 2.0 * fw)), int(min(h, y + 6.5 * fh)))


def _stem(pics, row):
    """A file stem no other passage of the day has: <HHMMSS>_ch.._<id>,
    else <HHMMSS>-2_ch.._<id>, -3, ... (it still ends in _<id>, which
    name_suggest and clothes_match read)."""
    taken = _taken.setdefault(pics, set())
    if len(_taken) > 3:                      # yesterday's folders let go
        for k in [k for k in _taken if k != pics]:
            _taken.pop(k, None)
    hhmmss, tail = row[0].replace(":", ""), "_ch%02d_%s" % (
        row[2], row[4] or "unknown")
    stem, k = hhmmss + tail, 1
    while stem in taken or any(os.path.exists(os.path.join(
            pics, stem + ext)) for ext in (".jpg", ".f16")):
        k += 1
        stem = "%s-%d%s" % (hhmmss, k, tail)
    taken.add(stem)
    return stem


def _stem_column(path):
    """Whether the day's file was begun with the "stem" column (read each
    time, not remembered: a file written anew keeps no stale answer)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return "stem" in fh.readline().strip().split(",")
    except OSError:
        return False


def write(day, row, crop=None, out=None, body=None, face=None):
    """One passage to people/entrance/<day>.csv, and under <day>/ its face
    picture (<stem>.jpg), its live numbers (face = (vector, YuNet row) ->
    <stem>.f16) and for a named one the clothes (<stem>_body.jpg -- 24 Nov,
    the same day's clothes say which desk is theirs where the desk's camera
    sees no face). Returns the stem."""
    folder = out or OUT
    pics = os.path.join(folder, day)
    with _lock:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, day + ".csv")
        new = not os.path.exists(path)
        stem = _stem(pics, row)
        line = "%s,%s,%d,%s,%s,%s,%.3f,%.3f,%d" % row
        if new or _stem_column(path):
            line += "," + stem
        with open(path, "a", encoding="utf-8") as fh:
            if new:
                fh.write(COLUMNS + ",stem\n")
            fh.write(line + "\n")
        if face is not None:
            vec, det_row = face
            nums = np.zeros(FACE_LEN, np.float32)
            v = np.asarray(vec, np.float32).ravel()[:128]
            r = np.asarray(det_row, np.float32).ravel()[:FACE_LEN - 128]
            nums[:len(v)], nums[128:128 + len(r)] = v, r
            os.makedirs(pics, exist_ok=True)
            nums.astype(np.float16).tofile(os.path.join(pics, stem + ".f16"))
        if crop is not None:
            import cv2
            os.makedirs(pics, exist_ok=True)
            cv2.imwrite(os.path.join(pics, stem + ".jpg"), crop,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
        if body is not None and getattr(body, "size", 0) and row[4]:
            import cv2
            os.makedirs(pics, exist_ok=True)
            cv2.imwrite(os.path.join(pics, stem + "_body.jpg"), body,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
    if new:
        _forget_old(folder)
    return stem


def live_face(day, stem, folder=None):
    """(unit vector (128,), YuNet row (15,)) of one passage as the gate saw
    it live, or None (a passage kept before 25 Nov's change has none)."""
    p = os.path.join(folder or OUT, day, "%s.f16" % stem)
    try:
        v = np.fromfile(p, np.float16).astype(np.float32)
    except (OSError, ValueError):
        return None
    if len(v) < FACE_LEN:
        return None
    vec = v[:128] / max(float(np.linalg.norm(v[:128])), 1e-6)
    return vec, v[128:FACE_LEN]


def _forget_old(folder):
    cutoff = time.time() - KEEP_DAYS * 86400
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        try:
            if os.path.getmtime(p) < cutoff:
                if os.path.isdir(p):
                    import shutil
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
        except OSError:
            pass


class Watch(threading.Thread):
    """One turnstile camera, watched in office hours."""

    def __init__(self, recorder, channel, url):
        super().__init__(daemon=True, name="entrance-%s-%d" % (recorder,
                                                              channel))
        self.recorder, self.channel, self._url = recorder, channel, url
        self.recent = []
        self.passages = 0
        self.stop_flag = False

    def _nets(self):
        import cv2
        import faces
        det = cv2.FaceDetectorYN.create(faces.DETECTOR, "", (320, 320),
                                        FACE_SCORE, 0.3, 20)
        rec = cv2.FaceRecognizerSF.create(faces.RECOGNIZER, "")
        return det, rec

    def run(self):
        import cv2
        import staff_faces
        from progress_track import PKT
        wait = 60
        try:
            det, rec = self._nets()
        except Exception:                                   # noqa: BLE001
            return                      # no face models: nothing to do
        ids, vecs = staff_faces.load_faces()
        loaded = time.time()
        while not self.stop_flag:
            now = datetime.now(PKT)
            if not (HOURS[0] <= now.strftime("%H:%M") <= HOURS[1]):
                time.sleep(60)
                continue
            if time.time() - loaded > 3600:          # the roster, hourly
                ids, vecs = staff_faces.load_faces()
                loaded = time.time()
            # timeouts: a silent recorder must not hold OpenCV's open (and
            # every other camera's) -- 25 Nov, the loop stood still an hour
            cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000])
            if not cap.isOpened():
                cap.release()
                time.sleep(wait)
                wait = min(wait * 2, 600)
                continue
            wait = 60
            last_look, misses = 0.0, 0
            while not self.stop_flag:
                if not cap.grab():
                    misses += 1
                    if misses > 50:
                        break
                    time.sleep(0.05)
                    continue
                misses = 0
                if time.time() - last_look < LOOK:
                    continue
                last_look = time.time()
                ok, frame = cap.retrieve()
                if not ok or frame is None:
                    continue
                now = datetime.now(PKT)
                if not (HOURS[0] <= now.strftime("%H:%M") <= HOURS[1]):
                    break
                try:
                    self.look(frame, det, rec, ids, vecs, now)
                except Exception:                           # noqa: BLE001
                    pass
            cap.release()

    def look(self, frame, det, rec, ids, vecs, now, out=None):
        """One frame: each clear face, matched and written."""
        import cv2
        h, w = frame.shape[:2]
        k = DETECT_WIDTH / float(w) if w > DETECT_WIDTH else 1.0
        small = cv2.resize(frame, None, fx=k, fy=k) if k < 1.0 else frame
        det.setInputSize((small.shape[1], small.shape[0]))
        _, rows = det.detect(small)
        if rows is None:
            return 0
        n = 0
        for r in rows:
            if r[-1] < FACE_SCORE:
                continue
            full = r.copy()
            full[:14] = r[:14] / k
            if full[2] < MIN_FACE or not frontal(full):
                continue
            aligned = rec.alignCrop(frame, full)
            v = rec.feature(aligned).astype(np.float32).ravel()
            v /= max(float(np.linalg.norm(v)), 1e-6)
            try:
                import cctv_faces
                cctv = cctv_faces.load()
            except Exception:                               # noqa: BLE001
                cctv = None
            status, best, score, margin = decide(v, ids, vecs, self.recent,
                                                 time.time(), cctv=cctv)
            if status is None:
                continue
            x, y, fw, fh = (int(v_) for v_ in full[:4])
            pad = int(0.35 * fw)
            crop = frame[max(0, y - pad):min(h, y + fh + pad),
                         max(0, x - pad):min(w, x + fw + pad)]
            if crop.size:
                crop = cv2.resize(crop, (160, int(160 * crop.shape[0]
                                                  / max(1, crop.shape[1]))))
            body = None
            if status == "named":
                bx1, by1, bx2, by2 = body_box(full, w, h)
                body = frame[by1:by2, bx1:bx2]
                if body.size:
                    body = cv2.resize(body, (int(256 * body.shape[1]
                                                 / max(1, body.shape[0])),
                                             256))
            write(now.strftime("%Y-%m-%d"),
                  (now.strftime("%H:%M:%S"), self.recorder, self.channel,
                   status, best if status == "named" else "", best, score,
                   margin, int(full[2])), crop if crop.size else None, out,
                  body=body, face=(v, full[:15]))
            self.passages += 1
            n += 1
        return n


def start(recorders, build_url, cameras=CAMERAS):
    """Start a watch per turnstile camera (room_loop.main); never raises.
    Returns how many started."""
    try:
        import faces
        import staff_faces
        if not faces.available() or not os.path.exists(staff_faces.FACES):
            return 0
        n = 0
        for rec_name, ch in cameras:
            rec = recorders.get(rec_name)
            if not rec or not rec.get("user"):
                continue
            url = build_url(rec["host"], ch, rec["user"], rec["password"],
                            True, rec.get("brand", "hikvision"))
            t = Watch(rec_name, ch, url)
            t.start()
            _threads.append(t)
            n += 1
        return n
    except Exception:                                       # noqa: BLE001
        return 0
