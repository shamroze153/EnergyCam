"""From the gate to the seat: whose desk is it, by the clothes they wear.

Shamroze, 26 Nov 2026: "gate wale camera se unko follow karo, dekho kahan
baith rahe hain. Picture gate se hi lo ... phir seat tak follow karo aur
save karo." The gate (Entry H, entrance_watch) names a passer by the face
on the way out and keeps their clothes (<stem>_body.jpg, shoulders to
knees, standing). The same day, the same clothes: somebody who left the
building rose from a desk a few minutes before; somebody who punched IN
sat down at one a few minutes after. So for each such moment:

  1. the candidate desks: those whose sitter left (an OUT) or arrived (an
     IN) in the minutes before / after, by the seat notes (desk_match's
     windows);
  2. the recorders' recording of each candidate desk's camera over that
     change (playback, read only, one login try, a few streams at most,
     140-H only, never a room in its private hours), a frame every STEP s;
  3. every person STANDING by that seat -- rising or sitting down -- as
     whole-body numbers (OSNet, reid.py), against the person's own gate
     body pictures of that day. Standing against standing: clothes from
     above against the gate's front view failed (clothes_match, 25 Nov).

The desk that matches best, clear of the others, gets a vote; votes over
moments and days name a desk only at a bar measured on the desks already
known (measure()); the rest go to ONE numbered review PDF with the
pictures: the gate's face and body, the person standing at the desk, the
directory photo.

    python follow_gate.py plan    [days...]        how much work, no playback
    python follow_gate.py run     [days...] --who known|free [--streams 2]
    python follow_gate.py measure                  the bar, on known desks
    python follow_gate.py propose                  votes -> proposals.json

Everything it writes is under people/follow/ (git-ignored, this laptop
only): scores.csv (a row a desk and moment), the best standing picture of
each, proposals.json. Times: the loop's seat notes and live gate days are
the laptop's clock (LAPTOP s ahead of the machines), the recordings the
recorders' (REC s off the machines; measured on nvr1's playback).
"""
import csv
import os
import sys
import threading
import time
from datetime import timedelta

import numpy as np
import pandas as pd

OUT = os.path.join("people", "follow")
ENTRANCE = os.path.join("people", "entrance")
CAMPUS = ("nvr1", "nvr4", "dvr2", "xvr3")
LAPTOP = 163.0           # s the laptop's clock ran ahead of the machines
REC = -18.0              # s the recorders' clocks ran off the machines
# 26 Nov: a frame of a recording takes 3-4 s to fetch -- every 15 s with
# 45 s either side made 26 frames and ~100 s a desk change on one stream
STEP = 20                # s between frames read over a desk's change
MAX_WINDOW = 5 * 60      # s of a change read at most
PAD = 30                 # s either side of a change's window
SURE = 0.80              # a match this close ends a desk's reading early
LEAVE = (0.5, 15.0)      # min from leaving a desk to the gate / OUT punch
ARRIVE = (-1.0, 15.0)    # min from the IN punch to sitting down
# a box this tall for its width: standing (26 Nov, the first frames read: a
# sitter seen from the side, upright, makes a box 1.6-1.7 times as tall as
# wide; somebody standing 2.5-3.5)
STANDING = 2.0
CROP_TOP = 0.85          # the gate keeps shoulders to knees: the top of a box
STREAMS = 3              # playback sessions open at once, at most
COLUMNS = ["event", "day", "eid", "kind", "t", "code", "score", "frames",
           "standing", "best_t", "picture", "score_any", "at"]


# ---------------------------------------------------------------- the times
def gate_to_laptop(t, gate_offset):
    """A gate time on the laptop's clock: a live day's already is (its
    offset against the machines is the laptop's, about LAPTOP); a day read
    from nvr1's recording is on the recorder's (about REC)."""
    if gate_offset is None:
        return t
    return t + pd.Timedelta(seconds=LAPTOP - float(gate_offset))


def laptop_to_recorder(t):
    return t - pd.Timedelta(seconds=LAPTOP - REC)


# ---------------------------------------------------------------- the gate
def templates(day, folder=ENTRANCE):
    """{employee code (no leading zeros): [body picture paths]} -- the
    gate's clothes of each named passer that day (<..>_<id>_body.jpg)."""
    import attendance
    pics = os.path.join(folder, day)
    out = {}
    if not os.path.isdir(pics):
        return out
    for f in sorted(os.listdir(pics)):
        if not f.endswith("_body.jpg"):
            continue
        eid = f[:-len("_body.jpg")].split("_")[-1]
        if eid and eid != "unknown":
            out.setdefault(attendance.code(eid), []).append(
                os.path.join(pics, f))
    return out


def events(day, eids, data=None, folder=ENTRANCE):
    """[{eid, kind ("out" | "in"), t (laptop clock), source}] for the people
    `eids` on `day`: their 140-H punches (HR's export) and, where the
    export has none near, their named passages at the gate (an exit)."""
    import attendance
    data = attendance.load() if data is None else data
    eids = {attendance.code(e) for e in eids}
    out = []
    if data is not None and len(data):
        mine = data[data["place"].str.startswith(attendance.CAMPUS)
                    & (data["at"].dt.strftime("%Y-%m-%d") == day)
                    & data["eid"].isin(eids)]
        for r in mine.sort_values("at").itertuples(index=False):
            t = r.at + pd.Timedelta(seconds=LAPTOP)
            if any(e["eid"] == r.eid and e["kind"] == r.kind and
                   (t - e["t"]).total_seconds() <= 120 for e in out):
                continue                 # the machine read twice: one punch
            out.append({"eid": r.eid, "kind": r.kind, "t": t,
                        "source": "punch"})
    path = os.path.join(folder, day + ".csv")
    if os.path.exists(path):
        g = pd.read_csv(path, dtype=str).fillna("")
        g = g[(g["status"] == "named")]
        off = attendance.clock_offset(day, folder, data=data) \
            if data is not None and len(data) else None
        last = {}
        for eid, t in zip(g["employee_id"].map(attendance.code), g["time"]):
            if eid not in eids:
                continue
            tl = gate_to_laptop(pd.Timestamp("%s %s" % (day, t)), off)
            if eid in last and tl - last[eid] < pd.Timedelta(minutes=5):
                continue                         # one passage, many looks
            last[eid] = tl
            if any(e["eid"] == eid and e["kind"] == "out" and
                   abs((e["t"] - tl).total_seconds()) <= 300 for e in out):
                continue                         # the punch says it already
            out.append({"eid": eid, "kind": "out", "t": tl,
                        "source": "gate"})
    return sorted(out, key=lambda e: (e["t"], e["eid"]))


