"""Whose desk is it, by the same day's clothes.

Shamroze, 24 Nov 2026: "gate se pata chal jaye koi enter ho raha hai ...
us hisaab se bhi productivity nikal sakte ho". The offices' cameras look
down on the desks and see no face to name; the gate (entrance_watch) names
people by their face, on the way out, and from 24 Nov keeps their clothes
too (<time>_ch.._<id>_body.jpg). Every desk keeps its sitter's look a few
times an hour (desk_watch.keep_look). On one day a person wears one set of
clothes: a desk whose sitter looks like one named passer -- and that
passer like no other desk -- is likely theirs.

OSNet (reid.py) sees a person standing at the gate straight on and the
same person seated from above, so the numbers are not a face's: before
anything is suggested, evaluate() scores the rule on the desks whose
sitter is known (named by hand, progress.yaml). Nothing here is sent to
anybody until that says it is right.

    python clothes_match.py [days...]   -> the check on known desks, and
                                           people/clothes_suggestions.csv

Numbers and pictures stay on this laptop (people/, progress/).
"""
import csv
import glob
import os
import sys
from datetime import datetime

import numpy as np

GATE = os.path.join("people", "entrance")
LOOKS = os.path.join("progress", "desk_looks")       # desk_watch.LOOKS
OUT = os.path.join("people", "clothes_suggestions.csv")
SAME = 0.65              # cosine of the day's means, at least ...
MARGIN = 0.05            # ... and this clear of the next person
MIN_LOOKS = 3            # a desk's looks in the day, at least
_vec = {}


def unit(v):
    v = np.asarray(v, np.float32)
    return v / max(float(np.linalg.norm(v)), 1e-6)


def gate_looks(day, folder=GATE, embed=None):
    """{employee_id: (n, 512)} -- the gate's pictures of named passers'
    clothes on the day, as OSNet sees them."""
    if embed is None:
        import cv2
        import reid

        def embed(path):
            img = cv2.imread(path)
            if img is None:
                return None
            return reid.embed(img, [(0, 0, img.shape[1], img.shape[0])])[0]
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, day, "*_body.jpg"))):
        eid = os.path.basename(path)[:-len("_body.jpg")].split("_")[-1]
        if path not in _vec:
            _vec[path] = embed(path)
        v = _vec[path]
        if v is None or not np.any(v):
            continue
        out.setdefault(eid, []).append(unit(v))
    return {e: np.array(v) for e, v in out.items()}


def desk_looks(day, base=LOOKS):
    """{desk code: (n, 512)} -- the desk's sitter's looks on the day."""
    out = {}
    for path in glob.glob(os.path.join(base, day, "*.f16")):
        v = np.fromfile(path, np.float16).astype(np.float32)
        v = v[:len(v) // 512 * 512].reshape(-1, 512)
        if len(v):
            out[os.path.basename(path)[:-4]] = v
    return out


def day_pairs(desks, gate, same=SAME, margin=MARGIN, min_looks=MIN_LOOKS):
    """{desk code: (employee_id, score, clear)} for one day: each desk's
    mean look against each passer's mean, where the desk's best passer
    has that desk as their own best too, `same` or more and `margin`
    clear of the desk's next passer."""
    codes = [c for c in sorted(desks) if len(desks[c]) >= min_looks]
    ids = sorted(gate)
    if not codes or not ids:
        return {}
    D = np.array([unit(np.mean([unit(v) for v in desks[c]], axis=0))
                  for c in codes])
    G = np.array([unit(np.mean(gate[e], axis=0)) for e in ids])
    S = D @ G.T
    out = {}
    for i, c in enumerate(codes):
        order = np.argsort(-S[i])
        j = int(order[0])
        nxt = float(S[i, order[1]]) if len(order) > 1 else -1.0
        if S[i, j] < same or S[i, j] - nxt < margin:
            continue
        if int(np.argmax(S[:, j])) != i:
            continue
        out[c] = (ids[j], float(S[i, j]), float(S[i, j] - nxt))
    return out


def combine(per_day):
    """[(code, employee_id, days agreeing, days against)] over the days:
    a desk's passer who won it most often, and how often another did."""
    tally = {}
    for pairs in per_day:
        for code, (eid, _, _) in pairs.items():
            tally.setdefault(code, {}).setdefault(eid, 0)
            tally[code][eid] += 1
    out = []
    for code, by in sorted(tally.items()):
        best = max(by.items(), key=lambda kv: kv[1])
        out.append((code, best[0], best[1], sum(by.values()) - best[1]))
    return out


def evaluate(pairs, truth):
    """(right, wrong) among the desks whose sitter is known."""
    right = sum(1 for c, (e, _, _) in pairs.items() if truth.get(c) == e)
    wrong = sum(1 for c, (e, _, _) in pairs.items()
                if c in truth and truth[c] != e)
    return right, wrong


def known_desks():
    """{desk code: employee_id} whose sitter is certain: named by hand,
    and progress.yaml's people at their desk's place."""
    import json
    import desks_data
    import progress_data as pdx
    truth = {c: e for c, (e, _) in desks_data.load_desk_names().items()}
    try:
        with open(desks_data.CODES, encoding="utf-8") as fh:
            reg = json.load(fh).get("desks") or {}
    except (OSError, ValueError):
        reg = {}
    for p in (pdx.load() or {}).get("people") or []:
        if not p.get("employee_id") or not p.get("seat"):
            continue
        cam = "%s.%d" % (p["recorder"], int(p["channel"]))
        sx, sy = (float(v) for v in p["seat"])
        for n, x, y in reg.get(cam) or []:
            if (x - sx) ** 2 + (y - sy) ** 2 <= 60 ** 2:
                truth["%s-%d" % (cam, n)] = str(p["employee_id"])
    return truth


def run(days, out=OUT):
    truth = known_desks()
    per_day, lines = [], []
    for day in days:
        pairs = day_pairs(desk_looks(day), gate_looks(day))
        per_day.append(pairs)
        r, w = evaluate(pairs, truth)
        lines.append("%s: %d desk(s) paired; on the known desks %d right, "
                     "%d wrong" % (day, len(pairs), r, w))
    rows = combine(per_day)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "employee_id", "days", "against", "known"])
        for code, eid, n, against in rows:
            w.writerow([code, eid, n, against, truth.get(code, "")])
    return lines, rows


def main(argv):
    days = argv[1:] or [datetime.now().strftime("%Y-%m-%d")]
    lines, rows = run(days)
    for line in lines:
        print(line)
    print("desks with a passer:", len(rows), "->", OUT)


if __name__ == "__main__":
    main(sys.argv)
