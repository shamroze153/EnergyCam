"""The building in 3D for the Progress tab: the floors one above another,
the places on them and the ways between, each employee where they are now
and the way they went today (Shamroze, 23 Nov 2026: "pura 3D banao ...
kaun kahan ja raha hai").

Plotly only (the hosted dashboard has it). The map is building.yaml's
schematic, not a floor plan; the positions are progress_data.route()'s --
the desk from the seat notes, elsewhere a face clearly theirs or the body
network's guess ("possibly"), never more sure than that.
"""
import plotly.graph_objects as go

import building

# One colour per employee, by code, the validated categorical order
# (dataviz reference palette, slots 1-5): the same employee keeps the same
# colour whoever else is shown. Light and dark are each mode's own steps.
COLOURS = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
}
INK = {
    "light": {"t1": "#0b0b0b", "t2": "#52514e", "t3": "#898781",
              "floor": "#898781", "link": "rgba(11,11,11,.22)",
              "box": "rgba(11,11,11,.30)", "s2": "#f0efec"},
    "dark": {"t1": "#f0efec", "t2": "#c3c2b7", "t3": "#898781",
             "floor": "#c3c2b7", "link": "rgba(255,255,255,.22)",
             "box": "rgba(255,255,255,.30)", "s2": "#1f1f1d"},
}
STOREY = 3.0                 # drawn height of a floor
HOW = {"desk": "at the desk", "face": "seen by face",
       "seen": "seen (confirmed)", "possible": "possibly (not confirmed)"}
INSIDE = (2.0, 1.6, 10.2, 8.0)   # the building's outline on every floor


def colour(code, mode="dark", order=None):
    """An employee's colour: by their place in `order` (the codes in
    progress.yaml's order), else by the number in the code."""
    pal = COLOURS.get(mode, COLOURS["dark"])
    if order and code in order:
        return pal[order.index(code) % len(pal)]
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    return pal[(int(digits) - 1) % len(pal)] if digits else pal[0]


def _at(b, name):
    p = building.xyz(b, name)
    return None if p is None else (p[0], p[1], p[2] * STOREY)


def where_now(person):
    """(place, how) where an employee is now, or (None, why)."""
    live = person.get("live") or {}
    state = live.get("state")
    desk = person.get("desk_place") or ""
    if state == "desk":
        return desk, "desk"
    if state == "away":
        since = live.get("since")
        pts = [p for p in person.get("route") or []
               if p.get("how") != "desk"
               and (since is None or p.get("t") is None or p["t"] >= since)]
        if pts:
            return pts[-1]["place"], pts[-1]["how"]
        return None, "away, not seen on a camera"
    return None, live.get("label") or "not in"


def path_points(b, route):
    """The day's way through the building as drawn points: every stop, and
    between two stops the fewest-steps way along the links (so a walk from
    the basement to the cafe goes up the stairs, not through the floors)."""
    xs, ys, zs = [], [], []
    stops = [p for p in route or [] if building.place(b, p.get("place"))]
    for i, p in enumerate(stops):
        way = [p["place"]]
        if i:
            way = building.route(b, stops[i - 1]["place"], p["place"])[1:] \
                or [p["place"]]
        for name in way:
            q = _at(b, name)
            if q:
                xs.append(q[0])
                ys.append(q[1])
                zs.append(q[2])
    return xs, ys, zs


def _hm(t):
    try:
        return t.strftime("%H:%M")
    except AttributeError:
        return str(t or "")[11:16] or str(t or "")


