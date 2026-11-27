"""Check places_day: where an employee's day went, from fake days only.

    python test_places.py

Nothing real is read: every file is made in a temporary folder, the
attendance export is a made-up frame, and no camera is opened.
"""
import ast
import json
import os
import shutil
import sys
import tempfile

import pandas as pd

import places_day as pl
import progress_data as pdx

FAILURES = []
DAY = "2026-11-20"           # a Friday


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def at(hhmm):
    return pd.Timestamp("%s %s" % (DAY, hhmm if hhmm.count(":") == 2
                                   else hhmm + ":00"))


def passes(start, end, state="desk", minutes=5):
    """Passes of `minutes` from start to end (HH:MM), all one state."""
    out, t = [], at(start)
    while t < at(end):
        u = min(t + pd.Timedelta(minutes=minutes), at(end))
        out.append((t, u, state))
        t = u
    return out


def seen(hhmm, room, kind=None, how="face", src="cctv", camera="nvr4:14"):
    return {"t": at(hhmm), "room": room,
            "kind": kind or pl.kind_of(room, plan=PLAN), "how": how,
            "src": src, "camera": camera}


def inside(a, b):
    """The machines: in at a, out at b (HH:MM), nothing else."""
    return {"first_in": at(a), "last_out": at(b), "inside": [(at(a), at(b))],
            "outings": [], "campus": [], "ins": [at(a)]}


def kinds(r):
    return [(s[0].strftime("%H:%M"), s[1].strftime("%H:%M"), s[2], s[3])
            for s in r["segments"]]


PLAN = {"places": {"H Smoking Area": {"outside": True},
                   "140-H Entry Area": {"outside": True},
                   "Basement Meeting Room": {},
                   "H Ground Floor Lobby": {}}}


def check_kinds():
    print("-- the kind of a room")
    check("a meeting room and the board room are meetings",
          (pl.kind_of("Basement Meeting Room", plan=PLAN),
           pl.kind_of("140-H Board Room", plan=PLAN)), ("meeting", "meeting"))
    check("the cafe, the pantry, the commons and the gaming area are the cafe",
          [pl.kind_of(r, plan=PLAN) for r in ("Prompt Cafe", "Pantry",
                                              "140-H Commons",
                                              "Gaming Area")],
          ["cafe"] * 4)
    check("smoking and prayer",
          (pl.kind_of("H Smoking Area", plan=PLAN),
           pl.kind_of("Mosque", plan=PLAN),
           pl.kind_of("Ablution Area", plan=PLAN)),
          ("smoking", "prayer", "prayer"))
    check("the street, a parking, the gate are out; so is a place the plan "
          "draws outside",
          [pl.kind_of(r, plan=PLAN) for r in ("H Street", "P1 Parking",
                                              "Entry H (the gate, going out)",
                                              "140-H Entry Area")],
          ["out"] * 4)
    check("a lobby, another office, their own room: inside, by name",
          [pl.kind_of(r, own="Wellows", plan=PLAN)
           for r in ("H Ground Floor Lobby", "Marketing", "Wellows")],
          ["inside"] * 3)
    check("the kinds the report card draws, in its order", pl.KINDS,
          ("desk", "meeting", "cafe", "smoking", "prayer", "inside", "out",
           "unknown"))


def check_runs():
    print("-- the passes as runs")
    line = [(at("10:00"), at("10:05"), "desk"),
            (at("10:05:40"), at("10:10"), "computer"),   # 40 s apart
            (at("10:17"), at("10:22"), "phone"),         # a 7-min hole
            (at("10:22"), at("10:27"), "away"),
            (at("10:40"), at("10:45"), "desk")]          # 13 min: a hole
    runs = pl._runs(line)
    as_hm = [(pd.Timestamp(s).strftime("%H:%M"),
              pd.Timestamp(e).strftime("%H:%M"), d) for s, e, d in runs]
    check("seconds between passes closed; a hole under ten minutes between "
          "two at the desk filled; any kind at the desk is the desk",
          as_hm[0], ("10:00", "10:22", True))
    check("a hole longer than that stays a hole",
          as_hm[1:], [("10:22", "10:27", False), ("10:40", "10:45", True)])
    check("a hole between a pass away and one at the desk is not filled",
          len(pl._runs([(at("10:00"), at("10:05"), "away"),
                        (at("10:09"), at("10:14"), "desk")])), 2)


