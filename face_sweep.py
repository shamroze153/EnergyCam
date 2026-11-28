"""Faces where people go, read at full size between the loop's batches.

Shamroze, 24 Nov 2026: where an employee goes when away from the desk --
the cafe, the commons, a smoke, the parking, prayer -- and "live se unki
picture le ke process karo". The pass reads those cameras (nvr1 and nvr4)
from the recorders' sub stream, 640x360: enough to count people, too small
for a face (on 24 Nov the named people's faces were found where a room is
read at full size -- the Basement, the reception -- and almost nowhere
else). So, between batches, a few of those cameras at a time are read from
the main stream (2560x1440 / 1920x1080) and handed to cctv_faces: a named
person seen off their seat is a sighting, the same as from the pass.

27 Nov night (Shamroze: every starred employee's whole day -- the cafes of
both campuses, the meeting rooms, prayer, the other campus): 141-C/D's
sub-stream recorders too (the 141-C cafe, its meeting rooms, the ablution
area, its lobbies), and the meeting rooms among the places looked at
first. A room the pass found empty is read again at full size only after
EMPTY_EVERY -- nobody's face is in it -- so the minutes go to the rooms
with people in them.

Everything goes through room_loop.fetch (the recorders' gates and every
room's private hours) and only in office hours; the 141 gym is never
chosen (it is no place people go, and its private hours stand). The
pass's zones and seats are in the pass's own pixels, so they are scaled to
the bigger picture (PASS_SIZE, which examine() fills).

    step(rooms, grab_main, look) -- from room_loop's pulse(), never raises.
"""
import csv
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime

# the recorders the pass reads at sub stream: 140-H's two and, from 27 Nov
# night, 141-C/D's four (cd_xvr1 and cd_xvr3 are read at main already)
CAMPUS = {"nvr1", "nvr4", "cd_nvr1", "cd_nvr2", "cd_nvr3", "cd_nvr4"}
PLACES = ("cafe", "meeting", "smoking", "prayer", "corridor", "outside")
# where people go, looked at twice as often
FIRST = ("cafe", "meeting", "smoking", "prayer")
EVERY = 60.0             # s between steps
PER_STEP = 3             # cameras a step
BUDGET = 15.0            # s: a slower step makes the next ones wait longer
HOURS = ("08:30", "21:30")
# A room the pass last counted empty is read at full size at most this
# often (s): it is passed over in the round until then.
EMPTY_EVERY = 20 * 60.0
NEVER = ("gym",)         # never chosen, whatever its kind (141's gym)
PASS_SIZE = {}           # (recorder, channel): (h, w) of the pass's frame
_state = {"at": 0.0, "i": 0, "slow": 1.0}
_read = {}               # (recorder, channel): when last read at full size


# 28 Nov (a holiday: Shamroze, "kal parso ki recording dekh kar kaam karo"):
# the full-size replays of the recordings (places_replay.py) say how often
# each camera gives a named face. On 26 Nov, 70 looks each: the Basement
# Meeting Room 69, the 140-H Entry Area 22, the Prompt Cafe 13-20 a camera
# -- and 34 of 97 cameras none at all. The round gave every camera the same
# minutes (the cafe/meeting kinds twice), so a third went on cameras that
# never name anybody. Where the replays have looked at a camera enough
# (YIELD_MIN_LOOKS), its sightings a look decide how often the round reads
# it: three times from YIELD_HIGH, twice from YIELD_SOME, else once; where
# they have not, its kind does, as before. The same cameras, the same
# seconds -- only their order and repeats change.
REPLAY = os.path.join("people", "sightings", "replay")
YIELD_DAYS = 7
YIELD_MIN_LOOKS = 30
YIELD_HIGH = 0.25
YIELD_SOME = 0.10
_yield = {"at": -1e18, "got": {}}


def yields(folder=REPLAY, now_s=None, every=3600.0):
    """{(recorder, channel): (sightings, looks)} over the last YIELD_DAYS
    days of full-size replays (places_replay's <day>.csv and
    <day>_done.csv), read again hourly; {} where there are none."""
    now_s = time.time() if now_s is None else now_s
    if now_s - _yield["at"] < every:
        return _yield["got"]
    _yield["at"] = now_s
    looks, hits = Counter(), Counter()
    try:
        days = sorted(f[:10] for f in os.listdir(folder)
                      if f.endswith("_done.csv"))[-YIELD_DAYS:]
        for d in days:
            with open(os.path.join(folder, d + "_done.csv"),
                      newline="") as fh:
                for r in csv.reader(fh):
                    if len(r) >= 2 and ":" in r[1]:
                        rec, ch = r[1].rsplit(":", 1)
                        looks[(rec, int(ch))] += 1
            path = os.path.join(folder, d + ".csv")
            if os.path.exists(path):
                with open(path, newline="") as fh:
                    for r in csv.DictReader(fh):
                        hits[(r["recorder"], int(r["channel"]))] += 1
    except (OSError, ValueError, KeyError):
        pass
    _yield["got"] = {k: (hits[k], n) for k, n in looks.items()}
    return _yield["got"]


