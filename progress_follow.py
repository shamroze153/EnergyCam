"""Following the five Progress employees from camera to camera.

Shamroze, 23 Nov 2026: "ek employee ko point out karo; jab woh move kare
to doosra camera foran on ho, usko dekhe ... camera alert ho jaye."

The cameras cannot be moved, and the recorders' settings are never
touched (CLAUDE.md). What can change is *when* a camera is looked at. The
loop looks at every camera once a pass, about every four and a half
minutes; between its batches (room_loop's on_batch, every 20 s or so) this
looks again at a few cameras that matter now:

  * each employee's desk camera, every DESK_EVERY seconds -- so a desk left
    empty is known within a minute or two, not a pass later;
  * once an employee has left the desk (two looks in a row without them),
    the cameras of the places nearest to where they were (building.yaml,
    by steps along its links; the cafe, smoking passage, meeting rooms and
    the mosque a little before the rest), FOLLOW_CAMS at a time, every
    FOLLOW_EVERY seconds, for FOLLOW_FOR after they left or were last seen
    -- and when one of them shows the employee, the looking moves round
    that place instead.

Every look goes through progress_track.observe, exactly as a pass's does:
the same desk rows, the same sightings (a face clearly theirs counts, the
body's best guess stays "possible" until somebody confirms it), the same
pictures, on this laptop only. Nothing here decides who anybody is.

What it costs: one look is a handful of frames grabbed through the
recorders' own gates and counted with the loop's model. A step that takes
longer than BUDGET seconds makes the next ones wait twice as long, so the
pass itself (the rooms and the ACs) is never starved.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime

import building
import progress_data as pdx
import progress_track as pt

DESK_EVERY = 60.0        # s between looks at the desk cameras
FOLLOW_EVERY = 30.0      # s between looks round somebody who has left
FOLLOW_CAMS = 4          # cameras a look round somebody
FOLLOW_FOR = 15 * 60.0   # s after leaving, or after the last sighting
MISSES = 2               # looks in a row without them = they have left
HOURS = ("07:30", "22:00")
BUDGET = 12.0            # s: a step slower than this slows the next ones
DESTINATIONS = ("cafe", "smoking", "meeting", "prayer")

_state = {}              # code -> what is known of them now
_clock = {"desk": 0.0, "follow": 0.0, "slow": 1.0}
_cams = {"stamp": None, "cams": {}}


def reset():
    """Forget everything (tests, and a new day)."""
    _state.clear()
    _clock.update(desk=0.0, follow=0.0, slow=1.0)


def _t(at):
    return at.timestamp() if hasattr(at, "timestamp") else float(at)


def _say(text):
    print(">> follow: %s" % text)


def on_desk(code, present, at, room, key):
    """A look at an employee's desk (a pass's or this module's)."""
    t = _t(at)
    s = _state.setdefault(code, {"present": None, "left": None,
                                 "around": None, "until": 0.0,
                                 "looked": {}, "misses": 0,
                                 "first_miss": None, "desk": room,
                                 "key": tuple(key)})
    s["desk"], s["key"] = room, tuple(key)
    if present:
        if s["left"] is not None:
            _say("%s back at the desk (%s)" % (code, _hm(t)))
        s.update(present=True, left=None, until=0.0, looked={}, misses=0,
                 first_miss=None, around=None)
        return
    if s["present"] is not True:
        s["present"] = False if s["present"] is None else s["present"]
        return
    s["misses"] += 1
    if s["first_miss"] is None:
        s["first_miss"] = t
    if s["misses"] >= MISSES:
        s.update(present=False, left=s["first_miss"], around=room,
                 until=t + FOLLOW_FOR, looked={})
        _say("%s left the desk (%s) at %s -- looking round it"
             % (code, room, _hm(s["left"])))


def on_seen(code, room, at, state, score):
    """A sighting of an employee away from the desk: look round there."""
    s = _state.get(code)
    if not s or s.get("left") is None:
        return
    t = _t(at)
    if s.get("around") != room:
        _say("%s %s in %s at %s (%.2f)"
             % (code, "seen by face" if state == "face" else "possibly",
                room, _hm(t), score))
    s.update(around=room, until=t + FOLLOW_FOR, looked={})


def _hm(t):
    return datetime.fromtimestamp(t, pt.PKT).strftime("%H:%M")


def following(t):
    """Codes being followed at time t."""
    return [c for c, s in _state.items()
            if s.get("left") is not None and t < s.get("until", 0.0)]


