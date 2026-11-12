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
