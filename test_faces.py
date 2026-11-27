"""Check the gate's faces read again with the machines (gate_match), the
recordings read again (entrance_backfill, replay_day) and the nightly hook
(desk_match). Synthetic numbers only -- no picture, no name, no ID.

    python test_faces.py
"""
import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

FAILURES = []
DAY = "2026-11-20"           # a Friday


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def at(hhmmss):
    return pd.Timestamp("%s %s" % (DAY, hhmmss))


def unit(i, dim=128):
    v = np.zeros(dim, np.float32)
    v[i] = 1.0
    return v


def face_like(i, cos, noise=100):
    """A unit face whose cosine to photo i is `cos` (and 0 to the others:
    the rest of it lies along an axis no photo uses)."""
    v = cos * unit(i) + np.sqrt(1.0 - cos * cos) * unit(noise)
    return (v / np.linalg.norm(v)).astype(np.float32)


def punches(rows):
    """attendance.load()'s frame from [(eid, "HH:MM:SS", "in"|"out")]."""
    return pd.DataFrame({
        "eid": [r[0] for r in rows],
        "at": [at(r[1]) for r in rows],
        "kind": [r[2] for r in rows],
        "place": ["140-H %s" % r[2].upper() for r in rows]}).sort_values(
            "at").reset_index(drop=True)


def check_backfill():
    print("-- the recording read again: its own clock, one login try")
    import entrance_backfill as eb
    check("the stream's clock when sane (behind the wall's)",
          eb.stream_seconds(5000, 10.0), 5.0)
    check("a little ahead of the wall is still the stream's",
          eb.stream_seconds(125000, 10.0), 125.0)
    check("no position yet: the wall's", eb.stream_seconds(0, 10.0), 10.0)
    check("a position far ahead (a clock of its own): the wall's",
          eb.stream_seconds(9e9, 10.0), 10.0)
    check("no number at all: the wall's", eb.stream_seconds(None, 7.0), 7.0)
    folder = tempfile.mkdtemp()
    real_read, real_done = eb.read_chunk, eb.DONE
    try:
        eb.DONE = os.path.join(folder, "backfilled.txt")
        calls = []

        def refused(rec, ch, a, b, user, password, nets, out=None,
                    on_open=None):
            calls.append(a)
            return -1
        eb.read_chunk = refused
        n = eb.run([DAY], {"nvr1": {"host": "h"}}, "u", "p", workers=3)
        check("a stretch that will not open: no other is tried (one login "
              "try), nothing marked read", (len(calls), n,
                                            os.path.exists(eb.DONE)),
              (1, 0, False))
        calls[:] = []

        def opens(rec, ch, a, b, user, password, nets, out=None,
                  on_open=None):
            if on_open:
                on_open()
            calls.append(a)
            return 2
        eb.read_chunk = opens
        n = eb.run([DAY], {"nvr1": {"host": "h"}}, "u", "p", workers=3)
        want = len(eb.chunks(DAY))
        check("once one has opened the others follow: every stretch read, "
              "each marked", (len(calls), n, len(open(eb.DONE).read()
                                                 .split())),
              (want, 2 * want, want))
    finally:
        eb.read_chunk, eb.DONE = real_read, real_done
        shutil.rmtree(folder)


def check_replay_plan():
    print("-- days read again: the loop's gaps, several days in one run")
    import replay_day as rd
    p = pd.DataFrame({"start": [at("12:00:00")], "end": [at("12:01:00")],
                      "camera": [None]})

    def passes_of(day):
        k = pd.Timestamp(day) - pd.Timestamp(DAY)
        return p.assign(start=p["start"] + k, end=p["end"] + k)
    plan = rd.plan_days("%s, 2026-11-23" % DAY, "12:00", "12:10", 5, False,
                        passes_of)
    check("each day's gaps only (12:00 was watched)",
          [(d, [t.strftime("%H:%M") for t in ts]) for d, ts in plan],
          [(DAY, ["12:05", "12:10"]), ("2026-11-23", ["12:05", "12:10"])])
    plan = rd.plan_days(DAY, "12:00", "12:10", 5, True, passes_of)
    check("--all: every moment", [t.strftime("%H:%M") for t in plan[0][1]],
          ["12:00", "12:05", "12:10"])
    check("never more than three playback streams at once", rd.STREAMS, 3)


