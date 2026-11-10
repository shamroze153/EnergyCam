# Morning report — 11 Nov 2026

Worked from the two zips sent last night (check_room at 20:32, tune frames).
Cameras could not be reached from here; everything below comes from those
frames. Seven commits, all tests passing.

## 1. Occupancy — what the 20:32 check found

**The building was not empty at 20:32.** Room 18 had a full table, Marketing,
Wellows, Prompt Cafe, Cyber Security and Room 17 all had people at desks, and
a cleaner was mopping Marketing. So most of the 74 detections are real people
and were left alone. Each one was looked at by eye.

**Six fixed objects were counted as people. All six are now ignore zones:**

| Camera | What it was | Score |
|---|---|---|
| H Smoking Area nvr1 ch12 | tree trunk | 0.58 |
| Outside H nvr1 ch29 | the wall along the left edge | 0.47 |
| H Basement Parking nvr1 ch13 | stacked boxes and a dispenser | 0.41 |
| Gaming Area nvr4 ch8 | a bottle on the counter | 0.34 |
| Outside H nvr1 ch31 | a post | 0.31 |
| HR Room dvr2 ch2 | door frame beyond the glass | 0.25 |

Each zone was run through the loop's own filter on the same frame: the object
is dropped, and every real person on that camera is still counted.

**Four were left alone on purpose:**

| Camera | What it is | Why not zoned |
|---|---|---|
| Old Finance Room xvr3 ch7 | a chair (0.43) | a zone on a chair hides whoever sits in it |
| DL Department dvr2 ch1 | two chairs with jackets (0.55, 0.54) | same |
| Cafe Shoe Rack nvr4 ch5 | the bench (0.30) | people sit there |
| H Ground Floor Lobby xvr3 ch14 | a shadow (0.26) | it is a walkway |

These make a room read **occupied** when it is empty — a missed bit of waste.
The opposite mistake, reading a room **empty** with people in it, is what
sends an alert to switch the cooling off on somebody, so the safe side was
chosen. If these rooms keep showing a ghost at night, the fix is to move the
chair, not to blind the camera.

**Admin Room "empty while I'm sitting here"** — fixed yesterday evening. The
detector finds a seated person there in about half the frames (0.31–0.54,
then nothing). A room now needs two empty passes in a row before it is called
empty. Restart the loop for it to take effect.

## 2. Air conditioners

**Admin Room is verified.** Its display is lit on 5 Nov (contrast 36.47) and
dark tonight (0.95) — the same as the original calibration. It now has an
anchor: if the camera is nudged, it refuses rather than reporting a running
unit as off. Tonight at 20:32 it was **off**.

**Every other room: the display cannot be seen from its camera.** This is the
real reason calibration kept failing, not the technician or the timing.

| Room | Camera | What the camera sees |
|---|---|---|
| Marketing (5 units) | dvr2 ch13 | units from below; no display in view |
| Wellows | dvr2 ch15 | unit from underneath, top-left corner |
| Creative Room | dvr2 ch4 | slim unit at the top; vent only |
| HR Room | dvr2 ch2 | edge of a unit at the frame border |
| AutoOS, DL, IT Head, Wellows ch16 | dvr2 | no unit in frame |
| Cyber Security, Room 17, Room 18 | xvr3 | no unit in frame |
| Basement ×4, Basement Meeting, Mosque, Old Finance, Prompt Cafe ×4 | nvr4 / xvr3 | no wall unit in frame |
| Reception, Board Room, H First Floor Lobby | nvr1 | **not judged** — see below |

The last row was captured at 640×360 because of a bug (section 3). They need
one more capture at full resolution before anything can be said.

**What this means.** Reading a unit's state from its display only works where
a camera faces the display. Here that is one unit out of nineteen. The rest
still work for occupancy — the system knows when the room is empty and asks
somebody to check — it just cannot say whether the unit is running. To know
that for every unit, the options are a camera angled at each display, or a
power/current sensor on each unit's circuit, which reads on/off exactly with
no camera at all.

## 3. Bugs fixed tonight

- **Calibration on the wrong resolution.** tune_detect and calibrate_room
  chose the stream from the recorder only, ignoring a room's `stream: main`.
  Reception, Board Room and H First Floor Lobby would have been calibrated at
  640×360 while the loop reads 2560×1440 — and every reading refused, silently.
  One shared rule now (`wants_main`), and a test that fails if any file decides
  for itself.
- **Wrong camera captured.** A room watched from two recorders had its second
  camera fetched from the first: "H First Floor Lobby ch16" was a picture of
  Reception. Fixed.
- **Calibration boxes on people.** Marketing's six candidates were all people
  who had moved. Anything that changes where a person stands is now ignored.
- **`--inverted` crashed** on its first real use. Fixed.

## 4. This morning

1. `pull.bat`, then close the loop window and start `run_forever.bat --evidence`
   again — the two-pass rule and the zones only apply after a restart.
2. Around 11:00, with the units running:
   `python tune_detect.py capture --rounds 1 --label day`
   (now at the loop's own resolution). Send me the `tune_frames` folder as a
   zip — Reception, Board Room and H First Floor Lobby can then be judged.
3. `python verify_live.py` once — the six zones should show no ghosts on those
   cameras.
4. C and D campuses: bring the recorder IPs.

## 5. What could not be done

- No camera was reachable from here, so nothing was captured overnight and
  the only waste reading is Admin Room (off at 20:32).
- Nothing ran after the zips were finished: without new frames there was
  nothing for a scheduled check to look at.
