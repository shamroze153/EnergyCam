"""Does the dashboard match the room right now? Look, and say where it does not.

audit.py reads the record back and finds patterns in it. This asks the
other question, the one a person standing in the building would ask: the
page says this room is empty -- is it?

It grabs a live frame from every camera, counts people with the same
detector and the same settings the loop uses, and puts that beside what the
database currently holds. Where the two disagree it writes the picture out
with the boxes drawn on, so the disagreement can be settled by looking
rather than argued about.

    python verify_live.py                  every room
    python verify_live.py --room "Admin Room"
    python verify_live.py --zone Offices
    python verify_live.py --pictures all   keep a picture of every room

The loop can keep running. This opens its own streams and writes nothing to
the database.

Two kinds of disagreement, and they are not equally serious:

  MISSED   the page says empty, the camera can see somebody. This is the
           one that matters. It is what makes the system ask for the
           cooling to be switched off in a room with people in it, and it
           raises nothing else, so nobody ever looks at that room.

  GHOST    the page says occupied, the camera can see nobody. Noise, and
           money counted against a room that was not being used. Usually a
           poster, a coat, a screen or a reflection, and rooms.yaml takes
           an ignore zone for it.

A count that is one or two different is usually neither: the database holds
the last cycle, which can be a couple of minutes old, and people move. The
age of each reading is printed so that can be judged rather than guessed.

Pictures have faces in them and are not blurred. They stay on this machine.
"""
import argparse
import os
import sys
from datetime import datetime

import cv2
import psycopg2
from dotenv import load_dotenv

from check_room import OUT_DIR, draw
from room_loop import (DETECT_IOU, DETECT_SIZE, fetch, ignored, load_rooms,
                       muffled, recorder_login, set_gates)
from privacy_blur import people_boxes
from schedule import PKT

VERIFY_DIR = os.path.join(OUT_DIR, "verify")


def latest_state(rooms):
    """What the dashboard is showing for each room, and how old it is."""
    load_dotenv()
    url = os.getenv("DASHBOARD_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        sys.exit("No DASHBOARD_DATABASE_URL in .env. This has to read room"
                 " history, which the camera machine's own credential"
                 " cannot do by design.")
    conn = psycopg2.connect(url, sslmode=os.getenv("DB_SSLMODE", "require"),
                            connect_timeout=15)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT ON (room) room, status, people, timestamp"
            "  FROM room_events ORDER BY room, timestamp DESC")
        return {row[0]: {"status": row[1], "people": row[2],
                         "at": row[3]} for row in cursor.fetchall()}
    finally:
        conn.close()


def count_now(room, recorders, model, timeout):
    """People the detector can see in this room right now, and the frames.

    Deliberately the same call the loop makes, with the room's own
    confidence and its ignore zones applied. A verification that counted
    differently from the thing it verifies would prove nothing.
    """
    # muffled() moved out of fetch() when the sweep started doing it once
    # around its parallel grab. This path calls fetch() directly and from
    # one thread, so it does its own -- without it the decoder writes a
    # screenful of "PPS id out of range" between every two rooms and the
    # table cannot be read.
    with muffled():
        frames = fetch(room, recorders, timeout)      # already widened
    most, answered, drawn = 0, 0, []
    for key, frame in frames.items():
        if frame is None:
            continue
        answered += 1
        boxes = people_boxes(frame, model, conf=room.conf,
                             imgsz=DETECT_SIZE, iou=DETECT_IOU)
        zones = room.ignore.get(key) or []
        kept = [b for b in boxes if not ignored(b, zones)]
        # The MAXIMUM across cameras, not the sum -- which is what the loop
        # does, because two cameras watching one room see the same people
        # twice and adding them would invent a crowd. Counting differently
        # from the thing being verified would manufacture disagreements and
        # prove nothing about either.
        most = max(most, len(kept))
        drawn.append((key, draw(frame, boxes, zones),
                      sorted((round(b[4], 2) for b in kept), reverse=True)))
    return most, answered, len(frames), drawn


# A count that differs by this much, with both sides agreeing somebody is
# there, is people moving between two samples rather than a fault.
DRIFT_TOLERANCE = 2

FAULTS = ("MISSED", "GHOST")


