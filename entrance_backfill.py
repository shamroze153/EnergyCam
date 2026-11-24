"""The turnstile's faces on days gone by, from the recorder's own recording.

Shamroze, 24 Nov 2026: "previous days ka record utha ke dekh sakte ho aur
match kar sakte ho, employees ke desk mein aane ka intezaar kiye bagair."
nvr1 plays back any time of a channel over RTSP (Hikvision's
/Streaming/tracks/<ch>01?starttime=YYYYMMDDTHHMMSSZ -- read as local time,
checked on 24 Nov: 18:30 played 18:30). Reading only: no setting of the
recorder is touched.

The recording plays at its own pace -- an hour takes an hour -- so this is
for the night, a few windows at once (WORKERS), each read exactly as the
live watch reads (entrance_watch.Watch.look: frontal faces only, against
every directory photo), into the same people/entrance/<date>.csv.

    python entrance_backfill.py 2026-11-23 [2026-11-20 ...]
"""
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import entrance_watch as ew

# When people leave through the gate: lunch and smoke breaks, and home.
WINDOWS = [("13:00", "15:30"), ("17:00", "22:00")]
WORKERS = 3
CHUNK_MIN = 50            # each playback session reads this many minutes
DONE = os.path.join("people", "entrance", "backfilled.txt")


def playback_url(rec, channel, start, user, password):
    return "rtsp://%s:%s@%s:554/Streaming/tracks/%d01?starttime=%s" % (
        quote(user, safe=""), quote(password, safe=""), rec["host"],
        int(channel), start.strftime("%Y%m%dT%H%M%SZ"))


def chunks(day, windows=None, minutes=CHUNK_MIN):
    """(start, end) datetimes covering the day's windows (WINDOWS, read
    when called -- 24 Nov: a default bound at import read the whole day
    when a trial had set four minutes)."""
    out = []
    for a, b in (windows if windows is not None else WINDOWS):
        t = datetime.strptime("%s %s" % (day, a), "%Y-%m-%d %H:%M")
        end = datetime.strptime("%s %s" % (day, b), "%Y-%m-%d %H:%M")
        while t < end:
            out.append((t, min(end, t + timedelta(minutes=minutes))))
            t += timedelta(minutes=minutes)
    return out


def done_before(path=DONE):
    if not os.path.exists(path):
        return set()
    return set(open(path, encoding="utf-8").read().split())


def read_chunk(rec, channel, start, end, user, password, nets_for, out=None):
    """Play back one stretch and read it as the live watch would. Returns
    how many passages it wrote."""
    import cv2
    from progress_track import PKT
    det, rec_net = nets_for()
    import staff_faces
    ids, vecs = staff_faces.load_faces()
    w = ew.Watch(rec.get("name", "nvr1"), channel, "")
    cap = cv2.VideoCapture(playback_url(rec, channel, start, user, password),
                           cv2.CAP_FFMPEG)
    if not cap.isOpened():
        return -1
    t0, last, misses = time.time(), 0.0, 0
    length = (end - start).total_seconds()
    while time.time() - t0 < length + 30:
        if not cap.grab():
            misses += 1
            if misses > 100:
                break
            time.sleep(0.05)
            continue
        misses = 0
        if time.time() - last < ew.LOOK:
            continue
        last = time.time()
        ok, frame = cap.retrieve()
        if not ok or frame is None:
            continue
        # the recording plays in step with the clock: its time is the
        # stretch's start plus the time since it began
        when = (start + timedelta(seconds=time.time() - t0)).replace(
            tzinfo=PKT)
        if when > end.replace(tzinfo=PKT):
            break
        try:
            w.look(frame, det, rec_net, ids, vecs, when, out)
        except Exception:                                   # noqa: BLE001
            pass
    cap.release()
    return w.passages


def run(days, recorders, user, password, channel=5, workers=WORKERS,
        out=None):
    """Every window of every day, WORKERS stretches at a time; a stretch
    read before (DONE) is not read again. Returns passages written."""
    import cv2
    import faces
    rec = recorders["nvr1"]
    rec.setdefault("name", "nvr1")
    todo = [(d, a, b) for d in days for a, b in chunks(d)
            if "%s_%s" % (d, a.strftime("%H%M")) not in done_before()]
    lock = threading.Lock()
    total = [0]

    def nets():
        return (cv2.FaceDetectorYN.create(faces.DETECTOR, "", (320, 320),
                                          ew.FACE_SCORE, 0.3, 20),
                cv2.FaceRecognizerSF.create(faces.RECOGNIZER, ""))

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                d, a, b = todo.pop(0)
            n = read_chunk(rec, channel, a, b, user, password, nets, out)
            with lock:
                if n >= 0:
                    total[0] += n
                    os.makedirs(os.path.dirname(DONE), exist_ok=True)
                    with open(DONE, "a", encoding="utf-8") as fh:
                        fh.write("%s_%s\n" % (d, a.strftime("%H%M")))
                print(">> %s %s-%s: %s passage(s)" % (
                    d, a.strftime("%H:%M"), b.strftime("%H:%M"),
                    n if n >= 0 else "no playback"), flush=True)
    threads = [threading.Thread(target=worker, daemon=True)
               for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return total[0]


def main(argv):
    days = argv[1:]
    if not days:
        print(__doc__)
        return
    from dotenv import load_dotenv
    load_dotenv()
    import room_loop
    recorders, _ = room_loop.load_rooms("rooms.yaml", ["nvr1"], None)
    user, password = room_loop.recorder_login("nvr1", recorders["nvr1"])
    n = run(days, recorders, user, password)
    print(">> backfill done: %d passage(s) written" % n)


if __name__ == "__main__":
    main(sys.argv)
