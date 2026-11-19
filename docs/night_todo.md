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
- [x] Seat notes: the loop now writes seats/<date>.csv (where each counted
      person was, numbers only, this machine only). After a working day,
      draw a seat map per camera locally (dots on an empty-room frame) and
      list in the report which rooms' seats are used; never commit them.
      17 Nov 19:25: `seat_map.py --day 2026-11-17`, 102 maps in
      frames/seats (ignored), seats.txt local. Busiest: 141-C Cafe 30
      seats, Room 18 29, Marketing 24, Room 32 23, Prompt Cafe 22,
      Basement 21. Room 18's dots sit on its desks. Run it again any
      working evening; it honours the gym's private hours.
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
      Done 07:20 (9893b64, 7cb4f16): the room's ceiling light was on;
      anchor moved to the TV's corner. And checking every unit against
      the frames either side of its threshold found three reading a
      running unit as off -- Room 27 by day (28.2 -> 12.4), Learning
      Center (36.1 -> 27.2: running at 04:22 on 14 Nov, unflagged),
      Prompt Cafe General 1 in the evening (38.7 -> 30.4).
      19 Nov 06:00, ac_keep 17-19 Nov: Finance flat in infrared (~2),
      Learning Center no longer goes infrared, Admin Room's infrared reads
      its unit on from 02:13 (a person in). Room 32: 17 Nov 07:17 -> 07:30
      its flap seems to open in infrared (contrast 8.7 -> 15.4) -- but the
      dawn lifted the room's light at the same moment (upper right 73 -> 91),
      so not a clean step (frames/room32_ir_step_17nov.jpg). Wait for a
      morning where it switches with the light steady before an infrared
      block.
      19 Nov 07:50: the same step at the same minute (07:19 9.2 -> 07:32
      15.3, light 78 -> 91; frames/room32_ir_step_19nov.jpg): it is the
      dawn on the unit, not the unit. An infrared "on" for Room 32 must sit
      above ~16, or every sunrise reads as switched on.
- [ ] Still to look at (scratchpad units_audit.py, unit_values.py):
      Prompt Cafe's Kenwood on ch 20 reads 21-29 around its 24.6 on the
      afternoon of 13 Nov (on or off not known) and its view check fails
      at night (-0.38) -- best re-measured with Shamroze switching it.
      Mosque: 87 of 142 colour frames fail the view check, Finance 52 of
      108: unread rather than wrong, but find when and why (as Admin
      Room's flap and Room 27's ceiling light).
      07:40: Mosque -- all its unread frames are from before its camera
      was turned on 14 Nov 11:40; every frame since reads. Finance --
      fixed (dc29305): its anchor was on the unit's top vents, seen only
      under the room light, so from 13 Nov 23:36 it was unread for 32
      hours; now on the floor unit's lower body. Only the Kenwood is
      left. For Shamroze: Finance also has a floor-standing unit on the
      right wall, in camera, while the survey says one AC.
- [x] 11:30 Done: louvres and flaps read by darkness (ac_detect.darkness,
      `dark_max` per unit), checked against every kept frame 17-19 Nov.
- [ ] Prompt Cafe's ch 20 Kenwood is `unread: true` until measured again
      with somebody switching it (no gap between open and shut).
- [x] 141-C Cafe tower 5 (far end, by the neon wall) read "on" 07:05-08:09
      on 19 Nov with its louvre shut: the ceiling lights off and the pink
      wash on the tower's edge lift its box to 25-36, inside the 31-39 it
      reads when truly open by day (18 Nov 11:33-14:05, slats plain), so no
      threshold separates them (frames/cafe141_unit5_compare.jpg). Needs a
      read of the slats themselves (stripes), or a box clear of the edge.
- [ ] Basement (140-H): units in frame since the camera team's 19 Nov
      adjustment -- ch 25 Haier display ("24"), ch 24 Haier whole, ch 23 a
      Kenwood and two splits cut by the top edge; DL Department's unit at
      ch 1's right edge. ac: visible from 19 Nov, so ac_keep holds their
      frames: calibrate each from its first clean off/on. Ask the camera
      team to tilt ch 23 down a little; Basement Meeting Room's unit is in
      no camera yet.
      19 Nov 22:30: ch 23 is moving -- tilting down by itself, its picture
      26 px higher at 22:20 than at 12:20, ~2.6 px an hour without a break
      (phase correlation; ch 21, 24, 25 and DL held within 1 px). A box on
      it would slide off within hours: none of ch 23's units is calibrated
      until it holds still (camera_work_list: tighten the mount). Its split
      D (top centre) switched off at ~22:00 -- the slot under its flap,
      open all day, shut at 22:07 -- the first clean switch seen there.
      ch 24, ch 25 and DL: no switch yet.
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

- [ ] 15 Nov 07:10, PROPOSAL (needs Shamroze's yes; it changes the
      count): when a camera switches between infrared and colour (dawn,
      dusk), every chair already set aside comes back as a box of
      another shape and is counted for forty more minutes (06:04-06:54
      today: Marketing, Creative, Basement, Room 18, Cyber Security,
      Squat Wolf 1 and 4). Idea: on a pass where the camera changed kind,
      a new box that mostly overlaps a spot already set aside keeps that
      spot's clock; it is checked for movement again from the next pass,
      so somebody who sits down at dawn is counted one pass late at most.
      19 Nov, again: 06:27-06:40 nine rooms came back "occupied" together
      (Marketing, Room 17, 141 Rooms 24/27/29, 141-C Room 3, H First Floor
      Lobby, Wellows, Data Centre Ops) -- Marketing's at 06:34 is a chair at
      0.47 in a dawn picture (frames/Marketing_dvr2_ch13_boxes.jpg).

