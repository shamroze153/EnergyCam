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

## The other way: Tailscale, and no cloud at all

Tailscale puts the phone and the office machine on one small private
network of their own. The phone then opens `http://<laptop>:8501` from
home, from mobile data, from anywhere — as if it were sitting on the
office WiFi. Nothing is published, nothing is hosted, and the occupancy
data never lands on anybody's server: the two devices talk to each other
directly.

The trade is the one above in reverse. Nothing is hosted, so the page is
reachable only while that machine is awake — which, once the always-on
machine exists, it always is.

### Before installing it

This is a company laptop, on a company network, and Tailscale is a way in
to it from outside the building. **Tell IT, and let them agree.** They gave
you the cable; this is the same conversation. A tool installed quietly on a
work machine to reach an internal page from home is the kind of thing that
is fine when asked about and a serious problem when discovered.

The free plan is for personal use. One person reaching their own machine is
what it is for; a team sharing a company dashboard is what the paid tiers
are for. Check the current limits and terms on tailscale.com/pricing rather
than taking a number from here — plans change, and this file does not.

### On the office machine

1. **tailscale.com/download/windows** — install, then sign in with a
   Google, Microsoft or GitHub account. Use an account you will still have
   next year; everything below hangs off it.
2. It joins and takes an address in the 100.64.x–100.127.x range. To see
   it, in any prompt:

   ```
   tailscale ip -4
   ```

   `run_dashboard.bat` prints it too, under **FROM ANYWHERE**, which is the
   easier place to read it.
3. In the Tailscale admin console, **disable key expiry** for this machine.
   Keys expire after a few months by default, and the machine then silently
   drops off the network — on an always-on box nobody logs into, that is a
   dashboard that stops working for a reason nobody will guess.

### On the phone

1. Tailscale from the Play Store or App Store.
2. Sign in with the **same account**.
3. Turn it on. That is the whole of it.

### Then

Open `http://100.x.y.z:8501` in the phone's browser. With MagicDNS on, the
machine's own name works too, which is easier to remember than four
numbers:

```
http://energycam-pc:8501
```

If the page will not load, the port is blocked: Windows treats the
Tailscale adapter as a new network and the firewall follows. One line, in
an Administrator prompt, once:

```
netsh advfirewall firewall add rule name="EnergyCam dashboard" dir=in action=allow protocol=TCP localport=8501
```

`run_dashboard.bat` prints that line as well.

### The password still matters

Tailscale limits *who can reach* the page to devices signed into that
account. It does nothing about a phone left unlocked on a table, and
nothing about the day somebody adds a device to the account to be helpful.
`DASHBOARD_PASSWORD` costs one typing and covers both. Set it.
