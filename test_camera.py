"""Check one camera channel on a recorder, the same way the system will.

VLC is more forgiving than what we actually use, so a stream that plays in VLC
can still fail here. This opens it with OpenCV over the same FFMPEG/TCP path as
unified_system.py, saves one frame, and reports what came back.

    python test_camera.py 192.168.67.57 1 energycam MYPASSWORD
    python test_camera.py 192.168.67.57 1 energycam MYPASSWORD --main
    python test_camera.py "rtsp://user:pass@host:554/some/path"

Hikvision numbers its streams <channel><stream>: channel 1 is 101 for the main
stream and 102 for the sub stream, channel 5 is 501 / 502, and so on. The sub
stream is the default here: it is smaller, lighter on the recorder, and enough
to find people. The AC's indicator light may need the main stream; try --main
if the light is too small to see in the saved frame.
"""
import os
import sys
import time
from urllib.parse import quote

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
import cv2  # noqa: E402  (must follow the env var above)


def build_url(host, channel, user, password, main=False):
    # The password sits in front of the @ that separates credentials from host,
    # so an @ or # inside it splits the URL in the wrong place unless escaped.
    stream = 1 if main else 2
    return "rtsp://%s:%s@%s:554/Streaming/Channels/%d%02d" % (
        quote(user, safe=""), quote(password, safe=""), host,
        int(channel), stream)


def main():
    args = [a for a in sys.argv[1:] if a != "--main"]
    want_main = "--main" in sys.argv

    if len(args) == 1 and args[0].startswith("rtsp://"):
        url, label = args[0], "custom"
    elif len(args) == 4:
        url = build_url(args[0], args[1], args[2], args[3], want_main)
        label = "ch%s %s" % (args[1], "main" if want_main else "sub")
    else:
        sys.exit(__doc__)

    shown = url
    if "@" in url:                      # keep the password out of the console
        shown = url[:url.index("://") + 3] + "***@" + url.split("@", 1)[1]
    print(">> opening %s" % shown)

    t0 = time.time()
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        print(">> FAILED to open the stream (%.1fs)" % (time.time() - t0))
        print(">> usual causes: wrong password, RTSP disabled on the recorder,")
        print("   this account not allowed to stream, or no route to the host.")
        sys.exit(1)

    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        print(">> connected, but no frame arrived. The channel may be empty,")
        print("   or that camera may be offline on the recorder.")
        sys.exit(1)

    h, w = frame.shape[:2]
    out = "frame_%s.jpg" % label.replace(" ", "_")
    cv2.imwrite(out, frame)
    print(">> OK  %dx%d  in %.1fs  ->  %s" % (w, h, time.time() - t0, out))
    if w < 800:
        print(">> note: this is a small picture. Fine for spotting people, but the")
        print("   AC's indicator light may be too small. Re-run with --main to compare.")


if __name__ == "__main__":
    main()
