"""Every desk at 140-H, day by day: who sat how long at each desk.

Shamroze, 24 Nov 2026: "jaise 5 employees ka banaya, waise 140 ke sab
employees ka -- jo desk par baithte hain -- progress bana do: kaun kitni
der desk par baitha." The five are followed by name (progress.yaml); this
is every other desk, from the seat notes the loop writes every pass of
every camera (seats/<date>.csv, back to 12 Nov):

  * a desk is a regular seat of an office camera (seat_map: a spot held
    in 10%+ of the passes of the last working days) -- so lobbies, the
    cafe, meeting rooms and the street are not desks, and the supporting
    staff, who do not sit at one, are not in it;
  * each desk's day is the five's rules exactly (progress_data.history:
    first in, last out, time at the desk of the watched time in the
    office, breaks; nothing filled across a hole; no sitter that begins
    after 22:00);
  * a desk carries a name only where one is known: the five, and seats
    named by face (seat_faces.py) -- otherwise its room and number.

Checked by eye on the five desks (97 of 100 frames); the other desks use
the same rules, unchecked one by one -- two cameras of one room can see
the same desk twice, and a desk shared in shifts is one desk.

    python desk_seats.py build [upto]   -> progress/desks.csv (local)
"""
import os
from datetime import datetime

import pandas as pd

import progress_data as pdx

CAMPUS = {"nvr1", "nvr4", "dvr2", "xvr3"}
OUT = os.path.join("progress", "desks.csv")         # git-ignored (progress/)
# The desks themselves are found by desk_seats.find_desks (seat_map, with
# OpenCV): this module stays pandas-only, so the dashboard can read it.
# Each desk's code, kept by place from day to day (desk_seats.
# stable_numbers): codes and pixels only, this laptop (progress/ is
# git-ignored).
CODES = os.path.join("progress", "desk_codes.json")


def codes_since(path=CODES):
    """"YYYY-MM-DD HH:MM:SS" from when a desk code means one place, or ""
    (before 24 Nov 18:00 codes were renumbered daily and at each restart)."""
    import json
    try:
        with open(path, encoding="utf-8") as fh:
            return str(json.load(fh).get("since") or "")
    except (OSError, ValueError):
        return ""


SEATS_NAMED = os.path.join("people", "seats_identified.csv")  # seat_faces
BY_GATE = os.path.join("people", "desks_by_gate.csv")          # gate_match
DESK_NAMES = os.path.join("people", "desk_names.csv")  # named on the tab
ROSTER = os.path.join("people", "roster.csv")          # staff_faces
DESK_PICS = os.path.join("frames", "desks")            # desk_watch, hourly


def load_roster(path=ROSTER):
    """[{employee_id, name, designation, department, project}] (the
    directory as staff_faces.py saved it), the Gadits left out."""
    import csv
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh)
                if not r["name"].strip().lower().endswith("gadit")]


def load_desk_names(path=DESK_NAMES):
    """{desk code: (employee_id, name)} as named on the Progress tab, the
    latest word for each ("" clears it)."""
    import csv
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["employee_id"]:
                out[r["code"]] = (r["employee_id"], r["name"])
            else:
                out.pop(r["code"], None)
    return out


