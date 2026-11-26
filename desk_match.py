"""Whose desk is it -- from the attendance machines, and checked by them.

Shamroze, 25 Nov 2026: name every employee's desk from the footage, check
it yourself, all day and all night, "mujhse poochne ki zaroorat nahi".

Two things, both from HR's machine log (attendance.py) and the seat notes:

  pair    A desk filled a few minutes after somebody's IN punch and emptied
          a few minutes before their OUT punch, day after day, far above
          what chance gives a desk that busy: z = (hits - n p) / sqrt(n p
          (1 - p)), p the share of ALL punches the desk's comings and goings
          match. One person, one desk, the strongest first. On the desks
          already known by face (25 Nov): 7 of 9 right at the loose line,
          every one right at the strong line below.

  check   A named desk is used while its person is inside the building by
          the machines: the share of its occupied minutes that fall inside
          the person's IN-to-OUT windows. A desk somebody else uses, or a
          wrong name, shows up as desk time while the person was out.

nightly() does both every night (the loop starts it after 23:30): checks
every named desk, takes back the names the machines alone gave whose check
fails, and names the strong new pairs whose check passes. Names are the
roster's; everything it writes is under people/ (this laptop only).

Two pairs it never makes (25 Nov, round 2's review): one refused once --
a "no" on a review PDF (people/desk_names_rejected.csv) or a name the
check took back -- and a desk whose best person over everybody already
has a desk. That desk is a second view of theirs (one desk seen by two
cameras, or one seat found twice), or the seat of somebody who comes and
goes with them; giving it to the next person was wrong every time.

    python desk_match.py            -> the check of every named desk
    python desk_match.py --nightly  -> check, take back, name new
"""
import csv
import math
import os
import sys
from collections import defaultdict
from datetime import datetime

import pandas as pd

import attendance
import desks_data
import progress_data as pdx

ARRIVE = (-4.0, 14.0)    # min after an IN punch a desk fills
LEAVE = (-14.0, 4.0)     # min before an OUT punch a desk empties
STRONG = {"hits": 10, "z": 8.0, "clear": 3.0, "share": 0.4}
# A looser line for a pair, safe only because every pair must still pass
# check() -- its desk used while its person was inside, 85% and more.
LOOSE = {"hits": 6, "z": 5.0, "clear": 2.0, "share": 0.3}
PAD = pd.Timedelta(minutes=10)
VERIFIED, DOUBT = 0.85, 0.60   # share of desk time inside the windows
MIN_DESK_MIN = 120              # desk minutes over the days, to judge
CHECKS = os.path.join("people", "desk_checks.csv")
DROPPED = os.path.join("people", "desk_names_dropped.csv")
REJECTED = os.path.join("people", "desk_names_rejected.csv")  # review: no


def punches(campus=attendance.CAMPUS, data=None):
    d = attendance.load() if data is None else data
    d = d[d["place"].str.startswith(campus)].copy()
    d["day"] = d["at"].dt.strftime("%Y-%m-%d")
    return d


def desks_to_score(cfg=None):
    """The registry's desks, less those a listed employee sits at, plus
    the listed employees' own seats (with their also: cameras)."""
    cfg = pdx.load() if cfg is None else cfg
    listed = [p for p in (cfg or {}).get("people") or [] if p.get("seat")]
    df = desks_data.load()
    out = []
    for c, g in (df.groupby("code") if len(df) else []):
        rec, ch = g["recorder"].iloc[0], int(g["channel"].iloc[0])
        x, y = float(g["x"].iloc[0]), float(g["y"].iloc[0])
        if any((p["recorder"], int(p["channel"])) == (rec, ch)
               and (float(p["seat"][0]) - x) ** 2
               + (float(p["seat"][1]) - y) ** 2 <= 70 ** 2 for p in listed):
            continue
        out.append({"code": c, "recorder": rec, "channel": ch,
                    "seat": [x, y]})
    for p in listed:
        out.append({"code": p["code"], "recorder": p["recorder"],
                    "channel": int(p["channel"]), "seat": p["seat"],
                    "also": p.get("also") or [],
                    "eid": str(p.get("employee_id") or "")})
    return out


def lines(desks, day):
    """{desk code: timeline} for the day (progress_data.timeline)."""
    n, p = pdx.notes(day), pdx.passes(day)
    return {d["code"]: pdx.timeline(d, n, p) for d in desks}


def comings(line):
    """(arrivals, departures) of one desk's day."""
    arr, dep, prev = [], [], "away"
    for i, (s, e, st) in enumerate(line):
        if st == "desk" and prev != "desk":
            arr.append(s)
        nxt = line[i + 1][2] if i + 1 < len(line) else "away"
        if st == "desk" and nxt != "desk":
            dep.append(e)
        prev = st
    return arr, dep


