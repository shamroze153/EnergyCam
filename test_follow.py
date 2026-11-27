"""Check the gate-to-seat follow (follow_gate.py): the clocks, the moments
and their candidate desks, who counts as standing by a seat, the votes, and
one login try per recorder. Synthetic numbers only -- no picture, no name.

    python test_follow.py
"""
import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

import follow_gate as fg

FAILURES = []
DAY = "2026-11-20"


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def at(hhmmss):
    return pd.Timestamp("%s %s" % (DAY, hhmmss))


def check_clocks():
    print("-- the clocks")
    check("a live day's gate time is the laptop's already",
          fg.gate_to_laptop(at("13:00:00"), fg.LAPTOP), at("13:00:00"))
    check("a day read from nvr1's recording: moved to the laptop's",
          fg.gate_to_laptop(at("13:00:00"), fg.REC),
          at("13:00:00") + pd.Timedelta(seconds=fg.LAPTOP - fg.REC))
    check("no offset known (today): as it is",
          fg.gate_to_laptop(at("13:00:00"), None), at("13:00:00"))
    check("the laptop's time asked of a recorder",
          fg.laptop_to_recorder(at("13:03:01")), at("13:00:00"))
    w = [(at("12:00:00"), at("12:04:00")), (at("15:00:00"), at("15:04:00"))]
    got = fg.to_laptop(w, [(at("14:55:00"), at("15:05:00"))])
    check("a window from the recording's seat notes is moved, the loop's "
          "not", got, [w[0], (w[1][0] + pd.Timedelta(seconds=181),
                              w[1][1] + pd.Timedelta(seconds=181))])


def check_gate_and_events():
    print("-- the gate's clothes and the moments")
    base = tempfile.mkdtemp()
    try:
        pics = os.path.join(base, DAY)
        os.makedirs(pics)
        for f in ("130000_ch05_00010_body.jpg", "130000_ch05_00010.jpg",
                  "131500-2_ch05_00010_body.jpg",
                  "140000_ch05_unknown.jpg"):
            open(os.path.join(pics, f), "w").close()
        tp = fg.templates(DAY, base)
        check("each named passer's body pictures, by their code",
              {k: len(v) for k, v in tp.items()}, {"10": 2})
        with open(os.path.join(base, DAY + ".csv"), "w") as fh:
            fh.write("time,recorder,channel,status,employee_id,best,score,"
                     "margin,face_w\n"
                     "13:00:00,nvr1,5,named,00010,00010,0.6,0.2,60\n"
                     "13:00:30,nvr1,5,named,00010,00010,0.6,0.2,60\n"
                     "18:00:00,nvr1,5,named,00010,00010,0.6,0.2,60\n"
                     "18:30:00,nvr1,5,named,00020,00020,0.6,0.2,60\n")
        data = pd.DataFrame({
            "eid": ["10", "10"], "kind": ["in", "out"],
            "at": [at("09:00:00"), at("12:57:00")],
            "place": ["140-H IN", "140-H OUT"]})
        ev = fg.events(DAY, ["10"], data, base)
        check("the punches (laptop clock) and the gate's exits no punch "
              "says already, one per passage",
              [(e["kind"], e["source"], e["t"].strftime("%H:%M:%S"))
               for e in ev],
              [("in", "punch", "09:02:43"), ("out", "punch", "12:59:43"),
               ("out", "gate", "18:00:00")])
    finally:
        shutil.rmtree(base)


def notes(times, x=500, y=600, h=200):
    return pd.DataFrame([{"time": t, "room": "R", "recorder": "dvr2",
                          "channel": 9, "cx": x, "cy": y, "w": 90, "h": h,
                          "score": 0.8, "frame_w": 1920, "frame_h": 1080,
                          "at": at(t)} for t in times])


def check_changes():
    print("-- a desk's comings and goings, and the moments' candidates")
    ends = pd.date_range(at("12:05:00"), at("13:00:00"), freq="5min")
    passes = pd.DataFrame({"start": ends - pd.Timedelta(minutes=5),
                           "end": ends, "camera": None})
    desk = {"code": "A", "recorder": "dvr2", "channel": 9,
            "seat": [500, 700]}
    seen = ["12:11:00", "12:16:00", "12:21:00", "12:26:00", "12:41:00",
            "12:46:00", "12:51:00"]
    ch = fg.changes(desk, notes(seen), passes)
    check("left after the last note at the desk, before the pass that "
          "found it empty ended",
          [(a.strftime("%H:%M:%S"), b.strftime("%H:%M:%S"))
           for a, b in ch["out"]],
          [("12:26:00", "12:31:00"), ("12:51:00", "12:56:00")])
    check("sat down after the empty pass began, by the first note (five "
          "minutes at most)",
          [(a.strftime("%H:%M:%S"), b.strftime("%H:%M:%S"))
           for a, b in ch["in"]],
          [("12:06:00", "12:11:00"), ("12:36:00", "12:41:00")])
    out_ev = {"eid": "10", "kind": "out", "t": at("12:32:00")}
    in_ev = {"eid": "10", "kind": "in", "t": at("12:33:00")}
    far = {"eid": "10", "kind": "out", "t": at("12:50:00")}
    c = {"A": ch}
    check("an exit 6 min after the desk emptied: a candidate",
          [x[0] for x in fg.candidates(out_ev, c)], ["A"])
    check("an arrival 8 min before the desk filled: a candidate",
          [x[0] for x in fg.candidates(in_ev, c)], ["A"])
    check("an exit 24 min after: not", fg.candidates(far, c), [])
    m = fg.moments(at("12:26:00"), at("12:27:00"), step=15, pad=15)
    check("a frame every STEP s over the window and its pad",
          [t.strftime("%H:%M:%S") for t in m],
          ["12:25:45", "12:26:00", "12:26:15", "12:26:30", "12:26:45",
           "12:27:00", "12:27:15"])


