"""Gather just the frames worth looking at before a camera visit.

A scan folder holds a frame from every camera on a recorder, and most of them
are of no use for this: corridors, stairwells, the car park, the roof. What
decides whether a camera needs moving is the handful of rooms with an air
conditioner in them -- is the unit in shot, and is its indicator light big
enough to read.

So this reads rooms.yaml, picks out the rooms that can raise an alert, copies
their frames into one folder, and names each one after the room instead of a
channel number.

    python collect_ac_frames.py

The rooms that never alert are skipped: the server rooms are not going to be
re-aimed, so their pictures do not need to travel anywhere.

Two things worth keeping in mind about what lands in that folder. These frames
are straight off the recorder, so faces are not blurred -- unlike everything
the running system stores. And a room that is busy right now will have people
in its frame. Before sending any of them on, look at what is in them, and crop
to the air conditioner if that is all somebody needs to see.
"""
import os
import shutil
import sys

import yaml


def find_frame(folder, channel):
    """Prefer the main stream: this is about reading a small indicator light."""
    for which in ("main", "sub"):
        path = os.path.join(folder, "ch%02d_%s.jpg" % (channel, which))
        if os.path.exists(path):
            return path
    return None


def main():
    if not os.path.exists("rooms.yaml"):
        sys.exit("run this from the folder that has rooms.yaml in it")
    cfg = yaml.safe_load(open("rooms.yaml"))
    recorders = cfg["recorders"]

    out = "review_frames"
    os.makedirs(out, exist_ok=True)

    copied, missing, skipped = [], [], 0
    for room in cfg["rooms"]:
        if room["ac"] not in ("visible", "hidden"):
            continue
        if room.get("alert") == "never":
            skipped += 1
            continue
        host = recorders[room["recorder"]]["host"]
        folder = "scan_%s" % host.replace(".", "_")
        for channel in room["channels"]:
            src = find_frame(folder, channel)
            if src is None:
                missing.append("%s ch%d (%s)"
                               % (room["name"], channel, folder))
                continue
            name = "%s_%s_ch%02d.jpg" % (room["recorder"],
                                         room["name"].replace(" ", "_"),
                                         channel)
            shutil.copy2(src, os.path.join(out, name))
            copied.append(name)

    for name in sorted(copied):
        print("   %s" % name)
    print(">> %d frame(s) in %s/" % (len(copied), out))
    if skipped:
        print(">> skipped %d room(s) that never alert" % skipped)
    if missing:
        print(">> not scanned yet:")
        for item in missing:
            print("   %s" % item)
    print(">> faces are not blurred in these. Look before sending them on.")


if __name__ == "__main__":
    main()