def scores(pu, day_lines):
    """{eid: {desk: (z, hits, punches)}} over the days given."""
    H = defaultdict(lambda: defaultdict(int))
    n_of, desk_hits, total = defaultdict(int), defaultdict(int), 0
    for day, ls in day_lines.items():
        tr = {c: comings(line) for c, line in ls.items()}
        for _, r in pu[pu["day"] == day].iterrows():
            t = r["at"]
            total += 1
            n_of[r["eid"]] += 1
            for c, (arr, dep) in tr.items():
                if r["kind"] == "in":
                    hit = any(ARRIVE[0] <= (a - t).total_seconds() / 60.0
                              <= ARRIVE[1] for a in arr)
                else:
                    hit = any(LEAVE[0] <= (e - t).total_seconds() / 60.0
                              <= LEAVE[1] for e in dep)
                if hit:
                    H[r["eid"]][c] += 1
                    desk_hits[c] += 1
    out = defaultdict(dict)
    for eid, ds in H.items():
        n = n_of[eid]
        for c, h in ds.items():
            p = max(desk_hits[c] / float(max(total, 1)), 1e-4)
            out[eid][c] = ((h - n * p) / math.sqrt(n * p * (1 - p)), h, n)
    return out


def pair(z, line=STRONG):
    """[(eid, desk, z, next z, hits, punches)], one to one, strongest
    first, those over `line` only."""
    ranked = []
    for eid, ds in z.items():
        best = sorted(ds.items(), key=lambda kv: -kv[1][0])
        c, (zz, h, n) = best[0]
        nxt = best[1][1][0] if len(best) > 1 else 0.0
        if h >= line["hits"] and zz >= line["z"] \
                and zz - nxt >= line["clear"] and h / float(n) >= line["share"]:
            ranked.append((zz, eid, c, nxt, h, n))
    out, used = [], set()
    for zz, eid, c, nxt, h, n in sorted(ranked, reverse=True):
        if c in used:
            continue
        used.add(c)
        out.append((eid, c, zz, nxt, h, n))
    return out


def refused(paths=None):
    """{(desk code, employee code)} never to be paired again: a "no" on a
    review (REJECTED, with a header) and the names the nightly check took
    back (DROPPED, without one)."""
    out = set()
    for path in paths or (REJECTED, DROPPED):
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if len(row) >= 2 and row[0] != "code" and row[1]:
                    out.add((row[0], attendance.code(row[1])))
    return out


def new_names(z_free, z_all, taken, no=frozenset(), line=LOOSE):
    """pair() over the free people and desks, less a pair refused once
    (`no`) and a desk whose best person over everybody (`z_all`) is one
    who already has a desk (`taken`) -- a second view of their desk, or
    the next seat of somebody who comes and goes with them."""
    best = {}
    for eid, ds in z_all.items():
        for c, (zz, _, _) in ds.items():
            if c not in best or zz > best[c][0]:
                best[c] = (zz, eid)
    out = []
    for eid, c, zz, nxt, h, n in pair(z_free, line):
        if (c, attendance.code(eid)) in no:
            continue
        top = best.get(c)
        mine = (z_all.get(eid) or {}).get(c, (zz,))[0]
        if top and top[1] != eid and top[1] in taken and top[0] > mine:
            continue
        out.append((eid, c, zz, nxt, h, n))
    return out


def check(line_by_day, eid, data=None):
    """How a desk's occupied time sits with its person's time inside:
    {"desk_min", "inside_min", "share", "days", "verdict"}; verdict
    "verified", "doubt" or "too little" (or "no punches")."""
    desk = inside = 0.0
    days = 0
    any_punch = False
    for day, line in line_by_day.items():
        win = attendance.inside(eid, day, data=data, pad=PAD)
        if win:
            any_punch = True
        occ = [(s, e) for s, e, st in line if st == "desk"]
        if not occ:
            continue
        days += 1
        for s, e in occ:
            m = (e - s).total_seconds() / 60.0
            desk += m
            inside += sum(max(0.0, (min(e, b) - max(s, a)).total_seconds())
                          for a, b in win) / 60.0
    share = inside / desk if desk else None
    if not any_punch:
        verdict = "no punches"
    elif desk < MIN_DESK_MIN:
        verdict = "too little"
    elif share >= VERIFIED:
        verdict = "verified"
    elif share < DOUBT:
        verdict = "doubt"
    else:
        verdict = "unsure"
    return {"desk_min": round(desk), "inside_min": round(inside),
            "share": share, "days": days, "verdict": verdict}


def named_desks(cfg=None):
    """[(desk dict, employee_id, how)] for every desk with a name."""
    cfg = pdx.load() if cfg is None else cfg
    names = desks_data.load_desk_names()
    machine = pdx.by_attendance()
    out = []
    for d in desks_to_score(cfg):
        if d.get("eid"):
            out.append((d, d["eid"], "listed"))
        elif d["code"] in names:
            out.append((d, names[d["code"]][0],
                        "attendance" if machine.get(d["code"]) ==
                        names[d["code"]][0] else "by hand"))
    return out


def days_with_punches(pu):
    return sorted(d for d in pu["day"].unique()
                  if os.path.exists(os.path.join(pdx.SEATS, d + ".csv")))