def check_matching():
    print("-- standing by the seat, and the votes")
    seat = (1000, 800)
    boxes = [(950, 400, 1050, 790, 0.9),     # standing at the seat
             (950, 650, 1080, 800, 0.9),     # sitting (wide)
             (300, 400, 400, 790, 0.9)]      # standing, far away
    check("only the standing person by the seat",
          fg.standing_near(boxes, seat, 1920), [boxes[0]])
    check("the gate's body picture covers the top of a standing box",
          fg.top_part((0, 100, 50, 300)), (0.0, 100.0, 50.0, 270.0))
    check("best desk and its margin",
          tuple(round(v, 2) if isinstance(v, float) else v
                for v in fg.best_of({"A": 0.7, "B": 0.5})), ("A", 0.7, 0.2))
    rows = [
        {"event": "e1", "eid": "10", "code": "A", "score": "0.72",
         "standing": "3"},
        {"event": "e1", "eid": "10", "code": "B", "score": "0.50",
         "standing": "2"},
        {"event": "e2", "eid": "10", "code": "A", "score": "0.66",
         "standing": "1"},
        {"event": "e2", "eid": "10", "code": "B", "score": "0.64",
         "standing": "1"},
        {"event": "e3", "eid": "10", "code": "B", "score": "0.80",
         "standing": "0"}]
    check("a moment votes only when clear of its other desks; nobody seen "
          "standing is no vote", fg.votes(rows, 0.6, 0.1), {("10", "A"): 1})
    any_rows = [dict(r, score_any=r["score"]) for r in rows]
    fit = {"10": {"A": (5.0,), "B": (3.0,)}}
    check("with the punches beside them: only a moment whose pictures and "
          "punches pick the same desk, of two desks or more",
          fg.votes(any_rows, 0.6, 0.1, field="score_any", fit=fit),
          {("10", "A"): 1})
    fit_b = {"10": {"A": (3.0,), "B": (5.0,)}}
    check("... the punches picking the other desk: no vote",
          fg.votes(any_rows, 0.6, 0.1, field="score_any", fit=fit_b), {})


class FakeCap:
    opened = []
    refuse = set()

    def __init__(self, url, *a):
        self.url = url
        FakeCap.opened.append(url)

    def isOpened(self):
        return not any(h in self.url for h in FakeCap.refuse)

    def read(self):
        return True, np.zeros((10, 10, 3), np.uint8)

    def release(self):
        pass


def check_one_login():
    print("-- one login try a recorder")
    import cv2
    real = cv2.VideoCapture
    try:
        cv2.VideoCapture = FakeCap
        FakeCap.refuse = {"10.0.0.2"}
        g = fg.Grabber({"nvr1": {"host": "10.0.0.1"},
                        "dvr2": {"host": "10.0.0.2", "brand": "dahua"}},
                       {"nvr1": ("u", "p"), "dvr2": ("u", "p")}, streams=2)
        t = at("13:00:00")
        a = [g.grab("dvr2", 9, t) for _ in range(3)]
        b = g.grab("nvr1", 5, t)
        tries = sum("10.0.0.2" in u for u in FakeCap.opened)
        check("a refused recorder is tried once, never again; another "
              "still read", (tries, a.count(None), b is not None,
                             sorted(g.refused)), (1, 3, True, ["dvr2"]))
        check("at most three streams", fg.Grabber({}, {}, 9).every._value,
              3)
    finally:
        cv2.VideoCapture = real


def check_review():
    print("-- the review: the way, the close-up, the answer (dry by default)")
    b = {"places": {p: {} for p in ("Desk Room", "Lobby X", "Reception X",
                                    "Attendance Machine H",
                                    "140-H After Entrance", "Entry H",
                                    "Parking X")},
         "links": [["Desk Room", "Lobby X"], ["Lobby X", "Reception X"],
                   ["Reception X", "Attendance Machine H"],
                   ["Attendance Machine H", "140-H After Entrance"],
                   ["140-H After Entrance", "Entry H"],
                   ["Desk Room", "Parking X"], ["Parking X", "Entry H"]]}
    cams = {("nvr1", 3): "Lobby X", ("nvr1", 4): "Reception X",
            ("nvr1", 9): "Parking X", ("nvr1", 14): "140-H After Entrance"}
    check("the way in through the building, nearest the gate first -- not "
          "out through the parking",
          fg.way_cameras("Desk Room", b, cams),
          [("nvr1", 14, "140-H After Entrance"), ("nvr1", 4, "Reception X"),
           ("nvr1", 3, "Lobby X")])
    import cv2
    base = tempfile.mkdtemp()
    try:
        img = np.full((400, 600, 3), 90, np.uint8)
        cv2.rectangle(img, (280, 100), (320, 260), (0, 255, 255), 3)
        p = os.path.join(base, "shot.jpg")
        cv2.imwrite(p, img)
        cu = fg.close_up(p)
        check("the close-up is cut round the boxed person",
              (cu.shape[0] < 400, cu.shape[1] < 600), (True, True))
        rows = os.path.join(base, "rows.json")
        with open(rows, "w") as fh:
            fh.write('[{"code": "zz.1-1", "eid": "999991"}, '
                     '{"code": "zz.1-2", "eid": "999992"}, '
                     '{"code": "zz.1-3", "eid": "999993"}]')
        got = fg.apply_answer(rows, wrong={2}, later={3})
        check("a dry run says what it would do", [x[2] for x in got],
              ["named", "refused", "pending"])
    finally:
        shutil.rmtree(base)


def main():
    check_clocks()
    check_gate_and_events()
    check_changes()
    check_matching()
    check_one_login()
    check_review()
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
