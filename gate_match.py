"""Whose desk is it: the turnstile's named faces against the desks that
emptied just before.

Shamroze, 24 Nov 2026: "kaun aaya, kaun gaya -- phir wahan se follow
karo." Entry H names a passer on the way out (entrance_watch.py, and the
recording of days gone by, entrance_backfill.py). Somebody who leaves the
building left a desk a few minutes earlier: for every named passage, each
desk whose stretch at the desk ended LEAD_MIN-LEAD_MAX minutes before is a
candidate, sharing one vote. Over lunches and evenings and days, a
person's own desk keeps getting the votes; the others scatter. A desk is
given to a person only with SUPPORT votes or more and twice the next
desk's -- and one person, one desk.

    python gate_match.py [days...]   -> people/desks_by_gate.csv (local)
    python gate_match.py --machines [days...]
                                     -> people/gate_machines/<day>.csv and
                                        people/gate_gallery.npz (local)

Like every name here, "by gate" is to be confirmed by a person.

The gate's faces read again with the machines beside them (26 Nov, the
face study of 25 Nov, people/session_handoff/face_agent/REPORT.md, recs 1
and 2), at night, for the days HR's export covers -- never live:

  exit    the face of somebody whose own OUT punch is within EXIT_S of the
          gate's time (its clock set right first: attendance.clock_offset),
          their photo EXIT_SAME or more and among the EXIT_TOP best of all,
          MARGIN clear of the others punching out then. A random employee
          punches out that near 0.6% of the time: on the study's 915 truth
          faces this was right 586 times and wrong once. These faces become
          the person's gate gallery -- their face as OUR camera sees it.
  inside  "gate+machines": the best photo among only the people inside by
          the machines then (+-INSIDE_PAD), INSIDE_SAME by INSIDE_MARGIN
          (+48% punches named in the study, none contradicted by
          construction; somebody else named 0.7% of the time when the right
          person is not a candidate -- a visitor, a tailgater). Kept apart
          from the live names.
"""
import csv
import os
import sys

import numpy as np
import pandas as pd

import desks_data
import progress_data as pdx

OUT = os.path.join("people", "desks_by_gate.csv")
ENTRANCE = os.path.join("people", "entrance")
LEAD_MIN = 0.0           # min from leaving the desk to the gate, at least
LEAD_MAX = 14.0          # and at most (stairs, a pass's 4.5 min blur)
SUPPORT = 2.0
CLEAR = 2.0
# the machines beside the gate (not in people/entrance/: its *.csv are days)
MACHINES = os.path.join("people", "gate_machines")
GALLERY = os.path.join("people", "gate_gallery.npz")
EXIT_S = 45.0
EXIT_SAME, EXIT_TOP = 0.40, 5
INSIDE_SAME, INSIDE_MARGIN = 0.45, 0.10
MARGIN = 0.10
INSIDE_PAD = 120.0
DRIFT_S = 30.0           # an hour whose clock strays this far: no exits
KEEP = 40                # gallery faces a person (the best scored)


def passages(day, folder=ENTRANCE):
    """The day's named passages at the gate: [(time, employee_id)]."""
    path = os.path.join(folder, day + ".csv")
    if not os.path.exists(path):
        return []
    d = pd.read_csv(path, dtype=str)
    d = d[d["status"] == "named"]
    return [(pd.Timestamp("%s %s" % (day, r["time"])), r["employee_id"])
            for _, r in d.iterrows()]


def desk_ends(desks, day, n, p):
    """{desk code: [times a stretch at the desk ended]} for the day."""
    out = {}
    for d in desks:
        person = {"code": d["code"], "recorder": d["recorder"],
                  "channel": d["channel"], "seat": d["seat"]}
        line = pdx.timeline(person, n, p)
        ends = []
        for i, (s, e, state) in enumerate(line):
            nxt = line[i + 1][2] if i + 1 < len(line) else "away"
            if state == "desk" and nxt != "desk":
                ends.append(e)
        out[d["code"]] = ends
    return out


