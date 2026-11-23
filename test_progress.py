"""Check Progress: employees' time at their desks, and its page.

    python test_progress.py
"""
import os
import shutil
import sys
import tempfile

import pandas as pd

import progress_data as pdx
import progress_view as pv

FAILURES = []
DAY = "2026-11-20"           # a Friday


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


PERSON = {"code": "P9", "department": "Test Room", "recorder": "dvr2",
          "channel": 15, "seat": [560, 700]}


def at(hhmm):
    return pd.Timestamp("%s %s" % (DAY, hhmm))


def passes_every(start, end, minutes=5):
    """Passes of `minutes` from start to end (HH:MM)."""
    ends = pd.date_range(at(start) + pd.Timedelta(minutes=minutes), at(end),
                         freq="%dmin" % minutes)
    return pd.DataFrame({"start": ends - pd.Timedelta(minutes=minutes),
                         "end": ends})


def note(hhmm, x=560, y=600, h=200, ch=15):
    """A person whose box ends at (x, y + h/2)."""
    return {"time": hhmm + ":30", "room": "Test Room", "recorder": "dvr2",
            "channel": ch, "cx": x, "cy": y, "w": 90, "h": h, "score": 0.8,
            "frame_w": 1920, "frame_h": 1080,
            "at": at(hhmm) + pd.Timedelta(seconds=30)}


def notes_at(times, **kw):
    return pd.DataFrame([note(t, **kw) for t in times])


def check_timeline():
    print("-- a desk, pass by pass")
    p = passes_every("10:00", "11:00")            # 12 passes
    # At the desk 10:00-10:30, one pass missed at 10:15 (the detector
    # blinking); away 10:30-10:50; one lone hit at 10:42 (somebody passing).
    seen = ["10:01", "10:06", "10:11", "10:21", "10:26", "10:42", "10:56"]
    line = pdx.timeline(PERSON, notes_at(seen), p)
    states = [s for _, _, s in line]
    check("twelve passes, twelve states", len(states), 12)
    check("the one pass missed between two at the desk is at the desk",
          states[3], "desk")
    check("a lone pass at the desk with away either side is away",
          states[8], "away")
    check("so: six at the desk, five away, then the last back",
          states, ["desk"] * 6 + ["away"] * 5 + ["away"])
    far = notes_at(["10:01", "10:06"], x=1500)
    check("a person elsewhere in the picture is not at this desk",
          [s for _, _, s in pdx.timeline(PERSON, far, p)][:2],
          ["away", "away"])
    other = notes_at(["10:01", "10:06"], ch=16)
    check("nor is one on another camera",
          [s for _, _, s in pdx.timeline(PERSON, other, p)][:2],
          ["away", "away"])
    check("no passes, no timeline: not watched is never away",
          pdx.timeline(PERSON, notes_at(seen), pd.DataFrame(
              columns=["start", "end"])), [])


def check_day():
    print("-- an employee's day")
    p = passes_every("08:00", "22:00")
    seen = ([t.strftime("%H:%M") for t in pd.date_range(
        at("10:01"), at("13:00"), freq="5min")]
        + [t.strftime("%H:%M") for t in pd.date_range(
            at("14:01"), at("21:00"), freq="5min")])
    s = pdx.day_summary(PERSON, DAY, notes_at(seen), p, hours=(10, 20))
    check("watched all of office hours", round(s["watched_min"]), 600)
    check("first in at the pass of 10:01", s["first"], at("10:00"))
    check("last out with the pass of 20:56", s["last"], at("21:00"))
    check("at the desk 10-13 and 14-20 in office hours: 9 h",
          round(s["desk_min"]), 540)
    check("so 90% of office hours", round(s["share"], 2), 0.9)
    check("the lunch hour is the one break", [round(b[2]) for b in
                                              s["breaks"]], [60])
    check("an hour after office hours", round(s["late_min"]), 60)
    check("and ten hours in the day", round(s["total_min"]), 600)
    slots = pdx.strip(s, 8, 24, 10)
    check("the strip: 08:00 not in yet", slots[0], "out")
    check("  10:10 at the desk", slots[13], "desk")
    check("  13:20 away (lunch)", slots[32], "away")
    check("  21:30 gone", slots[81], "out")
    check("  22:30 not watched", slots[87], "unwatched")
    none = pdx.day_summary(PERSON, DAY, pd.DataFrame(), p, hours=(10, 20))
    check("a day not at the desk: watched, no first, share 0",
          (none["first"], none["share"]), (None, 0.0))
    blind = pdx.day_summary(PERSON, DAY, notes_at(seen),
                            pd.DataFrame(columns=["start", "end"]))
    check("a day not watched has no share at all", blind["share"], None)