def check_all(cfg=None, pu=None, days=None, out=CHECKS):
    """Check every named desk; write people/desk_checks.csv; return rows."""
    pu = punches() if pu is None else pu
    days = days_with_punches(pu) if days is None else days
    nd = named_desks(cfg)
    by_day = {day: lines([d for d, _, _ in nd], day) for day in days}
    rows = []
    for d, eid, how in nd:
        c = check({day: by_day[day][d["code"]] for day in days}, eid)
        rows.append(dict(c, code=d["code"], employee_id=eid, how=how))
    _write(out, rows, ["code", "employee_id", "how", "days", "desk_min",
                       "inside_min", "share", "verdict"])
    return rows


def _write(path, rows, cols):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols + ["at"])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for r in rows:
            w.writerow([("%.3f" % r[c]) if isinstance(r.get(c), float)
                        else r.get(c, "") for c in cols] + [now])


def load_checks(path=CHECKS):
    """{desk code: {"share", "verdict", "days"}} from the last check."""
    if not os.path.exists(path):
        return {}
    d = pd.read_csv(path, dtype=str).fillna("")
    return {r["code"]: {"share": float(r["share"]) if r["share"] else None,
                        "verdict": r["verdict"], "days": r["days"],
                        "at": r["at"]} for _, r in d.iterrows()}


def nightly(cfg=None, roster=None, line=LOOSE):
    """Check every named desk; take back the machine-only names that fail;
    name the new pairs over `line` whose own check passes. Returns a short
    summary."""
    cfg = pdx.load() if cfg is None else cfg
    pu = punches()
    days = days_with_punches(pu)
    if not days:
        return "no punches on days with seat notes"
    rows = check_all(cfg, pu, days)
    dropped = [r for r in rows if r["how"] == "attendance"
               and r["verdict"] == "doubt"]
    for r in dropped:
        desks_data.save_desk_name(r["code"], "", "")
        _append(DROPPED, [r["code"], r["employee_id"], "%.2f" % r["share"]])
    # new pairs among the people and desks still free
    names = desks_data.load_desk_names()
    taken = {attendance.code(e) for e, _ in names.values()} | {
        attendance.code(p.get("employee_id")) for p in cfg.get("people")
        or [] if p.get("employee_id")}
    free = [d for d in desks_to_score(cfg)
            if d["code"] not in names and not d.get("eid")]
    fpu = pu[~pu["eid"].isin(taken)]
    by_day = {day: lines(free, day) for day in days}
    if roster is None:
        # the roster without staff_faces (which brings the face models,
        # and the hosted page has no OpenCV)
        roster = {attendance.code(r["employee_id"]): r
                  for r in desks_data.load_roster()}
    named_now = []
    for eid, c, zz, nxt, h, n in new_names(scores(fpu, by_day),
                                           scores(pu, by_day), taken,
                                           refused(), line):
        r = roster.get(eid)
        if not r:
            continue                      # not in the directory
        if any(w in (r.get("designation") or "").lower()
               for w in ("janitor", "gate keeper", "security guard",
                         "office boy", "driver")):
            continue                      # passes desks, sits at none
        ck = check({day: by_day[day][c] for day in days}, eid)
        if ck["verdict"] != "verified":
            continue
        desks_data.save_desk_name(c, r["employee_id"], r.get("name", ""))
        _append(pdx.BY_ATTENDANCE, [c, r["employee_id"], "%.1f" % zz, h, n,
                                    datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S")],
                ["code", "employee_id", "z", "hits", "punches", "at"])
        named_now.append(c)
    return ("checked %d named desks (%d verified, %d doubt); took back %d; "
            "named %d new" % (len(rows),
                              sum(r["verdict"] == "verified" for r in rows),
                              sum(r["verdict"] == "doubt" for r in rows),
                              len(dropped), len(named_now)))


def _append(path, row, header=None):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new and header:
            w.writerow(header)
        w.writerow(row)


def gate_faces():
    """The gate's faces read again with the machines beside them (26 Nov,
    gate_match.nightly_faces: exits -> the gate gallery, "gate+machines"
    names kept apart) -- after the desks, in the same night's run. Never
    raises: a summary or the reason it did not run.

    gate_match is loaded by name, not imported: the dashboard reaches this
    module (progress_data -> desk_match) and test_dashboard follows every
    import statement in it, and gate_match brings the face models (OpenCV)
    -- the laptop's half, never the hosted page's."""
    try:
        import importlib
        gate_match = importlib.import_module("gate_match")
        return gate_match.nightly_faces()
    except Exception as e:                                  # noqa: BLE001
        return "gate faces: not read (%s)" % type(e).__name__


def main(argv):
    if "--nightly" in argv:
        print(nightly())
        print(gate_faces())
        return
    for r in sorted(check_all(), key=lambda r: (r["verdict"], r["code"])):
        print("%-11s %-10s %-10s days %d desk %4dm share %s" % (
            r["code"], r["how"], r["verdict"], r["days"], r["desk_min"],
            "%.2f" % r["share"] if r["share"] is not None else "--"))


if __name__ == "__main__":
    main(sys.argv)
