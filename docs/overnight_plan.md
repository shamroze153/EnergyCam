# Overnight plan — empty building

For a Claude Code session running **on the office laptop** (the one with the
cable), or anyone at that keyboard. Everything here runs from
`C:\hfm_energy_project` in the `hfm_energy` environment.

The building is empty, which makes tonight the one time when **every person
the detector finds is wrong by definition** — a chair, a coat, a poster, a
reflection. Nobody has to judge whether a box is real.

## 1. Start clean

```
pull.bat
conda activate hfm_energy
```

Close any running loop window, then start it again so it has the latest code
(the two-pass "empty" rule that stops Admin Room flipping):

```
run_forever.bat --evidence
```

Leave that window alone. `--evidence` saves a picture of anyone counted after
hours — tonight, that is every false person, collected automatically.

## 2. The false-person audit

```
python check_room.py --all --zip
```

Run it twice, at least 15 minutes apart. Then, for each camera:

- **A box in the same place in both runs** is a fixed object. Add it as an
  ignore zone under that room in `rooms.yaml`, using the exact lines
  check_room prints. A zone is tied to one spot, so a real person standing in
  front of it is still counted.
- **A box in only one run** may be a guard or a cleaner. Leave it.
- **Never** zone a doorway, corridor or walkway — real people pass there.
- **Never** raise `conf` for a whole room to get rid of one chair. It also
  hides the half-hidden real person in the far corner.

After the zones are in, restart the loop and run `python verify_live.py`.
Every room should be empty or MATCH; anything else is still a false person.

## 3. AC baseline

```
python tune_detect.py capture --rounds 1 --label night
```

One frame per camera with the units (mostly) off. Tomorrow at ~11:00, with
the units running:

```
python tune_detect.py capture --rounds 1 --label day
```

The pair is what each unit is calibrated from — **only** where the camera is
in colour in both. A camera that went infrared at night cannot be compared
with its daytime frame; those rooms need one technician walk-through with
`calibrate_room.py --live`, which now masks out people automatically.

## 4. Before every push

```
for %t in (test_ac_detect test_room_loop test_dashboard test_day_story test_integration test_alerts test_verify test_audit test_analysis test_meters) do python %t.py
```

All must say `all checks passed`. Commit with a message that says what was
changed and why. **Never commit** `.env`, `frames/`, `evidence/`,
`tune_frames/` or anything with a face in it — they are in `.gitignore` for
that reason.

## 5. Do not

- touch `.env` or any password
- change `DETECT_CONF` / `DETECT_SIZE` globally
- stop the loop for longer than a restart
- delete anything from the database
