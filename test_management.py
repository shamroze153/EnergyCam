"""Management Preview (management_view.py): every panel drawn from plain
values, the twin laid out from real rooms, the discoveries' rules, and the
brief's rules kept -- no invented temperature, no individual ranking, no
camera picture.

    python test_management.py
"""
import json
import re
import sys

import management_view as mv

FAILURES = []


def check(name, got, want):
    ok = got == want
    print("%s  %s" % ("OK  " if ok else "FAIL", name))
    if not ok:
        print("      got:  %r\n      want: %r" % (got, want))
        FAILURES.append(name)


def rooms():
    return [
        {"name": "140-H DL Department", "short": "DL Department",
         "floor": "Ground floor", "zone": "H offices", "status": "occupied",
         "people": 12, "waste": False, "ac_state": "on", "units": 2,
         "desks": 20, "q": "?room=DL"},
        {"name": "140-H Meeting Room", "short": "Meeting Room",
         "floor": "Ground floor", "zone": "Offices", "status": "empty",
         "people": 0, "waste": True, "ac_state": "on", "units": 1,
         "desks": 0, "q": "?room=MR", "since": "empty 45 min"},
        {"name": "140-H Server Room", "short": "Server Room",
         "floor": "First floor", "zone": "Server rooms", "status": "unknown",
         "people": 0, "waste": False, "ac_state": None, "units": 1,
         "desks": 0, "q": "?room=SR"},
        {"name": "140-H Parking", "short": "Parking", "floor": "Ground floor",
         "zone": "H perimeter", "status": "occupied", "people": 3,
         "waste": False, "ac_state": None, "units": 0, "desks": 0, "q": ""},
        {"name": "141 Gym", "short": "Gym", "floor": "First floor",
         "zone": "Cafe & common", "status": "unknown", "people": 0,
         "waste": False, "ac_state": None, "units": 1, "desks": 0,
         "private": True, "q": ""},
    ]


def check_twin():
    print("-- the twin: real rooms on their floors, outdoors left out")
    t = mv.twin_payload(rooms())
    names = [r["name"] for f in t["floors"] for r in f["rooms"]]
    check("every indoor room drawn; the car park is not",
          (len(names), any("Parking" in n for n in names)), (4, False))
    by = {r["name"]: r for f in t["floors"] for r in f["rooms"]}
    check("states: occupied, AC-on-empty, not answering, private",
          (by["140-H DL Department"]["status"],
           by["140-H Meeting Room"]["status"],
           by["140-H Server Room"]["status"], by["141 Gym"]["status"]),
          ("occupied", "waste", "unknown", "private"))
    check("the AC-on-empty room carries the red callout",
          (by["140-H Meeting Room"]["call"]["title"],
           by["140-H Meeting Room"]["call"]["good"]), ("AC ON", False))
    check("busy desks never more than the desks",
          by["140-H DL Department"]["busy"], 12)
    check("it opens on the floor with the AC-on-empty room", t["start"],
          "Ground floor")
    rs = [r for f in t["floors"] for r in f["rooms"]]
    overlap = any(a is not b and a["floor"] == b["floor"]
                  and a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                  and a["z"] < b["z"] + b["d"] and b["z"] < a["z"] + a["d"]
                  for a in rs for b in rs)
    check("no two rooms on one floor overlap", overlap, False)
    check("the schematic says it is not the architect's plan",
          "not the architect" in t["note"], True)
    doc = mv.twin_doc({"twin": t}, 480)
    check("the 3D page: three.js and its controls from fixed versions, "
          "the data inline",
          ("three.js/r128/three.min.js" in doc,
           "three@0.128.0/examples/js/controls/OrbitControls.js" in doc,
           "__DATA__" in doc, json.dumps(t["start"]) in doc),
          (True, True, False, True))


