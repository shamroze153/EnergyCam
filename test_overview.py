"""Check the front pages say what happened: who came, who left, how many.

    python test_overview.py

The welcome page and the campus overview are arithmetic first and drawing
second, so the arithmetic is checked here on a made-up day whose answers are
known: Squat Wolf's two rooms, a room with no department, a lobby, a gate
outside, and a channel nobody uses.
"""
import re
import sys
from datetime import timedelta

import pandas as pd

import overview as ov

FAILURES = []
DAY = pd.Timestamp("2026-11-11 00:00", tz="Asia/Karachi")
NOW = (DAY + timedelta(hours=15)).tz_convert("UTC")


def check(label, ok, detail=""):
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> %s" % (detail,)))
    if not ok:
        FAILURES.append(label)


def at(h, m=0, day=0):
    return (DAY + timedelta(days=day, hours=h, minutes=m)).tz_convert("UTC")


def events():
    rows = []

    def add(room, *spells):
        rows.append((at(0, 0, -2), room, "empty", 0))
        for when, status, people in spells:
            rows.append((when, room, status, people))
    # Squat Wolf, two rooms. Room 0: in 9:30 with two, out at six.
    # Yesterday it emptied at 7:15 in the evening.
    add("SW Room 0",
        (at(9, 0, -1), "occupied", 2), (at(19, 15, -1), "empty", 0),
        (at(9, 30), "occupied", 2), (at(18), "empty", 0))
    # Room 1: in at ten with three, still in now. Yesterday the last of the
    # campus to leave, at 9:40 at night.
    add("SW Room 1",
        (at(10, 0, -1), "occupied", 3), (at(21, 40, -1), "empty", 0),
        (at(10), "occupied", 3))
    # A working room with no department: the cleaner at 7:05 for ten
    # minutes, then the day from nine.
    add("Marketing",
        (at(7, 5), "occupied", 1), (at(7, 15), "empty", 0),
        (at(9), "occupied", 1))
    # A lobby: busy at lunch.
    add("Lobby", (at(13), "occupied", 4), (at(14), "empty", 0))
    # The gate, outside: a guard all day. Never counted as inside.
    add("Gate", (at(0, 0, -1), "occupied", 2))
    return pd.DataFrame(rows, columns=["timestamp", "room", "status",
                                       "people"])


def rooms():
    rows = [
        # name, zone, dept, status, people, level
        ("SW Room 0", "Offices", "Squat Wolf", "empty", 0, "Amber"),
        ("SW Room 1", "Offices", "Squat Wolf", "occupied", 3, "Green"),
        ("Marketing", "Offices", "", "occupied", 1, "Green"),
        ("Lobby", "Cafe & common", "", "empty", 0, "Green"),
        ("Gate", "Outside & plant", "Security", "occupied", 2, "Green"),
        ("Dead channels", "Unused", "", "unknown", 0, "Fault"),
    ]
    out = []
    for name, zone, dept, status, people, level in rows:
        out.append({"room": name, "zone": zone, "dept": dept,
                    "status": status, "people": people, "level": level,
                    "headline": "Empty 3h 00m" if status == "empty" else "",
                    "sub": "", "ac": "hidden", "has_unit": True,
                    "alerts": True, "empty_since": at(12),
                    "occupied_since": at(9)})
    return pd.DataFrame(out)