def check_passes_and_usual():
    print("-- passes, and a usual day")
    folder = tempfile.mkdtemp()
    try:
        path = os.path.join(folder, "cycles.csv")
        pd.DataFrame({
            "time": ["2026-11-18 10:33:00", "2026-11-18 10:38:00",
                     "2026-11-19 09:00:00"],
            "cycle": [1, 2, 3],
            # 17 Nov 19:56 to 18 Nov 10:33: the laptop asleep in a pass.
            "seconds": [52000, 290, 280]}).to_csv(path, index=False)
        got = pdx.passes("2026-11-18", path)
        check("a pass the laptop slept through is left out", len(got), 1)
        check("  the real one kept, five minutes long",
              round((got["end"][0] - got["start"][0]).total_seconds()), 290)
    finally:
        shutil.rmtree(folder)

    def day(desk, watched, first=10.0, last=19.0, breaks=()):
        base = pd.Timestamp(DAY)
        came = desk > 0
        return {"watched_min": watched, "desk_min": desk,
                "share": desk / watched if watched else None,
                "first": base + pd.Timedelta(hours=first) if came else None,
                "last": base + pd.Timedelta(hours=last) if came else None,
                "breaks": list(breaks), "late_min": 0.0}

    days = [day(480, 600), day(360, 600, 11.0, 21.0, [(0, 0, 90.0)]),
            day(0, 600), day(60, 120)]
    u = pdx.usual(days, whole_min=480)
    check("three whole days, in on two", (u["days"], u["days_in"]), (3, 2))
    check("desk hours over the days in, not the day off", u["desk_h"], 7.0)
    check("first in and last out averaged", (u["first_h"], u["last_h"]),
          (10.5, 20.0))
    check("the longest break", u["longest_break"], 90.0)
    check("nothing watched, no usual day", pdx.usual([day(0, 0)]), None)
    person = dict(PERSON, since="2026-11-19")
    out = pdx.week(person, ["2026-11-18"], cache={
        "2026-11-18": (notes_at(["10:01"]), passes_every("10:00", "11:00"))})
    check("a day before the camera was re-aimed is marked, not read",
          (out[0].get("before"), out[0]["watched_min"]), (True, 0.0))


def check_page():
    print("-- the page")
    folder = tempfile.mkdtemp()
    try:
        seats = os.path.join(folder, "seats")
        os.makedirs(seats)
        rows = [note(t.strftime("%H:%M")) for t in pd.date_range(
            at("10:01"), at("19:00"), freq="5min")]
        frame = pd.DataFrame(rows).drop(columns=["at"])
        frame.to_csv(os.path.join(seats, "%s.csv" % DAY), index=False)
        p = passes_every("08:00", "22:00")
        pd.DataFrame({"time": p["end"].dt.strftime("%Y-%m-%d %H:%M:%S"),
                      "cycle": range(len(p)), "seconds": 300}).to_csv(
            os.path.join(folder, "cycles.csv"), index=False)
        here = os.getcwd()
        os.chdir(folder)
        try:
            cfg = {"campus": "140-H",
                   "people": [dict(PERSON, why="a test desk",
                                   check={"date": "20 Nov", "frames": 10,
                                          "agree": 9, "missed": "a chair"})],
                   "stages": [{"name": "Employees and codes",
                               "status": "done", "progress": 100,
                               "what": "five", "done": "23 Nov"},
                              {"name": "Time at the desk", "status": "doing",
                               "progress": 50, "what": "the desks",
                               "next": "check by eye", "due": "25 Nov"}]}
            people = pdx.build(cfg, DAY, (10, 20))
        finally:
            os.chdir(here)
    finally:
        shutil.rmtree(folder)
    check("one employee built, one working day", (len(people),
                                                  len(people[0]["days"])),
          (1, 1))
    html = pv.page("dark", cfg, people, "20 Nov 21:00", (10, 20))
    check("the employee is named by code when no name is kept",
          "Employee P9" in html, True)
    check("their desk's department is said beside it",
          "desk in Test Room" in html, True)
    check("the stages are on it", ("Employees and codes" in html,
                                   "In progress" in html), (True, True))
    check("and the check by eye, with what it missed",
          "9 of 10 frames agree" in html and "a chair" in html, True)
    check("each <style> closes on a line of its own (Streamlit's markdown)",
          ("</style><style>" in html, "</style>\n<style>" in html,
           "</style>\n<div" in html), (False, True, True))
    check("it says at the desk, never productive",
          ("at the desk" in html, "productive" in html.lower()),
          (True, False))
    named = dict(people[0], name="A <b>Name</b>")
    check("a name kept on the laptop is shown, escaped",
          "A &lt;b&gt;Name&lt;/b&gt;" in pv.card(named, pv.colours("dark")),
          True)
    for why in ("unset", "ask", "none"):
        check("the locked page (%s) shows no desk" % why,
              "P9" in pv.locked("light", why), False)
    check("unset says where the password goes",
          "PROGRESS_PASSWORD" in pv.locked("light", "unset"), True)
    check("hours read as a clock", (pv.hhmm(20.5), pv.hhmm(None)),
          ("20:30", "--"))
    check("minutes read as hours", (pv.dur(372), pv.dur(45)),
          ("6h 12m", "45m"))


def check_desk_activity():
    print("-- what an employee is doing at the desk")
    import desk_activity as da
    me = (0, 0.9, 500, 300, 620, 520)            # seated, box ends at 520
    seat = [560, 520]
    others = [(0, 0.8, 900, 300, 1020, 520)]     # somebody far off
    check("the person whose box ends at the desk is the employee",
          da.employee([me] + others, seat, 1920), me)
    check("nobody near the desk: no employee",
          da.employee(others, seat, 1920), None)
    neighbour = (0, 0.9, 630, 305, 750, 520)      # seated beside, same size
    standing = (0, 0.9, 600, 180, 700, 560)       # taller, head above, touching
    far_tall = (0, 0.9, 1300, 100, 1420, 700)     # tall, but across the room
    check("a neighbour sitting beside is not a visitor",
          da.visitor([me, neighbour], me), None)
    check("somebody standing over the desk is", da.visitor([me, standing], me),
          standing)
    check("somebody tall across the room is not (23 Nov, P1 typing alone)",
          da.visitor([me, far_tall], me), None)
    phone = (da.PHONE, 0.4, 540, 400, 560, 430)
    check("a phone in the employee's box is theirs",
          da.phone_near([phone], me), phone)
    check("a phone elsewhere is not",
          da.phone_near([(da.PHONE, 0.4, 1500, 400, 1520, 430)], me), None)