def check_crop_paths():
    print("-- each gate row's own picture")
    import gate_match as gm
    old = pd.DataFrame({"time": ["10:00:01", "10:00:01", "10:00:02"],
                        "channel": ["5", "5", "5"],
                        "employee_id": ["", "", "00010"]})
    got = [os.path.basename(p) for p in gm.crop_paths(DAY, old, "x")]
    check("before the stem column: two rows the same second and label "
          "shared one picture -- only the later owns it",
          got, ["", "100001_ch05_unknown.jpg", "100002_ch05_00010.jpg"])
    new = old.assign(stem=["100001_ch05_unknown", "100001-2_ch05_unknown",
                           "100002_ch05_00010"])
    got = [os.path.basename(p) for p in gm.crop_paths(DAY, new, "x")]
    check("with the stem column: each row its own",
          got, ["100001_ch05_unknown.jpg", "100001-2_ch05_unknown.jpg",
                "100002_ch05_00010.jpg"])


def gate_rows(spec):
    """day_faces()'s rows from [(HH:MM:SS, status, employee_id)]."""
    d = pd.DataFrame(spec, columns=["time", "status", "employee_id"])
    d["t"] = pd.to_datetime(DAY + " " + d["time"])
    d["crop"] = ["c%d.jpg" % i for i in range(len(d))]
    d["live"] = True
    d["face_w"] = "60"
    return d


def check_machines():
    print("-- the gate's faces with the machines beside them")
    import gate_match as gm
    # five named exits of employee 10, the gate's clock 160 s ahead
    outs = ["12:00:00", "13:00:00", "14:00:00", "15:00:00", "16:00:00"]
    spec = [((at(o) + pd.Timedelta(seconds=160 + k)).strftime("%H:%M:%S"),
             "named", "00010") for k, o in enumerate(outs)]
    data = punches([("10", "09:00:00", "in")]
                   + [("10", o, "out") for o in outs]
                   + [("10", o2, "in") for o2 in ("12:30:00", "13:30:00",
                                                    "14:30:00", "15:30:00")]
                   + [("20", "09:30:00", "in"),          # inside all day
                      ("30", "09:00:00", "in"), ("30", "11:00:00", "out")])
    rows = gate_rows(spec)
    off, bad = gm.clock(DAY, rows, data)
    check("the gate's clock against the machines': +160 s, no hour astray",
          (round(off), bad), (162, {}))
    # four exits at 12:xx right (+160 s), three at 17:xx astray (+300 s)
    o12 = ["12:00:00", "12:15:00", "12:30:00", "12:45:00"]
    o17 = ["17:00:00", "17:15:00", "17:30:00"]
    d2 = punches([("10", "09:00:00", "in")]
                 + [("10", o, "out") for o in o12 + o17])
    drift = gate_rows(
        [((at(o) + pd.Timedelta(seconds=160)).strftime("%H:%M:%S"), "named",
          "00010") for o in o12]
        + [((at(o) + pd.Timedelta(seconds=300)).strftime("%H:%M:%S"),
            "named", "00010") for o in o17])
    off2, bad2 = gm.clock(DAY, drift, d2)
    check("an hour whose clock strays: it, and every hour not shown right, "
          "left out", (round(off2), 17 in bad2, 12 in bad2, 3 in bad2),
          (160, True, False, True))
    ids = np.array(["00010", "00020", "00030"])
    V = np.stack([unit(0), unit(1), unit(2)])
    test = gate_rows(spec + [
        ("12:30:00", "unknown", ""),       # 20's face, 20 inside
        ("12:31:00", "unknown", ""),       # 30's face, 30 gone at 11:00
        ("13:45:00", "unknown", ""),       # 10's face, 10 inside, no exit
        ("16:02:50", "unknown", "")])      # 10's face at their OUT punch
    X = np.stack([face_like(0, 0.6)] * len(spec)
                 + [face_like(1, 0.5), face_like(2, 0.7),
                    face_like(0, 0.42), face_like(0, 0.42)])
    got = gm.machine_names(DAY, test, X, ids, V, data)
    by_time = {r.time: (r.rule, r.employee_id) for r in got.itertuples()}
    check("a face at its own OUT punch (clock set right): an exit, even "
          "at 0.42", by_time.get("16:02:50"), ("exit", "00010"))
    check("inside by the machines, 0.45 or more: gate+machines",
          by_time.get("12:30:00"), ("inside", "00020"))
    check("a face like somebody who had left: no name",
          by_time.get("12:31:00"), None)
    check("inside but under 0.45 and no OUT punch near: no name",
          by_time.get("13:45:00"), None)


