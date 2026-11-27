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

    def kp(**pts):
        k = [[0.0, 0.0, 0.0] for _ in range(17)]
        names = {"nose": 0, "rear": 3, "lear": 4, "rsh": 5, "lsh": 6,
                 "rwr": 9, "lwr": 10}
        for n, (x, y) in pts.items():
            k[names[n]] = [x, y, 0.9]
        return k
    head = dict(nose=(100, 100), rear=(80, 95), lear=(120, 95),
                rsh=(60, 160), lsh=(140, 160))
    check("a hand held to the ear is a call (pose)",
          da.on_a_call(kp(rwr=(78, 100), **head)), True)
    check("hands down at the keyboard are not",
          da.on_a_call(kp(rwr=(85, 260), lwr=(115, 262), **head)), False)
    check("no sure head or hand: no call",
          da.on_a_call(kp(nose=(100, 100))), False)
    check("the pose network is the one downloaded on 23 Nov",
          da.POSE_MODEL, "yolov8s-pose.pt")
    check("the loop's desk reading uses the one close look and the pose",
          ("da.close_look(frame, me, model)" in open("progress_track.py")
           .read() and "da.hand_at_head(frame, me)" in open(
               "desk_watch.py").read()), True)


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
    got = pt.candidates("140-H Reception", ("dvr9", 1), [seated, standing],
                        1920, set(), spots)
    check("at the reception desk the sitter is the receptionist, never a "
          "visiting employee (24 Nov, P2 matched twice)", got, [standing])
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


def check_twin():
    print("-- the 3D twin: numbers only, every room, the five on request")
    import twin_view as tv
    latest = [{"room": "Cafe", "status": "occupied", "people": 3,
               "ac_state": "on", "ac_units_on": 2},
              {"room": "Lobby", "status": "empty", "people": 0,
               "ac_state": "on", "ac_units_on": float("nan")}]
    d = tv.scene_data(B, latest)
    rooms = {r["n"]: r for r in d["rooms"]}
    check("every place of the building is a room of the scene",
          sorted(rooms), sorted(B["places"]))
    check("its live numbers ride along (a missing count stays unknown)",
          (rooms["Cafe"]["p"], rooms["Cafe"]["u"], rooms["Lobby"]["u"],
           rooms["Basement"]["st"]), (3, 2, None, "unknown"))
    check("floors by height", (rooms["Basement"]["f"], rooms["Cafe"]["f"]),
          (0, 2))
    check("nobody drawn unless asked (the Progress tab only)", d["emp"], [])
    html = tv.page(tv.scene_data(B, latest, [
        {"code": "P9", "place": "Cafe", "how": "face", "colour": "#2a78d6"}]),
        "dark", 500)
    check("the page is whole: no placeholder left, three.js pinned",
          ("__" not in html.replace("__proto__", ""),
           "three@0.128.0" in html, '"P9"' in html), (True, True, True))
    sneaky = dict(B, places=dict(B["places"], **{
        "</script><b>": {"floor": "Basement", "at": [1, 1]}}))
    check("a room's name cannot end the script",
          "</script><b>" in tv.page(tv.scene_data(sneaky), "light"), False)
    check("no picture in it: drawn from numbers alone",
          any(w in html for w in (".jpg", ".png", "data:image")), False)
    dash = open("rooms_dashboard.py", encoding="utf-8").read()
    check("3D is first in 140-H's row, and the page still opens on Overview",
          ('PRIMARY = (["3D"] if campus == PROGRESS_CAMPUS else [])' in dash,
           'st.session_state["view"] = "Overview"' in dash), (True, True))


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


def check_stretches():
    print("-- the day stretch by stretch")
    day_act = {"line": [
        (at("08:00"), at("08:05"), "out", ""),
        (at("10:00"), at("10:05"), "computer", "Test Room"),
        (at("10:05"), at("10:10"), "phone", "Test Room"),
        (at("10:10"), at("10:15"), "unseen", ""),
        (at("10:15"), at("10:20"), "cafe", "Prompt Cafe"),
        (at("11:00"), at("11:05"), "desk", "Test Room"),
        (at("11:05"), at("11:10"), "out", "")],
        "sightings": [{"t": at("10:12"), "place": "x", "how": "possible",
                       "score": 0.7, "recorder": "dvr9", "channel": 4}]}
    got = pdx.stretches(day_act, CAMS)
    check("desk, away, a hole not watched, desk -- from first in to last out",
          [(s["from"].strftime("%H:%M"), s["to"].strftime("%H:%M"), s["what"])
           for s in got],
          [("10:00", "10:10", "desk"), ("10:10", "10:20", "away"),
           ("10:20", "11:00", "unwatched"), ("11:00", "11:05", "desk")])
    check("what they did at the desk, by minutes",
          got[0]["kinds"], {"computer": 5.0, "phone": 5.0})
    check("where they were while away: confirmed, and possibly",
          (got[1]["where"], got[1]["seen"]),
          (["Prompt Cafe"], [("Cafe", "possible")]))
    html = pv.stretch_list({"stretches": got}, pv.colours("dark"))
    check("the page lists them latest first",
          html.index("11:00") < html.index("10:00") and "Not watched" in html
          and "possibly Cafe" in html, True)


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


def check_cases():
    print("-- the boss's cases: plain sentences from the week")

    def rec(d, first, last, desk, comp=None):
        return {"day": d, "first": pd.Timestamp("%s %s" % (d, first)),
                "last": pd.Timestamp("%s %s" % (d, last)), "in_min": 600.0,
                "desk_min": desk, "desk_pct": desk / 600.0, "part": False,
                "computer_pct": comp, "computer_min": None, "phone_min": 5.0,
                "talking_min": 0.0, "breaks": 3, "longest_break": 40.0}
    people = [
        {"code": "P1", "history": [rec("2026-11-20", "09:30", "19:00", 480,
                                       0.7)]},
        {"code": "P2", "history": [rec("2026-11-20", "10:30", "21:00", 240,
                                       0.3)]},
        {"code": "P3", "history": []}]
    got = pdx.cases(people)
    check("longest at the desk, most away, first in and last out, computer",
          [c["title"] for c in got],
          ["Longest at the desk", "Most away from the desk",
           "First in, last out", "At the computer"])
    check("who, in each", [c["codes"] for c in got],
          [["P1"], ["P2"], ["P1", "P2"], ["P1"]])
    check("never 'productive'",
          any("productiv" in c["text"].lower() for c in got), False)
    check("one employee with a day in is no case yet",
          pdx.cases(people[:1] + people[2:]), [])
    check("the page has them", "Cases for the boss" in pv.cases_block(people),
          True)
    people[0].update(name="Test Person", employee_id="09999")
    check("on the laptop a name (and ID) stands where the code stood",
          (pv.tag(people[0]), pv.tag(people[1]),
           "Test Person sits at the desk" in pv.cases_block(people)),
          ("Test Person · 09999", "P2", True))
    sent = pdx.from_payloads(pdx.to_payloads({}, [dict(people[0], focus=None,
                                                       live={})], (10, 20),
                                             "now"))[1][0]
    check("the hosted page gets neither the name nor the employee ID",
          (sent["name"], sent["employee_id"]), ("", ""))
    # 24 Nov, Shamroze: "name, id, or unki picture, teeno bhjdo" -- only
    # where progress.yaml says cloud_names: true, and of a picture only the
    # directory photo's small icon, never one from a camera.
    import base64
    import io
    from PIL import Image
    folder = tempfile.mkdtemp()
    try:
        Image.new("RGB", (300, 400), (180, 120, 90)).save(
            os.path.join(folder, "09999.jpg"))
        icon = pdx.photo_icon("09999", folder)
        gone = (pdx.photo_icon("00000", folder),
                pdx.photo_icon("../09999", folder), pdx.photo_icon("", folder))
    finally:
        shutil.rmtree(folder)
    im = Image.open(io.BytesIO(base64.b64decode(icon.split(",", 1)[1])))
    check("a directory photo becomes a small square JPEG icon",
          (icon.startswith("data:image/jpeg;base64,"), im.size,
           len(icon) < 12000), (True, (pdx.ICON, pdx.ICON), True))
    check("no photo, or an ID that is not a plain one, is no icon", gone,
          ("", "", ""))
    one = dict(people[0], focus=None, live={}, photo=icon)
    off = pdx.from_payloads(pdx.to_payloads({}, [one], (10, 20), "now"))[1][0]
    on = pdx.from_payloads(pdx.to_payloads({"cloud_names": True}, [one],
                                           (10, 20), "now"))[1][0]
    check("not allowed: no name, ID or photo leaves the laptop",
          (off["name"], off["employee_id"], off["photo"]), ("", "", ""))
    check("allowed (progress.yaml cloud_names: true): name, ID and the icon",
          (on["name"], on["employee_id"], on["photo"] == icon),
          ("Test Person", "09999", True))
    check("the page draws the icon -- and nothing but a JPEG data icon",
          ('class="pg-face"' in pv.face(on),
           pv.face({"photo": "https://x.example/a.jpg"}),
           pv.face({"photo": 'data:image/jpeg;base64,AA" onerror="x'}),
           pv.badge({"code": "P2"})),
          (True, "", "", '<span class="pg-code">P2</span>'))


def check_campus_faces():
    print("-- campus faces: the roster, and who sits where")
    import json
    import numpy as np
    import faces
    import seat_faces as sfc
    import staff_faces as stf
    from datetime import datetime as _dt
    import progress_track as pt
    folder = tempfile.mkdtemp()
    try:
        raw = os.path.join(folder, "raw.json")
        json.dump([["00001", "Some Gadit", "Partner", "Ex", "D"],
                   ["00010", "Ann One", "Engineer", "Tech", "Lab"],
                   ["00010", "Ann One", "Engineer", "Tech", "Lab"],
                   ["00011", "Bo Two", "Manager", "GTM", "W"]],
                  open(raw, "w"))
        rows = stf.make_roster(raw, os.path.join(folder, "roster.csv"))
        check("the roster leaves out the Gadits and repeats",
              [r["employee_id"] for r in rows], ["00010", "00011"])
        check("no email column in it", "email" in " ".join(stf.FIELDS), False)
        got, failed = stf.fetch_photos(
            rows, os.path.join(folder, "photos"), pause=0,
            opener=lambda url: b"\xff\xd8 jpeg" if "00010" in url else b"<html>")
        check("a photo is kept only when it is a JPEG",
              (got, [f[0] for f in failed]), (1, ["00011"]))
    finally:
        shutil.rmtree(folder)
    check("no portrait, no face", faces.of_photo(None), None)
    spots = [(500, 700), (900, 700)]
    check("a box on a seat is that seat; one between seats is none",
          (sfc.seat_of((450, 450, 550, 700), spots, 1920),
           sfc.seat_of((660, 450, 740, 700), spots, 1920)),
          ((500, 700), None))

    def unit(*v):
        v = np.array(v + (0.0,) * (128 - len(v)), np.float32)
        return v / np.linalg.norm(v)
    ids = np.array(["00010", "00011"])
    photos = np.array([unit(1, 0, 0), unit(0, 1, 0)])
    seats = {"dvr9_1_500_700": np.array([unit(1, .05 * i, 0)
                                         for i in range(10)]),
             "dvr9_1_900_700": np.array([unit(1, 1, 0)] * 10),
             "dvr9_2_300_600": np.array([unit(1, 0, 0)] * 3)}
    got = {r["seat"]: (r["status"], r["best"]) for r in
           sfc.match(seats, ids, photos)}
    check("a seat clearly one person's is named; between two is unsure; "
          "three faces are too few",
          (got["dvr9_1_500_700"], got["dvr9_1_900_700"][0],
           got["dvr9_2_300_600"][0]),
          (("named", "00010"), "unsure", "few faces"))
    folder = tempfile.mkdtemp()
    old = faces.of_person, faces.available
    try:
        faces.of_person = lambda frame, box: unit(1, 0, 0)
        faces.available = lambda: True
        frame = np.zeros((1080, 1920, 3), np.uint8)
        day = _dt(2026, 11, 20, 11, 0, tzinfo=pt.PKT)
        night = _dt(2026, 11, 20, 23, 0, tzinfo=pt.PKT)
        n = sfc.observe("R", ("dvr2", 15), frame, [(450, 450, 550, 700, .9)],
                        now=day, spots=spots, out=folder)
        kept = sfc.samples(["2026-11-20"], folder)
        check("a seated face is kept as numbers for its seat",
              (n, list(kept), kept["dvr2_15_500_700"].shape),
              (1, ["dvr2_15_500_700"], (1, 128)))
        # (141-C/D's recorders are watched too since 27 Nov: cd_xvr2, its
        # IP conflict unresolved, is not; the 141 gym never)
        check("not at night, not off the campus, never the gym",
              (sfc.observe("R", ("dvr2", 15), frame, [(450, 450, 550, 700)],
                           now=night, spots=spots, out=folder),
               sfc.observe("R", ("cd_xvr2", 3), frame, [(450, 450, 550, 700)],
                           now=day, spots=spots, out=folder),
               sfc.observe("141 Gym", ("cd_nvr2", 7), frame,
                           [(450, 450, 550, 700)], now=day, spots=spots,
                           out=folder)), (0, 0, 0))
        check("numbers, and one small picture of the seat for the check",
              sorted(os.path.splitext(f)[1] for f in os.listdir(
                  os.path.join(folder, "2026-11-20"))), [".f16", ".jpg"])
    finally:
        faces.of_person, faces.available = old
        shutil.rmtree(folder)
    source = open("room_loop.py", encoding="utf-8").read()
    check("the loop keeps seat faces, guarded",
          "seat_faces.observe(room.name, key, wide, counted)" in source
          and "seat_faces = None" in source, True)
    check("people/ never goes to git", "people/" in open(".gitignore").read(),
          True)


