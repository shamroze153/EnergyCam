"""Check the room-by-room AC electricity ledger.

    python test_energy_rooms.py
"""
import sys
from datetime import timedelta, timezone

import pandas as pd

import energy_rooms as er

PKT = timezone(timedelta(hours=5))
FAILURES = []
RATES = (67.0, 81.0)
WINDOW = (18.5, 22.5)


def check(label, got, want):
    ok = got == want
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> got %r, wanted %r" % (got, want)))
    if not ok:
        FAILURES.append(label)


def at(h, m=0, day=12):
    return (pd.Timestamp(2026, 11, day).tz_localize(PKT)
            + pd.Timedelta(hours=h, minutes=m)).tz_convert("UTC")


def events(room, rows):
    return pd.DataFrame([{"timestamp": t, "room": room, "status": s,
                          "people": p, "ac_state": ac, "ac_units_on": u}
                         for t, s, p, ac, u in rows])


def room(name, count=1, alerts=True, kw=1.2):
    return {"room": name, "has_unit": True, "alerts": alerts,
            "ac_count": count, "unit_kw": kw, "floor": "Ground floor",
            "dept": "", "tons_total": float(count)}


START, END = at(0), at(24)
ALIVE = [(START, END)]


def main():
    # Read: the cafe's camera saw two units on 10:00-14:00 with people in,
    # then one unit on 14:00-15:00 with the room empty.
    cafe = events("Cafe", [
        (at(0), "empty", 0, "off", 0),
        (at(10), "occupied", 8, "on", 2),
        (at(14), "empty", 0, "on", 1),
        (at(15), "empty", 0, "off", 0)])
    r = er.room_day(cafe, room("Cafe", 6), START, END, ALIVE, 6, RATES,
                    WINDOW, None)
    check("read: the measured units, not every unit in the room",
          round(r["kwh"], 2), round(4 * 2 * 1.2 + 1 * 1 * 1.2, 2))
    check("read: an hour on with nobody in is the waste",
          round(r["waste_kwh"], 2), 1.2)
    check("read: off-peak hours at the off-peak rate",
          round(r["rs"], 2), round((4 * 2 * 1.2 + 1.2) * 67, 2))
    check("read: badge", er.badge(r), "read")

    # Peak minutes cost the peak rate: one unit on 18:00-19:00 is 30 off-peak
    # minutes and 30 peak ones.
    eve = events("Admin", [(at(0), "empty", 0, "off", 0),
                           (at(18), "occupied", 2, "on", 1),
                           (at(19), "occupied", 2, "off", 0)])
    r = er.room_day(eve, room("Admin"), START, END, ALIVE, 1, RATES, WINDOW,
                    None)
    check("the peak half hour at the peak rate", round(r["rs"], 2),
          round(0.6 * 67 + 0.6 * 81, 2))

    # Assumed: nobody reads the unit. People 9:30-13:00 and 14:00-19:00 (an
    # hour's lunch: the AC stays on through it), then a cleaner's round at
    # 21:00 for ten minutes, which switches nothing on.
    hr = events("HR", [
        (at(0), "empty", 0, None, None),
        (at(9, 30), "occupied", 4, None, None),
        (at(13), "empty", 0, None, None),
        (at(14), "occupied", 4, None, None),
        (at(19), "empty", 0, None, None),
        (at(21), "occupied", 1, None, None),
        (at(21, 10), "empty", 0, None, None)])
    r = er.room_day(hr, room("HR", 2), START, END, ALIVE, 0, RATES, WINDOW,
                    None)
    check("assumed: on from settling in to the last leaving",
          round(r["on_h"], 2), 9.5)
    check("assumed: the empty lunch hour is what could have been off",
          round(r["empty_on_h"], 2), 1.0)
    check("assumed: every unit at its rated kW", round(r["kwh"], 2),
          round(9.5 * 2.4, 2))
    check("assumed: badge", er.badge(r), "assumed")

    # Gone three hours in the afternoon: two switch-ons, not one long day.
    long_gap = events("HR", [
        (at(0), "empty", 0, None, None),
        (at(9), "occupied", 3, None, None),
        (at(12), "empty", 0, None, None),
        (at(15), "occupied", 3, None, None),
        (at(17), "empty", 0, None, None)])
    r = er.room_day(long_gap, room("HR"), START, END, ALIVE, 0, RATES,
                    WINDOW, None)
    check("a gap of two hours or more is taken as switched off",
          round(r["on_h"], 2), 5.0)
    check("so none of it is waste", round(r["waste_kwh"], 2), 0.0)

    # Part read: three units, one read. The read one ran 10-12; people were
    # in 10-16, so the other two are assumed on 10-16.
    lc = events("LC", [
        (at(0), "empty", 0, "off", 0),
        (at(10), "occupied", 5, "on", 1),
        (at(12), "occupied", 5, "off", 0),
        (at(16), "empty", 0, "off", 0)])
    r = er.room_day(lc, room("LC", 3), START, END, ALIVE, 1, RATES, WINDOW,
                    None)
    check("part read: the read unit measured, the other two assumed",
          round(r["kwh"], 2), round(2 * 1.2 + 6 * 2 * 1.2, 2))
    check("part read: only the measured part counts as measured",
          round(r["measured_kwh"], 2), 2.4)
    check("part read: badge", er.badge(r), "read 1 of 3")
    check("part read: the assumed units' hours kept apart",
          (round(r["on_h"], 2), round(r["assumed_on_h"], 2)), (2.0, 6.0))

    # The AC line under a room's people, slot by slot (Shamroze, 13 Nov:
    # "was the AC running or off while it sat empty?"). Hourly slots here.
    s = er.ac_slots(cafe, room("Cafe", 6), 6, START, at(16), END, 24, ALIVE)
    check("read: off before ten", s[9], er.OFF)
    check("read: running with people in", s[10], er.ON)
    check("read: running with nobody in is waste", s[14], er.WASTE)
    check("read: off again after three", s[15], er.OFF)
    check("read: still to come after now", s[16], "later")
    unread = events("Cafe", [(at(0), "empty", 0, None, None)])
    check("read room, no reading: not read, never off",
          er.ac_slots(unread, room("Cafe"), 1, START, at(16), END, 24,
                      ALIVE)[5], er.UNREAD)
    s = er.ac_slots(hr, room("HR", 2), 0, START, at(23), END, 24, ALIVE)
    check("assumed: on while people are in", s[10], er.ASSUMED_ON)
    check("assumed: the lunch hour inside the stretch is waste", s[13],
          er.ASSUMED_WASTE)
    check("assumed: the cleaner's round switches nothing on", s[21],
          er.ASSUMED_OFF)
    check("assumed: off before anybody came", s[8], er.ASSUMED_OFF)
    gap = [(START, at(12)), (at(14), END)]
    s = er.ac_slots(cafe, room("Cafe", 6), 6, START, at(16), END, 24, gap)
    check("a stretch nobody watched is blank, not off", s[12], None)
    check("a room with no unit has no AC line",
          er.ac_slots(cafe, {"room": "Lobby", "has_unit": False}, 0, START,
                      at(16), END, 24, ALIVE), [])

    # A server room: cooled all day on purpose.
    dc = events("DC", [(at(0), "empty", 0, None, None)])
    r = er.room_day(dc, room("DC", 1, alerts=False), START, END, ALIVE, 0,
                    RATES, WINDOW, None)
    check("a room cooled around the clock: 24 hours", round(r["on_h"], 2),
          24.0)
    check("and none of it waste", r["waste_rs"], 0.0)

    # Time the loop was not running is not counted.
    half = [(START, at(12))]
    r = er.room_day(cafe, room("Cafe", 6), START, END, half, 6, RATES,
                    WINDOW, None)
    check("unwatched time is left out, not assumed", round(r["kwh"], 2),
          round(2 * 2 * 1.2, 2))

    # A room with no unit is not in the ledger at all.
    check("no unit, no line",
          er.room_day(cafe, {"room": "Lobby", "has_unit": False}, START,
                      END, ALIVE, 0, RATES, WINDOW, None), None)

    # The ledger and its page.
    rooms = pd.DataFrame([room("Cafe", 6), room("HR", 2),
                          dict(room("Lobby"), has_unit=False)])
    both = pd.concat([cafe, hr])
    rows = er.ledger(both, rooms, START, END, None, {"Cafe": 6}, RATES,
                     WINDOW)
    check("the ledger has a line per room with a unit",
          [r["room"] for r in rows], ["HR", "Cafe"])
    t = er.totals(rows)
    check("totals add the rooms up", round(t["kwh"], 2),
          round(sum(r["kwh"] for r in rows), 2))
    html = er.page("light", "AC electricity today", rows, {"campus": "141"},
                   {"rs": t["rs"] * 2}, "yesterday by this time", 3)
    check("the page compares with the day before", "−50% on yesterday" in
          html, True)
    check("the page says what it leaves out", "3 units in rooms no camera"
          in html, True)
    check("the page names each kind", all(w in html for w in (
        ">read<", ">assumed<")), True)
    check("the dark page draws too", er.page("dark", "x", rows, {})
          .startswith("<style>"), True)
    check("an empty ledger draws", "0 kWh" in er.page("dark", "x", [], {}),
          True)

    # A unit that is on draws half its rated kW on average: half the kWh.
    r = er.room_day(hr, room("HR", 2), START, END, ALIVE, 0, RATES, WINDOW,
                    None, duty=0.5)
    check("the duty halves the kWh", round(r["kwh"], 2),
          round(9.5 * 2.4 / 2, 2))
    check("but not the hours", round(r["on_h"], 2), 9.5)
    check("and the room's rated kW is still its rated kW", r["kw"], 2.4)

    # The check against the meters: the latest two days every meter was
    # read, the last save of each day, plus the panels' figure.
    readings = pd.DataFrame([
        {"meter": "gf", "taken": at(17, 38, day=10), "reading": 51282.0},
        {"meter": "gf", "taken": at(17, 46, day=10), "reading": 51282.0},
        {"meter": "ff", "taken": at(17, 46, day=10), "reading": 32744.0},
        {"meter": "gf", "taken": at(16, 49, day=11), "reading": 51505.0},
        {"meter": "ff", "taken": at(16, 49, day=11), "reading": 33003.0},
        {"meter": "ff", "taken": at(9, 0, day=12), "reading": 33100.0}])
    solar = pd.DataFrame([{"taken": at(16, 49, day=11), "kwh": 281.0}])
    w = er.meter_window(readings, ["gf", "ff"], solar)
    check("the meters: grid on both", w["grid"], 482.0)
    check("plus the panels", w["total"], 763.0)
    check("from the last save of the first day", w["from"], at(17, 46, day=10))
    check("a day only one meter was read on is not the end", w["to"],
          at(16, 49, day=11))
    check("one day of readings is no stretch yet",
          er.meter_window(readings[readings["taken"] < at(0, day=11)],
                          ["gf", "ff"], solar), None)
    html = er.page("light", "x", [], {}, check=dict(w, ac_kwh=534.0),
                   duty=0.5)
    check("the page shows the ACs' share of the building", "70%" in html,
          True)
    check("and says what the duty is", "draw 50% of its rated" in html, True)

    # Is it getting better: a column a day, today marked as not whole.
    def tot(rs, waste, kwh=10.0):
        return {"rs": rs, "waste_rs": waste, "kwh": kwh}

    week = [(pd.Timestamp(2026, 11, 9).date(), tot(0, 0, 0), False),
            (pd.Timestamp(2026, 11, 10).date(), tot(9000, 2000), False),
            (pd.Timestamp(2026, 11, 11).date(), tot(9000, 3000), False),
            (pd.Timestamp(2026, 11, 12).date(), tot(8000, 1250), False),
            (pd.Timestamp(2026, 11, 13).date(), tot(3000, 400), True)]
    html = er.trend("light", week)
    check("a day nobody watched is left off the week",
          "Mon 9" in html, False)
    check("the last whole day against the days before it",
          "<b>Thursday</b>: Rs 1,250 ran with nobody in" in html
          and "50% less" in html, True)
    check("today is labelled as not a whole day", "so far" in html, True)
    check("the worst whole day is pointed at", "most wasted" in html, True)
    check("a single day is no trend", er.trend("dark", week[:2]), "")
    # A day the loop watched only part of is drawn but not compared: the
    # first cut called a whole Wednesday "764% worse" than three of those.
    part = [(week[1][0], dict(week[1][1], watched_h=10.4), False),
            (week[2][0], dict(week[2][1], watched_h=23.5), False),
            (week[4][0], dict(week[4][1], watched_h=14.0), True)]
    html = er.trend("light", part)
    check("a part-watched day says how much was watched",
          "10h watched" in html, True)
    check("and is not compared with", "more than" in html
          or "less than" in html, False)
    check("which the page says", "once two whole days" in html, True)
    check("a ledger says how much of it was watched",
          er.totals(er.ledger(cafe, pd.DataFrame([room("Cafe", 6)]), START,
                              END, [START + pd.Timedelta(minutes=m)
                                    for m in range(0, 360, 5)],
                              {"Cafe": 6}, RATES, WINDOW))["watched_h"] < 7,
          True)

    # Who comes when's "empty, with the AC on", across the buildings.
    check("141-C's rooms are 141-C's", er.building({"room": "141-C Cafe",
                                                    "campus": "141"}),
          "141-C")
    check("141's other rooms are its main building",
          er.building({"room": "141 Finance Room", "campus": "141"}),
          "141 main")
    check("140-H is 140-H", er.building({"room": "Marketing",
                                         "campus": "140-H"}), "140-H")
    rooms = pd.DataFrame([dict(room("141-C Cafe", 6), campus="141"),
                          dict(room("HR", 2), campus="140-H")])
    cafe_c = cafe.assign(room="141-C Cafe")
    rows = er.ledger(pd.concat([cafe_c, hr]), rooms, START, END, None,
                     {"141-C Cafe": 6}, RATES, WINDOW)
    b = er.by_building(rows)
    check("buildings in the fixed order", list(b), ["140-H", "141-C"])
    check("each building's waste is its rooms'",
          round(b["141-C"]["waste_kwh"], 2), 1.2)
    two = er.average([rows, [dict(r, waste_rs=0.0, empty_on_h=0.0)
                             for r in rows]])
    check("two days averaged: half the waste",
          round(sum(r["waste_rs"] for r in two), 2),
          round(sum(r["waste_rs"] for r in rows) / 2, 2))
    html = er.empty_page("dark", rows, {"campus": "140-H"}, "Wed 12 Nov")
    check("the empty page lists the room that sat empty with its AC on",
          "141-C Cafe" in html and "HR" in html, True)
    check("a room's link goes to its own campus",
          "campus=141&amp;room=141-C+Cafe" in html, True)
    # The Energy tab at 141 splits its rupees by building too.
    split = er.page("light", "AC today", rows, {"campus": "141"})
    check("the Energy page has a card a building when there are several",
          'class="er-bld"' in split and "141-C" in split and "140-H" in split,
          True)
    alone = er.page("light", "AC today", [r for r in rows
                                          if r["building"] == "140-H"], {})
    check("and none for a single building", 'class="er-bld"' in alone,
          False)
    check("nothing empty, said plainly",
          "No room with a unit sat empty" in er.empty_page(
              "light", [dict(r, empty_on_h=0.0) for r in rows], {}, "x"),
          True)

    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