def verdict(seen, answered, cameras, state):
    """What to call the difference, if it is one.

    Nobody seen proves nothing unless every camera answered -- the same
    asymmetry the loop itself runs on. A room half of whose cameras are
    down cannot contradict anything.

    The first version of this called everything a disagreement and found
    thirty-three of them in sixty-one rooms, which is not an audit, it is
    noise. Two samples of a building with people walking about in it will
    differ almost everywhere: the loop's reading is up to a cycle old, and
    in a cycle somebody crosses a corridor. So the verdicts now separate
    what is a fault from what is simply two different moments:

      MISSED and GHOST are faults, and only when they repeat.
      DRIFT is the count moving, which decides nothing: occupancy is a
        yes or no, and both sides say yes.
      FOLLOWING means the loop recorded a change while this was looking --
        it is keeping up, which is the opposite of a fault.
    """
    if answered == 0:
        return "NO CAMERA", "no camera answered; nothing can be said"
    status = (state or {}).get("status")
    if status is None:
        return "NOT RECORDED", "the loop has never written this room down"
    if status == "unknown":
        return ("RECOVERED" if answered else "SILENT",
                "the page says nobody looked; %d of %d cameras answered"
                % (answered, cameras))
    page = int((state.get("people") or 0))
    if status == "empty" and seen > 0:
        return "MISSED", ("the page says empty, %d person(s) visible"
                          % seen)
    if status == "occupied" and seen == 0 and answered == cameras:
        return "GHOST", ("the page says %d person(s), none visible on any"
                         " of %d cameras" % (page, cameras))
    if status == "occupied" and abs(seen - page) > DRIFT_TOLERANCE:
        return "DRIFT", "the page says %d, %d visible now" % (page, seen)
    return "MATCH", ""


