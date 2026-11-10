# Seeing it from home

The dashboard reads the database and nothing else. It never touches a camera
— the loop does that, at 140-H, on the cable. So the page itself has no
reason to live on the office network, and putting it somewhere reachable
from home is a deployment question, not an engineering one.

One thing it does not fix, and the one worth being clear about first.

## Hosting does not make it live

The page is live when the **loop** is running. The loop runs at 140-H, on
the machine plugged into the camera VLAN. Host the dashboard in Karachi, in
Frankfurt, anywhere — if the laptop at the office is shut, the page loads
from home and says *silent for 14h*, because that is the truth.

What hosting buys is **reach**: the page opens from a phone, from home, from
a meeting, without being on the office WiFi. What it does not buy is data.
For data after hours there is no substitute for `docs/always_on.md`.

## The door

On the office WiFi the page needs no password: whoever is on that network is
already in the building. Reachable from home, that stops being true, and
what is behind it is not a chart of kilowatts. It is which rooms people sat
in, what time each of them arrived, what time they left, grouped by
department — a record about identified people at work. Since the readings
page was added it can be written to as well.

So before it goes anywhere with a public address, set `DASHBOARD_PASSWORD`.
Unset means no door, which is right for the office desk and wrong for
anything else; the page does not pretend otherwise either way.

It is a shared word, not a login. There are no accounts and no record of who
looked. It keeps out passers-by, search engines and anybody who is forwarded
the link — not a colleague who has been told the word. Where the host offers
its own viewer list, use that **as well**; it is the better lock, this is the
one that works everywhere.

## Streamlit Community Cloud

The repository is public, which is fine: no credential is in it, and the
deploy only needs the code. Everything secret goes in Streamlit's own
secrets box, which is not the repository.

1. **share.streamlit.io** → sign in with GitHub → **New app**
2. Repository `shamroze153/EnergyCam`, branch `main`, main file
   `rooms_dashboard.py`
3. **Advanced settings → Secrets**, paste these three, with your own values:

   ```toml
   DASHBOARD_DATABASE_URL = "postgresql://energycam_dashboard:...@...supabase.com:5432/postgres"
   DB_SSLMODE = "require"
   DASHBOARD_PASSWORD = "something long, not the office WiFi password"
   ```

   `energycam_dashboard`, never `energycam_app`. The camera machine's
   credential cannot read room data by design — that is the point of the
   split, and the answer to a permission error here is the second
   credential, never a wider grant on the first.

4. Deploy. It installs `requirements.txt`, which is the cloud set — no
   OpenCV, no YOLO, because the page counts nobody.
5. In the app's settings, make it **private** and add the people who should
   see it by email, if your account offers that. Do this as well as the
   password, not instead of it.

Supabase needs no change: it is already on the internet, which is how the
laptop reaches it now.

### What will look different up there

- **Look at the rooms** will be empty. It reads `snapshots/` from the disk
  it is running on, and those frames are on the office machine. That is
  deliberate — they are unblurred pictures of people at work and they do not
  belong on a hosting service.
- Everything else — campus, rooms, meters, analysis, history — is database
  only and works unchanged.

## The other way: no cloud at all

If putting occupancy data on somebody else's computer is not wanted, a
private network between the phone and the office machine does the same job
and nothing leaves the building: **Tailscale** or **ZeroTier**, free, an app
on the phone and the same on the laptop. The phone then reaches
`http://<laptop>:8501` from anywhere, exactly as if it were on the office
WiFi.

The trade is the one above in reverse: nothing is hosted, so the page is
reachable only while that machine is awake — which, once the always-on
machine exists, it always is.
