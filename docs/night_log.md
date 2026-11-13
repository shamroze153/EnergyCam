# Night log

What each overnight audit found and what was changed. Newest at the bottom.
Two or three lines a round; picture file names, never pictures.

## 11 November 2026

* 17:10 field audit (by hand): 64 of 104 rooms matched outright. The loop
  was still on its start-up rooms.yaml, so 14 rooms (NVR2's, the outside
  groups) were never recorded — restart needed after every rooms.yaml change.
* Fixed the same evening: the small detector (Creative 0→3, Squat Wolf
  Room 4 1→4, Marketing 3→6, the shoe rack no longer a person); Creative's
  strict bar only after hours; NVR3's 960x1088 widened; ghost zones on
  141 Finance ch27, Reception Meeting Room ch10, H First Floor Lobby xvr3:16;
  Room 32's ch16 split out as its own meeting room.
* 18:25 round 1 (Claude on the laptop): loop restarted 18:24 on the current
  code. Doctor: all 9 recorders answer. verify_live: 0 MISSED, 0 GHOST,
  76 MATCH, 20 FOLLOWING (the fresh loop catching up), 8 DRIFT, 1 FAINT
  (Squat Wolf Room 0, 0.32). Nothing in rooms.yaml needed changing.
* Fixed: `.gitignore` now really ignores `frames/` and `*.zip` (evidence.zip,
  84 MB unblurred, was one `git add -A` from the public repo);
  `restart_loop.bat` waits with ping, since `timeout` fails without a
  keyboard; test_dashboard/test_alerts fixed for Windows (utf-8, DETECTOR).
* 18:50 Meters said 0 units / Rs 0 for 10 Nov: Save pressed 5-9 times, each
  3-second pair read as a day. Now the last reading of a day counts: 223 +
  259 units, Rs 32,294. Solar has its own card (281 kWh, ~Rs 18,827, 56% of
  the ground floor). New tab "Empty time": each room's empty minutes.
* 20:05 the limit stopped work at ~19:15; a resume job now runs every
  30 min (:07, :37) beside the 2-hour audit.
* 20:15 "First in 12:06 night, Marketing" checked: Marketing really works
  late (check_room at 20:03 shows real people on both cameras; occupied
  1-4 all last night). Not a ghost, so no ignore box. The 7-minute gap at
  midnight made it an "arrival"; first sight within 30 min of midnight is
  now carried over from the night.
* 20:30 money fixed: the peak was counted on UTC (23:30-03:30, not
  18:30-22:30); Analysis now ranks by working-hours empty time (Rs 23,627
  a week) with nights/weekends apart (Rs 105,365 only if units left on);
  front page "at stake today" working hours only (140-H 13,100 -> 2,579).
  "First in" ignores before 5am (DL at 2:43am: check at the 2am round).
* 20:45 round 2: 0 MISSED, 1 GHOST (Entry H, nvr1 ch5, page said 1 at
  20:45, nobody in frame). check_room at 20:52 finds 0.51 at the bottom-
  right corner (536,326-585,360) that looks like the top of a seated
  guard's head: left for Shamroze, no ignore box (frames/verify/
  ghost_Entry_H_ch05_nvr1_2045.jpg, frames/Entry_H_nvr1_ch05_boxes.jpg).
  No unit in Entry H, so no money on it.
* 20:55 AC calibrated: 141 Finance Room ch30, box 1088,99-1103,112 (digits
  only, the CLAUDE.md box held the logo too): on 34.6, off 8.7, gap 25.8.
  Room 32 and Learning Center still on at 20:46; Admin Room reads on.
* 21:05 the loop (restarted 20:58) wrote 141 Finance Room "AC off" at
  21:02: the calibration works end to end. Admin Room: empty since 20:50
  with its unit read ON, a real case for the alert. Room 32 and Learning
  Center still on at 21:02. Auto-finding display boxes for the other
  visible units fails (18:30 daylight vs 21:00 lamps changes the whole
  frame); they need a box drawn by hand on a frame with the unit on.
  Cameras turn infrared when rooms go dark, and a colour calibration is
  refused there by design, so OFF frames must be taken while lights are on.