def check_every_desk():
    print("-- every desk: the world's measures, and each desk's activity")
    import numpy as np
    import desk_watch as dw
    import desks_data as dd
    import progress_track as pt
    from datetime import datetime as _dt
    p = passes_every("09:00", "17:00")
    sat = notes_at([t.strftime("%H:%M") for t in pd.date_range(
        at("10:01"), at("12:30"), freq="5min")]
        + [t.strftime("%H:%M") for t in pd.date_range(
            at("13:01"), at("13:40"), freq="5min")])
    x = dd.extras(PERSON, DAY, sat, p, hours=(10.0, 20.0))
    check("one focus block (10:00-12:30, unbroken); 40 minutes is not one",
          (x["focus_blocks"], round(x["focus_min"])), (1, 150))
    check("in on time, nothing after hours, the hour 10-11 full",
          (round(x["late_min"]), x["after_min"], round(x["h10"])),
          (0, 0.0, 60))
    check("core hours (11-17) at the desk: 130 of 360 minutes",
          round(100 * x["core_pct"]), 36)
    # 24 Nov 18:00: codes numbered busiest-first moved from day to day;
    # now a desk keeps its number by place.
    import desk_seats as ds
    reg = {}
    check("first day: numbered in the order found",
          ds.stable_numbers("dvr2.2", [(1550, 182), (1091, 789)], reg),
          [1, 2])
    check("next day, busiest first the other way round: same numbers",
          ds.stable_numbers("dvr2.2", [(1085, 785), (1548, 190)], reg),
          [2, 1])
    check("a new seat gets the next number; one gone frees none",
          ds.stable_numbers("dvr2.2", [(700, 600), (1090, 788)], reg),
          [3, 2])
    check("and the desk follows its seat's small moves",
          reg["dvr2.2"][1][1:], [1090.0, 788.0])
    check("two seats near one desk: the nearer keeps it",
          ds.stable_numbers("dvr2.2", [(1120, 790), (1095, 789)], reg),
          [4, 2])
    # 24 Nov: the same day's clothes -- the gate keeps a named passer's,
    # each desk its sitter's look -- pair a desk with a passer.
    import clothes_match as cm
    import desk_watch as dw_
    import entrance_watch as ew_

    def u512(*v):
        x = np.zeros(512, np.float32)
        x[:len(v)] = v
        return x / np.linalg.norm(x)
    looks = {"dvr2.13-1": np.array([u512(1, 0.1), u512(1, 0), u512(0.9, 0.1)]),
             "dvr2.13-2": np.array([u512(0.1, 1), u512(0, 1), u512(0.1, 0.9)]),
             "dvr2.13-3": np.array([u512(0.7, 0.7)] * 3),     # like both
             "dvr2.13-4": np.array([u512(0, 0, 1)])}          # too few looks
    gate_ = {"A": np.array([u512(1, 0)]), "B": np.array([u512(0, 1)]),
             "C": np.array([u512(0, 0, 0, 1)])}
    pairs = cm.day_pairs(looks, gate_)
    check("clothes: a desk and a passer that pick each other; a look like"
          " two passers, or too few looks, pairs nobody",
          sorted((c, e) for c, (e, _, _) in pairs.items()),
          [("dvr2.13-1", "A"), ("dvr2.13-2", "B")])
    check("checked on the desks whose sitter is known",
          cm.evaluate(pairs, {"dvr2.13-1": "A", "dvr2.13-2": "X"}), (1, 1))
    check("over days: the passer a desk got most, and how often another",
          cm.combine([pairs, {"dvr2.13-1": ("A", .7, .1)},
                      {"dvr2.13-1": ("Z", .7, .1)}])[0],
          ("dvr2.13-1", "A", 2, 1))
    check("the gate's clothes box: under the face, three faces wide",
          ew_.body_box((100, 50, 40, 50), 2560, 1440), (60, 40, 180, 375))
    lk = tempfile.mkdtemp()
    try:
        when = pd.Timestamp("2026-11-24 11:00", tz="Asia/Karachi")
        dw_._looked.clear()
        kept = [dw_.keep_look("2026-11-24", "dvr2.13-1", None, (0, 0, 9, 9),
                              when + pd.Timedelta(minutes=m), lk,
                              embed=lambda f, b: [u512(1, 0)])
                for m in (0, 5, 16)]
        v = np.fromfile(os.path.join(lk, "looks", "2026-11-24",
                                     "dvr2.13-1.f16"), np.float16)
        check("a desk's sitter's look kept every 15 minutes, as numbers",
              (kept, len(v) // 512), ([True, False, True], 2))
    finally:
        shutil.rmtree(lk)
        dw_._looked.clear()
    # 24 Nov: names suggested camera against camera -- each desk's face
    # against the gate's faces -- only where the two pick each other.
    import numpy as np
    import name_suggest as ns

    def unit(*v):
        v = np.array(v + (0.0,) * (128 - len(v)), np.float32)
        return v / np.linalg.norm(v)
    G = np.array([unit(1, 0, 0), unit(0, 1, 0), unit(0.6, 0.8, 0)])
    seats = {"dvr2_9_1425_1000": (unit(1, 0.05, 0), 20),
             "dvr2_9_700_1050": (unit(0.3, 0.95, 0), 12),   # B or C?
             "nvr1_11_1375_500": (unit(0.9, 0.1, 0), 9)}
    got = ns.suggest(seats, ["A", "B", "C"], G)
    check("the desk and the person pick each other; the person's second"
          " desk and a near tie are not suggested",
          [(s["seat"], s["employee_id"]) for s in got],
          [("dvr2_9_1425_1000", "A")])
    since_f = os.path.join(tempfile.mkdtemp(), "codes.json")
    check("no codes file, nothing to leave out", dd.codes_since(since_f), "")
    with open(since_f, "w") as fh:
        fh.write('{"since": "2026-11-24 18:20:00", "desks": {}}')
    check("the codes file says from when",
          dd.codes_since(since_f), "2026-11-24 18:20:00")
    folder = tempfile.mkdtemp()
    old = dict(dw._desks), dict(dw._count)
    old_embed = dw.EMBED
    try:
        dw._desks.update(day=None, by_cam={})
        dw._count.clear()
        dw.EMBED = lambda f, b: [u512(0, 1)]       # no network in a test
        desk = {"code": "dvr9.1-1", "room": "Test Room", "recorder": "dvr2",
                "channel": 15, "seat": [500, 700], "share": 0.5}
        frame = np.zeros((1080, 1920, 3), np.uint8)
        now = _dt(2026, 11, 20, 11, 0, tzinfo=pt.PKT)
        n = dw.observe("Test Room", ("dvr2", 15), frame,
                       [(450, 450, 550, 700, .9)], None, now,
                       out=os.path.join(folder, "act"),
                       crops=os.path.join(folder, "crops"),
                       finder=lambda day: [desk])
        got = pd.read_csv(os.path.join(folder, "act", DAY + ".csv"))
        check("a sitter with no phone look this pass is 'desk' (not read)",
              (n, got["state"].tolist(), got["code"].tolist()),
              (1, ["desk"], ["dvr9.1-1"]))
        dw.observe("Test Room", ("dvr2", 15), frame, [], None, now,
                   out=os.path.join(folder, "act"),
                   crops=os.path.join(folder, "crops"),
                   finder=lambda day: [desk])
        got = pd.read_csv(os.path.join(folder, "act", DAY + ".csv"))
        check("nobody at it: away", got["state"].tolist()[-1], "away")
        check("one picture of the desk an hour",
              len(os.listdir(os.path.join(folder, "crops", DAY))), 1)
        check("not at night", dw.observe(
            "Test Room", ("dvr2", 15), frame, [], None,
            _dt(2026, 11, 20, 23, 30, tzinfo=pt.PKT),
            out=os.path.join(folder, "act"), finder=lambda day: [desk]), 0)
        check("the sitter's look kept beside the reading",
              os.path.exists(os.path.join(folder, "act", "looks", DAY,
                                          "dvr9.1-1.f16")), True)
    finally:
        dw.EMBED = old_embed
        dw._looked.clear()
        dw._desks.clear()
        dw._desks.update(old[0])
        dw._count.clear()
        dw._count.update(old[1])
        shutil.rmtree(folder)
    df = pd.DataFrame([dict(day=DAY, code="dvr9.1-1", room="Test Room",
                            first=at("10:00"), last=at("18:00"), part=False,
                            desk_min=300.0, desk_pct=0.6, computer_pct=0.5,
                            phone_min=10.0, talking_min=5.0, focus_min=120.0,
                            core_pct=0.7, late_min=75.0, after_min=0.0,
                            longest_break=30.0)])
    s = dd.summary(df, 7, {"dvr9.1-1": ("Test Person", "09999", "x")})
    check("the desk's usual: who, in, hours, computer, focus, late starts",
          (s["Who"][0], s["Usual in"][0], s["At the desk, h a day"][0],
           s["Computer %"][0], s["Focus, h a day"][0], s["Late starts"][0]),
          ("Test Person", "10:00", 5.0, 50.0, 2.0, 1))
    source = open("room_loop.py", encoding="utf-8").read()
    check("the loop reads every desk, guarded",
          "desk_watch.observe(room.name, key, wide, counted, model)" in source
          and "desk_watch = None" in source, True)
    ran = []
    old_at = dw._rebuilt["at"]
    try:
        dw._rebuilt["at"] = 0.0
        first = dw.rebuild(clock=lambda: 1e9, build=ran.append)
        again = dw.rebuild(clock=lambda: 1e9 + 600, build=ran.append)
        later = dw.rebuild(clock=lambda: 1e9 + 3700, build=ran.append)
        check("every desk's days worked out again at most hourly",
              (first, again, later, len(ran)), (True, False, True, 2))
    finally:
        dw._rebuilt["at"] = old_at
    check("the loop rebuilds them, guarded",
          "desk_watch.rebuild()" in source, True)
    import desk_activity as da_
    a = (0, .9, 450, 450, 550, 700)          # sits at seat A
    seats = {"A": (500, 700), "B": (560, 700)}
    got = da_.assign_desks([a], seats, 1920)
    check("one person, one desk: the nearer seat has him, the other none",
          (got["A"] is a, got["B"]), (True, None))
    neighbour = (0, .9, 560, 440, 650, 705)   # seated at B, box touching
    standing = (0, .9, 470, 250, 560, 720)    # tall, head above, touching
    sat = da_.assign_desks([a, neighbour], seats, 1920)
    check("a neighbour seated at the next desk is no visitor; somebody "
          "standing over the desk is",
          (da_.standing_visitor([a, neighbour], a, list(sat.values())),
           da_.standing_visitor([a, neighbour, standing], a,
                                list(sat.values())) is standing),
          (None, True))
    check("the desk's picture marks its seat where it really is (held "
          "inside the frame at an edge)",
          (dw.seat_in_crop((1080, 1920), (960, 700)),
           dw.seat_in_crop((1080, 1920), (960, 60))), ((240, 360), (240, 50)))
    check("and a box round the person sitting there, in the picture's "
          "pixels, held inside it",
          (dw.box_in_crop((1080, 1920), (960, 700), (860, 400, 1060, 720)),
           dw.box_in_crop((1080, 1920), (960, 700), (0, 0, 5000, 5000))),
          ((156, 110, 323, 376), (0, 0, 479, 479)))
    import desks_data as dd_
    pics = tempfile.mkdtemp()
    try:
        for d_, f_ in (("2026-11-23", "dvr9.1-2_10.jpg"),
                       ("2026-11-24", "dvr9.1-2_09.jpg"),
                       ("2026-11-24", "dvr9.1-2_13.jpg"),
                       ("2026-11-24", "dvr9.1-10_13.jpg"),
                       ("2026-11-24", "notes.txt")):
            os.makedirs(os.path.join(pics, d_), exist_ok=True)
            open(os.path.join(pics, d_, f_), "wb").close()
        got = dd_.all_desk_pictures(pics)
        check("naming the desks: each desk's pictures, every day's, newest "
              "first", ([os.path.basename(p) for p in got["dvr9.1-2"]],
                        sorted(got)),
              (["dvr9.1-2_13.jpg", "dvr9.1-2_09.jpg", "dvr9.1-2_10.jpg"],
               ["dvr9.1-10", "dvr9.1-2"]))
        check("and when each was taken",
              dd_.picture_when(got["dvr9.1-2"][0]), "Tue 24 Nov, 13:00")
    finally:
        shutil.rmtree(pics)
    rooms_of = {"a.1-2": "R1", "a.1-10": "R1", "a.1-1": "R1", "b.2-1": "R2",
                "a.1-3": "R1"}
    seen = {c: ["x.jpg"] for c in ("a.1-2", "a.1-10", "a.1-1", "b.2-1")}
    hand = {"a.1-2": ("00001", "Some One")}
    check("it walks the desks with a picture, room by room, in desk order",
          dd_.naming_list(rooms_of, seen, {}, dd_.ALL_ROOMS, True),
          ["a.1-1", "a.1-2", "a.1-10", "b.2-1"])
    check("one room; a named desk left out until every desk is asked for",
          (dd_.naming_list(rooms_of, seen, hand, "R1", True),
           dd_.naming_list(rooms_of, seen, hand, "R1", False)),
          (["a.1-1", "a.1-10"], ["a.1-1", "a.1-2", "a.1-10"]))
    notes2 = pd.DataFrame([
        dict(time="10:00:00", recorder="dvr9", channel=1, cx=500, cy=600,
             w=100, h=200, score=.9, frame_w=1920, frame_h=1080,
             at=at("10:00"))])
    both_desks = [{"code": "A", "recorder": "dvr9", "channel": 1,
                   "seat": [500, 700]},
                  {"code": "B", "recorder": "dvr9", "channel": 1,
                   "seat": [540, 700]}]
    got = dd_.assign_notes(notes2, both_desks)
    check("Every desk too: one note counts at one desk only",
          (len(got["A"]), len(got["B"])), (1, 0))
    rs = dd_.room_summary(pd.DataFrame([
        dict(day=DAY, code=c, room="Test Room", first=at("10:00"),
             desk_min=300.0, desk_pct=0.6, focus_min=60.0,
             **{"h%02d" % h: (60.0 if h == 11 else 0.0)
                for h in range(8, 23)}) for c in ("A", "B")]), DAY)
    check("room by room: desks, sat at today, usual hours, the 11:00 hour "
          "full", (rs[0]["desks"], rs[0]["sat_today"], rs[0]["desk_h"],
                   rs[0]["hourly"][3]), (2, 2, 5.0, 1.0))
    back = pdx.from_payloads([("_desks", {"day": DAY, "rooms": rs})])[0]
    check("the hosted page reads it back", back["desks"]["rooms"][0]["room"],
          "Test Room")
    # 25 Nov: a desk named on the tab, then listed under a code -- the
    # desk's old row stayed in progress_days (the laptop may not delete),
    # and the employee was on the hosted page twice.
    from datetime import datetime as _dtm, timezone as _tz
    t_send = _dtm(2026, 11, 25, 3, 8, tzinfo=_tz.utc)
    t_old = _dtm(2026, 11, 24, 19, 20, tzinfo=_tz.utc)
    rows_ = [("_project", {"campus": "140-H"}, t_send),
             ("P13", {"code": "P13", "employee_id": "00042"}, t_send),
             ("nvr4.23-3", {"code": "nvr4.23-3", "employee_id": "00042"},
              t_old),
             ("_desks", {"day": DAY, "rooms": []}, t_old),
             ("P1", {"code": "P1", "employee_id": ""}, t_send)]
    got_ = pdx.from_payloads(rows_)
    check("a row the laptop stopped sending is left out; _desks stays",
          ([p["code"] for p in got_[1]], "desks" in got_[0]),
          (["P1", "P13"], True))
    twice = pdx.from_payloads([(c, d) for c, d, _ in rows_])
    check("and one employee is never shown twice: the listed code wins",
          [p["code"] for p in twice[1]], ["P1", "P13"])
    desks = [{"code": "dvr9.1-1", "recorder": "dvr9", "channel": 1,
              "seat": [500.0, 700.0]}]
    named = [{"recorder": "dvr9", "channel": "1", "x": "500", "y": "700",
              "status": "named", "employee_id": "09999",
              "name": "Test Person"}]
    key = ("dvr9", "1", "500", "700", "09999")
    check("a seat named by face is 'to confirm' until somebody says",
          dd.names_for(desks, [], named)["dvr9.1-1"][2],
          "by face, to confirm")
    check("a yes confirms it; a no takes the name away",
          (dd.names_for(desks, [], named, reviews={key: "yes"})["dvr9.1-1"][2],
           dd.names_for(desks, [], named, reviews={key: "no"})),
          ("by face, confirmed", {}))
    folder = tempfile.mkdtemp()
    try:
        path = os.path.join(folder, "r.csv")
        dd.save_review("dvr9", 1, 500, 700, "09999", "yes", path)
        dd.save_review("dvr9", 1, 500, 700, "09999", "no", path)
        check("the latest word on a seat stands", dd.load_reviews(path),
              {key: "no"})
    finally:
        shutil.rmtree(folder)
    check("the review is in the dashboard",
          "def show_seat_review" in open("rooms_dashboard.py",
                                         encoding="utf-8").read(), True)


def desks_data_names_gate():
    import desks_data as dd
    got = dd.names_for([{"code": "A", "recorder": "dvr2", "channel": 15,
                         "seat": [500, 700]}], [], [],
                       by_gate={"A": ("Test Person", "00010")})
    return got["A"][2]


def check_entrance():
    print("-- the turnstile: frontal faces only, one row a passage")
    import numpy as np
    import entrance_watch as ew

    def row(rx, lx, nx):
        r = np.zeros(15, np.float32)
        r[4], r[6], r[8] = rx, lx, nx
        return r
    check("a face straight on is compared; a profile, or a tiny one, not",
          (ew.frontal(row(100, 160, 131)), ew.frontal(row(100, 160, 175)),
           ew.frontal(row(100, 110, 105))), (True, False, False))

    def unit(*v):
        v = np.array(v + (0.0,) * (128 - len(v)), np.float32)
        return v / np.linalg.norm(v)
    ids = np.array(["00010", "00011"])
    photos = np.array([unit(1, 0, 0), unit(0, 1, 0)])
    recent = []
    got = ew.decide(unit(1, .1, 0), ids, photos, recent, 1000.0)
    check("a face clearly one photo's names its passer",
          (got[0], got[1]), ("named", "00010"))
    check("the same person a minute later is the same passage",
          ew.decide(unit(1, .1, 0), ids, photos, recent, 1060.0)[0], None)
    check("and two minutes later a new one",
          ew.decide(unit(1, .1, 0), ids, photos, recent, 1200.0)[0], "named")
    check("a face like neither photo is unknown, its best guess kept",
          ew.decide(unit(.7, .7, .3), ids, photos, [], 1300.0)[0], "unknown")
    folder = tempfile.mkdtemp()
    try:
        ew.write(DAY, ("10:22:51", "nvr1", 5, "named", "00010", "00010",
                       0.52, 0.16, 147), None, folder)
        got = pd.read_csv(os.path.join(folder, DAY + ".csv"), dtype=str)
        check("a passage is a row: time, camera, who, how sure",
              (got["employee_id"][0], got["channel"][0], got["score"][0]),
              ("00010", "5", "0.520"))
        # 25 Nov (the face study): two faces the same second with the same
        # label wrote one file name -- 17.5% of the pictures lost. And the
        # live numbers are kept beside each picture.
        pic = np.full((40, 40, 3), 128, np.uint8)
        det = np.arange(15, dtype=np.float32) * 100
        s1 = ew.write(DAY, ("10:22:52", "nvr1", 5, "unknown", "", "00010",
                            0.3, 0.0, 60), pic, folder,
                      face=(unit(1, 0, 0), det))
        s2 = ew.write(DAY, ("10:22:52", "nvr1", 5, "unknown", "", "00011",
                            0.3, 0.0, 60), pic, folder,
                      face=(unit(0, 1, 0), det))
        got = pd.read_csv(os.path.join(folder, DAY + ".csv"), dtype=str)
        check("two faces in one second: two pictures, each named in its row",
              (list(got["stem"]), sorted(os.listdir(os.path.join(folder,
                                                                 DAY)))),
              (["102251_ch05_00010", "102252_ch05_unknown",
                "102252-2_ch05_unknown"],
               ["102252-2_ch05_unknown.f16", "102252-2_ch05_unknown.jpg",
                "102252_ch05_unknown.f16", "102252_ch05_unknown.jpg"]))
        live = ew.live_face(DAY, s2, folder)
        check("the live numbers kept: the face's vector and YuNet's row",
              (s1 != s2, round(float(live[0] @ unit(0, 1, 0)), 3),
               float(live[1][3]), float(live[1][14])),
              (True, 1.0, 300.0, 1400.0))
        check("  none for a passage kept before them",
              ew.live_face(DAY, "102251_ch05_00010", folder), None)
        old = os.path.join(folder, "2026-11-20.csv")
        with open(old, "w") as fh:
            fh.write(ew.COLUMNS + "\n09:00:00,nvr1,5,unknown,,,0.3,0.0,60\n")
        ew.write("2026-11-20", ("09:00:01", "nvr1", 5, "unknown", "", "",
                                0.3, 0.0, 60), None, folder)
        check("a day's file begun before the stem keeps its nine columns",
              pd.read_csv(old, dtype=str).shape, (2, 9))
    finally:
        shutil.rmtree(folder)
    # 25 Nov: the gate's clock against the machines' -- the laptop ran
    # ~160 s ahead; a 45-s punch check needs it known, day by day
    import attendance as att
    gd = tempfile.mkdtemp()
    try:
        passed = [("13:02:40", "90001"), ("13:12:42", "90002"),
                  ("14:02:45", "90003"), ("17:02:38", "90004"),
                  ("18:02:41", "90005"), ("15:00:00", "90001"),
                  ("16:00:00", "90009")]
        with open(os.path.join(gd, DAY + ".csv"), "w") as fh:
            fh.write(ew.COLUMNS + "\n" + "".join(
                "%s,nvr1,5,named,%s,%s,0.6,0.2,60\n" % (t, e, e)
                for t, e in passed))
        outs = pd.DataFrame({
            "eid": ["90001", "90002", "90003", "90004", "90005"],
            "at": [pd.Timestamp(DAY + " " + t) for t in
                   ("13:00:00", "13:10:00", "14:00:00", "17:00:00",
                    "18:00:00")],
            "kind": "out", "place": "140-H OUT"})
        check("the gate's clock ahead of the machines', by its exits "
              "(the median; a passage far from any punch left out)",
              att.clock_offset(DAY, gd, data=outs), 161.0)
        check("  too few exits: not known",
              att.clock_offset(DAY, gd, data=outs.iloc[:3]), None)
    finally:
        shutil.rmtree(gd)
    check("Entry H only (the building door's camera sees backs)",
          ew.CAMERAS, [("nvr1", 5)])
    import gate_match as gm
    import entrance_backfill as eb
    check("the recording read in windows: lunch and evening, 50-min stretches",
          [(a.strftime("%H:%M"), b.strftime("%H:%M"))
           for a, b in eb.chunks(DAY, [("13:00", "14:30")])],
          [("13:00", "13:50"), ("13:50", "14:30")])
    p_ = passes_every("09:00", "14:00")
    sat_a = notes_at([t.strftime("%H:%M") for t in pd.date_range(
        at("10:01"), at("12:00"), freq="5min")], x=500)
    sat_b = notes_at([t.strftime("%H:%M") for t in pd.date_range(
        at("10:01"), at("12:40"), freq="5min")], x=900)
    both = pd.concat([sat_a, sat_b], ignore_index=True)
    desks_ = [{"code": "A", "recorder": "dvr2", "channel": 15,
               "seat": [500, 700]},
              {"code": "B", "recorder": "dvr2", "channel": 15,
               "seat": [900, 700]}]
    folder = tempfile.mkdtemp()
    try:
        for d in ("2026-11-19", DAY):
            with open(os.path.join(folder, d + ".csv"), "w") as fh:
                fh.write("time,recorder,channel,status,employee_id,best,"
                         "score,margin,face_w\n12:05:00,nvr1,5,named,00010,"
                         "00010,0.5,0.1,90\n")

        def shifted(day):
            k = pd.Timestamp(day) - pd.Timestamp(DAY)
            return both.assign(at=both["at"] + k)

        def passes_of(day):
            k = pd.Timestamp(day) - pd.Timestamp(DAY)
            return p_.assign(start=p_["start"] + k, end=p_["end"] + k)
        v = gm.votes(["2026-11-19", DAY], desks_, folder, shifted, passes_of)
        check("a passer at 12:05 votes for the desk left at 12:00, not the "
              "one still sat at", v, {"00010": {"A": 2.0}})
        check("two days of it give the desk; one person, one desk",
              gm.assign(v), [("00010", "A", 2.0, 0.0)])
        check("one passage alone gives nothing",
              gm.assign({"00010": {"A": 1.0}}), [])
    finally:
        shutil.rmtree(folder)
    check("a desk named by the gate is to be confirmed",
          desks_data_names_gate(), "by the gate, to confirm")
    source = open("room_loop.py", encoding="utf-8").read()
    check("the loop starts it, guarded, never on --once",
          "entrance_watch.start(recorders, build_url)" in source
          and "entrance_watch = None" in source
          and "not args.once" in source, True)


def check_cctv_faces():
    print("-- CCTV faces: a named person's face in our own cameras")
    import numpy as np
    import cctv_faces as cf
    import entrance_watch as ew
    import faces
    import progress_track as pt
    from datetime import datetime as _dt
    from types import SimpleNamespace as _NS
    # 24 Nov: the gate's straight-on faces join a known person's gallery,
    # only those named far above the line.
    gdir = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(gdir, "2026-11-24"))
        with open(os.path.join(gdir, "2026-11-24.csv"), "w") as fh:
            fh.write("time,recorder,channel,status,employee_id,best,score,"
                     "margin,face_w\n"
                     "13:03:47,nvr1,5,named,00042,,0.62,0.30,80\n"
                     "13:05:37,nvr1,5,named,00042,,0.52,0.11,70\n"
                     "13:06:00,nvr1,5,named,00099,,0.70,0.30,90\n")
        for n in ("130347_ch05_00042", "130537_ch05_00042",
                  "130600_ch05_00099"):
            open(os.path.join(gdir, "2026-11-24", n + ".jpg"), "wb").close()
        got = cf.gate_samples({"00042"}, ["2026-11-24"], gdir,
                              embed=lambda p: np.ones(128, np.float32))
        check("the gate's sure pictures of a known person join the gallery",
              {k: len(v) for k, v in got.items()}, {"00042": 1})
    finally:
        shutil.rmtree(gdir)
    gdir = tempfile.mkdtemp()
    try:
        ew.write("2026-11-26", ("13:03:47", "nvr1", 5, "named", "00042",
                                "00042", 0.62, 0.30, 80), None, gdir,
                 face=(np.eye(128, dtype=np.float32)[3], np.zeros(15)))
        got = cf.gate_samples({"00042"}, ["2026-11-26"], gdir,
                              embed=lambda p: np.ones(128, np.float32))
        check("  since 25 Nov, the passage's live numbers -- not its "
              "picture read again",
              (got["00042"].shape, int(np.argmax(got["00042"][0]))),
              ((1, 128), 3))
    finally:
        shutil.rmtree(gdir)
    # 24 Nov: the cafe, smoking, parking ... cameras the pass reads at
    # 640x360 are read at full size between batches, a few at a time.
    import face_sweep as fs
    rooms_ = [_NS(name="140-H Commons", cameras=[("nvr1", 18), ("nvr1", 21)],
                  stream=None),
              _NS(name="H Smoking Area", cameras=[("nvr1", 12)], stream=None),
              _NS(name="Basement", cameras=[("nvr4", 21)], stream="main"),
              _NS(name="Marketing", cameras=[("dvr2", 3)], stream=None),
              _NS(name="Outside H", cameras=[("nvr1", 27)], stream=None)]
    cams = [(r.name, k) for r, k in fs.cameras(rooms_)]
    check("where people go, at sub stream: the cafe and smoking twice a"
          " round; not a main-stream room, not an office",
          cams, [("140-H Commons", ("nvr1", 18)),
                 ("140-H Commons", ("nvr1", 21)),
                 ("H Smoking Area", ("nvr1", 12)),
                 ("Outside H", ("nvr1", 27)),
                 ("140-H Commons", ("nvr1", 18)),
                 ("140-H Commons", ("nvr1", 21)),
                 ("H Smoking Area", ("nvr1", 12))])
    grabbed, looked = [], []
    fs._state.update(at=0.0, i=0, slow=1.0)
    when = _dt(2026, 11, 24, 13, 0, tzinfo=pt.PKT)
    n1 = fs.step(rooms_, None, lambda r, k: grabbed.append(k) or 1,
                 lambda r, k, f: looked.append(k), now=when, clock=lambda: 100.0)
    n2 = fs.step(rooms_, None, lambda r, k: 1,
                 lambda r, k, f: looked.append(k), now=when, clock=lambda: 130.0)
    n3 = fs.step(rooms_, None, lambda r, k: 1,
                 lambda r, k, f: looked.append(k), now=when, clock=lambda: 161.0)
    check("three cameras a minute, the next three the minute after",
          (n1, n2, n3, looked[3:]), (3, 0, 3, [("nvr1", 27), ("nvr1", 18),
                                                ("nvr1", 21)]))
    check("and nothing out of office hours",
          fs.step(rooms_, None, lambda r, k: 1, lambda r, k, f: None,
                  now=_dt(2026, 11, 24, 23, 0, tzinfo=pt.PKT),
                  clock=lambda: 999.0), 0)
    fs.PASS_SIZE[("nvr1", 18)] = (360, 640)
    check("the pass's pixels per full-size pixel (640x360 in 2560x1440)",
          fs.scale_to(("nvr1", 18), np.zeros((1440, 2560, 3), np.uint8)),
          (0.25, 0.25))
    check("unknown until the pass has read the camera",
          fs.scale_to(("nvr1", 99), np.zeros((1440, 2560, 3), np.uint8)),
          None)

    def unit(*v):
        v = np.array(v + (0.0,) * (128 - len(v)), np.float32)
        return v / np.linalg.norm(v)
    desks = [{"code": "A", "recorder": "dvr9", "channel": 1,
              "seat": [500.0, 700.0]}]
    known = cf.known_desks({"A": ("00010", "Ann")}, desks,
                           [{"employee_id": "00011", "recorder": "dvr9",
                             "channel": 2, "seat": [300, 600]}],
                           [{"status": "named", "recorder": "dvr9",
                             "channel": "3", "x": "100", "y": "100",
                             "employee_id": "00012"}], reviews={})
    check("certain desks: by hand, the five with an ID -- not a seat named "
          "by face until confirmed", [k[0] for k in known],
          ["00010", "00011"])
    folder = tempfile.mkdtemp()
    try:
        base = os.path.join(folder, "seat_faces")
        os.makedirs(os.path.join(base, "2026-11-20"))
        np.array([unit(1, .02 * i, 0) for i in range(5)], np.float16) \
            .tofile(os.path.join(base, "2026-11-20", "dvr9_1_500_700.f16"))
        out = os.path.join(folder, "cctv.npz")
        per = cf.build(known, {"00011": np.array([unit(0, 1, 0)] * 4)},
                       out, base)
        check("the desk's kept faces become its sitter's gallery",
              sorted((k, len(v)) for k, v in per.items()),
              [("00010", 5), ("00011", 4)])
        ids, vecs = cf.load(out)
        check("a face like Ann's in our cameras is Ann's",
              cf.best(unit(1, .05, 0), ids, vecs)[0], "00010")
        check("a face between two people is nobody's",
              cf.best(unit(1, 1, 0), ids, vecs), None)
        photos = np.array([unit(0, 0, 1), unit(0, .2, 1)])
        got = ew.decide(unit(1, .05, 0), np.array(["00010", "00011"]),
                        photos, [], 1000.0, cctv=(ids, vecs))
        check("at the gate the CCTV gallery names somebody their photo "
              "would not", (got[0], got[1]), ("named", "00010"))
        old = faces.of_person, faces.available, cf._cache.copy()
        try:
            faces.of_person = lambda frame, box: unit(1, .05, 0)
            faces.available = lambda: True
            cf._cache.update(stamp=None)
            cf.OUT_SAVED = out
            frame = np.zeros((1080, 1920, 3), np.uint8)
            now = _dt(2026, 11, 20, 13, 0, tzinfo=pt.PKT)
            cf._seen.clear()
            orig_load = cf.load
            cf.load = lambda path=None: (ids, vecs)
            n = cf.observe("Prompt Cafe", ("nvr4", 14), frame,
                           [(900, 300, 1000, 600, .9), (450, 450, 550, 700)],
                           now=now, spots=[(500, 700)],
                           out=os.path.join(folder, "sightings"))
            got = pd.read_csv(os.path.join(folder, "sightings", DAY + ".csv"),
                              dtype=str)
            check("a named person off any seat (the cafe) is a sighting; "
                  "the one at a seat is left to seat_faces",
                  (n, got["employee_id"].tolist(), got["room"].tolist()),
                  (1, ["00010"], ["Prompt Cafe"]))
            # 26 Nov: a seat in an office is its owner's (seat_faces); a
            # cafe table is no desk -- whoever sits there is looked at.
            cf._seen.clear()
            seat_only = [(450, 450, 550, 700)]
            in_office = cf.observe("Test Room", ("dvr2", 15), frame,
                                   seat_only, now=now, spots=[(500, 700)],
                                   out=os.path.join(folder, "s2"))
            at_cafe = cf.observe("Prompt Cafe", ("nvr4", 14), frame,
                                 seat_only, now=now, spots=[(500, 700)],
                                 out=os.path.join(folder, "s2"))
            check("sitting at an office's regular seat is left out; at a "
                  "cafe table, named", (in_office, at_cafe), (0, 1))
            check("the same person on the same camera again soon is not "
                  "written twice", cf.observe(
                      "Prompt Cafe", ("nvr4", 14), frame,
                      [(900, 300, 1000, 600, .9)], now=now, spots=[],
                      out=os.path.join(folder, "sightings")), 0)
            cf.load = orig_load
        finally:
            faces.of_person, faces.available = old[0], old[1]
            cf._cache.clear()
            cf._cache.update(old[2])
    finally:
        shutil.rmtree(folder)
    source = open("room_loop.py", encoding="utf-8").read()
    check("the loop looks for named people everywhere, guarded",
          "cctv_faces.observe(room.name, key, wide, counted)" in source
          and "cctv_faces = None" in source, True)
    check("the galleries are rebuilt with every desk, hourly",
          "cctv_rebuild()" in open("desk_watch.py").read(), True)


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
    # 24 Nov: gone home, still shown in the office.
    check("19:20, twenty minutes away: still away",
          state("19:20")["state"], "away")
    # 24 Nov: the laptop slept 21:34-21:55; at 22:03 someone who left at
    # 19:00 was "away" again, the hole having started the stretch afresh.
    holed = pd.concat([passes_every("08:00", "21:30"),
                       passes_every("21:55", "22:05")], ignore_index=True)
    ah = pdx.day_activity(PERSON, DAY, rows=rows, notes=notes_at(seen),
                          passes=holed, reviews={})
    s = pdx.live(ah, at("22:03"), (10, 20))
    check("after a hole in the watching, gone is still gone",
          (s["state"], s["since"]), ("gone", at("19:00")))
    s = state("19:45")
    check("19:45, 45 min away after five, seen nowhere: probably gone home",
          (s["state"], s["label"], s["since"]),
          ("gone", "Probably gone home", at("19:00")))
    # The campus cameras' faces and the gate's (cctv_faces, entrance_watch)
    folder = tempfile.mkdtemp()
    try:
        with open(os.path.join(folder, DAY + ".csv"), "w") as fh:
            fh.write("time,employee_id,room,recorder,channel,score,margin\n"
                     "13:32:00,00042,Prompt Cafe,nvr4,14,0.55,0.25\n"
                     "13:40:00,00042,Marketing,dvr2,3,0.55,0.12\n"
                     "13:45:00,00042,Gaming Area,nvr4,12,0.45,0.30\n"
                     "13:50:00,00099,Prompt Cafe,nvr4,14,0.70,0.40\n")
        cc = pdx.cctv_rows(DAY, "00042", "P9", folder)
        check("a face far clear of the next is a place; near or faint is not",
              (len(cc), list(cc["room"]), list(cc["state"])),
              (1, ["Prompt Cafe"], ["face"]))
        with open(os.path.join(folder, DAY + ".csv"), "w") as fh:
            fh.write("time,recorder,channel,status,employee_id,best,score,"
                     "margin,face_w\n"
                     "13:07:00,nvr1,5,named,00042,,0.61,0.2,80\n"
                     "13:08:00,nvr1,5,unknown,,,0.3,0.0,60\n"
                     "19:10:00,nvr1,5,named,00042,,0.58,0.2,80\n")
        gr = pdx.gate_rows(DAY, "00042", "P9", folder)
        check("the gate: the named passages only",
              list(gr["time"]), ["13:07:00", "19:10:00"])
    finally:
        shutil.rmtree(folder)
    g = pdx.day_activity(PERSON, DAY, rows=rows, notes=notes_at(seen),
                         passes=p, reviews={}, extra=gr)
    check("out through the gate at 13:07: out of the building till the desk"
          " (55 min), and the 19:10 pass at the gate (5)",
          round(g["minutes"]["left"]), 60)
    s = pdx.live(g, at("13:30"), (10, 20))
    check("13:30: out of the building, through the gate at 13:07",
          (s["state"], s["label"], s["place"]),
          ("away", "Out of the building", "through the gate at 13:07"))
    s = pdx.live(g, at("19:30"), (10, 20))
    check("19:30: out through the gate at 19:10 after five: gone home",
          (s["state"], s["label"], s["since"]),
          ("gone", "Gone home", at("19:10:00")))
    g2 = pdx.day_activity(PERSON, DAY, rows=rows, notes=notes_at(seen),
                          passes=p, reviews={},
                          extra=pd.concat([gr, cc], ignore_index=True))
    check("seen in the cafe at 13:32: back inside, not out of the building",
          (round(g2["minutes"]["left"]), round(g2["minutes"]["cafe"]),
           round(g2["minutes"]["unseen"])), (30, 5, 30))
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
              (sent, len(cur.rows) >= 2, "_project" in [r[1] for r in
                                                       cur.rows]),
              (True, True, True))
        desks_rows = [r for r in cur.rows if r[1] == "_desks"]
        check("every desk goes room by room, with no desk code or name in it",
              all('"code"' not in r[2] and '"name"' not in r[2]
                  for r in desks_rows), True)
        check("the payload goes in twice: no EXCLUDED column is read (the "
              "camera machine may read only day and code)",
              ("EXCLUDED" in pt.UPSERT, cur.rows[0][2] == cur.rows[0][3]),
              (False, True))
        check("and one earlier day goes with it, for the day picker",
              len({r[0] for r in cur.rows}), 2)
        check("not again within five minutes",
              pt.publish(lambda: Conn(cur), clock=lambda: 1e9 + 60), False)
        # 24 Nov: an employee added to progress.yaml belongs on the days
        # already sent -- the fortnight goes again.
        first_past = sorted({r[0] for r in cur.rows})[0]
        again = Cur()
        pt._published.update(at=0.0, cfg="changed")
        pt.publish(lambda: Conn(again), clock=lambda: 1e9 + 400)
        check("progress.yaml changed: the past days are sent again",
              first_past in {r[0] for r in again.rows}, True)
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


