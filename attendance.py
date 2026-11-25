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
    return {"first_in": first_in, "last_out": last_out,
            "inside_min": inside, "outings": outings,
            "punches": int(len(mine))}