def weight(key, kind, seen):
    """How many times a round reads the camera: by its replays' sightings
    a look where they have looked enough, else by its kind."""
    h, n = (seen or {}).get(key, (0, 0))
    if n >= YIELD_MIN_LOOKS:
        y = h / float(n)
        return 3 if y >= YIELD_HIGH else 2 if y >= YIELD_SOME else 1
    return 2 if kind in FIRST else 1


def cameras(rooms, is_main=None, seen=None):
    """[(room, key)] to read at full size: the rooms the pass reads at sub
    stream that are places people go, the cafe, meeting rooms, smoking and
    prayer twice in the round -- or, with `seen` (yields()), each camera
    as often as weight() says, the most giving first. is_main(room,
    recorder name): room_loop.wants_main, the one place that decides a
    stream."""
    import progress_data as pdx
    is_main = is_main or (lambda room, rec: getattr(room, "stream", None)
                          == "main")
    first, rest, kinds = [], [], {}
    for room in rooms:
        if any(w in str(room.name).lower() for w in NEVER):
            continue
        kind = pdx.place_of(room.name)
        if kind not in PLACES:
            continue
        for key in room.cameras:
            key = (key[0], int(key[1]))
            if key[0] not in CAMPUS or is_main(room, key[0]):
                continue
            (first if kind in FIRST else rest).append((room, key))
            kinds[key] = kind
    if not seen:
        return first + rest + first
    w = {key: weight(key, kinds[key], seen) for _, key in first + rest}
    order = sorted(first + rest, key=lambda rk: -w[rk[1]])
    return (order + [rk for rk in order if w[rk[1]] >= 2]
            + [rk for rk in order if w[rk[1]] >= 3])


def empty_lately(room, key, t):
    """True while the pass's last count of the room was nobody and the
    camera was read at full size less than EMPTY_EVERY ago."""
    return (getattr(room, "people", None) == 0
            and t - _read.get(key, -1e18) < EMPTY_EVERY)


def pick(cams, start, t, count=PER_STEP):
    """The next `count` cameras of the round from `start`, passing over
    rooms empty lately and a camera already picked: ([(room, key)], where
    the round goes on from)."""
    out, keys, j = [], set(), start
    for _ in range(len(cams)):
        if len(out) >= count:
            break
        room, key = cams[j % len(cams)]
        j += 1
        if key in keys or empty_lately(room, key, t):
            continue
        out.append((room, key))
        keys.add(key)
    return out, j % len(cams)


def step(rooms, is_main, grab_main, look, now=None, clock=time.time,
         muffle=None):
    """Read the next PER_STEP cameras at full size, every EVERY seconds;
    look(room, key, frame) hands each to cctv_faces. Returns how many were
    read. Never raises."""
    try:
        return _step(rooms, is_main, grab_main, look, now, clock, muffle)
    except Exception:                                       # noqa: BLE001
        return 0


def _step(rooms, is_main, grab_main, look, now, clock, muffle):
    from progress_track import PKT
    now = now or datetime.now(PKT)
    if not (HOURS[0] <= now.strftime("%H:%M") <= HOURS[1]):
        return 0
    t = clock()
    if t - _state["at"] < EVERY * _state["slow"]:
        return 0
    _state["at"] = t
    cams = cameras(rooms, is_main, seen=yields())
    if not cams:
        return 0
    batch, _state["i"] = pick(cams, _state["i"] % len(cams), t)
    if not batch:
        return 0
    for _, key in batch:
        _read[key] = t
    seen = 0
    with (muffle() if muffle else nullcontext()):
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            jobs = [(room, key, pool.submit(grab_main, room, key))
                    for room, key in batch]
            got = []
            for room, key, job in jobs:
                try:
                    got.append((room, key, job.result()))
                except Exception:                           # noqa: BLE001
                    got.append((room, key, None))
    for room, key, frame in got:
        if frame is not None:
            look(room, key, frame)
            seen += 1
    _state["slow"] = 2.0 if clock() - t > BUDGET else 1.0
    return seen


def scale_to(key, frame):
    """(sx, sy): the pass's pixels per pixel of this bigger frame, or None
    while the pass has not read the camera yet."""
    small = PASS_SIZE.get((key[0], int(key[1])))
    if not small or frame is None:
        return None
    return small[1] / float(frame.shape[1]), small[0] / float(frame.shape[0])