def main():
    # ---- whose room is it --------------------------------------------------
    check("outside belongs to no department",
          ov.department_of("Gate", "Outside & plant", "Security") is None)
    check("a written department wins",
          ov.department_of("SW Room 0", "Offices", "Squat Wolf")
          == "Squat Wolf")
    check("a working room without one is its own department",
          ov.department_of("Marketing", "Offices", "") == "Marketing")
    check("a lobby without one goes with its zone",
          ov.department_of("Lobby", "Cafe & common", "") == "Cafe & common")

    s = ov.campus_summary("Test", rooms(), events(), None, NOW, stake=1234.4,
                          stake_note="upper bound")

    # ---- now ---------------------------------------------------------------
    check("people inside are the indoor rooms only", s["inside_now"] == 4,
          s["inside_now"])
    check("the gate is counted, separately", s["outside_now"] == 2,
          s["outside_now"])
    check("rooms in use, indoors", (s["rooms_busy"], s["rooms_total"])
          == (2, 4), (s["rooms_busy"], s["rooms_total"]))
    check("a channel nobody uses is not a room on this page",
          all(r["name"] != "Dead channels" for r in s["rooms"]))

    # ---- the day -----------------------------------------------------------
    check("the campus opened with the first department to start its day",
          s["first_in"] == at(9) and s["first_who"] == "Marketing",
          (s["first_in"], s["first_who"]))
    check("the cleaner at seven is not the day starting",
          s["first_in"] != at(7, 5))
    # 13:00-14:00: Room 0 (2) + Room 1 (3) + Marketing (1) + Lobby (4).
    check("the busiest moment adds every room inside, not the gate",
          s["peak"] == 10 and s["peak_at"] == at(13), (s["peak"], s["peak_at"]))
    check("yesterday ended when the last working room emptied",
          s["last_out_yday"] == at(21, 40, -1), s["last_out_yday"])
    check("and nobody stayed the night", not s["overnight"])
    check("the day is drawn in quarter hours", len(s["curve_in"]) == 96)
    now_slot = (15 * 60) // 15
    check("nothing is drawn after now",
          all(v is None for v in s["curve_in"][now_slot + 1:]))
    check("the gate is a line of its own",
          s["curve_out"][10 * 4] == 2, s["curve_out"][10 * 4])

    # ---- departments -------------------------------------------------------
    depts = {d["name"]: d for d in s["depts"]}
    sw = depts.get("Squat Wolf")
    check("Squat Wolf is one department of two rooms",
          sw is not None and sw["rooms"] == 2, sw and sw["rooms"])
    check("it started with its first room",
          sw and sw["starts"] == at(9, 30), sw and sw["starts"])
    check("its people are its rooms' people added up",
          sw and sw["people"] == 3 and sw["peak"] == 5,
          sw and (sw["people"], sw["peak"]))
    check("still in, because one room is",
          sw and sw["still_in"] and sw["last_out"] is None)
    check("and one of its rooms wants a walk", sw and sw["walk"] == 1)
    check("the lobby is a common area, not a department of work",
          not depts["Cafe & common"]["work"])
    check("working departments come first",
          [d["work"] for d in s["depts"]] == sorted(
              [d["work"] for d in s["depts"]], reverse=True))
    check("the walk list is the rooms the grader flagged",
          [e["name"] for e in s["walk"]] == ["SW Room 0"])

    # ---- the night that did not end ----------------------------------------
    late = events()
    late = pd.concat([late, pd.DataFrame([
        (at(20, 0, -1), "Marketing", "occupied", 1)],
        columns=late.columns)]).sort_values("timestamp")
    late = late[~((late["room"] == "Marketing") & (late["timestamp"] < at(9))
                  & (late["timestamp"] >= at(0)))]
    n = ov.campus_summary("Test", rooms(), late, None, NOW)
    check("somebody in at midnight means yesterday never ended",
          n["overnight"])
    md = {d["name"]: d for d in n["depts"]}["Marketing"]
    check("and that department is in since last night, not an arrival",
          md["carried"] and n["first_who"] != "Marketing",
          (md["carried"], n["first_who"]))

    # ---- the pages ---------------------------------------------------------
    base = {"campus": None, "theme": None}
    for theme in ("dark", "light"):
        page = ov.welcome([s], theme, "<svg></svg>", "live", True,
                          "Wednesday", base)
        check("%s: the welcome page names the campus and lets you in" % theme,
              "Test" in page and "Enter campus" in page
              and 'href="?campus=Test"' in page)
        check("%s: nothing reads None or nan" % theme,
              not re.search(r">\s*(None|nan|NaT)\s*<", page))
        body = ov.campus_body(s, theme, {"campus": "Test", "theme": None})
        check("%s: a room chip opens that room on this campus" % theme,
              'href="?campus=Test&amp;room=SW+Room+1#roomdetail"' in body
              or 'href="?campus=Test&room=SW+Room+1#roomdetail"' in body)
        check("%s: outside is folded away, and says it is not counted"
              % theme, "<details" in body and "never counted" in body)
        check("%s: the walk card says what to check" % theme,
              "Worth a walk" in body and "SW Room 0" in body)
        # 12 Nov, Shamroze: one click to only the rooms worth a look.
        items = ov.walk_items(s, [{"room": "SW Room 1", "waste": True}],
                              {"SW Room 0": "Ground floor"})
        check("%s: a unit seen running in an empty room comes first" % theme,
              [i["name"] for i in items][:1] == ["SW Room 1"])
        check("%s: each room once, the walk list after it" % theme,
              len({i["name"] for i in items}) == len(items)
              and "SW Room 0" in [i["name"] for i in items])
        button = ov.walk_button(theme, len(items), {"campus": "Test"})
        check("%s: the button opens only those rooms" % theme,
              "only=walk" in button and "worth a look" in button)
        check("%s: the front page's card links straight to the list" % theme,
              "only=walk" in page and "worth a look" in page)
        check("%s: no rooms, no button" % theme,
              ov.walk_button(theme, 0, {"campus": "Test"}) == "")
        just = ov.walk_page(theme, items, {"campus": "Test"})
        check("%s: the list has the rooms, their floor and a way back"
              % theme, "SW Room 0" in just and "Ground floor" in just
              and "the whole building" in just)
        anchors_w = re.findall(r"<a [^>]*>", just + button)
        check("%s: and its links stay in this tab" % theme,
              all('target="_self"' in a for a in anchors_w))
        # Streamlit opens a markdown link in a new tab unless the anchor
        # names its own target: entering a campus opened a second copy.
        anchors = re.findall(r"<a [^>]*>", page + body)
        check("%s: every link stays in this tab" % theme,
              anchors and all('target="_self"' in a for a in anchors),
              [a for a in anchors if 'target="_self"' not in a][:2])
    chart = ov.area_chart(s, ov.TOKENS["dark"])
    check("no words inside the stretched SVG -- they would stretch too",
          "<text" not in chart)
    check("every quarter hour up to now can be hovered",
          chart.count('class="hit"') == now_slot + 1,
          chart.count('class="hit"'))
    bar = ov.strip(sw["slots"], ov.TOKENS["dark"], now_slot)
    widths = sum(int(w) for w in re.findall(r'width="(\d+)"', bar))
    check("a strip covers the whole day exactly", widths == 96, widths)
    check("a name with an ampersand is escaped, not broken",
          "&amp;" in ov.esc("Outside & plant") and
          "<b>" not in ov.esc("<b>"))
    check("the theme switch keeps the campus",
          ov.link({"campus": "141-C/D"}, theme="light")
          == "?campus=141-C%2FD&theme=light")
    check("and dark, the default, drops out of the address",
          ov.link({"campus": "141-C/D", "theme": "light"}, theme=None)
          == "?campus=141-C%2FD")

    print()
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
