# What the cameras actually see

7 November 2026. Read from the whole-site scan taken at 13:15–13:17, one
frame from each of the 96 cameras, examined at full width in the upper two
fifths of each frame — which is where a split unit is mounted, and where a
downscaled contact sheet is useless.

This matters because the original `ac:` labels were set from a contact sheet
during the survey, at a size where a wall unit is a few pixels. Several of
them are wrong, and a room labelled `visible` that has no unit in any of its
frames cannot be calibrated at all: somebody would go and stand in it with
the remote and find nothing to measure.

## Units confirmed in frame — the calibration list

| Room | Camera | Where the unit is |
|---|---|---|
| Admin Room | dvr2 ch9 | top left, on the long wall. Already calibrated, **unconfirmed** — see `ac_units.yaml` |
| Marketing | dvr2 **ch13** | top right, above the green door. **Not ch3** — ch3 sees no unit |
| Wellows | dvr2 **ch15** | top left, vent slats clearly visible. **Not ch16** |
| H First Floor Lobby | nvr1 ch22 / xvr3 ch16 | above the seating area |

## Probably in frame — confirm before calibrating

| Room | Camera | Doubt |
|---|---|---|
| 140-H Reception | nvr1 ch11 | a white unit high on the right, cut off by the top of the frame. May need the camera tilted down before its display is usable |
| 140-H Reception | nvr1 ch16 | a tall white cabinet by the red wall — possibly a floor-standing unit, possibly a cupboard |
| Mosque | nvr4 ch6 | a white unit at the extreme left edge, partly out of frame |

## Labelled `visible`, but no unit in any of the room's frames

Changed to `hidden`. Both are honest; `hidden` is the one that matches the
pictures. The practical difference is the wording of an alert: `visible`
promises a unit the camera can see, `hidden` says somebody has to walk past
and look.

| Room | Cameras checked |
|---|---|
| DL Department | dvr2 ch1 |
| HR Room | dvr2 ch2 |
| Creative Room | dvr2 ch4 |
| AutoOS | dvr2 ch10, ch14 |
| IT Head Room | dvr2 ch11 |
| Room 18 | xvr3 ch11, ch13 |

Not changed, because only the upper part of each frame was examined and no
unit was seen there — worth one more look on site: **Room 17** (xvr3 ch3,
ch5, ch8) and **Cyber Security Room** (xvr3 ch2).

Correctly labelled `hidden` already, confirmed: Old Finance Room (xvr3 ch7),
140-H Board Room (nvr1 ch24).

## Cameras that look into somewhere else

The commonest fault on this site, and the reason a room reports people who
are not in it. The people are real; they are in the corridor, or the next
office, through a door or a pane of glass. A room stuck at one person is
never counted as empty, so it quietly stops being watched for waste.

Two are fixed with zones, measured against the frames:

- **Creative Room** dvr2 ch4 — the corridor through the glass door.
- **UPS Room** dvr2 ch5 — a desk in the next room, through the doorway.

Seen in the frames but **no zone written**, because nothing was actually
miscounted there on 7 November and a zone aimed at a guess can hide a real
person:

- **HR Room** dvr2 ch2 — a full office of desks and chairs through the glass
  partition on the right.
- **DL Department** dvr2 ch1 — an open doorway into another office.
- **AutoOS** dvr2 ch10 — glass walls on two sides.
- **Wellows** dvr2 ch15 — a glass partition into the next room.

Run the loop with `--evidence` and these will declare themselves: any one of
them that counts somebody at two in the morning leaves a picture of exactly
what it counted, and then the zone is measured rather than guessed.

## What a second pass over all 95 frames found

Measured rather than eyeballed, across every frame at once.

**Three dead cameras.** xvr3 channels 6, 9 and 12 come back black — brightness
0.4 out of 255 — and identical to each other. Nothing is connected. They were
already labelled "unused" and were still being fetched every cycle, six
seconds each for a black frame. Now `watch: false`, kept in the file with the
measurement so nobody re-adds them.

**Nothing else is dead, dark or blown out.** Every other camera gives the
detector something to work with. That is a better result than expected on 95
cameras.

**No two cameras show the same place**, beyond the three black ones. The
first-floor lobby was the only genuine duplicate on this site and it is
already merged, so there are no more merges to find.

**The resolution split is the real finding.**

| Recorder | Stream | What comes back |
|---|---|---|
| dvr2 | main | 1920×1080 ×13, 1280×720 ×2, 960×576 |
| nvr1 | sub | **640×360 ×31** |
| nvr4 | sub | **640×360 ×32** |
| xvr3 | main | 1920×1080 ×10, 1280×720 ×5, 960×576 |

14 of the 32 cameras on rooms that can raise a check were coming back under
1000px wide. That is enough to see somebody is in a corridor and nowhere near
enough to read an air conditioner's display: at 640×360 the display is a
handful of pixels and a threshold measured from it would be measuring noise.

Seven rooms on nvr1 and nvr4 now ask for the main stream by name — 140-H
Reception, 140-H Board Room, H First Floor Lobby, Mosque, Prompt Cafe,
Basement, Basement Meeting Room. The other fifty cameras stay on sub, because
a car park does not need the extra decoding. **Without this, none of those
seven could have been calibrated tomorrow.**

## Other things the pictures settled

- **Prompt Cafe is not broken.** 82 detections across its four cameras on a
  Saturday afternoon are customers. The cafe was open and full.
- **140-H Board Room**'s one detection at 0.28 is an empty orange-and-white
  chair. Fixed with `conf: 0.40` rather than a zone, because a chair moves.
- **UPS Room**'s 0.37 and **H First Floor Lobby**'s 0.47 are real people.
  Raising the confidence to clear the faint detections — the obvious move —
  would have lost both.
- **AutoOS** saw nobody at all. Its earlier count of one is not in this scan.
- **"First Floor Lobby"** (dvr2 ch7) is not a lobby. It is a narrow corridor
  between glass-walled offices, and the name should change. Left alone:
  whoever walked the building names the rooms.
- **Data Centre Operations** (dvr2 ch6) had two people visible in the frame
  and the detector found none. The infrared image is washed out almost to
  line art. It never alerts, so nothing turns on it, but it is the clearest
  example on site of a camera the detector cannot read.