def check_nightly():
    print("-- the night's run: gate_machines/<day>.csv and the gallery")
    import entrance_watch as ew
    import gate_match as gm
    base = tempfile.mkdtemp()
    try:
        gate = os.path.join(base, "entrance")
        mach = os.path.join(base, "machines")
        gal = os.path.join(base, "gallery.npz")
        outs = ["12:00:00", "13:00:00", "14:00:00", "15:00:00", "16:00:00"]
        data = punches([("10", "09:00:00", "in")]
                       + [("10", o, "out") for o in outs]
                       + [("10", o2, "in") for o2 in ("12:30:00", "13:30:00",
                                                        "14:30:00",
                                                        "15:30:00")])
        for k, o in enumerate(outs):
            t = (at(o) + pd.Timedelta(seconds=160 + k)).strftime("%H:%M:%S")
            ew.write(DAY, (t, "nvr1", 5, "named", "00010", "00010", 0.6, 0.3,
                           60), out=gate, face=(face_like(0, 0.6),
                                                np.zeros(15)))
        ew.write(DAY, ("16:02:50", "nvr1", 5, "unknown", "", "00010", 0.42,
                       0.4, 60), out=gate, face=(face_like(0, 0.42),
                                                 np.zeros(15)))
        ids = np.array(["00010", "00020"])
        V = np.stack([unit(0), unit(1)])
        s = gm.nightly_faces(folder=gate, out=mach, gallery=gal, data=data,
                             photos=(ids, V))
        m = pd.read_csv(os.path.join(mach, DAY + ".csv"), dtype=str)
        gids, gv = gm.load_gallery(gal)
        check("every exit kept, the unknown one at its punch among them",
              (int((m["rule"] == "exit").sum()),
               "16:02:50" in set(m["time"])), (6, True))
        check("the gallery: the person's faces at their own OUT punches, "
              "their live numbers", (list(gids), round(float(gv[0] @
                                                             unit(0)), 2)),
              (["00010"] * 6, 0.6))
        check("a summary for the log", s.startswith("gate faces: 1 day(s), "
                                                    "6 exit face(s) of 1 "),
              True)
        check("no day outside HR's export is read",
              gm.nightly_faces(days=["2026-11-21"], folder=gate, out=mach,
                               gallery=gal, data=data, photos=(ids, V))
              .startswith("gate faces: 0 day(s)"), True)
        check("nothing written in the gate's own folder but its days",
              sorted(f for f in os.listdir(gate) if f.endswith(".csv")),
              [DAY + ".csv"])
    finally:
        shutil.rmtree(base)


def check_hook():
    print("-- desk_match's night run reads the gate's faces, never raises")
    import desk_match as dm
    import gate_match as gm
    real = gm.nightly_faces
    try:
        def boom(*a, **k):
            raise RuntimeError("no models")
        gm.nightly_faces = boom
        check("a failure is a line in the log, not a crash",
              dm.gate_faces(), "gate faces: not read (RuntimeError)")
        gm.nightly_faces = lambda *a, **k: "gate faces: 2 day(s)"
        check("the summary otherwise", dm.gate_faces(),
              "gate faces: 2 day(s)")
    finally:
        gm.nightly_faces = real


def check_safetensors():
    """27 Nov: AdaFace's weights are read by our own small reader of the
    safetensors format (no pickle, nothing executed from the file)."""
    import json
    import struct
    import tempfile
    import adaface
    a = np.arange(6, dtype="<f4").reshape(2, 3)
    b = np.array([1.5, -2.0], dtype="<f2")
    data = a.tobytes() + b.tobytes()
    head = {"x.weight": {"dtype": "F32", "shape": [2, 3],
                         "data_offsets": [0, a.nbytes]},
            "y": {"dtype": "F16", "shape": [2],
                  "data_offsets": [a.nbytes, a.nbytes + b.nbytes]},
            "__metadata__": {"format": "pt"}}
    h = json.dumps(head).encode()
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "t.safetensors")
        with open(p, "wb") as fh:
            fh.write(struct.pack("<Q", len(h)) + h + data)
        got = adaface.read_safetensors(p)
        check("safetensors: names, shapes and numbers read back",
              (sorted(got), got["x.weight"].tolist(), got["y"].tolist()),
              (["x.weight", "y"], a.tolist(), [1.5, -2.0]))
    finally:
        import shutil
        shutil.rmtree(d)


