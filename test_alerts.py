"""Check that the alerts stay quiet.

The failure that matters here is not a missed alert. It is an alert that
arrives too often, because that one ends with a filter rule in somebody's
inbox and the system switched off without anybody deciding to switch it off.
So almost everything below is a check that something is NOT said.
"""
import datetime
import sys
import types

for name, module in (
        ("cv2", types.SimpleNamespace(resize=lambda *a, **k: None,
                                      INTER_LINEAR=1)),
        ("dotenv", types.SimpleNamespace(load_dotenv=lambda: None)),
        ("psycopg2", types.SimpleNamespace(Error=Exception, connect=None)),
        ("privacy_blur", types.SimpleNamespace(DETECTOR="yolov8s.pt",
                                               count_people=lambda *a, **k: 0,
                                               people_boxes=lambda *a, **k: [],
                                               anonymize=lambda f, m: f)),
        ("test_camera", types.SimpleNamespace(build_url=lambda *a, **k: "",
                                              grab=lambda *a, **k: (None, "")))):
    sys.modules.setdefault(name, module)

from alerts import Alerter, compose  # noqa: E402
from room_loop import PKT, Room  # noqa: E402

# A Thursday evening: after hours, so the shorter wait applies.
T0 = datetime.datetime(2026, 11, 5, 21, 0, tzinfo=PKT)
FAILURES = []


def at(minutes):
    return T0 + datetime.timedelta(minutes=minutes)


def room(**kw):
    cfg = dict(name="Marketing", recorder="dvr2", channels=[3], ac="visible",
               empty_after_minutes=45)
    cfg.update(kw)
    return Room(cfg)


def check(label, got, want):
    ok = got == want
    print("%-4s %s" % ("OK" if ok else "FAIL", label))
    if not ok:
        FAILURES.append("%s: got %r, wanted %r" % (label, got, want))


def names(rooms):
    return sorted(r.name for r in rooms)


def main():
    # Nothing is said about a room that has not been empty long enough.
    a = Alerter(gather_seconds=0)
    r = room()
    r.observe(0, 1, T0)
    check("a room just gone empty is not mentioned",
          names(a.consider([r], T0)), [])

    # Once it passes the threshold, it is -- once.
    r.observe(0, 1, at(40))
    first = names(a.consider([r], at(40)))
    check("past its threshold it is mentioned", first, ["Marketing"])
    r.observe(0, 1, at(60))
    check("and not again in the same empty period",
          names(a.consider([r], at(60))), [])
    r.observe(0, 1, at(300))
    check("nor hours later, still the same period",
          names(a.consider([r], at(300))), [])

    # Somebody walks in and leaves again, an hour after the last mention:
    # a genuinely new empty period, but inside the two-hour cooldown. This
    # is the chair that reads as a person once an hour, and it must not
    # manufacture a fresh alert each time.
    r.observe(2, 1, at(100))
    r.observe(0, 1, at(101))
    r.observe(0, 1, at(115))          # empty 14 min; after hours that is due
    check("the new period really is due",
          r.due_for_check(at(115)), True)
    check("but inside the cooldown it is still not mentioned",
          names(a.consider([r], at(115))), [])

    # Past the cooldown, the same thing is worth saying again.
    r.observe(3, 1, at(200))
    r.observe(0, 1, at(201))
    r.observe(0, 1, at(215))
    check("past the cooldown a new period is mentioned",
          names(a.consider([r], at(215))), ["Marketing"])

    # Rooms that empty together travel together.
    a = Alerter(gather_seconds=600, min_gap_seconds=0)
    many = [room(name="Room %d" % i) for i in range(3)]
    for r in many:
        r.observe(0, 1, T0)
        r.observe(0, 1, at(40))
    check("the first room alone waits for the others",
          names(a.consider(many, at(40))), [])
    check("and they go as one list once the gathering time is up",
          names(a.consider(many, at(51))), ["Room 0", "Room 1", "Room 2"])

    # A crowd does not wait: six rooms is enough to send at once.
    a = Alerter(gather_seconds=600, min_gap_seconds=0)
    crowd = [room(name="R%d" % i) for i in range(6)]
    for r in crowd:
        r.observe(0, 1, T0)
        r.observe(0, 1, at(40))
    check("six rooms at once do not wait out the gathering time",
          len(a.consider(crowd, at(40))), 6)

    # The floor under everything.
    a = Alerter(gather_seconds=0, min_gap_seconds=900)
    one, two = room(name="One"), room(name="Two")
    one.observe(0, 1, T0)
    two.observe(4, 1, T0)             # Two still has people in it
    one.observe(0, 1, at(40))
    check("the first send goes", names(a.consider([one, two], at(40))), ["One"])
    two.observe(0, 1, at(38))         # Two empties only now
    two.observe(0, 1, at(50))         # and passes its threshold
    check("Two really is due", two.due_for_check(at(50)), True)
    check("but a second send inside the floor does not go",
          names(a.consider([one, two], at(50))), [])
    two.observe(0, 1, at(60))         # a full fifteen minutes after the first
    check("and goes once the floor has passed",
          names(a.consider([one, two], at(60))), ["Two"])

    # A room whose unit is known OFF is the room that got it right.
    a = Alerter(gather_seconds=0)
    off = room(name="Behaving")
    off.observe(0, 1, T0, "off", "1 unit(s) read")
    off.observe(0, 1, at(60), "off", "1 unit(s) read")
    check("an empty room with its unit off is never mentioned",
          names(a.consider([off], at(60))), [])

    on = room(name="Running")
    on.observe(0, 1, T0, "on", "1 unit(s) read")
    on.observe(0, 1, at(60), "on", "1 unit(s) read")
    check("an empty room with its unit on is", names(a.consider([on], at(60))),
          ["Running"])

    # Server rooms and rooms with no unit never appear.
    a = Alerter(gather_seconds=0)
    never = room(name="UPS Room", alert="never", empty_after_minutes=None)
    plain = room(name="Cafe Stairs", ac="none")
    for r in (never, plain):
        r.observe(0, 1, T0)
        r.observe(0, 1, at(600))
    check("a room cooled on purpose is never mentioned",
          names(a.consider([never, plain], at(600))), [])

    # What the mail says, which is as much the product as when it is sent.
    unknown = room(name="Board Room")
    unknown.observe(0, 1, T0)
    unknown.observe(0, 1, at(50))
    subject, body = compose([unknown], at(50))
    check("the subject says it is after hours",
          subject.startswith("[after hours]"), True)
    check("and does not claim cooling it cannot see",
          "cooled" in subject, False)
    check("the body asks rather than asserts",
          "has not been calibrated" in body, True)
    check("and says what the numbers are not",
          "electricity meter" in body, True)

    running = room(name="Board Room")
    running.observe(0, 1, T0, "on", "1 unit(s) read")
    running.observe(0, 1, at(50), "on", "1 unit(s) read")
    subject, body = compose([running], at(50))
    check("with a unit known on, the subject says cooled",
          "cooled" in subject, True)
    check("and the body says switch it off", "Switch it off" in body, True)

    hidden = room(name="Basement Meeting Room", ac="hidden")
    hidden.observe(0, 1, T0)
    hidden.observe(0, 1, at(50))
    _, body = compose([hidden], at(50))
    check("a room whose unit no camera sees says so",
          "not in any camera" in body, True)

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
