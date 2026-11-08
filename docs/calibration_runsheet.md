# Calibration run-sheet

Everything that has to be decided has been decided. What is left is walking,
switching and pressing Enter.

## Before you start

```
python doctor.py
```

from anywhere with internet, before you leave. It checks the logins, the
database, the tables and what is already calibrated, and it needs no cable.
Then, once you are plugged in, `python doctor.py --cameras` tries all four
recorders and reports the frame size each gives.

Seven rooms on nvr1 and nvr4 were being read at 640×360, which is too small
to see a unit's display. They now ask for the main stream in rooms.yaml, so
`pull.bat` first and check the frame size in `check_room.py` output is
1920×1080 or 1280×720 before calibrating any of them. If one still comes
back 640×360, that recorder is not serving a main stream on that channel and
the room cannot be calibrated until it does.

```
C:\hfm_energy_project\run_rooms.bat
```

Let it finish one cycle, then stop it with Ctrl+C. That proves the cable, the
four recorders and the credentials are all working before you walk anywhere.
Then, in the Supabase SQL editor, run `sql/05_merge_lobby.sql` once -- it
carries the old lobby's history into the merged room.

## One command per room

```
python calibrate_room.py --live --room "Marketing" --channel 13
```

It asks you to switch the unit on, takes a frame, asks you to switch it off,
takes another, finds the display, measures both, and saves a picture with a
green box drawn on it. Open that picture. If the box is on the display, answer
y. If it is on something else, answer n -- the two frames are kept, so you can
try `--choice 2` or your own `--roi` without touching the unit again.

It refuses rather than writes when the two states are too close together, when
the frames were taken in different light, when they look swapped, or when the
channel is not one the loop visits. Each of those would otherwise produce a
confident number with nothing behind it.

**Switch the unit, not the wall socket.** A unit cut at the socket has a dark
display because it has no power, not because it is off, and the measurement
would then describe the socket rather than the thermostat.

**Stand out of the camera's way** between pressing Enter and the frame
arriving -- about two seconds.

## The order to walk it

### 1. Confirmed: a unit is in frame. Straight to calibration.

- [ ] **Marketing** — `--room "Marketing" --channel 13`  (dvr2, top right, above the green door)
- [ ] **Wellows** — `--room "Wellows" --channel 15`  (dvr2, top left, vent slats in frame)
- [ ] **H First Floor Lobby** — `--room "H First Floor Lobby" --channel 22`  (nvr1, above the seating area)
- [ ] **Admin Room** — `--room "Admin Room" --channel 9`  (dvr2, top left -- REDO: the existing box is unconfirmed)

Admin Room is on this list because its existing calibration is unconfirmed:
the box sits on the unit's body rather than the dark recess in a later frame.
Redoing it with `--live --replace` also writes the anchor that makes a nudged
camera refuse itself instead of reporting a running unit as off for ever.

### 2. Probable: look first, then calibrate if the display is really there.

- [ ] **140-H Reception** nvr1 ch11 — high on the right, cut off by the top of the frame -- may need the camera tilted down first
- [ ] **140-H Reception** nvr1 ch16 — tall white cabinet by the red wall -- a floor-standing unit, or a cupboard
- [ ] **Mosque** nvr4 ch6 — extreme left edge, partly out of frame

For these, look at the camera's picture before switching anything:

```
python check_room.py --room "140-H Reception"
```

### 3. Unknown: one look each, no calibration unless something is there.

- [ ] **Room 17** xvr3 ch3, 5, 8 — nothing seen in the upper part of any of the three
- [ ] **Cyber Security Room** xvr3 ch2 — nothing seen in the upper part
- [ ] **Prompt Cafe** nvr4 ch13, 14, 15, 20 — never examined -- the frames were full of people
- [ ] **Basement** nvr4 ch21, 23, 24, 25 — labelled hidden; check whether any camera sees a unit
- [ ] **Basement Meeting Room** nvr4 ch22 — labelled hidden; on the camera-adjustment list anyway
- [ ] **140-H Board Room** nvr1 ch24 — labelled hidden; on the camera-adjustment list anyway
- [ ] **Old Finance Room** xvr3 ch7 — labelled hidden; confirmed no unit in frame

If a room turns out to have no unit in any camera, set it to `ac: hidden` in
rooms.yaml. That is not a failure: it is the difference between an alert that
says "its unit is running, switch it off" and one that says "somebody walk
past and check". Both are useful; only one of them can be said truthfully.

## While you are there

- [ ] **Basement Meeting Room** (nvr4 ch22) and **140-H Board Room** (nvr1
      ch24) — both `ac: hidden`. If either camera can be tilted so the unit
      comes into frame, that converts a "go and look" into a measurement.
- [ ] **"First Floor Lobby"** (dvr2 ch7) is a narrow corridor between
      glass-walled offices, not a lobby. Decide what it is actually called.
- [ ] **Room 17** and **Cyber Security Room** — settle whether they have a
      unit at all.

## After every room

```
C:\hfm_energy_project\run_rooms.bat --evidence
```

Startup should report the number of calibrated rooms, and each one's badge on
the dashboard should read AC ON or AC OFF rather than a question mark.
`--evidence` keeps a picture of anyone counted outside working hours, which is
how the rooms that count people who are not there will finally be caught.

## What is still not done after tomorrow

- An always-on machine at 140-H. The loop stops when the laptop goes home, so
  the hours where the money is are still not being recorded. See
  `docs/always_on.md`.
- Alerts are built and tested but not switched on: they need SENDER_EMAIL,
  APP_PASSWORD and ALERT_TO in `.env`, and a day of watching what they would
  have sent before `--alerts` goes on for real.

