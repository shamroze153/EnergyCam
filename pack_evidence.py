"""Pack the evidence folder small enough to send, keeping what matters.

The evidence folder holds a picture of every person the loop counted after
hours, boxes and scores drawn on. A night of it is a few hundred full-size
frames -- far over what a chat upload allows -- and most of them are the
same ghost photographed every two minutes. To say what a ghost is, a
handful of pictures per camera is enough, spread across the night so a
chair that was there at nine and gone at two shows as both.

    python pack_evidence.py                    last 24 hours, every camera
    python pack_evidence.py --hours 12 --per-camera 6

Writes evidence_pack_<time>.zip next to the evidence folder, shrunk to
1280 pixels wide. The pictures are unblurred: the zip goes to whoever is
reviewing it and nowhere else, never into git.
"""
import argparse
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta

import cv2

NAME = re.compile(r"^(?P<cam>.+_ch\d{2})_(?P<at>\d{8}_\d{6})\.jpg$")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--folder", default="evidence")
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--per-camera", type=int, default=8)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--limit-mb", type=float, default=28)
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        sys.exit("no %s folder here -- run this in the project folder"
                 % args.folder)
    since = datetime.now() - timedelta(hours=args.hours)
    cams = {}
    for name in os.listdir(args.folder):
        m = NAME.match(name)
        if not m:
            continue
        at = datetime.strptime(m.group("at"), "%Y%m%d_%H%M%S")
        if at >= since:
            cams.setdefault(m.group("cam"), []).append((at, name))
    if not cams:
        sys.exit("nothing in %s from the last %g hours" % (args.folder,
                                                           args.hours))

    # Evenly spread across the night rather than the first few, so a thing
    # that is counted all night shows up at its start, middle and end.
    chosen = []
    for cam, shots in sorted(cams.items()):
        shots.sort()
        step = max(1, len(shots) / float(args.per_camera))
        picks = sorted({shots[min(len(shots) - 1, int(i * step))][1]
                        for i in range(min(args.per_camera, len(shots)))})
        chosen.extend(picks)
        print("   %-40s %4d picture(s), keeping %d" % (cam, len(shots),
                                                       len(picks)))

    out = "evidence_pack_%s.zip" % datetime.now().strftime("%Y%m%d_%H%M")
    quality = 80
    while True:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for name in chosen:
                im = cv2.imread(os.path.join(args.folder, name))
                if im is None:
                    continue
                if im.shape[1] > args.width:
                    h = int(im.shape[0] * args.width / im.shape[1])
                    im = cv2.resize(im, (args.width, h))
                ok, buf = cv2.imencode(".jpg", im,
                                       [cv2.IMWRITE_JPEG_QUALITY, quality])
                if ok:
                    z.writestr(name, buf.tobytes())
        size = os.path.getsize(out) / 1e6
        if size <= args.limit_mb or quality <= 40:
            break
        quality -= 15
    print("\n>> %s  %.1f MB, %d picture(s) from %d camera(s)"
          % (out, size, len(chosen), len(cams)))
    if size > args.limit_mb:
        print(">> still over %g MB -- run again with --per-camera 4"
              % args.limit_mb)
    print(">> unblurred: send it to the reviewer, never into git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