* 21:30 Empty time gets "Last 7 days": one row a room, one cell a day,
  coloured by the share of watched time it sat empty. Checked on real data
  (Old Finance Room 9h 34m of 15h watched is 140-H's emptiest this week).
* 21:47 AC re-check: Room 32 and Admin Room still read on. Learning Center
  box (196,136-222,174) still shows a dark "25" on a pale face, only dimmer
  with the room light: it looks like a sticker or an always-on display, so
  it cannot tell on from off. For Shamroze: is that "25" a label?
* 22:15 round 3: 0 MISSED, 5 GHOST. Squat Wolf Room 0 (has a unit): an
  object on the desk edge by the window scored 0.27-0.36 in all five
  evidence frames 21:05-22:10, room empty -> ignore box [1795,520,1885,
  635] on cd_nvr3 ch4 (checked: drops it, keeps a person beside it).
  Reception Roof, Cafe Shoe Rack, H Basement Parking, P1 Parking: on/off
  all evening like people passing, no units -- left alone. Loop restarted.
* 22:47 AC: Admin Room now reads off (1.3). Room 32's display went dark
  (14.8 -> 5.1) but the camera is in infrared now, and calibrate_room
  refuses colour-on against infrared-off, rightly. Room 32 needs an off
  frame with the lights on (or an on frame in infrared): for the day.
* 00:15 round 4: 0 MISSED, 3 GHOST (141 MR 01, IT Head Room, 141-D
  Genset). Night check, every detection looked at: real people still in
  Admin Room (0.91, 0.74), Wellows (0.81), Prompt Cafe (0.81). Ghosts
  that kept rooms flickering occupied all night, fixed for night only:
  DL Department chairs 0.28-0.29 -> conf_after_hours 0.40 (also the
  "2:43am first in"); Room 18 plant/monitor 0.48, clutter 0.28-0.31 ->
  0.55; 141 Assembly Meeting Room chairs 0.34 -> 0.40. 141 Gym poster
  0.34 -> ignore box. Loop restarted.
* 00:50 the round-4 ghosts followed up: 141 MR 01 had an object left on
  the table read at 0.27-0.42 (evidence 23:54, 00:07, 00:25; a real
  cleaner at 23:29) -> ignore box on the table top, cd_nvr1 ch9.
  IT Head Room at 00:08 is a real person. 141-D Genset: outside, no unit.
* 02:15 round 5: 0 MISSED, 2 GHOST. The MR 01 and Gym zones hold (their
  detections now "0 counted"). Pantry: a real person 01:11-01:41 (0.57-
  0.93), left alone. DL Department still flickered on one chair at 0.47-
  0.49 (a real person at 01:04 scored 0.85) -> night bar 0.40 -> 0.55.
  Night-only bars: Room 17 chairs 0.26-0.32 -> 0.40; Prompt Cafe chair
  0.41 -> 0.50 (real people 0.81); H First Floor Sitting Area cushion
  0.32 -> 0.40. Creative Room chair at 0.42 is over its 0.40 night bar,
  but its real people under the purple light score below 0.40, so left
  for Shamroze (frames/Creative_Room_dvr2_ch04_boxes.jpg). Loop restarted.
* 04:15 round 6: 2 MISSED, both objects, not people: Room 18 a jacket on
  a chair at 0.58 (the loop rightly read empty; no change), H First Floor
  Sitting Area the cushion on the glass ledge at 0.61 -> zone. A real bug:
  141 Reception Meeting Room's zone [330,150,620,520] was drawn on 1920x1080
  but ch10 is read at 640x360, so it covered the room's own table and hid
  people sitting there, while the desk beyond the glass was still counted.
  Now [108,44,212,178] (checked: desk dropped, table kept). Every other
  zone checked against its real frame size: all inside. Outdoor ghosts
  (Solar Array, parkings) left. Loop restarted.
* 04:40 check_room (and so every night check) now warns when a zone
  reaches past the frame it is used on -- the test that would have caught
  the Reception Meeting Room zone a day earlier. Test in test_verify.py.
* 06:15 round 7: 0 MISSED, 6 GHOST, no zone warnings. The ghosts in rooms
  with units (Assembly, 141-D MR02, Squat Wolf 4, H First Floor Lobby)
  are one or two events each since 02:30, around dawn: not chronic, left.
  Pantry mugs on the counter at 0.34 -> zone on nvr4 ch17. For Shamroze:
  Room 17's chair now 0.44 (over its 0.40 night bar) and Room 18's chair
  with a jacket 0.61 (over 0.55) as the light changes at dawn -- raising
  the bars further risks real people, so left (frames/Room_17_xvr3_ch03_
  boxes.jpg, frames/Room_18_xvr3_ch13_boxes.jpg).
* 07:45 Room 32 AC tried again in morning colour light: its box (1626,6-
  1646,28) gives on 14.8 vs off 11.4, gap 3.4, refused -- the box is not
  on the lit display well enough. Needs redrawing on site, unit running.
* 08:15 round 8: 0 MISSED, 2 GHOST, 82 MATCH, no zone warnings. Room 21
  was empty all night (no flicker); the ghost is a morning arrival at
  08:08 gone before the check. 141 Outside (NVR 3) is outdoors. Nothing
  changed.

## 12 November 2026, the day

* Morning: the cloud page died on a stale analysis_view (fixed: modules
  reload when their files change). Who comes when: one-click days/hours,
  readable in light theme. 141-C Room 3 store: night bar 0.50.
* 10:48 round 9: 0 MISSED, 0 GHOST, 84 MATCH.
* AC on site with Shamroze switching units: Learning Center (3 units, the
  floor one by its louvres), Room 32 (3 units, the one above the TV by its
  flap), 141-C Cafe (6 x 2-ton towers, five by their louvres on ch14).
  Assembly Meeting Room's one unit is in no camera -> ac: hidden. Rooms
  with units no camera sees read "on" when any seen unit runs, and
  unknown, not "off", when the seen ones are off.
* 11:30 the campus page opens on "Air conditioning, right now": units
  running, kW, Rs an hour, empty rooms with units on flagged SWITCH OFF.
  The loop counts units running (ac_units_on; needs sql/09 run once).
  Rooms can carry ac_tons; money and kW follow it (cafe 2 t, Assembly 1 t).
  141 Finance Room read "camera moved" all afternoon: sun through the
  window under the unit. Its anchor now covers the unit and the wall above
  (0.97-0.98 day and evening). All five calibrated rooms read live.
* 13:00 Shamroze's 140-H AC survey (57 units, 74.5 t) in rooms.yaml:
  each unit's tons for 12 rooms (ac_tons lists), and the directors' rooms,
  the data centre and the guest room as unwatched_units. Still to place:
  the ground-floor director room, the prayer area (GCR), the glass meeting
  room, Rooms 7, 8, 9, and the basement's six between its three rooms.
* 13:10 all 140-H units placed (Shamroze: Cyber Security 1 t, Old Finance
  1 t, the basement's 2 t in its meeting room). Placed by judgement and
  marked "check" in rooms.yaml: IT Head Room = the survey's director room
  (2 t + 1 t inverter; no Room 11 in the survey), Board Room = GCR 2 t,
  HR = Room 7 2 t, Marketing = Room 8 5 x 1 t. rooms.yaml now adds up to
  the survey exactly: 57 units, 74.5 t (39 x 1, 3 x 1.5, 13 x 2, 2 x 2.5),
  a test holds it there.
* 12:47 round 10: 0 MISSED, 0 GHOST, 81 MATCH. Loop restarted after it.
* 13:40 campus page: "The building, floor by floor" -- every room drawn
  with its people and its AC (running / off / not visible), SWITCH OFF on
  empty rooms with a unit running, and its usual day once two watched days
  agree (cleaners' early rounds left out, nights counted as nights). 140-H
  floors in rooms.yaml. "Enter campus" no longer asks for the password
  again: the door writes an entry ticket into the address and every link
  carries it. Prompt Cafe, Commons and Mosque are their own lines now, not
  "Cafe & common" added up (Shamroze saw 15 for a cafe holding 10-12).
* 14:05 Meters and Analysis are one tab, Energy, with each room's AC
  electricity today against yesterday by this time (kWh, Rs, the part with
  nobody in). At full rated power 140-H's ACs came to 1,073 kWh on 11 Nov,
  more than the whole building's 763 on the meters: ac_duty 0.5 in
  rooms.yaml, and the tab shows the ACs' share of the latest meter stretch
  (66%). Who comes when: "Empty, with the AC on" for 140-H, 141 main,
  141-C and 141-D. IT Head Room is 1 unit (Shamroze), the survey's 1 t
  inverter moved to an unwatched director room. Sizes read "5 AC · 1 ton
  each · 5 ton total". Meter readings: only 10 and 11 Nov are in the
  database; none since. Loop restarted 14:03.
* 14:20 Shamroze: IT Head Room's one unit is 1.5 t. So it is not the
  survey's director room (2 t + 1 t, now an unwatched director room), and
  the survey list missed it: 140-H is 58 units, 76 t (test updated).
* 14:35 field audit: 79 MATCH, 4 GHOST, 1 MISSED. All five were real
  people the page showed a pass late (UPS Room, 141-C Room 3 store, 141
  Finance Lobby, Genset Area, Cafe Shoe Rack): each went empty/full at the
  next pass, no object. No zones. Passes took 4-7 min: the loop now
  fetches the next batch's cameras while it counts (14:47 pass: 211 s, of
  which 151 s waiting on cameras, 60 s counting; cycles.csv now says so).
* 141-C/D recorders: NVR 1-4 connected; XVR 2 (.59) reachable, login
  refused; DVR on 192.168.1.64 (another network); XVR 1/3/4 have no
  address on file. 192.168.67.77 and .78 answer as Dahua recorders not in
  our list: probably two of XVR 1/3/4. For IT.
* 14:49 every recorder, both campuses, stopped answering RTSP from this
  laptop (HTTP pages still load, the cable is fine): nothing recorded from
  about 14:48. Likely the recorders' own protection after an audit, three
  loop restarts and a port check within fifteen minutes. A change taking
  rooms in turns between recorders went in at 14:49 and was reverted, as
  the first suspect; it was not the cause but stays out until tested on a
  healthy network. Loop stopped 15:04 so it stops retrying; checked again
  at 15:27 with an RTSP OPTIONS (no login) before restarting.
* 15:06 the cause: Shamroze had unplugged the laptop's camera cable and
  put it back. Every recorder answers again; the turn-taking change is
  back in (the diagnostic that blamed it ran with the cable out). Loop
  started 15:07; first pass 209 s, 0 unknown: 112 s waiting (was 151),
  98 s counting (was 60) -- the laptop's CPU now decodes and counts at
  once, so ~210 s is its pace. A gap in the record from ~14:48 to 15:07.
* 15:30-16:00 XVR 1 (Shamroze's login): 192.168.67.77, 16 channels. Its
  2nd-floor rooms are in: Rooms 22 (CS), 24-29, pantry, lobby, corridor;
  ch 14 is a second angle on Learning Center. Learning Center's ch 2 had
  counted a man in the next office through the glass and missed the one
  in the room (feet on the table); ch 14 sees him, and a zone over the
  doors drops the other (frames/141_Learning_Center_*_boxes.jpg). Fixed
  check_room for rooms on two recorders. Loop restarted 15:55: 115 rooms,
  230 s a pass, 0 unknown. Still to come: XVR 2 (login), .78 (XVR 3 or
  4, login), the last XVR's address, the DVR (192.168.1.64, needs an IP
  on 192.168.67.x), and the units in the new offices.
* 16:10 XVR 2: not a bad login but an IP conflict -- another device
  (80/554/8000, its own MAC) answers at .59, where the XVR's own ports
  (8200/8201) are shut. IT to move it (.63, .81, .87-.99 free). XVR 3
  (Shamroze's login) is 192.168.67.78: ground-floor Rooms 3 (IT), 5 and 8
  (vacant), 6 (three angles), 7, 11 (IVC), the ground- and first-floor
  lobbies; ch 12 black. Checked live: Room 6's people found (one far
  person boxed twice on ch 6 -- a count drift, not a fault), vacant Room 8
  empty. "(ground floor)" in a 141 name now files under Ground floor.
* 16:27 field audit, 123 rooms: 89 MATCH, 5 GHOST, 2 MISSED -- all people
  moving (a man from vacant Room 5 to vacant Room 8; Board Room's meeting
  ending; Gaming Area, Mosque), each right on the next pass; the gym's
  was a real person at the back; P2 Parking outdoors, no unit, left.
* 16:40 Shamroze: the 141 gym is ladies-only 15:00-20:00 -- take no data
  then. private_hours on 141 Gym: the camera is not opened in those
  hours by the loop or any tool; the room reads unknown (16:49). Gym
  pictures taken inside those hours were deleted (today's checks; the 11
  Nov 17:46-18:36 pack, loose and zipped). The counts already written
  for 15:00-16:45 today are still in the database: Shamroze to say.
* 16:40-16:50 every XVR 1 / XVR 3 camera checked by eye: people found
  right in every office; vacant Rooms 5 and 8 right. The 2nd-floor
  corridor counted people in the offices through its glass walls (ch 5,
  6, 12): three zones, re-checked to 0. Hazy lenses worth a wipe: XVR 1
  ch 1 (Room 22), ch 12 (corridor), ch 14 (Learning Center). Loop
  restarted 16:45.
* 16:51 round: covered by the 16:27 audit and the 16:40-16:50 camera
  check, so no second audit on top of them. Loop healthy: 123 rooms, 252 s
  a pass, the one unknown is the gym in its private hours; no gym picture
  since 15:00 anywhere on the laptop.
* 17:00 Shamroze: delete the gym counts written 15:10-16:39 today. The
  loop's role is refused (rightly: it cannot read or delete a room's
  rows), so sql/10_gym_ladies_hours.sql is for an administrator to run in
  Supabase; earlier days' 15:00-20:00 gym rows are a commented block.
* 17:15 Shamroze ran sql/10 (all days, at his word): checked read-only,
  the gym has no count left in 15:00-20:00 on any day -- only "unknown"
  at 15:00 on 11 and 12 Nov and the loop's own at 16:49.
* 18:30 Shamroze's readings for 12 Nov are in (he will read at about 6 pm
  daily): ground floor 51,718 (213 units in 25.7 h), first floor 33,265
  (262), solar 255 kWh. Each day is now put on a 24-hour footing (213 in
  25.7 h is 199 a day), the raw figure and hours in the tooltip. Evening
  dashboard work: worth-a-look list, day parts, the headcount strip over
  the whole day, Rs / day, colours, quiet loading, a heartbeat every
  minute. Night jobs: 2-hour audit, 21:22 calibration, the 30-minute
  check working through docs/night_todo.md.