def check_tracking():
    print("-- the whole day, and the loop's hook")
    import numpy as np
    import progress_track as pt
    check("the dashboard's half needs no OpenCV",
          "cv2" in open("progress_data.py", encoding="utf-8").read(), False)
    check("kinds of place", [pt.place_of(r) for r in (
        "140-H Board Room", "H Smoking Area", "Mosque", "Prompt Cafe",
        "P1 Parking", "H Ground Floor Lobby", "HR Room")],
        ["meeting", "smoking", "prayer", "cafe", "outside", "corridor",
         "office"])
    check("their own department's room is their own room",
          pt.place_of("Test Room", own="Test Room"), "own room")
    # The re-ID matching, on made-up vectors.
    def unit(*v):
        v = np.array(v + (0.0,) * (512 - len(v)), np.float32)
        return v / np.linalg.norm(v)
    g = {"P1": unit(1, 0, 0), "P2": unit(0, 1, 0)}
    check("somebody clearly like P1 is P1",
          pt.best_match(unit(0.9, 0.1, 0.0), g)[0], "P1")
    check("somebody between two employees is nobody (the margin)",
          pt.best_match(unit(1, 1, 0), g), None)
    check("somebody like neither is nobody",
          pt.best_match(unit(0, 0, 1), g), None)
    pt._gallery.clear()
    pt.learn(DAY, "P9", unit(1, 0, 0))
    pt.learn(DAY, "P9", unit(0.8, 0.2, 0))
    check("an employee's look is the mean of their desk sightings",
          round(float(np.dot(pt.gallery(DAY, "P9"), unit(0.9, 0.1, 0))), 2),
          1.0)
    check("no desk sighting yet, no look", pt.gallery(DAY, "P8"), None)
    spots = {("dvr9", 1): [(500, 700)]}
    seated = (0, 0.9, 450, 400, 550, 700)
    standing = (0, 0.9, 900, 300, 1000, 700)
    tiny = (0, 0.9, 900, 300, 920, 330)
    got = pt.candidates("Test Office", ("dvr9", 1),
                        [seated, standing, tiny], 1920, set(), spots)
    check("in an office, somebody at a regular seat is its owner, not a "
          "visitor; a tiny box is too small to tell", got, [standing])
    got = pt.candidates("Prompt Cafe", ("dvr9", 1), [seated], 1920, set(),
                        spots)
    check("in the cafe a regular seat is still a candidate", got, [seated])
    pt._gallery.clear()

    # A day: at the desk 10:00-12:00 (computer, one phone read), away
    # 12:00-13:00, back 13:00-14:00 (no activity read), gone after.
    p = passes_every("08:00", "16:00")
    seen = [t.strftime("%H:%M") for t in pd.date_range(
        at("10:01"), at("12:00"), freq="5min")] + [
        t.strftime("%H:%M") for t in pd.date_range(
            at("13:01"), at("14:00"), freq="5min")]
    rows = pd.DataFrame([
        {"time": t.strftime("%H:%M:%S"), "code": "P9", "kind": "desk",
         "state": "phone" if t.hour == 11 and t.minute < 10 else "computer",
         "room": "Test Room", "recorder": "dvr2", "channel": 15,
         "score": 1.0, "x1": 0, "y1": 0, "x2": 0, "y2": 0}
        for t in pd.date_range(at("10:02"), at("11:58"), freq="5min")])
    rows["at"] = pd.to_datetime(DAY + " " + rows["time"])
    d = pdx.day_activity(PERSON, DAY, rows=rows, notes=notes_at(seen),
                         passes=p)
    m = d["minutes"]
    check("first in, last out", (d["first_in"], d["last_out"]),
          (at("10:00"), at("14:00")))
    check("two hours read at the desk, mostly the computer",
          (round(m["computer"] + m["phone"]), m["phone"] > 0), (120, True))
    check("the hour back without a reading is 'desk', not guessed",
          round(m["desk"]), 60)
    check("the hour away, with no camera match, is unseen",
          round(m["unseen"]), 60)
    check("the estimate shares the unread hour as the read ones were",
          round(sum(d["estimate"].values())), 180)
    check("before and after the day is 'out', not unseen",
          d["line"][0][2], "out")

    # Sightings while away: possible until confirmed; only "yes" counts.
    seen = pd.DataFrame([
        {"time": "12:20:00", "code": "P9", "kind": "seen",
         "state": "possible", "room": "Prompt Cafe", "recorder": "nvr4",
         "channel": 14, "score": 0.76, "x1": 0, "y1": 0, "x2": 0, "y2": 0},
        {"time": "10:30:00", "code": "P9", "kind": "seen",
         "state": "possible", "room": "H Smoking Area", "recorder": "nvr1",
         "channel": 12, "score": 0.80, "x1": 0, "y1": 0, "x2": 0, "y2": 0},
        {"time": "15:40:00", "code": "P9", "kind": "seen",
         "state": "possible", "room": "Prompt Cafe", "recorder": "nvr4",
         "channel": 14, "score": 0.81, "x1": 0, "y1": 0, "x2": 0, "y2": 0}])
    seen["at"] = pd.to_datetime(DAY + " " + seen["time"])
    both = pd.concat([rows, seen], ignore_index=True)
    sat = notes_at(
        [t.strftime("%H:%M") for t in pd.date_range(
            at("10:01"), at("12:00"), freq="5min")]
        + [t.strftime("%H:%M") for t in pd.date_range(
            at("13:01"), at("14:00"), freq="5min")])
    d = pdx.day_activity(PERSON, DAY, rows=both, notes=sat, passes=p,
                         reviews={})
    check("a sighting while away is listed as possible, not counted",
          ([s["kind"] for s in d["possible"]], d["places"]), (["cafe"], {}))
    check("one while at the desk is not even listed (10:30)",
          any(s["time"] == "10:30:00" for s in d["possible"]), False)
    check("one more than an hour after the last out is not (15:40)",
          any(s["time"] == "15:40:00" for s in d["possible"]), False)
    d = pdx.day_activity(PERSON, DAY, rows=both, notes=sat, passes=p,
                         reviews={("12:20:00", "P9", "Prompt Cafe"): "yes"})
    check("confirmed, it is a place in the day's hours",
          (round(d["places"].get("cafe", 0)), d["possible"]), (5, []))
    d = pdx.day_activity(PERSON, DAY, rows=both, notes=sat, passes=p,
                         reviews={("12:20:00", "P9", "Prompt Cafe"): "no"})
    check("rejected, it is forgotten", (d["places"], d["possible"]), ({}, []))
    folder = tempfile.mkdtemp()
    try:
        pdx.save_review(DAY, "12:20:00", "P9", "Prompt Cafe", "yes", folder)
        pdx.save_review(DAY, "12:20:00", "P9", "Prompt Cafe", "no", folder)
        check("the latest word on a sighting stands",
              pdx.load_reviews(DAY, folder),
              {("12:20:00", "P9", "Prompt Cafe"): "no"})
    finally:
        shutil.rmtree(folder)

    # The loop's hook: one camera's boxes for the employee's desk.
    folder = tempfile.mkdtemp()
    old = (pt.OUT, pt.CROPS, pt._cfg.copy())
    try:
        pt.OUT = os.path.join(folder, "progress")
        pt.CROPS = os.path.join(folder, "crops")
        pt._cfg.update({"mtime": "fixed", "people": [PERSON]})
        orig = pt._people
        pt._people = lambda: [PERSON]
        frame = np.full((1080, 1920, 3), 120, np.uint8)
        from datetime import datetime as _dt
        now = _dt(2026, 11, 20, 10, 5, 0, tzinfo=pt.PKT)
        pt.observe("Test Room", ("dvr2", 15), frame,
                   [(500, 400, 620, 700, 0.9)], None, now)
        pt.observe("Test Room", ("dvr2", 15), None, [], None, now)
        pt.observe("Other", ("cd_nvr1", 3), frame, [(0, 0, 10, 10, .9)],
                   None, now)
        got = pd.read_csv(os.path.join(pt.OUT, DAY + ".csv"))
        check("the hook writes one desk row for the employee's camera",
              (len(got), got["kind"][0], got["state"][0]),
              (1, "desk", "computer"))
        check("and keeps the desk's picture for the day's video",
              len(os.listdir(os.path.join(pt.CROPS, DAY, "P9"))), 1)
        pt._people = orig
    finally:
        pt.OUT, pt.CROPS = old[0], old[1]
        pt._cfg.clear()
        pt._cfg.update(old[2])
        shutil.rmtree(folder)
    source = open("room_loop.py", encoding="utf-8").read()
    check("the loop calls the hook, guarded",
          "progress_track.observe(room.name, key, wide, counted, model)"
          in source and "progress_track = None" in source, True)


