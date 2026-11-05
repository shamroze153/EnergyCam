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

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|stimeout;6000000")
import cv2  # noqa: E402  (must follow the env var above)


def build_url(host, channel, user, password, main=False):
    # The password sits in front of the @ that separates credentials from host,
    # so an @ or # inside it splits the URL in the wrong place unless escaped.
    stream = 1 if main else 2
    return "rtsp://%s:%s@%s:554/Streaming/Channels/%d%02d" % (
        quote(user, safe=""), quote(password, safe=""), host,
        int(channel), stream)


# A flat frame is almost certainly one the decoder has not filled in yet, so
# this is the line between "still warming up" and "a real picture".
FLAT = 12.0


def grab(url, min_frames=10, max_seconds=6.0, flat=FLAT):
    """Open a stream and return a frame that has actually been decoded.

    H.265 only carries a whole picture in a keyframe; the frames between one
    keyframe and the next say what moved, nothing more. Joining a stream part
    way through means the first reads decode against a reference that was
    never received, and what comes back is a flat grey rectangle with a few
    motion artefacts on it. It is a valid frame as far as OpenCV is concerned,
    which is why reading once and trusting it is wrong.

    So read until the picture has some contrast in it, and keep the last frame
    either way: a genuinely dark room looks flat too, and a dark picture of the
    room is still more use than none.
    """
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        return None, "no stream"

    frame, decoded, misses = None, 0, 0
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        ok, f = cap.read()
        if not ok or f is None:
            misses += 1
            if misses >= 20:
                break
            time.sleep(0.05)
            continue
        misses = 0
        frame, decoded = f, decoded + 1
        if decoded >= min_frames and float(f.std()) >= flat:
            break
    cap.release()

    if frame is None:
        return None, "no frames"
    return frame, "ok" if float(frame.std()) >= flat else "flat"


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
    frame, status = grab(url)
    if status == "no stream":
        print(">> FAILED to open the stream (%.1fs)" % (time.time() - t0))
        print(">> usual causes: wrong password, RTSP disabled on the recorder,")
        print("   this account not allowed to stream, or no route to the host.")
        sys.exit(1)
    if frame is None:
        print(">> connected, but no frame arrived. The channel may be empty,")
        print("   or that camera may be offline on the recorder.")
        sys.exit(1)

    h, w = frame.shape[:2]
    out = "frame_%s.jpg" % label.replace(" ", "_")
    cv2.imwrite(out, frame)
    print(">> OK  %dx%d  in %.1fs  ->  %s" % (w, h, time.time() - t0, out))
    if status == "flat":
        print(">> note: hardly any contrast in this frame. Either the room is")
        print("   dark, or the picture never finished decoding. Run it again.")
    if w < 800:
        print(">> note: this is a small picture. Fine for spotting people, but the")
        print("   AC's indicator light may be too small. Re-run with --main to compare.")


if __name__ == "__main__":
    main()
