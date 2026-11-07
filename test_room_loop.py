"""Check the room state machine without touching a recorder.

This exists because of one specific failure. The single-room system once sent
an alert saying a room was empty while two people were in the snapshot attached
to it. Multiplying that across thirty rooms multiplies the ways it can happen:
a camera that does not answer, a room watched by two cameras where only one
replies, a restart after an hour of downtime.

Every case below is one of those. Run it after changing anything in Room:

    python test_room_loop.py
"""
import datetime
import sys
import types

for name, module in (
        ("cv2", types.SimpleNamespace(resize=lambda *a, **k: None,
                                      INTER_LINEAR=1)),
        ("dotenv", types.SimpleNamespace(load_dotenv=lambda: None)),
        # Stubbed so the state machine can be checked anywhere, including on a
        # machine with no database driver installed. Nothing here touches it.
        ("psycopg2", types.SimpleNamespace(Error=Exception, connect=None)),
        ("privacy_blur", types.SimpleNamespace(count_people=lambda *a, **k: 0,
                                               anonymize=lambda f, m: f)),
        ("test_camera", types.SimpleNamespace(build_url=lambda *a, **k: "",
                                              grab=lambda *a, **k: (None, "")))):
    sys.modules.setdefault(name, module)

from room_loop import PKT, Room  # noqa: E402

T0 = datetime.datetime(2026, 11, 5, 18, 0, tzinfo=PKT)
FAILURES = []


def at(minutes):
    return T0 + datetime.timedelta(minutes=minutes)


def room(**overrides):
    cfg = dict(name="Marketing", recorder="dvr2", channels=[3, 13],
               ac="visible", empty_after_minutes=45)
    cfg.update(overrides)
    return Room(cfg)


def check(label, got, want):
    ok = got == want
    print("%-4s %s" % ("OK" if ok else "FAIL", label))
    if not ok:
        FAILURES.append("%s: got %r, wanted %r" % (label, got, want))


