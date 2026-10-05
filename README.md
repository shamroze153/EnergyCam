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
| Camera system (`unified_system.py`, `watchdog.py`, tools) | Office laptop / server (on-prem) | `pip install -r requirements-local.txt` |
| Dashboard (`dashboard.py`) | Streamlit Community Cloud | `requirements.txt` (installed automatically by Streamlit) |

`requirements.txt` must stay small: only what `dashboard.py` imports. Heavy
packages (ultralytics/torch, opencv) make the Streamlit Cloud build slow or fail.

## Setup (camera system, Windows)

1. `conda activate hfm_energy`
2. `pip install -r requirements-local.txt`
3. Create `.env` with `SENDER_EMAIL`, `APP_PASSWORD`, `RECEIVER_EMAIL`,
   `RTSP_URL`, `DATABASE_URL`. **Never commit `.env`.**
4. Run: `python unified_system.py` (or `run_system.bat` for auto-restart)
5. Watchdog (separate window): `python watchdog.py`

## Dashboard

- Local: `streamlit run dashboard.py` (reads `DATABASE_URL` from `.env`)
- Cloud: Streamlit Community Cloud, main file `dashboard.py`, Python 3.11,
  secret `DATABASE_URL = "postgresql://..."` (use Supabase's **Session pooler** URL)

All times on the dashboard are Pakistan time (PKT).

## One-time upgrade (old version -> this version)

1. Stop the old `unified_system.py`.
2. `pip install -r requirements-local.txt` (adds `tzdata` for Pakistan time).
3. Run `sql/one_time_upgrade.sql` **once** in Supabase SQL Editor (fixes old
   rows saved 5 hours ahead, drops the unused `phone_count` column).
4. Start the new version.

## Tools

- `calibrate_ac.py` - prints LED/flap thresholds for `ac_config.py` from an
  "AC off" and an "AC on" image (`--mode day` or `--mode night`)
- `zone_picker.py` - draw fixed blur zones on a camera frame, prints a
  `FIXED_ZONES = [...]` line for `privacy_blur.py`
- `blur_preview.py` - live preview of the privacy blur
- `generate_report.py` - PDF summary report
- `watchdog.py` - emails if the main system stops sending heartbeats
- `retention_cleanup.gs` - Google Apps Script for the alert receiver's Gmail:
  deletes old HFM alert emails daily
- `.github/workflows/keepalive.yml` - pings Supabase every 3 days so the free
  project is not auto-paused (needs the `DATABASE_URL` GitHub secret)

## Main settings (top of `unified_system.py`)

| Setting | Default | Meaning |
|---|---|---|
| `EMPTY_THRESHOLD_SECONDS` | 10 | room must be empty this long (AC on) before an alert |
| `RETENTION_DAYS` | 90 | DB rows older than this are deleted daily |
| `AFTER_HOURS_START` / `END` | 19:00 / 08:00 | alerts in this window get `[AFTER-HOURS]` in the subject |
| `DELETE_SENT_COPIES` | True | delete sent alerts from the sender's Gmail Sent + Trash |