def watched(*middle):
    """A day the loop watched from 09:00 to 19:00: away before and after
    the given passes."""
    first, last = middle[0][0], middle[-1][1]
    return passes("09:00", first.strftime("%H:%M:%S"), "away") \
        + list(middle) + passes(last.strftime("%H:%M:%S"), "19:00", "away")


def check_day():
    print("-- one day, rule by rule")
    # at the desk 10:00-12:00 and 13:00-18:00, away 12:00-13:00
    line = watched(*(passes("10:00", "12:00")
                     + passes("12:00", "13:00", "away")
                     + passes("13:00", "18:00")))
    r = pl.day_places(DAY, line, machines=inside("09:50", "18:10"))
    check("the day runs from the IN punch to the OUT punch",
          (r["span"][0].strftime("%H:%M"), r["span"][1].strftime("%H:%M")),
          ("09:50", "18:10"))
    check("away from the desk while the machines say inside: in the "
          "building, place not seen",
          kinds(r), [("09:50", "10:00", "inside", ""),
                     ("10:00", "12:00", "desk", ""),
                     ("12:00", "13:00", "inside", ""),
                     ("13:00", "18:00", "desk", ""),
                     ("18:00", "18:10", "inside", "")])
    check("the minutes add up to the day, kind by kind",
          (round(sum(r["totals"].values()), 6), round(r["totals"]["desk"]),
           round(r["totals"]["inside"])), (500.0, 420, 80))
    check("every kind is in the totals, nothing seen is zero",
          (sorted(r["totals"]) == sorted(pl.KINDS), r["totals"]["cafe"]),
          (True, 0.0))
    check("away 80 minutes, none placed by a camera",
          (round(r["away_min"]), r["seen_min"]), (80, 0.0))

    # one sighting in the cafe: five minutes either side
    r = pl.day_places(DAY, line, [seen("12:30", "Prompt Cafe")],
                      machines=inside("09:50", "18:10"))
    check("a sighting stands for five minutes either side of it",
          kinds(r)[2:5], [("12:00", "12:25", "inside", ""),
                          ("12:25", "12:35", "cafe", "Prompt Cafe"),
                          ("12:35", "13:00", "inside", "")])
    check("and the segment says what placed it",
          r["segments"][3][4], "face")
    # a sighting near the desk is cut at the desk
    r = pl.day_places(DAY, line, [seen("12:02", "Pantry")],
                      machines=inside("09:50", "18:10"))
    check("a window is cut to the time away from the desk",
          kinds(r)[2], ("12:00", "12:07", "cafe", "Pantry"))
    # two sightings of one room 25 minutes apart, no desk between: one stay
    r = pl.day_places(DAY, line, [seen("12:10", "Basement Meeting Room"),
                                  seen("12:35", "Basement Meeting Room")],
                      machines=inside("09:50", "18:10"))
    check("two of one room up to half an hour apart are one stay",
          kinds(r)[2:4], [("12:00", "12:05", "inside", ""),
                          ("12:05", "12:40", "meeting",
                           "Basement Meeting Room")])
    # but not across a pass at the desk
    line2 = passes("10:00", "12:00") + passes("12:00", "12:20", "away") \
        + passes("12:20", "12:30") + passes("12:30", "13:00", "away") \
        + passes("13:00", "18:00")
    r = pl.day_places(DAY, line2, [seen("12:10", "Basement Meeting Room"),
                                   seen("12:40", "Basement Meeting Room")],
                      machines=inside("09:50", "18:10"))
    check("not across a pass at the desk between them",
          [k for k in kinds(r) if k[2] == "meeting"],
          [("12:05", "12:15", "meeting", "Basement Meeting Room"),
           ("12:35", "12:45", "meeting", "Basement Meeting Room")])
    # two rooms whose windows meet: the nearer sighting has each minute
    r = pl.day_places(DAY, line, [seen("12:20", "Prompt Cafe"),
                                  seen("12:26", "H Ground Floor Lobby")],
                      machines=inside("09:50", "18:10"))
    check("two rooms' windows meet halfway between their sightings",
          kinds(r)[3:5], [("12:15", "12:23", "cafe", "Prompt Cafe"),
                          ("12:23", "12:31", "inside",
                           "H Ground Floor Lobby")])
    # a sighting while the desk shows them sitting is not used
    r = pl.day_places(DAY, line, [seen("11:00", "Prompt Cafe")],
                      machines=inside("09:50", "18:10"))
    check("a sighting while at the desk is not used, and is counted",
          (r["totals"]["cafe"], r["conflicts"]["desk"]), (0.0, 1))


