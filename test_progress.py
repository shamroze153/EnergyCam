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


def main():
    check_timeline()
    check_day()
    check_passes_and_usual()
    check_page()
    check_kept_local()
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