def save_desk_name(code, employee_id, name, path=DESK_NAMES):
    """Shamroze names a desk (Shamroze, 24 Nov: "picture dalo, aage naam
    aur ID main daal dunga -- 100% match")."""
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["code", "employee_id", "name", "at"])
        w.writerow([code, employee_id or "", name or "",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")])


def desk_picture(code, day=None, base=DESK_PICS):
    """The newest hourly picture of a desk (that day's, else any day's)."""
    import glob
    for pattern in ([os.path.join(base, day, "%s_*.jpg" % code)] if day
                    else []) + [os.path.join(base, "*", "%s_*.jpg" % code)]:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


ALL_ROOMS = "All rooms"


def desk_key(code):
    """dvr2.9-10 after dvr2.9-9: the numbers in a desk's code as numbers."""
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", code)]


def naming_list(rooms_of, pictures, hand, room, todo_only):
    """The desks "Name the desks" walks through, one at a time: those with
    a picture (a desk nobody has sat at yet cannot be named by eye), in
    `room` (or ALL_ROOMS), and not named yet unless `todo_only` is False --
    by room, then desk."""
    return sorted((c for c in rooms_of
                   if pictures.get(c) and room in (ALL_ROOMS, rooms_of[c])
                   and not (todo_only and c in hand)),
                  key=lambda c: (rooms_of[c], desk_key(c)))


def all_desk_pictures(base=DESK_PICS):
    """{desk code: [its hourly pictures, newest first]} -- one look at the
    folder, not one a desk."""
    import glob
    out = {}
    for path in glob.glob(os.path.join(base, "*", "*.jpg")):
        day = os.path.basename(os.path.dirname(path))
        code, _, hour = os.path.splitext(os.path.basename(path))[0] \
            .rpartition("_")
        if code and hour.isdigit():
            out.setdefault(code, []).append((day, hour, path))
    return {c: [p for _, _, p in sorted(v, reverse=True)]
            for c, v in out.items()}


def picture_when(path):
    """"Tue 24 Nov, 13:00" for frames/desks/<day>/<code>_<HH>.jpg."""
    import datetime as _dt
    day = os.path.basename(os.path.dirname(path))
    hour = os.path.splitext(os.path.basename(path))[0].rpartition("_")[2]
    try:
        d = _dt.date.fromisoformat(day)
    except ValueError:
        return ""
    return "%s %d %s, %s:00" % (d.strftime("%a"), d.day, d.strftime("%b"),
                                hour)


def load_by_gate(path=BY_GATE):
    """{desk code: (name, employee_id)} from the gate's matching."""
    import csv
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return {r["code"]: (r["name"], r["employee_id"])
                for r in csv.DictReader(fh)}
SEAT_REVIEWS = os.path.join("people", "seat_reviews.csv")
SEAT_FACES = os.path.join("people", "seat_faces")
PHOTOS = os.path.join("people", "photos")


def load_seats_named(path=SEATS_NAMED):
    import csv
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_reviews(path=SEAT_REVIEWS):
    """A person's word on each seat named by face: {(recorder, channel, x,
    y, employee_id): "yes" | "no"}, the latest for each."""
    import csv
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[(r["recorder"], str(r["channel"]), str(r["x"]), str(r["y"]),
                 r["employee_id"])] = r["verdict"]
    return out


def save_review(recorder, channel, x, y, employee_id, verdict,
                path=SEAT_REVIEWS):
    """One yes/no on a seat's name (the Progress tab), on this laptop."""
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["recorder", "channel", "x", "y", "employee_id",
                        "verdict", "at"])
        w.writerow([recorder, channel, x, y, employee_id, verdict,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")])


def seat_picture(recorder, channel, x, y, base=SEAT_FACES):
    """The newest picture kept of a seat's sitter (seat_faces), or None."""
    import glob
    hits = sorted(glob.glob(os.path.join(base, "*", "%s_%s_%s_%s.jpg"
                                         % (recorder, channel, x, y))))
    return hits[-1] if hits else None


def names_for(desks, people=None, seats_named=None, reach=60.0,
              reviews=None, by_gate=None, named=None):
    """{desk code: (name, employee_id, how)}: first the desks Shamroze
    named on the tab (named: load_desk_names()), then the five by their
    seat, then seats named by face (people/seats_identified.csv, "named")
    -- "by face, confirmed" once a person said yes, gone once they said no
    (reviews: load_reviews()) -- and last the gate's matching."""
    reviews = reviews or {}
    out = {}
    for code, (eid, name) in (named or {}).items():
        out[code] = (name, eid, "named by hand")
    for p in people or []:
        for d in desks:
            if (d["recorder"], d["channel"]) != (p.get("recorder"),
                                                 int(p.get("channel") or 0)):
                continue
            sx, sy = (float(v) for v in p.get("seat") or (0, 0))
            if (d["seat"][0] - sx) ** 2 + (d["seat"][1] - sy) ** 2 <= reach ** 2:
                if d["code"] in out:          # named by hand: that stands
                    continue
                out[d["code"]] = (p.get("name") or p.get("code", ""),
                                  str(p.get("employee_id") or ""),
                                  "followed (%s)" % p.get("code", ""))
    for r in seats_named or []:
        if r.get("status") != "named":
            continue
        word = reviews.get((r["recorder"], str(r["channel"]), str(r["x"]),
                            str(r["y"]), r.get("employee_id", "")), "")
        if word == "no":
            continue
        for d in desks:
            if (d["recorder"], d["channel"]) != (r["recorder"],
                                                 int(r["channel"])):
                continue
            if (d["seat"][0] - float(r["x"])) ** 2 + \
                    (d["seat"][1] - float(r["y"])) ** 2 <= reach ** 2:
                out.setdefault(d["code"], (
                    r.get("name", ""), r.get("employee_id", ""),
                    "by face, confirmed" if word == "yes"
                    else "by face, to confirm"))
    # last: the gate's matching (gate_match.py), where nothing else named it
    for code, (name, eid) in (by_gate or {}).items():
        out.setdefault(code, (name, eid, "by the gate, to confirm"))
    return out


ACTIVITY = os.path.join("progress", "desks_activity")   # desk_watch.py
FOCUS_MIN = 60           # an unbroken stretch at the desk this long: focus
CORE = (11, 17)          # the core hours everybody is expected in
LATE_AFTER = (10, 30)    # in after this is a late start


def extras(person, day, n, p, hours=None):
    """What the world's workplace-analytics tools measure, from the same
    pass-by-pass line (progress_data.timeline): focus (unbroken stretches
    at the desk of FOCUS_MIN+, as "deep work" blocks), the share of the
    core hours at the desk, a late start, minutes at the desk after the
    office day, and the desk minutes in each hour 08-22 (the heatmap)."""
    hours = hours or pdx.office_hours()
    line = pdx.timeline(person, n, p)
    out = {"focus_min": 0.0, "focus_blocks": 0, "core_pct": None,
           "late_min": None, "after_min": 0.0}
    out.update({"h%02d" % h: 0.0 for h in range(8, 23)})
    run_s = run_e = None
    core_desk = core_seen = 0.0
    first = None
    end_day = pd.Timestamp(day) + pd.Timedelta(hours=float(hours[1]))
    c0 = pd.Timestamp(day) + pd.Timedelta(hours=CORE[0])
    c1 = pd.Timestamp(day) + pd.Timedelta(hours=CORE[1])

    def close_run():
        if run_s is not None:
            m = (run_e - run_s).total_seconds() / 60.0
            if m >= FOCUS_MIN:
                out["focus_min"] += m
                out["focus_blocks"] += 1
    for s, e, state in line:
        lo, hi = max(s, c0), min(e, c1)
        if hi > lo:
            core_seen += (hi - lo).total_seconds() / 60.0
        if state != "desk":
            close_run()
            run_s = run_e = None
            continue
        if first is None and s.hour >= pdx.DAY_FROM:
            first = s
        if hi > lo:
            core_desk += (hi - lo).total_seconds() / 60.0
        if e > end_day:
            out["after_min"] += (e - max(s, end_day)).total_seconds() / 60.0
        t = s
        while t < e:                       # spread over the hours
            h_end = (t.floor("h") + pd.Timedelta(hours=1))
            seg_end = min(e, h_end)
            if 8 <= t.hour <= 22:
                out["h%02d" % t.hour] += (seg_end - t).total_seconds() / 60.0
            t = seg_end
        if run_s is not None and s - run_e <= pdx.JOINED:
            run_e = e
        else:
            close_run()
            run_s, run_e = s, e
    close_run()
    if core_seen > 0:
        out["core_pct"] = core_desk / core_seen
    if first is not None:
        start = pd.Timestamp(day) + pd.Timedelta(hours=float(hours[0]))
        out["late_min"] = (first - start).total_seconds() / 60.0
    return out


def assign_notes(day_notes, desks):
    """Each seat note to one desk at most: on each camera, pass by pass,
    notes and desks matched one to one, nearest first -- the rule
    desk_activity.assign_desks keeps live (24 Nov, checked by eye: a
    neighbour had been counted at an empty desk beside his own).
    Returns {desk code: that desk's notes}."""
    out = {d["code"]: [] for d in desks}
    if day_notes is None or day_notes.empty:
        return {c: day_notes for c in out}
    by_cam = {}
    for d in desks:
        by_cam.setdefault((d["recorder"], int(d["channel"])), []).append(d)
    for (rec, ch, _), g in day_notes.groupby(["recorder", "channel", "time"]):
        ds = by_cam.get((rec, int(ch)))
        if not ds:
            continue
        width = float(g["frame_w"].iloc[0]) or 1.0
        pairs = []
        for idx, r in g.iterrows():
            reach = max(pdx.SEAT_RADIUS * width, pdx.SEAT_REACH * float(r["h"]))
            bx, by = float(r["cx"]), float(r["cy"]) + float(r["h"]) / 2.0
            for d in ds:
                dist = ((bx - d["seat"][0]) ** 2 + (by - d["seat"][1]) ** 2) \
                    ** 0.5
                if dist <= reach:
                    pairs.append((dist / reach, idx, d["code"]))
        used_i, used_d = set(), set()
        for _, idx, code in sorted(pairs):
            if idx in used_i or code in used_d:
                continue
            used_i.add(idx)
            used_d.add(code)
            out[code].append(idx)
    return {c: day_notes.loc[ix] for c, ix in out.items()}


def build(upto=None, count=20, folder=pdx.SEATS, out=OUT, desks=None,
          activity=ACTIVITY, codes=None):
    """Every desk's working days up to `upto` to progress/desks.csv: one
    row a desk a day (the history's columns, the world's measures, and the
    desk's own). With `codes` (CODES), the activity rows written before
    the codes were kept by place are left out: their code meant another
    desk (presence comes from the seat notes, by place, and stands)."""
    upto = upto or datetime.now().strftime("%Y-%m-%d")
    desks = desks or []              # desk_seats.find_desks(upto)
    cache, rows, acts = {}, [], {}
    since = codes_since(codes) if codes else ""

    def rows_for(day):
        if day not in acts:
            a = pdx.load_activity(day, activity)
            if since and len(a) and day <= since[:10]:
                a = a[a["at"] >= pd.Timestamp(since)] if day == since[:10] \
                    else a.iloc[0:0]
            acts[day] = a
        return acts[day]
    hours = pdx.office_hours()
    # each day's notes shared out among the desks, one person one desk
    per_desk = {d["code"]: {} for d in desks}
    for day in pdx.working_days(upto, count, folder):
        n_all, p_all = pdx.notes(day), pdx.passes(day)
        for code, n_desk in assign_notes(n_all, desks).items():
            per_desk[code][day] = (n_desk, p_all)
    for d in desks:
        person = {"code": d["code"], "recorder": d["recorder"],
                  "channel": d["channel"], "seat": d["seat"],
                  "department": d["room"]}
        cache = per_desk.get(d["code"], {})
        try:
            past = pdx.history(person, upto, count, folder, cache, stored={},
                               rows_for=rows_for)
        except Exception:                                   # noqa: BLE001
            past = []
        for r in past:
            n, p = cache.get(r["day"], (None, None))
            try:
                more = extras(person, r["day"], n, p, hours) \
                    if n is not None else {}
            except Exception:                               # noqa: BLE001
                more = {}
            rows.append(dict(r, **more, code=d["code"], room=d["room"],
                             recorder=d["recorder"], channel=d["channel"],
                             x=d["seat"][0], y=d["seat"][1],
                             share=d["share"]))
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_csv(out, index=False)
    return df


def load(path=OUT):
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    for c in ("first", "last"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def room_summary(df, day, days=7):
    """Room by room, for the hosted page -- rooms and numbers only, never a
    name or a desk's code: desks, desks sat at on `day`, the usual hours at
    a desk and desk %, focus, and `day`'s hour-by-hour share of desks sat
    at (h08..h22)."""
    if df.empty:
        return []
    out = []
    hours = ["h%02d" % h for h in range(8, 23)]
    for room, g in df.groupby("room"):
        came = g[g["first"].notna()]
        recent = came[came["day"] > sorted(came["day"].unique())[-days - 1]] \
            if came["day"].nunique() > days else came
        today = g[(g["day"] == day) & g["first"].notna()]
        n = int(g["code"].nunique())
        row = {"room": room, "desks": n, "sat_today": int(today["code"]
                                                          .nunique()),
               "desk_h": round(float(recent["desk_min"].mean()) / 60.0, 1)
               if len(recent) else None,
               "desk_pct": round(100 * float(recent["desk_pct"].mean()))
               if len(recent) and recent["desk_pct"].notna().any() else None,
               "focus_h": round(float(pd.to_numeric(
                   recent.get("focus_min"), errors="coerce").mean()) / 60.0,
                   1) if "focus_min" in recent.columns and len(recent)
               else None}
        if all(h in g.columns for h in hours):
            day_rows = g[g["day"] == day]
            row["hourly"] = [round(min(1.0, float(day_rows[h].sum())
                                       / (60.0 * n)), 2) if n else 0.0
                             for h in hours]
        out.append(row)
    return sorted(out, key=lambda r: r["room"])


def summary(df, days=7, names=None):
    """One row a desk: its usual over its last `days` days in -- the
    table the Progress tab shows. names: names_for()."""
    names = names or {}
    out = []
    if df.empty:
        return pd.DataFrame()
    # once, not a desk at a time (24 Nov: rooms.yaml read 164 times kept
    # the Progress tab from ever reaching "Name the desks")
    late_bar = LATE_AFTER[0] * 60 + LATE_AFTER[1] - pdx.office_hours()[0] * 60
    for code, g in df.groupby("code"):
        came = g[g["first"].notna()].sort_values("day")
        whole = came[~came["part"].astype(str).str.lower().eq("true")]
        use = (whole if len(whole) else came).tail(days)
        name = names.get(code, ("", "", ""))

        def clock(s):
            m = s.dt.hour * 60 + s.dt.minute
            return "%02d:%02d" % divmod(int(m.mean()), 60) if len(m) else ""
        def avg(col, k=1.0, nd=0):
            if col not in use.columns or not len(use):
                return None
            v = pd.to_numeric(use[col], errors="coerce").dropna()
            return round(float(v.mean()) * k, nd) if len(v) else None
        late = pd.to_numeric(use.get("late_min", pd.Series(dtype=float)),
                             errors="coerce")
        out.append({
            "Room": g["room"].iloc[0], "Desk": code,
            "Who": name[0], "Employee ID": name[1], "Named": name[2],
            "Days in": int(len(came)),
            "Usual in": clock(use["first"]) if len(use) else "",
            "Usual out": clock(use["last"]) if len(use) else "",
            "At the desk, h a day": avg("desk_min", 1 / 60.0, 1),
            "Desk %": avg("desk_pct", 100),
            "Computer %": avg("computer_pct", 100),
            "Phone, min a day": avg("phone_min"),
            "Talking, min a day": avg("talking_min"),
            "Focus, h a day": avg("focus_min", 1 / 60.0, 1),
            "Core hours at desk %": avg("core_pct", 100),
            "Late starts": int((late > late_bar).sum()) if len(late) else 0,
            "After hours, min a day": avg("after_min"),
            "Longest break, min": avg("longest_break"),
            "Last day": came["day"].iloc[-1] if len(came) else "",
        })
    return pd.DataFrame(out).sort_values(["Room", "Desk"]).reset_index(
        drop=True)


# Built by `python desk_seats.py build [upto]`.