def check_out():
    print("-- out of the building")
    line = watched(*(passes("10:00", "12:00")
                     + passes("12:00", "13:30", "away")
                     + passes("13:30", "18:00")))
    m = inside("09:55", "18:05")
    m["outings"] = [(at("12:10"), at("13:00"))]
    m["inside"] = [(at("09:55"), at("12:10")), (at("13:00"), at("18:05"))]
    r = pl.day_places(DAY, line, [seen("12:40", "Prompt Cafe"),
                                  seen("12:20", "H Smoking Area")],
                      machines=m)
    got = kinds(r)
    check("out through the machine and back: out, certain",
          ("12:25", "13:00", "out", "") in got, True)
    check("a sighting outside the building names where in the outing",
          ("12:15", "12:25", "smoking", "H Smoking Area") in got, True)
    check("one inside during the outing is not used, and is counted",
          (r["totals"]["cafe"], r["conflicts"]["outing"]), (0.0, 1))
    check("before and after the outing, inside by the machines",
          (got[2], got[6]), (("12:00", "12:10", "inside", ""),
                             ("13:00", "13:30", "inside", "")))
    # the other campus's machines
    m = inside("09:55", "18:05")
    m["campus"] = [(at("12:15"), at("12:50"), "141-D")]
    m["inside"] = [(at("09:55"), at("12:15")), (at("12:50"), at("18:05"))]
    r = pl.day_places(DAY, line, machines=m)
    check("punches at 141-D are out of 140-H, named so",
          ("12:15", "12:50", "out", "141-D") in kinds(r), True)
    # the gate: out from the passage until the next IN punch
    m = inside("09:55", "18:05")
    m["ins"] = [at("09:55"), at("12:50")]
    r = pl.day_places(DAY, line, exits=[at("12:05")], machines=m)
    check("named at the gate: out until the next IN punch",
          ("12:05", "12:50", "out", "") in kinds(r), True)
    check("and the segment says it was the gate",
          [s[4] for s in r["segments"] if s[2] == "out"], ["gate"])
    r = pl.day_places(DAY, line, [seen("12:30", "Prompt Cafe")],
                      exits=[at("12:05")], machines=inside("09:55", "18:05"))
    check("... or until seen inside again",
          [k for k in kinds(r) if k[2] in ("out", "cafe")],
          [("12:05", "12:25", "out", ""),
           ("12:25", "12:35", "cafe", "Prompt Cafe")])
    r = pl.day_places(DAY, line, exits=[at("12:05")])
    check("... or until back at the desk", [k for k in kinds(r)
                                             if k[2] == "out"],
          [("12:05", "13:30", "out", "")])


def check_not_known():
    print("-- what nothing says is not known")
    line = passes("10:00", "12:00") + passes("12:00", "13:00", "away") \
        + passes("13:00", "14:00") + passes("14:30", "18:00")
    r = pl.day_places(DAY, line)
    check("no machines: away is not known", kinds(r)[1],
          ("12:00", "13:00", "unknown", ""))
    check("a hole in the watching is not known, and says so",
          (kinds(r)[3], r["segments"][3][4]),
          (("14:00", "14:30", "unknown", ""), "unwatched"))
    m = inside("09:55", "18:05")
    r = pl.day_places(DAY, line, machines=m)
    check("a hole is not known even while the machines say inside -- the "
          "desk or not is not known", kinds(r)[4],
          ("14:00", "14:30", "unknown", ""))
    m["inside"] = [(at("09:55"), at("12:30"))]    # the export stops here
    r = pl.day_places(DAY, line, machines=m)
    check("after the machines' export ends, away is not known",
          [k for k in kinds(r) if "12:00" <= k[0] < "13:00"],
          [("12:00", "12:30", "inside", ""),
           ("12:30", "13:00", "unknown", "")])
    check("no desk and no punch: no day",
          (pl.day_places(DAY, passes("10:00", "12:00", "away"))["span"],
           pl.day_places(DAY, [])["segments"]), (None, []))
    r = pl.day_places(DAY, passes("10:00", "12:00", "away"),
                      machines=inside("10:00", "12:00"))
    check("the machines alone make a day: in the building, place not seen",
          kinds(r), [("10:00", "12:00", "inside", "")])


