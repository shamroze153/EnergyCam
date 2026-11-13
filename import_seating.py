"""Refresh seating.yaml's desk counts from the admin team's seating sheet.

    python import_seating.py seating.csv

Download the sheet's "seating" tab as CSV (File > Download > .csv), then run
this on it. Only these columns are read: Room Code, Room Code - Dashboard,
location, Floor Tag, Category, Status and BU. The names and employee codes
are never read, and nothing but counts is written -- seating.yaml goes into
a public repository. Delete the downloaded file afterwards.

Each space in seating.yaml lists the sheet's Room Code(s) it covers, and
which camera rooms see it (rooms:). A refresh keeps those, recounts the
desks, and adds any code it has not seen before as a new space with no
camera (a person then says which room it is).
"""
import csv
import sys

import seating

FLOORS = {"basement": "Basement", "ground": "Ground floor",
          "first": "First floor", "second": "Second floor",
          "third": "Third floor"}
CAMPUS = {"140 H": ("140-H", "140-H"), "141 C": ("141-C/D", "141-C"),
          "141 D": ("141-C/D", "141-D")}


def counts(rows):
    """{room code: {seats, allocated, in_use, out_of_order, teams, ...}}."""
    out = {}
    for r in rows:
        code = (r.get("Room Code") or "").strip()
        if not code:
            continue
        c = out.setdefault(code, {
            "seats": 0, "allocated": 0, "in_use": 0, "out_of_order": 0,
            "teams": {}, "label": (r.get("Room Code - Dashboard") or "").strip(),
            "location": (r.get("location") or "").strip(),
            "floor": (r.get("Floor Tag") or "").strip()})
        c["seats"] += 1
        category = (r.get("Category") or "").strip().lower()
        status = (r.get("Status") or "").strip().lower()
        if category == "allocated":
            c["allocated"] += 1
        if status == "occupied":
            c["in_use"] += 1
        elif status == "ooo":
            c["out_of_order"] += 1
        team = (r.get("BU") or "").strip()
        if team and team.lower() != "unassigned":
            c["teams"][team] = c["teams"].get(team, 0) + 1
    return out


def refresh(data, found):
    """seating.yaml's spaces recounted from `found`; new codes appended."""
    known = set()
    spaces = []
    for s in data["spaces"]:
        mine = [found[c] for c in s["codes"] if c in found]
        known.update(s["codes"])
        # The new counts are the sheet's own; a correction stays in
        # override and still wins when the file is read.
        s = dict(s, sheet=None)
        if mine:
            for key in ("seats", "allocated", "in_use", "out_of_order"):
                s[key] = sum(m[key] for m in mine)
            teams = {}
            for m in mine:
                for t, n in m["teams"].items():
                    teams[t] = teams.get(t, 0) + n
            s["teams"] = teams
        else:
            # Gone from the sheet: no desks there any more.
            for key in ("seats", "allocated", "in_use", "out_of_order"):
                s[key] = 0
            s["teams"] = {}
        spaces.append(s)
    for code in sorted(set(found) - known):
        m = found[code]
        campus, building = CAMPUS.get(m["location"], (m["location"],
                                                      m["location"]))
        spaces.append({
            "name": "%s %s" % (building, m["label"] or code), "campus": campus,
            "building": building,
            "floor": FLOORS.get(m["floor"].lower(), m["floor"]),
            "codes": [code], "seats": m["seats"], "allocated": m["allocated"],
            "in_use": m["in_use"], "out_of_order": m["out_of_order"],
            "teams": m["teams"], "rooms": [],
            "note": "New on the sheet: which camera room is it?"})
    return dict(data, spaces=spaces)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8-sig", newline="") as f:
        found = counts(csv.DictReader(f))
    if not found:
        print("No Room Code column with rows in %s -- is it the seating tab?"
              % argv[1])
        return 1
    data = refresh(seating.load(), found)
    if len(argv) > 2:
        data["as_of"] = argv[2]
    with open(seating.PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(seating.dump(data))
    print("%d desks in %d spaces (%d given); %d spaces have a camera."
          % (sum(s["seats"] for s in data["spaces"]), len(data["spaces"]),
             sum(s["allocated"] for s in data["spaces"]),
             sum(1 for s in data["spaces"] if s["rooms"])))
    print("Delete %s now: it has people's names in it." % argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
