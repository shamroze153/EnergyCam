# Tonight's list (12-13 Nov)

Work through these between the 2-hour audit rounds, one at a time: tests
green, `git status` (no pictures), push, a line in night_log.md, then tick
it here. Shamroze reads the morning summary in Roman Urdu.

- [x] 21:22 AC calibration from frames/ac_watch/ (18:15-21:15): every unit
      with a clear on/off gap gets a box in ac_units.yaml (Rooms 26, 27 and
      8 at 141 are new candidates). Restart the loop after. In the morning
      report: which units were calibrated, on which camera, and how sure.
- [x] Mobile (375 px), light and dark: every tab -- Overview with the
      "worth a look" button and list, Who comes when (day-parts lane, waste
      line), Rooms, Empty time (Rs / day column), Energy, One room (the
      headcount strip). Fix anything cut off, overlapping or unreadable.
- [x] Dark theme: the new pieces (walk list, day parts, headcount strip,
      week grid, Energy tiles) read well on dark.
- [x] Who comes when, "last 7 working days": the waste per room in the
      averaged table too, as the one-day lines have it.
- [x] Energy at 141: tiles per building (main, 141-C, 141-D), as Who comes
      when's "Empty, with the AC on" has.
- [x] Front page: the campus cards' "N rooms worth a walk" opens the
      worth-a-look list (only=walk) rather than the whole campus.
- [x] Energy, meters (Shamroze reads them daily at about 6 pm): set each
      day's units beside its usage -- people-hours from the cameras that
      day -- and show units per person-hour, so a busy day and a wasteful
      day can be told apart. Days are already on a 24-hour footing.

## Added 22:45 (Shamroze: audit all night, catch ghosts, calibrate what you
## can, see where people sit)

- [ ] Every 2-hour round at night: look at the night_check pictures for
      ghosts in rooms with a unit; a clear object gets a zone (never a
      seat), as tonight's Assembly Meeting Room table.
- [ ] Seat notes: the loop now writes seats/<date>.csv (where each counted
      person was, numbers only, this machine only). After a working day,
      draw a seat map per camera locally (dots on an empty-room frame) and
      list in the report which rooms' seats are used; never commit them.
- [x] 09:12 morning report job; 11:12 morning AC calibration from the
      08:00-11:00 watch (both scheduled). Report sent; the watch caught no
      uncalibrated unit switching, but the cafe's tower 6 was calibrated by
      hand with Shamroze (ch 2, `also:`).
- [ ] Night (infrared) calibration: Finance Room, Room 32, Room 27,
      Learning Center go infrared when the lights go off and their
      calibrations are colour-only; Admin Room the reverse. Shamroze, 13
      Nov: do it from the data. The loop now keeps every AC camera's frame
      every 10 min in frames/ac_keep (3 days) and ac_units.yaml takes an
      `infrared:` block; each morning, find a unit's switch in infrared and
      calibrate it there.
      15 Nov 06:05, ac_keep 13-15 Nov: Admin Room's colour block done
      (98c9cc2), and its night "off" now read (the anchor took in the
      flap: 39 of 43 off frames were refused). Finance (IR 1-4),
      Learning Center (8-10), Room 32 (7-8) and Room 27 (1-3) stayed
      flat in infrared both nights -- no unit switched in the dark, so
      nothing to measure yet. Keep looking each morning (scratchpad
      keep_steps.py, ir_series.py). Correction 06:35: Room 27 does go
      infrared (90 frames by ac_detect.is_infrared, which the loop uses;
      a looser test in keep_steps had called its tinted night picture
      colour). Also Room 27 in colour: 16 frames on Sat 14 Nov
      10:41-13:13 refused as a moved camera (anchor 0.45), fine again
      from 13:27 -- look at those frames for what changed by day.
- [ ] Names for cd_nvr4:17 (corridor), :26 (outside lane, guard), :31
      (pantry/kitchen); :30 duplicates the cafe's cd_nvr1:14. Asked.

