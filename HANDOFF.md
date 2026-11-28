# EnergyCam: handoff, 28 Nov 2026

This file is the place to start: where the project stands, what runs where, what is open, and a prompt
for the next Claude session. `CLAUDE.md` has the full running notes. The old `README.md` and `HANDOVER.md`
describe the October single-room system.

> This repository is **public**. It holds code, counts and rules only. No names, employee IDs, photos,
> face numbers, camera pictures, passwords or database URLs belong here. Those stay on the camera
> laptop: `.env`, `people/`, `progress/`, `frames/`, `twin_scans/` and `progress.yaml`, all git-ignored.

---

## 1. What EnergyCam is now

EnergyCam uses the existing CCTV of two Disrupt campuses in Karachi:

* **140-H**: one building, basement to 2nd floor; 96 cameras in 62 rooms.
* **141-C/D**: two joined buildings with five more recorders.

It started as "is this room empty while its AC runs?" and grew into building and people intelligence.

**Energy and AC**

* Live occupancy for every room.
* AC on/off, read from each unit's display or louvre. A unit no camera sees is "unknown", never guessed.
* An empty-cooling ledger in rupees.
* Meters, bills and solar before/after.
* Savings & peak.
* A weekly e-mail.

**Desks and presence**

* 167 desks found at 140-H, each read every pass:
  * at the desk or away;
  * computer, phone or talking;
  * an hourly picture, kept locally.
* HR's attendance punches (IN/OUT) are imported.
* Every office employee has a **Presence** card. It was called "Productivity" until 28 Nov.
  * Attendance 40%, desk 40%, desk activity 20%.
  * A gold star means "fully observed".
  * The card shows coverage as minutes, and why the rest was not seen.

**Faces** (HR approved; the staff were told; everything stays local)

* Gate faces are checked against the punch machines and are about 96% right.
* Desk faces, punch timing and AdaFace together name desks.
* Doubtful names go to one review PDF for Shamroze.
* Away from the desk, faces are matched on the cafe, prayer, smoking and corridor cameras.

**Management Preview** (first tab, password)

* KPI cards and a schematic three.js 3D twin.
* Team-level patterns and discoveries with evidence.
* An Experiment Lab, rooms, savings, and an evidence-and-trust panel.

**Owner:** Shamroze. Talk to him in short Roman Urdu, step by step, one command at a time.

## 2. Rules that are never bent

These are in full in `CLAUDE.md`.

1. No camera picture in git, on the hosted page, or sent to any outside AI. The repo is public.
2. Credentials only in `.env`. Never print, commit or log a password or database URL.
3. Database grants stay narrow.
4. Never change recorder settings. Never retry a refused recorder login (XMeye-type recorders lock the
   account).
5. Work on `main`. Run every test before a push; push only green. Run `git status` before every commit.
6. **The 141 gym is ladies-only 15:00–20:00.** Its camera is never opened then, and no picture from those
   hours is kept. `private_hours` in `rooms.yaml` and `room_loop.fetch` enforce this.
7. Never a name, ID or face number in the repo. The hosted page gets codes and numbers, plus names only
   behind the password where `progress.yaml` says `cloud_names: true`.
8. Say "at the desk" / "presence", never "productive", for anything a camera measures.
9. Unknown is neutral. Time no camera saw never counts against anybody.

## 3. What runs where

| Piece | How |
|---|---|
| **The loop** | `room_loop.py`: every camera every pass (2–10 min), YOLOv8-small, AC reading, desks, faces, places. Started with `restart_loop.bat --evidence`. **Exactly one loop**, which is a parent plus its quiet_start child. Reads `rooms.yaml` once at start: restart it after any change. Each pass is logged to `cycles.csv`. |
| **Starting it so it outlives a Claude session** | PowerShell, sandbox disabled: `Invoke-CimMethod Win32_Process Create` with `cmd.exe /c "C:\hfm_energy_project\restart_loop.bat --evidence"`. List processes with `Get-CimInstance Win32_Process`, also sandbox disabled, because the sandbox hides them. |
| **Laptop dashboard** | `run_dashboard.bat` (`rooms_dashboard.py`, Streamlit): the full version, with names and camera pictures. |
| **Hosted dashboard** | Streamlit Community Cloud. It redeploys from GitHub `main` by itself and never shows a camera picture. |
| **Tools** | git at `%LOCALAPPDATA%\miniconda3\Library\bin\git.exe`; python at `%LOCALAPPDATA%\miniconda3\envs\hfm_energy\python.exe`. Commit messages go through a file (`git commit -F`), because PowerShell 5.1 breaks quotes. |
| **Attendance** | HR's Data Studio report, a rolling 24 h window (its link is in local memory, not here). In the app browser, about every 12 h: right-click the table > Refresh data > Export chart > Export data > CSV. Then `python attendance_import.py <the .tmp file>`. |
| **Desk naming round** (about every 3 h in office hours) | `python desk_match.py --nightly`, then `python coverage.py`. Sure pairs name themselves; doubtful ones go into one numbered review PDF for Shamroze. |
| **Night audit** (every 2 h) | `python field_audit.py`, in the background, about 17 min. Read `field_audit_*/verify.txt` and the pictures in `frames/verify/`. Fix only what is clearly wrong: an `ignore:` box over a spot nobody uses, or a room's own `conf`. Log 2–3 lines in `docs/night_log.md`. |
| **Places replay** (night) | `python places_replay.py <day> 09:30 21:00`, and `--campus 141 --skip cd_nvr3 --one cd_nvr2`. |
| **Tests** | The 25 files listed in `CLAUDE.md` (`test_room_loop.py` … `test_management.py`). All passed on 28 Nov. |