def check_ada_budget():
    """27 Nov: AdaFace at the seats is held to ADA_BUDGET seconds a minute,
    so the loop's pass never waits on it; a new minute starts afresh."""
    import seat_faces as sf
    saved = dict(sf._ada_clock)
    try:
        t = 6000.0 * 60
        sf._ada_clock.update(minute=0, spent=0.0)
        check("a fresh minute: AdaFace runs", sf._ada_ok(t), True)
        sf._ada_spent(sf.ADA_BUDGET - 1.0, t + 5)
        check("under the budget: still runs", sf._ada_ok(t + 10), True)
        sf._ada_spent(2.0, t + 20)
        check("past the budget: SFace only", sf._ada_ok(t + 30), False)
        check("the next minute: runs again", sf._ada_ok(t + 61), True)
    finally:
        sf._ada_clock.clear()
        sf._ada_clock.update(saved)


def check_ada_seat_face():
    """27 Nov: a seat's many AdaFace samples are weighted by AdaFace's own
    quality (the length of its numbers): the clear faces lead, the blurred
    ones -- seen from above, turned away -- hardly count."""
    import seat_faces as sf
    rng = np.random.default_rng(7)
    good = np.zeros((6, 512), np.float32)
    good[:, 0] = 1.0
    good += rng.normal(0, 0.05, good.shape).astype(np.float32)
    good = good / np.linalg.norm(good, axis=1, keepdims=True) * 25.0
    poor = rng.normal(0, 1, (8, 512)).astype(np.float32)
    poor = poor / np.linalg.norm(poor, axis=1, keepdims=True) * 6.0
    m, n = sf.ada_seat_face(np.vstack([poor, good]))
    check("the clear faces lead the seat's face",
          (round(float(m[0]), 1) >= 0.9, round(float(np.linalg.norm(m)), 3)),
          (True, 1.0))
    old = good / 25.0                      # kept at unit length before 16:00
    m2, _ = sf.ada_seat_face(np.vstack([old, good]))
    check("unit-length samples from before still count",
          round(float(m2[0]), 1) >= 0.9, True)
    check("no samples, no face", sf.ada_seat_face(np.zeros((0, 512))),
          (None, 0))


def check_ada_threads():
    """27 Nov: AdaFace inside the loop must leave PyTorch's thread count
    alone -- it is the whole process's, and the loop's YOLO runs on it."""
    import inspect
    import adaface
    src = open("faces.py", encoding="utf-8").read()
    check("the loop's AdaFace sets OpenVINO's threads, not torch's",
          "AdaFace(ov_threads=" in src and "AdaFace(threads=" not in src,
          True)
    s = inspect.getsource(adaface.AdaFace.__init__)
    check("torch's threads only when torch runs the network",
          s.index("set_num_threads") > s.index("if self.ov is None"), True)