## For Shamroze, 14 Nov morning: black chairs at night

- [x] 14 Nov: built on Shamroze's yes (room_loop.drop_still), fixed the
      same night for infrared noise, exposure steps and missed passes;
      by 22:17 it set aside chairs in 18 rooms and a real person working
      in 141 Room 22 was still counted.
      In infrared, empty black office chairs read as people at 0.35-0.67
      (Creative Room ch 4 0.59, Room 18 ch 13 0.63, Room 17 ch 5 0.62,
      141 Rooms 25-28 0.35-0.67), while real people at night scored
      0.39-0.57 (141 Room 22 01:47, Creative Room 22:53). A chair is a
      seat (no zone) and a bar would lose the late workers, so those rooms
      read "occupied" through the night and their AC is never flagged.
      Proposal, not built: a night check for movement -- a box whose
      pixels do not change between passes is furniture (a seated person
      breathes, types, turns). Needs his yes; it changes the loop.

- [x] 05:25 done (807132e): each pass keeps the clocks in
      still_state.npz; checked live by restarting at 05:20 -- the first
      pass after it still had Room 27's chair timed from 05:13.
      15 Nov 05:10: every loop restart at night starts the movement
      check's 40-minute clocks again, so the chairs count for 40 minutes
      after each fix (05:03-05:45 tonight). Idea: on stopping, the loop
      keeps each spot's clock and its small grey thumbnail in a local,
      ignored file and reads it back if it is under 15 minutes old.
      Those thumbnails are pictures (480 wide, grey): local only, never
      in git, and never the gym in its private hours (never opened).

## Added 13 Nov evening (the seating sheet, Desks page)

- [x] 18:47 Room 17: the sheet has 24 of its 47 desks given, the cameras
      never saw more than 5 at once. Its three cameras see most desks and
      the chairs were empty: the count is real. xvr3 ch 8 is hazy.
- [x] 07:20 made (frames/morning/camera_list_14nov.jpg, local; to send
      with the 08:53 report). For Shamroze's morning (13 Nov, "send me a picture of which camera
      frames to fix, I will do it myself"): a contact sheet of the cameras
      to clean or turn, each with what is wrong -- local, sent with
      SendUserFile, never in git. So far: 140-H xvr3 ch 8 (Room 17) hazy;
      141 cd_xvr1 ch 1 (Room 22) its right third dark and blurred;
      140-H xvr3 ch 3 (Room 17): the far desks' chairs, cut by the top
      edge, read as people all night at 0.44-0.85 -- tilt it down a
      little (they are seats by day, so no zone, and too strong for a
      night bar); 141 Room 25's alcove chair (one camera, 0.32-0.73).
      Add to it each round.
- [x] 19:25 Seat map for 13 Nov, numbers (`seat_map.py --no-pictures`,
      10-19): Room 18 33 seats used (sheet 43 desks), Marketing 26 (28),
      141 Room 32 19 (17), Room 17 6 (47). AutoOS and 141 Room 22 show
      people every pass but no spot held 15% of the day: their boxes
      wander more than a seat's radius. Local only (seats.txt).
- [x] 22:20 Seat map pictures for 13 Nov (71, frames/seats/, local).
      AutoOS's and Room 22's dots are on real desks, each chair split
      into 3-4 spots: seat_map now measures against a spot's middle and
      reaches 0.3 of the camera's usual box height. Room 22 0 -> 6 seats,
      AutoOS 0 -> 2; the rest about the same. A room with two cameras
      can count one seat twice (Room 32: 22 spots, 17 desks).
- [ ] 140-H rooms on the sheet with no camera room yet: R4, R11, R12,
      R14, R15, 19A/19B (asked Shamroze).

Rules that hold all night: the 141 gym's camera is never opened 15:00-20:00;
no picture into git; no recorder settings; no retried logins (XVR 2 and 4
are IP conflicts, the DVR is on another network -- leave them).