def votes(days, desks, entrance=ENTRANCE, notes_of=None, passes_of=None):
    """{employee_id: {desk code: votes}} over the days."""
    notes_of = notes_of or pdx.notes
    passes_of = passes_of or pdx.passes
    out = {}
    for day in days:
        seen = passages(day, entrance)
        if not seen:
            continue
        ends = desk_ends(desks, day, notes_of(day), passes_of(day))
        for t, eid in seen:
            cand = [c for c, es in ends.items() for e in es
                    if pd.Timedelta(minutes=LEAD_MIN) <= t - e
                    <= pd.Timedelta(minutes=LEAD_MAX)]
            cand = sorted(set(cand))
            for c in cand:
                out.setdefault(eid, {})
                out[eid][c] = out[eid].get(c, 0.0) + 1.0 / len(cand)
    return out


def assign(v, support=SUPPORT, clear=CLEAR):
    """One desk a person and one person a desk, strongest first:
    [(employee_id, desk code, votes, next desk's votes)]."""
    ranked = []
    for eid, ds in v.items():
        best = sorted(ds.items(), key=lambda kv: -kv[1])
        top = best[0]
        nxt = best[1][1] if len(best) > 1 else 0.0
        if top[1] >= support and top[1] >= clear * nxt:
            ranked.append((top[1], eid, top[0], nxt))
    out, taken = [], set()
    for votes_, eid, code, nxt in sorted(ranked, reverse=True):
        if code in taken:
            continue
        taken.add(code)
        out.append((eid, code, round(votes_, 2), round(nxt, 2)))
    return out


def crop_paths(day, d, folder=ENTRANCE):
    """Each row's face picture: <stem>.jpg; or, on a day kept before the
    stem column, <HHMMSS>_ch.._<label>.jpg -- two rows the same second with
    the same label shared that name and the later wrote over the earlier,
    so only the last such row owns it ("" for the others)."""
    pics = os.path.join(folder, day)
    if "stem" in d.columns:
        return [os.path.join(pics, s + ".jpg") if s else ""
                for s in d["stem"].fillna("")]
    label = d["employee_id"].fillna("").replace("", "unknown")
    names = (d["time"].str.replace(":", "", regex=False) + "_ch"
             + d["channel"].astype(int).map("{:02d}".format) + "_" + label
             + ".jpg")
    last = ~names.duplicated(keep="last")
    return [os.path.join(pics, n) if k else "" for n, k in zip(names, last)]


def _nets():
    import cv2
    import faces
    return (cv2.FaceDetectorYN.create(faces.DETECTOR, "", (320, 320), 0.6,
                                      0.3, 20),
            cv2.FaceRecognizerSF.create(faces.RECOGNIZER, ""))