def check_night():
    print("-- at night: a stretch that only begins after 22:00 is no sitter")
    p = passes_every("21:30", "23:30")
    line = pdx.timeline(PERSON, notes_at(["23:06", "23:11", "23:16"]), p)
    check("an empty chair in infrared at 23:05-23:20 is not at the desk",
          [s for s in line if s[2] == "desk"], [])
    line = pdx.timeline(PERSON, notes_at(
        ["21:46", "21:51", "21:56", "22:01", "22:06", "22:11"]), p)
    check("somebody who sat down before 22:00 and works on is kept",
          (min(s[0] for s in line if s[2] == "desk").strftime("%H:%M"),
           max(s[1] for s in line if s[2] == "desk").strftime("%H:%M")),
          ("21:45", "22:15"))


def check_average():
    print("-- the usual week: averages over the last seven days in")

    def day(d, first, last, desk, part=False, comp=None):
        return {"day": d, "first": pd.Timestamp("%s %s" % (d, first)),
                "last": pd.Timestamp("%s %s" % (d, last)), "in_min": 600.0,
                "desk_min": desk, "desk_pct": desk / 600.0, "part": part,
                "computer_pct": comp, "computer_min": None if comp is None
                else comp * 600, "phone_min": None if comp is None else 10.0,
                "talking_min": None if comp is None else 5.0, "breaks": 2,
                "longest_break": 30.0}
    past = [day("2026-11-%02d" % d, "10:00", "20:00", 300.0)
            for d in range(10, 16)]
    past += [day("2026-11-16", "11:00", "21:00", 480.0, comp=0.7),
             day("2026-11-17", "09:00", "13:00", 100.0, part=True),
             {"day": "2026-11-18", "first": None, "last": None}]
    a = pdx.average(past)
    check("seven whole days in; a part day and a day not in left out",
          (a["days"], a["from"], a["to"]), (6, "2026-11-11", "2026-11-16"))
    check("usual in and out as clock times",
          (round(a["first"]), round(a["last"])), (610, 1210))
    check("desk % the mean of the days", round(a["desk_pct"], 3),
          round((5 * 0.5 + 0.8) / 6, 3))
    check("computer % only over the days it was read",
          (a["computer_pct"], a["read_days"]), (0.7, 1))
    check("nobody in yet: nothing", pdx.average([]), None)
    html = pv.averages_table([{"code": "P9", "department": "Test",
                               "history": past}])
    check("the page's table says the usual in and out",
          "10:10" in html and "20:10" in html and "1 day read" in html, True)