def check_rules():
    print("-- the discoveries: explainable rules, strongest first")
    live = [{"room": "140-H Meeting Room", "waste": True, "kw": 1.5,
             "counted": 1, "since": "empty 45 min"},
            {"room": "140-H DL Department", "waste": False, "kw": 3.0,
             "counted": 2}]
    ledger = [{"room": "140-H Meeting Room", "waste_rs": 640.0,
               "empty_on_h": 3.5},
              {"room": "140-H Cafe", "waste_rs": 40.0, "empty_on_h": 0.5}]
    hourly = [[0, 0]] * 13 + [[120, 90], [100, 80]] + [[50, 0]] * 9
    ds = mv.discover(live, ledger, hourly, ["141 Room 9"], 67.0,
                     lambda r: "?room=" + r, {"140-H Meeting Room": 1})
    check("AC-on-empty now first, then today's empty cooling, the hours, "
          "the silent camera",
          [d["kind"] for d in ds], ["waste_now", "waste_today", "hours",
                                    "gap"])
    check("a room under Rs 100 of empty cooling is not a discovery",
          any("Cafe" in d["title"] for d in ds), False)
    check("each one says its evidence and confidence",
          all(d["evidence"] and d["confidence"] for d in ds), True)
    check("an unread unit's money is low confidence",
          mv.discover([], [{"room": "X", "waste_rs": 300, "empty_on_h": 2}],
                      [], [], 67, str, {})[0]["confidence"].startswith("low"),
          True)
    check("the empty-cooling hours joined: 1 pm to 3 pm", mv._waste_spans(
        hourly)[0][:2], (13, 15))
    rows = mv.room_rows(rooms(), lambda r: "?room=" + r)
    check("the room table: wasted cooling first, private hours left out",
          ([r["kind"] for r in rows][0], any("Gym" in r["room"]
                                             for r in rows)),
          ("waste", False))


def check_work():
    print("-- work patterns: team-level shares, no one ranked")
    hist = [{"day": "2026-11-26", "in_min": 480, "desk_min": 300,
             "computer_min": 200, "phone_min": 30, "talking_min": 10}]
    people = [{"role": "Engineer, Technology, X", "history": hist}] * 6 + [
        {"role": "Analyst, Finance, X", "history": hist}] * 2
    w = mv.work_payload(people)
    check("shares add to 100 and the desk share is the desk's",
          (round(sum(v for _, v, _ in w["shares"])), round(w["at_desk"])),
          (100, 62))
    check("departments with 5+ measured only",
          [t[0] for t in mv.team_rows(people)], ["Technology"])
    check("nobody read: no pattern", mv.work_payload([]), None)


def check_page():
    print("-- the page: every panel drawn, nothing made up")
    t = mv.twin_payload(rooms())
    p = {"campus": "140-H", "live": True, "live_text": "live",
         "when": "Fri, Nov 27, 2026\n9:00 PM",
         "campuses": [{"name": "140-H", "on": True, "url": "?a"},
                      {"name": "141-C/D", "on": False, "url": "?b"}],
         "nav": [{"label": "Dashboard", "icon": "home", "on": True,
                  "url": "#"}],
         "kpis": [{"icon": "people", "colour": "#60a5fa", "label": "People",
                   "value": "120", "spark": [1, 2, 3], "note": "now"}],
         "twin": t,
         "work": dict(mv.work_payload([{"role": "a, b", "history": [
             {"day": "2026-11-26", "in_min": 400, "desk_min": 200}]}] * 3),
             day_label="Thu 26 Nov", curve=[1, 2, None, 4],
             curve_labels=[(0, "9am")], note="team-level"),
         "teams": [], "energy": {"today": [1, None], "yday": [1, 2],
                                 "now_hour": 0, "vs_yday": -10.0,
                                 "diff_rs": -50.0, "note": "estimated"},
         "ac": {"efficient": 80.0, "on": "3", "readable": 5, "all_units": 9,
                "waste_rooms": 1, "note": "ring"},
         "discoveries": [], "rooms_table": mv.room_rows(rooms(), str),
         "savings": {"pairs": [("Today", 100.0, 80.0)], "note": "lower"},
         "trust": [(True, "The loop", "live"), (None, "Room temperature",
                                                "not measured")],
         "actions": [{"label": "Rooms", "icon": "camera", "colour": "#fff",
                      "url": "?c"}], "silent": [], "health_text": "ok"}
    page = "".join([mv.css(), mv.header(p), mv.nav(p), mv.kpis(p),
                    mv.twin_head(p), mv.work(p), mv.energy(p), mv.ac_panel(p),
                    mv.discoveries(p), mv.teams(p), mv.rooms_table(p),
                    mv.savings(p), mv.trust(p), mv.actions(p)])
    check("no 'None', no stray %, no camera picture",
          ("None" in re.sub(r"<style>.*?</style>", "", page, flags=re.S),
           "%%" in page, ".jpg" in page or "<img" in page),
          (False, False, False))
    check("temperature is said to be not measured, never a number",
          "Room temperature: not measured" in page, True)
    check("one <style> block, on its own (the Streamlit gotcha)",
          mv.css().count("<style>"), 1)
    check("the header without the campus links where the page draws its "
          "own switch", ("mp-camp" in mv.header(p), "mp-camp" in mv.header(
              p, pills=False)), (True, False))


def main():
    check_twin()
    check_rules()
    check_work()
    check_page()
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
