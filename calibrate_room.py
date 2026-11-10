"""Find and measure the box over an air conditioner's display.

Admin Room was done by hand: two frames, one with the unit running and one
without, then hunt for the pixels that were bright in the first and dark in
the second, draw a box round them, and measure the contrast inside it in both.
That worked, and it is the same nineteen more times, which is exactly the kind
of job that should not be done by hand.

Use it in three steps.

  1. Point the room's camera at the unit and take two frames, one of each
     state. The unit must be clearly on in one and off in the other -- the
     measurement is the difference between them, so two frames of the same
     state produce nothing usable, which this refuses rather than writes.

         python tune_detect.py capture --room "Admin Room" --rounds 1 --label on
         (switch the unit off, wait for the display to go dark)
         python tune_detect.py capture --room "Admin Room" --rounds 1 --label off

  2. Measure. This proposes the box, measures both frames inside it, and
     writes a picture with the box drawn on so you can see it sits over the
     display and not over a light switch or somebody's shirt.

         python calibrate_room.py --room "Admin Room" --channel 9 \\
             --on frames/Admin_Room_ch09_on.jpg \\
             --off frames/Admin_Room_ch09_off.jpg

  3. Look at the preview. If the box is right, run it again with --write to
     put the numbers in ac_units.yaml. If the box landed on the wrong thing,
     pick another from the list it printed with --choice 2, or give your own
     with --roi 352,34,383,67.

What it will not do is write a threshold it cannot defend. If the two states
are too close together, the box is almost certainly on the wrong thing, or the
unit was in the same state in both frames, and a threshold drawn between them
would flip on nothing more than the camera's noise.
"""
import argparse
import io
import os
import re
import sys

import cv2
import numpy as np
import yaml

from ac_detect import (CONFIG, anchor_box, contrast, fingerprint,
                        is_infrared, pack)

PREVIEW_DIR = "frames"
# Below this gap between the two states the box is not telling the two apart.
# Admin Room's real unit gave 35.7, so this is not a tight rule -- it is there
# to catch a box on the wrong object, or two frames of the same state.
MIN_GAP = 8.0
PAD = 3                 # a few pixels round the lit cluster, for camera shake