def embed_crop(img, det, rec, up=2.0):
    """The face of a small gate picture (160 px wide), read again: the
    picture enlarged for the detector, the face nearest its middle. A unit
    vector (128,) or None."""
    import cv2
    if img is None or not getattr(img, "size", 0):
        return None
    big = cv2.resize(img, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    det.setInputSize((big.shape[1], big.shape[0]))
    _, rows = det.detect(big)
    if rows is None or not len(rows):
        return None
    H, W = big.shape[:2]

    def key(r):
        fx, fy = r[0] + r[2] / 2.0, r[1] + r[3] / 2.0
        return r[-1] - ((fx - W / 2.0) ** 2 + (fy - H / 2.0) ** 2) ** 0.5 \
            / max(W, H)
    r = max(rows, key=key)
    v = rec.feature(rec.alignCrop(big, r)).astype(np.float32).ravel()
    return v / max(float(np.linalg.norm(v)), 1e-6)


def day_faces(day, folder=ENTRANCE, cache=MACHINES, nets=None):
    """The day's gate rows that have a face: (rows, X (n, 128)). A row's
    face is its live numbers (<stem>.f16, entrance_watch.live_face) or, on
    a day kept before them, its picture read again -- weaker by ~0.065 for
    the right person (the study), so the bars here are on that scale --
    remembered in <cache>/<day>_faces.npz so a night reads each once."""
    path = os.path.join(folder, day + ".csv")
    if not os.path.exists(path):
        return pd.DataFrame(), np.zeros((0, 128), np.float32)
    import entrance_watch
    d = pd.read_csv(path, dtype=str).fillna("")
    d["crop"] = crop_paths(day, d, folder)
    known = {}
    cpath = os.path.join(cache, day + "_faces.npz") if cache else None
    if cpath and os.path.exists(cpath):
        z = np.load(cpath, allow_pickle=False)
        known = {str(k): v for k, v in zip(z["keys"], z["vecs"])}
    det = rec = None
    added, vecs, keep, live = 0, [], [], []
    for i, r in enumerate(d.itertuples(index=False)):
        v = None
        stem = getattr(r, "stem", "")
        if stem:
            got = entrance_watch.live_face(day, stem, folder)
            if got is not None:
                v = got[0]
        is_live = v is not None
        if v is None and r.crop:
            k = os.path.basename(r.crop)
            if k in known:
                v = known[k] if np.any(known[k]) else None
            elif os.path.exists(r.crop):
                import cv2
                if det is None:
                    det, rec = (nets or _nets)()
                v = embed_crop(cv2.imread(r.crop), det, rec)
                known[k] = v if v is not None else np.zeros(128, np.float32)
                added += 1
        if v is not None:
            vecs.append(np.asarray(v, np.float32))
            keep.append(i)
            live.append(is_live)
    if cpath and added:
        os.makedirs(cache, exist_ok=True)
        np.savez(cpath, keys=np.array(list(known)),
                 vecs=np.array(list(known.values()), np.float32))
    rows = d.iloc[keep].reset_index(drop=True)
    rows["live"] = live
    rows["t"] = pd.to_datetime(day + " " + rows["time"], errors="coerce")
    return rows, (np.vstack(vecs) if vecs else np.zeros((0, 128),
                                                         np.float32))


# Each turnstile camera and the campus whose machines stand at it (27 Nov:
# 141's turnstile, cd_nvr2 ch 6, beside 140-H's Entry H)
GATES = {"nvr1": "140-H", "cd_nvr2": "141"}


def gate_campus(recorder):
    return GATES.get(str(recorder or ""), "140-H")


def clock(day, rows, data, near=600.0, least=5, campus=None):
    """(offset s, {hour: False}) -- the gate's clock against the machines'
    (as attendance.clock_offset: the median of the named passages' times
    from their own nearest OUT punch, within `near`), and the hours whose
    own median strays more than DRIFT_S from it (23 Nov's evening playback
    drifted by minutes): no exit is read in those. None when unknown."""
    import attendance
    campus = campus or attendance.CAMPUS
    named = rows[(rows["status"] == "named") & (rows["employee_id"] != "")]
    outs = data[(data["kind"] == "out")
                & data["place"].str.startswith(campus)
                & (data["at"].dt.strftime("%Y-%m-%d") == day)]
    by = {e: pd.DatetimeIndex(g["at"]) for e, g in outs.groupby("eid")}
    diffs = []
    for eid, t in zip(named["employee_id"], named["t"]):
        p = by.get(attendance.code(eid))
        if p is None or pd.isna(t):
            continue
        dd = (t - p).total_seconds()
        k = abs(dd).argmin()
        if abs(dd[k]) <= near:
            diffs.append((t.hour, float(dd[k])))
    if len(diffs) < least:
        return None, {}
    off = float(np.median([x for _, x in diffs]))
    bad, few = {}, []
    for h in range(24):
        mine = [x for hh, x in diffs if hh == h]
        if len(mine) < 3:
            few.append(h)
        elif abs(float(np.median(mine)) - off) > DRIFT_S:
            bad[h] = False
    if bad:
        # a clock that strayed in one hour may in the next: on such a day
        # only the hours shown to be right are read
        bad.update({h: False for h in few})
    return off, bad


def _decide(S, allowed, same, margin):
    """Per row: (column named or -1, top, second) among the allowed."""
    T = np.where(allowed, S, -2.0)
    o = np.argsort(-T, axis=1)[:, :2] if T.shape[1] > 1 else \
        np.zeros((len(T), 2), int)
    top = np.take_along_axis(T, o[:, :1], 1)[:, 0]
    sec = np.take_along_axis(T, o[:, 1:2], 1)[:, 0] if T.shape[1] > 1 \
        else np.full(len(T), -2.0)
    sec = np.where(sec <= -2.0, -1.0, sec)
    ok = (top >= same) & (top - sec >= margin)
    return np.where(ok, o[:, 0], -1), top, sec


def machine_names(day, rows, X, ids, V, data, campus=None):
    """Each gate row read with the machines (rec 2's exits, rec 1's
    inside-gating): a DataFrame of the rows named -- time, rule ("exit" /
    "inside"), employee_id (the photo's), score, margin, plus the row's
    own columns. An exit wins over an inside name. `campus`: the machines
    at that gate (gate_campus), 140-H's by default."""
    import attendance
    campus = campus or attendance.CAMPUS
    cols = ["day", "time", "rule", "employee_id", "score", "margin",
            "status", "live_id", "face_w", "crop", "stem", "live"]
    if not len(rows) or not len(ids) or data is None or not len(data):
        return pd.DataFrame(columns=cols)
    off, bad = clock(day, rows, data, campus=campus)
    mine = data[data["place"].str.startswith(campus)
                & (data["at"].dt.strftime("%Y-%m-%d") == day)]
    if not len(mine):
        return pd.DataFrame(columns=cols)
    end = data["at"].max()
    codes = np.array([attendance.code(i) for i in ids])
    S = X @ np.asarray(V, np.float32).T
    tm = (rows["t"] - pd.Timedelta(seconds=off or 0.0)).values.astype(
        "datetime64[s]").astype(np.int64)
    ok_clock = np.array([off is not None and bad.get(h, True)
                         for h in rows["t"].dt.hour])
    # after the export's last punch nobody is known to be inside
    in_export = tm <= np.datetime64(end, "s").astype(np.int64)
    inside = np.zeros(S.shape, bool)
    exits = np.zeros(S.shape, bool)
    col = {}
    for j, c in enumerate(codes):
        col.setdefault(c, []).append(j)
    for eid, g in mine.groupby("eid"):
        if eid not in col:
            continue
        m = np.zeros(len(rows), bool)
        e = np.zeros(len(rows), bool)
        for a, b in attendance.inside(eid, day, campus, data=mine):
            a = np.datetime64(a, "s").astype(np.int64)
            b = np.datetime64(b, "s").astype(np.int64)
            m |= (tm >= a - INSIDE_PAD) & (tm <= b + INSIDE_PAD)
        for x in g.loc[g["kind"] == "out", "at"]:
            e |= np.abs(tm - np.datetime64(x, "s").astype(np.int64)) <= EXIT_S
        for j in col[eid]:
            inside[:, j] = m
            exits[:, j] = e & ok_clock
    inside &= in_export[:, None]
    rank = np.argsort(np.argsort(-S, axis=1), axis=1)
    pe, te, se = _decide(S, exits & (rank < EXIT_TOP), EXIT_SAME, MARGIN)
    pi, ti, si = _decide(S, inside, INSIDE_SAME, INSIDE_MARGIN)
    out = []
    for i in range(len(rows)):
        if pe[i] >= 0:
            rule, j, s, m = "exit", pe[i], te[i], te[i] - se[i]
        elif pi[i] >= 0:
            rule, j, s, m = "inside", pi[i], ti[i], ti[i] - si[i]
        else:
            continue
        r = rows.iloc[i]
        out.append([day, r["time"], rule, str(ids[j]), round(float(s), 3),
                    round(float(m), 3), r["status"], r["employee_id"],
                    r.get("face_w", ""), os.path.basename(r["crop"]),
                    r.get("stem", ""), bool(r["live"])])
    return pd.DataFrame(out, columns=cols)


def load_machine_names(days=None, folder=MACHINES, rules=("exit", "inside")):
    """The rows nightly_faces() named, over the days (default: all kept)."""
    if not os.path.isdir(folder):
        return pd.DataFrame()
    days = days or sorted(f[:-4] for f in os.listdir(folder)
                          if f.endswith(".csv"))
    parts = []
    for day in days:
        p = os.path.join(folder, day + ".csv")
        if os.path.exists(p):
            parts.append(pd.read_csv(p, dtype=str).fillna(""))
    if not parts:
        return pd.DataFrame()
    d = pd.concat(parts, ignore_index=True)
    return d[d["rule"].isin(rules)].reset_index(drop=True)


def load_gallery(path=GALLERY):
    """(ids, vecs) of the gate gallery: each person's faces at their own
    OUT punches, as the gate camera saw them."""
    if not os.path.exists(path):
        return np.array([]), np.zeros((0, 128), np.float32)
    z = np.load(path, allow_pickle=False)
    return z["ids"], z["vecs"]


def nightly_faces(days=None, folder=ENTRANCE, out=MACHINES,
                  gallery=GALLERY, data=None, photos=None, nets=None):
    """The gate's days that HR's export covers read with the machines:
    people/gate_machines/<day>.csv (the rows named, by rule) and the gate
    gallery (every person's exit faces, KEEP best). Returns a summary."""
    import attendance
    data = attendance.load() if data is None else data
    if data is None or not len(data):
        return "gate faces: no punches"
    covered = set(attendance.days(data=data))
    have = sorted(f[:-4] for f in os.listdir(folder) if f.endswith(".csv")
                  and len(f) == 14) if os.path.isdir(folder) else []
    days = [d for d in (days or have) if d in covered and d in have]
    if not days:
        return "gate faces: 0 day(s) the export covers -- gallery kept"
    if photos is None:
        import staff_faces
        photos = staff_faces.load_faces()
    ids, V = photos
    os.makedirs(out, exist_ok=True)
    n_exit = n_in = 0
    for day in days:
        rows, X = day_faces(day, folder, out, nets)
        # each turnstile with its own campus's machines (27 Nov: 141's too)
        parts = []
        gate_of = (rows["recorder"].map(gate_campus) if "recorder" in rows
                   else pd.Series(["140-H"] * len(rows)))
        for campus in sorted(set(gate_of)):
            m = (gate_of == campus).values
            parts.append(machine_names(
                day, rows[m].reset_index(drop=True), X[m], ids, V, data,
                campus))
        named = pd.concat(parts, ignore_index=True) if parts else \
            machine_names(day, rows, X, ids, V, data)
        named.to_csv(os.path.join(out, day + ".csv"), index=False)
        n_exit += int((named["rule"] == "exit").sum())
        n_in += int((named["rule"] == "inside").sum())
    # the gallery from every day read so far (not only tonight's): each
    # person's faces at their own OUT punches
    gal = {}
    for day in sorted(f[:-4] for f in os.listdir(out) if f.endswith(".csv")
                      and len(f) == 14):
        if day not in covered or day not in have:
            continue
        m = pd.read_csv(os.path.join(out, day + ".csv"), dtype=str
                        ).fillna("")
        m = m[m["rule"] == "exit"]
        if not len(m):
            continue
        rows, X = day_faces(day, folder, out, nets)
        idx = {t: i for i, t in enumerate(rows["time"] + "|"
                                          + rows["crop"].map(os.path.basename))}
        for r in m.itertuples(index=False):
            i = idx.get(r.time + "|" + r.crop)
            if i is not None:
                gal.setdefault(r.employee_id, []).append((float(r.score),
                                                          X[i]))
    gids, gvecs = [], []
    for eid, got in sorted(gal.items()):
        for s, v in sorted(got, key=lambda x: -x[0])[:KEEP]:
            gids.append(eid)
            gvecs.append(v)
    np.savez(gallery, ids=np.array(gids),
             vecs=np.array(gvecs, np.float32) if gvecs
             else np.zeros((0, 128), np.float32))
    return ("gate faces: %d day(s), %d exit face(s) of %d people (gallery), "
            "%d named gate+machines" % (len(days), n_exit, len(gal), n_in))


def main(argv):
    import staff_faces
    if len(argv) > 1 and argv[1] == "--machines":
        print(nightly_faces(argv[2:] or None))
        return
    days = argv[1:] or sorted(f[:-4] for f in os.listdir(ENTRANCE)
                              if f.endswith(".csv"))
    df = desks_data.load()
    desks = [{"code": c, "recorder": g["recorder"].iloc[0],
              "channel": int(g["channel"].iloc[0]),
              "seat": [float(g["x"].iloc[0]), float(g["y"].iloc[0])]}
             for c, g in df.groupby("code")] if len(df) else []
    got = assign(votes(days, desks))
    names = {r["employee_id"]: r for r in staff_faces.load_roster()}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "employee_id", "name", "designation", "votes",
                    "next"])
        for eid, code, v_, nxt in got:
            r = names.get(eid, {})
            w.writerow([code, eid, r.get("name", ""),
                        r.get("designation", ""), v_, nxt])
    print("desks named by the gate:", len(got), "->", OUT)


if __name__ == "__main__":
    main(sys.argv)