**Schedules die with a Claude session. Recreate them:**

* the night round every 2 h;
* a resume check at :07 and :37 (one loop, `cycles.csv` under 15 min old, then the approved items in the
  local `people/session_handoff/night_plan.md`);
* the naming round about every 3 h;
* the attendance export about every 12 h.

## 4. Where the numbers stand (28 Nov 2026)

* **Attendance-scored office staff:** 128 at 140-H, 177 at 141-C/D (the workforce is counted apart).
* **Desk staff with a named desk a camera sees:**

  | Campus | Named | Fully observed (new rule) |
  |---|---|---|
  | 140-H | 79 of 125 | 38 |
  | 141-C/D | 36 of 175 | 11 |

* **Coverage of desk-named staff,** time placed by a camera out of the machines' time in the building:
  * 140-H: 51%. On days places were tracked, about 89% of the unseen time is "their desk seen empty and no
    other camera named them".
  * 141-C/D: 44%. 218 h of the unseen time is cameras that do not answer (cd_nvr3 never opens; it is left
    alone and never retried).
* **Accuracy:**
  * Gate face names: about 96% right against the punch machines.
  * Desk presence: about 80% right on 72 hourly pictures checked by eye; 97% on the five pilot desks.
  * Away-from-desk places, checked by eye: 140-H 22 of 30 right; 141 9 of 20 right.

## 5. What changed on 28 Nov

* **Advisor zip for ChatGPT.** Code, 15 page screenshots and 20 anonymised employee-days. The key stays on
  the laptop.
* **ChatGPT's master build brief.** Shamroze picked from it:
  * "Presence", not "Productivity", on every page;
  * the star renamed "fully observed";
  * coverage as minutes on each card;
  * a reason for every not-seen stretch;
  * a real 3D twin, one verified floor first.
