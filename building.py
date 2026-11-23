"""The building as places and the ways between them (building.yaml).

Shamroze, 23 Nov 2026: "entry, reception, basement, ground floor, first
floor, cafe -- pura 3D bana sakte ho; employee jahan jaye, camera usko
follow kare." Two users:

  * the loop's follow mode (progress_follow.py): when an employee leaves the
    desk, the cameras of the places fewest steps from where they were are
    looked at first, again and again, instead of each camera once a pass;
  * the Progress tab (building_view.py): the floors one above another, where
    each employee is now and the way they went today.

yaml only, so the hosted dashboard can read it.
"""
import os
from collections import deque

import yaml

BUILDING = "building.yaml"
_cache = {"path": None, "mtime": None, "data": None}


def load(path=None):
    """building.yaml, read again only when it changes; {} if missing."""
    path = path or BUILDING
    try:
        m = os.path.getmtime(path)
    except OSError:
        return {}
    if _cache["path"] != path or _cache["mtime"] != m:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        data.setdefault("floors", [])
        data.setdefault("places", {})
        data.setdefault("links", [])
        _cache.update(path=path, mtime=m, data=data)
    return _cache["data"]


def floors(b):
    """Floor names, bottom to top."""
    return list(b.get("floors") or [])


def level(b, floor):
    """A floor's height: 0 for the lowest."""
    fl = floors(b)
    return fl.index(floor) if floor in fl else 0


def place(b, name):
    return (b.get("places") or {}).get(name)


def xyz(b, name):
    """Where a place is drawn: (x, y, floor level), or None."""
    p = place(b, name)
    if not p:
        return None
    x, y = (float(v) for v in (p.get("at") or (0, 0))[:2])
    return x, y, float(level(b, p.get("floor")))


def neighbours(b):
    """{place: set of places one step away} (links go both ways)."""
    out = {n: set() for n in (b.get("places") or {})}
    for link in b.get("links") or []:
        if len(link) < 2:
            continue
        a, z = link[0], link[1]
        out.setdefault(a, set()).add(z)
        out.setdefault(z, set()).add(a)
    return out


def steps_from(b, start):
    """{place: steps from `start`} for every place reachable."""
    near = neighbours(b)
    if start not in near:
        return {}
    seen = {start: 0}
    todo = deque([start])
    while todo:
        here = todo.popleft()
        for n in sorted(near.get(here, ())):
            if n not in seen:
                seen[n] = seen[here] + 1
                todo.append(n)
    return seen


def route(b, a, z):
    """The fewest-steps way from place a to place z, both ends included;
    [] when there is none (or either is unknown)."""
    near = neighbours(b)
    if a not in near or z not in near:
        return []
    back = {a: None}
    todo = deque([a])
    while todo:
        here = todo.popleft()
        if here == z:
            break
        for n in sorted(near.get(here, ())):
            if n not in back:
                back[n] = here
                todo.append(n)
    if z not in back:
        return []
    way = [z]
    while back[way[-1]] is not None:
        way.append(back[way[-1]])
    return way[::-1]


def cameras(rooms_path="rooms.yaml", recorders=None):
    """{(recorder, channel): room name} from rooms.yaml -- every camera of
    every room (of `recorders`, if given)."""
    try:
        with open(rooms_path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
    except OSError:
        return {}
    out = {}
    for r in cfg.get("rooms") or []:
        # a room is on one recorder (`recorder` + `channels`) or on several
        # (`cameras: [{recorder, channel}]`, H First Floor Lobby)
        keys = [(r.get("recorder"), ch) for ch in r.get("channels") or []]
        keys += [(c.get("recorder"), c.get("channel"))
                 for c in r.get("cameras") or [] if isinstance(c, dict)]
        for rec, ch in keys:
            if recorders and rec not in recorders:
                continue
            try:
                out[(rec, int(ch))] = r.get("name")
            except (TypeError, ValueError):
                continue
    return out


def campus_rooms(rooms_path="rooms.yaml", recorders=None):
    """The names of the rooms with a camera on `recorders`."""
    return sorted(set(cameras(rooms_path, recorders).values()))


def nearest_cameras(b, cams, start, skip=()):
    """Cameras to look at for somebody last seen at place `start`, nearest
    first: [(steps, (recorder, channel), place)]. Cameras of places not in
    the building, and those in `skip`, are left out."""
    steps = steps_from(b, start)
    out = [(steps[room], key, room) for key, room in cams.items()
           if room in steps and key not in skip]
    return sorted(out, key=lambda t: (t[0], t[2], t[1]))


def problems(b, rooms):
    """What is wrong with building.yaml against rooms.yaml's room names
    `rooms` (of the campus): unknown places, links to nowhere, floors no
    one has heard of, and rooms left off the map."""
    out = []
    places = b.get("places") or {}
    fl = set(floors(b))
    for name, p in places.items():
        if name not in rooms:
            out.append("place %r is not a room in rooms.yaml" % name)
        if (p or {}).get("floor") not in fl:
            out.append("place %r is on an unknown floor %r"
                       % (name, (p or {}).get("floor")))
    for link in b.get("links") or []:
        for end in link[:2]:
            if end not in places:
                out.append("link %r goes to %r, not a place" % (link, end))
    for name in rooms:
        if name not in places:
            out.append("room %r is not on the map" % name)
    return out