def check_board():
    """The scoreboard (24 Nov): one line an employee, at the desk first,
    and no comparison with the usual before an hour in."""
    import progress_view as pv
    c = pv.colours("light")
    t = pd.Timestamp("2026-11-24 09:00")

    def person(code, state, desk, away, first=True):
        return {"code": code, "department": "Room",
                "live": {"state": state, "since": t},
                "focus": {"day": "2026-11-24",
                          "first_in": t if first else None,
                          "minutes": {"computer": desk, "unseen": away},
                          "estimate": {"computer": desk, "phone": 0.0,
                                       "talking": 0.0},
                          "read": 1, "slots": ["desk"] * 4},
                "history": [{"day": "2026-11-23", "first": t, "last": t,
                             "desk_pct": 0.5, "in_min": 480, "desk_min": 240}]}
    people = [person("P1", "away", 90, 30), person("P2", "desk", 100, 20),
              person("P3", "desk", 4, 0)]
    html = pv.today_board(people, c)
    check("one line an employee, the header besides", html.count(
        'class="pg-row '), 4)
    check("at the desk before away", html.index("Employee P2")
          < html.index("Employee P1"), True)
    check("four minutes in is not compared with the usual",
          "+50" not in html and "Employee P3" in html, True)
    check("two hours in is: 83% against a usual 50%", "+33" in html, True)
    check("somebody not in shows no desk time",
          pv.board_row(person("P4", "out", 5, 0, first=False), c)[0].count(
              "<b>--</b>") >= 2, True)
    # The gate (Entry H) names people on the way out: away, and named at
    # the gate after leaving the desk, is out of the building.
    gone = person("P5", "away", 100, 40)
    gone["gate"] = ["08:30:00", "09:20:00"]
    gone["live"].update(since=pd.Timestamp("2026-11-24 09:10"),
                        label="Out of the building",
                        place="through the gate at 09:20")   # live() says
    row = pv.board_row(gone, c)[0]
    check("away and named at the gate since: out of the building",
          "Out of the building" in row and "through the gate at 09:20" in row
          and "gate out 08:30" in row, True)
    gone["focus"]["minutes"].update(cafe=12.0, left=30.0, unseen=20.0)
    row = pv.board_row(gone, c)[0]
    check("and where they were away, in words",
          "away: cafe 12m &middot; out of the building 30m &middot; not seen"
          in row, True)
    # 24 Nov: one employee's report card -- today beside the usual, the
    # day place by place and from-to, and a usual day hour by hour.
    segs = pdx.segments([
        (t, t + pd.Timedelta(minutes=5), "computer", "Room"),
        (t + pd.Timedelta(minutes=5), t + pd.Timedelta(minutes=10),
         "computer", "Room"),
        (t + pd.Timedelta(minutes=10), t + pd.Timedelta(minutes=40), "cafe",
         "Prompt Cafe"),
        (t + pd.Timedelta(minutes=40), t + pd.Timedelta(minutes=60), "left",
         "out of the building")])
    check("the day's passes joined into runs, one kind in one place",
          [(s[2], round((s[1] - s[0]).total_seconds() / 60)) for s in segs],
          [("computer", 10), ("cafe", 30), ("left", 20)])
    card_p = person("P8", "away", 100, 40)
    card_p["focus"].update(
        segments=segs, minutes={"computer": 100.0, "cafe": 30.0,
                                "left": 10.0},
        stretches=[{"from": t, "to": t + pd.Timedelta(minutes=10),
                    "minutes": 10.0, "what": "desk",
                    "kinds": {"computer": 10.0}, "where": [], "seen": []},
                   {"from": t + pd.Timedelta(minutes=10),
                    "to": t + pd.Timedelta(minutes=40), "minutes": 30.0,
                    "what": "away", "kinds": {"cafe": 30.0},
                    "where": ["Prompt Cafe"], "seen": []},
                   {"from": t + pd.Timedelta(minutes=40),
                    "to": t + pd.Timedelta(minutes=43), "minutes": 3.0,
                    "what": "unwatched", "kinds": {}, "where": [],
                    "seen": []}])
    card_p["days"] = [{"day": d, "watched_min": 600, "first": t,
                       "desk_min": 300, "total_min": 300}
                      for d in ("2026-11-23", "2026-11-24")]
    card_p["slots"] = [["desk"] * 6 * 16, ["out"] * 6 + ["desk"] * 6]
    today_html = pv.report(card_p, c, pv.REPORT_VIEWS[0])
    check("the card: today beside the usual, each place a lane",
          all(x in today_html for x in (">Usual<", "Came in", "At the desk",
                                        "Cafe<em>", "Out of the building",
                                        "&nbsp;&nbsp;cafe")), True)
    check("from-to, oldest first, a short hole in the watching left out",
          (today_html.index("09:00&ndash;09:10")
           < today_html.index("Away: Prompt Cafe"),
           "Not watched" in today_html), (True, False))
    check("never says productive",
          "productive" in today_html.lower(), False)
    usual_html = pv.report(card_p, c, pv.REPORT_VIEWS[1])
    check("the usual day: hour by hour over the past days, today as dots"
          " only where they were in",
          ("over 1 working day" in usual_html,
           usual_html.count('title="today ')), (True, 1))
    top = pv.page("light", {"campus": "140-H"}, [card_p], "now", part="top")
    rest = pv.page("light", {"campus": "140-H"}, [card_p], "now",
                   part="rest")
    check("the page in two parts, the card between them",
          ("Today, employee by employee" in top, "Every day" in top,
           "Today, employee by employee" in rest), (True, False, False))
    # 25 Nov: a desk score -- time at the desk, long stretches, on time --
    # its parts shown, and where the day stands on the board.
    sp = {"code": "P8", "focus": {
        "day": "2026-11-24", "first_in": pd.Timestamp("2026-11-24 11:25"),
        "minutes": {"computer": 120.0},
        "stretches": [{"what": "desk", "minutes": 90.0},
                      {"what": "away", "minutes": 20.0},
                      {"what": "desk", "minutes": 30.0}]}}
    other = {"code": "P9", "focus": dict(sp["focus"],
                                         minutes={"computer": 300.0})}
    ds_ = pv.day_score(sp, 10.0, 20.0, None, [sp, other])
    check("desk score: 20% of the office day at the desk, 75% of it in long "
          "stretches, 25 min late past the grace (two quarters) -- 48.5, "
          "2nd of 2",
          ([round(v) for _, v, _, _ in ds_["parts"]], ds_["score"],
           ds_["rank"], ds_["of"]), ([20, 75, 80], 48.5, 2, 2))
    check("and on the card, never 'productive'",
          ("desk score" in pv.score_card(sp, pv.colours("light"), team=[sp]),
           "productive" in pv.score_card(sp, pv.colours("light")).lower()),
          (True, False))
    check("no score before they came in",
          pv.day_score({"focus": {"first_in": None}}), None)
    # 25 Nov: a day read again from the recordings (replay_day.py) -- only
    # the loop's gaps, notes in the loop's own format, passes of one camera.
    import replay_day as rd
    mo = rd.moments("2026-11-23", "12:00", "12:20", 5)
    check("replay: a moment every five minutes",
          [m.strftime("%H:%M") for m in mo],
          ["12:00", "12:05", "12:10", "12:15", "12:20"])
    loop_ends = [pd.Timestamp("2026-11-23 12:01"),
                 pd.Timestamp("2026-11-23 12:19")]
    check("replay: only the moments no loop pass came near (3 min)",
          [m.strftime("%H:%M") for m in rd.unwatched(mo, loop_ends)],
          ["12:05", "12:10", "12:15"])
    check("replay: the loop's seat-note row",
          rd.note_rows(mo[0], "Basement", ("nvr4", 23),
                       [(1160, 220, 1210, 290, 0.61)], (1080, 1920, 3)),
          [["12:00:00", "Basement", "nvr4", 23, "1185", "255", "50", "70",
            "0.61", 1920, 1080]])
    ps = pd.DataFrame({
        "start": pd.to_datetime(["2026-11-23 12:00", "2026-11-23 12:05",
                                 "2026-11-23 12:10"]),
        "end": pd.to_datetime(["2026-11-23 12:05", "2026-11-23 12:10",
                               "2026-11-23 12:15"]),
        "camera": ["nvr4:23", "nvr4:23", "dvr2:9"]})
    nt = pd.DataFrame([{"recorder": "nvr4", "channel": 23, "cx": 1185,
                        "cy": 250, "w": 40, "h": 72, "score": 0.6,
                        "frame_w": 1920,
                        "at": pd.Timestamp("2026-11-23 12:0%d" % m)}
                       for m in (3, 8)])
    a_line = pdx.timeline({"recorder": "nvr4", "channel": 23,
                           "seat": [1185, 286]}, nt, ps)
    b_line = pdx.timeline({"recorder": "dvr2", "channel": 9,
                           "seat": [500, 500]}, nt, ps)
    check("a replayed camera's passes are its own: its desk read in them, "
          "another camera's desk not called away in them",
          ([s for _, _, s in a_line], [s for _, _, s in b_line]),
          (["desk", "desk"], ["away"]))
    # 25 Nov: one desk seen by two cameras (also:): a note on either counts.
    nts = pd.DataFrame([
        {"recorder": "nvr4", "channel": 23, "cx": 1185, "cy": 250, "w": 40,
         "h": 72, "score": 0.6, "frame_w": 1920,
         "at": pd.Timestamp("2026-11-24 12:15")},
        {"recorder": "nvr4", "channel": 25, "cx": 890, "cy": 535, "w": 120,
         "h": 50, "score": 0.4, "frame_w": 1920,
         "at": pd.Timestamp("2026-11-24 13:30")},
        {"recorder": "nvr4", "channel": 25, "cx": 300, "cy": 535, "w": 120,
         "h": 50, "score": 0.9, "frame_w": 1920,
         "at": pd.Timestamp("2026-11-24 13:35")}])
    one = {"recorder": "nvr4", "channel": 23, "seat": [1185, 286]}
    both = dict(one, also=[["nvr4", 25, 890, 560]])
    check("a desk seen from two cameras: a note on either is the desk",
          (len(pdx.desk_notes(one, nts)), len(pdx.desk_notes(both, nts))),
          (1, 2))
    # 24 Nov: every desk named on the tab joins the board by itself; a
    # desk that is a listed employee's own seat, or their ID, does not.
    listed = [{"code": "P1", "employee_id": "00042", "recorder": "dvr2",
               "channel": 9, "seat": [1425, 993]}]
    hand = {"dvr2.9-1": ("00042", "Listed Already"),
            "dvr2.9-2": ("00077", "New Person"),
            "dvr2.9-5": ("00088", "Own Seat Of P1")}
    seats_ = {"dvr2.9-1": ("dvr2", 9, 1426.0, 997.0),
              "dvr2.9-2": ("dvr2", 9, 692.0, 1054.0),
              "dvr2.9-5": ("dvr2", 9, 1430.0, 1000.0)}
    got = pdx.desk_people(listed, hand, seats_, {"dvr2.9-2": "Admin Room"},
                          {"00077": {"designation": "Officer",
                                     "department": "Workplace Services"}})
    check("a named desk joins the board, its days by place, its activity"
          " from every desk's reading",
          [(g["code"], g["name"], g["department"], g["role"], g["since"],
            g["activity"]) for g in got],
          [("dvr2.9-2", "New Person", "Admin Room",
            "Officer, Workplace Services", pdx.DESK_SINCE, pdx.DESK_ACTIVITY)])
    check("a desk with no name says it is a desk",
          (pv.who({"code": "dvr2.9-3"}), pv.who({"code": "P4"})),
          ("Desk dvr2.9-3", "Employee P4"))
    home = person("P7", "gone", 300, 60)
    home["live"].update(label="Probably gone home",
                        since=pd.Timestamp("2026-11-24 17:40"))
    check("gone, said as likely as it is",
          "Probably gone home" in pv.board_row(home, c)[0], True)
    late = person("P6", "desk", 100, 20)
    # 27 Nov (Shamroze: the timing is flexible -- only in after 11:00 is
    # late)
    late["focus"]["first_in"] = pd.Timestamp("2026-11-24 11:10")
    check("in at 11:10 is late; 10:40 is not",
          "pg-late" in pv.board_row(late, c, start=10.0)[0]
          and "pg-late" not in pv.board_row(dict(late, focus=dict(
              late["focus"], first_in=pd.Timestamp("2026-11-24 10:40"))),
              c, start=10.0)[0], True)
    blinky = person("P7", "desk", 100, 20)
    blinky["focus"]["stretches"] = [
        {"what": "desk", "minutes": 50}, {"what": "away", "minutes": 4},
        {"what": "desk", "minutes": 30}, {"what": "away", "minutes": 25}]
    row = pv.board_row(blinky, c)[0]
    check("a break is ten minutes away or more; the longest sitting shown",
          "1 break<" in row.replace("1 break</small>", "1 break<")
          and "longest sitting 50m" in row, True)
    import tempfile
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "2026-11-24.csv"), "w") as fh:
        fh.write("time,recorder,channel,status,employee_id,best,score,"
                 "margin,face_w\n09:20:00,nvr1,5,named,00001,00001,0.6,0.2,"
                 "60\n09:30:00,nvr1,5,unknown,,00002,0.4,0.0,50\n")
    check("the gate's named passages, by employee ID; unknown faces left out",
          pdx.gate_passages("2026-11-24", tmp), {"00001": ["09:20:00"]})
    shutil.rmtree(tmp)


