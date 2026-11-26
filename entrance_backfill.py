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

    python entrance_backfill.py 2026-11-23 [2026-11-20 ...] [--workers 2]

One login try: the first stretch opens alone, and a stretch that will not
open stops the whole run (26 Nov: a refused login is never tried again --
these recorders lock the account). The others start once one has opened.

A face's time is the recording's own (the stream's clock from the stretch's
start), not the time since it began playing: 25 Nov's study found 23 Nov's
evening drifted by minutes -- three streams decoded more slowly than the
recorder sent them, so wall-clock time ran ahead of the picture.
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
SLACK = 120.0             # s the stream's clock may run ahead of the wall's


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


def stream_seconds(pos_msec, wall, slack=SLACK):
    """Seconds into the stretch: the stream's own clock (OpenCV's position,
    ms) when it is sane -- above zero and not further ahead of the time it
    has been playing than `slack` -- else the time it has been playing."""
    try:
        pos = float(pos_msec) / 1000.0
    except (TypeError, ValueError):
        return wall
    if pos <= 0.0 or pos > wall + slack:
        return wall
    return pos


STATS = {}               # (day, HHMM) -> {"drift": s, "clock": "stream"|...}


def read_chunk(rec, channel, start, end, user, password, nets_for, out=None,
               on_open=None):
    """Play back one stretch and read it as the live watch would. Returns
    how many passages it wrote, or -1 when the stretch would not open.
    on_open(): called once the playback has opened (run() lets the other
    workers start then)."""
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
    if on_open is not None:
        on_open()
    t0, last, misses = time.time(), 0.0, 0
    length = (end - start).total_seconds()
    drift, by_stream = 0.0, 0
    # a stream decoded more slowly than it is sent takes longer than its
    # length: read on until the picture's own time reaches the end, within
    # a wall-clock limit
    while time.time() - t0 < 1.5 * length + 60:
        if not cap.grab():
            misses += 1
            if misses > 100:
                break
            time.sleep(0.05)
            continue
        misses = 0
        wall = time.time() - t0
        secs = stream_seconds(cap.get(cv2.CAP_PROP_POS_MSEC), wall)
        if secs > length:
            break
        if time.time() - last < ew.LOOK:
            continue
        last = time.time()
        ok, frame = cap.retrieve()
        if not ok or frame is None:
            continue
        if secs != wall:
            by_stream += 1
            drift = max(drift, wall - secs)
        when = (start + timedelta(seconds=secs)).replace(tzinfo=PKT)
        try:
            w.look(frame, det, rec_net, ids, vecs, when, out)
        except Exception:                                   # noqa: BLE001
            pass
    cap.release()
    STATS[(start.strftime("%Y-%m-%d"), start.strftime("%H%M"))] = {
        "drift": round(drift, 1), "clock": "stream" if by_stream else "wall",
        "minutes": round((time.time() - t0) / 60.0, 1)}
    return w.passages


def run(days, recorders, user, password, channel=5, workers=WORKERS,
        out=None):
    """Every window of every day, WORKERS stretches at a time; a stretch
    read before (DONE) is not read again. Returns passages written."""
    import cv2
    import faces
    rec = recorders["nvr1"]
    rec.setdefault("name", "nvr1")
    done = done_before(DONE)
    todo = [(d, a, b) for d in days for a, b in chunks(d)
            if "%s_%s" % (d, a.strftime("%H%M")) not in done]
    lock = threading.Lock()
    total = [0]
    opened = threading.Event()        # one stretch has opened: the rest may
    refused = threading.Event()       # one would not: nobody tries again

    def nets():
        return (cv2.FaceDetectorYN.create(faces.DETECTOR, "", (320, 320),
                                          ew.FACE_SCORE, 0.3, 20),
                cv2.FaceRecognizerSF.create(faces.RECOGNIZER, ""))

    def worker(first):
        if not first:
            while not (opened.is_set() or refused.is_set()):
                time.sleep(0.5)
        while not refused.is_set():
            with lock:
                if not todo:
                    return
                d, a, b = todo.pop(0)
            n = read_chunk(rec, channel, a, b, user, password, nets, out,
                           on_open=opened.set)
            with lock:
                if n >= 0:
                    total[0] += n
                    os.makedirs(os.path.dirname(DONE), exist_ok=True)
                    with open(DONE, "a", encoding="utf-8") as fh:
                        fh.write("%s_%s\n" % (d, a.strftime("%H%M")))
                else:
                    refused.set()     # a refused login is never retried
                st = STATS.get((d, a.strftime("%H%M")), {})
                print(">> %s %s-%s: %s%s" % (
                    d, a.strftime("%H:%M"), b.strftime("%H:%M"),
                    ("%d passage(s)" % n) if n >= 0 else
                    "no playback -- stopping, no other stretch is tried",
                    (" (clock %s, behind by up to %.0f s, %.0f min)"
                     % (st["clock"], st["drift"], st["minutes"]))
                    if st else ""), flush=True)
    threads = [threading.Thread(target=worker, args=(i == 0,), daemon=True)
               for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return total[0]


def main(argv):
    args = list(argv[1:])
    workers = WORKERS
    if "--workers" in args:
        i = args.index("--workers")
        workers = max(1, min(WORKERS, int(args[i + 1])))
        del args[i:i + 2]
    days = args
    if not days:
        print(__doc__)
        return
    from dotenv import load_dotenv
    load_dotenv()
    import room_loop
    recorders, _ = room_loop.load_rooms("rooms.yaml", ["nvr1"], None)
    user, password = room_loop.recorder_login("nvr1", recorders["nvr1"])
    n = run(days, recorders, user, password, workers=workers)
    print(">> backfill done: %d passage(s) written" % n)


if __name__ == "__main__":
    main(sys.argv)
