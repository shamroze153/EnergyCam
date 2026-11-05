"""Walk every channel on a recorder and save one frame from each.

Mapping a recorder's channels to real rooms by hand is slow: open a channel,
look at it, write it down, open the next. This does the whole recorder in one
command and leaves you a single contact sheet to label.

    python scan_channels.py 192.168.67.57 energycam MYPASSWORD
    python scan_channels.py 192.168.67.57 energycam MYPASSWORD --channels 1-32
    python scan_channels.py 192.168.67.57 energycam MYPASSWORD --main

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

from test_camera import build_url, grab

TILE_W, TILE_H, COLS = 320, 180, 4


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
    print(">> %s, channels %s, %s stream -> %s/"
          % (host, spec, which, outdir))

    tiles, live = [], []
    for ch in channels:
        url = build_url(host, ch, user, password, want_main)
        frame, status = grab(url)
        if frame is not None:
            h, w = frame.shape[:2]
            name = "ch%02d_%s.jpg" % (ch, which)
            cv2.imwrite(os.path.join(outdir, name), frame)
            flat = "  (flat -- dark room, or never decoded)" if (
                status == "flat") else ""
            print("   ch %-3d %dx%d  %s%s" % (ch, w, h, name, flat))
            live.append(ch)
        else:
            print("   ch %-3d %s" % (ch, status))
        tiles.append((ch, frame, status))

    # Draw the sheet from every frame in the folder, not just this pass, so a
    # recorder scanned in two halves still gives one picture of the whole
    # recorder rather than a sheet of only the half scanned last.
    failed = {ch: status for ch, frame, status in tiles if frame is None}
    found = saved_frames(outdir, which)
    sheet_tiles = []
    for ch in sorted(set(found) | set(channels)):
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
        fh.write("#   ac=none    nothing here to switch off: stairs,"
                 " corridor, parking, outdoors\n")
        fh.write("#\n")
        fh.write("# Every channel gets watched either way. The label only"
                 " decides what we can say:\n")
        fh.write("#   ac=yes     empty room and the unit still running ->"
                 " report the waste outright\n")
        fh.write("#   ac=hidden  empty room -> ask someone to walk past and"
                 " check the unit\n")
        fh.write("#   ac=none    left out of the room list\n")
        fh.write("#\n")
        fh.write("# ch 3   = Marketing      ac=yes\n")
        fh.write("#\n")
        for ch in sorted(rows):
            fh.write("ch %-3d = %s\n" % (ch, rows[ch]))

    print(">> %d of %d channels are live" % (len(live), len(channels)))
    if kept:
        print(">> kept %d room name(s) from an earlier pass" % kept)
    print(">> open %s, then fill in %s" % (sheet_path, map_path))


if __name__ == "__main__":
    main()