def one_pass(rooms, recorders, model, timeout, state):
    """Every room once: what was seen, and what to call it."""
    out = {}
    for room in sorted(rooms, key=lambda r: r.name):
        seen, answered, cameras, drawn = count_now(room, recorders, model,
                                                   timeout)
        label, why = verdict(seen, answered, cameras, state.get(room.name))
        out[room.name] = {"seen": seen, "answered": answered,
                          "cameras": cameras, "drawn": drawn,
                          "label": label, "why": why}
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms.yaml")
    ap.add_argument("--room", action="append")
    ap.add_argument("--zone")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--per-recorder", type=int, default=2,
                    help="streams open at once on one recorder (default 2,"
                         " lower than the loop's because the loop is"
                         " probably running too)")
    ap.add_argument("--rounds", type=int, default=2,
                    help="how many times a suspected fault must repeat"
                         " before it is reported (default 2). One sample"
                         " of a building with people walking about in it"
                         " disagrees nearly everywhere and means nothing.")
    ap.add_argument("--pictures", choices=["faults", "all", "none"],
                    default="faults",
                    help="which rooms to write a picture for. The default"
                         " keeps the footage down: a room that agrees"
                         " needs no photograph of the people in it.")
    args = ap.parse_args()

    load_dotenv()
    recorders, rooms = load_rooms(args.config, None, args.room)
    if args.zone:
        rooms = [r for r in rooms if r.zone == args.zone]
    if not rooms:
        sys.exit("no rooms matched")

    # load_rooms reads rooms.yaml, which holds no credentials: the logins
    # live in .env and are attached here, exactly as the loop and
    # check_room.py do it. Every recorder any of these rooms has a camera
    # on, not just each room's own -- a room may be watched across two.
    for key in {rec for room in rooms for rec, _ in room.cameras}:
        if key not in recorders:
            sys.exit("rooms.yaml has a camera on recorder %r but no such"
                     " recorder" % key)
        user, password = recorder_login(key, recorders[key])
        recorders[key]["user"], recorders[key]["password"] = user, password
    # And cap the streams per recorder. The loop is almost certainly running
    # while this does, so this is a second set of connections arriving at
    # the same four machines: without a cap they all pile onto whichever
    # recorder answers first, which is how one of them got locked out once.
    set_gates(recorders, args.per_recorder)

    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")

    before = latest_state(rooms)
    started = datetime.now(PKT)
    print("Live check \u2014 %s, %d room(s), %d round(s)"
          % (started.strftime("%a %d %b %H:%M"), len(rooms), args.rounds))
    print("Looking at every room, then again at anything that looked"
          " wrong...")
    first = one_pass(rooms, recorders, model, args.timeout, before)

    # Only the suspected faults are looked at again. A room that agreed
    # needs no second photograph of the people in it, and re-reading all
    # sixty-one would take another three minutes to confirm what is not in
    # question.
    suspects = [r for r in rooms if first[r.name]["label"] in FAULTS]
    repeats = {}
    for extra in range(max(0, args.rounds - 1)):
        if not suspects:
            break
        print("   round %d: re-checking %d room(s) that looked wrong"
              % (extra + 2, len(suspects)))
        again = one_pass(suspects, recorders, model, args.timeout, before)
        for name, result in again.items():
            repeats.setdefault(name, []).append(result)
        suspects = [r for r in suspects
                    if again[r.name]["label"] == first[r.name]["label"]]

    # The loop is running while this looks. If it wrote a change for a room
    # during the window, it saw what we saw -- that is the system working,
    # and calling it a fault would be exactly backwards.
    after = latest_state(rooms)
    moved = {name for name, row in after.items()
             if (before.get(name) or {}).get("at") != row.get("at")}

    print()
    print("=" * 74)
    print("%-26s %-16s %-10s %s" % ("ROOM", "THE PAGE SAID", "VISIBLE",
                                    "VERDICT"))
    print("-" * 74)

    # A fault is confirmed only if it survived every extra round. The
    # suspect list is narrowed each round, so a room that stopped matching
    # simply has fewer entries than there were rounds.
    confirmed = set()
    for room in rooms:
        name = room.name
        if first[name]["label"] not in FAULTS or name in moved:
            continue
        seen_again = repeats.get(name, [])
        if len(seen_again) < args.rounds - 1:
            continue
        if all(r["label"] == first[name]["label"] for r in seen_again):
            confirmed.add(name)

    counts, faults = {}, []
    for room in sorted(rooms, key=lambda r: r.name):
        result = first[room.name]
        label, why = result["label"], result["why"]

        if label in FAULTS and room.name not in confirmed:
            if room.name in moved:
                label, why = "FOLLOWING", ("the loop recorded a change for"
                                           " this room while we looked")
            else:
                label, why = "PASSING", ("looked wrong once and not again"
                                         " \u2014 somebody moving")
        counts[label] = counts.get(label, 0) + 1
        if label in FAULTS:
            faults.append(room.name)

        # The state the verdict was taken against, not the state at the
        # end. Printing the later one produced rows that cannot be read --
        # "occupied (1), 0 visible, MATCH" -- because the page had said
        # something different at the moment the comparison was made.
        mine = before.get(room.name)
        if mine and mine.get("status"):
            says = "%s %s" % (mine["status"],
                              "" if mine.get("people") in (None, 0)
                              else "(%d)" % mine["people"])
            says = "%-14s" % says.strip()
        else:
            says = "%-14s" % "\u2014"
        print("%-26s %s %-10s %s"
              % (room.name[:26], says,
                 "%d/%d cam" % (result["seen"], result["answered"])
                 if result["answered"] else "none", label))
        if why and label != "MATCH":
            print("%-26s   %s" % ("", why))
        if label in FAULTS:
            # How confident, which is the whole diagnosis. A person found
            # at 0.9 that the loop missed is a timing difference; one found
            # at 0.27 against a 0.25 threshold is a detection that lands
            # some frames and not others, and the room needs a lower
            # confidence or a larger input size rather than a new camera.
            for (rec, channel), _, scores in result["drawn"]:
                if scores:
                    print("%-26s   %s ch%d: %s" % ("", rec, channel,
                                                   ", ".join("%.2f" % v
                                                             for v in scores)))

        keep = (args.pictures == "all"
                or (args.pictures == "faults" and label in FAULTS))
        if keep and result["drawn"]:
            os.makedirs(VERIFY_DIR, exist_ok=True)
            safe = "".join(c if c.isalnum() else "_" for c in room.name)
            for (rec, channel), canvas, scores in result["drawn"]:
                cv2.imwrite(os.path.join(
                    VERIFY_DIR, "%s_%s_ch%02d_%s_%s.jpg"
                    % (label.lower(), safe, channel, rec,
                       started.strftime("%H%M"))), canvas)
            print("%-26s   picture(s) in %s" % ("", VERIFY_DIR))

    print("-" * 74)
    print("FAULTS \u2014 worth acting on")
    for label in FAULTS:
        print("   %-13s %d" % (label, counts.get(label, 0)))
    print("NOT FAULTS")
    for label in ("PASSING", "FOLLOWING", "DRIFT", "MATCH", "NO CAMERA",
                  "NOT RECORDED", "RECOVERED", "SILENT"):
        if counts.get(label):
            print("   %-13s %d" % (label, counts[label]))
    print()
    print("   PASSING    looked wrong once, not on the repeat: somebody")
    print("              walking through between two samples.")
    print("   FOLLOWING  the loop wrote a change for that room while this")
    print("              was looking. It saw what we saw.")
    print("   DRIFT      the count differs by more than %d but both agree"
          % DRIFT_TOLERANCE)
    print("              somebody is there. Occupancy is a yes or no, and")
    print("              both say yes, so nothing is decided wrongly.")

    if faults:
        print("\n%d room(s) to look at: %s" % (len(faults),
                                               ", ".join(faults)))
        print("Open their pictures in %s. If the people are in the frame"
              % VERIFY_DIR)
        print("with no box on them, the detector needs help"
              " (tune_detect.py).")
        print("If they are not in the frame at all, no setting will find"
              " them and")
        print("the camera has to move. A GHOST with nobody in the frame is"
              " a poster,")
        print("a coat, a screen or a reflection: rooms.yaml takes an"
              " ignore zone.")
    else:
        print("\nNo faults that repeated. The loop is tracking the"
              " building.")
    print("\nPictures are unblurred and stay on this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