# ---------------------------------------------------------------- the desks
def changes(desk, day_notes, day_passes):
    """A desk's comings and goings that day with the window each happened
    in (laptop clock): {"out": [(a, b)], "in": [(a, b)]} -- a leaving
    between the last note at the desk and the end of the pass that found it
    empty; a sitting down between the start of the pass that found it empty
    and the first note at the desk."""
    import progress_data as pdx
    line = pdx.timeline(desk, day_notes, day_passes)
    seen = pdx.at_desk(desk, day_notes) if day_notes is not None and \
        len(day_notes) else []
    out = {"out": [], "in": []}
    for k in range(len(line) - 1):
        s0, e0, st0 = line[k]
        s1, e1, st1 = line[k + 1]
        if s1 - e0 > pdx.JOINED:
            continue                     # a hole: nothing known between
        if st0 == "desk" and st1 != "desk":
            last = [t for t in seen if s0 <= t <= e0]
            a = max(last) if last else s0
            out["out"].append((a, min(e1, a + pd.Timedelta(
                seconds=MAX_WINDOW))))
        elif st0 != "desk" and st1 == "desk":
            first = [t for t in seen if s1 <= t <= e1]
            b = min(first) if first else e1
            out["in"].append((max(s0, b - pd.Timedelta(seconds=MAX_WINDOW)),
                              b))
    return out


def candidates(event, desk_changes):
    """[(desk code, (a, b))]: the desks whose change fits the moment -- a
    leaving LEAVE minutes before an exit, a sitting down ARRIVE minutes
    after an arrival."""
    t = event["t"]
    out = []
    for code, ch in desk_changes.items():
        for a, b in ch.get(event["kind"], []):
            if event["kind"] == "out":
                lead = (t - a).total_seconds() / 60.0
                ok = LEAVE[0] <= lead <= LEAVE[1]
            else:
                lead = (b - t).total_seconds() / 60.0
                ok = ARRIVE[0] <= lead <= ARRIVE[1]
            if ok:
                out.append((code, (a, b)))
                break
    return out


def moments(a, b, step=STEP, pad=PAD):
    """The times to read over a change (laptop clock), every `step` s."""
    t, stop = a - pd.Timedelta(seconds=pad), b + pd.Timedelta(seconds=pad)
    out = []
    while t <= stop:
        out.append(t)
        t += pd.Timedelta(seconds=step)
    return out


# ---------------------------------------------------------------- the match
def standing_near(boxes, seat, width, ratio=STANDING):
    """The people standing by a seat: a box as tall as `ratio` times its
    width whose feet are within reach of the seat (a share of the frame,
    or of the box's own height)."""
    sx, sy = (float(v) for v in seat)
    out = []
    for b in boxes:
        x1, y1, x2, y2 = (float(v) for v in b[:4])
        w, h = x2 - x1, y2 - y1
        if w <= 0 or h < ratio * w:
            continue
        reach = max(0.06 * width, 0.7 * h)
        if ((x1 + x2) / 2.0 - sx) ** 2 + (y2 - sy) ** 2 <= reach ** 2:
            out.append(b)
    return out


def top_part(box, share=CROP_TOP):
    """The part of a standing box the gate's body picture covers."""
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    return (x1, y1, x2, y1 + share * (y2 - y1))


def best_of(scores):
    """(best code, its score, the margin to the next) of {code: score}."""
    r = sorted(scores.items(), key=lambda kv: -kv[1])
    if not r:
        return None, 0.0, 0.0
    return r[0][0], r[0][1], r[0][1] - (r[1][1] if len(r) > 1 else 0.0)


def votes(rows, same, margin, min_frames=1, field="score", fit=None):
    """{(eid, code): votes}: a moment votes for the desk whose standing
    person matched the gate's clothes best, `same` or more and `margin`
    clear of the moment's other desks (field "score_any": anybody by the
    seat, sitting too). With `fit` ({eid: {code: (z, ...)}}, the punch
    timing), only a moment of two desks or more whose pictures and punches
    pick the same desk votes -- measured 26 Nov on the known people's
    moments: pictures alone 20 of 35 right, punches alone 31, both
    agreeing 18 of 19."""
    out = {}
    by_event = {}
    for r in rows:
        if field == "score" and int(r.get("standing") or 0) < min_frames:
            continue
        by_event.setdefault(r["event"], {})[r["code"]] = float(
            r.get(field) or 0)
    eid_of = {r["event"]: r["eid"] for r in rows}
    for ev, sc in by_event.items():
        code, s, m = best_of(sc)
        if code is None or s < same or m < margin:
            continue
        if fit is not None:
            mine = fit.get(eid_of[ev], {})
            if len(sc) < 2 or max(sc, key=lambda c: mine.get(
                    c, (-99.0,))[0]) != code:
                continue
        k = (eid_of[ev], code)
        out[k] = out.get(k, 0) + 1
    return out


