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

Like every name here, "by gate" is to be confirmed by a person.
"""
import csv
import os
import sys

import pandas as pd

import desks_data
import progress_data as pdx

OUT = os.path.join("people", "desks_by_gate.csv")
ENTRANCE = os.path.join("people", "entrance")
LEAD_MIN = 0.0           # min from leaving the desk to the gate, at least
LEAD_MAX = 14.0          # and at most (stairs, a pass's 4.5 min blur)
SUPPORT = 2.0
CLEAR = 2.0


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


def main(argv):
    import staff_faces
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
