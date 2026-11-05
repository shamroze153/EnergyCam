"""Walk every channel on a recorder and save one frame from each.

Mapping a recorder's channels to real rooms by hand is slow: open a channel,
look at it, write it down, open the next. This does the whole recorder in one
command and leaves you a single contact sheet to label.

    python scan_channels.py 192.168.67.57 energycam MYPASSWORD
    python scan_channels.py 192.168.67.57 energycam MYPASSWORD --channels 1-32
    python scan_channels.py 192.168.67.57 energycam MYPASSWORD --main
    python scan_channels.py 192.168.67.57 energycam MYPASSWORD --brand dahua

Each channel is opened, read, and closed before the next one starts, so the
recorder is never serving more than one stream at a time. That is the same
grab-and-release pattern the room loop will use, so a recorder that survives
this scan will survive the real thing.

Output lands in a folder named after the host: one JPG per live channel,
contact_sheet.jpg with the channel number drawn on every tile, and
channel_map.txt listing the live channels for you to write room names next to.

A channel with no camera on it can take several seconds to give up, so a full
32-channel scan is a couple of minutes. Leave it running.
"""
import glob
import os
import re
import sys

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|stimeout;6000000")
import cv2  # noqa: E402  (must follow the env var above)
import numpy as np  # noqa: E402

from test_camera import PATHS, build_url, grab, probe

TILE_W, TILE_H, COLS = 320, 180, 4

# Recorders number their channels from 1 with no gaps, so a run of dead ones
# means the end of the recorder rather than a run of broken cameras. Stopping
# there matters: a Dahua that is asked for channels it does not have starts
# refusing outright after a while, and a locked-out account looks exactly like
# a wrong password to whoever picks this up next.
STOP_AFTER_DEAD = 4
BRAND_FILE = "recorder.txt"


def remembered_brand(outdir):
    path = os.path.join(outdir, BRAND_FILE)
    if not os.path.exists(path):
        return None
    for line in open(path):
        if line.startswith("brand="):
            brand = line.split("=", 1)[1].strip()
            if brand in PATHS:
                return brand
    return None


def remember_brand(outdir, brand):
    with open(os.path.join(outdir, BRAND_FILE), "w") as fh:
        fh.write("brand=%s\n" % brand)


