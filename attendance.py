"""The attendance machines' punches: when each employee came in and went out.

Shamroze, 25 Nov 2026: HR's export of the machines' log -- one row a punch:
machine, employee code, time, the machine's place ("140-H IN", "140-H OUT",
"141-D IN", ...) and status (0 in, 1 out). Punches put in by hand from the
Life app (machine CheckInManual / CheckOutManual, place "Life IN/OUT") are
left out, as HR asked: they say what somebody typed, not when they passed.

The file is people's names' companion -- employee codes and times -- so it
lives in people/attendance/ on this laptop only (git-ignored), like the
roster. What leaves it is per-employee figures on the Progress page: first
in, last out, time in the building, the times out in between.

    attendance.day(employee_id, "2026-11-24")
        -> {"first_in", "last_out", "inside_min", "outings": [(out, back)],
            "punches"} or None
"""
import glob
import os

import pandas as pd

FOLDER = os.path.join("people", "attendance")
MANUAL = ("CheckInManual", "CheckOutManual")
CAMPUS = "140-H"
# Out and back in within this long is the turnstile twice, not an outing.
BLIP = pd.Timedelta(minutes=2)
_cache = {"key": None, "data": None}


def code(x):
    """An employee code as the roster keeps it, with or without the
    leading zeros the export drops."""
    s = str(x).strip()
    return s.lstrip("0") or "0"


def load(folder=None):
    """Every machine punch in the folder's CSVs (read again when they
    change): eid (code()), at, kind ("in" / "out"), place."""
    folder = folder or FOLDER
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    key = tuple((f, os.path.getmtime(f)) for f in files)
    if _cache["key"] == key and _cache["data"] is not None:
        return _cache["data"]
    parts = []
    for f in files:
        try:
            parts.append(pd.read_csv(f, dtype={"emp_code": str,
                                               "machine_id": str,
                                               "machine_location": str}))
        except (OSError, ValueError, pd.errors.ParserError):
            continue
    if not parts:
        data = pd.DataFrame(columns=["eid", "at", "kind", "place"])
    else:
        d = pd.concat(parts, ignore_index=True)
        if "id" in d.columns:
            d = d.drop_duplicates("id")
        d = d[~d["machine_id"].isin(MANUAL)]
        d = d[d["machine_location"].notna()
              & (d["machine_location"] != "\\N")]
        data = pd.DataFrame({
            "eid": d["emp_code"].map(code),
            "at": pd.to_datetime(d["date_time"], errors="coerce"),
            "kind": d["status"].astype(str).map({"0": "in", "1": "out"}),
            "place": d["machine_location"].astype(str)})
        data = data.dropna(subset=["at", "kind"]).sort_values("at")
    _cache.update(key=key, data=data)
    return data


def inside(employee_id, day_, campus=CAMPUS, data=None, pad=None):
    """[(from, to)] the employee was inside by the machines that day: each
    IN to the OUT after it (the last IN to the end of the day when nobody
    punched out), widened by `pad` either side."""
    data = load() if data is None else data
    if not employee_id or data is None or not len(data):
        return []
    mine = data[(data["eid"] == code(employee_id))
                & (data["at"].dt.strftime("%Y-%m-%d") == day_)
                & data["place"].str.startswith(campus)]
    out, t_in = [], None
    for _, r in mine.iterrows():
        if r["kind"] == "in" and t_in is None:
            t_in = r["at"]
        elif r["kind"] == "out" and t_in is not None:
            out.append((t_in, r["at"]))
            t_in = None
    if t_in is not None:
        out.append((t_in, pd.Timestamp(day_) + pd.Timedelta(hours=24)))
    if pad is not None:
        out = [(a - pad, b + pad) for a, b in out]
    return out


GATE = os.path.join("people", "entrance")    # entrance_watch: <day>.csv
NEAR_OUT = 600           # s: a gate passage this near its own OUT punch


def clock_offset(day_, gate=None, campus=CAMPUS, data=None, near=NEAR_OUT,
                 least=5):
    """Seconds the gate's clock ran ahead of the machines' that day (gate
    time minus machine time): the median, over the gate's named passages,
    of the time from that person's own nearest OUT punch, within `near`.
    None with fewer than `least` such passages.

    25 Nov (the face study): +162 to +165 s on the live days -- the
    laptop's clock, which Windows was not syncing (160 s ahead of internet
    time that evening) -- and -18 s on days read from the recorder's
    playback. A 45-s punch check needs it taken off first."""
    data = load() if data is None else data
    path = os.path.join(gate or GATE, day_ + ".csv")
    if data is None or not len(data) or not os.path.exists(path):
        return None
    try:
        g = pd.read_csv(path, dtype=str).fillna("")
    except (OSError, ValueError, pd.errors.ParserError):
        return None
    g = g[g["status"] == "named"]
    outs = data[(data["kind"] == "out") & data["place"].str.startswith(campus)
                & (data["at"].dt.strftime("%Y-%m-%d") == day_)]
    by = {e: pd.DatetimeIndex(grp["at"]) for e, grp in outs.groupby("eid")}
    diffs = []
    for eid, t in zip(g["employee_id"], g["time"]):
        punches = by.get(code(eid))
        at = pd.to_datetime("%s %s" % (day_, t), errors="coerce")
        if punches is None or pd.isna(at):
            continue
        d = (at - punches).total_seconds()
        k = abs(d).argmin()
        if abs(d[k]) <= near:
            diffs.append(float(d[k]))
    if len(diffs) < least:
        return None
    return float(pd.Series(diffs).median())


