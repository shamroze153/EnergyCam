"""Check desks against people: the seating sheet's counts and the cameras'.

    python test_seating.py
"""
import io
import os
import sys
import tempfile

import import_seating
import seating

FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def day(people_by_hour, watched=range(0, 24)):
    """1440 minutes: people_by_hour {hour: n}, unwatched outside `watched`."""
    out = []
    for h in range(24):
        for _ in range(60):
            out.append(people_by_hour.get(h, 0) if h in watched else None)
    return out


def main():
    # ---- the file itself: counts only, and it reads back -----------------
    data = seating.load()
    names = " ".join(s["name"] for s in data["spaces"])
    check("seating.yaml loads, with desks", len(data["spaces"]) > 0, True)
    check("the sheet's 701 desks are all there",
          sum(s["seats"] for s in data["spaces"]), 701)
    check("  399 of them given to somebody on the sheet",
          sum((s["sheet"] or s)["allocated"] for s in data["spaces"]), 399)
    dc = [s for s in data["spaces"] if "Data centre" in s["name"]]
    check("141-D's data centre: no desk given, whatever the sheet says"
          " (Shamroze, 13 Nov)",
          (dc[0]["allocated"], dc[0]["free"], dc[0]["teams"],
           dc[0]["sheet"]["allocated"]), (0, 13, {}, 10))
    check("  so 389 given once corrected",
          sum(s["allocated"] for s in data["spaces"]), 389)
    check("given never exceeds desks", all(
        s["allocated"] <= s["seats"] for s in data["spaces"]), True)
    text = open(seating.PATH, encoding="utf-8").read()
    # The sheet's columns that hold people never appear in the file.
    check("no name or employee-code column in seating.yaml",
          any(w in text for w in ("Emp Name", "Emp Code", "emp_name")), False)
    check("no space is named after a person: every name is a room",
          all(any(k in s["name"] for k in ("Room", "room", "desks", "R1",
                                           "R2", "AutoOS", "Marketing",
                                           "Wellows", "Squat", "Store",
                                           "Assembly", "Data Centre"))
              for s in data["spaces"]), True)
    import yaml
    rooms = {r["name"] for r in yaml.safe_load(
        open(os.path.join(os.path.dirname(seating.PATH), "rooms.yaml"),
             encoding="utf-8"))["rooms"]}
    missing = [r for s in data["spaces"] for r in s["rooms"]
               if r not in rooms]
    check("every camera room named in seating.yaml is in rooms.yaml",
          missing, [])
    again = seating.load(_write(seating.dump(data)))
    check("dump then load gives the same spaces",
          again["spaces"] == data["spaces"], True)
    check("  and keeps the date", str(again["as_of"]), str(data["as_of"]))
    check("Squat Wolf's five cameras share its desks",
          [len(s["rooms"]) for s in data["spaces"]
           if s["name"].startswith("Squat Wolf")], [5])
    del names

    # ---- the import: names never read, codes keep their camera rooms -----
    sheet = ("No,location,Campus Code,Floor Tag,Room No. Tag,Work Station Tag,"
             "Emp Name,Emp Code,Type of Employee,Room Code,Room Code - "
             "Dashboard,Seat Code,BU,Department,Category,Status\n"
             "1,140 H,C1,First,R17,W1,Somebody One,11,Permanent,C1-FF-R17,"
             "First Floor-Room 17,C1-FF-R17-W1,Disrupt Labs,,Allocated,"
             "Occupied\n"
             "2,140 H,C1,First,R17,W2,Vacant,,,C1-FF-R17,First Floor-Room 17,"
             "C1-FF-R17-W2,Unassigned,,Unallocated,Vacant\n"
             "3,141 D,C2,Third,R40,W1,Somebody Two,12,Permanent,C2-TF-R40,"
             "Third Floor-Room 40,C2-TF-R40-W1,PureSquare,,Allocated,"
             "Occupied\n")
    import csv
    found = import_seating.counts(csv.DictReader(io.StringIO(sheet)))
    check("the import counts desks per room code",
          {k: v["seats"] for k, v in found.items()},
          {"C1-FF-R17": 2, "C2-TF-R40": 1})
    check("  allocated and in use from Category and Status",
          (found["C1-FF-R17"]["allocated"], found["C1-FF-R17"]["in_use"]),
          (1, 1))
    check("  teams leave out Unassigned",
          found["C1-FF-R17"]["teams"], {"Disrupt Labs": 1})
    check("  and nothing it keeps holds a name",
          "Somebody" in repr(found), False)
    fresh = import_seating.refresh(
        {"as_of": "x", "source": "y", "spaces": [dict(
            seating.load()["spaces"][0], name="Room 17",
            codes=["C1-FF-R17"], rooms=["Room 17"])]}, found)
    check("a known code keeps its camera room and takes the new count",
          (fresh["spaces"][0]["rooms"], fresh["spaces"][0]["seats"]),
          (["Room 17"], 2))
    check("a new code comes in with no camera, named from the sheet",
          (fresh["spaces"][1]["name"], fresh["spaces"][1]["rooms"],
           fresh["spaces"][1]["floor"], fresh["spaces"][1]["building"]),
          ("141-D Third Floor-Room 40", [], "Third floor", "141-D"))
    check("  and the written file has no name in it",
          "Somebody" in seating.dump(fresh), False)
    fixed = dict(seating.load()["spaces"][0], name="Room 17",
                 codes=["C1-FF-R17"], rooms=["Room 17"],
                 override={"allocated": 0}, sheet={"allocated": 99})
    again = import_seating.refresh({"as_of": "x", "source": "y",
                                    "spaces": [fixed]}, found)
    back = seating.load(_write(seating.dump(again)))["spaces"][0]
    check("a refresh writes the sheet's new count and keeps the correction",
          (back["sheet"]["allocated"], back["allocated"], back["seats"]),
          (1, 0, 2))

    # ---- minutes into figures --------------------------------------------
    check("two cameras' minutes add up",
          seating.combined([[1, None, 2], [3, None, None]]), [4, None, 2])
    check("a spike of a few minutes is not the busiest moment",
          seating.held_peak([2] * 30 + [9] * 3 + [2] * 30), 2)
    check("ten minutes running is",
          seating.held_peak([2] * 30 + [9] * 12 + [2] * 30), 9)
    busy = day({10: 4, 11: 8, 12: 8, 13: 6, 14: 8, 15: 4})
    f = seating.day_figures(busy, (10.0, 20.0))
    check("a day's busiest moment in office hours", f["peak"], 8)
    check("  its average over the office day",
          round(f["mean"], 2), round((4 + 8 + 8 + 6 + 8 + 4) / 10.0, 2))
    check("  and the share of it anybody was in", round(f["busy"], 2), 0.6)
    check("a day mostly unwatched does not count",
          seating.day_figures(day({11: 5}, watched=range(10, 13)),
                              (10.0, 20.0)), None)
    check("today so far: the office day ends now",
          seating.day_figures(day({11: 5}, watched=range(0, 14)),
                              (10.0, 14.0))["peak"], 5)
    s = seating.summary([{"peak": 4, "mean": 2, "busy": .5},
                         {"peak": 10, "mean": 4, "busy": .7},
                         {"peak": 6, "mean": 3, "busy": .6}, None])
    check("usual busiest is the median day's, highest kept apart",
          (s["days"], s["peak"], s["top"], s["mean"]), (3, 6, 10, 3))
    check("nobody in any day watched",
          seating.verdict({"days": 4, "peak": 0, "top": 0, "mean": 0}, 10),
          ("empty", "nobody seen in 4 days"))
    check("under a quarter of the desks at the busiest: hardly used",
          seating.verdict({"days": 3, "peak": 4, "top": 5, "mean": 2},
                          47)[0], "low")
    check("half full or more: well used",
          seating.verdict({"days": 3, "peak": 9, "top": 9, "mean": 3},
                          16)[0], "good")
    check("more people than desks says so",
          seating.verdict({"days": 3, "peak": 12, "top": 12, "mean": 8},
                          10)[0], "over")
    check("no camera figures yet", seating.verdict(None, 10)[0],
          "unwatched")
    check("hour by hour, office hours only",
          seating.hourly(busy, (10.0, 13.0)), [4.0, 8.0, 8.0])
    check("  an hour mostly unwatched is unknown",
          seating.hourly(day({10: 3}, watched=range(10, 11)), (10.0, 12.0)),
          [3.0, None])

    # ---- the page ----------------------------------------------------------
    c = {"text": "#000", "muted": "#555", "faint": "#999", "line": "#ddd",
         "surface": "#fff", "track": "#eee", "track_dark": "#ccc",
         "given": "#ccc", "peak": "#9ec5f4", "mean": "#2a78d6",
         "unwatched": "#f0efec", "cell_ink": ["#000"] * 3 + ["#fff"] * 3,
         "tones": {k: ("#eee", "#333") for k in (
             "empty", "low", "half", "good", "over", "unwatched")}}
    items = [dict(sp, summary=None, verdict=("unwatched", "not watched yet"),
                  now=None, ac="") for sp in data["spaces"]
             if sp["campus"] == "140-H"]
    items[0]["summary"] = {"days": 3, "peak": 4, "top": 5, "mean": 2.5,
                           "busy": .5}
    items[0]["verdict"] = ("low", "hardly used")
    items[0]["now"] = 3
    html = seating.page(
        [("140-H", items, [("Thu 12", 237, [10, 30, None]),
                           ("Today", 237, [20])],
          {"days": 3, "peak": 58, "top": 60, "mean": 40, "busy": .8})],
        c, seating.RAMP_LIGHT, (10.0, 13.0), "2026-11-13", "sheet", 3)
    check("the page draws the campus", "140-H" in html, True)
    check("  with its desks and how many are given",
          "desks given to somebody" in html, True)
    check("  the hours, with a key", "not watched" in html
          and "50%+" in html, True)
    check("the shade runs from the ramp's first step to its last",
          (seating.shade(0, seating.RAMP_LIGHT),
           seating.shade(0.9, seating.RAMP_LIGHT)),
          (seating.RAMP_LIGHT[0], seating.RAMP_LIGHT[-1]))
    check("  blending between steps",
          seating.shade(0.1, ["#000000", "#ffffff"]), "#333333")
    check("  today's later hours blank, not 'not watched'",
          html.count("Today") >= 1 and "<td></td>" in html, True)
    check("  the desks no camera sees, behind a click",
          "no camera sees yet" in html, True)
    check("  and the emptiest room's numbers",
          "usually <b>4</b> at once" in html, True)
    check("style is one line (markdown breaks on a newline in <style>)",
          "\n" in seating.CSS, False)

    print("\n%s" % ("all checks passed" if not FAILURES
                    else "%d FAILED" % len(FAILURES)))
    return 1 if FAILURES else 0


def _write(text):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


if __name__ == "__main__":
    sys.exit(main())
