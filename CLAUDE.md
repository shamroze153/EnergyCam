# EnergyCam — notes for Claude

Existing CCTV, used to see which rooms are empty while their air
conditioners run, on two Disrupt campuses in Karachi. Owner: Shamroze.
**Talk to him in short Roman Urdu, step by step, one command at a time.**

## What runs where

* **The loop** — `room_loop.py`, started with `run_rooms.bat --evidence` in an
  Anaconda Prompt on this laptop. Reads `rooms.yaml` **once, at start**: after
  any change to `rooms.yaml`, restart it with `restart_loop.bat --evidence`.
  Never start a second loop beside a running one (the rooms would be written
  twice). Each pass is logged to `cycles.csv`.
* **The dashboard** — `rooms_dashboard.py` (`run_dashboard.bat`), also on
  Streamlit Cloud for phones, which redeploys from GitHub `main` by itself.
  Front pages: `overview.py`; meters/analysis: `energy_view.py`;
  "Who comes when": `day_story.py`, `day_timeline.py`.
* **Campuses** — 140-H (recorders nvr1, nvr4, dvr2, xvr3) and 141-C/D
  (cd_nvr1–4, cd_xvr1 at .77 = 2nd floor rooms 22–29; cd_xvr2 shares
  .59 with another device — an IP conflict, not a bad login: wait for IT
  to move it; .78 is XVR 3 or 4; the DVR is on 192.168.1.64).
  All on 192.168.67.x through the camera cable; the internet is the Wi-Fi.
* **Database** — Supabase. `DATABASE_URL` (energycam_app) writes;
  `DASHBOARD_DATABASE_URL` (energycam_dashboard) reads room history.
* **Detector** — YOLOv8 **small** (`privacy_blur.DETECTOR`, conf 0.25,
  imgsz 1280). `ENERGYCAM_DETECTOR=yolov8n.pt` in `.env` goes back to nano.

## Rules that are never bent

1. **No camera picture ever goes into git.** The repository is public and
   the frames are unblurred people at their desks. `frames/`, `evidence/`,
   `ac_survey/`, `pack_*`, `field_audit_*`, `*.jpg`, `*.zip` are ignored —
   still run `git status` before every commit and look.
2. **Credentials live only in `.env`.** Never print, paste, log or commit a
   password or a database URL. Never put one in a commit message.
3. Do not widen database grants; the camera machine's role stays narrow.
4. Do not change settings on the recorders, and do not retry a refused
   login (XMeye-type recorders lock the account).
5. Work on `main` (that is what `pull.bat` pulls). Run the tests before a
   push; push only green.
6. The 141 gym is ladies-only 15:00–20:00: its camera is never opened then
   (`private_hours` in rooms.yaml; `room_loop.fetch` and every tool honour
   it). Never work around it, and never keep a gym picture from those hours.

Tests: `python test_room_loop.py`, `test_overview.py`, `test_energy.py`,
`test_dashboard.py`, `test_day_story.py`, `test_verify.py`,
`test_integration.py`, `test_audit.py`, `test_ac_detect.py`,
`test_meters.py`, `test_analysis.py`, `test_alerts.py`, `test_empty.py`,
`test_live_ac.py`, `test_floors.py`, `test_energy_rooms.py`, `test_seats.py`.

Where people sit: the loop writes each counted person's place to
`seats/<date>.csv` (numbers only, this machine only). `python seat_map.py`
turns a day of them into seats per room (`seats.txt`) and a picture per
camera in `frames/seats/` -- local, never committed.

How many units run in a room (for "5 of 6 running" and the live kW on the
campus page) goes in `room_events.ac_units_on`, which an administrator adds
once with `sql/09_ac_units.sql`. Until then the loop writes rooms without
it and says so once; restart the loop after the SQL is run.

## Checking the counts are right

* `python field_audit.py` — doctor, `verify_live` (the page against the
  cameras, two rounds, a picture of every disagreement in `frames/verify/`),
  `ac_survey` (full-size frames of every AC room) and, out of working hours,
  `check_room --all` (every detection drawn; at night each one is a ghost).
  One zip at the end.
* `python verify_live.py --room "Creative Room" --rounds 3` — one room.
* `python verify_live.py --room "X" --watch 10` — stand in a room, see it.
* `python collect_pack.py` — six rounds of every camera, ten minutes apart,
  with what the page said each round, in uploadable zips.

Reading `verify_live`: **GHOST** page says people, none visible — often the
loop a pass behind; repeated, it is an object. **MISSED** a person nobody
counted. **FOLLOWING / PASSING / DRIFT / FAINT** are not faults.

Fixing:
* An object read as a person, somewhere **nobody sits** (a chair beyond a
  glass wall, a shoe rack, a coat stand): an `ignore:` box in `rooms.yaml`
  for that camera, in that camera's own frame pixels. Never over a seat
  people use — that hides them too.
* A room's own `conf:` or `conf_after_hours:` (strict only at night) —
  never a building-wide change for one room.
* A squeezed picture (1080N, e.g. 960x1080/1088) is widened in
  `room_loop.ANAMORPHIC`; a new squeezed size goes there.
* A camera looking through glass into the next room: zone the next room.

## Air conditioners

Only units whose display the camera can see can be read; see
`ac_units.yaml`. Calibrating needs the unit switched on and off once:

    python calibrate_room.py --live --room "141 Finance Room" --channel 30 --roi 1083,90,1105,115 --write
    python calibrate_room.py --live --room "141 Room 32 (2nd floor)" --channel 25 --roi 1626,6,1646,28 --write

141 Finance Room, 141 Learning Center, 141 Room 32 and 141-C Cafe are done
(12 Nov, on site with Shamroze). Learning Center and Room 32 have three
units each and one readable (the floor unit's louvres; the flap of the unit
above Room 32's TV); the cafe has six 2-ton towers and five readable on
ch14 by the louvre at the top of each. `unseen_units` in ac_units.yaml
keeps an "off" in those rooms as unknown. 141 Assembly Meeting Room's unit
is in no camera (now `ac: hidden`). The "25"
on Learning Center's split unit is an asset number, not a display -- never
box it. A flap or louvre that opens when the unit runs reads as well as a
display does, and better than a display too small to see.

## A night on its own

Each round, every two hours:

1. `git pull`.
2. `python field_audit.py`; read `field_audit_*/verify.txt` and look at
   the pictures it names (and `frames/*_boxes.jpg` at night).
3. Fix what is clearly wrong, as above. Leave what is uncertain for
   Shamroze, with the picture's file name.
4. Tests, `git status` (no pictures!), commit, push.
5. If `rooms.yaml` changed: `restart_loop.bat --evidence`.
6. Add two or three lines to `docs/night_log.md`: the time, what the
   audit found, what was changed. Commit it.

In the morning: a short Roman Urdu summary — what was found, what was
fixed, what needs a person.
