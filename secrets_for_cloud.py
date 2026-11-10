"""Print the secrets block for a hosted dashboard, from the .env that works.

Three deploys were spent inventing new passwords, running ALTER ROLE and
retyping connection strings by hand. None of that was necessary: the office
machine already holds a credential that reads this database every day. The
job is to copy that one, not to mint another -- a new password is a new
thing to get wrong, and the error PostgreSQL gives when you do is the same
error it gives when the role does not exist.

So: read .env, convert the string to the form a host needs, and print it
ready to paste.

    python secrets_for_cloud.py

Two conversions it does, which are the two things that go wrong by hand:

  * Supabase's direct host answers only on IPv6. Most hosts speak IPv4, and
    the failure looks exactly like a wrong password. The pooler address is
    the same database over IPv4, and through it the user name carries the
    project reference after a dot -- `energycam_dashboard.abcdefgh`, not
    `energycam_dashboard`.
  * A password is being put inside a URL, so any of @ : / ? # & in it ends
    the field early. Percent-encoding is not optional and is invisible when
    it is missing: the password simply appears to be wrong.

What it prints is a live credential. It goes in the host's secrets box and
nowhere else -- not a chat, not a screenshot, not the repository.
"""
import os
import re
import sys
from urllib.parse import quote, unquote, urlsplit

DIRECT = re.compile(r"^db\.([a-z0-9]+)\.supabase\.co$", re.I)
POOLED = re.compile(r"^(aws|gcp)-\d+-[a-z0-9-]+\.pooler\.supabase\.com$", re.I)


def read_env(path=".env"):
    """The .env file as a dict, without needing python-dotenv."""
    if not os.path.exists(path):
        return {}
    found = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        found[key.strip()] = value.strip().strip('"').strip("'")
    return found


def convert(url, pooler=None):
    """The connection string in the form a host can use.

    Returns (string, notes). Anything it cannot do safely it leaves alone
    and says so, rather than producing a string that looks right.
    """
    notes = []
    parts = urlsplit(url)
    if not parts.hostname or not parts.username:
        return None, ["This does not look like a connection string."]

    # urlsplit hands back what is written in the URL, which for a working
    # string is already percent-encoded. Encoding that again turns %40 into
    # %2540 and the password silently becomes a different password. Decode
    # first, then encode once: a string that was already right survives
    # unchanged, and one that was never encoded gets encoded.
    user = unquote(parts.username)
    password = unquote(parts.password or "")
    host, port = parts.hostname, parts.port or 5432

    direct = DIRECT.match(host)
    if direct:
        ref = direct.group(1)
        if not pooler:
            notes.append(
                "This is the direct host, which answers only on IPv6 and will"
                " fail from most hosts. Re-run with the pooler address from"
                " Supabase -> Project Settings -> Database, e.g."
                " --pooler aws-0-ap-south-1.pooler.supabase.com")
        else:
            host, port = pooler, 5432
            if "." not in user:
                user = "%s.%s" % (user, ref)
                notes.append("Through the pooler the user name carries the"
                             " project reference, so it is now %s" % user)
    elif POOLED.match(host):
        if "." not in user:
            notes.append(
                "This is a pooler address but the user name has no project"
                " reference after a dot, which the pooler needs. It looks"
                " like %s.<project ref>" % user)
    elif pooler:
        notes.append("Host left as it is: it is neither Supabase's direct"
                     " address nor a pooler one.")

    if password != quote(password, safe=""):
        notes.append("The password contains characters that have a meaning"
                     " inside a URL, so it has been percent-encoded. Paste"
                     " the line below exactly; do not retype the password.")

    return ("postgresql://%s:%s@%s:%d%s"
            % (quote(user, safe="."), quote(password, safe=""), host, port,
               parts.path or "/postgres"), notes)


def main():
    pooler = None
    if "--pooler" in sys.argv:
        pooler = sys.argv[sys.argv.index("--pooler") + 1]

    env = read_env()
    url = env.get("DASHBOARD_DATABASE_URL")
    warn = []
    if not url:
        url = env.get("DATABASE_URL")
        warn.append(
            "There is no DASHBOARD_DATABASE_URL in .env, so this is"
            " DATABASE_URL -- the camera machine's credential. It can write,"
            " and on a public address that is the one thing the separate"
            " roles exist to prevent. Use energycam_dashboard instead; the"
            " role already exists.")
    if not url:
        print("No connection string found in .env. Run this in the project"
              " folder on the office machine.")
        return 1

    converted, notes = convert(url, pooler)
    if converted is None:
        for note in notes:
            print(">> %s" % note)
        return 1

    for note in warn + notes:
        print(">> %s\n" % note)

    print("Paste this into the host's secrets box, and nowhere else:")
    print()
    print('DASHBOARD_DATABASE_URL = "%s"' % converted)
    print('DB_SSLMODE = "require"')
    print('DASHBOARD_PASSWORD = "%s"'
          % (env.get("DASHBOARD_PASSWORD") or "choose one, or delete this line"))
    print()
    print("That is a live credential on your screen. Not a chat, not a"
          " screenshot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
