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
          label, "COUNT")
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

    # A count that differs is a weaker finding than the other two: the
    # reading can be minutes old and people move.
    label, why = verify_live.verdict(5, 1, 1, page("occupied", 3))
    check("a different count is COUNT, not MISSED", label, "COUNT")
    check("and prints both numbers", "says 3, 5 visible" in why, True)

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
