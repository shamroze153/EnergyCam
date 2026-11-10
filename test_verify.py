"""Check the live verifier calls the same disagreements a person would.

This tool exists to be believed: it tells somebody their dashboard is
wrong about a room. A verdict that fires when nothing is wrong wastes a
walk; one that stays quiet when a room full of people reads empty leaves
in place the exact fault it was built to catch.

    python test_verify.py
"""
import sys

import verify_live

FAILURES = []


def check(label, got, want):
    ok = got == want
    print("%-4s %s" % ("OK" if ok else "FAIL", label))
    if not ok:
        FAILURES.append("%s: got %r, wanted %r" % (label, got, want))


def page(status, people=None):
    return {"status": status, "people": people}


def main():
    # The one that matters. The page says nobody is there; the camera can
    # see somebody. This is what asks for the cooling to be switched off in
    # a room with people in it.
    label, why = verify_live.verdict(4, 1, 1, page("empty", 0))
    check("empty page, people visible, is MISSED", label, "MISSED")
    check("and the reason says how many", "4 person(s) visible" in why, True)

    # Noise, and money counted against a room nobody used.
    label, _ = verify_live.verdict(0, 2, 2, page("occupied", 1))
    check("occupied page, nobody visible, is GHOST", label, "GHOST")

    # Nobody seen proves nothing unless every camera answered. The loop runs
    # on that asymmetry and so must anything checking it.
    label, _ = verify_live.verdict(0, 1, 3, page("occupied", 2))
    check("with two of three cameras down, GHOST is not claimed",
          label in verify_live.FAULTS, False)
    label, _ = verify_live.verdict(0, 1, 5, page("occupied", 9))
    check("not even when the page's count is far higher",
          label in verify_live.FAULTS, False)
    label, _ = verify_live.verdict(0, 0, 2, page("occupied", 2))
    check("with no camera answering, nothing is claimed",
          label, "NO CAMERA")
    check("not even against a page that says empty",
          verify_live.verdict(0, 0, 1, page("empty", 0))[0], "NO CAMERA")

    # Agreement, including the ordinary case of an empty room.
    check("empty page and nobody visible agree",
          verify_live.verdict(0, 1, 1, page("empty", 0))[0], "MATCH")
    check("the same count agrees",
          verify_live.verdict(3, 1, 1, page("occupied", 3))[0], "MATCH")

    # The count moving decides nothing: occupancy is a yes or no and both
    # sides say yes. The first version called every such room a
    # disagreement and found 33 in 61, which is noise, not an audit.
    check("one person either way is not a finding at all",
          verify_live.verdict(4, 1, 1, page("occupied", 3))[0], "MATCH")
    check("nor two", verify_live.verdict(5, 1, 1, page("occupied", 3))[0],
          "MATCH")
    label, why = verify_live.verdict(9, 1, 1, page("occupied", 3))
    check("a large gap is DRIFT, never MISSED", label, "DRIFT")
    check("and prints both numbers", "says 3, 9 visible" in why, True)
    check("DRIFT is not counted as a fault", "DRIFT" in verify_live.FAULTS,
          False)
    check("MISSED and GHOST are", sorted(verify_live.FAULTS),
          ["GHOST", "MISSED"])

    # Zero visible against an occupied page is a ghost however small the
    # page's count, and must not be softened into drift.
    check("nobody visible is a GHOST, not DRIFT",
          verify_live.verdict(0, 1, 1, page("occupied", 1))[0], "GHOST")
    # And one person against an empty page is MISSED however few.
    check("one person against an empty page is MISSED",
          verify_live.verdict(1, 1, 1, page("empty", 0))[0], "MISSED")

    # A room the loop has never written down is not a disagreement.
    check("a room with no reading is called out as such",
          verify_live.verdict(2, 1, 1, None)[0], "NOT RECORDED")
    check("and so is one whose status is missing",
          verify_live.verdict(2, 1, 1, page(None))[0], "NOT RECORDED")

    # The page saying "nobody looked" while cameras answer is worth seeing:
    # the camera is back and the next cycle will pick it up.
    check("a page that says unknown, with cameras answering, is RECOVERED",
          verify_live.verdict(0, 2, 2, page("unknown"))[0], "RECOVERED")

    # people=None on an occupied row must not crash or read as zero people
    # disagreeing with zero seen.
    check("an occupied row with no count still compares",
          verify_live.verdict(0, 1, 1, page("occupied", None))[0], "GHOST")

    # fetch() reads rec["user"] and rec["password"], which rooms.yaml does
    # not contain -- the logins are in .env and have to be attached first.
    # Missing that is not a wrong answer, it is a KeyError on the first
    # room, after the header has printed. The loop and check_room.py both
    # do it; so must anything else that calls fetch.
    source = open("verify_live.py", encoding="utf-8").read()
    check("the recorders are given their logins before any stream opens",
          "recorder_login(key, recorders[key])" in source, True)
    check("and .env is loaded first", "load_dotenv()" in source, True)
    check("the streams per recorder are capped", "set_gates(" in source,
          True)
    check("logins are attached before the first fetch",
          source.index("recorder_login") < source.index("latest_state(rooms)"),
          True)

    # Every recorder any room has a camera on, not just each room's own:
    # a room can be watched across two, and the second would have no login.
    check("every recorder a camera sits on is covered",
          "for rec, _ in room.cameras" in source, True)

    # The decoder writes its complaints straight to file descriptor 2, past
    # anything Python can intercept. Without muffling, the table is buried
    # in "PPS id out of range" and cannot be read at all.
    check("the grab is muffled so the table stays readable",
          "with muffled():" in source, True)

    # A fault has to repeat, and the loop writing a change for that room
    # while we looked is the loop working, not a fault.
    check("faults are confirmed over more than one round",
          "len(seen_again) < args.rounds - 1" in source, True)
    check("and a room the loop updated meanwhile is not accused",
          "name in moved" in source, True)
    check("only the suspected faults are looked at again",
          "re-checking %d room(s)" in source, True)

    # The table has to show the state the verdict was taken against. It
    # was showing the state at the end, which produced rows nobody can
    # read: "occupied (1), 0 visible, MATCH" -- true only because the page
    # said empty at the moment of comparison and changed afterwards.
    check("the table prints the state the verdict used",
          "mine = before.get(room.name)" in source, True)
    check("and not the one read afterwards",
          "mine = after.get(room.name)" in source, False)

    # The confidence is the whole diagnosis for a MISSED room: 0.9 means a
    # timing difference, 0.27 against a 0.25 threshold means a detection
    # that lands in some frames and not others.
    check("a fault reports how confident the detection was",
          'print("%-26s   %s ch%d: %s"' in source, True)

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
