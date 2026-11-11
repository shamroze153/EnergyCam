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


# Every make puts its channels at a different path, and a recorder answers a
# path it does not know with a refusal that looks exactly like a bad password.
# So the path is something to find out, not to assume.
PATHS = {
    "hikvision": lambda ch, main: "/Streaming/Channels/%d%02d" % (
        ch, 1 if main else 2),
    "dahua": lambda ch, main: "/cam/realmonitor?channel=%d&subtype=%d" % (
        ch, 0 if main else 1),
    "uniview": lambda ch, main: "/unicast/c%d/s%d/live" % (
        ch, 1 if main else 2),
    # XMeye / Xiongmai -- the white-label DVRs with "Net Card", "Media Port"
    # and "HS Download" in their network menu (141-C/D's XVR2). They want
    # the login inside the path rather than in front of the host; the
    # placeholders are filled in by build_url. stream 0 is main, 1 is sub.
    "xmeye": lambda ch, main: ("/user={user}&password={password}"
                               "&channel=%d&stream=%d.sdp?" % (ch, 0 if main else 1)),
    # Newer XMeye firmware turned the & into _ and stopped taking the
    # password as typed: it wants the recorder's own 8-letter scramble of it
    # (sofia_hash below). 141-C/D's XVR2 refused the older form on every
    # channel, which is what this one is here for.
    "xmeye-hash": lambda ch, main: ("/user={user}_password={xmhash}"
                                    "_channel=%d_stream=%d.sdp?real_stream"
                                    % (ch, 0 if main else 1)),
}

# A make whose recorders come in more than one firmware. Asking for the make
# by name tries each in turn on the first channel, then keeps the one that
# answered.
FAMILIES = {"xmeye": ["xmeye", "xmeye-hash"]}


def sofia_hash(password):
    """The scramble XMeye recorders keep instead of the password.

    MD5 of the password, then each pair of bytes added together and mapped
    onto 0-9A-Za-z. The empty password comes out as tlJwpbo6, which is the
    value printed in every XMeye manual, so that is the test of this.
    """
    import hashlib
    digest = hashlib.md5(password.encode("utf-8")).digest()
    out = []
    for i in range(8):
        n = (digest[2 * i] + digest[2 * i + 1]) % 62
        if n < 10:
            out.append(chr(ord("0") + n))
        elif n < 36:
            out.append(chr(ord("A") + n - 10))
        else:
            out.append(chr(ord("a") + n - 36))
    return "".join(out)


def split_host(host, default=554):
    """192.168.67.59 or 192.168.67.59:5540 -- a recorder whose RTSP was moved
    off 554 is written with its port, in rooms.yaml and on the command line."""
    if ":" in host:
        name, port = host.rsplit(":", 1)
        return name, int(port)
    return host, default


def build_url(host, channel, user, password, main=False, brand="hikvision"):
    # The password sits in front of the @ that separates credentials from host,
    # so an @ or # inside it splits the URL in the wrong place unless escaped.
    if brand not in PATHS:
        raise ValueError("unknown make %r; known: %s"
                         % (brand, ", ".join(sorted(PATHS))))
    path = PATHS[brand](int(channel), main)
    path = path.replace("{user}", quote(user, safe="")) \
               .replace("{password}", quote(password, safe="")) \
               .replace("{xmhash}", sofia_hash(password))
    name, port = split_host(host)
    return "rtsp://%s:%s@%s:%d%s" % (
        quote(user, safe=""), quote(password, safe=""), name, port, path)


def mask(url):
    """The console is read over someone's shoulder and pasted into chats.

    Both places a password can sit: in front of the host, and -- for XMeye
    recorders -- inside the path as password=..., which the first version
    of this did not know about and would have printed in full.
    """
    import re
    if "@" in url:
        url = url[:url.index("://") + 3] + "***@" + url.split("@", 1)[1]
    # Up to the next & for the older XMeye form, up to the next _field= for
    # the newer one, whose fields are joined by _ -- a character a password
    # or a user name can also contain, so it is not enough on its own.
    return re.sub(r"(user|password)=.*?(?=&|_password=|_channel=|$)",
                  r"\1=***", url)


def probe(host, channel, user, password, main=False, brand=None,
          verbose=False):
    """Try each make's path until one gives a picture. Returns the make too."""
    status = "no stream"
    if isinstance(brand, (list, tuple)):
        names = list(brand)
    else:
        names = FAMILIES.get(brand, [brand]) if brand else list(PATHS)
    for name in names:
        url = build_url(host, channel, user, password, main, name)
        if verbose:
            print(">> trying %s: %s" % (name, mask(url)))
        frame, status = grab(url, max_seconds=5.0)
        if frame is not None:
            return frame, status, name
    return None, status, None


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
    argv = sys.argv[1:]
    want_main = "--main" in argv
    brand = None
    if "--brand" in argv:
        i = argv.index("--brand")
        if i + 1 >= len(argv):
            sys.exit("--brand needs one of: %s" % ", ".join(sorted(PATHS)))
        brand = argv[i + 1]
        del argv[i:i + 2]
    args = [a for a in argv if a != "--main"]

    t0 = time.time()
    if len(args) == 1 and args[0].startswith("rtsp://"):
        label = "custom"
        print(">> opening %s" % mask(args[0]))
        frame, status = grab(args[0])
    elif len(args) == 4:
        host, channel, user, password = args
        label = "ch%s %s" % (channel, "main" if want_main else "sub")
        frame, status, brand = probe(host, channel, user, password,
                                     want_main, brand, verbose=True)
    else:
        sys.exit(__doc__)

    if frame is None and status == "no stream":
        print(">> no path gave a picture (%.1fs)" % (time.time() - t0))
        print(">> usual causes: wrong password, RTSP disabled on the recorder,")
        print("   this account not allowed to stream, no route to the host,")
        print("   or a make that is not one of: %s" % ", ".join(sorted(PATHS)))
        sys.exit(1)
    if frame is None:
        print(">> connected, but no frame arrived. The channel may be empty,")
        print("   or that camera may be offline on the recorder.")
        sys.exit(1)
    if brand:
        print(">> this recorder speaks %s" % brand)

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
