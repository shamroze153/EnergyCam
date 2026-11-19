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

    # ---- night rounds are not a department's day (19 Nov) -------------------
    # Disrupt Labs read "In 1:06 night": one person seen for ten minutes at a
    # time, every twenty, merged into one stay. Its day is its first stay
    # from DAY_OPENS_AT; the night is said apart.
    def room_row(name, dept, status, people):
        return {"room": name, "zone": "Offices", "dept": dept,
                "status": status, "people": people, "level": "Green",
                "headline": "", "sub": "", "ac": "hidden", "has_unit": True,
                "alerts": True, "empty_since": at(12), "occupied_since": at(9)}
    night_rooms = pd.DataFrame([room_row("Labs A", "Labs", "occupied", 2),
                                room_row("Store", "Night Only", "empty", 0)])
    night_events = pd.DataFrame([
        (at(0, 0, -2), "Labs A", "empty", 0),
        # As in the Basement that night: blips under ten minutes apart,
        # one merged stay of 56 minutes -- longer than an "early visit".
        (at(1, 6), "Labs A", "occupied", 1), (at(1, 23), "Labs A", "empty", 0),
        (at(1, 32), "Labs A", "occupied", 1), (at(1, 45), "Labs A", "empty", 0),
        (at(1, 53), "Labs A", "occupied", 1), (at(2, 2), "Labs A", "empty", 0),
        (at(9, 30), "Labs A", "occupied", 2),
        (at(0, 0, -2), "Store", "empty", 0),
        (at(2, 0), "Store", "occupied", 1), (at(2, 40), "Store", "empty", 0),
    ], columns=["timestamp", "room", "status", "people"])
    ns = ov.campus_summary("Test", night_rooms, night_events, None, NOW)
    nd = {d["name"]: d for d in ns["depts"]}
    labs = nd["Labs"]
    check("night rounds: the department's day starts with its morning",
          (labs["starts"], labs["night"]) == (at(9, 30), at(1, 6)),
          (labs["starts"], labs["night"]))
    card = ov._dept_card(labs, ov.TOKENS["light"], ov.now_slot(ns))
    check("  and the card says the morning, and the night apart",
          ("In <b>%s</b>" % ov.clock(at(9, 30))) in card
          and "night visits from" in card, card[:200])
    check("  so the campus opened with it",
          (ns["first_in"], ns["first_who"]) == (at(9, 30), "Labs"),
          (ns["first_in"], ns["first_who"]))
    only = nd["Night Only"]
    check("a department seen only at night has no day yet",
          (only["starts"], only["night"]) == (None, at(2, 0)),
          (only["starts"], only["night"]))
    check("  and says so",
          "Night visits only" in ov._dept_card(only, ov.TOKENS["light"],
                                               ov.now_slot(ns)))

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

    # ---- the greeting by the Karachi clock (19 Nov: "Good afternoon" at
    # 1:50 in the night) --------------------------------------------------
    said = [ov.greeting(pd.Timestamp("2026-11-19 %02d:30" % h, tz=ov.LOCAL))
            for h in (1, 4, 6, 13, 18, 22)]
    check("night, morning, afternoon, evening, night by the clock",
          said == ["Good night", "Good night", "Good morning",
                   "Good afternoon", "Good evening", "Good night"], said)

    # ---- the cameras went dark before the rooms did (17 Nov) ---------------
    def every5(a, b):
        out, t = [], a
        while t < b:
            out.append(t)
            t += pd.Timedelta(minutes=5)
        return out
    whole = every5(at(0, 0, -1), NOW)
    w = ov.campus_summary("Test", rooms(), events(), whole, NOW)
    check("watched all evening: the last-out stands",
          (w["last_out_yday"], w["watch_ended"]), (at(21, 40, -1), None))
    dark = every5(at(0, 0, -1), at(21, 35, -1)) + every5(at(9), NOW)
    d = ov.campus_summary("Test", rooms(), events(), dark, NOW)
    check("the laptop slept at 21:35: last out is not known",
          (d["last_out_yday"], d["watch_ended"] is not None), (None, True))
    check("and the page says when the cameras went off",
          ov.last_out_text(d)[0] == "not known"
          and ov.last_out_text(d)[1].startswith("cameras off from"),
          ov.last_out_text(d))
    check("an ordinary evening still reads as a time",
          ov.last_out_text(w)[1], "last room emptied")

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
              "Worth a look" in body and "SW Room 0" in body)
        # 19 Nov: one word for it -- the card said "worth a walk" over a
        # link saying "worth a look".
        check("%s: never 'worth a walk' on the front page or the campus"
              % theme, "worth a walk" not in (page + body).lower(),
              re.findall(r".{20}worth a walk.{10}", (page + body).lower())[:1])
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
    # 19 Nov: from Savings on 140-H, the 141-C/D pill (and Light/Dark)
    # landed on 141's Overview -- the tab open is carried across now.
    head = ov.campus_head({"name": "140-H"}, ["140-H", "141-C/D"], "light",
                          "M", "Live", True, "now",
                          {"campus": "140-H", "theme": "light"},
                          {"view": "Savings & peak"})
    hrefs = re.findall(r'href="([^"]*)"', head)
    check("a switch of campus keeps the tab open",
          "?campus=141-C%2FD&theme=light&view=Savings+%26+peak" in hrefs,
          hrefs)
    check("and so does Light/Dark",
          "?campus=140-H&theme=dark&view=Savings+%26+peak" in hrefs, hrefs)
    # Light is the default (17 Nov): "Dark" must say dark, and "Light" may
    # drop the theme. It sent theme=None and the page stayed light.
    dark = ov.campus_head({"name": "140-H"}, ["140-H"], "dark", "M", "Live",
                          True, "now", {"campus": "140-H", "theme": "dark"})
    check("the Dark button opens the dark page",
          'href="?campus=140-H&theme=dark">Dark<' in head.replace(
              "&view=Savings+%26+peak", ""), hrefs)
    check("and the Light button the light one",
          'href="?campus=140-H">Light<' in dark)
    check("All campuses goes to the front page, not a tab",
          "?theme=light&view=Savings+%26+peak" not in hrefs
          and any(h.startswith("?theme=light") for h in hrefs), hrefs)
    plain = ov.campus_head({"name": "140-H"}, ["140-H", "141-C/D"], "light",
                           "M", "Live", True, "now",
                           {"campus": "140-H", "theme": "light"})
    check("with no tab to keep, the links are as before",
          "?campus=141-C%2FD&theme=light"
          in re.findall(r'href="([^"]*)"', plain))

    print()
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
