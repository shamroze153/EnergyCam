# HFM Energy Saving Detection

Uses an existing office CCTV camera to spot a meeting room that is **empty while
the AC is still on**. It emails an alert with a privacy-blurred snapshot and logs
anonymous events (room, occupancy, AC on/off, time) to a cloud Postgres
database (Supabase). A Streamlit dashboard shows live status.

Video and snapshots never leave the building and are never saved to disk.
See [HANDOVER.md](HANDOVER.md) for architecture, privacy controls and hosting.

## Two parts, two requirement files

| Part | Runs on | Install |
|---|---|---|
| Camera system (`unified_system.py`, `heartbeat_watchdog.py`, tools) | Office laptop / server (on-prem) | `pip install -r requirements-local.txt` |
| Dashboard (`dashboard.py`) | Streamlit Community Cloud | `requirements.txt` (installed automatically by Streamlit) |

`requirements.txt` must stay small: only what `dashboard.py` imports. Heavy
packages (ultralytics/torch, opencv) make the Streamlit Cloud build slow or fail.

## Database first

Before the camera system is started for the first time, an administrator runs
`sql/01_schema.sql` and `sql/02_roles.sql` once in the Supabase SQL editor. The
application no longer creates its own tables, and each component connects with its own
least-privilege role rather than one shared password. See
[sql/README.md](sql/README.md) for the run order and which credential goes where.

## Setup (camera system, Windows)

1. `conda activate hfm_energy`
2. `pip install -r requirements-local.txt`
3. Create `.env` with `SENDER_EMAIL`, `APP_PASSWORD`, `RECEIVER_EMAIL`,
   `RTSP_URL`, `DATABASE_URL`. **Never commit `.env`.**
   `DATABASE_URL` here is the **`energycam_app`** connection string — it may write log
   rows and delete expired ones, and nothing else.
4. Run: `python unified_system.py` (or `run_system.bat` for auto-restart)
5. Watchdog (separate window, ideally a different machine):
   `python heartbeat_watchdog.py`, with the **`energycam_watchdog`** string in its own
   `.env`.

## Dashboard

