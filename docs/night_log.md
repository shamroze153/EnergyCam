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
