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

Rules that hold all night: the 141 gym's camera is never opened 15:00-20:00;
no picture into git; no recorder settings; no retried logins (XVR 2 and 4
are IP conflicts, the DVR is on another network -- leave them).
