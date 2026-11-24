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

Everything goes through room_loop.fetch (the recorders' gates and every
room's private hours) and only in office hours. The pass's zones and
seats are in the pass's own pixels, so they are scaled to the bigger
picture (PASS_SIZE, which examine() fills).

    step(rooms, grab_main, look) -- from room_loop's pulse(), never raises.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime

CAMPUS = {"nvr1", "nvr4"}            # the 140-H recorders read at sub stream
PLACES = ("cafe", "smoking", "prayer", "corridor", "outside")
FIRST = ("cafe", "smoking", "prayer")  # where people go, looked at twice as often
EVERY = 60.0             # s between steps
PER_STEP = 3             # cameras a step
BUDGET = 15.0            # s: a slower step makes the next ones wait longer
HOURS = ("08:30", "21:30")
PASS_SIZE = {}           # (recorder, channel): (h, w) of the pass's frame
_state = {"at": 0.0, "i": 0, "slow": 1.0}


def cameras(rooms, is_main=None):
    """[(room, key)] to read at full size: 140-H's rooms the pass reads at
    sub stream that are places people go, the cafe, smoking and prayer
    twice in the round. is_main(room, recorder name): room_loop.wants_main,
    the one place that decides a stream."""
    import progress_data as pdx
    is_main = is_main or (lambda room, rec: getattr(room, "stream", None)
                          == "main")
    first, rest = [], []
    for room in rooms:
        kind = pdx.place_of(room.name)
        if kind not in PLACES:
            continue
        for key in room.cameras:
            key = (key[0], int(key[1]))
            if key[0] not in CAMPUS or is_main(room, key[0]):
                continue
            (first if kind in FIRST else rest).append((room, key))
    return first + rest + first


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
    cams = cameras(rooms, is_main)
    if not cams:
        return 0
    i = _state["i"] % len(cams)
    batch = (cams + cams)[i:i + PER_STEP]
    _state["i"] = i + PER_STEP
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