def check_presence_only():
    """25 Nov, Shamroze: the Basement's people only by where they are --
    at the desk, in the Basement off it, the cafe, the smoking area --
    never what they do at the desk."""
    print("-- presence only (the Basement)")
    base = dict(PERSON, department="Basement")
    check("a Basement desk is presence only; another room is not",
          (pdx.presence_only(base, {}), pdx.presence_only(PERSON, {})),
          (True, False))
    check("progress.yaml's list decides where it has one; a person's own "
          "word wins", (pdx.presence_only(PERSON, {"presence_only":
                                                   ["Test Room"]}),
                        pdx.presence_only(dict(base, presence_only=False), {}),
                        pdx.presence_only(base, {"presence_only": []})),
          (True, False, False))
    p = passes_every("10:00", "11:00")
    seen = notes_at(["10:01", "10:06", "10:11", "10:16"])
    rows = pd.DataFrame([{"time": "10:03:00", "code": "P9", "kind": "desk",
                          "state": "computer", "room": "Test Room",
                          "recorder": "dvr2", "channel": 15, "score": 1.0,
                          "at": at("10:03")}])
    watched = pdx.day_activity(dict(PERSON, presence_only=False), DAY,
                               rows=rows, notes=seen, passes=p, reviews={})
    only = pdx.day_activity(dict(PERSON, presence_only=True), DAY, rows=rows,
                            notes=seen, passes=p, reviews={})
    check("elsewhere the desk's activity is read; presence only it is not",
          (watched["read"] > 0, only["read"], round(only["minutes"]["desk"]),
           round(only["minutes"]["computer"])), (True, 0, 20, 0))
    c = pv.colours("light")
    t = at("10:00")
    card_p = {"code": "P9", "department": "Basement", "presence_only": True,
              "live": {"state": "away", "since": t},
              "focus": {"day": DAY, "first_in": t,
                        "minutes": {"desk": 60.0, "own room": 15.0,
                                    "smoking": 12.0, "cafe": 20.0},
                        "estimate": {"computer": 0.0, "phone": 0.0,
                                     "talking": 0.0}, "read": 0,
                        "segments": pdx.segments([
                            (t, t + pd.Timedelta(minutes=60), "desk",
                             "Basement"),
                            (t + pd.Timedelta(minutes=60),
                             t + pd.Timedelta(minutes=75), "own room",
                             "Basement"),
                            (t + pd.Timedelta(minutes=75),
                             t + pd.Timedelta(minutes=87), "smoking",
                             "Smoking Area"),
                            (t + pd.Timedelta(minutes=87),
                             t + pd.Timedelta(minutes=107), "cafe",
                             "Prompt Cafe")]),
                        "stretches": [
                            {"from": t, "to": t + pd.Timedelta(minutes=60),
                             "minutes": 60.0, "what": "desk",
                             "kinds": {"desk": 60.0}, "where": [],
                             "seen": []},
                            {"from": t + pd.Timedelta(minutes=60),
                             "to": t + pd.Timedelta(minutes=75),
                             "minutes": 15.0, "what": "away",
                             "kinds": {"own room": 15.0},
                             "where": ["Basement"], "seen": []}]},
              "history": []}
    html = pv.report(card_p, c, pv.REPORT_VIEWS[0])
    check("the card: no computer, phone or talking, and says why",
          ("at the computer" in html, "on the phone" in html,
           "activity not read" in html, "Presence only" in html),
          (False, False, False, True))
    check("  the Basement, the smoking area and the cafe each a lane",
          all(x in html for x in ("In the Basement, off the desk<em>",
                                  "Smoking area<em>", "Cafe<em>")), True)
    check("  and in the figures, the Basement by name",
          "in the Basement, off the desk" in html, True)
    check("  the board's line says the same", "away: in the Basement, off the "
          "desk" in pv.board_row(card_p, c)[0], True)
    check("a day nobody read is 'at the desk', never 'at the computer'",
          ("At the computer" in pv.day_block(card_p["focus"], c),
           "At the desk" in pv.day_block(card_p["focus"], c)), (False, True))
    # Followed less: once off the desk, only their own room, the cafe and
    # the smoking area (B has no smoking camera: the Basement and the cafe).
    import progress_follow as pf
    from datetime import datetime as _dt
    import progress_track as pt
    pf.reset()
    t0 = _dt(2026, 11, 20, 11, 0, 0, tzinfo=pt.PKT)
    try:
        pf.on_desk("P9", True, t0, "Basement", ("dvr9", 5))
        pf.on_desk("P9", False, t0 + pd.Timedelta(minutes=1), "Basement",
                   ("dvr9", 5))
        pf.on_desk("P9", False, t0 + pd.Timedelta(minutes=2), "Basement",
                   ("dvr9", 5))
        when = (t0 + pd.Timedelta(minutes=2)).timestamp()
        wide = [k for k, _ in pf.plan(when, B, CAMS, set(CAMS), count=6)]
        pf._state["P9"]["looked"] = {}
        narrow = [k for k, _ in pf.plan(when, B, CAMS, set(CAMS), count=6,
                                        narrow={"P9"})]
        check("followed less: the cafe only, not the stairs and lobby",
              (("dvr9", 3) in wide, narrow), (True, [("dvr9", 4)]))
    finally:
        pf.reset()
    for name, needle in (("desk_watch.py", "presence_rooms()"),
                         ("progress_track.py", "pdx.presence_only(p)")):
        check("%s reads no activity at a presence-only desk" % name,
              needle in open(name, encoding="utf-8").read(), True)