def check_span():
    print("-- where the day begins and ends")
    line = passes("10:00", "17:00")
    r = pl.day_places(DAY, line, [seen("09:30", "Prompt Cafe")])
    check("a sighting inside within an hour before the desk widens the day "
          "to it", kinds(r)[:2], [("09:30", "09:35", "cafe", "Prompt Cafe"),
                                  ("09:35", "10:00", "unknown", "")])
    r = pl.day_places(DAY, line, [seen("17:40", "H Street")],
                      machines=inside("09:58", "17:05"))
    check("one outside after the last OUT does not: the way home",
          r["span"][1].strftime("%H:%M"), "17:05")
    r = pl.day_places(DAY, line, [seen("19:30", "Prompt Cafe")])
    check("nor one more than an hour after the desk",
          r["span"][1].strftime("%H:%M"), "17:00")
    night = passes("07:00", "07:30") + passes("10:00", "17:00")
    r = pl.day_places(DAY, night, machines=inside("09:55", "17:05"))
    check("a desk before eight is not the start of the day",
          r["span"][0].strftime("%H:%M"), "09:55")
    line = passes("10:00", "12:00") + passes("12:00:30", "17:00")
    r = pl.day_places(DAY, line, machines=inside("10:00", "17:00"))
    check("seconds between two passes at the desk are not a break",
          kinds(r), [("10:00", "17:00", "desk", "")])
    line = passes("10:00", "12:00") + passes("12:00", "12:20", "away") \
        + passes("12:20", "17:00")
    m = inside("10:00", "17:00")
    m["outings"] = [(at("12:00"), at("12:19:30"))]
    r = pl.day_places(DAY, line, machines=m)
    check("a sliver under a minute goes to its neighbour",
          [k[2] for k in kinds(r)], ["desk", "out", "desk"])


def check_unsure():
    print("-- a face that keeps finding them at their desk")
    line = passes("10:00", "12:00") + passes("12:00", "13:00", "away") \
        + passes("13:00", "18:00")
    many = [seen("10:30", "Prompt Cafe"), seen("11:00", "H Street"),
            seen("11:30", "Pantry"), seen("12:30", "Prompt Cafe")]
    r = pl.day_places(DAY, line, many, machines=inside("09:55", "18:05"))
    check("three of four at the desk: none of that source is used that day",
          (r["unsure"], r["totals"]["cafe"], r["conflicts"]["desk"]),
          (["cctv"], 0.0, 3))
    other = [dict(g, src="listed") for g in many[:1]] + many[3:]
    r = pl.day_places(DAY, line, other, machines=inside("09:55", "18:05"))
    check("one at the desk is a slip, the rest stand",
          (r["unsure"], round(r["totals"]["cafe"])), ([], 10))
    named = [dict(g, src="named", how="seen") for g in many]
    r = pl.day_places(DAY, line, named, machines=inside("09:55", "18:05"))
    check("a picture a person named is never set aside",
          (r["unsure"], round(r["totals"]["cafe"])), ([], 10))
    gate = [at("10:30"), at("11:00"), at("11:30"), at("12:10")]
    r = pl.day_places(DAY, line, exits=gate,
                      machines=inside("09:55", "18:05"))
    check("nor the gate's, when it keeps naming them while they sit",
          (r["unsure"], r["totals"]["out"]), (["gate"], 0.0))