def check_presence_rules():
    print("-- at the desk: the rules checked by eye on 24 Nov")
    p = passes_every("10:00", "11:00")
    # A big box near the camera ends 80 px from the desk's point: inside
    # 0.3 of its own 300 px height, outside the frame's 67 px.
    far_big = notes_at(["10:01", "10:06", "10:11"], y=630 - 150 + 0,
                       h=300)
    far_big["cy"] = 700 + 80 - 150          # bottom 80 px below the point
    states = [s for _, _, s in pdx.timeline(PERSON, far_big, p)][:3]
    check("a big sitter's own height sets the reach", states,
          ["desk", "desk", "desk"])
    weak = notes_at(["10:01", "10:06", "10:11"])
    weak["score"] = 0.29
    check("a note under DESK_MIN_SCORE (a turned empty chair) is not a "
          "sitter", [s for _, _, s in pdx.timeline(PERSON, weak, p)][:3],
          ["away", "away", "away"])
    lone = notes_at(["10:21"])
    lone["score"] = 0.9                      # seated: 90 x 200, ratio 2.2?
    lone["w"], lone["h"] = 260, 295          # ratio 1.13: sitting
    check("a sure, seated lone pass is kept (back at the desk)",
          [s for _, _, s in pdx.timeline(PERSON, lone, p)][4], "desk")
    lone["w"], lone["h"] = 134, 329          # ratio 2.46: standing
    lone["cy"] = 700 - 329 / 2.0
    check("a lone pass of somebody standing by the desk is not",
          [s for _, _, s in pdx.timeline(PERSON, lone, p)][4], "away")
    holes = pd.concat([passes_every("10:00", "10:10"),
                       passes_every("10:30", "10:40")], ignore_index=True)
    # desk 10:00-10:05, nothing 10:05-10:10, (a 20 min hole), desk 10:30-35
    gap = notes_at(["10:01", "10:31"])
    gap["w"], gap["h"] = 120, 160
    gap["cy"] = 700 - 80
    states = [s for _, _, s in pdx.timeline(PERSON, gap, holes)]
    check("nothing is filled in across a hole in the watching",
          states[1], "away")


def check_now_and_history():
    print("-- right now, and every day kept")
    p = passes_every("08:00", "21:00")
    seen = ([t.strftime("%H:%M") for t in pd.date_range(
        at("10:01"), at("13:00"), freq="5min")]
        + [t.strftime("%H:%M") for t in pd.date_range(
            at("14:01"), at("19:00"), freq="5min")])
    rows = pd.DataFrame(columns=["time", "code", "kind", "state", "room",
                                 "recorder", "channel", "score", "at"])
    a = pdx.day_activity(PERSON, DAY, rows=rows, notes=notes_at(seen),
                         passes=p, reviews={})

    def state(hhmm):
        return pdx.live(a, at(hhmm), (10, 20))

    check("09:00: not in yet", state("09:00")["state"], "out")
    s = state("11:00")
    check("11:00: at the desk since 10:00", (s["state"],
                                             s["since"]), ("desk", at("10:00")))
    s = state("13:30")
    check("13:30: away since 13:00", (s["state"], s["since"]),
          ("away", at("13:00")))
    s = state("20:45")
    check("20:45: gone for the day, left at 19:00",
          (s["state"], s["since"]), ("gone", at("19:00")))
    rec, _ = pdx.day_record(PERSON, DAY, notes_at(seen), p, rows=rows,
                            reviews={})
    check("the day: in 10:00, out 19:00, 8 h at the desk of 9",
          (rec["first"], rec["last"], round(rec["desk_min"]),
           round(rec["in_min"]), round(rec["desk_pct"], 2)),
          (at("10:00"), at("19:00"), 480, 540, 0.89))
    check("  one break, an hour", (rec["breaks"], round(rec["longest_break"])),
          (1, 60))
    folder = tempfile.mkdtemp()
    try:
        path = os.path.join(folder, "history.csv")
        pdx.store_history([dict(rec, code="P9")], path)
        back = pdx.load_history(path)[(DAY, "P9")]
        check("the history file keeps the day",
              (back["first"], back["last"], round(back["desk_min"])),
              (at("10:00"), at("19:00"), 480))
    finally:
        shutil.rmtree(folder)
    # The hosted page's copy: names blank, times back as times.
    import json
    people = [{"code": "P9", "name": "A Name", "department": "Test Room",
               "focus": {"first_in": at("10:00")}, "history": [rec]}]
    rows_out = pdx.to_payloads({"campus": "140-H", "stages": []}, people,
                               (10, 20), "20 Nov 21:00")
    check("no name leaves this machine",
          "A Name" in "".join(j for _, j in rows_out), False)
    cfg, back, made, hours = pdx.from_payloads(
        [(c, json.loads(j)) for c, j in rows_out])
    check("and the numbers come back as they went",
          (back[0]["focus"]["first_in"], back[0]["history"][0]["last"],
           made, hours), (at("10:00"), at("19:00"), "20 Nov 21:00",
                          (10, 20)))


