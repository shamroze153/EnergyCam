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

    python rtsp_hello.py 192.168.67.59 --env CD_XVR2

With the login from .env it goes one step further, which the scanner cannot:
it asks for channel 1 on each make's path and reads the recorder's answer
to each. 401 means the login is wrong -- and it stops at the first one, so a
wrong password costs one failed login, not a dozen. 404 means the login was
accepted and the path was not, which is no failure at all. 200 is the path.
"""
import hashlib
import os
import re
import socket
import sys

from test_camera import PATHS, build_url, split_host

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


def read_reply(sock):
    """One RTSP reply: status line, headers, and the body it says it has."""
    data = b""
    while b"\r\n\r\n" not in data and len(data) < 16384:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.decode("latin-1", "replace").split("\r\n")
    headers = {}
    for line in lines[1:]:
        key, sep, value = line.partition(":")
        if sep:
            headers[key.strip().lower()] = value.strip()
    want = int(headers.get("content-length", "0") or 0)
    while len(body) < want:
        chunk = sock.recv(4096)
        if not chunk:
            break
        body += chunk
    return lines[0].strip(), headers


def status_code(line):
    match = re.match(r"RTSP/\d\.\d\s+(\d+)", line)
    return int(match.group(1)) if match else 0


def authorization(challenge, method, uri, user, password):
    """The answer to a Digest (or Basic) challenge, as a player would send."""
    if challenge.lower().startswith("basic"):
        import base64
        token = base64.b64encode(
            ("%s:%s" % (user, password)).encode("utf-8")).decode("ascii")
        return "Basic " + token
    fields = dict(re.findall(r'(\w+)="?([^",]*)"?', challenge))
    realm, nonce = fields.get("realm", ""), fields.get("nonce", "")

    def md5(text):
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    ha1 = md5("%s:%s:%s" % (user, realm, password))
    ha2 = md5("%s:%s" % (method, uri))
    if "auth" in fields.get("qop", ""):
        nc, cnonce = "00000001", md5(os.urandom(8).hex())[:16]
        response = md5("%s:%s:%s:%s:auth:%s" % (ha1, nonce, nc, cnonce, ha2))
        return ('Digest username="%s", realm="%s", nonce="%s", uri="%s", '
                'response="%s", qop=auth, nc=%s, cnonce="%s"'
                % (user, realm, nonce, uri, response, nc, cnonce))
    response = md5("%s:%s:%s" % (ha1, nonce, ha2))
    return ('Digest username="%s", realm="%s", nonce="%s", uri="%s", '
            'response="%s"' % (user, realm, nonce, uri, response))


def describe(host, uri, user, password, timeout=5.0):
    """DESCRIBE uri, answering one login challenge. Returns (code, line, logged_in).

    logged_in is True when credentials were actually sent, so that a 401 on
    the second request can be told apart from a recorder that just never
    asked for a login.
    """
    name, port = split_host(host)
    with socket.create_connection((name, port), timeout) as sock:
        sock.settimeout(timeout)
        req = ("DESCRIBE %s RTSP/1.0\r\nCSeq: 1\r\nUser-Agent: EnergyCam\r\n"
               "Accept: application/sdp\r\n\r\n" % uri)
        sock.sendall(req.encode("utf-8"))
        line, headers = read_reply(sock)
        if status_code(line) != 401 or "www-authenticate" not in headers:
            return status_code(line), line, False
        auth = authorization(headers["www-authenticate"], "DESCRIBE", uri,
                             user, password)
        req = ("DESCRIBE %s RTSP/1.0\r\nCSeq: 2\r\nUser-Agent: EnergyCam\r\n"
               "Accept: application/sdp\r\nAuthorization: %s\r\n\r\n"
               % (uri, auth))
        sock.sendall(req.encode("utf-8"))
        line, _ = read_reply(sock)
        return status_code(line), line, True


def find_path(host, user, password, channel=1):
    """Try each make's path for one channel; stop at the first wrong login."""
    name, port = split_host(host)
    print(">> asking for channel %d on each known path, with the login from"
          " .env:" % channel)
    for main in (False, True):
        for brand in PATHS:
            url = build_url(host, channel, user, password, main, brand)
            # The same address the scanner would open, minus the user:pass@
            # in front: the login goes in the Authorization header instead.
            after = url.split("@", 1)[1]
            uri = "rtsp://%s:%d%s" % (name, port, after[after.index("/"):])
            label = "%-10s %s" % (brand, "main" if main else "sub ")
            try:
                code, line, sent = describe(host, uri, user, password)
            except OSError as e:
                print("   %s -> no answer (%s)" % (label, type(e).__name__))
                continue
            print("   %s -> %s" % (label, line or "(empty reply)"))
            if code == 200:
                print(">> this is the path: scan with --brand %s%s"
                      % (brand, "" if not main else " --main"))
                if main:
                    print("   (only the main stream answered on this path)")
                return brand
            if code == 401 and sent:
                print(">> the recorder refused this user name and password.")
                print("   Stopping at the first refusal, so this cost one"
                      " failed login. Check the login on the")
                print("   recorder's own screen, and that the account may"
                      " watch live video.")
                return None
    print(">> the login was accepted, but no known path gave a stream."
          " Send this output as it is.")
    return None


def main():
    argv = sys.argv[1:]
    env_name = None
    if "--env" in argv:
        i = argv.index("--env")
        if i + 1 >= len(argv):
            sys.exit("--env needs a name, such as CD_XVR2")
        env_name = argv[i + 1]
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("-")]
    if len(args) != 1:
        sys.exit(__doc__)
    report(args[0])
    if env_name:
        from dotenv import load_dotenv
        load_dotenv()
        user = os.getenv(env_name + "_USER")
        password = os.getenv(env_name + "_PASS")
        if not user or not password:
            sys.exit("%s_USER and %s_PASS are not both in .env"
                     % (env_name, env_name))
        print()
        find_path(args[0], user, password)


if __name__ == "__main__":
    main()
