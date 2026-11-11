"""Ask a recorder what it is, without logging in.

    python rtsp_hello.py 192.168.67.59
    python rtsp_hello.py 192.168.67.59:5540

When the scanner gets "no stream" on a port that is open, it cannot tell a
wrong path from a wrong password: the camera library only says that it did
not work. The recorder itself says much more, to anyone who asks. This sends
the two questions every video player sends first -- what can you do, and
describe the stream -- with no user name and no password, and prints the
answer: whether it is video at all, what the server calls itself, and how it
wants a login done. A question with no login in it is not a failed login, so
this can be run as often as needed without locking the account.
"""
import socket
import sys

from test_camera import split_host

# What each make tends to put in its Server header or its login realm.
# Lower case; any one is enough.
SIGNS = [
    ("dahua", ("dahua", "login to ", "dh-", "dhip")),
    ("hikvision", ("hikvision", "hikvisionrealserver", "ip camera(",
                   "hipcam")),
    ("xmeye", ("h264dvr", "xmeye", "xiongmai", "sofia", "jufeng")),
    ("uniview", ("uniview", "unv ")),
]


def ask(host, timeout=4.0):
    """OPTIONS then DESCRIBE, each on its own connection, no credentials."""
    name, port = split_host(host)
    url = "rtsp://%s:%d/" % (name, port)
    answers = []
    for cseq, method in ((1, "OPTIONS"), (2, "DESCRIBE")):
        req = ("%s %s RTSP/1.0\r\nCSeq: %d\r\nUser-Agent: EnergyCam\r\n"
               % (method, url, cseq))
        if method == "DESCRIBE":
            req += "Accept: application/sdp\r\n"
        req += "\r\n"
        data = b""
        try:
            with socket.create_connection((name, port), timeout) as s:
                s.settimeout(timeout)
                s.sendall(req.encode("ascii"))
                while b"\r\n\r\n" not in data and len(data) < 8192:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
        except OSError as e:
            answers.append((method, "no answer (%s)" % type(e).__name__, {}))
            continue
        head = data.split(b"\r\n\r\n", 1)[0].decode("latin-1", "replace")
        lines = head.split("\r\n") if head else [""]
        headers = {}
        for line in lines[1:]:
            key, sep, value = line.partition(":")
            if sep:
                headers.setdefault(key.strip().lower(), []).append(
                    value.strip())
        answers.append((method, lines[0].strip() or "(empty reply)", headers))
    return answers


def guess(answers):
    text = " ".join(" ".join(v for vs in h.values() for v in vs)
                    for _, _, h in answers).lower()
    for make, signs in SIGNS:
        if any(sign in text for sign in signs):
            return make
    return None


def report(host, tried=()):
    """Print what the recorder said, in plain words. Returns the make.

    tried: the paths the scan has already failed with, so that it does not
    send someone back to run the very scan that just failed.
    """
    answers = ask(host)
    print(">> asked %s what it is (no login sent):" % host)
    spoke_rtsp = False
    for method, status, headers in answers:
        print("   %-8s -> %s" % (method, status))
        spoke_rtsp = spoke_rtsp or status.startswith("RTSP/")
        for key in ("server", "www-authenticate", "public"):
            for value in headers.get(key, []):
                print("              %s: %s" % (key.title(), value[:110]))
    if all(status.startswith("no answer") for _, status, _ in answers):
        print(">> Nothing answered on that port.")
        return None
    if not spoke_rtsp:
        print(">> Something is listening on that port, but it is not a video"
              " (RTSP) server.")
        print("   RTSP is probably on another port: look in the recorder's"
              " network settings.")
        return None
    make = guess(answers)
    if make and any(t == make or t.startswith(make + "-") for t in tried):
        print(">> it calls itself %s, and the %s paths were the ones just"
              " tried." % (make, make))
        print("   So the path is right and the login is not: the user name"
              " or password in .env,")
        print("   or an account that is not allowed to watch live video.")
        print("   Log in on the recorder's own screen with exactly those to"
              " be sure.")
    elif make:
        print(">> it calls itself %s: scan with --brand %s" % (make, make))
    else:
        print(">> it does not say its make. Send this output as it is.")
    return make


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(args) != 1:
        sys.exit(__doc__)
    report(args[0])


if __name__ == "__main__":
    main()
