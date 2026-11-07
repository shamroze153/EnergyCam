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
guessing. Calibration is two photographs and one command, per room.

1. With the unit **running**, and again with it **off** once the display has
   gone dark:

   ```
   python tune_detect.py capture --room "Admin Room" --rounds 1 --label on
   python tune_detect.py capture --room "Admin Room" --rounds 1 --label off
   ```

2. Measure. This finds the display by looking for what was lit in one frame
   and dark in the other, measures the contrast inside that box in both, and
   saves a picture with the box drawn on:

   ```
   python calibrate_room.py --room "Admin Room" --channel 9 \
       --on frames/Admin_Room_ch09_on.jpg --off frames/Admin_Room_ch09_off.jpg
   ```

3. Open `frames/Admin_Room_ch09_box.jpg` and check the green box is over the
   unit's display. If it is, run the same command again with `--write`. If it
   landed on something else, pick another box from the list it printed with
   `--choice 2`, or give your own with `--roi 352,34,383,67`.

It refuses rather than writes when the two states are too close together, when
the frames were taken in different lighting, when the two frames look swapped,
and when the channel is not one the loop visits for that room -- each of which
would otherwise produce a confident reading with nothing behind it. A room
whose display genuinely cannot be seen belongs in `rooms.yaml` as
`ac: hidden`, which is honest, rather than calibrated badly.

Results live in `ac_units.yaml`, one block per room, each carrying the two
measurements its threshold came from and the date they were taken.

## Tools

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