def grey(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame


def people_in(frames, margin=24):
    """Every box a person stands in, in either frame, a little enlarged.

    Marketing's first preview put all six candidates on people: somebody
    bending over a desk, two at the back, a bag on a desk somebody had
    moved. Between two frames thirty seconds apart, in a room in use, the
    biggest changes are always people, and a person at the far end of an
    open-plan office is small enough to pass the "too big for a display"
    filter. A change that lands on a person is not an air conditioner.

    The model is loaded only here, and only when asked: the rest of this
    tool runs without it.
    """
    from privacy_blur import people_boxes
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    out = []
    for frame in frames:
        h, w = frame.shape[:2]
        for x1, y1, x2, y2, _ in people_boxes(frame, model):
            out.append((max(0, x1 - margin), max(0, y1 - margin),
                        min(w, x2 + margin), min(h, y2 + margin)))
    return out


def overlaps(box, others):
    x1, y1, x2, y2 = box
    return any(x1 < b[2] and b[0] < x2 and y1 < b[3] and b[1] < y2
               for b in others)


def candidates(on, off, limit=6, people=None):
    """Boxes round the things that are lit in one frame and dark in the other.

    Returned best-first. The best is usually the display, but a person who
    moved between the two frames also lights pixels up, so the alternatives
    are printed and a preview is drawn rather than the first one being taken
    on trust.
    """
    on_g, off_g = grey(on).astype(np.int16), grey(off).astype(np.int16)
    gain = on_g - off_g
    if gain.max() < 20:
        return []
    # Bright in the lit frame as well as brighter than before: a display glows,
    # it does not merely change.
    mask = ((gain > max(25, gain.max() * 0.45)) & (on_g > 150)).astype(np.uint8)
    # A display's strokes are not one shape. A seven-segment "22" is six or
    # eight separate bars with dark gaps between them, so labelling the lit
    # pixels as they are returns one box per bar: six narrow boxes down one
    # digit instead of one box round the whole display. Closing the mask first
    # joins pixels within a few of each other, which is the display, and
    # leaves things further apart separate, which is a display and a person.
    joined = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
    count, _, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    height, width = mask.shape
    frame_area = height * width
    found = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if area < 15:
            continue                      # sensor noise
        if w * h > frame_area * 0.02:
            continue                      # too big for a display: a person, a lamp
        box = (max(0, x - PAD), max(0, y - PAD),
               min(width, x + w + PAD), min(height, y + h + PAD))
        if people and overlaps(box, people):
            continue                      # somebody moved; not a unit
        lit, dark = contrast(on, box), contrast(off, box)
        if lit is None or dark is None:
            continue
        found.append({"box": box, "area": int(area), "on": lit, "off": dark,
                      "gap": lit - dark})
    found.sort(key=lambda c: c["gap"], reverse=True)
    return found[:limit]


def draw_preview(on, found, chosen, path):
    canvas = on.copy()
    if canvas.ndim == 2:
        canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    for n, cand in enumerate(found, 1):
        x1, y1, x2, y2 = cand["box"]
        picked = cand["box"] == chosen
        colour = (0, 230, 0) if picked else (0, 160, 255)
        cv2.rectangle(canvas, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), colour, 2)
        cv2.putText(canvas, str(n), (x1 - 2, max(12, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 2)
    if chosen and all(c["box"] != chosen for c in found):
        x1, y1, x2, y2 = chosen
        cv2.rectangle(canvas, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), (0, 230, 0), 2)
    cv2.imwrite(path, canvas)


FILE_HEADER = """\
# Calibrated air-conditioner detection, one block per room.
#
# Kept apart from rooms.yaml on purpose. That file says which camera watches
# which room and is edited by whoever walks the building; this one holds
# measurements taken from two photographs and is edited by whoever did the
# measuring. Mixing them would mean a survey and a calibration arguing over
# the same lines.
#
# Nothing is written here that was not measured. Every block carries the two
# numbers it came from and when they were taken, so a threshold that starts
# misbehaving can be compared against the day it was set rather than argued
# about.

rooms:
"""


def block(room, recorder, channel, size, infrared, label, box, threshold,
          on_std, off_std, on_peak, off_peak, taken, anchor=""):
    """One room, as text, with the reasoning kept beside the numbers."""
    x1, y1, x2, y2 = (int(v) for v in box)
    return """
  %s:
    recorder: %s
    channel: %d
    # The lighting the measurement was taken in. The contrast inside a box
    # depends on it, so a reading under the other kind is refused rather
    # than guessed at.
    expect: %s
    # The frame this box was drawn on. A box is a position in pixels, so it
    # means nothing on a picture of a different size: switch the stream from
    # main to sub and these numbers land somewhere else entirely while still
    # producing a confident answer. Checked before every reading.
    frame_size: [%d, %d]
    units:
      - label: %s
        led_roi: [%d, %d, %d, %d]
        led_std_threshold: %.1f
        # A thumbnail of the unit and the wall round the box, levelled for
        # brightness, compared before every reading. Nudge the camera and the
        # box lands on blank wall, where it reads low contrast for ever and
        # calls a running unit off -- silently, and in the direction nobody
        # notices, because a unit never reported as on sends nobody anywhere.
        anchor: %s
        measured:
          on_std: %.2f          # display lit
          off_std: %.2f          # display blank
          on_peak: %d
          off_peak: %d
          taken: %s
          # A gap of %.1f between the two states. The threshold is the
          # midpoint, so anything inside that gap would read the same.
          # Negative means this unit goes DARK when it runs rather than
          # lighting up, and the reading is taken that way round: the
          # direction is read back off these two numbers, not stored
          # separately, so they cannot disagree with each other.
""" % (room, recorder, channel, "infrared" if infrared else "colour",
       int(size[0]), int(size[1]), label, x1, y1, x2, y2, threshold, anchor,
       on_std, off_std, int(on_peak), int(off_peak), taken, on_std - off_std)


def unit_block(label, box, threshold, on_std, off_std, on_peak, off_peak,
               taken, anchor=""):
    """One unit, as text, to go under a room that already has others.

    A room with five air conditioners is not five rooms. The first version
    of this wrote one unit and refused a second, so the only way to record
    the other four was --replace, which threw away the first -- and the
    only way to find that out was to do it. Five units, one switch-on, four
    silently lost.
    """
    x1, y1, x2, y2 = (int(v) for v in box)
    return """      - label: %s
        led_roi: [%d, %d, %d, %d]
        led_std_threshold: %.1f
        anchor: %s
        measured:
          on_std: %.2f          # display lit
          off_std: %.2f          # display blank
          on_peak: %d
          off_peak: %d
          taken: %s
          # A gap of %.1f between the two states.
""" % (label, x1, y1, x2, y2, threshold, anchor, on_std, off_std,
       int(on_peak), int(off_peak), taken, on_std - off_std)


def add_unit(path, room, label, box, threshold, on_std, off_std, on_peak,
             off_peak, taken, anchor=""):
    """Append one unit to a room already in the file, leaving the rest alone.

    Text again, not a reload-and-dump, for the same reason write_config
    does it: a dump produces valid YAML and deletes every comment, and the
    comments are the reasoning behind each threshold.
    """
    existing = io.open(path, newline="").read()
    lines = existing.splitlines(True)
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^  %s:" % re.escape(room), line):
            start = i
            break
    if start is None:
        sys.exit(">> %s is not in %s yet. Run this without --add first, so"
                 " the room and its first unit are written together."
                 % (room, path))

    # The room ends where the next one at the same indent begins.
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^  \S", lines[i]):
            end = i
            break
    inside = "".join(lines[start:end])
    if "    units:" not in inside:
        sys.exit(">> %s has no units: list to add to." % room)
    if re.search(r"^      - label: %s\s*$" % re.escape(label), inside, re.M):
        sys.exit(">> %s already has a unit called %r. Give this one a"
                 " different --label, so the two can be told apart in an"
                 " alert." % (room, label))

    # Append after the last line of the room block, trimming the blank
    # lines that separate rooms so the new unit lands inside this one.
    body = "".join(lines[start:end]).rstrip("\n") + "\n"
    new = body + unit_block(label, box, threshold, on_std, off_std, on_peak,
                            off_peak, taken, anchor)
    tmp = path + ".tmp"
    with io.open(tmp, "w", newline="\n") as fh:
        fh.write("".join(lines[:start]) + new + "\n"
                 + "".join(lines[end:]).lstrip("\n"))
    os.replace(tmp, path)


def write_config(path, room, recorder, channel, size, infrared, label,
                 box, threshold, on_std, off_std, on_peak, off_peak, taken,
                 replace=False, anchor=""):
    """Add one room, leaving the rest of the file exactly as it was.

    The block is appended as text rather than the file being reloaded and
    dumped back out. A dump would produce valid YAML and silently delete every
    comment in it -- and the comments here are the reasoning behind each
    threshold, which is the part worth keeping. Nineteen rooms through a
    re-dump would leave a file of bare numbers nobody can argue with.
    """
    new = block(room, recorder, channel, size, infrared, label, box,
                threshold, on_std, off_std, on_peak, off_peak, taken, anchor)
    existing = ""
    if os.path.exists(path):
        existing = io.open(path, newline="").read()
    if re.search(r"^  %s:" % re.escape(room), existing, re.M):
        if not replace:
            sys.exit(">> %s is already in %s. Its old block is still there\n"
                     "   with the measurements behind it. To replace it, run\n"
                     "   the same command again with --replace; the old block\n"
                     "   is kept in git, so `git diff %s` shows what changed."
                     % (room, path, path))
        # Cut the old block out: its own line, plus every line indented
        # under it, up to the next room at the same level.
        lines = existing.splitlines(True)
        out, dropping = [], False
        for line in lines:
            if re.match(r"^  %s:" % re.escape(room), line):
                dropping = True
                continue
            if dropping:
                if line.strip() == "" or line.startswith("    ") or \
                        line.startswith("  #") or line.startswith("      "):
                    continue
                dropping = False
            out.append(line)
        existing = "".join(out).rstrip("\n") + "\n"
    if not existing.strip():
        existing = FILE_HEADER
    elif not re.search(r"^rooms:", existing, re.M):
        existing = existing.rstrip("\n") + "\n\nrooms:\n"
    tmp = path + ".tmp"
    with io.open(tmp, "w", newline="\n") as fh:
        fh.write(existing.rstrip("\n") + "\n" + new)
    os.replace(tmp, path)


def ask(prompt):
    """Wait for the person at the keyboard, or give up cleanly."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        sys.exit("\n>> stopped; nothing was written")


def take_both(args):
    """Both frames, from the camera, with the unit switched in between.

    The three-command version worked and nobody will do it nineteen times.
    Every room meant a capture, a walk to the switch, another capture, then
    typing two filenames back in -- and a filename typed wrong measures the
    wrong room without saying so.
    """
    from dotenv import load_dotenv

    from room_loop import (load_rooms, recorder_login, widen)
    from test_camera import build_url, grab

    load_dotenv()
    recorders, rooms = load_rooms(args.rooms, None, [args.room])
    room = rooms[0]
    pair = [c for c in room.cameras if c[1] == args.channel]
    if not pair:
        sys.exit("%s is watched on %s, not channel %d"
                 % (room.name, spell(room), args.channel))
    recorder = pair[0][0]
    rec = recorders[recorder]
    user, password = recorder_login(recorder, rec)
    url = build_url(rec["host"], args.channel, user, password,
                    rec.get("stream", "sub") == "main",
                    rec.get("brand", "hikvision"))

    def shot(what):
        frame, why = grab(url, max_seconds=8.0)
        if frame is None:
            sys.exit(">> no frame came back from %s channel %d (%s). Check the"
                     " cable and the recorder, then try again."
                     % (recorder, args.channel, why))
        wide = widen(frame)
        os.makedirs(PREVIEW_DIR, exist_ok=True)
        path = os.path.join(PREVIEW_DIR, "%s_ch%02d_%s.jpg"
                            % (args.room.replace(" ", "_"), args.channel, what))
        cv2.imwrite(path, wide)
        print("   saved %s  (%dx%d)" % (path, wide.shape[1], wide.shape[0]))
        return wide

    print(">> %s, %s channel %d" % (room.name, recorder, args.channel))
    print()
    print("   1. Switch the air conditioner ON and wait until its display is")
    print("      lit. Stand out of the camera's way.")
    ask("      Press Enter when it is lit: ")
    on = shot("on")
    print()
    print("   2. Now switch it OFF and wait until the display has gone dark.")
    print("      A display that is still fading will read as half lit.")
    ask("      Press Enter when it is dark: ")
    off = shot("off")
    print()
    return on, off


def spell(room):
    if len({rec for rec, _ in room.cameras}) == 1:
        return "channel(s) " + ", ".join(str(c) for _, c in room.cameras)
    return ", ".join("%s ch%d" % c for c in room.cameras)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--room", required=True, help="the room's name in rooms.yaml")
    ap.add_argument("--channel", type=int, required=True,
                    help="the camera that can see the unit")
    ap.add_argument("--recorder", help="only needed if rooms.yaml has no such room")
    ap.add_argument("--live", action="store_true",
                    help="take both frames from the camera now, asking you to"
                         " switch the unit between them. One command per room"
                         " instead of three and two filenames")
    ap.add_argument("--on", help="a frame with the unit running")
    ap.add_argument("--off", help="a frame with it off")
    ap.add_argument("--roi", help="your own box: x1,y1,x2,y2")
    ap.add_argument("--choice", type=int, default=1,
                    help="use the Nth box from the list instead of the first")
    ap.add_argument("--label", default="split unit",
                    help="what to call the unit in the file")
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--rooms", default="rooms.yaml")
    ap.add_argument("--write", action="store_true",
                    help="put the result in ac_units.yaml")
    ap.add_argument("--replace", action="store_true",
                    help="overwrite this room if it is already calibrated")
    ap.add_argument("--no-people-mask", action="store_true",
                    help="do not ignore changes where a person stands. Only"
                         " for an empty room, where loading the detector is"
                         " a waste of time.")
    ap.add_argument("--inverted", action="store_true",
                    help="this unit goes DARK when it runs rather than"
                         " lighting up -- a vent flap opening, or a display"
                         " that switches itself off once running. Measure"
                         " the difference that way round.")
    ap.add_argument("--add", action="store_true",
                    help="add another unit to a room already calibrated,"
                         " instead of replacing it. For a room with more"
                         " than one air conditioner: measure each from the"
                         " same pair of frames with --choice")
    args = ap.parse_args()

    if args.live:
        if args.on or args.off:
            sys.exit("--live takes the frames itself; drop --on and --off")
        on, off = take_both(args)
    else:
        if not (args.on and args.off):
            sys.exit("give --on and --off, or --live to take them now")
        on = cv2.imread(args.on)
        off = cv2.imread(args.off)
        for path, frame in ((args.on, on), (args.off, off)):
            if frame is None:
                sys.exit("cannot read %s" % path)
    if on.shape[:2] != off.shape[:2]:
        sys.exit("the two frames are different sizes (%dx%d and %dx%d). They"
                 " must come from the same camera and the same stream."
                 % (on.shape[1], on.shape[0], off.shape[1], off.shape[0]))

    height, width = on.shape[:2]
    on_ir, off_ir = is_infrared(on), is_infrared(off)
    print(">> %s, channel %d, %dx%d" % (args.room, args.channel, width, height))
    print(">> lighting: on frame %s, off frame %s"
          % ("infrared" if on_ir else "colour",
             "infrared" if off_ir else "colour"))
    if on_ir != off_ir:
        sys.exit(">> the two frames were taken in different lighting -- one in\n"
                 "   colour and one in infrared. The contrast inside a box\n"
                 "   changes with the lighting, so a threshold measured across\n"
                 "   the two would mean nothing. Take both frames with the room\n"
                 "   lights in the same state, then run this again.")

    # Check the room against rooms.yaml here rather than letting the loop find
    # out at startup, so a wrong channel is caught while the frames are still
    # on screen and can be retaken.
    recorder = args.recorder
    if os.path.exists(args.rooms):
        rooms = {r["name"]: r for r in
                 (yaml.safe_load(open(args.rooms)) or {}).get("rooms", [])}
        entry = rooms.get(args.room)
        if entry is None:
            print(">> warning: rooms.yaml has no room called %r, so the loop"
                  " will never read it. Check the spelling." % args.room)
        else:
            recorder = recorder or entry["recorder"]
            if args.channel not in entry["channels"]:
                sys.exit(">> %s is watched on channel(s) %s, not %d. The loop"
                         " only reads the unit on a channel it visits, so this"
                         " would never be read."
                         % (args.room, ", ".join(str(c) for c in
                                                 entry["channels"]),
                            args.channel))
            if entry.get("ac") == "none":
                print(">> warning: rooms.yaml says this room has no unit"
                      " (ac: none). Change it to visible if it does.")
    if not recorder:
        sys.exit("give --recorder, or add the room to rooms.yaml first")

    # Anything that changed where a person stands is that person moving.
    # Found once, from both frames, and handed to every search below.
    people = [] if args.no_people_mask else people_in((on, off))
    if people:
        print(">> %d person box(es) masked out: a change there is somebody"
              " moving, not a unit" % len(people))
    found = candidates(on, off, people=people)
    if args.roi:
        try:
            box = tuple(int(v) for v in args.roi.split(","))
            assert len(box) == 4
        except (ValueError, AssertionError):
            sys.exit("--roi wants four numbers: x1,y1,x2,y2")
    elif candidates(off, on, people=people):
        # Swapping --on and --off is the easy mistake to make, and left alone
        # it reads as "nothing lit up", which sends somebody back to the
        # recorder to retake two perfectly good frames.
        #
        # But it is not always the mistake. Marketing produced this twice,
        # in the right order both times: nothing lights up when those units
        # start, something goes dark instead -- a vent flap opening onto a
        # dark cavity, or a display that switches itself off once the unit
        # is running. Either is a real and repeatable difference between
        # the two states, and --inverted measures it that way round.
        if args.inverted:
            found = candidates(off, on, people=people)
            print(">> inverted: measuring what goes DARK when the unit"
                  " runs, rather than what lights up.")
            if not 1 <= args.choice <= len(found):
                sys.exit("--choice must be between 1 and %d" % len(found))
            box = found[args.choice - 1]["box"]
        else:
            sys.exit(
                ">> nothing lit up going from the off frame to the on"
                " frame,\n"
                "   but plenty does the other way round. Two possibilities,\n"
                "   and the preview will settle which:\n"
                "\n"
                "   1. The frames are swapped -- --on wants the one with"
                " the\n"
                "      unit RUNNING. Retake them in that order.\n"
                "   2. This unit goes dark rather than lighting up: a vent\n"
                "      flap opening, or a display that switches itself off\n"
                "      once the unit is running. Then run the same command\n"
                "      again with --inverted, on the same two frames:\n"
                "\n"
                "        python calibrate_room.py --room %r --channel %d \\\n"
                "            --on %s \\\n"
                "            --off %s --inverted\n"
                "\n"
                "   Look at the preview either way. If the box lands on the\n"
                "   vent or the display it is right; if it lands on a window\n"
                "   or a lamp, the room light changed between the frames and\n"
                "   neither reading means anything."
                % (args.room, args.channel,
                   os.path.join(PREVIEW_DIR, "%s_ch%02d_on.jpg"
                                % (args.room.replace(" ", "_"),
                                   args.channel)),
                   os.path.join(PREVIEW_DIR, "%s_ch%02d_off.jpg"
                                % (args.room.replace(" ", "_"),
                                   args.channel))))
    elif not found:
        sys.exit(">> nothing lit up between the two frames. Either the unit was\n"
                 "   in the same state in both, or its display is not visible to\n"
                 "   this camera. Check the two pictures side by side before\n"
                 "   trying again, and if the display really cannot be seen, set\n"
                 "   this room to ac: hidden in rooms.yaml -- a room whose unit\n"
                 "   cannot be read is better recorded as unreadable than guessed.")
    else:
        if not 1 <= args.choice <= len(found):
            sys.exit("--choice must be between 1 and %d" % len(found))
        box = found[args.choice - 1]["box"]

    if found:
        print(">> %d thing(s) %s between the two frames:"
              % (len(found),
                 "went DARK when the unit started" if args.inverted
                 else "lit up"))
        for n, cand in enumerate(found, 1):
            x1, y1, x2, y2 = cand["box"]
            running, idle = ((cand["off"], cand["on"]) if args.inverted
                             else (cand["on"], cand["off"]))
            print("   %s%d  box %4d,%4d %4d,%4d  %3dx%-3d  running %6.2f"
                  "  off %6.2f  gap %6.2f"
                  % ("*" if cand["box"] == box else " ", n, x1, y1, x2, y2,
                     x2 - x1, y2 - y1, running, idle,
                     abs(running - idle)))

    on_std, off_std = contrast(on, box), contrast(off, box)
    if on_std is None or off_std is None:
        sys.exit("that box is empty -- check the numbers against the picture")
    if off_std > on_std and not args.inverted:
        print(">> the box has MORE contrast with the unit off than on. The two"
              " frames are probably the wrong way round: check --on and --off,"
              " or use --inverted if this unit really does go dark when it"
              " runs.")
    # The gap is how far apart the two states are, whichever way round they
    # sit. An inverted unit has a perfectly good gap in the other direction,
    # and taking it unsigned is what lets the refusal below mean "these two
    # states are indistinguishable" rather than "these two states are the
    # wrong way round".
    gap = abs(on_std - off_std)
    threshold = (on_std + off_std) / 2
    x1, y1, x2, y2 = box
    on_peak = int(grey(on)[y1:y2, x1:x2].max())
    off_peak = int(grey(off)[y1:y2, x1:x2].max())

    print(">> box %d,%d %d,%d  (%dx%d pixels)"
          % (x1, y1, x2, y2, x2 - x1, y2 - y1))
    print(">> contrast inside it:  running %.2f (brightest pixel %d)"
          % (on_std, on_peak))
    print("                        off     %.2f (brightest pixel %d)"
          % (off_std, off_peak))
    print(">> gap %.2f, so the line between them sits at %.1f" % (gap, threshold))

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    preview = os.path.join(PREVIEW_DIR, "%s_ch%02d_box.jpg"
                           % (args.room.replace(" ", "_"), args.channel))
    draw_preview(on, found, box, preview)
    print(">> preview with the box drawn on: %s" % preview)
    print(">> open it and check the green box is over the unit's display.")

    if gap < MIN_GAP:
        sys.exit("\n>> NOT WRITTEN. The gap is only %.2f, which is too small to\n"
                 "   tell the two states apart: anything this close would flip\n"
                 "   on the camera's own noise. Either the box is on the wrong\n"
                 "   thing -- try --choice 2, or --roi with your own numbers --\n"
                 "   or the unit was in the same state in both frames." % gap)

    write = args.write
    if args.live and not write:
        # Re-running in live mode means switching the unit on and off again,
        # and walking back to it. So the question is asked here, once, with
        # the preview already on disk to look at.
        print()
        print(">> Open the preview above. The green box should sit on the"
              " unit's display.")
        answer = ask(">> %s %s? [y/N] "
                     % ("Add this unit to" if args.add else "Write this to",
                        args.config)).strip().lower()
        if answer not in ("y", "yes"):
            print(">> not written. The two frames are kept, so you can try a"
                  " different box without touching the unit again:")
            print("   python calibrate_room.py --room %r --channel %d \\"
                  % (args.room, args.channel))
            print("       --on %s --off %s --choice 2"
                  % (os.path.join(PREVIEW_DIR, "%s_ch%02d_on.jpg"
                                  % (args.room.replace(" ", "_"), args.channel)),
                     os.path.join(PREVIEW_DIR, "%s_ch%02d_off.jpg"
                                  % (args.room.replace(" ", "_"), args.channel))))
            return
        write = True
    if not write:
        print("\n>> nothing written yet. Check the preview, then run the same"
              " command again with --write")
        return

    from datetime import datetime
    from schedule import PKT
    taken = datetime.now(PKT).strftime("%Y-%m-%dT%H:%M%z")
    anchor = pack(fingerprint(off, anchor_box(box, (width, height)),
                              hide=box))
    if args.add:
        add_unit(args.config, args.room, args.label, box, threshold,
                 on_std, off_std, on_peak, off_peak, taken, anchor)
        print("\n>> added %r to %s in %s" % (args.label, args.room,
                                             args.config))
    else:
        write_config(args.config, args.room, recorder, args.channel,
                     (width, height), on_ir, args.label, box, threshold,
                     on_std, off_std, on_peak, off_peak, taken,
                     replace=args.replace, anchor=anchor)
        print("\n>> written to %s" % args.config)
    print(">> restart the loop and this room's air conditioner stops being a"
          " question mark on the dashboard.")


if __name__ == "__main__":
    main()
