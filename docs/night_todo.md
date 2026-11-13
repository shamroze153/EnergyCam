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
- [ ] Names for cd_nvr4:17 (corridor), :26 (outside lane, guard), :31
      (pantry/kitchen); :30 duplicates the cafe's cd_nvr1:14. Asked.

## Added 13 Nov evening (the seating sheet, Desks page)

- [x] 18:47 Room 17: the sheet has 24 of its 47 desks given, the cameras
      never saw more than 5 at once. Its three cameras see most desks and
      the chairs were empty: the count is real. xvr3 ch 8 is hazy.
- [ ] For Shamroze's morning (13 Nov, "send me a picture of which camera
      frames to fix, I will do it myself"): a contact sheet of the cameras
      to clean or turn, each with what is wrong -- local, sent with
      SendUserFile, never in git. So far: 140-H xvr3 ch 8 (Room 17) hazy.
      Add to it each round.
- [x] 19:25 Seat map for 13 Nov, numbers (`seat_map.py --no-pictures`,
      10-19): Room 18 33 seats used (sheet 43 desks), Marketing 26 (28),
      141 Room 32 19 (17), Room 17 6 (47). AutoOS and 141 Room 22 show
      people every pass but no spot held 15% of the day: their boxes
      wander more than a seat's radius. Local only (seats.txt).
- [ ] Seat map pictures for 13 Nov, after 22:00 when the rooms are empty
      (`python seat_map.py --day 2026-11-13 --hours 10-19`; it opens the
      cameras): look at AutoOS's and Room 22's -- are the dots spread
      over real desks, or is the camera seeing a passage? Local only.
- [ ] 140-H rooms on the sheet with no camera room yet: R4, R11, R12,
      R14, R15, 19A/19B (asked Shamroze).

Rules that hold all night: the 141 gym's camera is never opened 15:00-20:00;
no picture into git; no recorder settings; no retried logins (XVR 2 and 4
are IP conflicts, the DVR is on another network -- leave them).