- Local: `streamlit run dashboard.py` (reads `DATABASE_URL` from `.env`)
- Cloud: Streamlit Community Cloud, main file `dashboard.py`, Python 3.11,
  secret `DATABASE_URL = "postgresql://..."` (use Supabase's **Session pooler** URL)
- Use the **`energycam_dashboard`** string, which can only read the `logs` table.

All times on the dashboard are Pakistan time (PKT).

## One-time upgrade (old version -> this version)

1. Stop the old `unified_system.py`.
2. `pip install -r requirements-local.txt` (adds `tzdata` for Pakistan time).
3. Run `sql/one_time_upgrade.sql` **once** in Supabase SQL Editor (fixes old
   rows saved 5 hours ahead, drops the unused `phone_count` column).
4. Start the new version.

## Calibrating a room's air conditioner

Until a room is calibrated the loop records its occupancy but its unit's state
stays unknown, which the dashboard shows as a dashed question mark rather than
guessing. One command per room:

```
python calibrate_room.py --live --room "Marketing" --channel 13
```

It asks you to switch the unit on, takes a frame, asks you to switch it off,
takes another, finds the display by looking for what was lit in one and dark
in the other, measures the contrast inside that box in both, and saves a
picture with the box drawn on. Open that picture; if the box is on the
display, answer y. If it landed on something else, answer n — the two frames
are kept, so you can try `--choice 2` or your own `--roi 352,34,383,67`
without touching the unit again.

Switch the unit, not the wall socket. A unit cut at the socket has a dark
display because it has no power, not because it is off.

`docs/calibration_runsheet.md` has the order to walk the building in, which
rooms have a unit in frame and which only look as though they do.

The three-step version still works where the frames already exist:

```
python tune_detect.py capture --room "Admin Room" --rounds 1 --label on
python tune_detect.py capture --room "Admin Room" --rounds 1 --label off
python calibrate_room.py --room "Admin Room" --channel 9 \
    --on frames/Admin_Room_ch09_on.jpg --off frames/Admin_Room_ch09_off.jpg
```

It refuses rather than writes when the two states are too close together, when
the frames were taken in different lighting, when the two frames look swapped,
and when the channel is not one the loop visits for that room -- each of which
would otherwise produce a confident reading with nothing behind it. A room
whose display genuinely cannot be seen belongs in `rooms.yaml` as
`ac: hidden`, which is honest, rather than calibrated badly.

Results live in `ac_units.yaml`, one block per room, each carrying the two
measurements its threshold came from and the date they were taken.

## Before you drive in

```
python doctor.py
```

Everything that can be checked from a desk: the files, rooms.yaml, what is
calibrated and whether it still has an anchor, the recorder logins, the
database and its tables, whether the loop is currently reporting, alerts,
disk space, and how much unblurred footage is sitting in `evidence/` and
`frames/`. It changes nothing.

`--cameras` then tries each recorder, which needs the cable. It reports the
frame size it got, and says so if a room that asked for the main stream came
back at 640×360 — that room cannot be calibrated until the recorder serves
one.

A morning is lost the same way every time: somebody drives in, plugs the
cable, starts the loop, and finds a password missing or a table never
created. All of that is knowable before leaving.

## The two meters

Every rupee on the dashboard rests on two guesses — 1.2 kW per unit and
Rs 55 per kWh — which is why the page says "at stake" and never "bill". The
meters are what replace them.

Once, as the project owner, in the Supabase SQL editor: `sql/06_meters.sql`.

Then two numbers a day, at roughly the same hour:

```
python log_meter.py gf 48231 --temp 34
python log_meter.py first 20114 --temp 34
```

Give the cumulative figure off the meter's face and the day's units are
worked out from the one before; give units straight from the K-Electric app
with `--units`. A reading that goes backwards is refused rather than turned
into a negative day. `--show` prints the last fortnight.

The day's high matters because weather drives an air conditioner harder than
people do — without it, a cool week looks like a saving.

Monthly, when the bill arrives:

```
python log_meter.py --bill gf 4120 238000 --from 2026-10-01 --to 2026-10-31
```

Three things to know about these two meters:

- **The ground floor + basement meter has the solar array behind it.** Its
  units are what came from the grid *after* the panels, so a bright day reads
  low for reasons unrelated to anybody switching anything off. That meter
  alone cannot show a saving. The first floor + cafe meter has no solar and
  is the clean one.
- **A day runs from one reading to the next**, not from midnight, so the
  night sits inside one number. The occupancy hours set beside it are counted
  over exactly that window.
- **Rooms have to be assigned to a meter** with `meter: gf_basement` or
  `meter: first_cafe` in rooms.yaml. The rooms whose own names say which
  floor they are on are already set; the rest are not guessed, and the
  Meters view counts how many are still unassigned.

After about four weeks the Meters view shows units per empty-and-cooled hour
— the measured figure that replaces the 1.2 kW assumption. It is withheld
until then, because a fortnight of this is mostly a figure about the weather.

## Alerts

The dashboard only works while somebody is looking at it, and the hours worth
money are the ones when nobody is. `--alerts` is the part that speaks without
being asked:

```
run_rooms.bat --alerts
```

It needs three things in `.env`: `SENDER_EMAIL` (the account that sends),
`APP_PASSWORD` (a Google app password for that account, not the account
password), and `ALERT_TO` (who receives, several addresses separated by
commas). Without `--alerts` the loop prints what it would have sent and sends
nothing, which is the right way to watch it for a day before letting it
write to anybody.

An alert that arrives too often is not a weaker version of a useful alert; it
is a filter rule in somebody's inbox, and after that the system is off
without anyone deciding to turn it off. So:

- **One room, one empty period, one mention.** Walking in and out starts a
  new period, so there is also a two-hour floor per room — otherwise a chair
  that reads as a person once an hour would manufacture a fresh alert all
  night.
- **One email, not one per room.** Rooms empty together at the end of the
  day, so they are gathered for ten minutes and sent as a list. Six at once
  go immediately rather than waiting.
- **A room whose unit is known to be off is never mentioned.** That is the
  room that got it right.
- **Nothing is claimed that was not measured.** An uncalibrated room's mail
  says it is empty and asks somebody to look; it does not announce waste
  nobody can see.

## A room that counts people who are not there

A camera that sees a person in a poster, a mannequin or a reflection reports
that room occupied for ever. The room then never counts as empty, so it
quietly stops being watched for waste -- which is why it is worth fixing
rather than living with.

The number alone cannot be argued with, so start by looking at what the
detector is actually drawing a box around:

```
python check_room.py --room "AutoOS"
```

It grabs a live frame from each of the room's cameras, draws every detection
with its confidence, saves the pictures in `frames/`, and prints the lines to
paste into `rooms.yaml`. Open the pictures before changing anything.

- A box on something that never moves -- a poster, a fire extinguisher, a
  chair with a jacket on it -- use the `ignore:` zone it prints. The zone is
  tied to that one spot, and a detection is only dropped when most of it sits
  inside: a real person standing in front of the poster is bigger, reaches
  outside the zone, and is still counted.
- Several faint boxes on clutter, all scoring well below the real people --
  use the `conf:` line it suggests. It applies to that room alone.
- A box on a real person you had forgotten about -- the room is right.

Prefer a zone. A confidence applies to the whole room, including the far
corner where somebody is half hidden behind a monitor, and missing a real
person is the error that matters: it is what sends somebody upstairs to an
occupied room.

### A room that is wrong only sometimes

A zone and a confidence both need to be aimed at something you can see. A
room that reports one person at three in the morning and is innocent by the
time anybody looks cannot be caught that way: run `check_room.py` and the
room is empty, the detector agrees, and the only trace is a number nobody
can argue with.

Run the loop with `--evidence` and it keeps the frame itself, boxes and
scores drawn on, whenever somebody is counted **outside working hours**:

```
run_rooms.bat --evidence
```

By morning `evidence/` holds one picture per wrong count, named by room,
camera and the minute. A chair at 0.31 at 2am is then an ordinary fix. It
stays quiet during the day, because a counted person during the day is
simply a person. These frames are not blurred and `evidence/` is in
`.gitignore`; keep the folder on that machine.

## Tools

- `check_room.py` - draws every detection on a live frame with its confidence,
  and prints the `rooms.yaml` lines to deal with a wrong count (see above).
  `--all --zip` does the whole site into one zip with a report.txt; run it
  when the building is empty, and every detection left is a false one
- `calibrate_room.py` - finds and measures the box over a unit's display from
  an "on" and an "off" frame, and writes `ac_units.yaml` (see above)
- `ac_detect.py` - reads `ac_units.yaml` and answers on / off / unknown for a
  frame; used by the room loop
- `calibrate_ac.py` - the older single-camera version of the above, for
  `ac_config.py`; kept for the Conference Room setup
- `zone_picker.py` - draw fixed blur zones on a camera frame, prints a
  `FIXED_ZONES = [...]` line for `privacy_blur.py`
- `blur_preview.py` - live preview of the privacy blur
- `generate_report.py` - PDF summary report
- `heartbeat_watchdog.py` - emails if the main system stops sending heartbeats
- `retention_cleanup.gs` - Google Apps Script for the sender's and receiver's
  Gmail: deletes old HFM alert emails daily
- `diagnose_live.py` - prints what the camera/AI sees per frame (confidences,
  DAY/NIGHT numbers, AC values) to tune settings
- `.github/workflows/keepalive.yml` - pings Supabase every 3 days so the free
  project is not auto-paused (needs the `DATABASE_URL` GitHub secret)
- `gemma_room_check.py` - asks Gemma 4 (Gemini API) what one camera frame
  shows: lights on/off, AC running or not, other devices on, energy waste, and
  a short alert in English and Roman Urdu. People are counted and blurred by
  YOLO on this machine first, so no face is sent. Needs `GEMINI_API_KEY` in
  `.env`. Examples: `python gemma_room_check.py --image room.jpg`,
  `python gemma_room_check.py` (one RTSP frame), `--watch 10` (every 10 min).
  Results go to `gemma_checks.jsonl`; the blurred frame that was sent is saved
  as `gemma_last_frame.jpg`.

## Dashboard room colours (top of `dashboard.py`)

| Colour | Meaning |
|---|---|
| Green | room in use, or AC off |
| Amber | room empty, AC on, less than `RED_AFTER_MINUTES` (30) |
| Red | room empty, AC on for 30+ minutes |
| Offline | no data from that room for `OFFLINE_AFTER_MINUTES` (3) - check the camera system |

Rooms needing action are listed first.

## Main settings (top of `unified_system.py`)

| Setting | Default | Meaning |
|---|---|---|
| `EMPTY_THRESHOLD_SECONDS` | 10 | room must be empty this long (AC on) before an alert |
| `RETENTION_DAYS` | 90 | DB rows older than this are deleted daily |
| `AFTER_HOURS_START` / `END` | 19:00 / 08:00 | alerts in this window get `[AFTER-HOURS]` in the subject |
| `DELETE_SENT_COPIES` | True | delete sent alerts from the sender's Gmail Sent + Trash (turns itself off if IMAP is disabled) |
| `BACKGROUND_PIXELATE` (`privacy_blur.py`) | False | optional strict privacy: lightly pixelate the whole snapshot except the ACs |