def days(campus=CAMPUS, data=None):
    """The days the export covers at a campus, oldest first."""
    data = load() if data is None else data
    if data is None or not len(data):
        return []
    d = data[data["place"].str.startswith(campus)]
    return sorted(d["at"].dt.strftime("%Y-%m-%d").unique())


HOME_SHARE = 0.5     # of an employee's punches at a campus: their campus


def home_shares(campus=CAMPUS, data=None):
    """{eid: share of all their punches made at `campus`'s machines}."""
    data = load() if data is None else data
    if data is None or not len(data):
        return {}
    at = data["place"].str.startswith(campus)
    return at.groupby(data["eid"]).mean().to_dict()


def visitors(campus=CAMPUS, data=None, home=HOME_SHARE):
    """How many passed a campus's machines but punch mostly elsewhere."""
    s = home_shares(campus, data)
    return sum(1 for v in s.values() if 0 < v < home)


def summary(campus=CAMPUS, data=None, start=10.0, grace=15, workdays=None,
            home=HOME_SHARE):
    """Every employee OF a campus -- at least `home` of their punches at its
    machines (25 Nov: 84 of 228 through 140-H's machines punch mostly at
    141-D, about 2.5 h a day at 140-H; they are visitors here, not its
    staff) -- over every day of the export: [{eid, days: {day: day()},
    days_in, usual_in, usual_out, inside_h, late, outings, home_share}] --
    usual_in / usual_out the median clock hour on working days in, inside_h
    the mean hours in the building, late the working days in after start +
    grace minutes. `workdays`: the days to count (default: Monday to
    Friday of the export). home=0 keeps everybody who passed."""
    data = load() if data is None else data
    all_days = days(campus, data)
    if workdays is None:
        workdays = [d for d in all_days if pd.Timestamp(d).dayofweek < 5]
    d = data[data["place"].str.startswith(campus)]
    shares = home_shares(campus, data)
    out = []
    for eid in sorted(d["eid"].unique()):
        if shares.get(eid, 1.0) < home:
            continue                    # mostly another campus's: a visitor
        mine = d[d["eid"] == eid]
        per = {}
        for day_ in sorted(mine["at"].dt.strftime("%Y-%m-%d").unique()):
            s = day(eid, day_, campus, mine)
            if s and s["first_in"] is not None:
                per[day_] = s
        work = [per[x] for x in workdays if x in per]
        if not per:
            continue

        def hour(t):
            return t.hour + t.minute / 60.0

        ins = sorted(hour(s["first_in"]) for s in work)
        outs = sorted(hour(s["last_out"]) for s in work
                      if s["last_out"] is not None)
        closed = [s for s in work if s.get("closed", True)]
        late_line = start + grace / 60.0
        out.append({
            "eid": eid, "days": per, "days_in": len(work),
            "of": len(workdays),
            "usual_in": ins[len(ins) // 2] if ins else None,
            "usual_out": outs[len(outs) // 2] if outs else None,
            # over the days that end on an OUT punch only; None when no
            # day does (the hours are not known, not zero)
            "inside_h": (sum(s["inside_min"] for s in closed) / 60.0
                         / len(closed)) if closed else None,
            "hours_days": len(closed),
            "late": sum(1 for x in ins if x > late_line),
            "outings": (sum(len(s["outings"]) for s in work) / float(len(work)))
            if work else None,
            "home_share": round(float(shares.get(eid, 1.0)), 2)})
    return out


def day(employee_id, day_, campus=CAMPUS, data=None):
    """One employee's day at one campus's machines, or None with no punch.

    first_in / last_out: the first IN and the last OUT punch (a day may
    end with nobody punching out: last_out None). inside_min: the time
    from each IN to the OUT after it. outings: (out, back) -- out through
    the machine and in again the same day, longer than BLIP."""
    data = load() if data is None else data
    if not employee_id or data is None or not len(data):
        return None
    mine = data[(data["eid"] == code(employee_id))
                & (data["at"].dt.strftime("%Y-%m-%d") == day_)
                & data["place"].str.startswith(campus)]
    if not len(mine):
        return None
    ins = mine[mine["kind"] == "in"]["at"].tolist()
    outs = mine[mine["kind"] == "out"]["at"].tolist()
    first_in = ins[0] if ins else None
    last_out = outs[-1] if outs and (not ins or outs[-1] > ins[0]) else None
    inside, outings = 0.0, []
    t_in = None
    last_out_at = None
    for _, r in mine.iterrows():
        if r["kind"] == "in":
            if last_out_at is not None and r["at"] - last_out_at > BLIP:
                outings.append((last_out_at, r["at"]))
            last_out_at = None
            if t_in is None:
                t_in = r["at"]
        else:
            if t_in is not None:
                inside += (r["at"] - t_in).total_seconds() / 60.0
                t_in = None
            last_out_at = r["at"]
    # closed: every IN met an OUT after it -- only then is inside_min the
    # day's time in the building (25 Nov: a day ending on an IN counted as
    # a morning, or nothing, and pulled the hours of whoever never punches
    # out down to zero)
    return {"first_in": first_in, "last_out": last_out,
            "inside_min": inside, "outings": outings,
            "closed": t_in is None and last_out is not None,
            "punches": int(len(mine))}