def campus_cameras():
    """{(recorder, channel): room} of the Progress campus, from rooms.yaml
    (read again when it changes)."""
    import os
    try:
        stamp = os.path.getmtime("rooms.yaml")
    except OSError:
        stamp = None
    if _cams["stamp"] != stamp or not _cams["cams"]:
        _cams.update(stamp=stamp, cams=building.cameras(
            recorders=pt.CAMPUS_RECORDERS))
    return _cams["cams"]


# Presence only (the Basement, 25 Nov: "itna zyada follow karne ki zaroorat
# nahi"): somebody who left such a desk is looked for only where it counts
# for them -- their own room, the cafe, the smoking area.
NARROW_PLACES = ("cafe", "smoking")


def plan(t, b, cams, available, count=FOLLOW_CAMS, narrow=()):
    """The cameras to look at now round everybody being followed:
    [(key, [codes])], best first. Nearest places first, less-looked-at
    before looked-at, destinations a little before corridors; never an
    employee's own desk camera (the desk looks see that). Codes in
    `narrow` (presence only) only in their own room, the cafe and the
    smoking area."""
    desks = {s.get("key") for s in _state.values()}
    want = {}
    for code in following(t):
        s = _state[code]
        for steps, key, room in building.nearest_cameras(
                b, cams, s.get("around") or s.get("desk"), skip=desks):
            if key not in available:
                continue
            if code in narrow and room != s.get("desk") and \
                    pdx.place_of(room) not in NARROW_PLACES:
                continue
            score = steps + 2 * s["looked"].get(key, 0)
            if pdx.place_of(room) in DESTINATIONS:
                score -= 2
            best = want.get(key)
            if best is None or score < best[0]:
                want[key] = (score, [code])
            elif score == best[0]:
                best[1].append(code)
    chosen = sorted(want.items(), key=lambda kv: (kv[1][0], kv[0]))[:count]
    for key, (_, codes) in chosen:
        for code in codes:
            looked = _state[code]["looked"]
            looked[key] = looked.get(key, 0) + 1
    return [(key, codes) for key, (_, codes) in chosen]


def step(rooms, recorders, grab, look, now=None, clock=time.time,
         muffle=None):
    """One step between the loop's batches. grab(room, key) -> frame or
    None; look(room, key, frame) counts it and hands it to progress_track.
    Returns how many cameras were looked at. Never raises."""
    try:
        return _step(rooms, grab, look, now, clock, muffle)
    except Exception as e:                                  # noqa: BLE001
        _say("a step failed (%s)" % e)
        return 0


def _step(rooms, grab, look, now, clock, muffle):
    people = pt._people()
    if not people:
        return 0
    now = now or datetime.now(pt.PKT)
    if not (HOURS[0] <= now.strftime("%H:%M") <= HOURS[1]):
        return 0
    t = clock()
    by_key = {}
    for room in rooms:
        for key in room.cameras:
            by_key.setdefault(tuple(key), room)
    looks = []
    if t - _clock["desk"] >= DESK_EVERY * _clock["slow"]:
        for p in people:
            key = (p["recorder"], int(p["channel"]))
            if key in by_key and key not in looks:
                looks.append(key)
        _clock["desk"] = t
    if following(now.timestamp()) and \
            t - _clock["follow"] >= FOLLOW_EVERY * _clock["slow"]:
        b = building.load()
        if b:
            narrow = {p.get("code") for p in people if pdx.presence_only(p)}
            for key, _ in plan(now.timestamp(), b, campus_cameras(),
                               set(by_key), narrow=narrow):
                if key not in looks:
                    looks.append(key)
        _clock["follow"] = t
    if not looks:
        return 0
    frames = {}
    with (muffle() if muffle else nullcontext()):
        with ThreadPoolExecutor(max_workers=min(4, len(looks))) as pool:
            jobs = {key: pool.submit(grab, by_key[key], key) for key in looks}
            for key, job in jobs.items():
                try:
                    frames[key] = job.result()
                except Exception:                           # noqa: BLE001
                    frames[key] = None
    seen = 0
    for key in looks:
        if frames.get(key) is not None:
            look(by_key[key], key, frames[key])
            seen += 1
    took = clock() - t
    _clock["slow"] = 2.0 if took > BUDGET else 1.0
    return seen


# progress_track tells this module about every desk look and sighting.
pt.ON_DESK.append(on_desk)
pt.ON_SEEN.append(on_seen)