* 18:47 round: 75 MATCH, 3 GHOST, 1 MISSED, gym "no camera" (private
  hours, as meant). Board Room, First Floor Lobby and Cyber Security were
  people moving, right at 18:57. Pantry read 2 from 18:44 with nobody in
  any of its three frames and no object to blame: no unit there, left;
  look again next round (frames/verify/ghost_Pantry_ch1*_nvr4_1847.jpg).
  Heartbeats now every ~70 s. Nothing changed, no restart.
* 19:30 phone check (375 px), light and dark, every tab: no sideways
  scroll anywhere. Fixed: Rooms rows ran 30 px past the screen (fixed
  column widths; the name now shrinks); One room's hourly chart had its
  hours near-white on the light page and Plotly's toolbar over the bars
  (own colours, no toolbar, margins for the axes); the key's "not
  watched" and "not yet" swatches were invisible (outlined).
* 19:55 Who comes when, last 7 working days: a "Wasted / day" column,
  averaged only over days the loop watched for 12 hours or more (so far
  one: Wed 11; the header says how many). Disrupt Labs Rs 516 that day.
* 20:25 Energy at 141: a card a building under the tiles -- today so far
  141 main Rs 8,603 (Rs 909 with nobody in), 141-C Rs 3,160, 141-D
  Rs 3,144. The gym watched again from 20:00 (0 unknown).