def check_machines():
    print("-- the attendance machines, on the laptop's clock")
    import attendance

    def punch(t, kind, place="140-H"):
        return {"eid": "77", "at": at(t), "kind": kind,
                "place": "%s %s" % (place, kind.upper())}
    data = pd.DataFrame([
        punch("00:36", "in"), punch("04:25", "out"),      # the night's
        punch("09:50", "in"), punch("11:00", "out"),
        punch("11:01", "in"),                              # a blip
        punch("12:00", "out"), punch("12:10", "in", "141-D"),
        punch("12:40", "out", "141-D"), punch("13:00", "in"),
        punch("13:05", "in"), punch("18:00", "out")])
    rows = [(r["at"], r["kind"], r["place"]) for _, r in data.iterrows()]
    end = pd.Timestamp(DAY) + pd.Timedelta(days=1)
    got = pl.punch_day(rows, attendance.CAMPUS, attendance.BLIP, end)
    want_day = attendance.day("77", DAY, data=data)
    want_inside = attendance.inside("77", DAY, data=data)
    check("the list reading agrees with attendance.day and .inside",
          (got[0], got[1], got[2], got[3]),
          (want_day["first_in"], want_day["last_out"], want_inside,
           want_day["outings"]))
    old = pl._offset
    pl._offset = lambda day, data: 120.0           # laptop 2 min ahead
    try:
        m = pl.machines_for("77", DAY, data=data)
    finally:
        pl._offset = old
    check("the night's punches do not start the day; times moved 2 minutes",
          m["first_in"].strftime("%H:%M"), "09:52")
    check("the other campus's punches: out, from its first to the next "
          "punch here", [(a.strftime("%H:%M"), b.strftime("%H:%M"), w)
                         for a, b, w in m["campus"]],
          [("12:12", "13:02", "141-D")])
    check("inside is cut where they were at the other campus",
          [(a.strftime("%H:%M"), b.strftime("%H:%M")) for a, b in m["inside"]],
          [("09:52", "11:02"), ("11:03", "12:02"), ("13:02", "18:02")])
    check("an out-and-in within two minutes is the turnstile, no outing",
          [(a.strftime("%H:%M"), b.strftime("%H:%M")) for a, b in m["outings"]],
          [("12:02", "13:02")])
    late = data[data["at"] <= at("12:30")]          # the export stops 12:30
    old = pl._offset
    pl._offset = lambda day, data: 0.0
    pl._machines.update(data=None)
    try:
        m = pl.machines_for("77", DAY, data=late)
    finally:
        pl._offset = old
        pl._machines.update(data=None)
    check("after the export's last punch the machines say nothing",
          (m["known_until"].strftime("%H:%M"),
           max(b for _, b in m["inside"]).strftime("%H:%M")),
          ("12:10", "12:00"))
    check("nobody, no export, no punch: None",
          (pl.machines_for("", DAY, data=data),
           pl.machines_for("78", DAY, data=data)), (None, None))


def _write(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(header) + "\n")
        for r in rows:
            fh.write(",".join(str(v) for v in r) + "\n")


