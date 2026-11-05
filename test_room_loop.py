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
        ("privacy_blur", types.SimpleNamespace(count_people=lambda *a, **k: 0)),
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