def check_scrfd_pieces():
    """27 Nov: SCRFD (insight_ov.py) finds the seats' faces -- the sitter's
    own face is the one nearest the head crop's middle, aligned by the
    least-squares similarity onto ArcFace's five points; YuNet stays the
    fallback."""
    import faces
    import insight_ov as io
    ang = np.deg2rad(12.0)
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    src = (io.ARCFACE_DST @ R.T) * 1.7 + np.array([40.0, 25.0])
    M = io.umeyama(src, io.ARCFACE_DST)
    back = src @ M[:, :2].T + M[:, 2]
    check("the five points are put back on the template",
          float(np.abs(back - io.ARCFACE_DST).max()) < 1e-3, True)
    pts = np.zeros((5, 2), np.float32)
    found = [(10, 40, 60, 100, 0.95, pts),      # a neighbour, at the side
             (130, 30, 190, 100, 0.70, pts),    # the sitter, in the middle
             (300, 40, 310, 50, 0.99, pts)]     # too small to count
    best = io.sitter_face(found, (200, 320, 3))
    check("the sitter's face is the one in the middle, not the biggest score",
          best[:4], (130, 30, 190, 100))
    check("no face wide enough, no face",
          io.sitter_face(found[2:], (200, 320, 3)), None)
    saved = (faces.scrfd_available, faces.find_strong, faces.feature_aligned,
             faces.ada_feature, faces.ada_available, faces.find)
    try:
        one = np.zeros(128, np.float32)
        one[0] = 1.0
        ada = np.full(512, 2.0, np.float32)
        faces.scrfd_available = lambda: True
        faces.find_strong = lambda frame, box: np.zeros((112, 112, 3),
                                                        np.uint8)
        faces.feature_aligned = lambda f: one
        faces.ada_available = lambda: True
        faces.ada_feature = lambda f: ada
        faces.find = lambda frame, box: None
        got = faces.of_person_both(None, (0, 0, 10, 10))
        check("SCRFD's face gives both readings", (got[0] is one,
                                                   got[1] is ada),
              (True, True))
        faces.find_strong = lambda frame, box: None
        check("no SCRFD face and no YuNet face: no reading",
              faces.of_person_both(None, (0, 0, 10, 10)), None)
    finally:
        (faces.scrfd_available, faces.find_strong, faces.feature_aligned,
         faces.ada_feature, faces.ada_available, faces.find) = saved


def check_ada_sightings():
    """27 Nov night: away from their desks, one AdaFace look names a person
    only when it is clearly theirs (0.45, by 0.10); a pass's sighting is
    written as the SFace galleries' are."""
    import shutil
    import tempfile
    from datetime import datetime as _dt
    import cctv_faces as cf
    import faces
    import progress_track as pt
    ids = np.array(["00010", "00011"])
    R = np.zeros((2, 512), np.float32)
    R[0, 0] = R[1, 1] = 1.0
    near0 = np.zeros(512, np.float32)
    near0[0], near0[2] = 0.8, 0.6                  # 0.8 to 00010, 0 to 00011
    both = np.zeros(512, np.float32)
    both[0] = both[1] = 1.0                        # 0.71 to each
    check("a clear AdaFace look is named; one between two is not",
          (cf.ada_best(near0 * 9.0, ids, R)[0],
           cf.ada_best(both, ids, R), cf.ada_best(None, ids, R)),
          ("00010", None, None))
    saved = (cf.ada_refs, cf.load, faces.of_person_both, faces.available,
             dict(cf._ada_clock), dict(cf._seen))
    folder = tempfile.mkdtemp()
    try:
        cf.ada_refs = lambda path=None: (ids, R)
        cf.load = lambda path=None: (np.array([]), np.zeros((0, 128)))
        faces.available = lambda: True
        faces.of_person_both = lambda frame, box: (
            np.ones(128, np.float32) / np.sqrt(128), near0)
        cf._ada_clock.update(minute=0, spent=0.0)
        cf._seen.clear()
        frame = np.zeros((1080, 1920, 3), np.uint8)
        noon = _dt(2026, 11, 26, 13, 0, tzinfo=pt.PKT)
        n = cf.observe("140-H Cafe", ("nvr1", 3), frame,
                       [(100, 100, 200, 400, 0.9)], now=noon, spots=[],
                       out=folder)
        rows = open(os.path.join(folder, "2026-11-26.csv")).read()
        check("a cafe sighting by AdaFace is written", (n, "00010" in rows),
              (1, True))
        check("never the 141 gym", cf.observe(
            "141 Gym", ("cd_nvr2", 7), frame, [(100, 100, 200, 400, 0.9)],
            now=noon, spots=[], out=folder), 0)
    finally:
        (cf.ada_refs, cf.load, faces.of_person_both, faces.available) = \
            saved[:4]
        cf._ada_clock.clear()
        cf._ada_clock.update(saved[4])
        cf._seen.clear()
        cf._seen.update(saved[5])
        shutil.rmtree(folder)


def main():
    check_safetensors()
    check_ada_budget()
    check_ada_seat_face()
    check_ada_threads()
    check_scrfd_pieces()
    check_ada_sightings()
    check_backfill()
    check_replay_plan()
    check_crop_paths()
    check_machines()
    check_nightly()
    check_hook()
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