* 20:55 front page: under each campus card, "N rooms worth a look ->"
  straight to that campus's list (7 at 140-H, 9 at 141 this evening).
* 20:47 round: 91 MATCH, 10 GHOST, 1 MISSED -- the end of the day, people
  leaving: nine were right on the 20:56 or 21:01 pass. 141 Assembly
  Meeting Room flickered every pass: a bag on the table read 0.56 on ch 4
  in the dark (frames/141_Assembly_Meeting_Room_cd_nvr2_ch04_boxes.jpg)
  -> a zone on the table top. Loop restarted 21:08.
* 22:05 evening AC watch (18:15-21:15, every 5 min, 36 cameras): one unit
  switched off cleanly with the lights left on -- 141 Room 27's split,
  ch 7: its display lit to 19:40, dark from 19:45. Calibrated, box
  272,150-300,176: on 51.2, off 5.2, gap 46 (frames/141_Room_27_(2nd_
  floor)_ch07_box.jpg). Room 26's floor unit and Room 8's split never
  changed all evening; Marketing ch3 and Room 17 ch5 were people and a
  light, not units. Loop restarted.
* 22:30 Energy, meters: "Units for the use they were for" -- each meter
  day's grid and solar units per person-hour (people x hours in the rooms
  on those meters, from the cameras, only while the loop was watching).
  Wed 11: 699 units for 868 person-hours, 0.81 each; days watched under
  20 hours get no ratio, and say so. Tonight's list is done.