def check_attendance():
    """25 Nov: HR's export of the attendance machines -- first in, last
    out, time in the building, the outings; the Life app's hand-typed
    punches left out; an outing through the machine is out of the
    building."""
    print("-- the attendance machines")
    import attendance as att
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, "logs.csv"), "w") as fh:
            fh.write("id,machine_id,emp_code,date_time,machine_location,"
                     "status\n"
                     "1,CheckInManual,90042,%s 08:00:00,Life IN,0\n"
                     "2,M1,90042,%s 09:58:00,140-H IN,0\n"
                     "3,M2,90042,%s 11:00:00,140-H OUT,1\n"
                     "4,M1,90042,%s 11:01:00,140-H IN,0\n"
                     "5,M2,90042,%s 13:05:00,140-H OUT,1\n"
                     "6,M1,90042,%s 13:50:00,140-H IN,0\n"
                     "7,M3,90042,%s 15:00:00,141-D IN,0\n"
                     "8,M2,90042,%s 19:12:00,140-H OUT,1\n"
                     "8,M2,90042,%s 19:12:00,140-H OUT,1\n"
                     % ((DAY,) * 9))
        data = att.load(tmp)
        got = att.day("090042", DAY, data=data)
        check("first in, last out; the hand-typed punch and 141's left out",
              (got["first_in"], got["last_out"], got["punches"]),
              (at("09:58"), at("19:12"), 6))
        check("an outing longer than the turnstile's blip, once",
              [(a.strftime("%H:%M"), b.strftime("%H:%M"))
               for a, b in got["outings"]], [("13:05", "13:50")])
        check("time in the building: IN to OUT, each time",
              round(got["inside_min"]), 62 + 124 + 322)
        check("codes as the roster keeps them", (att.code("090001"),
                                                 att.code("90001")),
              ("90001", "90001"))
        check("nobody's punches, nothing", att.day("90002", DAY, data=data),
              None)
        summ = att.summary(data=data)
        check("every employee through the machines, the usual",
              [(s["eid"], s["days_in"], round(s["usual_in"], 2),
                round(s["inside_h"], 2), s["late"]) for s in summ],
              [("90042", 1, 9.97, 8.47, 0)])
        import attendance_view as av_
        roster_ = {"90042": {"employee_id": "90042", "name": "Some One",
                             "department": "Testing"}}
        page_u = av_.usual("light", summ, roster_)
        page_d = av_.one_day("light", summ, roster_, DAY)
        check("the usual table and one day's list",
              ("Some One" in page_u and "1 of 1" in page_u,
               "09:58" in page_d and "19:12" in page_d), (True, True))
        # 8.47 h of 10 (0.5 x 0.847), at their own usual hour (0.3), in on
        # the one working day (0.2): 92
        check("an attendance score for every employee, from the machines",
              (av_.score(summ[0]), "%%" in page_u,
               "<th>Attendance</th>" in page_u),
              (92, False, True))
        # A day that ends on an IN: its hours are not known -- not zero.
        open_ = dict(summ[0], inside_h=None, hours_days=0)
        check("no OUT to close a day: hours unknown, score from the rest",
              (att.day("90042", DAY, data=data)["closed"], av_.score(open_)),
              (True, 100))
        # 25 Nov: one score for everybody -- the desk's beside it where a
        # camera sees their named desk, half each; the CSV says the same.
        dk_ = {"90042": {"score": 70.0, "days": 4}}
        page_k = av_.usual("light", summ, roster_, desk=dk_)
        tab_ = av_.table(summ, roster_, dk_)
        check("overall: half attendance, half desk where the desk is seen",
              (av_.overall(92, None), av_.overall(92, 70),
               "Overall" in page_k, tab_[0]["Overall score"],
               tab_[0]["Desk score"],
               av_.table(summ, roster_)[0]["Overall score"]),
              (92, 81, True, 81, 70, 92))
        # The hosted page (25 Nov: "cloud pe add karte raho"): names only
        # where cloud_names allows; the numbers come back as they went.
        import json as _json
        import desks_data as dd_
        old_roster, old_load = dd_.load_roster, att.load
        try:
            dd_.load_roster = lambda *a, **k: [
                {"employee_id": "90042", "name": "Some One",
                 "designation": "Tester", "department": "Testing"}]
            att.load = lambda folder=None: data
            check("nothing for the hosted page without cloud_names",
                  pdx.attendance_payload({}), None)
            sent_ = pdx.attendance_payload({"cloud_names": True})
            back_ = pdx.from_payloads([
                ("_attendance", _json.loads(_json.dumps(
                    pdx._jsonable(sent_))))])[0]["attendance"]
            r0 = back_["rows"][0]
            check("  with it: name, ID, the usual, each day's in and out",
                  (r0["name"], r0["employee_id"], r0["days_in"],
                   r0["days"][DAY]["first_in"], back_["days"]),
                  ("Some One", "90042", 1, at("09:58"), [DAY]))
            # the directory photo's icon may go (cloud_names); a camera
            # picture -- a frame's path -- never
            check("  and never a camera picture in it",
                  ".jpg" in _json.dumps(pdx._jsonable(sent_)).lower()
                  or "frames" in _json.dumps(pdx._jsonable(sent_)).lower(),
                  False)
        finally:
            dd_.load_roster, att.load = old_roster, old_load
    finally:
        shutil.rmtree(tmp)
    p = passes_every("10:00", "11:00")
    seen = notes_at(["10:01", "10:06", "10:11", "10:16", "10:51", "10:56"])
    a = pdx.day_activity(dict(PERSON), DAY, rows=pd.DataFrame(), notes=seen,
                         passes=p, reviews={},
                         outside=[(at("10:22"), at("10:47"))])
    kinds = [k for _, _, k, _ in a["line"]]
    # passes 10:20-10:45 lie mostly inside 10:22-10:47; 10:45-10:50 not
    check("away inside an outing through the machine: out of the building",
          ("left" in kinds, round(a["minutes"]["left"])), (True, 25))
    c = pv.colours("light")
    card = {"code": "P9", "department": "Room", "focus": {
        "day": DAY, "first_in": at("10:00"), "minutes": {"desk": 60.0},
        "estimate": {}, "read": 0, "stretches": [],
        "attendance": {"first_in": at("09:58"), "last_out": at("19:12"),
                       "inside_min": 509.0, "punches": 6,
                       "outings": [(at("13:05"), at("13:50"))]}},
        "history": []}
    html = pv.report(card, c, pv.REPORT_VIEWS[0])
    check("the card: the machine's in and out, the outing",
          ("Machine: in &middot; out" in html, "09:58 &middot; 19:12" in html,
           "1 time, 45m" in html), (True, True, True))
    check("the export is never in git (people/)",
          "people/" in open(".gitignore").read(), True)
    # A desk named by the machines alone says so, on its card.
    listed_ = []
    got_ = pdx.desk_people(listed_, {"dvr9.1-1": ("90042", "Some One"),
                                     "dvr9.1-2": ("90043", "Other One")},
                           {"dvr9.1-1": ("dvr9", 1, 100.0, 100.0),
                            "dvr9.1-2": ("dvr9", 1, 400.0, 100.0)},
                           {"dvr9.1-1": "Room", "dvr9.1-2": "Room"}, {},
                           {"dvr9.1-1": "90042"})
    check("named by the machines, or by hand",
          [(g["code"], g["how"]) for g in got_],
          [("dvr9.1-1", "attendance"), ("dvr9.1-2", "by hand")])
    card_m = dict(card, code="dvr9.1-1", name="Some One", how="attendance")
    check("  and the card says it was not checked by eye",
          "not checked by eye" in pv.report(card_m, c, pv.REPORT_VIEWS[0]),
          True)
    # desk_match (25 Nov): a named desk checked against the machines.
    import desk_match as dm
    pdata = pd.DataFrame({"eid": ["90042"] * 2,
                          "at": [at("09:58"), at("13:05")],
                          "kind": ["in", "out"], "place": ["140-H IN",
                                                           "140-H OUT"]})
    line_ok = [(at("10:00"), at("12:00"), "desk")]
    line_bad = [(at("10:00"), at("11:00"), "desk"),
                (at("14:00"), at("17:00"), "desk")]
    ok_ = dm.check({DAY: line_ok}, "90042", data=pdata)
    bad_ = dm.check({DAY: line_bad}, "90042", data=pdata)
    check("the desk used while its person was inside: verified",
          (ok_["verdict"], round(ok_["share"], 2)), ("verified", 1.0))
    check("used mostly while they were out: doubt",
          (bad_["verdict"], round(bad_["share"], 2)), ("doubt", 0.25))
    check("nobody's punches: said so", dm.check({DAY: line_ok}, "90099",
                                                data=pdata)["verdict"],
          "no punches")
    zs = {"a": {"d1": (12.0, 20, 30), "d2": (3.0, 5, 30)},
          "b": {"d1": (9.0, 15, 30), "d3": (8.5, 14, 30)},
          "c": {"d4": (9.0, 4, 6)}}
    check("pairs: the strongest first, one desk each, clear of the next",
          [(e, d_) for e, d_, *_ in dm.pair(zs)], [("a", "d1")])
    # A pair refused once is never made again; a desk whose best person
    # already has a desk is theirs (a second view), never the next one's.
    zf_ = {"a": {"d1": (9.0, 12, 20)}, "b": {"d2": (9.0, 12, 20)},
           "c": {"d3": (9.0, 12, 20)}}
    za_ = dict(zf_, t={"d2": (11.0, 15, 20)})
    check("new names: not the refused pair, not a named person's second view",
          [(e, d_) for e, d_, *_ in dm.new_names(
              zf_, za_, taken={"t"}, no={("d1", "a")}, line=dm.STRONG)],
          [("c", "d3")])
    tmp_r = tempfile.mkdtemp()
    try:
        rej_ = os.path.join(tmp_r, "rejected.csv")
        drop_ = os.path.join(tmp_r, "dropped.csv")
        with open(rej_, "w", encoding="utf-8") as fh:
            fh.write("code,employee_id,why,at\n"
                     "dvr9.1-3,090042,wrong,2026-11-25 15:55:00\n")
        with open(drop_, "w", encoding="utf-8") as fh:
            fh.write("dvr9.1-4,90043,0.41\n")
        check("  refused: a review's no and a name taken back",
              dm.refused([rej_, drop_]),
              {("dvr9.1-3", "90042"), ("dvr9.1-4", "90043")})
    finally:
        shutil.rmtree(tmp_r)
    check("the words on the card",
          pv.machine_check_words({"share": 0.96, "verdict": "verified"}),
          "checked by the attendance machines: 96% of the desk's time while "
          "they were inside")
    loop_src = open("room_loop.py", encoding="utf-8").read()
    check("the loop starts the nightly check, guarded, in its own process",
          "desk_match_nightly(now)" in loop_src
          and '"desk_match.py", "--nightly"' in loop_src, True)
    import room_loop as rl_
    started = []
    st_ = {"day": None}
    from datetime import datetime as _dt2
    check("not before 23:30; once a night",
          (rl_.desk_match_nightly(_dt2(2026, 11, 25, 22, 0), st_,
                                  lambda: started.append(1)),
           rl_.desk_match_nightly(_dt2(2026, 11, 25, 23, 40), st_,
                                  lambda: started.append(1)),
           rl_.desk_match_nightly(_dt2(2026, 11, 25, 23, 55), st_,
                                  lambda: started.append(1)), len(started)),
          (None, "2026-11-25", None, 1))
    # The desk score over several days (25 Nov): long stretches per day,
    # each whole day scored as the card does, then averaged.
    T_ = pd.Timestamp
    line_ = [(T_(DAY + " 10:00"), T_(DAY + " 10:30"), "desk"),
             (T_(DAY + " 10:32"), T_(DAY + " 11:20"), "desk"),
             (T_(DAY + " 11:20"), T_(DAY + " 11:40"), "away"),
             (T_(DAY + " 11:40"), T_(DAY + " 12:10"), "desk")]
    check("long stretches: passes minutes apart are one, away ends one",
          pdx.long_runs(line_, T_(DAY + " 10:00"), T_(DAY + " 20:00")), 80.0)
    pp_ = {"days": [
        {"day": "2026-11-20", "first": T_("2026-11-20 10:00"),
         "desk_min": 300.0, "long_min": 240.0},
        {"day": "2026-11-21", "first": T_("2026-11-21 11:25"),
         "desk_min": 600.0, "long_min": 600.0},
        {"day": "2026-11-22", "first": None, "desk_min": 0.0}]}
    # 50x.5 + 80x.3 + 100x.2 = 69; 100x.5 + 100x.3 + 80x.2 = 96
    s1_ = pv.period_score(pp_)
    s2_ = pv.period_score(pp_, now=T_("2026-11-21 15:00"))
    check("desk score over the days; today only once the office day ends",
          (round(s1_["score"], 1), s1_["days"], round(s2_["score"], 1),
           s2_["days"], pv.period_score({"days": []})),
          (82.5, 2, 69.0, 1, None))
    # Productivity (25 Nov): attendance 40, desk 40, activity 20; a part
    # not measured gives its weight to the others.
    import productivity_view as prv
    hist_ = [{"desk_min": 300.0, "computer_min": 240.0, "phone_min": 15.0,
              "talking_min": 15.0},
             {"desk_min": 300.0, "computer_min": None}]
    a_ = prv.activity({"history": hist_})
    check("activity: computer 80% of desk time, phone+talk 10% -> 83",
          (round(a_["computer"]), round(a_["talk_phone"]), round(a_["score"]),
           a_["days"]), (80, 10, 83, 1))
    check("  a desk whose camera never sees a screen: not readable",
          prv.activity({"history": [{"desk_min": 300.0, "computer_min": 0.0,
                                     "phone_min": 0, "talking_min": 0}]}),
          None)
    check("productivity: all three, two, or the machines alone",
          (prv.productivity(60, 80, 90), prv.productivity(60, 80, None),
           prv.productivity(60, None, None), prv.productivity(None, None,
                                                              None)),
          (74, 70, 60, None))
    board_ = [dict(pp_, employee_id="090042", code="dvr9.1-1",
                   history=hist_, name="Some One", department="Room")]
    rows_ = [{"eid": "90042", "days_in": 2, "of": 2, "usual_in": 10.0,
              "usual_out": 19.0, "inside_h": 9.0, "outings": 0.0, "late": 0,
              "hours_days": 2, "days": {}},
             {"eid": "90043", "days_in": 1, "of": 2, "usual_in": 11.0,
              "usual_out": 18.0, "inside_h": None, "outings": 0.0, "late": 1,
              "hours_days": 0, "days": {}}]
    ros_ = {"90042": {"employee_id": "90042", "name": "Some One",
                      "department": "Testing"},
            "90043": {"employee_id": "90043", "name": "Other One",
                      "department": "Testing"}}
    em_ = prv.employees(rows_, ros_, board_)
    by_ = {e["eid"]: e for e in em_}
    check("every employee: the machines for all, the desk where seen",
          (len(em_), by_["90042"]["measured"], by_["90043"]["measured"],
           by_["90043"]["desk"]), (2, "desk camera + activity", "machines",
                                   None))
    # 140-H's own: most of their punches at its machines; a 141-D employee
    # passing through is a visitor, not on the list (25 Nov: 84 of 228)
    import attendance as att2
    vis_ = pd.DataFrame({
        "eid": ["90060"] * 2 + ["90061"] * 4,
        "at": [T_(DAY + " 10:00"), T_(DAY + " 19:00"), T_(DAY + " 12:00"),
               T_(DAY + " 12:30"), T_(DAY + " 09:00"), T_(DAY + " 18:00")],
        "kind": ["in", "out", "in", "out", "in", "out"],
        "place": ["140-H IN", "140-H OUT", "140-H IN", "140-H OUT",
                  "141-D IN", "141-D OUT"]})
    check("a campus's own employees; a visitor from another campus is not",
          ([r["eid"] for r in att2.summary(data=vis_,
                                           workdays=[DAY])],
           att2.visitors(data=vis_)), (["90060", "90061"], 0))
    vis2_ = pd.concat([vis_, pd.DataFrame({
        "eid": ["90061"] * 2, "at": [T_(DAY + " 20:00"), T_(DAY + " 21:00")],
        "kind": ["in", "out"], "place": ["141-D IN", "141-D OUT"]})])
    check("  4 of 6 punches at 141-D: a visitor at 140-H, left out",
          ([r["eid"] for r in att2.summary(data=vis2_, workdays=[DAY])],
           att2.visitors(data=vis2_)), (["90060"], 1))
    # the CEO (25 Nov): business units and departments; a profile each,
    # with their colleagues beside them
    for e_ in em_:
        e_["bu"] = "Unit A"
    by_bu_ = prv.group_rows(em_, "bu")
    prof_ = prv.profile_html("light", by_["90042"], em_)
    check("units and departments grouped; a profile with colleagues",
          ([n for n, _, _ in by_bu_], "with colleagues in Testing" in prof_,
           "1st" in prof_, "Other One" in prof_, "frames" in prof_),
          (["Unit A"], True, True, True, False))
    top_ = prv.summary_html("light", em_, ["2026-11-20", "2026-11-21"])
    tab2_ = prv.table_html("light", em_)
    check("  the page: figures, departments, the table, no camera picture",
          ("Productivity &middot; 140-H" in top_, "Other One" in tab2_,
           "frames" in top_ + tab2_, "%%" in top_ + tab2_),
          (True, True, False, False))
    # 25 Nov night (Shamroze: "chhota banao"): four figures, then a flash
    # card per department -- how many monitored, its productivity; opened,
    # its report card above only its people
    short_ = prv.top_html("light", em_, ["2026-11-20", "2026-11-21"],
                          visitors=2)
    cards_ = prv.dept_cards(em_)
    head_ = prv.dept_head_html("light", cards_[0][0], cards_[0][1], em_)
    avg_ = round(prv._mean([e["productivity"] for e in cards_[0][1]]))
    check("  short: four figures; a card per department, its count and "
          "productivity; opened, its report card",
          (short_.count('class="ec-card ec-kpi"'), "2 visitors" in short_,
           [n for n, _, _ in cards_] == [n for n, _, _ in
                                         prv.group_rows(em_, "dept")],
           "<b>%d</b> employee" % len(cards_[0][1]) in cards_[0][2],
           "<b>%d</b>" % avg_ in cards_[0][2],
           "Employees monitored" in head_, "%%" in short_ + head_,
           "frames" in short_ + head_ + "".join(h for _, _, h in cards_)),
          (4, True, True, True, True, True, False, False))
    dt_ = prv.dept_table_html("light", cards_[0][1])
    check("  its people in the page's colours: ranked, a dash where not "
          "measured, never 'None'",
          ('<td class="rk">1</td>' in dt_, "&ndash;" in dt_, "None" in dt_,
           "%%" in dt_, "frames" in dt_), (True, True, False, False, False))
    src_ = open("rooms_dashboard.py", encoding="utf-8").read()
    check("  the Progress tab one way in: Productivity, the rest behind a "
          "switch",
          ('st.toggle(PROGRESS_MORE, key="progress_more")' in src_,
           "PROGRESS_VIEWS" in src_), (True, False))