## Added 17 Nov (Shamroze)

- [x] 141-C Cafe read 2-3 of 6 when 4 ran (16 Nov 16:42): towers 2 and 3
      failed their view check by day; anchors moved, tower 3's night
      threshold raised (a6cbd92).
- [x] Each room and campus, each day: AC cost, the waste, which hours,
      and a chart -- "Hour by hour for" on the Energy tab (59abacd).
- [x] 07157bb: light by default, sidebar, today-at-a-glance cards and
      a tip on each campus Overview (proposal canvas approved).
      Still possible: the walk list as a tick-off checklist, a help
      button in the corner.
      Envoy's look (his screenshot, 17 Nov): light page, a left sidebar
      of sections with icons (Home, Schedule, Visitors, Workplace,
      Analytics...), a setup checklist card, a help card on the right,
      a red chat button in the corner -- "pyara sa khoobsurat sa". Study
      it and propose our front page in that style (light theme first,
      sidebar of our tabs, cards) before building.

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

Dashboard, best it can be (Shamroze, 18 Nov evening: "UI/UX behtar, fast,
order, jo missing hai poora karo"). One at a time, each checked in the
browser on a phone and in dark before it is pushed:
- [x] 18:30 Last out yesterday said "8:00 evening" where the cameras went
      dark (laptop asleep 19:56): now "not known · cameras off from ...".
- [x] 18:30 The ledger 6x faster (same figures to the paisa, 114 room-days
      compared); finished days kept on disk: Savings tab 30 s -> 2 s.
- [x] 23:55 The meter readings form (Energy tab): easier and nicer -- both
      meters side by side with the last reading, the units since then shown
      live as you type, a warning for a number lower than the last or an
      odd jump, solar and today's high optional, one big Save.
- [x] 01:00 Front page: a "Savings & peak" door beside AC timings and Desks,
      carrying this week's "could have been saved".
- [x] 01:15 Energy tab order: what somebody acts on first (today vs yesterday,
      the month's bill), the long tables after; check its load time now.
- [x] 02:00 Energy > Meters & bill takes ~13 s on a first open: profile
      show_meters (load_history, cooled_in_windows, person_hours) and make
      it a few seconds, same figures.
- [x] 02:05 "Look at the rooms" on a phone and in dark (not checked 19 Nov):
      fits; stills are off by design and it says how to turn them on.
- [x] 01:20 Every tab once on a phone and in dark: nothing wider than the
      screen, no text in the series colour, numbers right-aligned.

## Added 19 Nov 12:55 (Shamroze: "calibrate it yourself from the data")

- [ ] After this evening's switch-off, from frames/ac_keep -- only frames
      from 19 Nov 09:54 on count for the cameras moved this morning:
      Marketing (ch3 M1 and M2 by their displays, M3; ch13 the Kenwood and
      the row's nearest unit), Wellows W1 (ch16), AutoOS (ch10), Basement
      (ch23 Kenwood and the two louvres, ch24 and ch25 Haiers), DL (ch1),
      H First Floor Lobby (nvr1 ch22). Each: find the switch by eye, pick
      the box on the frames either side, a second camera in `also:`,
      `anchor_roi` where the unit's own change reaches round the box,
      `dark_max` for a louvre; then replay the block over every kept frame
      against the eye: a "running" in an off period must be zero. Restart
      the loop.
      20 Nov 00:50, done: Marketing M1 (ch3, white light, on 10:00 / off
      15:42) and the ch13 Kenwood (display, on 10:48 / off 22:01, `also:`,
      view check on its "2 years" badge -- the default region matched the
      pre-move wall at 0.57-0.79); Basement ch25 Haier (display, off 22:01,
      view check above the louvre). Left: Marketing M2 -- clean by its
      louvre's darkness (open 0.47-0.63, shut 0.76-0.98, line 0.70) but one
      day only, so it waits for 20 Nov's switch (calibrate_room refuses its
      contrast gap of 6.7; write the block by hand with `dark_max`); M3
      and the row; Wellows W1 (louvre changes too faintly, darkness
      overlaps); AutoOS (clear by day -- louvre open 13:00-20:55, shut
      11:45 -- unclear at night: a blue light and a red reflection stay on);
      ch24 Haier, DL, H First Floor Lobby: not looked at yet. Ch23: never
      until its mount holds. Tools: scratchpad spotline.py / darkline.py /
      timesheet.py / gridview.py / replay_unit.py / replay_also.py.
- [ ] Same for 141, from frames kept since 19 Nov 13:33 (the ten rooms set
      visible then): Reception Meeting Room (cd_nvr2 ch9/10), 141-D MR01
      (ch15) and MR02 (ch16) -- their louvres show; Rooms 6, 7, 21, 29,
      Room 32 Meeting Room, MR 01 and MR 02 (1st floor). Each: does its
      louvre or display change at the switch-off? Calibrate only a clean
      change; an end-on unit that never changes stays unread. Then the
      follow-up table at the top of docs/ac_camera_audit.md.
      Note (18:30): seven of them are kept at the sub stream -- cd_nvr2's
      at 640x360 (Reception MR, 141-D MR01, MR02), cd_nvr1's at 720x576
      (MR 01, MR 02, Room 21, Room 32 MR). If a louvre is too small to read
      there, set the room to `stream: main` -- and first rescale its
      `ignore:` boxes to 1920x1080 (Reception MR ch10, 141-D MR01 ch15,
      MR 01 ch9, Room 21 ch23), then verify_live it, by day.

Rules that hold all night: the 141 gym's camera is never opened 15:00-20:00;
no picture into git; no recorder settings; no retried logins (XVR 2 and 4
are IP conflicts, the DVR is on another network -- leave them).