def check_publish():
    print("-- the numbers sent to the hosted page")
    import progress_track as pt

    class Cur:
        def __init__(self, fail=None):
            self.rows, self.fail = [], fail

        def executemany(self, sql, rows):
            if self.fail:
                raise self.fail
            self.rows += list(rows)

        def close(self):
            pass

    class Conn:
        def __init__(self, cur):
            self.cur = cur

        def cursor(self):
            return self.cur

        def commit(self):
            pass

        def close(self):
            pass

    import psycopg2
    cur = Cur()
    old = dict(pt._published)
    old_history = pdx.HISTORY
    scratch = tempfile.mkdtemp()
    pdx.HISTORY = os.path.join(scratch, "history.csv")   # not the real one
    try:
        pt._published.update(at=0.0, missing=False, told=False)
        sent = pt.publish(lambda: Conn(cur), clock=lambda: 1e9)
        check("every employee and the project, upserted",
              (sent, len(cur.rows) >= 2, cur.rows[-1][1]),
              (True, True, "_project"))
        check("not again within five minutes",
              pt.publish(lambda: Conn(cur), clock=lambda: 1e9 + 60), False)
        err = psycopg2.errors.UndefinedTable("no table")
        pt._published.update(at=0.0, missing=False, told=False)
        sent = pt.publish(lambda: Conn(Cur(fail=err)), clock=lambda: 2e9)
        check("no table yet: nothing sent, said once, tried again hourly",
              (sent, pt._published["missing"]), (False, True))
    finally:
        pt._published.clear()
        pt._published.update(old)
        pdx.HISTORY = old_history
        shutil.rmtree(scratch)
    loop = open("room_loop.py", encoding="utf-8").read()
    check("the loop sends them, guarded",
          "progress_track.publish(connect)" in loop, True)
    dash = open("rooms_dashboard.py", encoding="utf-8").read()
    check("the hosted page reads them when it has no progress.yaml",
          "cached_progress_cloud" in dash and "FROM progress_days" in dash,
          True)


def check_kept_local():
    print("-- kept on this machine")
    ignored = open(".gitignore", encoding="utf-8").read().split()
    check("progress.yaml is git-ignored", "progress.yaml" in ignored, True)
    check("the seat notes are git-ignored", "seats/" in ignored, True)
    source = open("rooms_dashboard.py", encoding="utf-8").read()
    check("the dashboard's Progress door is its own password",
          'wanted = _setting("PROGRESS_PASSWORD")' in source, True)
    check("  and unset means locked",
          'progress_view.locked(mode, "unset")' in source, True)


def check_faces():
    print("-- faces: only a clear face names somebody")
    import numpy as np
    import faces

    def unit(*v):
        v = np.array(v + (0.0,) * (128 - len(v)), np.float32)
        return v / np.linalg.norm(v)
    g = {"P1": np.array([unit(1, 0, 0), unit(.95, .05, 0), unit(.9, .1, 0)]),
         "P2": np.array([unit(0, 1, 0), unit(.05, .95, 0), unit(.1, .9, 0)])}
    check("a face like P1's kept faces is P1",
          faces.best_match(unit(.97, .03, 0), g)[0], "P1")
    check("a face half like P1, half like P2 is nobody (the margin)",
          faces.best_match(unit(1, 1, 0), g), None)
    check("a face like nobody's is nobody",
          faces.best_match(unit(0, 0, 1), g), None)
    check("no face, no answer", faces.best_match(None, g), None)
    check("the score is the mean of the best three",
          round(faces.score(unit(1, 0, 0), np.array(
              [unit(1, 0, 0), unit(1, 0, 0), unit(0, 1, 0), unit(1, 0, 0)])),
              3), 1.0)
    folder = tempfile.mkdtemp()
    try:
        check("no gallery yet is an empty one",
              faces.load_gallery("P7", folder).shape, (0, 128))
        for i in range(5):
            faces.add_to_gallery("P7", unit(1, .01 * i, 0), folder)
        check("the first five desk faces are kept",
              len(faces.load_gallery("P7", folder)), 5)
        check("then a stranger in the chair is not learned as the employee",
              faces.add_to_gallery("P7", unit(0, 0, 1), folder), False)
        check("but another face of theirs is",
              faces.add_to_gallery("P7", unit(1, .02, 0), folder), True)
        check("nothing is kept for no face",
              faces.add_to_gallery("P7", None, folder), False)
        check("the gallery is numbers, not pictures",
              sorted(os.listdir(folder)), ["P7.npy"])
    finally:
        shutil.rmtree(folder)
    # A face sighting stands as seen without a review; a "no" still wins.
    p = passes_every("08:00", "16:00")
    sat = notes_at([t.strftime("%H:%M") for t in pd.date_range(
        at("10:01"), at("12:00"), freq="5min")]
        + [t.strftime("%H:%M") for t in pd.date_range(
            at("13:01"), at("14:00"), freq="5min")])
    rows = pd.DataFrame([
        {"time": "12:20:00", "code": "P9", "kind": "seen", "state": "face",
         "room": "Prompt Cafe", "recorder": "nvr4", "channel": 14,
         "score": 0.58, "x1": 0, "y1": 0, "x2": 0, "y2": 0}])
    rows["at"] = pd.to_datetime(DAY + " " + rows["time"])
    d = pdx.day_activity(PERSON, DAY, rows=rows, notes=sat, passes=p,
                         reviews={})
    check("seen by face (0.58, under the body's 0.70): a place, no review",
          (round(d["places"].get("cafe", 0)), d["possible"],
           [s["how"] for s in d["sightings"]]), (5, [], ["face"]))
    d = pdx.day_activity(PERSON, DAY, rows=rows, notes=sat, passes=p,
                         reviews={("12:20:00", "P9", "Prompt Cafe"): "no"})
    check("a face somebody says no to is forgotten",
          (d["places"], d["sightings"]), ({}, []))
    import progress_track as pt
    check("the loop learns faces only at the desk, compares them elsewhere",
          ("faces.add_to_gallery" in open("progress_track.py").read(),
           "faces.best_match" in open("progress_track.py").read()),
          (True, True))
    check("face numbers stay on this laptop",
          "progress/" in open(".gitignore").read()
          and "models/" in open(".gitignore").read(), True)
    check("and the tracker still runs without the face models",
          callable(pt.face_galleries), True)


