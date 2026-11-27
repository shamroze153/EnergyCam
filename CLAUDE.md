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
`test_live_ac.py`, `test_floors.py`, `test_energy_rooms.py`, `test_seats.py`,
`test_ac_plan.py`, `test_seating.py`, `test_savings.py`, `test_progress.py`,
`test_places.py`, `test_faces.py`, `test_follow.py`, `test_management.py`.

Management Preview (27-28 Nov night, ChatGPT's "Office Intelligence" brief
and its three mock-ups, Shamroze: "exact aisa dashboard"): the first tab on
both campuses, behind the Progress password (MANAGEMENT_PASSWORD if ever
set), always drawn dark (CHOSEN_MODE keeps the reader's theme for links).
`management_view.py` draws it from what the other views work out -- KPI
cards, a three.js 3D twin (a schematic: real rooms placed by the system,
sized by seating.yaml's desks; still until "Explore 3D" so the page
scrolls), team-level work patterns from the board (departments from the
roster / the sent attendance rows; never an individual ranking), AC money
today vs yesterday, explainable discoveries with evidence and confidence,
the room table, the cooling-empty tracker, evidence & trust. Never a camera
picture; temperature says "not measured". Experiment Lab and an insights
table (the brief's days 2-5) are next.

26 Nov night (four background workers, all merged): `places_day.py` --
where each named person's day went (desk / meeting / cafe / smoking /
prayer / inside / out / unknown), on each board person as p["places"]
(focus day's segments) and p["places_days"] (totals); camera sightings
placed under 1% of away time while cctv_faces skipped anybody at a
regular seat on every camera -- since 26 Nov 13:40 only an office's (or
a staffed desk's) seat is skipped, as progress_track.candidates. The
laptop's Progress page takes the loop's board (progress/board_latest.pkl,
progress_data.latest_board) rather than building it (70-80 s). The report card draws it
as "Where the day went". Workforce staff (janitorial, office boys, gate
and security, valet, technicians, by designation --
productivity_view.WORKFORCE) are a section of their own. Gate: nightly
`gate_match.nightly_faces` (exits within 45 s of the person's own OUT
punch, clock-corrected; gate+machines names kept apart in
people/gate_machines/); desk_match adds a presence rule (auto-names only
past margin 1.05, right on every known desk); round 5's review PDF is in
people/session_handoff/agents/faces/. AC: ac_detect opt-ins `dark_pct`,
`slats_min`, `min_std`; ac_units.yaml fixes for the 141-C cafe towers,
Reception, Learning Center, Marketing, Room 27/32, Basement ch24 (see
docs/ac_camera_audit.md, 26 Nov). Energy: "Solar, month by month" keeps a
month's MWh as a solar_daily row noted MONTH_NOTE.

Progress (23 Nov): HR approved watching a handful of employees.
`progress_data.py` turns the seat notes into each employee's day at their
own desk (first in, last out, hours at the desk, breaks; a pass never made
is "not watched", never "away"); `progress_view.py` draws the dashboard's
"Progress" tab -- the project's stages and an employee card each -- behind
its own password, `PROGRESS_PASSWORD` (.env / secrets; unset = locked).
Which employee, which desk, which code: `progress.yaml`, this machine only
(git-ignored; `progress.example.yaml` shows the shape). Never commit it,
never put a name or a result in the repo. The hosted page gets codes and
numbers -- and, since 24 Nov, each named employee's name, employee ID and
a small icon of their directory photo, because progress.yaml says
`cloud_names: true` (Shamroze: "teeno bhjdo ... pw protected h to masla
nai h"; `progress_data.to_payloads`, `photo_icon`). Never a camera
picture on the hosted page. Say "at the desk", never
"productive", and check a new desk by eye on its kept frames first.
The loop reads what each employee is doing at the desk every pass
(`desk_activity.py`: computer / phone / talking -- a phone found in their
own box, "talking" only somebody standing over the desk) through
`progress_track.observe` (guarded: it can never stop a pass), writing
`progress/<date>.csv` and the desk's picture to `frames/progress/` (both
local, kept 7 days). `progress_video.py` turns a day into a video per
employee (the tab plays it). Following them to other cameras: shirt
colour was tested on 23 Nov and turned down; `reid.py` runs OSNet-AIN
(`reid_osnet.py`, torchreid's MIT code, unchanged; weights in `models/`,
git-ignored, loaded `weights_only=True`) on every 140-H camera's people
who are not at a regular seat of an office, and writes the best match
over 0.70 (by 0.03) as a *possible* sighting with a picture. Only a
sighting confirmed on the tab ("Sightings to check" -> `review_<date>.csv`)
counts as a place. Never confirm one for Shamroze without being sure by
eye. `yolov8s-pose.pt` is downloaded but not used until a day of phone
moments shows it helps.

Faces and following (23 Nov night, HR's permission for these five):
`faces.py` (OpenCV's YuNet + SFace, `models/`, git-ignored) learns each
employee's face only at their own desk (`progress/faces/<code>.npy`,
numbers, never a picture, this laptop only; a stranger in the chair is
not admitted once five are kept) and names them elsewhere only far above
OpenCV's line (SAME 0.55, MARGIN 0.15) -- such a sighting is state "face"
and counts without review (a "no" on the tab still wins). On the ceiling
cameras a face is often too small or from above: no face is no answer,
and the body re-ID's "possible" stands. `building.yaml` is 140-H as places
on four floors and the ways between them (a sketch from the cameras, not a
floor plan -- correct it from the fire-exit plans; `building.problems`
must stay empty, test_progress checks it). `progress_follow.py`, called
from the loop between batches (`pulse`), looks at the five desk cameras
every minute and, once a desk is empty two looks running, at the cameras
nearest to where that employee was (cafe, smoking, meeting rooms and the
mosque a little first) every 30 s for 15 min, moving round each new
sighting -- through `fetch` (gates, private hours) and
`progress_track.observe`, so the same rows, pictures and rules. The
Progress tab draws `building_view.py`'s 3D building: everybody now, and
the day's way (also on the hosted page: codes and room names only).

Campus faces (24 Nov: Shamroze -- HR approved face recognition for the
whole campus, and the staff have been told). `staff_faces.py`: the
members directory (life.disrupt.com, read by the signed-in app browser)
as `people/roster.csv` -- employee ID, name, designation, department,
project; no emails; the Gadits left out, as Shamroze asked -- the
directory photos in `people/photos/` (for the double check by eye) and
their face numbers in `people/faces.npz`. `seat_faces.py`, called from
`room_loop.examine`: the face of whoever sits at each regular seat of a
140-H camera, as numbers per seat and day (`people/seat_faces/`, 14
days); `python seat_faces.py match <days>` names a seat only from 8+
faces whose mean is far above the line (0.45) and clear of the next
(0.10) -- tested on 24 Nov: P3's seat named right (0.53, by 0.12), the
seats seen from above or blurred left unnamed, never wrong. People/ is
git-ignored: never a name, ID, photo or face number in the repo; on the
hosted page only what `cloud_names` lets through (above). A named seat is shown beside its directory photo for a
person to confirm before anything is built on it.

Every desk (24 Nov, Shamroze: "140 ke sab employees ka, jo desk par
baithte hain"): `desk_seats.find_desks` -- every regular seat of 140-H's
office cameras (167 desks, 13 rooms); `desk_watch.py` (from
`room_loop.examine`) reads each desk every pass -- talking / the phone in
a close look every third pass / "desk" (not read) / away -- into
`progress/desks_activity/`, an hourly picture under `frames/desks/`, and
rebuilds `progress/desks.csv` hourly (`desks_data.build`: the five's
rules, plus focus blocks of 60+ min, core hours 11-17, late starts,
after hours, an hourly heatmap). Desk codes are kept by place
(`progress/desk_codes.json`, `desk_seats.stable_numbers`, since 24 Nov
18:09): before that they were renumbered busiest-first every day and at
every restart, so names, pictures and activity given to a code moved
(the old pictures are in `frames/desks_before_codes/`, not to be named
from). Naming desks by hand from their pictures was too hard for
Shamroze (24 Nov): `name_suggest.py [days]` matches each desk's face
(seat_faces) against the gate's frontal faces of named people, the same
days, and suggests a name only where both pick each other; each comes as
one picture (desk sitter | gate pictures | directory photo) in
`frames/suggest/` for a yes / no (`name_suggest.save_answer`, a yes names
the desk). Where people go (24 Nov): the cafe, commons, smoking, parking,
prayer and entry cameras are read at 640x360 by the pass (nvr1/nvr4 sub),
too small for a face; `face_sweep.py`, from the loop's pulse, reads three
of them a minute at full size (main stream, through fetch) for
`cctv_faces`, and a known person's CCTV gallery now takes the gate's
straight-on pictures of them too (`cctv_faces.gate_samples`, named at
0.55 by 0.15). The offices on dvr2/xvr3 are read at 1920x1080 already:
their desks fail by face because the cameras look down, not for size.
For the desks seen from above: the gate keeps a named passer's clothes
(`<time>_ch.._<id>_body.jpg`), desk_watch keeps every desk's sitter's
look (OSNet, `progress/desk_looks/`, every 15 min), and
`clothes_match.py <day>` pairs them the same day -- first scored on the
known desks; suggest nothing from it until it is right there. Every desk
has a report card on the laptop (unnamed: "Desk <code>"), and a desk
named on the tab joins the board by itself (`progress_data.desk_people`).
Far desks and old recordings (25 Nov night): rooms.yaml `zoom:` regions
per camera are read again by `room_loop.detect` in 640-px tiles at twice
the size, in office hours only (Basement ch 23/25's far rows), by the loop,
verify_live and check_room alike. A desk seen by two cameras: `also:
[[rec, ch, x, y]]` on a progress.yaml person. `replay_day.py <day> <from>
<to>` reads the recorders' recordings (playback, read only, one login try,
140-H only, never private hours) every 5 min and writes seat notes and
one-camera passes to `seats/replay/`; progress_data reads them beside the
loop's (the loop's gaps by default, `--all` for a camera the loop saw
badly). Desk pictures for naming come from the same playback
(Dahua `/cam/playback`, Hikvision `/Streaming/tracks/<ch>01`). The report
card opens with a desk score (at the desk 50%, stretches of an hour+ 30%,
on time 20%) -- time at the desk, not the work's worth.
The Progress tab's "Every desk at
140-H" (laptop only) shows the day and the usual week; a desk has a name
only where one is known. `desks_data.py` stays pandas-only for the
dashboard (test_dashboard checks its imports).

Savings & peak (18 Nov): the dashboard's "Savings & peak" tab is
`savings.py` -- the scoreboard (meters against the last bill and the same
month a year ago; what cooling empty rooms cost, this week against the
last, on the rooms both weeks watched) and every room's peak-hours cost.
`weekly_report.py` mails the same every Monday from 09:00 (the loop starts
it, `room_loop.weekly_mail`) to `REPORT_TO` -- an address that lives only
in `.env`, never in the repo -- from `SENDER_EMAIL`. By hand:
`python weekly_report.py --preview x.html` (nothing sent) or `--send`.
`ledger_data.py` is the page's reading of rooms.yaml and of the ledger,
shared with the mail so both say the same figure.

Solar (20 Nov): 140-H's array, 63.85 kW, behind the ground floor +
basement meter, went up 1 Oct 2026 and was on test all October (a neutral
fault); it works in full from November. rooms.yaml `assumptions:` holds
`solar_kw`, `solar_since`, `solar_full_from`; the Energy page's "Solar:
before and after" compares the last bill before it (September) with the
readings since, the first floor meter (no panels) as the control, and
"This month's bill, meter by meter" puts each meter's pace at its own last
three bills' rupees a unit.

Desks (13 Nov): `seating.yaml` holds the admin team's seating sheet as
counts only -- desks per room, how many given to somebody, by team -- and
which camera rooms see them (`rooms:`). The sheet itself has people's
names: never commit it, never copy a name into the repo. To refresh,
download its "seating" tab as CSV and run `python import_seating.py
<file.csv>`, then delete the CSV. The dashboard's "Desks" tab (and "Desks &
space" on the front page) puts the cameras' head counts against it.

Where people sit: the loop writes each counted person's place to
`seats/<date>.csv` (numbers only, this machine only). `python seat_map.py`
turns a day of them into seats per room (`seats.txt`) and a picture per
camera in `frames/seats/` -- local, never committed.

How many units run in a room (for "5 of 6 running" and the live kW on the
campus page) goes in `room_events.ac_units_on`, which an administrator adds
once with `sql/09_ac_units.sql`. Until then the loop writes rooms without
it and says so once; restart the loop after the SQL is run.

## 27 Nov, night

* **141-C/D Progress** (Shamroze: "141c/d me bh bnana ... 140H ki tarah
  dept wise", same password): `PROGRESS_CAMPUSES` in rooms_dashboard
  (campus -> the machines' place prefix, where its visitors punch). Its
  employees are those with half their punches at "141-D ..." machines;
  no 141 desk is named in a camera yet, so the score is attendance alone
  and the page says so. Hosted: the loop sends `_attendance_141`
  (progress_track.OTHER_CAMPUSES).
* **Monitor** tab (his picture of a plant-monitoring dashboard):
  monitor_view.py + rooms_dashboard.show_monitor, both campuses.
* **Attendance link** he sent is a Looker Studio report behind Google
  sign-in (shamroze.nasir's account): he must sign in to the app
  browser himself; until then HR's export (people/attendance/) is all.

## Handoff -- 25 Nov, 19:25 (read this first in a new session)

Everything that runs is pushed (396598b); the loop and the laptop
dashboard were restarted at 19:20. The previous session's plan, scratch
scripts, the review PDFs and the face study are in
`people/session_handoff/` (git-ignored: names and IDs live there) --
start with `people/session_handoff/night_plan.md`,
`people/session_handoff/face_agent/REPORT.md` and the memory files.

* **Productivity page (the CEO's, 25 Nov)**: Progress tab, top --
  `productivity_view.py` + `rooms_dashboard.productivity_section`. Filters
  by business unit (roster "project") and department; the campus figures;
  business units and departments; the departments as sections to open,
  each a table (directory photo, productivity bar); a click on a line, or
  "Find an employee", opens a profile: scores and parts, a bar chart with
  the department's colleagues (theirs marked), every day's IN/OUT by the
  machines, the camera's day and building map where their desk is seen.
  Productivity = attendance 40%, desk 40%, desk activity 20% (computer,
  and not phone/talking, as shares of desk time where read); a part not
  measured gives its weight to the others. CSV download for submission.
  140-H's employees = at least half their punches at 140-H
  (`attendance.HOME_SHARE`): 144 + 3 board-only = 147; ~84 from 141-D are
  visitors, left out and counted. Hours count only days ending on an OUT.
* **Report cards (25 Nov night, Shamroze: "naya banda bhi samjhe")**: the
  Progress tab is ONE way in -- department cards -> its employees as cards
  (their productivity beside the department's, hours a day, usual in/out)
  -> a report card (`employee_report.py`): average and today so far, why
  above/below the team, strong / weak points against the department
  (5+ measured, else all 140-H -- Microsoft Viva's floor), early signs
  against their OWN usual (long days, hours falling, later in, earlier
  out, days missed), a factor strip and an IN/OUT days chart (HTML rows,
  readable on a phone). From big companies' practice: a long day is never
  credit, quiet is no merit and only a lot of talk is mentioned ("may be
  work"), breaks shown neutrally, the work's results not measured (said
  on the card). The rest (desk cameras' board, every desk, attendance
  lists; laptop: naming tools, videos) behind switches at the bottom.
  HR's export cut mid-day (25 Nov, 12:21) no longer counts anybody absent
  (`attendance.cut_short`). The laptop clock runs ~160 s fast (Windows
  time not syncing) -- `attendance.clock_offset` measures it per day;
  syncing it waits on Shamroze.
* **Streamlit gotcha**: two `<style>` blocks on one line in st.markdown
  leave the second open and swallow the page; keep each style block its
  own markdown block ("\n\n" between them -- productivity_view._styles).
* **Submission files** (local): people/session_handoff/report/
  productivity_<day>.pdf (from the page, directory photos only) and
  video/140H_employees_<day>.mp4 (+ _phone.mp4, camera pictures: never
  shared beyond Shamroze).
* **Face verification (background study, REPORT.md)**: the gate's face
  names are ~96% right by the machines; the gap is coverage. Top ideas:
  attendance-gated naming at 0.45 (+48% punches named), galleries built
  from OUT punches (+87% crops named), and three no-risk fixes first
  (store the live face numbers, stop the crop file-name clash losing
  17.5%, correct the gate clock +162-165 s). Not built yet.
* **Desk names**: 51 named desks (people/desk_names.csv), about 56 people
  on the hosted board. Round 2's review is applied; refused pairs are in
  people/desk_names_rejected.csv (desk_match never re-pairs them), four
  waiting for a clearer picture in people/desk_names_pending.csv.
  Punch timing is the only strong evidence (about 85% right at round 2's
  bar), so a machine-only name goes through ONE review PDF
  (session_handoff/review_pdf2.py; Shamroze replies only the wrong
  numbers). Next: round 3 (session_handoff/desk_candidates.py, then
  pick_candidates.py; P4's ID as a row in it).
* **Not useful (tested)**: clothes from the gate to the desk, and the
  seating plan in Downloads (January; people moved).
* **Waiting on Shamroze**: P4's identity; a current seating sheet with
  Emp Codes (optional); HR's newer exports for the days after 25 Nov.
* **Schedules die with a session -- recreate them**: the night round
  every 2 h at :17 (A night on its own), a resume check at :07 and :37
  (one loop, cycles.csv under 15 min, then the plan). The 25 Nov 16:17
  round was skipped for the handover.

## Handoff -- where the campus face work stands (24 Nov, 12:35)

For a new session: everything that runs is in the repo; everything that
names a person is on this laptop only. Read this, then docs/night_log.md.

* Runs in the loop (room_loop.examine / main): `progress_track` (the
  five), `progress_follow` (desk cameras every minute; follows a leaver),
  `seat_faces` (faces per regular seat), `desk_watch` (every desk's
  activity -- pose: a hand to the head is a call; screen seen = computer,
  else "desk"), `cctv_faces.observe` (named people seen off their seat ->
  people/sightings/), `entrance_watch` (Entry H main stream on a thread:
  faces on the way out, frontal only, names at 0.50 by 0.10, photo or CCTV
  gallery), and hourly `desk_watch.rebuild` (seat names by face,
  progress/desks.csv, the CCTV galleries).
* By hand, at night: `python entrance_backfill.py <days>` (the recorder's
  playback of Entry H, lunch 13:00-15:30 and evening 17:00-22:00, real
  time, resumes from people/entrance/backfilled.txt), then
  `python gate_match.py` (a desk for a person after 2+ votes over days).
* Local only, never in git: progress.yaml (names of the five),
  people/ (roster, photos, faces.npz, cctv_faces.npz, seat_faces/,
  entrance/, sightings/, desk_names.csv, seat_reviews.csv,
  seats_identified.csv, desks_by_gate.csv), progress/, frames/, .env.
  A new machine has none of it: the code runs and names nobody.
* The Progress tab (laptop): Who sits where (Yes/No on seats named by
  face), Every desk (day, usual week, heatmap), Name the desks (one desk
  at a time, 24 Nov: its hourly pictures with the sitter in a yellow box
  -- `desk_watch.mark_seat` -- the directory picker, and the chosen
  person's directory photo beside it; it saves only on "Save", never on
  a change -- the old grid wrote blanks when the page errored. Names
  given there are certain and become CCTV galleries). The hosted page gets codes and numbers, and the
  named employees' name, ID and directory-photo icon (`cloud_names: true`
  in progress.yaml) -- never a camera picture.
* Session schedules die with the session -- recreate in a new one: the
  night audit every 2 h at :17; a resume check at :07 and :37; on 24 Nov
  18:43 the day's seat-face match and review sheet, 22:37 the gate
  backfill of 19, 20, 23, 24 Nov then gate_match, and the 21:33 Progress
  accuracy report.
* Checked by eye on 24 Nov (72 hourly desk pictures): presence at the
  campus's desks ~80% (36 pictures whose seat could be judged; the five's
  desks 97%); the "talking" rule called seated neighbours visitors on all
  6 read passes -- now one person one desk (desk_activity.assign_desks,
  desks_data.assign_notes) and a visitor must stand and sit at no desk.
  32 of the 72 pictures had the seat off-centre (desk_crop holds the
  square inside the frame): the hourly pictures now carry a ring on the
  seat (desk_watch.mark_seat) -- judge a desk by the ring.
* Open when the session ended (24 Nov 12:35), in this order:
  1. Shamroze: the two "Sightings to check" of P2 at 140-H Reception
     (12:14 and 12:19, scores 0.73 and 0.75) are the receptionist, not
     P2. Write "no" for both (`progress_data.save_review(day, time,
     "P2", "140-H Reception", "no")`; the exact HH:MM:SS times are in
     P2's `focus["possible"]` from `progress_data.build`).
  2. Rebuild `rooms_dashboard.show_sightings` the way Name the desks is
     built (Shamroze: "1 line me 1 image do or agay uska name dalne ka
     kaho me choose krlunga"): one picture to a line, and beside it "who
     is this?" -- the directory picker, saved only on a button. A pick
     that is the employee the network guessed (their ID known from
     progress.yaml or a named desk) is a "yes"; any other pick is a "no",
     and is kept as who that picture shows (a local file under people/),
     ready to feed that person's CCTV gallery.
  3. False body re-ID matches: somebody sitting at a regular seat (any
     desk `desk_seats.find_desks` found, the reception desk included) is
     that seat's sitter, never a sighting of somebody else -- leave them
     out before matching in `progress_track` (reid runs on "people who
     are not at a regular seat of an office"; the reception desk slipped
     through).
  4. Done 12:34: the restarted loop's publish put a name, ID and a
     3-4 KB `photo` in P3's and P5's progress_days rows, and
     `progress_view.page` draws their icons from them. Not yet seen by
     eye on Streamlit Cloud itself (its redeploy installs `pillow` from
     requirements.txt) -- ask Shamroze to look on his phone.
  5. Waiting on Shamroze: whether to build a card like P1-P5's for every
     employee whose desk he names in Name the desks (laptop, and name and
     icon on the hosted page). He is naming desks now; his first three
     (Admin Room dvr2.9-1, -2, -4) were blanked at 12:16 and need
     picking again.
  6. Recreate the session schedules listed above.
  Later: check the gate's and the cameras' sightings of named people by
  eye; label a fresh set of boxed desk pictures to measure computer /
  phone / talking at the campus's desks.

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

At night (after hours) the loop leaves out a box whose pixels have not
moved for 40 minutes (`room_loop.drop_still`, 14 Nov): empty black chairs
in infrared score like people (0.35-0.67) and real people at night as
little as 0.28, so no bar separates them, but a chair never moves. A
sleeper stirs within half an hour and is kept. What it leaves out goes to
`still_spots.json` (local), which `verify_live` treats as a zone -- so a
chair it set aside is not reported MISSED. Its clocks survive a restart
(15 Nov): each pass keeps them, with the small grey picture each camera
was last compared against, in `still_state.npz` -- pictures, so local and
ignored, never a private-hours room, removed by day.

## Air conditioners

Only units whose display the camera can see can be read; see
`ac_units.yaml`. Calibrating needs the unit switched on and off once:

    python calibrate_room.py --live --room "141 Finance Room" --channel 30 --roi 1083,90,1105,115 --write
    python calibrate_room.py --live --room "141 Room 32 (2nd floor)" --channel 25 --roi 1626,6,1646,28 --write

Calibrating from the data, without anybody switching units by hand
(Shamroze, 13 Nov: "calibrate them yourself"): the loop keeps a frame of
every camera that can see a unit every ten minutes, day and night, in
`frames/ac_keep/<date>/<HHMM>/` for three days (never in git; private
rooms are never opened, so never kept). Each morning look there for a
unit switching -- a clean local step at a unit's display or louvre with
the room's lights unchanged -- and calibrate from the frame either side.
A camera that goes infrared at night needs its own night calibration: an
`infrared:` block inside the colour one in ac_units.yaml (same units, same
order, measured on infrared frames), or `colour:` inside an infrared one
(Admin Room). A unit seen face-on by a second camera goes in `also:`.

14 Nov, on site with Shamroze: Prompt Cafe 3 of 5 (both 2.5 t Generals on
ch14, one Kenwood on ch20; `unseen_units: 2` until the other two are in a
camera) and the Mosque's two Kenwoods (ch6, by their displays). Two
lessons: `calibrate_room --add` puts a unit under the room's FIRST camera,
so a unit on another camera must be moved into an `also:` block; and a
unit's view check (anchor) must not take in the recorder's clock or date
-- give it an `anchor_roi` clear of them (the cafe's unit 2 and the
mosque's top unit). `docs/camera_work_list.md` is the list for the camera
team, building by building, from Monday 16 Nov.

19 Nov, from the kept frames with nobody switching (Shamroze: "calibrate
it yourself"): 140-H Reception's split (nvr1 ch11, by its louvre) and
floor tower (ch16, in `also:`, by its front outlet). Two more lessons: a
louvre that swings reads, at its narrowest, as dark as a shut one -- put
`dark_max` under every shut frame, so a narrow swing is "not seen
running" and never the other way round; and a tower whose front panel
slides open changes the view round its own box, so every running frame
read as "the camera has moved" until it got an `anchor_roi` on the
tower's top. Before restarting, replay a new block over every kept frame
against periods checked by eye: a "running" in an off period must be
zero. docs/ac_camera_audit.md has every camera of both campuses and the
units it sees, and at its top the follow-up table (units / in camera /
calibrated) -- keep it current after each calibration. "In camera" per
room is rooms.yaml's `in_view:`; the campus page's "Units a camera reads"
tile counts it live against what is calibrated.

20 Nov, same way: Marketing M1 and the ch13 Kenwood, Basement ch25 Haier.
One more lesson: a view check over a plain white face can pass a wrong
view -- the Kenwood's default region matched the wall the camera saw
before it was moved, 0.57-0.79 in the evening light. Score every new
block's view check against frames from before the camera's last move
too, and if one passes, give the unit an `anchor_roi` on something with
shape (its badge, logo or edge), clear of the louvre and the clock.

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

In the morning: look through `frames/ac_keep/` for units that switched
(day and night, see "Air conditioners") and calibrate what is clean; then
a short Roman Urdu summary — what was found, what was fixed, which ACs
were calibrated, what needs a person.