def check_files():
    print("-- the sightings, the gate and the board, from files")
    tmp = tempfile.mkdtemp()
    saved = (pl.SIGHTINGS, pl.ACTIVITY, pl.NAMED, pl.GATE, pl._export,
             pl._offset, pdx.ACTIVITY)
    try:
        pl.SIGHTINGS = os.path.join(tmp, "sightings")
        pl.ACTIVITY = pdx.ACTIVITY = os.path.join(tmp, "progress")
        pl.NAMED = os.path.join(tmp, "sighting_names.csv")
        pl.GATE = os.path.join(tmp, "entrance")
        pl.forget()
        _write(os.path.join(pl.SIGHTINGS, DAY + ".csv"),
               ["time", "employee_id", "room", "recorder", "channel",
                "score", "margin"],
               [["12:30:00", "77", "Prompt Cafe", "nvr4", 14, 0.62, 0.30],
                ["12:40:00", "77", "Pantry", "nvr4", 16, 0.55, 0.12],
                ["12:45:00", "77", "Mosque", "nvr4", 6, 0.45, 0.30],
                ["12:50:00", "88", "Mosque", "nvr4", 6, 0.70, 0.40]])
        _write(os.path.join(pl.ACTIVITY, DAY + ".csv"),
               ["time", "code", "kind", "state", "room", "recorder",
                "channel", "score", "x1", "y1", "x2", "y2"],
               [["12:05:00", "P9", "seen", "face", "Basement Meeting Room",
                 "nvr4", 22, 0.66, 0, 0, 0, 0],
                ["12:15:00", "P9", "seen", "possible", "Prompt Cafe", "nvr4",
                 14, 0.80, 0, 0, 0, 0],
                ["12:20:00", "P9", "seen", "possible", "Pantry", "nvr4", 16,
                 0.81, 0, 0, 0, 0],
                ["12:25:00", "P9", "seen", "face", "Mosque", "nvr4", 6, 0.6,
                 0, 0, 0, 0],
                ["12:00:00", "P9", "desk", "away", "Test Room", "dvr2", 15,
                 0.0, 0, 0, 0, 0]])
        _write(pl.NAMED, ["day", "time", "guessed", "room", "recorder",
                          "channel", "picture", "employee_id", "at"],
               [[DAY, "15:00:00", "P1", "Marketing", "dvr2", 3, "", "77",
                 "x"]])
        _write(os.path.join(pl.GATE, DAY + ".csv"),
               ["time", "recorder", "channel", "status", "employee_id",
                "best", "score", "margin", "face_w"],
               [["13:10:00", "nvr1", 5, "named", "77", "77", 0.6, 0.2, 80],
                ["13:20:00", "nvr1", 5, "unknown", "", "77", 0.4, 0.0, 80],
                ["13:30:00", "nvr1", 5, "named", "88", "88", 0.6, 0.2, 80]])
        said = {("12:15:00", "P9", "Prompt Cafe"): "yes",
                ("12:25:00", "P9", "Mosque"): "no"}
        g = pl.sightings_for("P9", DAY, "77", cams={("nvr4", 16): "Pantry"},
                             plan=PLAN, reviews=said)
        check("a face far enough clear counts; one too near the next "
              "person's, or too low, does not",
              [x["room"] for x in g if x["src"] == "cctv"], ["Prompt Cafe"])
        check("their own face rows count, a body match only with a yes, a "
              "no wins",
              [(x["room"], x["how"]) for x in g if x["src"] == "listed"],
              [("Basement Meeting Room", "face"), ("Prompt Cafe", "seen")])
        check("a picture a person named is them",
              [(x["room"], x["how"]) for x in g if x["src"] == "named"],
              [("Marketing", "seen")])
        check("every sighting says its kind and its camera",
              (g[0]["kind"], g[0]["camera"]), ("meeting", "nvr4:22"))
        check("for measuring, every possible body match",
              len(pl.sightings_for("P9", DAY, "77", plan=PLAN, reviews={},
                                   possible=True)), 6)
        check("the gate: their named passages only",
              [t.strftime("%H:%M") for t in pl.exits_for("77", DAY)],
              ["13:10"])
        check("no employee ID, no faces and no gate -- their own rows only",
              ([x["src"] for x in pl.sightings_for("P9", DAY, "", plan=PLAN,
                                                   reviews={})],
               pl.exits_for("", DAY)), (["listed", "listed"], []))
        check("a day with no files has nothing",
              (pl.sightings_for("P9", "2026-11-19", "77", reviews={}),
               pl.exits_for("77", "2026-11-19")), ([], []))

        # the board: the focus day's places and each day's minutes
        export = pd.DataFrame([
            {"eid": "77", "at": at("09:55"), "kind": "in",
             "place": "140-H IN"},
            {"eid": "77", "at": at("18:05"), "kind": "out",
             "place": "140-H OUT"}])
        pl._export = lambda: export
        pl._offset = lambda day, data: 0.0
        person = {"code": "P9", "name": "Somebody", "employee_id": "77",
                  "department": "Test Room", "recorder": "dvr2",
                  "channel": 15, "seat": [560, 700], "since": "2026-11-20"}
        line = watched(*(passes("10:00", "12:00")
                         + passes("12:00", "13:30", "away")
                         + passes("13:30", "18:00")))
        places, per_day = pl.board(person, "77", ["2026-11-19", DAY], DAY,
                                   cams={}, lines={DAY: line,
                                                   "2026-11-19": line})
        # (27 Nov: and every day's stops, for the report card's day stop by
        # stop on any day)
        check("the focus day's places: day, segments, totals, and by_day",
              (sorted(places), sorted(places["by_day"])),
              (["by_day", "day", "segments", "totals"], [DAY]))
        check("segments are (start, end, kind, name), one after another",
              (all(len(s) == 4 for s in places["segments"]),
               all(a[1] == b[0] for a, b in zip(places["segments"],
                                                places["segments"][1:]))),
              (True, True))
        check("the totals have every kind, in minutes",
              (sorted(places["totals"]) == sorted(pl.KINDS),
               places["totals"]["desk"]), (True, 390.0))
        check("each day's minutes by kind; a day before `since` has none",
              sorted(per_day), [DAY])
        check("the meeting room, prayer, the cafe and the gate are in the "
              "day, in order",
              [s[2] for s in places["segments"]],
              ["inside", "desk", "meeting", "inside", "prayer", "cafe",
               "inside", "out", "desk", "inside"])
        check("where two rooms' windows meet, halfway between the sightings",
              [s[1].strftime("%H:%M:%S") for s in places["segments"]
               if s[2] == "prayer"], ["12:27:30"])
        blob = json.dumps(pdx._jsonable({"p": places, "d": per_day}))
        check("no name and no employee ID in what the page is sent",
              ("Somebody" in blob, '"77"' in blob), (False, False))
        back = pdx._restore(json.loads(blob))
        check("and it comes back from the hosted page as it went",
              (back["p"]["segments"][1][0], back["d"][DAY]["desk"]),
              (places["segments"][1][0], 390.0))
    finally:
        (pl.SIGHTINGS, pl.ACTIVITY, pl.NAMED, pl.GATE, pl._export,
         pl._offset, pdx.ACTIVITY) = saved
        pl.forget()
        shutil.rmtree(tmp, ignore_errors=True)


