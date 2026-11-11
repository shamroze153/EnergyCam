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