* 22:50 Shamroze: keep auditing all night, calibrate what you can, see
  where people sit. The loop now notes each counted person's place in the
  picture (seats/<date>.csv, numbers only, this machine only): 62 in the
  first pass. A morning AC watch waits for 08:00-11:00 (people switching
  units on) with the calibration at 11:12; the report at 09:12. Loop
  restarted 22:46.

## 13 November 2026

* 00:20 round (the 22:47 one was lost to the usage limit): 108 MATCH,
  0 MISSED, 2 GHOST -- 141's open-air first-floor lobby and P1 Parking,
  no units, left. The seat notes found "people" at the same spot all
  night: Squat Wolf Room 2's empty chair (0.31, 17 passes) and HR Room's
  monitor and chair back (0.29, 16) -> night bars 0.45 and 0.40 (seats,
  so no zones). Left for Shamroze: Marketing ch13, a small shape behind a
  chair at 0.34 that may be a head (evidence/Marketing_dvr2_ch13_
  20261113_000515.jpg); 141-C Cafe ch2, a thin figure by the far pillar
  at 0.55, maybe the guard (frames/141-C_Cafe_cd_nvr1_ch02_boxes.jpg).
  Wellows' 0.78 and 0.66 are real people working late. Loop restarted.
* 00:47 round: covered by the 00:20 audit. The two night bars hold: no
  "person" in Squat Wolf Room 2 or HR Room in the seat notes since 00:40.
  Loop healthy, 0 unknown.