B = {"floors": ["Basement", "Ground floor", "First floor"],
     "places": {"Desk Room": {"floor": "Ground floor", "at": [1, 1]},
                "Lobby": {"floor": "Ground floor", "at": [2, 1]},
                "Stairs": {"floor": "Ground floor", "at": [3, 1]},
                "Cafe": {"floor": "First floor", "at": [3, 3]},
                "Basement": {"floor": "Basement", "at": [3, 1]},
                "Far Office": {"floor": "First floor", "at": [5, 5]}},
     "links": [["Desk Room", "Lobby"], ["Lobby", "Stairs"],
               ["Stairs", "Cafe"], ["Stairs", "Basement"],
               ["Cafe", "Far Office"]]}
CAMS = {("dvr9", 1): "Desk Room", ("dvr9", 2): "Lobby",
        ("dvr9", 3): "Stairs", ("dvr9", 4): "Cafe", ("dvr9", 5): "Basement",
        ("dvr9", 6): "Far Office"}


def check_building():
    print("-- the building: places, ways, the nearest cameras")
    import building
    check("the fewest steps from a desk to the cafe go up the stairs",
          building.route(B, "Desk Room", "Cafe"),
          ["Desk Room", "Lobby", "Stairs", "Cafe"])
    check("no way to an unknown place", building.route(B, "Desk Room", "X"),
          [])
    check("steps from the desk", building.steps_from(B, "Desk Room")["Far "
                                                                     "Office"],
          4)
    check("a place's height is its floor's",
          building.xyz(B, "Cafe"), (3.0, 3.0, 2.0))
    got = building.nearest_cameras(B, CAMS, "Desk Room", skip={("dvr9", 1)})
    check("the cameras nearest first, the desk's own left out (a tie in "
          "steps goes by the room's name)",
          [k for _, k, _ in got][:3], [("dvr9", 2), ("dvr9", 3), ("dvr9", 5)])
    check("a sound map has no problems", building.problems(B, list(B[
        "places"])), [])
    check("a room left off the map is said",
          building.problems(B, list(B["places"]) + ["New Room"]),
          ["room 'New Room' is not on the map"])
    real = building.load()
    rooms = [r for r in building.campus_rooms(
        recorders={"nvr1", "nvr4", "dvr2", "xvr3"})
        if r != "XVR 3 unused channels"]
    check("building.yaml has every 140-H room, and nothing else",
          building.problems(real, rooms), [])
    check("140-H's floors, bottom to top", building.floors(real),
          ["Basement", "Ground floor", "First floor", "Cafe floor"])
    check("from Wellows to the cafe by the stairs",
          "H Stairs" in building.route(real, "Wellows", "Prompt Cafe"), True)