def main():
    # Seeing a person settles it. One camera is enough to prove occupancy.
    r = room()
    r.observe(people=1, answered=1, now=T0)
    check("a person on one of two cameras means occupied", r.status, "occupied")

    # Seeing nobody settles nothing unless every camera looked.
    r = room()
    r.observe(0, 1, T0)
    check("nobody, on one camera of two, is not empty", r.status, "unknown")
    check("  and starts no empty clock", r.empty_since, None)

    r = room()
    r.observe(0, 2, T0)
    check("nobody, on both cameras, is empty", r.status, "empty")
    check("  and starts the clock", r.empty_since, T0)
    r.observe(0, 2, at(44))
    check("44 minutes is not yet 45", r.due_for_check(at(44)), False)
    r.observe(0, 2, at(46))
    check("46 minutes is", r.due_for_check(at(46)), True)

    # A camera dropping out mid-count must stop the clock, not freeze it.
    r = room()
    r.observe(0, 2, T0)
    r.observe(0, 1, at(20))
    check("a camera dropping out clears the clock", r.empty_since, None)
    r.observe(0, 2, at(21))
    check("  and the clock restarts when it returns", r.empty_since, at(21))
    check("  so no alert inherits the earlier minutes",
          r.due_for_check(at(30)), False)

    r = room()
    r.observe(0, 2, T0)
    r.observe(2, 2, at(30))
    check("somebody walking in clears the clock", r.empty_since, None)

    r = room()
    r.observe(0, 2, T0)
    r.observe(0, 0, at(10))
    check("a recorder going away leaves the room unknown", r.status, "unknown")
    check("  with no clock running", r.empty_since, None)

    # The server rooms are cooled on purpose and are empty nearly always.
    r = room(name="UPS Room", channels=[5], alert="never",
             empty_after_minutes=None)
    r.observe(0, 1, T0)
    r.observe(0, 1, at(600))
    check("ten hours empty never makes a server room due",
          r.due_for_check(at(600)), False)

    r = room(name="Cafe Stairs", channels=[1], ac="none",
             empty_after_minutes=None)
    r.observe(0, 1, T0)
    check("a room with no unit is never due", r.due_for_check(at(600)), False)
    check("  but is still counted", r.status, "empty")

    # Operating hours. A room empty for half an hour in the afternoon has
    # somebody in a meeting; the same room empty for half an hour at midnight
    # has nobody coming back, and should not wait the same forty-five minutes.
    afternoon = datetime.datetime(2026, 11, 5, 14, 0, tzinfo=PKT)   # Thursday
    night = datetime.datetime(2026, 11, 5, 23, 30, tzinfo=PKT)
    saturday = datetime.datetime(2026, 11, 7, 14, 0, tzinfo=PKT)
    for label, start in (("a weekday afternoon", afternoon),
                         ("a weekday night", night),
                         ("a Saturday afternoon", saturday)):
        r = room()
        r.observe(0, 2, start)
        r.observe(0, 2, start + datetime.timedelta(minutes=20))
        due = r.due_for_check(start + datetime.timedelta(minutes=20))
        check("20 min empty on %s%s" % (label,
                                        " is due" if due else " is not due"),
              due, label != "a weekday afternoon")

    # The air conditioner. Four states matter, not two: the alert the whole
    # system exists to send is "empty AND still running", and a room that is
    # empty with its unit already off is the outcome we want, not a fault.
    r = room()
    r.observe(0, 2, T0, "off", "1 unit(s) read")
    r.observe(0, 2, at(60), "off", "1 unit(s) read")
    check("empty an hour with the unit off is not due",
          r.due_for_check(at(60)), False)

    r = room()
    r.observe(0, 2, T0, "on", "1 unit(s) read")
    r.observe(0, 2, at(60), "on", "1 unit(s) read")
    check("empty an hour with the unit running is due",
          r.due_for_check(at(60)), True)

    r = room()
    r.observe(0, 2, T0, None, "not calibrated")
    r.observe(0, 2, at(60), None, "not calibrated")
    check("empty an hour with the unit unread is still due",
          r.due_for_check(at(60)), True)

    r = room()
    r.observe(3, 2, T0, "on", "1 unit(s) read")
    check("somebody in the room with the unit on is never due",
          r.due_for_check(at(0)), False)

    # A unit coming on in a room that is already empty has to be written down.
    # If state carried occupancy alone, that moment -- the moment the waste
    # begins -- would look like no change at all and never reach the database.
    r = room()
    r.observe(0, 2, T0, "off", "1 unit(s) read")
    before = r.state()
    r.observe(0, 2, at(5), "on", "1 unit(s) read")
    check("the unit switching on in an empty room is a change",
          r.state() != before, True)

    r = room()
    r.observe(0, 2, T0, "off", "1 unit(s) read")
    before = r.state()
    r.observe(0, 2, at(5), "off", "1 unit(s) read")
    check("nothing changing is not a change", r.state(), before)

    # A calibration pointing at a channel the room does not have would never be
    # read, and a room whose unit is never read looks exactly like a room
    # nobody has calibrated. So it is caught at startup instead.
    from room_loop import check_ac_units
    rooms = [room(name="Admin Room", recorder="dvr2", channels=[9])]
    check("a calibration on a channel the room has is counted",
          check_ac_units({"Admin Room": {"recorder": "dvr2", "channel": 9}},
                         rooms), 1)
    for label, bad in (
            ("a channel the room does not have",
             {"Admin Room": {"recorder": "dvr2", "channel": 11}}),
            ("no channel at all", {"Admin Room": {"recorder": "dvr2"}}),
            ("the wrong recorder",
             {"Admin Room": {"recorder": "nvr4", "channel": 9}})):
        try:
            check_ac_units(bad, rooms)
            check("%s is refused" % label, "accepted", "refused")
        except SystemExit:
            check("%s is refused" % label, "refused", "refused")
    check("a calibrated room not in this run is ignored",
          check_ac_units({"Somewhere Else": {"recorder": "nvr1", "channel": 4}},
                         rooms), 0)

    print()
    if FAILURES:
        print("%d FAILURE(S):" % len(FAILURES))
        for line in FAILURES:
            print("  %s" % line)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