def figure(b, people, mode="dark", height=640):
    """The 3D building with everybody on it."""
    ink = INK.get(mode, INK["dark"])
    fig = go.Figure()
    floors = building.floors(b)
    places = b.get("places") or {}
    x0, y0, x1, y1 = -1.4, -1.6, 13.0, 9.8
    for i, name in enumerate(floors):
        z = i * STOREY
        fig.add_trace(go.Mesh3d(
            x=[x0, x1, x1, x0], y=[y0, y0, y1, y1], z=[z] * 4,
            i=[0, 0], j=[1, 2], k=[2, 3], color=ink["floor"], opacity=0.07,
            hoverinfo="skip", showlegend=False))
        bx0, by0, bx1, by1 = INSIDE
        fig.add_trace(go.Scatter3d(
            x=[bx0, bx1, bx1, bx0, bx0], y=[by0, by0, by1, by1, by0],
            z=[z] * 5, mode="lines", line=dict(color=ink["box"], width=2),
            hoverinfo="skip", showlegend=False))
        # the floor's name at its near right corner, the one facing the eye
        fig.add_trace(go.Scatter3d(
            x=[x1], y=[y0], z=[z + 0.15], mode="text", text=[name],
            textposition="middle left",
            textfont=dict(color=ink["t2"], size=12), hoverinfo="skip",
            showlegend=False))
    # the ways between places
    lx, ly, lz = [], [], []
    for link in b.get("links") or []:
        a, z_ = _at(b, link[0]), _at(b, link[1])
        if a and z_:
            lx += [a[0], z_[0], None]
            ly += [a[1], z_[1], None]
            lz += [a[2], z_[2], None]
    fig.add_trace(go.Scatter3d(x=lx, y=ly, z=lz, mode="lines",
                               line=dict(color=ink["link"], width=2),
                               hoverinfo="skip", showlegend=False))
    # every place: a small dot, its name on hover; the names that matter
    # (where somebody is or was, the stairs, the desks) written on
    named = set()
    for p in people:
        named.add(p.get("desk_place"))
        named.update(q.get("place") for q in p.get("route") or [])
    named.update(n for n, v in places.items() if (v or {}).get("stairs"))
    named.update(("140-H Reception", "Prompt Cafe"))
    px, py, pz, ptext, phover = [], [], [], [], []
    for name, v in places.items():
        q = _at(b, name)
        if not q:
            continue
        px.append(q[0])
        py.append(q[1])
        pz.append(q[2])
        ptext.append(name if name in named else "")
        phover.append("%s<br>%s" % (name, (v or {}).get("floor", "")))
    fig.add_trace(go.Scatter3d(
        x=px, y=py, z=pz, mode="markers+text", text=ptext,
        textposition="top center", textfont=dict(color=ink["t3"], size=10),
        marker=dict(size=3, color=ink["t3"]), hovertext=phover,
        hoverinfo="text", showlegend=False))
    # each employee: today's way, then where they are now
    order = [p.get("code") for p in people]
    for i, p in enumerate(people):
        code = p.get("code", "?")
        col = colour(code, mode, order)
        xs, ys, zs = path_points(b, p.get("route"))
        if len(xs) > 1:
            fig.add_trace(go.Scatter3d(
                x=xs, y=ys, z=zs, mode="lines",
                line=dict(color=col, width=4), opacity=0.55,
                hoverinfo="skip", legendgroup=code, showlegend=False))
        stops = [q for q in p.get("route") or [] if _at(b, q.get("place"))]
        if stops:
            pts = [_at(b, q["place"]) for q in stops]
            fig.add_trace(go.Scatter3d(
                x=[t[0] for t in pts], y=[t[1] for t in pts],
                z=[t[2] for t in pts], mode="markers",
                marker=dict(size=4, color=col),
                hovertext=["%s &middot; %s%s &middot; %s<br>%s" % (
                    code, _hm(q.get("t")),
                    "&ndash;%s" % _hm(q["until"]) if q.get("until") else "",
                    q["place"], HOW.get(q.get("how"), q.get("how", "")))
                    for q in stops],
                hoverinfo="text", legendgroup=code, showlegend=False))
        place, how = where_now(p)
        q = _at(b, place) if place else None
        if q is None:
            continue
        # a small nudge each, so two people in one room are both seen
        dx, dy = ((i % 3) - 1) * 0.28, ((i // 3) - 0.5) * 0.28
        fig.add_trace(go.Scatter3d(
            x=[q[0] + dx], y=[q[1] + dy], z=[q[2] + 0.35],
            mode="markers+text", text=[code], textposition="top center",
            textfont=dict(color=ink["t1"], size=13),
            marker=dict(size=11, color=col,
                        symbol="circle" if how in ("desk", "face", "seen")
                        else "circle-open",
                        line=dict(color=ink["s2"], width=2)),
            name="%s &middot; %s" % (code, place),
            hovertext=["%s &middot; now: %s<br>%s" % (
                code, place, HOW.get(how, how))],
            hoverinfo="text", legendgroup=code, showlegend=True))
    axis = dict(visible=False, showbackground=False)
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=ink["t2"]),
        hoverlabel=dict(bgcolor=ink["s2"], font=dict(color=ink["t1"])),
        legend=dict(orientation="h", y=1.02, x=0, font=dict(color=ink["t2"])),
        scene=dict(xaxis=axis, yaxis=axis, zaxis=axis,
                   aspectmode="manual",
                   aspectratio=dict(x=2.0, y=1.4, z=1.25),
                   camera=dict(eye=dict(x=1.35, y=-1.75, z=0.95))))
    return fig


def way_lines(people):
    """Each employee's day in words, for under the picture."""
    out = []
    for p in people:
        bits = []
        for q in p.get("route") or []:
            if q.get("how") == "desk":
                bits.append("%s-%s desk" % (_hm(q.get("t")), _hm(q.get("until"))))
            else:
                bits.append("%s %s%s" % (
                    _hm(q.get("t")),
                    "possibly " if q.get("how") == "possible" else "",
                    q.get("place")))
        place, how = where_now(p)
        now = ("now: %s (%s)" % (place, HOW.get(how, how))) if place \
            else "now: %s" % how
        out.append((p.get("code", "?"), now, " -> ".join(bits) or
                    "no way recorded today"))
    return out
