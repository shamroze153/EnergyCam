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