def check_follow():
    print("-- follow mode: the cameras round somebody who has left the desk")
    from datetime import datetime as _dt
    import building
    import progress_follow as pf
    import progress_track as pt
    pf.reset()
    t0 = _dt(2026, 11, 20, 11, 0, 0, tzinfo=pt.PKT)

    def t(minutes):
        return t0 + pd.Timedelta(minutes=minutes)
    pf.on_desk("P9", True, t(0), "Desk Room", ("dvr9", 1))
    check("at the desk: nobody followed", pf.following(t(0).timestamp()), [])
    pf.on_desk("P9", False, t(1), "Desk Room", ("dvr9", 1))
    check("one look without them is not leaving (a missed detection)",
          pf.following(t(1).timestamp()), [])
    pf.on_desk("P9", False, t(2), "Desk Room", ("dvr9", 1))
    check("two in a row is: followed from the first miss",
          (pf.following(t(2).timestamp()), pf._state["P9"]["left"]),
          (["P9"], t(1).timestamp()))
    got = pf.plan(t(2).timestamp(), B, CAMS, set(CAMS), count=2)
    check("the nearest camera, and the cafe as soon (a likely place to "
          "go), never the desk's own",
          [k for k, _ in got], [("dvr9", 2), ("dvr9", 4)])
    got = pf.plan(t(3).timestamp(), B, CAMS, set(CAMS), count=2)
    check("then the ones not looked at yet", [k for k, _ in got][0],
          ("dvr9", 3))
    pf.on_seen("P9", "Cafe", t(4), "possible", 0.74)
    check("a sighting moves the looking round it",
          pf._state["P9"]["around"], "Cafe")
    got = pf.plan(t(4).timestamp(), B, CAMS, set(CAMS), count=1)
    check("so the cafe's own camera comes first",
          [k for k, _ in got], [("dvr9", 4)])
    check("followed for a while after the last sighting, then not",
          (pf.following(t(18).timestamp()), pf.following(t(20).timestamp())),
          (["P9"], []))
    pf.on_desk("P9", True, t(10), "Desk Room", ("dvr9", 1))
    check("back at the desk: not followed", pf.following(t(10).timestamp()),
          [])
    pf.on_desk("P8", False, t(0), "Desk Room", ("dvr9", 1))
    pf.on_desk("P8", False, t(1), "Desk Room", ("dvr9", 1))
    check("never seen at the desk today: not followed (not in yet)",
          pf.following(t(1).timestamp()), [])

    # A step: the desk camera every minute; round them once they have left.
    pf.reset()
    room = type("R", (), {"name": "Desk Room", "cameras": [("dvr9", 1)]})()
    others = [type("R", (), {"name": n, "cameras": [k]})()
              for k, n in CAMS.items() if k != ("dvr9", 1)]
    person = dict(PERSON, recorder="dvr9", channel=1, code="P9")
    grabbed, looked = [], []
    old = (pt._people, building.load, pf.campus_cameras)
    present = [True]
    try:
        pt._people = lambda: [person]
        building.load = lambda path=None: B
        pf.campus_cameras = lambda: CAMS

        def grab(r, key):
            grabbed.append(key)
            return "frame"

        def look(r, key, frame):
            looked.append(key)
            if key == ("dvr9", 1):
                pf.on_desk("P9", present[0], clock_now[0], "Desk Room", key)
        clock_now = [t(0)]

        def step(minutes):
            clock_now[0] = t(minutes)
            return pf.step([room] + others, {}, grab, look, now=t(minutes),
                           clock=lambda: t(minutes).timestamp())
        check("at 11:00 the desk camera is looked at", (step(0), grabbed),
              (1, [("dvr9", 1)]))
        grabbed.clear()
        check("not again within the minute", (step(0.5), grabbed), (0, []))
        present[0] = False
        step(1)
        step(2)
        grabbed.clear()
        step(3)
        check("once they have left, the cameras round the desk too",
              grabbed[0] == ("dvr9", 1) and ("dvr9", 2) in grabbed
              and ("dvr9", 1) not in grabbed[1:], True)
        grabbed.clear()
        late = _dt(2026, 11, 20, 23, 0, 0, tzinfo=pt.PKT)
        check("not at night", pf.step([room] + others, {}, grab, look,
                                      now=late, clock=lambda: late.timestamp()),
              0)
        check("a step that breaks says so and goes on",
              pf.step([room], {}, None, None, now=t(30),
                      clock=lambda: t(30).timestamp()), 0)
    finally:
        pt._people, building.load, pf.campus_cameras = old
        pf.reset()
    source = open("room_loop.py", encoding="utf-8").read()
    check("the loop follows between its batches, guarded",
          "progress_follow.step(rooms, recorders, grab_one, look_again"
          in source and "progress_follow = None" in source, True)
    check("and looks through the same gates and private hours (fetch)",
          "return fetch(SimpleNamespace(" in source, True)


def check_route_and_map():
    print("-- the day's way through the building, and its 3D picture")
    import building_view as bv
    day_act = {"line": [
        (at("10:00"), at("10:05"), "computer", "Test Room"),
        (at("10:05"), at("10:10"), "computer", "Test Room"),
        (at("10:10"), at("10:15"), "unseen", ""),
        (at("10:15"), at("10:20"), "unseen", ""),
        (at("10:20"), at("10:25"), "phone", "Test Room")],
        "sightings": [
            {"t": at("10:12"), "place": "140 H Cafe", "how": "possible",
             "score": 0.74, "recorder": "dvr9", "channel": 4},
            {"t": at("10:17"), "place": "140 H Cafe", "how": "possible",
             "score": 0.75, "recorder": "dvr9", "channel": 4}]}
    got = pdx.route(day_act, "Desk Room", CAMS)
    check("desk, the cafe (by its camera's room name, once), desk again",
          [(q["t"].strftime("%H:%M"), q["place"], q["how"]) for q in got],
          [("10:00", "Desk Room", "desk"), ("10:12", "Cafe", "possible"),
           ("10:20", "Desk Room", "desk")])
    check("a stop keeps till when", got[1]["until"], at("10:17"))
    person = {"code": "P9", "desk_place": "Desk Room", "route": got,
              "live": {"state": "away", "since": at("10:10")}}
    check("away and possibly seen: now possibly there",
          bv.where_now(person), ("Cafe", "possible"))
    check("at the desk: at the desk",
          bv.where_now(dict(person, live={"state": "desk"})),
          ("Desk Room", "desk"))
    check("away, not seen since leaving: nowhere drawn",
          bv.where_now(dict(person, route=got[:1]))[0], None)
    xs, ys, zs = bv.path_points(B, got)
    check("the way drawn goes by the stairs, not through the floor",
          len(xs), 7)
    fig = bv.figure(B, [person], "dark")
    check("the picture has the floors, the ways, the places and P9",
          any("P9" in (t.name or "") for t in fig.data)
          and len(fig.data) > len(B["floors"]) * 3, True)
    check("colours follow the code, not the order shown",
          bv.colour("P3", "light"), bv.colour("P3", "light", ["P1", "P2",
                                                              "P3"]))
    check("the way in words", bv.way_lines([person])[0][0], "P9")
    check("the hosted copy carries the way (codes and rooms, no names)",
          [q["place"] for q in pdx.from_payloads(pdx.to_payloads(
              {}, [dict(person, name="Someone")], (10, 20), "now"))[1][0][
              "route"]], ["Desk Room", "Cafe", "Desk Room"])


def main():
    check_faces()
    check_building()
    check_follow()
    check_route_and_map()
    check_night()
    check_average()
    check_timeline()
    check_day()
    check_passes_and_usual()
    check_page()
    check_desk_activity()
    check_tracking()
    check_presence_rules()
    check_now_and_history()
    check_publish()
    check_kept_local()
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