* 01:05 seat_map.py: a day of seat notes -> seats per room (seats.txt) and
  a picture per camera (frames/seats/, local). Tried on 23:00-24:00: the
  141-C Cafe's 1-8 people at night are real (scores to 0.82, counts
  moving), Wellows has a desk held 93% of the night. The working-day map
  comes after today.
* 01:30 phone check again, dark, front page and every tab at both
  campuses: nothing past the screen but one line in Energy's "Where to
  start" list at 141 (a room's long figure), now wrapping. The list is
  done; the rest of the night is the 2-hour rounds and the morning jobs.
* 02:47 round: 105 MATCH, 0 MISSED, 2 GHOST, both empty office chairs
  the seat notes had flagged: AutoOS ch 10 (tall dark chair, up to 0.67,
  12 passes -- likely 12 Nov's "first in at 2:38 night") and 141 Finance
  Room ch 27 (0.30-0.49) -> night bars 0.70 and 0.55 (evidence/AutoOS_
  dvr2_ch10_20261113_025800.jpg, evidence/141_Finance_Room_cd_nvr1_ch27_
  20261113_025530.jpg). Loop restarted 03:05.
* 04:47 round: 107 MATCH, 0 MISSED, 2 GHOST. 141-D Outside Area is
  outdoors with no unit (no waste, left). Marketing: tiny boxes on desk
  things, ch 3 at 0.39 and ch 13 at 0.34 -> night bar 0.45. The seat
  notes also showed Room 17 with 1-5 "people" every pass all night (two
  empty chairs at the top of ch 3, median 0.52-0.56, up to 0.82) over its
  0.40 bar, so its four units were taken as running all night -> 0.60
  (evidence/Room_17_xvr3_ch03_20261113_045812.jpg, evidence/Marketing_
  dvr2_ch03_20261113_045912.jpg). Loop restarted 05:06.
* 05:25 phone check, dark, both campuses, every tab: nothing past the
  screen, no errors. Rooms' "Every room" heading broke over two lines
  beside its caption on a phone; the caption now wraps under it. Today's
  biggest AC figure at 140-H is Room 17's 13 kWh -- the chairs before
  05:06, for Shamroze in the morning.
* 06:47 round: 95 MATCH, 0 MISSED, 4 GHOST, 21 FOLLOWING. First, a
  correction to 04:47: Room 17's 0.60 was wrong. 12 Nov's evening frames
  show a real person at that same far desk on ch 3 scoring 0.87 (frames/
  ac_watch/2040) and one on ch 8 at 0.37-0.57; chairs and people score
  alike there, so back to 0.40 and left for Shamroze. The night bar can
  now name one camera (conf_after_hours: {10: 0.70}): AutoOS ch 10 and
  141 Finance Room ch 27 only, so their other cameras keep the normal
  bar; Marketing 0.45 -> 0.40. Ghosts: 141 Gym ch 7 weight plates and
  141 Room 6 ch 7 wall marks -> tight zones. 141 Room 26 ch 10 (chairs
  where people sit and score 0.45-0.90 in the evening) and 140-H Commons
  (far terrace chairs, no unit) left. Loop restarted 07:01. The audit's
  night_check (07:04): 20 detections, indoors only faint one-offs (0.28-
  0.42, Wellows, Rooms 22/25, Squat Wolf 1) and a real person in Room 29
  at 06:58 (0.89). Nothing more changed.
* 08:20: the morning AC watch had not started -- the scratch watcher,
  started at 22:45, re-read the date after midnight and was waiting for
  14 Nov. Fixed and restarted at 08:21: 36 frames from 17 rooms every
  five minutes until 11:00, for the 11:12 calibration.
* 08:47 round: 93 MATCH, 0 MISSED, 2 GHOST, 17 FOLLOWING. Wellows: a
  real person 08:33-08:51 (0.90-0.92) had just gone out -- jacket on the
  chair, bag on the desk -- the loop a pass behind, not a fault. 141 Room
  26: the known chairs, left. Night check at 08:57 is people arriving.
  Nothing changed, no restart.
* 09:50 calibration, first look at 08:21-09:46: no uncalibrated unit
  switched cleanly. Room 26's unit turned yellow at 08:51 together with
  the floor under it -- the wooden door opening, reflected, not the unit;
  Marketing, Wellows, Mosque unchanged; Room 8's flap sits under the
  clock overlay. The calibrated ones read right in daylight: 141-C Cafe 2
  running / 3 off, Room 32 one running with its person in. The rest at
  11:12, on the full 08:21-11:00 watch.
* 10:00 Shamroze: the cafe's six towers are all in the cameras -- why "1
  not visible"? The sixth is the tower on the right of ch 14 by the plant
  (frames/cafe_sixth.jpg), side on: its louvre faces away and nothing on
  it moved when towers 2 and 4 went off at 20:35 on 12 Nov. ch 2's tower
  is one of the five from the far end. The panel says "not readable" now;
  reading it needs one on/off by hand while the cameras are watched.
* 10:30 Shamroze: on a room's page he cannot tell whether the AC ran while
  the room sat empty. One room now has an AC line under the people line,
  slot for slot (blue running with people, red stripes running with nobody
  in, grey off, dark grey not read; paler where it is assumed), and three
  cards: how long it ran, how long with nobody in, Rs wasted. A 20-second
  live watch of the cafe runs to 11:21 for the sixth tower's switch.
* 10:40 Shamroze: why "not read" for the cafe all night? Two faults. At
  20:45 the lights changed round towers 2 and 3 (match 0.17-0.31) and the
  whole room was refused as "camera moved", though 1, 4, 5 matched; now
  only the astray units go unread. And from 07:14 the loop read all five
  off (units 0, room unknown for the sixth) and the AC line drew that as
  not read; now it is off. Loop restarted 10:39. Last night's rows stay as
  written; tonight should read three towers.
* 10:47 round: 93 MATCH, 0 MISSED, 3 GHOST -- 141 Gym (people exercising,
  0.73-0.82, gone by the check) and Reception Meeting Room (a real 0.78)
  the loop a pass behind; 141 Outside (NVR 3) outdoors, no unit. Nothing
  changed for them.
* 11:00 the cafe's tower 6 is the one at the back by the coffee machine,
  face on to ch 2 (Shamroze; I had been looking at the wrong tower). He had
  it switched off at 10:53: its louvre read ~52 on, ~23 off. A room can now
  be read on more than one camera (ac_units.yaml `also:`), and the cafe
  reads 1-5 on ch 14 and 6 on ch 2 -- six of six, a real "off" at last.
  Loop restarted 10:59. The panel now says "3 of 6 running".
* 11:10 Shamroze: the cafe's AC line still says "not read" for 00:00-
  07:14 -- the camera never switched off. Right: those rows were written
  before the 10:39 fix (tower 4 matched 0.53 at 07:09 and the whole room
  was refused); kept pictures read them now as off, but rows already
  written stay. Tonight the lights will still put towers 2, 3 and 6 astray,
  and 1, 4, 5 read. "not read" renamed "unit unreadable (camera on)".
* 11:30 Shamroze: confirm the units stay readable at night, when nobody is
  there to look. Not yet: last night's rows show Finance Room, Room 32 and
  Room 27 unread from about 01:00 to 07:00, and the night audits' pictures
  say why -- those cameras switch to infrared when the lights go off, and
  every calibration but Admin Room's is colour-only (Admin Room is the
  reverse: infrared-only, so colour evenings are refused). Each needs a
  night calibration: one on/off in the dark. Asked for.