def load_scores(path=None):
    """The rows of one scores file, or of every people/follow/scores*.csv."""
    import glob
    paths = [path] if path else sorted(glob.glob(os.path.join(
        OUT, "scores*.csv")))
    out = []
    for p in paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                out += list(csv.DictReader(fh))
    return out


def append_score(row, path=None):
    path = path or os.path.join(OUT, "scores.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(COLUMNS)
        w.writerow([row.get(c, "") for c in COLUMNS])


def event_id(day, ev):
    return "%s|%s|%s|%s" % (day, ev["eid"], ev["kind"],
                            ev["t"].strftime("%H%M%S"))


# ------------------------------------------------------- the recordings
class Grabber:
    """One frame of a camera's recording at a moment. One login try per
    recorder: its first session opens alone, a refusal leaves it alone for
    good; `streams` sessions at most over all the recorders."""

    def __init__(self, recorders, logins, streams=2):
        self.recorders, self.logins = recorders, logins
        self.every = threading.Semaphore(max(1, min(STREAMS, streams)))
        self.lock = threading.Lock()
        self.first = {r: threading.Lock() for r in recorders}
        self.opened, self.refused = set(), set()

    def grab(self, rec, ch, when):
        import cv2

        import replay_day
        import room_loop as rl
        if rec in self.refused or rec not in self.logins:
            return None
        user, password = self.logins[rec]
        gate = self.first[rec] if rec not in self.opened else None
        if gate is not None:
            gate.acquire()
        try:
            if rec in self.refused:
                return None
            with self.every:
                cap = cv2.VideoCapture(replay_day.playback_url(
                    self.recorders[rec], ch, when.to_pydatetime(), user,
                    password), cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    with self.lock:
                        self.refused.add(rec)
                    cap.release()
                    return None
                with self.lock:
                    self.opened.add(rec)
                frame, t0 = None, time.time()
                while time.time() - t0 < 10:
                    ok, f = cap.read()
                    if ok and f is not None:
                        frame = f
                        break
                cap.release()
        finally:
            if gate is not None:
                gate.release()
        return rl.widen(frame) if frame is not None else None


def score_change(tvecs, desk, a, b, grab, detect, embed, keep=None):
    """The best match by a desk over one change: (score standing, frames
    read, standing people seen, (time, frame, box) of the best, score of
    anybody by the seat, sitting too)."""
    best, best_any, n_frames, n_standing = 0.0, 0.0, 0, 0
    shot = shot_any = None
    for t in moments(a, b):
        frame = grab(desk["recorder"], int(desk["channel"]),
                     laptop_to_recorder(t))
        if frame is None:
            continue
        n_frames += 1
        near = standing_near(detect(frame), desk["seat"], frame.shape[1],
                             ratio=0.0)
        if not near:
            continue
        v = embed(frame, [top_part(x) for x in near])
        s = (v @ tvecs.T).max(axis=1) if len(tvecs) else np.zeros(len(v))
        for i, b_ in enumerate(near):
            up = (b_[3] - b_[1]) >= STANDING * (b_[2] - b_[0])
            n_standing += up
            if up and float(s[i]) > best:
                best, shot = float(s[i]), (t, frame, b_)
            if float(s[i]) > best_any:
                best_any, shot_any = float(s[i]), (t, frame, b_)
        if best >= SURE:
            break
    return best, n_frames, n_standing, shot or shot_any, best_any


def to_laptop(windows, replayed):
    """Windows found in the recordings' seat notes (replay_day: the
    recorder's clock) moved to the laptop's, like the loop's own."""
    shift = pd.Timedelta(seconds=LAPTOP - REC)
    out = []
    for a, b in windows:
        if any(s <= b <= e for s, e in replayed):
            a, b = a + shift, b + shift
        out.append((a, b))
    return out


def save_shot(shot, path):
    """The desk camera's frame at the best moment, the person boxed --
    local only (people/follow/)."""
    import cv2
    t, frame, box = shot
    img = frame.copy()
    x1, y1, x2, y2 = (int(v) for v in box[:4])
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 3)
    h, w = img.shape[:2]
    k = 960.0 / w
    img = cv2.resize(img, (960, int(h * k)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return path


# ---------------------------------------------------------------- the plan
ZMIN, HITS_MIN = 2.0, 2   # a desk the person's punches fit at least this


def timing(desks, refresh=False, path=None):
    """{eid: {desk code: (z, hits, punches)}} -- desk_match's punch timing
    over every day of the export, kept in people/follow/timing.pkl (a few
    minutes to work out; made again with refresh)."""
    import pickle

    import attendance
    import desk_match as dm
    import desks_data
    path = path or os.path.join(OUT, "timing.pkl")
    if os.path.exists(path) and not refresh:
        with open(path, "rb") as fh:
            return pickle.load(fh)
    roster = {attendance.code(r["employee_id"]) for r in
              desks_data.load_roster()}
    pu = dm.punches()
    pu = pu[pu["eid"].isin(roster)]
    days = dm.days_with_punches(pu)
    z = dm.scores(pu, {day: dm.lines(list(desks.values()), day)
                       for day in days})
    z = {e: dict(v) for e, v in z.items()}
    os.makedirs(OUT, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(z, fh)
    return z


def plan(days, who="all", data=None, zmin=ZMIN, hits_min=HITS_MIN):
    """[(day, event, [(code, (a, b))])] -- every moment with its candidate
    desks, for the people with gate clothes that day. who: "known" (their
    desk is named: for measuring), "free" (no desk yet: the candidates
    only free desks) or "all"."""
    import attendance
    import desk_match as dm
    import desks_data
    import progress_data as pdx
    cfg = pdx.load() or {}
    desks = {d["code"]: d for d in dm.desks_to_score(cfg)}
    names = desks_data.load_desk_names()
    known = {c: attendance.code(e) for c, (e, _) in names.items()}
    for d in desks.values():
        if d.get("eid"):
            known[d["code"]] = attendance.code(d["eid"])
    known_people = set(known.values())
    skip = ("janitor", "gate keeper", "security guard", "office boy",
            "driver", "electrician", "plumber", "handyman", "cleaner",
            "guard", "rider")
    trade = {attendance.code(r["employee_id"]) for r in
             desks_data.load_roster() if any(
                 w in (r.get("designation") or "").lower() for w in skip)}
    # only the desks the person's punches already fit (desk_match): the
    # pictures then choose among a few, not among every desk that emptied
    z = timing(desks)
    out = []
    for day in days:
        tp = templates(day)
        people = [e for e in tp if e not in trade and (
            who == "all" or (who == "known") == (e in known_people))]
        if not people:
            continue
        n, p = pdx.notes(day), pdx.passes(day)
        use = desks if who != "free" else {c: d for c, d in desks.items()
                                           if c not in known}
        rp = p[p["camera"].notna()] if len(p) else p
        ch = {}
        for c, d in use.items():
            cam = "%s:%d" % (d["recorder"], int(d["channel"]))
            mine = [(s, e) for s, e, k in zip(rp["start"], rp["end"],
                                              rp["camera"]) if k == cam] \
                if len(rp) else []
            got = changes(d, n, p)
            ch[c] = {k: to_laptop(v, mine) for k, v in got.items()}
        for ev in events(day, people, data):
            fit = z.get(ev["eid"], {})
            cands = [(c, ab) for c, ab in candidates(ev, ch)
                     if c in fit and fit[c][0] >= zmin
                     and fit[c][1] >= hits_min]
            if cands:
                out.append((day, ev, cands))
    return out, desks, known


def run(days, who, streams=2, limit=None, per_person=3, out_scores=None,
        min_cands=1):
    """Read the recordings for each planned moment and score its candidate
    desks; resumable (a desk and moment scored before is not read again).
    min_cands 2: only moments with a choice to make (a lone candidate's
    pictures cannot vote, see votes())."""
    from dotenv import load_dotenv
    load_dotenv()
    import cv2

    import reid
    import room_loop as rl
    from privacy_blur import DETECTOR, people_boxes
    from ultralytics import YOLO
    try:
        import torch
        torch.set_num_threads(2)
    except Exception:                                       # noqa: BLE001
        pass
    todo, desks, known = plan(days, who)
    done = {(r["event"], r["code"]) for r in load_scores(out_scores)}
    # the measure needs the person's own desk among the candidates
    if who == "known":
        mine = {}
        for c, e in known.items():
            mine.setdefault(e, set()).add(c)
        todo = [x for x in todo if mine.get(x[1]["eid"], set())
                & {c for c, _ in x[2]} and len(x[2]) >= 2]
    # fewest candidates first, at most per_person moments a person (those
    # read before count too)
    todo = [x for x in todo if len(x[2]) >= min_cands]
    todo.sort(key=lambda x: (len(x[2]), x[0]))
    count, picked = {}, []
    for ev_id in {r["event"] for r in load_scores(out_scores)}:
        e = ev_id.split("|")[1]
        count[e] = count.get(e, 0) + 1
    for x in todo:
        if all((event_id(x[0], x[1]), c) in done for c, _ in x[2]):
            continue
        e = x[1]["eid"]
        if count.get(e, 0) >= per_person:
            continue
        count[e] = count.get(e, 0) + 1
        picked.append(x)
    if limit:
        picked = picked[:limit]
    print(">> %d moment(s), %d desk changes to read" % (
        len(picked), sum(len(x[2]) for x in picked)), flush=True)
    recorders, rooms = rl.load_rooms("rooms.yaml", list(CAMPUS), None)
    logins = {}
    for rec in CAMPUS:
        if rec in recorders:
            try:
                logins[rec] = rl.recorder_login(rec, recorders[rec])
            except SystemExit:
                pass
    private = {}
    for room in rooms:
        for key in room.cameras:
            private[(key[0], int(key[1]))] = getattr(room, "private", None)
    g = Grabber(recorders, logins, streams)
    model = YOLO(DETECTOR)
    dlock = threading.Lock()

    def detect(frame):
        with dlock:
            return people_boxes(frame, model, conf=0.3, imgsz=1280)

    def embed(frame, boxes):
        with dlock:
            return reid.embed(frame, boxes)

    tcache = {}

    def tvecs(day, eid):
        if (day, eid) not in tcache:
            vs = []
            for p in templates(day).get(eid, []):
                img = cv2.imread(p)
                if img is not None:
                    vs.append(embed(img, [(0, 0, img.shape[1],
                                           img.shape[0])])[0])
            vs = [v for v in vs if np.any(v)]
            tcache[(day, eid)] = np.array(vs, np.float32) if vs \
                else np.zeros((0, 512), np.float32)
        return tcache[(day, eid)]

    from concurrent.futures import ThreadPoolExecutor

    def one(day, ev, code, ab):
        try:
            return _one(day, ev, code, ab)
        except Exception as e:                              # noqa: BLE001
            print(">> %s %s: %s" % (event_id(day, ev), code,
                                    type(e).__name__), flush=True)
            return None

    def _one(day, ev, code, ab):
        d = desks[code]
        if rl.is_private(private.get((d["recorder"], int(d["channel"]))),
                         ev["t"].to_pydatetime().replace(tzinfo=rl.PKT)):
            return None
        tv = tvecs(day, ev["eid"])
        if not len(tv):
            return None
        s, nf, ns, shot, s_any = score_change(tv, d, ab[0], ab[1], g.grab,
                                              detect, embed)
        pic = ""
        if shot is not None:
            pic = save_shot(shot, os.path.join(
                OUT, day, "%s_%s_%s_%s.jpg" % (ev["eid"], ev["kind"],
                                               ev["t"].strftime("%H%M%S"),
                                               code)))
        return {"event": event_id(day, ev), "day": day, "eid": ev["eid"],
                "kind": ev["kind"], "t": ev["t"].strftime("%H:%M:%S"),
                "code": code, "score": "%.3f" % s, "frames": nf,
                "standing": ns,
                "best_t": shot[0].strftime("%H:%M:%S") if shot else "",
                "picture": pic, "score_any": "%.3f" % s_any,
                "at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")}
    jobs = [(day, ev, code, ab) for day, ev, cands in picked
            for code, ab in cands if (event_id(day, ev), code) not in done]
    n = 0
    with ThreadPoolExecutor(max_workers=max(1, min(STREAMS, streams))) as p:
        for r in p.map(lambda j: one(*j), jobs):
            if r is not None:
                append_score(r, out_scores)
                n += 1
                if n % 10 == 0:
                    print(">> %d desk changes read" % n, flush=True)
    print(">> done: %d desk changes read%s" % (
        n, ("; recorders left alone (refused): %s" % sorted(g.refused))
        if g.refused else ""), flush=True)
    return n


def measure(rows=None, known=None, field="score"):
    """On the known people's moments: how often the best desk is their own,
    for a few bars. Returns [(same, margin, named, right)]."""
    import attendance
    rows = load_scores() if rows is None else rows
    if known is None:
        import desk_match as dm
        import desks_data
        import progress_data as pdx
        known = {c: attendance.code(e) for c, (e, _) in
                 desks_data.load_desk_names().items()}
        for d in dm.desks_to_score(pdx.load() or {}):
            if d.get("eid"):
                known[d["code"]] = attendance.code(d["eid"])
    mine = {}
    for c, e in known.items():
        mine.setdefault(e, set()).add(c)
    by_event = {}
    for r in rows:
        if r["eid"] in mine:
            by_event.setdefault(r["event"], (r["eid"], {}))[1][r["code"]] = \
                float(r.get(field) or 0)
    out = []
    for same in (0.0, 0.4, 0.5, 0.55, 0.6, 0.65, 0.7):
        for margin in (0.0, 0.05, 0.1, 0.15):
            named = right = 0
            for ev, (eid, sc) in by_event.items():
                if not (mine[eid] & set(sc)):
                    continue
                code, s, m = best_of(sc)
                if s >= same and m >= margin:
                    named += 1
                    right += code in mine[eid]
            out.append((same, margin, named, right))
    return out, len(by_event)


# --------------------------------------------------- proposals and the PDF
PROPOSALS = os.path.join(OUT, "proposals.json")
# a vote: anybody by the seat (score_any) 0.45+, 0.05 clear, and the punch
# timing's own pick among the moment's desks
VOTE_SAME, VOTE_MARGIN, MIN_VOTES = 0.45, 0.05, 1


def propose(rows=None, same=VOTE_SAME, margin=VOTE_MARGIN,
            min_votes=MIN_VOTES, field="score_any", out=PROPOSALS,
            fit=None):
    """Each free person's desk by the votes of their moments: the desk with
    the most votes (at least `min_votes`, more than any other desk's),
    one person one desk, never a refused pair. Writes proposals.json:
    [{code, eid, votes, against, moments, best score, picture, day, t}]."""
    import json

    import attendance
    import desk_match as dm
    import desks_data
    import progress_data as pdx
    rows = load_scores() if rows is None else rows
    names = desks_data.load_desk_names()
    known = {attendance.code(e) for e, _ in names.values()} | {
        attendance.code(p.get("employee_id")) for p in
        (pdx.load() or {}).get("people") or [] if p.get("employee_id")}
    refused = {(c, attendance.code(e)) for c, e in dm.refused()}
    # a desk he found confusing waits for him: never paired again here
    pending = set()
    pp = os.path.join("people", "desk_names_pending.csv")
    if os.path.exists(pp):
        with open(pp, encoding="utf-8") as fh:
            pending = {r["code"] for r in csv.DictReader(fh)}
    if fit is None:
        import pickle
        tp = os.path.join(OUT, "timing.pkl")
        fit = pickle.load(open(tp, "rb")) if os.path.exists(tp) else {}
    v = votes(rows, same, margin, field=field, fit=fit)
    per = {}
    for (eid, code), n in v.items():
        per.setdefault(eid, []).append((n, code))
    moments_of = {}
    best_row = {}
    for r in rows:
        moments_of.setdefault(r["eid"], set()).add(r["event"])
        k = (r["eid"], r["code"])
        if r.get("picture") and (k not in best_row or float(r[field]) >
                                 float(best_row[k][field])):
            best_row[k] = r
    picks = []
    for eid, lst in per.items():
        if eid in known:
            continue
        lst.sort(reverse=True)
        n, code = lst[0]
        against = sum(x for x, _ in lst[1:])
        if n < min_votes or n <= against or code in names or \
                (code, eid) in refused or code in pending:
            continue
        r = best_row.get((eid, code), {})
        zz = fit.get(eid, {}).get(code, (0.0, 0, 0))
        picks.append({"code": code, "eid": eid, "votes": n,
                      "z": round(float(zz[0]), 1), "hits": int(zz[1]),
                      "punches": int(zz[2]),
                      "against": against,
                      "moments": len(moments_of.get(eid, ())),
                      "score": float(r.get(field) or 0),
                      "picture": r.get("picture", ""),
                      "day": r.get("day", ""), "t": r.get("t", ""),
                      "kind": r.get("kind", ""),
                      "best_t": r.get("best_t", "")})
    picks.sort(key=lambda p: (-p["votes"], -p["score"]))
    used, out_rows = set(), []
    before = {}
    if os.path.exists(out):                 # pictures on the way found before
        with open(out, encoding="utf-8") as fh:
            before = {(p["code"], p["eid"]): p.get("way")
                      for p in json.load(fh) if p.get("way")}
    for p in picks:
        if p["code"] in used:
            continue
        used.add(p["code"])
        if (p["code"], p["eid"]) in before:
            p["way"] = before[(p["code"], p["eid"])]
        out_rows.append(p)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(out_rows, fh, indent=1)
    return out_rows


WAY_BEFORE = (150, 10)   # s before / after the moment at the gate's side
WAY_STEP = 10
WAY_PLACES = 3           # the places nearest the gate on the way


def way_cameras(room, b=None, cams=None, places=WAY_PLACES):
    """[(recorder, channel, place)] on the way from a desk's room to Entry
    H (building.yaml's links), the places nearest the gate first."""
    import building
    b = b or building.load()
    cams = cams if cams is not None else building.cameras(
        recorders=list(CAMPUS))
    # through the building to its door's attendance machine (the fewest
    # steps to the gate itself can run out through the basement parking
    # and the street), then the stretch from the machine to the gate
    route = building.route(b, room, "Attendance Machine H")
    if len(route) < 2:
        return []
    route = route + ["140-H After Entrance", "Entry H"]
    by_place = {}
    for (rec, ch), r in cams.items():
        by_place.setdefault(r, []).append((rec, int(ch)))
    out = []
    for p in reversed(route[1:-1]):
        for rec, ch in sorted(by_place.get(p, [])):
            out.append((rec, ch, p))
        if len({x[2] for x in out}) >= places:
            break
    return out


def ways(rows=None, streams=2, out=PROPOSALS):
    """For each proposal: one or two clear pictures of the person on the
    way between the desk and the gate (the lobby, the stairs, reception),
    found the same way -- standing people in the minutes before they
    reached the gate (after, for a coming in), matched to the gate's
    clothes. Adds "way": [picture paths] to proposals.json."""
    import json

    import cv2
    from dotenv import load_dotenv
    load_dotenv()
    import desks_data
    import reid
    import room_loop as rl
    from privacy_blur import DETECTOR, people_boxes
    from ultralytics import YOLO
    rows = json.load(open(out)) if rows is None else rows
    recorders, rooms = rl.load_rooms("rooms.yaml", list(CAMPUS), None)
    logins = {}
    for rec in CAMPUS:
        if rec in recorders:
            try:
                logins[rec] = rl.recorder_login(rec, recorders[rec])
            except SystemExit:
                pass
    private = {(k[0], int(k[1])): getattr(r, "private", None)
               for r in rooms for k in r.cameras}
    g = Grabber(recorders, logins, streams)
    model = YOLO(DETECTOR)
    df = desks_data.load()
    room = {c: x["room"].iloc[0] for c, x in df.groupby("code")} \
        if len(df) else {}
    for r in rows:
        day, eid = r["day"], r["eid"]
        tv = []
        for p in templates(day).get(eid, []):
            img = cv2.imread(p)
            if img is not None:
                v = reid.embed(img, [(0, 0, img.shape[1], img.shape[0])])[0]
                if np.any(v):
                    tv.append(v)
        if not tv or not r.get("t"):
            continue
        tv = np.array(tv, np.float32)
        t0 = pd.Timestamp("%s %s" % (day, r["t"]))
        span = (-WAY_BEFORE[0], WAY_BEFORE[1]) if r.get("kind") == "out" \
            else (-WAY_BEFORE[1], WAY_BEFORE[0])
        found = []
        for rec, ch, place in way_cameras(room.get(r["code"], "")):
            if rl.is_private(private.get((rec, ch)),
                             t0.to_pydatetime().replace(tzinfo=rl.PKT)):
                continue
            best, shot = 0.0, None
            t = t0 + pd.Timedelta(seconds=span[0])
            while t <= t0 + pd.Timedelta(seconds=span[1]):
                frame = g.grab(rec, ch, laptop_to_recorder(t))
                t += pd.Timedelta(seconds=WAY_STEP)
                if frame is None:
                    continue
                boxes = [x for x in people_boxes(frame, model, conf=0.3,
                                                 imgsz=1280)
                         if (x[3] - x[1]) >= 1.8 * (x[2] - x[0])
                         and (x[3] - x[1]) >= 120]
                if not boxes:
                    continue
                v = reid.embed(frame, [top_part(x) for x in boxes])
                s = (v @ tv.T).max(axis=1)
                i = int(np.argmax(s))
                if float(s[i]) > best:
                    best, shot = float(s[i]), (t, frame, boxes[i])
            if shot is not None and best >= 0.5:
                found.append((best, save_shot(shot, os.path.join(
                    OUT, day, "%s_way_%s_%s%d.jpg" % (
                        eid, r["t"].replace(":", ""), rec, ch)))))
            if len(found) >= 2:
                break
        r["way"] = [p for _, p in sorted(found, reverse=True)]
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    return rows


def gate_pictures(day, eid, near=None, folder=ENTRANCE):
    """(face picture, body picture) of the person's named passage that day
    whose body was kept -- the one nearest `near` ("HH:MM:SS"), else the
    first."""
    import attendance
    pics = os.path.join(folder, day)
    if not os.path.isdir(pics):
        return None, None

    def secs(hhmmss):
        try:
            return int(hhmmss[:2]) * 3600 + int(hhmmss[2:4]) * 60 + \
                int(hhmmss[4:6])
        except ValueError:
            return 0
    best = None
    for f in sorted(os.listdir(pics)):
        if f.endswith("_body.jpg") and attendance.code(
                f[:-len("_body.jpg")].split("_")[-1]) == eid:
            d = abs(secs(f[:6]) - secs(near.replace(":", ""))) if near \
                else 0
            if best is None or d < best[0]:
                best = (d, f)
    if best is None:
        return None, None
    f = best[1]
    face = os.path.join(pics, f[:-len("_body.jpg")] + ".jpg")
    return (face if os.path.exists(face) else None, os.path.join(pics, f))


def close_up(path, size=300):
    """The boxed person from a saved desk frame, cut out larger than the
    box so the desk shows: (image) or None."""
    import cv2
    img = cv2.imread(path) if path and os.path.exists(path) else None
    if img is None:
        return None
    # the yellow box drawn by save_shot: the largest yellow outline (26 Nov:
    # all yellow pixels together also took in yellow things in the room)
    m = cv2.inRange(img, (0, 200, 200), (80, 255, 255))
    found = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = found[0] if len(found) == 2 else found[1]
    rects = [cv2.boundingRect(c) for c in cnts]
    rects = [r for r in rects if r[2] >= 12 and r[3] >= 12]
    if not rects:
        return img
    x, y, w, h = max(rects, key=lambda r: r[2] * r[3])
    x1, x2, y1, y2 = x, x + w, y, y + h
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    half = int(max(x2 - x1, y2 - y1) * 0.9) + 20
    h, w = img.shape[:2]
    return img[max(0, cy - half):min(h, cy + half),
               max(0, cx - half):min(w, cx + half)]


def pdf(rows=None, out=None, title=None):
    """ONE numbered review PDF of the proposals (local, people/follow/):
    a row a desk -- who, the evidence in words, the gate's face and body,
    the person at the desk in those clothes (close and whole frame), the
    directory photo. Reply with the numbers that are WRONG."""
    import glob
    import json

    import cv2
    from PIL import Image

    import attendance
    import desks_data
    rows = json.load(open(PROPOSALS)) if rows is None else rows
    out = out or os.path.join(OUT, "Desks_follow_review.pdf")
    title = title or "Desks by the gate's clothes (follow) -- %s" % \
        pd.Timestamp.now().strftime("%d %b %H:%M")
    roster = {attendance.code(r["employee_id"]): r
              for r in desks_data.load_roster()}
    df = desks_data.load()
    room = {c: g["room"].iloc[0] for c, g in df.groupby("code")} \
        if len(df) else {}
    W, ROW, PER = 1600, 330, 5
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    def fit(img, h, maxw=None):
        k = h / float(img.shape[0])
        img = cv2.resize(img, (max(1, int(img.shape[1] * k)), h))
        return img[:, :maxw] if maxw else img

    canvas_rows = []
    for n, r in enumerate(rows, 1):
        rr = roster.get(r["eid"], {})
        c = np.full((ROW, W, 3), 255, np.uint8)
        cv2.rectangle(c, (0, 0), (W - 1, ROW - 1), (210, 210, 210), 1)
        cv2.putText(c, str(n), (16, 60), FONT, 1.6, (40, 90, 200), 3,
                    cv2.LINE_AA)
        lines = [(rr.get("name", "?"), 0.75, (0, 0, 0), 2),
                 ("ID %s" % rr.get("employee_id", r["eid"]), 0.6,
                  (60, 60, 60), 1),
                 (rr.get("designation", ""), 0.55, (60, 60, 60), 1),
                 ("%s / %s" % (rr.get("department", ""),
                               rr.get("project", "")), 0.5, (60, 60, 60), 1),
                 ("%s - desk %s" % (room.get(r["code"], ""), r["code"]),
                  0.55, (0, 0, 0), 1),
                 ("same clothes at this desk: %d time(s)%s" % (
                     r["votes"], (", elsewhere %d" % r["against"])
                     if r["against"] else ""), 0.45, (90, 90, 90), 1),
                 ("came/left by the desk: %d of %d punches" % (
                     r.get("hits", 0), r.get("punches", 0)), 0.45,
                  (90, 90, 90), 1),
                 ("%s %s %s" % (r["day"][5:], "left" if r["kind"] == "out"
                                else "came", r["t"][:5]), 0.45,
                  (90, 90, 90), 1)]
        y = 92
        for text, size, col, th in lines:
            cv2.putText(c, str(text)[:44], (16, y), FONT, size, col, th,
                        cv2.LINE_AA)
            y += 29
        x = 440
        tiles = []
        face, body = gate_pictures(r["day"], r["eid"], r.get("t"))
        for p, label in ((face, "gate face"), (body, "gate clothes")):
            img = cv2.imread(p) if p else None
            if img is not None:
                tiles.append((fit(img, 220, 200), label))
        cu = close_up(r.get("picture"))
        if cu is not None:
            tiles.append((fit(cu, 280, 300), "at the desk %s" %
                          r.get("best_t", "")[:5]))
        for wp in (r.get("way") or [])[:1]:
            wc = close_up(wp)
            if wc is not None:
                tiles.append((fit(wc, 280, 260), "on the way"))
        full = cv2.imread(r["picture"]) if r.get("picture") and \
            os.path.exists(r["picture"]) else None
        if full is not None:
            tiles.append((fit(full, 280, 500), "the desk's camera"))
        ph = next(iter(glob.glob(os.path.join(
            "people", "photos", rr.get("employee_id", "-") + ".*"))), None)
        img = cv2.imread(ph) if ph else None
        if img is not None:
            tiles.append((fit(img, 220, 180), "directory photo"))
        for img, label in tiles:
            if x + img.shape[1] > W - 8:
                break
            c[10:10 + img.shape[0], x:x + img.shape[1]] = img
            cv2.putText(c, label, (x, ROW - 10), FONT, 0.5, (60, 60, 60), 1,
                        cv2.LINE_AA)
            x += img.shape[1] + 10
        canvas_rows.append(c)
    if not canvas_rows:
        return None
    head = np.full((90, W, 3), 255, np.uint8)
    cv2.putText(head, title, (16, 40), FONT, 0.9, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(head, "Reply with the numbers that are WRONG; the rest are "
                "named.", (16, 75), FONT, 0.6, (60, 60, 60), 1, cv2.LINE_AA)
    pages = []
    for i in range(0, len(canvas_rows), PER):
        page = np.vstack(([head] if i == 0 else []) + canvas_rows[i:i + PER])
        pages.append(Image.fromarray(cv2.cvtColor(page, cv2.COLOR_BGR2RGB)))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pages[0].save(out, save_all=True, append_images=pages[1:],
                  resolution=110)
    stem = os.path.splitext(out)[0]
    for i, pg in enumerate(pages, 1):
        pg.save("%s_page%d.jpg" % (stem, i), quality=85)
    with open(stem + ".json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    return out


def apply_answer(pdf_json, wrong=(), later=(), said="", write=False):
    """Shamroze's answer to a follow PDF: the numbers he calls wrong are
    refused pairs, the ones he cannot tell pending, every other row named.
    Writes only with write=True (a dry run prints what it would do)."""
    import json
    from datetime import datetime

    import attendance
    import desks_data
    rows = json.load(open(pdf_json, encoding="utf-8"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    who = "%s Shamroze, follow PDF%s: " % (now[:10], (" (%s)" % said)
                                          if said else "")
    roster = {attendance.code(r["employee_id"]): r
              for r in desks_data.load_roster()}
    names = desks_data.load_desk_names()
    taken = {attendance.code(e) for e, _ in names.values()}
    done = []

    def put(path, header, row):
        if not write:
            return
        new = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(header)
            w.writerow(row)
    for n, r in enumerate(rows, 1):
        rr = roster.get(r["eid"], {})
        eid = rr.get("employee_id", r["eid"])
        if n in wrong:
            put(os.path.join("people", "desk_names_rejected.csv"),
                ["code", "employee_id", "why", "at"],
                [r["code"], eid, who + "wrong", now])
            done.append((n, r["code"], "refused"))
        elif n in later:
            put(os.path.join("people", "desk_names_pending.csv"),
                ["code", "employee_id", "why", "at"],
                [r["code"], eid, who + "not sure", now])
            done.append((n, r["code"], "pending"))
        elif r["code"] in names or attendance.code(eid) in taken:
            done.append((n, r["code"], "skipped: already named"))
        else:
            if write:
                desks_data.save_desk_name(r["code"], eid, rr.get("name", ""))
            taken.add(attendance.code(eid))
            done.append((n, r["code"], "named"))
    return done


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("what", choices=["plan", "run", "measure", "propose",
                                     "ways", "pdf", "apply"])
    ap.add_argument("--same", type=float, default=VOTE_SAME)
    ap.add_argument("--margin", type=float, default=VOTE_MARGIN)
    ap.add_argument("--votes", type=int, default=MIN_VOTES)
    ap.add_argument("--field", default="score_any", choices=["score",
                                                             "score_any"])
    ap.add_argument("--pdf-json", default=os.path.join(
        OUT, "Desks_follow_review.json"), help="apply: the PDF's rows")
    ap.add_argument("--wrong", default="", help="apply: numbers he called "
                    "wrong")
    ap.add_argument("--later", default="", help="apply: numbers he could "
                    "not tell")
    ap.add_argument("--said", default="", help="apply: his words")
    ap.add_argument("--apply", action="store_true",
                    help="apply: write (without it, a dry run)")
    ap.add_argument("days", nargs="*")
    ap.add_argument("--who", default="known", choices=["known", "free",
                                                       "all"])
    ap.add_argument("--streams", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--per-person", type=int, default=3)
    ap.add_argument("--min-cands", type=int, default=1)
    ap.add_argument("--out", default=None,
                    help="the scores file (default people/follow/scores.csv)")
    args = ap.parse_args(argv[1:])
    days = args.days or ["2026-11-17", "2026-11-18", "2026-11-19",
                         "2026-11-20", "2026-11-25"]
    if args.what == "plan":
        todo, desks, known = plan(days, args.who)
        n = [len(c) for _, _, c in todo]
        print("moments %d (people %d), candidate desks per moment: mean %.1f"
              ", 1: %d, 2-3: %d, 4+: %d" % (
                  len(todo), len({e["eid"] for _, e, _ in todo}),
                  float(np.mean(n)) if n else 0, sum(x == 1 for x in n),
                  sum(2 <= x <= 3 for x in n), sum(x >= 4 for x in n)))
    elif args.what == "run":
        run(days, args.who, args.streams, args.limit, args.per_person,
            args.out, args.min_cands)
    elif args.what == "propose":
        got = propose(same=args.same, margin=args.margin,
                      min_votes=args.votes, field=args.field)
        print("proposed %d desk(s) -> %s" % (len(got), PROPOSALS))
        for p in got:
            print("  %-11s votes %d against %d moments %d best %.2f" % (
                p["code"], p["votes"], p["against"], p["moments"],
                p["score"]))
    elif args.what == "ways":
        got = ways(streams=args.streams)
        print("pictures on the way for %d of %d" % (
            sum(1 for r in got if r.get("way")), len(got)))
    elif args.what == "pdf":
        print(pdf() or "nothing to send")
    elif args.what == "apply":
        def nums(v):
            return {int(x) for x in v.replace(" ", "").split(",") if x}
        if not args.apply:
            print("DRY RUN -- nothing is written (add --apply to write)")
        for n, code, what in apply_answer(args.pdf_json, nums(args.wrong),
                                          nums(args.later), args.said,
                                          args.apply):
            print("  %2d %-11s %s" % (n, code, what))
    else:
        for field in ("score", "score_any"):
            res, n = measure(field=field)
            print("known people's moments scored: %d (%s)" % (
                n, "standing" if field == "score" else "anybody by the seat"))
            for same, margin, named, right in res:
                if named:
                    print("  best >= %.2f, clear by %.2f: named %3d, right "
                          "%3d (%.0f%%)" % (same, margin, named, right,
                                            100.0 * right / named))


if __name__ == "__main__":
    main(sys.argv)