* **Star rule (15eab13).** The shares are now of the machines' time in the building, not of the camera's
  own first-to-last sighting. Someone seen only 12:00–13:00 used to be "100% at the desk". The star needs
  at least 30% at the desk and at least half the time placed by a camera.
  (15eab13's commit message is stale by mistake; the night log has the right one.)
* **Presence rename and coverage line (e098296).**
* **Reasons for not seen (fdae002).** Each stretch is one of: `desk_empty`, `unwatched`, `untracked`
  (days before places were tracked) or `no_record`.
* **UPS Room ignore box.** A stored orange chair was being read as a person.
* **`twin_scans/` is git-ignored,** together with `*.ply`, `*.spz`, `*.glb` and `*.splat`.

## 6. Known limits

* Many office cameras look **down** from the ceiling, so there is no face to read at the desk. Corridor
  cameras are read on 640x360 sub-streams, too small for a face.
* Sightings away from the desk need a face. Body re-ID (OSNet) is only "possible" and needs a person to
  confirm it.
* Naming desks: punch timing alone is about 70–85% right. Shamroze's last review was 1 of 3 right. Few
  141 desks are named.
* Desk activity (phone / talking / computer) is rough. On low-resolution cameras (nvr1, nvr4) it cannot be
  told.
* One laptop, CPU only (OpenVINO). If it sleeps, or the Claude session ends, the loop can stop.
* The attendance import is manual. The laptop clock runs about 160 s fast; an offset is measured each day.
* Room temperature is not measured. Rooms whose units are partly read are "assumed".
* **Licences:** InsightFace SCRFD and AdaFace weights are research-use; YOLOv8 is AGPL-3.0. Both need a
  review before anything commercial.
* The app is one 7,500-line Streamlit file with about 15 tabs.

## 7. What to do next, in order

1. **Fewer "not seen" minutes, measured.** At 140-H the gap is face reads where people go once they leave
   the desk:
   * the main stream on the cafe, corridor and entry cameras;
   * a bigger `face_sweep` budget;
   * event-driven reads where a desk just emptied.

   Measure before and after with `productivity_view.not_seen` summed over each campus. Never lower the
   face thresholds just to cut "not seen".
2. **Real 3D twin, one floor first: the 140-H ground floor.** Shamroze will bring:
   * photos of the fire-exit plans, every floor;
   * **Scaniverse** scans (Android, processed on the phone), taken with the office empty;
   * two or three tape measurements a floor.

   He copies them by cable into `twin_scans/`, which stays local. Then:
   * align the scan on the plan (Blender);
   * show it in three.js with a Gaussian-splat viewer plus plan geometry;
   * give rooms stable IDs, clickable for live AC and occupancy;
   * place people as anonymous avatars by CCTV-to-plan calibration, never faces.

   An iPhone Pro with Polycam, or a professional laser scan, would be more exact if one becomes available.
3. **One app, not fifteen tabs.** Six destinations: Command Center, People (Presence), Digital Twin,
   Energy & Sustainability, Facilities, System & Admin. One local **Operator Console** for desk review,
   sightings, attendance import and night jobs. Migrate to Next.js + FastAPI only gradually, read-only
   screens first, keeping the Python loop.
4. **Management Preview.** Store insights and experiments; this needs an administrator to run one SQL.
5. **AC calibration** from `frames/ac_keep/`: units seen switching on the kept frames.
6. **141 desks:** naming rounds; the 141 offices' places replay.

**Waiting on Shamroze:**

* the 3D scans and plan photos;
* firm answers on doubtful review rows;
* a current seating sheet with employee codes (optional);
* the laptop clock sync;
* whether HR can give work-system data for real performance (tickets, deliverables). Until then the cards
  say "not assessed".

**Rejected:**

* gait recognition;
* buying hardware before a benchmark;
* matching clothes from the gate to the desk;
* AC outdoor-unit reading.

## 8. Local files a new session needs (laptop only, never in git)

* `people/session_handoff/night_plan.md`: the numbered running plan, with what is approved and open.
* `people/session_handoff/`: review PDFs, naming tools, boss reports, the advisor zip and its key.
* `people/`: roster, directory photos, face numbers, desk names, sightings, attendance exports.
* `progress/`, `frames/`, `seats/`: the loop's local records and pictures.
* Claude's memory files: `C:\Users\<user>\.claude\projects\C--hfm-energy-project\memory\`.

---

## 9. Prompt for the next Claude session (copy and paste)

```
You are continuing EnergyCam in C:\hfm_energy_project (branch main) for Shamroze. Talk to him in short
Roman Urdu, step by step, one command at a time.

First, read: HANDOFF.md (this hand-off), CLAUDE.md (full notes and the rules that are never bent),
people/session_handoff/night_plan.md (local, the numbered plan: what is approved and open), and the
memory files. Then check:
1. Exactly ONE loop: list python processes with Get-CimInstance Win32_Process (sandbox disabled), command
   line containing room_loop.py; a parent plus its quiet_start child is one loop. Never start a second.
2. The last line of cycles.csv is under 15 minutes old. If no loop runs, start it with Invoke-CimMethod
   Win32_Process Create 'cmd.exe /c "C:\hfm_energy_project\restart_loop.bat --evidence"' (sandbox
   disabled). If a loop runs but cycles.csv is stale, do not start another: check TCP 554 on the
   recorders (no login retries) and tell Shamroze.
3. git pull, git status, and run the 25 test files listed in CLAUDE.md.

Recreate the schedules (they die with each session): the night round every 2 h ("A night on its own" in
CLAUDE.md); a resume check at :07 and :37; the desk naming round (desk_match.py --nightly, then
coverage.py) about every 3 h in office hours; the attendance export about every 12 h (app browser, HR's
Data Studio report; steps in HANDOFF.md section 3 and in local memory).

Then continue HANDOFF.md section 7, in order, one small tested milestone at a time:
(1) cut "not seen" by reading faces where people go once they leave the desk -- measure first and after
    with productivity_view.not_seen per campus; never lower thresholds just to cut "not seen";
(2) the real 3D twin of the 140-H ground floor, once Shamroze's Scaniverse scans and fire-exit plan
    photos are in twin_scans/ (local only);
(3) toward six destinations and one Operator Console, gradually.

Never: a camera picture, name, employee ID, face number, password or database URL in git, on the hosted
page or to an outside AI; open the 141 gym camera from 15:00 to 20:00 or keep a picture from those
hours; change recorder settings or retry a refused login; push without every test green; call a camera
measure "productivity" (it is presence; unknown time is neutral). Before each commit run git status and
look at the diff for pictures and names. End each piece of work with 2-3 lines in docs/night_log.md and
an update to people/session_handoff/night_plan.md.
```