def check_words():
    print("-- the words for the card")
    t = {"desk": 312.0, "meeting": 54.0, "cafe": 36.0, "smoking": 18.0,
         "prayer": 2.0, "inside": 66.0, "out": 24.0, "unknown": 0.0}
    check("the overview, in the building and out",
          pl.overview(t), "8.1 h in the building: 5.2 h at the desk, 0.9 h "
          "meeting rooms, 0.6 h cafe, 0.3 h smoking, 1.1 h elsewhere in the "
          "building; 0.4 h out")
    check("a stretch in words",
          pl.describe((at("13:05"), at("13:40"), "cafe", "Prompt Cafe")),
          "from 13:05 to 13:40 in the cafe (Prompt Cafe)")
    check("inside, by name or not",
          (pl.describe((at("13:05"), at("13:40"), "inside", "Marketing")),
           pl.describe((at("13:05"), at("13:40"), "inside", ""))),
          ("from 13:05 to 13:40 in Marketing",
           "from 13:05 to 13:40 in the building, place not seen"))


def check_guarded():
    print("-- it never stops the page")
    old = pl.board

    def broken(*a, **k):
        raise RuntimeError("anything")
    pl.board = broken
    try:
        got = pdx.places_of({"code": "P9"}, "77", [DAY], DAY)
    finally:
        pl.board = old
    check("progress_data.places_of: anything wrong is no places",
          got, (None, {}))
    src = open("progress_data.py", encoding="utf-8").read()
    body = src.split("def build(", 1)[1].split("\ndef ", 1)[0]
    check("build() gives every board person places and places_days",
          'out[-1]["places"], out[-1]["places_days"] = places_of(' in body,
          True)
    tree = ast.parse(open("places_day.py", encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    check("places_day needs no camera library: pandas and the project's "
          "pandas-only modules", sorted(names - set(sys.stdlib_module_names)),
          ["attendance", "building", "desks_data", "pandas",
           "progress_data"])
    text = open("places_day.py", encoding="utf-8").read().lower()
    check("and says 'at the desk', never 'productive'",
          "productive" in text, False)


def main():
    check_kinds()
    check_runs()
    check_day()
    check_out()
    check_not_known()
    check_span()
    check_unsure()
    check_machines()
    check_files()
    check_words()
    check_guarded()
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