def check_report_card():
    """25 Nov night (Shamroze: "naya banda bhi samjhe"): department -> its
    people as cards -> a report card each -- against the team, strong and
    weak points, early signs, today so far; and what big companies learned:
    a long day is no credit, talk is often the work, teams of five+."""
    print("-- the report card")
    import attendance as att3
    import employee_report as er
    T = pd.Timestamp
    week = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19",
            "2026-11-20", "2026-11-24"]

    def hr(hhmm):
        h, m = hhmm.split(":")
        return int(h) + int(m) / 60.0

    def person(eid, i, o, p, dept="Testing", talking=5.0, last=None):
        days = {}
        for d in week:
            out_ = None if (d == week[-1] and last == "open") else o
            days[d] = {"first_in": T("%s %s" % (d, i)),
                       "last_out": T("%s %s" % (d, out_)) if out_ else None,
                       "inside_min": (hr(out_) - hr(i)) * 60 if out_ else 0.0,
                       "outings": [], "closed": bool(out_)}
        return {"eid": eid, "id": eid, "name": "Person %s" % eid,
                "role": "Engineer", "dept": dept, "bu": "Unit A", "photo": "",
                "days": days, "board": None, "attendance": p, "desk": None,
                "activity": None, "desk_parts": None, "desk_days": 0,
                "act": {"computer": 60.0, "phone": 3.0, "talking": talking,
                        "talk_phone": 3.0 + talking},
                "productivity": p, "days_in": len(week), "of": len(week),
                "usual_in": hr(i), "usual_out": hr(o),
                "hours": hr(o) - hr(i)}
    emps = er.prepare([person("1", "10:00", "19:00", 80, talking=30.0),
                       person("2", "10:05", "19:05", 78),
                       person("3", "09:55", "18:55", 79),
                       person("4", "10:10", "19:10", 77, last="open"),
                       person("5", "11:30", "19:30", 60),
                       person("6", "09:00", "20:30", 90, talking=0.0),
                       person("7", "10:00", "19:00", 75, dept="Solo")])
    by = {e["eid"]: e for e in emps}
    late_c = er.compare(by["5"], emps)
    strong5, weak5 = er.points(by["5"], late_c)
    late_w = [c for c in weak5 if c["key"] == "arrival"]
    check("a late comer: 'comes in late' a weak point, against their own "
          "team of six",
          (len(late_w), "Comes in late" in er.say(late_w[0], by["5"]),
           late_w[0]["team"], late_w[0]["n"]), (1, True, "Testing", 6))
    strong6, _ = er.points(by["6"], er.compare(by["6"], emps))
    check("  11.5 h a day is no strong point (a wellbeing sign, Microsoft) "
          "-- and saying little is no merit",
          ("hours" in [c["key"] for c in strong6],
           "talking" in [c["key"] for c in strong6],
           any("Long days" in t for _, t in er.signals(by["6"]))),
          (False, False, True))
    _, weak1 = er.points(by["1"], er.compare(by["1"], emps))
    check("  a lot of talk at the desk: worth a look, said as maybe work",
          [("may be work" in er.say(c, by["1"])) for c in weak1
           if c["key"] == "talking"], [True])
    check("  a team under five is compared with all of 140-H",
          er.compare(by["7"], emps)[0]["team"], "140-H")
    check("  a steady pattern says so",
          er.signals(by["2"]), [("good", "Steady: no warning sign in their "
                                 "pattern")])
    now_ = T("2026-11-24 21:00")
    t2, t4 = er.today(by["2"], now_), er.today(by["4"], now_)
    check("today so far: a day closed by its OUT is scored; an open one "
          "only says what is known",
          (t2["score"] is not None, ("Out", "19:05") in t2["facts"],
           t4["score"], ("Out", "not yet") in t4["facts"]),
          (True, True, None, True))
    cutp = person("8", "09:00", "19:00", 70)
    cutp["days"]["2026-11-25"] = {"first_in": T("2026-11-25 09:30"),
                                  "last_out": None, "inside_min": 0.0,
                                  "outings": [], "closed": False}
    check("  an export cut mid-day: its last day is known as cut short",
          er.cut_day([cutp]), "2026-11-25")
    page_ = er.report_html("light", by["5"], emps, now_, (10.0, 20.0),
                           "2026-11-24")
    cards_ = er.emp_card(by["5"], er.dept_avg(emps))
    check("  the card: points, signs, the team chart, the days; never "
          "'None', a camera picture or a stray %",
          ("Strong points" in page_, "Weak points" in page_,
           "factor by factor" in page_, "Their days" in page_,
           "Not measured here" in page_, "None" in page_ + cards_,
           "frames" in page_ + cards_, "%%" in page_ + cards_,
           "dept 77" in cards_),
          (True, True, True, True, True, False, False, False, True))
    # 26 Nov night (Shamroze): the overview first -- where a day went --
    # against a colleague ("X, Y se kyun behtar"), and the workforce apart
    import productivity_view as prv2
    al = er.allocation(by["2"], "2026-11-24")
    check("where a day went: in the building by the machines, nothing "
          "made up where no camera sees the desk",
          (round(al["in"]), al["desk"], er.shares(al)),
          (540, None, [("inside", 540.0)]))
    line_ = er.day_line(by["2"], "2026-11-24")
    check("  the day in one line, from first in to last out",
          [(round(a, 2), round(b, 2), k) for a, b, k, _ in line_],
          [(10.08, 19.08, "inside")])
    board_ = {"history": [{"day": "2026-11-24", "desk_min": 300.0,
                           "computer_min": 200.0, "phone_min": 10.0,
                           "talking_min": 20.0}],
              "places_days": {"2026-11-24": {"meeting": 45.0, "cafe": 30.0}}}
    al2 = er.allocation(dict(by["2"], board=board_), "2026-11-24")
    check("  with a desk camera and places: at the desk, the places, the "
          "rest of the building",
          er.shares(al2), [("desk", 300.0), ("meeting", 45.0), ("cafe", 30.0),
                           ("inside", 165.0)])
    # 26 Nov: the card opens on the newest whole day, never the export's
    # mid-day stub
    stub = dict(by["2"], _cut="2026-11-25",
                days=dict(by["2"].get("days") or {},
                          **{"2026-11-25": {"first_in": "10:41",
                                            "closed": False}}))
    opts_ = ["2026-11-25", "2026-11-24"]
    check("the report card opens on the last whole day, not a cut one",
          (er.default_day(stub, opts_), er.default_day(by["2"], opts_[1:]),
           er.default_day({}, ["2026-11-25"])), (1, 0, 0))
    # 26 Nov: the laptop's page takes the loop's board (built every five
    # minutes to publish) rather than a minute of its own
    import tempfile as _tf
    import time as _time
    _d = _tf.mkdtemp()
    try:
        bp = os.path.join(_d, "board.pkl")
        pdx.save_board([{"code": "P1"}], "2026-11-26", (10, 20), path=bp)
        got_ = pdx.latest_board("2026-11-26", (10.0, 20.0), path=bp)
        later_ = _time.time() + 3600
        rv = os.path.join(_d, "review.csv")
        open(rv, "w").close()
        os.utime(rv, (later_, later_))
        check("the loop's board is used when today's, same hours, fresh",
              (got_, pdx.latest_board("2026-11-25", (10, 20), path=bp),
               pdx.latest_board("2026-11-26", (9, 20), path=bp),
               pdx.latest_board("2026-11-26", (10, 20), path=bp,
                                now=later_),
               pdx.latest_board("2026-11-26", (10, 20), path=bp,
                                newer=[rv]),
               pdx.latest_board("2026-11-26", (10, 20),
                                path=os.path.join(_d, "none.pkl"))),
              ([{"code": "P1"}], None, None, None, None, None))
    finally:
        shutil.rmtree(_d)
    # 27 Nov (Shamroze: "141c/d me bh bnana shru krdo ... 140H ki tarah
    # dept wise"): 141-C/D's employees, by the machines, on their own page
    import json as _json
    import productivity_view as _pv
    _cfg = pdx.from_payloads([("_attendance_141", _json.dumps(
        {"rows": [{"eid": "7"}], "days": ["2026-11-24"]}))])[0]
    check("141-C/D's attendance comes back from the hosted rows on its own",
          (_cfg.get("attendance_by") or {}).get("141", {}).get("days"),
          ["2026-11-24"])
    _e = _pv.employees([{"eid": "7", "days_in": 1, "of": 1, "days": {},
                         "usual_in": 10.0, "usual_out": 19.0,
                         "inside_h": 9.0}], {"7": {"name": "A",
                                                   "department": "Ops"}},
                       campus="141-C/D")
    _top = _pv.top_html("light", _e, ["2026-11-24"], "now", 3, 0,
                        "141-C/D", "140-H")
    check("  its page says 141-C/D, its visitors from 140-H, no desk camera",
          ("Productivity &middot; 141-C/D" in _top,
           "from 140-H left out" in _top, "140-H&#x27;s" in _top,
           "none named here yet" in _top, _e[0]["campus"]),
          (True, True, False, True, "141-C/D"))
    # 27 Nov: Microsoft Viva's ways of working on the report card -- focus,
    # meetings, before/after office hours -- beside the team, not scored
    _w = {"eid": "9", "dept": "Ops", "_cut": None,
          "days": {"2026-11-24": {"first_in": pd.Timestamp(
                       "2026-11-24 09:00"), "last_out": pd.Timestamp(
                       "2026-11-24 21:30"), "closed": True}},
          "board": {"days": [{"first": 10.0, "long_min": 180.0},
                             {"first": 10.0, "long_min": 120.0}],
                    "places_days": {"2026-11-24": {"meeting": 60.0}}}}
    _w["days"]["2026-11-24"]["inside_min"] = 750.0
    ww = er.ways(_w, (10.0, 20.0))
    # (the timing is flexible, 24/7 -- Shamroze, 27 Nov: no "after office
    # hours"; the hours a week, whatever the clock)
    check("ways of working: focus 12.5 h, meetings 5 h, 62.5 h a week in "
          "the building", (round(ww["focus_h"], 1), round(ww["meeting_h"], 1),
                           round(ww["week_h"], 1)), (12.5, 5.0, 62.5))
    wh = er.ways_html(_w, [_w, dict(_w, eid="8", board=None)], (10.0, 20.0))
    check("  drawn beside the team, past 50 h counted, no after-hours, no "
          "None", ("Ways of working" in wh, "2 of 2" in wh,
                   "office hours" in wh, "None" in wh,
                   "no camera reads" in er.ways_html(dict(_w, board=None),
                                                     [_w])),
          (True, True, False, False, True))
    # 27 Nov (Shamroze: "review pdf tab bhejo jab tum confident na ho"):
    # a sure face names its desk by itself; a close one goes to the PDF
    import seat_faces as _sf
    _rows = [{"seat": "dvr2_9_500_700", "best": "00010", "score": .60,
              "second_score": .40, "samples": 20, "status": "named"},
             {"seat": "dvr2_9_900_700", "best": "00011", "score": .42,
              "second_score": .35, "samples": 12, "status": "unsure"},
             {"seat": "dvr2_9_100_700", "best": "00012", "score": .30,
              "second_score": .29, "samples": 12, "status": "unsure"},
             {"seat": "dvr2_9_300_700", "best": "00013", "score": .70,
              "second_score": .40, "samples": 30, "status": "named"}]
    _desks = [{"code": "dvr2.9-%d" % i, "recorder": "dvr2", "channel": 9,
               "seat": [x, 700]} for i, x in ((1, 505), (2, 890), (3, 100),
                                              (4, 300))]
    _sure, _doubt = _sf.name_plan(
        _rows, _sf.seat_desks(_rows, _desks), {"dvr2.9-4": ("13", "X")},
        {("dvr2.9-9", "10")}, {"00010", "00011", "00012", "00013"})
    check("faces: sure named by itself, close ones for the PDF, a named "
          "desk and a weak match left alone",
          ([s[:2] for s in _sure], [d[:2] for d in _doubt]),
          ([("dvr2.9-1", "00010")], [("dvr2.9-2", "00011")]))
    import desks_data as _dd
    check("  141-C/D's cameras are read for desks too; never the gym; its "
          "MR rooms are meetings",
          ("cd_nvr1" in _dd.CAMPUS and "nvr1" in _dd.CAMPUS,
           _dd.watched_room("141 Gym"), _dd.watched_room("141 Room 32"),
           pdx.place_of("141-D MR01 (2nd floor)"),
           pdx.place_of("141 MR 01 (1st floor)"),
           pdx.place_of("141 Corridor (2nd floor)"),
           pdx.place_of("141 Room 7 (ground floor)")),
          (True, False, True, "meeting", "meeting", "corridor", "office"))
    src_ = open("rooms_dashboard.py", encoding="utf-8").read()
    check("  each campus's page has only its own desks' people",
          "show_productivity(mode, ours(board)" in src_
          and "not_141(people)" in src_, True)
    check("  a Progress tab on 141-C/D behind the same door, the loop sends "
          "its rows", ('"141-C/D": ("141", "140-H")' in src_
                       and "campus in PROGRESS_CAMPUSES" in src_
                       and 'OTHER_CAMPUSES = ("141",)' in open(
                           "progress_track.py", encoding="utf-8").read()),
          True)
    check("  the page asks for it before building its own",
          "progress_data.latest_board(" in src_
          and "pdx.save_board(people, day, hours)"
          in open("progress_track.py", encoding="utf-8").read(), True)
    ov_ = er.overview_html(dict(by["2"], board=board_), "2026-11-24")
    check("  drawn: four figures, the bar by place, the line, no 'None'",
          ("Where the day went" in ov_, "Meeting rooms" in ov_,
           "ov-line" in ov_, "None" in ov_), (True, True, True, False))
    rows_, gap_ = er.pair(by["6"], by["5"])
    vs_ = er.pair_html(by["6"], by["5"])
    check("one against another: the factors both have, who is better (a "
          "day past 10.5 h is no credit), and what makes the gap",
          ([r[0] for r in rows_ if r[3] == "a"][:2], bool(gap_),
           "30 points</b> ahead" in vs_,
           "comes in 2 h 30 min earlier" in vs_, "is no credit" in vs_),
          (["arrival", "talking"], True, True, True, True))
    check("  the team's usual stands in for a colleague",
          er.team_usual(by["5"], emps)["name"], "Testing's usual")
    wl_ = er.workload(emps)
    check("the campus's workload: past 10.5 h a day long, 8 h of a 9 h team "
          "still healthy",
          (sorted(x["eid"] for x in wl_["long"]),
           sorted(x["eid"] for x in wl_["low"]), len(wl_["healthy"]),
           "Long days" in er.workload_html(emps)), (["6"], [], 6, True))
    strip_ = er.dept_strip_html(emps)
    check("  a department's day at a glance: a dot a person, the long day "
          "marked on the strip and on the card",
          ("dstrip" in strip_, strip_.count('<i style="left:'),
           "long days 1" in strip_,
           er.emp_card(by["6"], 77.0, "long").count("long days"),
           "long days" in er.emp_card(by["2"], 77.0, "healthy")),
          (True, 7, True, 1, False))
    check("workforce staff by their designation, each kind with its own",
          (prv2.crew_group("Janitorial"), prv2.crew_group("Office Boy"),
           prv2.crew_group("Gate Keeper"), prv2.crew_group("Senior Engineer")),
          ("Janitorial", "Office boys", "Gate and security", None))
    crew_ = er.prepare([dict(person("9", "09:00", "18:00", 70),
                             staff="workforce", dept="Janitorial",
                             role="Janitorial")])
    check("  their card: a workforce score beside their group's, never "
          "'productivity'",
          ("workforce score" in er.emp_card(crew_[0], 70.0),
           "group 70" in er.emp_card(crew_[0], 70.0),
           "Workforce staff" in er.crew_card(crew_)), (True, True, True))
    # 26 Nov 08:19 (Shamroze, the hosted page): Progress stopped with a
    # TypeError -- Streamlit Cloud ran the new script against the old,
    # still-loaded modules. fresh_modules lets a changed module go.
    import ast
    import json as json_
    import time as time_
    import types
    import progress_data as pdx2
    src = open("rooms_dashboard.py", encoding="utf-8").read()
    fns = {n.name: ast.get_source_segment(src, n)
           for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    tmp = tempfile.mkdtemp()
    try:
        ns = {"os": os, "sys": sys,
              "SELF": os.path.join(tmp, "rooms_dashboard.py")}
        exec(fns["_fresh_modules"], ns)
        for n_ in ("app_a.py", "app_b.py", "rooms_dashboard.py"):
            open(os.path.join(tmp, n_), "w").close()

        def loaded():
            mods_ = {}
            for n_ in ("app_a", "app_b", "rooms_dashboard"):
                m_ = types.ModuleType(n_)
                m_.__file__ = os.path.join(tmp, n_ + ".py")
                mods_[n_] = m_
            other = types.ModuleType("pandas_like")
            other.__file__ = os.path.join(os.path.dirname(tmp), "x", "y.py")
            mods_["pandas_like"] = other
            return mods_
        state = {}
        mods = loaded()
        first = ns["_fresh_modules"](tmp, mods, state)
        mods = loaded()                         # read again by the page
        same = ns["_fresh_modules"](tmp, mods, state)
        os.utime(os.path.join(tmp, "app_b.py"),
                 (time_.time() + 60, time_.time() + 60))
        after = ns["_fresh_modules"](tmp, mods, state)
        check("the app's modules read again when any of its files changed "
              "-- all of them together, and on a process's first run; "
              "nothing when nothing changed; never the page or a library",
              (first, same, after, "pandas_like" in mods,
               "rooms_dashboard" in mods),
              (["app_a", "app_b"], [], ["app_a", "app_b"], True, True))
    finally:
        shutil.rmtree(tmp)
    shown = []
    ns2 = {"os": os, "sys": sys, "SELF": os.path.abspath(
        "rooms_dashboard.py"),
           "st": types.SimpleNamespace(warning=lambda t, icon=None:
                                       shown.append(t))}
    exec(fns["guarded"], ns2)
    import io as io_
    err_, sys.stderr = sys.stderr, io_.StringIO()
    try:
        got_ = ns2["guarded"]("Productivity", lambda: None + 1)
    finally:
        sys.stderr = err_
    check("  a part that fails says so in one line -- its kind of error, "
          "never a value -- and the page carries on",
          (got_, len(shown), "Productivity could not be drawn" in shown[0],
           "TypeError" in shown[0]), (None, 1, True, True))
    check("  and the page does it before importing its own modules, with no "
          "list to forget; each part of Progress drawn on its own",
          (src.index("\n_fresh_modules()") < src.index("\nimport overview"),
           "order = (" in fns["_fresh_modules"],
           'guarded("Productivity", show_productivity_sent' in src,
           'guarded("Productivity", show_productivity,' in src),
          (True, False, True, True))
    # the hosted page's own path: what the laptop sends, through JSON and
    # back (timestamps as text, tuples as lists), drawn part by part
    day_ = "2026-11-24"
    att_row = {"eid": "1", "days": by["2"]["days"], "days_in": 6, "of": 6,
               "usual_in": 10.08, "usual_out": 19.08, "inside_h": 9.0,
               "late": 0, "outings": 0.0, "name": "Person 1",
               "employee_id": "1", "designation": "Engineer",
               "department": "Testing", "project": "Unit A", "photo": ""}
    crew_row = dict(att_row, eid="2", employee_id="2",
                    designation="Office Boy", name="Person 2")
    board_p = {"code": "P9", "employee_id": "1", "name": "Person 1",
               "days": [{"day": day_, "first": T(day_ + " 10:10"),
                         "desk_min": 300.0, "long_min": 200.0,
                         "watched_min": 540.0}],
               "history": [{"day": day_, "first": T(day_ + " 10:10"),
                            "last": T(day_ + " 19:00"), "desk_min": 300.0,
                            "computer_min": 200.0, "phone_min": 10.0,
                            "talking_min": 20.0}],
               "places": {"day": day_, "segments": [
                   (T(day_ + " 10:10"), T(day_ + " 13:00"), "desk", "", "desk"),
                   (T(day_ + " 13:00"), T(day_ + " 13:40"), "cafe",
                    "Prompt Cafe", "face")],
                   "totals": {"desk": 170.0, "cafe": 40.0}},
               "places_days": {day_: {"desk": 170.0, "cafe": 40.0}}}
    back = pdx2._restore(json_.loads(json_.dumps(pdx2._jsonable(
        {"rows": [att_row, crew_row], "people": [board_p]}))))
    ros_ = {r["eid"]: {"name": r["name"], "employee_id": r["employee_id"],
                       "designation": r["designation"],
                       "department": r["department"],
                       "project": r["project"], "photo": ""}
            for r in back["rows"]}
    ems = prv2.employees(back["rows"], ros_, back["people"], (10.0, 20.0),
                         T(day_ + " 21:00"))
    off_ = er.prepare([x for x in ems if x.get("staff") != "workforce"])
    cr_ = er.prepare([x for x in ems if x.get("staff") == "workforce"])
    page2 = "".join([
        prv2.top_html("light", off_, [day_], "now", 0, len(cr_)),
        er.workload_html(off_), er.crew_card(cr_),
        er.crew_head("light", cr_)] + [
        er.dept_head("light", n_, es_, off_)
        for n_, es_, _ in prv2.dept_cards(off_)] + [
        er.report_html("light", x, pool_, T(day_ + " 21:00"), (10.0, 20.0),
                       day_, crew=pool_ is cr_)
        for pool_ in (off_, cr_) for x in pool_])
    check("the hosted page's path -- through JSON and back -- draws every "
          "part, the day's places in the line",
          (len(off_), len(cr_), "Cafe and pantry" in page2, "None" in page2),
          (1, 1, True, False))
    # the machines' export cut at 12:21 (25 Nov): nobody absent that day
    raw = pd.DataFrame({
        "eid": ["90070"] * 3,
        "at": [T("2026-11-24 10:00"), T("2026-11-24 19:00"),
               T("2026-11-25 12:21")],
        "kind": ["in", "out", "in"], "place": ["140-H IN", "140-H OUT",
                                               "140-H IN"]})
    s_ = att3.summary(data=raw)
    check("  HR's export cut at 12:21: that day shown, never counted",
          (att3.cut_short(raw), s_[0]["of"], s_[0]["days_in"],
           "2026-11-25" in s_[0]["days"]), ("2026-11-25", 1, 1, True))


def main():
    check_report_card()
    check_attendance()
    check_presence_only()
    check_board()
    check_faces()
    check_building()
    check_follow()
    check_route_and_map()
    check_twin()
    check_night()
    check_stretches()
    check_average()
    check_cases()
    check_campus_faces()
    check_every_desk()
    check_entrance()
    check_cctv_faces()
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