* 11:30 Multi-camera rooms: the recorders' channel names are all defaults
  (read once each, read-only), so Shamroze's names live in his viewer.
  Every live channel is in a room except cd_nvr4:17 (a corridor), :26 (an
  outside lane with a guard), :31 (a pantry/kitchen) and :30, a duplicate
  of the cafe's cd_nvr1:14. Names asked for.
* 11:40 morning calibration (08:21-10:56 watch, every 5 minutes): no
  uncalibrated unit switched cleanly. Every local step was a chair, a bag,
  a door or a person (Room 17 ch 5, Reception, Room 26, Cyber Security,
  H First Floor Lobby, Marketing ch 3); the unit areas of Marketing,
  Wellows, Mosque and Room 8 stayed flat. Those units need a hand on/off,
  as tower 6 had. Nothing written.
* 12:30 Shamroze: from Who comes when, recommend AC timings -- when to run
  how many units, when to keep all off. ac_plan.py: each room's people
  half hour by half hour over up to ten working days, units in proportion
  to its busiest half hour, one unit after 8 pm only where people are
  there as a habit, short dips and short visits smoothed out. Under Who
  comes when, a line and a 24-hour bar a room, with the saving against all
  units 10-8. The cafe, from one full day so far: 1 at 10, 2 from 10:30, 3
  at noon, all 6 at 3, down to 2 by 6:30, 1 after 8 -- about Rs 1,600 a day
  less. test_ac_plan.py.
