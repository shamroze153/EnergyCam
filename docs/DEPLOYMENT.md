# EnergyCam — deployment strategy

Prepared in response to the security review. It describes what is installed, where
it runs, what leaves the building, what access is required, and how the system is
started, updated and retired.

## 1. What runs where

| Part | Runs on | Purpose |
|------|---------|---------|
| `unified_system.py` | a machine inside the client's network (camera PC or DVR server) | reads the camera, detects people and AC state, sends alerts, writes log rows |
| `heartbeat_watchdog.py` | **a different machine** | emails if no heartbeat has been written for two hours |
| `dashboard.py` | Streamlit Community Cloud | read-only view of room history |
| `keepalive.yml` | GitHub Actions | keeps a free Supabase project from pausing |
| Postgres (Supabase) | Supabase, client's own project and region | stores text event rows only |

The watchdog belongs on a separate machine on purpose. A watchdog running beside the
thing it watches cannot report that the machine is off.

## 2. What leaves the building

Only two things:

1. **Text rows** to Postgres: timestamp, room name, EMPTY/OCCUPIED, AC1/AC2 ON/OFF,
   person count, alert flag. No images, no video, no names, no identification.
2. **Alert emails** containing a snapshot in which people, monitors, laptops,
   keyboards and phones are pixelated before the image is formed. If blurring fails
   for any reason, the email is sent **without** an image.

Video is never written to disk. Frames exist in memory only.

## 3. Host requirements

Measured: YOLOv8n at 640 px on a 2560×1440 frame is about 45 ms per frame on four
Xeon cores, roughly 20 frames per second. The program processes every new frame, so
it uses most of one machine's CPU continuously.

| Item | Requirement |
|------|-------------|
| CPU | 4 cores (Intel i5 8th generation or equivalent). No GPU needed. |
| RAM | 8 GB (the program peaks near 1–1.5 GB) |
| Disk | 10 GB free (Python and libraries are about 3 GB). No footage is stored. |
| OS | Windows 10/11, or Ubuntu 22.04+ |
| Python | 3.11 |

Running this on an existing DVR server is possible, but the CPU load is continuous.
Confirm the DVR's own recording has headroom before sharing the machine, or give
EnergyCam its own host.

## 4. Network access

| Direction | Destination | Port | Why |
|-----------|-------------|------|-----|
| LAN | camera IP | TCP 554 (RTSP) | video stream |
| Outbound | `*.pooler.supabase.com` | TCP 5432 | log rows and heartbeat |
| Outbound | `smtp.gmail.com` | TCP 465 | alert emails |
| Outbound | `imap.gmail.com` | TCP 993 | delete the system's own sent copies |
| Outbound (once) | `github.com`, PyPI | TCP 443 | first install only |

**No inbound ports are required.** Nothing listens. We recommend the camera sits on a
restricted VLAN where only this host may reach it on 554.

## 5. Credentials

Four database roles, one per component, each with only what it needs. See
[../sql/README.md](../sql/README.md) for the full table and the queries that verify it.

| Component | Role | May do |
|-----------|------|--------|
| camera system | `energycam_app` | INSERT, DELETE; read only the `timestamp` column; **no schema changes** |
| dashboard | `energycam_dashboard` | SELECT on `logs` |
| watchdog | `energycam_watchdog` | SELECT on `heartbeat` |
| keep-alive | `energycam_keepalive` | SELECT on `heartbeat` |

Row Level Security is enabled on both tables, so the project's public REST API cannot
read them with the anon key.

Secrets live in three places and nowhere else: the `.env` file beside the program on
each on-premise machine, Streamlit Cloud's app secrets, and GitHub Actions secrets.
They are never committed. Rotate every six months and whenever someone with access
leaves, using [../sql/03_rotate.sql](../sql/03_rotate.sql).

## 6. Installation order

1. An administrator runs `sql/01_schema.sql`, then `sql/02_roles.sql`, once.
2. On each machine: install Python 3.11, then
   `pip install -r requirements-local.lock.txt` (see `requirements-local.txt` for how
   that lock file is produced).
3. Create `.env` with `SENDER_EMAIL`, `APP_PASSWORD`, `RECEIVER_EMAIL`, `RTSP_URL`
   and the correct `DATABASE_URL` for that machine's role. Permissions: readable only
   by the account that runs the service (`chmod 600` on Linux).
4. Calibrate the AC thresholds for the room, day and night: `calibrate_ac.py`.
5. Start the service (section 7) and confirm a `>> LOGGED:` line every 30 seconds.

The program verifies its settings before touching the camera or the database. A
missing or malformed setting stops it with exit code 78 and a message naming what is
wrong; it does not retry, because a restart cannot supply a setting that is absent.

## 7. Running as a service

**Windows.** `run_system.bat` restarts the program if it stops, and halts on exit
code 78. Start it at boot with Task Scheduler: *Create Task*, run whether the user is
logged on or not, trigger *At startup*, action `C:\hfm_energy_project\run_system.bat`
with *Start in* set to that folder, and untick *Stop the task if it runs longer
than…*. Repeat for the watchdog on its own machine.

**Linux.** A unit at `/etc/systemd/system/energycam.service`:

```ini
[Unit]
Description=EnergyCam detection
After=network-online.target
Wants=network-online.target

[Service]
User=energycam
WorkingDirectory=/opt/energycam
ExecStart=/opt/energycam/venv/bin/python unified_system.py
Restart=on-failure
RestartPreventExitStatus=78
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`RestartPreventExitStatus=78` mirrors the batch file: a configuration error stops the
service instead of looping.

## 8. Updates

Changes are reviewed on a branch and merged before deployment. On the host:
`git pull`, then `pip install -r requirements-local.lock.txt`, then restart the
service. Dependencies are upgraded deliberately — test, then regenerate the lock
file — never automatically.

## 9. Data retention

Log and heartbeat rows older than 90 days are deleted daily by the program itself.
Alert emails older than one day are deleted from both the sending and receiving
mailboxes by `retention_cleanup.gs`, a daily Google Apps Script. Both periods are
settings and can be shortened at the client's request.

## 10. Removing the system

Stop and remove the service, delete the program folder including `.env`, revoke the
four database roles, delete the Streamlit app and the GitHub Actions secret, and drop
the two tables if the client wants the history gone. Nothing else is left behind:
the system installs no drivers, opens no ports, and stores nothing outside its own
folder.