def parse_channels(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    seen, ordered = set(), []
    for c in out:
        if c >= 1 and c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def contact_sheet(tiles):
    rows = (len(tiles) + COLS - 1) // COLS
    sheet = np.full((rows * TILE_H, COLS * TILE_W, 3), 24, dtype=np.uint8)
    for i, (ch, frame, status) in enumerate(tiles):
        row, col = divmod(i, COLS)
        if frame is not None:
            tile = cv2.resize(frame, (TILE_W, TILE_H))
        else:
            tile = np.full((TILE_H, TILE_W, 3), 40, dtype=np.uint8)
            cv2.putText(tile, status, (10, TILE_H // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1,
                        cv2.LINE_AA)
        cv2.rectangle(tile, (0, 0), (TILE_W - 1, TILE_H - 1), (70, 70, 70), 1)
        cv2.rectangle(tile, (0, 0), (74, 22), (0, 0, 0), -1)
        cv2.putText(tile, "ch %d" % ch, (6, 16), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 255, 255), 1, cv2.LINE_AA)
        y, x = row * TILE_H, col * TILE_W
        sheet[y:y + TILE_H, x:x + TILE_W] = tile
    return sheet


def saved_frames(outdir, which):
    """Every channel already captured in this folder, from any pass."""
    found = {}
    for path in glob.glob(os.path.join(outdir, "ch*_%s.jpg" % which)):
        match = re.match(r"ch(\d+)_", os.path.basename(path))
        if match:
            found[int(match.group(1))] = path
    return found


def load_map(path):
    """Read back whatever room names are already written in the map."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for line in fh:
            if not line.startswith("ch "):
                continue
            head, sep, rest = line.partition("=")
            if not sep:
                continue
            try:
                rows[int(head.split()[1])] = rest.strip()
            except (IndexError, ValueError):
                continue
    return rows


def take_value(argv, flag, default=None):
    if flag not in argv:
        return default
    i = argv.index(flag)
    if i + 1 >= len(argv):
        sys.exit("%s needs a value" % flag)
    value = argv[i + 1]
    del argv[i:i + 2]
    return value


def main():
    argv = sys.argv[1:]
    want_main = "--main" in argv
    spec = take_value(argv, "--channels", "1-16")
    brand = take_value(argv, "--brand")
    if brand and brand not in PATHS:
        sys.exit("--brand must be one of: %s" % ", ".join(sorted(PATHS)))
    stop_after = int(take_value(argv, "--stop-after", STOP_AFTER_DEAD))
    outdir = take_value(argv, "--out")
    args = [a for a in argv if a != "--main"]
    if len(args) != 3:
        sys.exit(__doc__)

    host, user, password = args
    channels = parse_channels(spec)
    if not channels:
        sys.exit("no channels to scan in %r" % spec)
    outdir = outdir or "scan_%s" % host.replace(".", "_")
    os.makedirs(outdir, exist_ok=True)

    which = "main" if want_main else "sub"
    brand = brand or remembered_brand(outdir)
    print(">> %s, channels %s, %s stream -> %s/"
          % (host, spec, which, outdir))
    if brand:
        print(">> %s, from an earlier pass" % brand)

    tiles, live, scanned, dead_run = [], [], [], 0
    for ch in channels:
        scanned.append(ch)
        if brand:
            frame, status = grab(
                build_url(host, ch, user, password, want_main, brand))
        else:
            # Work out the make once, on the first channel that answers, then
            # stop guessing: trying three paths on every dead channel would
            # treble the time a scan spends on the ones with no camera.
            frame, status, found = probe(host, ch, user, password, want_main,
                                         verbose=True)
            if found:
                brand = found
                remember_brand(outdir, brand)
                print(">> this recorder speaks %s; using it for the rest"
                      % brand)
        if frame is not None:
            h, w = frame.shape[:2]
            name = "ch%02d_%s.jpg" % (ch, which)
            cv2.imwrite(os.path.join(outdir, name), frame)
            flat = "  (flat -- dark room, or never decoded)" if (
                status == "flat") else ""
            print("   ch %-3d %dx%d  %s%s" % (ch, w, h, name, flat))
            live.append(ch)
            dead_run = 0
        else:
            print("   ch %-3d %s" % (ch, status))
            dead_run += 1
        tiles.append((ch, frame, status))
        if stop_after and dead_run >= stop_after:
            print(">> %d dead channels in a row -- this is the end of the"
                  " recorder." % dead_run)
            print("   Stopping rather than asking for channels it does not"
                  " have, which is what gets an account locked out.")
            print("   Pass --stop-after 0 to scan the whole range anyway.")
            break

    # Draw the sheet from every frame in the folder, not just this pass, so a
    # recorder scanned in two halves still gives one picture of the whole
    # recorder rather than a sheet of only the half scanned last.
    failed = {ch: status for ch, frame, status in tiles if frame is None}
    found = saved_frames(outdir, which)
    sheet_tiles = []
    for ch in sorted(set(found) | set(scanned)):
        if ch in found:
            sheet_tiles.append((ch, cv2.imread(found[ch]), "ok"))
        else:
            sheet_tiles.append((ch, None, failed.get(ch, "not scanned")))
    sheet_path = os.path.join(outdir, "contact_sheet.jpg")
    cv2.imwrite(sheet_path, contact_sheet(sheet_tiles))

    # A recorder is usually scanned in more than one pass, so keep the room
    # names from the earlier passes instead of starting the map over.
    map_path = os.path.join(outdir, "channel_map.txt")
    rows = load_map(map_path)
    kept = sum(1 for ch in rows if ch not in live and rows[ch])
    for ch in live:
        rows.setdefault(ch, "")
    with open(map_path, "w") as fh:
        fh.write("# %s -- one line per live channel.\n" % host)
        fh.write("#\n")
        fh.write("# Write the room name, then how the air conditioner sits"
                 " in the picture:\n")
        fh.write("#   ac=yes     in frame, near enough to read its"
                 " indicator light or flap\n")
        fh.write("#   ac=hidden  the room has one, but this camera cannot"
                 " see it\n")
        fh.write("#   ac=none    no unit here at all: stairs, corridor,"
                 " parking, outdoors\n")
        fh.write("#\n")
        fh.write("# Every channel gets watched either way. The label only"
                 " decides what we can say:\n")
        fh.write("#   ac=yes     empty room and the unit still running ->"
                 " report the waste outright\n")
        fh.write("#   ac=hidden  empty room -> ask someone to walk past and"
                 " check the unit\n")
        fh.write("#   ac=none    still watched and still counted, but never"
                 " raises an alert\n")
        fh.write("#\n")
        fh.write("# ch 3   = Marketing      ac=yes\n")
        fh.write("#\n")
        for ch in sorted(rows):
            fh.write("ch %-3d = %s\n" % (ch, rows[ch]))

    print(">> %d of %d channels scanned are live"
          % (len(live), len(scanned)))
    if kept:
        print(">> kept %d room name(s) from an earlier pass" % kept)
    print(">> open %s, then fill in %s" % (sheet_path, map_path))


if __name__ == "__main__":
    main()