* 13:15 Shamroze: the timings on the front page too, one click, for the
  rooms a camera reads (with what was observed) or every room. A button
  under the campuses opens "Recommended AC timings" for both; read rooms
  get a second, amber bar of what their units really did. Where every unit
  is read the plan is capped at the most ever seen running: the cafe ran
  16 unit-hours a day on two or three towers, the uncapped plan asked for
  36. Capped: 1 at 10, 2 at noon, 3 at 3, 1 after 6:30, never more than 3
  -- about Rs 2,580 a day less than all six 10-8.
* 13:15 Loading: a new visit sat on a black screen while the page was
  built. Now a curtain is the first thing painted -- before pandas and
  plotly are imported -- naming the campus, with changing lines and a
  moving bar, lifted when the page is built; only on a visit's first run,
  so the half-minute refresh does not flash it.
* 13:30 The loop now keeps every AC camera's frame every 10 min in
  frames/ac_keep (3 days) for calibrating from the data, and
  ac_units.yaml takes an `infrared:` block for nights. Loop restarted
  12:24; 26 frames in its first minutes.
* 15:35 Shamroze: the timings page looked odd. Rebuilt as cards, a room
  each, on one page: the saving on top, then the day in five parts in
  plain words (night, arriving, working hours, going home, after hours --
  "1 AC 10am-12pm -> 2 AC 12pm-3pm -> ..."), the bars behind "Details".
  Three tiles above: the day's saving, the rooms, the room that saves most.
* 15:30 round: 87 MATCH, 0 MISSED, 6 GHOST; the gym not opened (ladies'
  hours). 141 Room 21 ch 23: a black bin under the counter counted 74
  times today, 00:00-15:38 -> a tight zone (74 of 75 notes go, ch 24's
  people stay). The rest were people just gone or outdoors. Loop
  restarted 15:42.
* 15:50 Shamroze's survey of 141's ground floors, by room: 141-C 14 units /
  21 t, 141-D 28 units / 31.5 t. Rooms the cameras see got their units;
  the rest went into unwatched_units (counted, never read). 141-D's
  ground-floor rooms are named "141 Room N (ground floor)": a new
  `building:` in rooms.yaml puts them under 141-D without renaming them.
  To confirm with him: whether Reception meeting room 2 and Assembly
  meeting room 2 have cameras, and whether 141 Admin Room is 141-D's R1.
  First and second floors to come. Loop restarted 15:53.
* 16:47 round: 84 MATCH, 1 MISSED, 3 GHOST; the gym not opened. The
  MISSED is 140-H After Entrance, a passage (no unit). UPS Room's people
  are real visitors (0.67-0.88; cooled on purpose anyway), the Meeting
  Room Lobby's too (0.85-0.90); 141 Reception Roof has a small thing at
  0.34 on ch 14 -- outdoors, no unit, left. Nothing changed, no restart.
* 17:00-18:45 Desks: the admin team's seating sheet into seating.yaml,
  counts only (701 desks, 399 given; no names), and a Desks tab. Shamroze
  matched 141-D: Finance is Room 19, HR Rooms 17-18, the data centre
  Rooms 15-16 (none of its desks given, whatever the sheet says -- an
  `override:`). Loop restarted 18:18 for Finance and the data centre's
  `building:`; one loop running.
* 18:47 round: 123 rooms, 2 GHOST, 1 MISSED, 2 FAINT, 7 DRIFT; nothing
  with a unit. Attendance Machine H and P3 Parking show nobody (a pass
  behind, no unit); the Pantry miss is a real person just in (0.89).
  Room 17 (47 desks, never more than 5 seen): its three cameras see most
  desks and the chairs really are empty -- the low count is real. But
  xvr3 ch 8 is hazy (lens dirty or misted): on the list for Shamroze's
  morning camera fixes. Nothing changed, no restart.
