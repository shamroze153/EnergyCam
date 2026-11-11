"""One day, every room, as a timeline -- the picture the table was failing to be.

Each room is a track across the 24 hours. Occupied time is drawn on it in
one hue, darker for more people (four steps: 1, 2-3, 4-6, 7+). An early
visit -- the cleaner before the day -- is hatched rather than solid, so it
reads as "somebody passed through" and not as the day starting. Time the
loop was not running is a pale hatch, so a gap in the record never passes
for an empty room. The peak tariff is a shaded band behind every track,
because that is where the money is, and a thin line marks now.

Colours: a single sequential blue ramp, from the reference palette in the
dataviz guidance, its own steps for light and for dark. No status colour
is used for a series; text stays in text inks.
"""
import pandas as pd

import day_story as ds

RAMP = {   # people buckets -> blue steps (ordinal: nothing too close to the surface)
    "light": ["#86b6ef", "#3987e5", "#256abf", "#184f95"],
    "dark":  ["#1c5cab", "#2a78d6", "#6da7ec", "#b7d3f6"],
}
BUCKETS = [(1, 1, "1"), (2, 3, "2–3"), (4, 6, "4–6"), (7, 10 ** 6, "7+")]
INK = {
    "light": {"text": "#14181B", "muted": "#6B7378", "faint": "#9AA3A8",
              "grid": "#e1e0d9", "track": "#F0F1F2", "band": "rgba(250,178,25,.13)",
              "now": "#14181B", "hatch": "#c3c2b7"},
    "dark":  {"text": "#E6EAED", "muted": "#8A949A", "faint": "#5E6A70",
              "grid": "#2c2c2a", "track": "#1B2228", "band": "rgba(250,178,25,.10)",
              "now": "#E6EAED", "hatch": "#383835"},
}


def colour(people, mode):
    ramp = RAMP[mode]
    for i, (lo, hi, _) in enumerate(BUCKETS):
        if lo <= people <= hi:
            return ramp[i]
    return ramp[-1]


def pct(ts, start):
    return max(0.0, min(100.0, (ts - start).total_seconds() / 864.0))


def track(day, story, start, mode):
    """The coloured pieces of one room's track, as HTML."""
    ink = INK[mode]
    early = story.get("early")
    html = ""
    for status, people, a, b in day:
        left, width = pct(a, start), pct(b, start) - pct(a, start)
        if width <= 0:
            continue
        if status == "unknown":
            html += ('<span title="%s – %s: nobody watching" style="'
                     'position:absolute;left:%.3f%%;width:%.3f%%;top:3px;'
                     'bottom:3px;background:repeating-linear-gradient(135deg,'
                     '%s 0 2px,transparent 2px 6px);opacity:.7;"></span>'
                     % (ds.clock(a), ds.clock(b), left, width, ink["hatch"]))
            continue
        if status != "occupied":
            continue
        fill = colour(people, mode)
        is_early = early and a >= early["from"] and b <= early["to"]
        style = (("background:repeating-linear-gradient(45deg,%s 0 2px,"
                  "transparent 2px 5px);box-shadow:inset 0 0 0 1px %s;"
                  % (fill, fill)) if is_early else "background:%s;" % fill)
        html += ('<span title="%s – %s: %d %s%s" style="position:absolute;'
                 'left:%.3f%%;width:max(2px,%.3f%%);top:2px;bottom:2px;'
                 'border-radius:2px;%s"></span>'
                 % (ds.clock(a), ds.clock(b), people,
                    "person" if people == 1 else "people",
                    " (early visit)" if is_early else "",
                    left, width, style))
    return html


def summary(story, left):
    """The few words to the right of a track."""
    if story["first_in"] is None:
        return "nobody"
    bits = []
    if story["carried"]:
        bits.append("from last night")
    elif story["starts"] is None:
        bits.append("brief visits only")
    else:
        bits.append(ds.clock(story["starts"]))
    if story["last_out"] is not None and left:
        bits[-1] += " → " + ds.clock(story["last_out"])
    elif story["first_in"] is not None:
        bits[-1] += " → still in"
    if story["peak"]:
        bits.append("peak %d" % story["peak"])
    return " · ".join(bits)


def render(rows, start, now, peak, mode="light"):
    """rows: [(name, day, story, left)] already sorted. Returns HTML."""
    ink = INK[mode]
    end = start + pd.Timedelta(days=1)
    grid = "".join(
        '<span style="position:absolute;left:%.3f%%;top:0;bottom:0;'
        'border-left:1px solid %s;"></span>' % (h / 24.0 * 100, ink["grid"])
        for h in range(3, 24, 3))
    band = ('<span style="position:absolute;left:%.3f%%;width:%.3f%%;top:0;'
            'bottom:0;background:%s;"></span>'
            % (peak[0] / 24.0 * 100, (peak[1] - peak[0]) / 24.0 * 100,
               ink["band"]))
    now_line = ""
    if start <= now < end:
        now_line = ('<span title="now" style="position:absolute;left:%.3f%%;'
                    'top:-4px;bottom:-4px;border-left:1.5px solid %s;"></span>'
                    % (pct(now, start), ink["now"]))
    labels = [(0, "12 night"), (3, "3"), (6, "6 morning"), (9, "9"),
              (12, "noon"), (15, "3"), (18, "6 evening"), (21, "9")]
    axis = "".join(
        '<span style="position:absolute;left:%.3f%%;transform:translateX(%s);'
        'font-size:.66rem;color:%s;white-space:nowrap;">%s</span>'
        % (h / 24.0 * 100, "0" if h == 0 else "-50%", ink["faint"], t)
        for h, t in labels)
    band_label = ('<span style="position:absolute;left:%.3f%%;width:%.3f%%;'
                  'text-align:center;font-size:.62rem;color:%s;">peak tariff'
                  '</span>' % (peak[0] / 24.0 * 100,
                               (peak[1] - peak[0]) / 24.0 * 100, ink["muted"]))
    head = ('<div style="display:flex;gap:12px;align-items:end;margin-bottom:4px;">'
            '<div style="flex:0 0 170px;"></div><div style="flex:1 1 auto;'
            'position:relative;height:30px;min-width:360px;">'
            '<div style="position:absolute;top:0;left:0;right:0;height:14px;">%s'
            '</div><div style="position:absolute;bottom:0;left:0;right:0;'
            'height:14px;">%s</div></div><div style="flex:0 0 280px;"></div>'
            '</div>' % (band_label, axis))
    body = ""
    for name, day, story, left in rows:
        body += (
            '<div style="display:flex;gap:12px;align-items:center;'
            'margin:0 0 6px;">'
            '<div style="flex:0 0 170px;font-size:.8rem;color:%s;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">%s</div>'
            '<div style="flex:1 1 auto;position:relative;height:22px;'
            'min-width:360px;background:%s;border-radius:4px;">%s%s%s%s</div>'
            '<div style="flex:0 0 280px;font-size:.74rem;color:%s;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">%s</div>'
            '</div>' % (ink["text"], name, ink["track"], band, grid,
                        track(day, story, start, mode), now_line,
                        ink["muted"], summary(story, left)))
    swatch = lambda style: ('<span style="display:inline-block;width:14px;'
                            'height:10px;border-radius:2px;vertical-align:-1px;'
                            'margin-right:5px;%s"></span>' % style)
    legend = ('<div style="display:flex;flex-wrap:wrap;gap:16px;font-size:.72rem;'
              'color:%s;margin:2px 0 14px 182px;">' % ink["muted"])
    legend += "".join("<span>%s%s</span>" % (
        swatch("background:%s;" % RAMP[mode][i]),
        "%s %s" % (lab, "person" if lab == "1" else "people"))
        for i, (_, _, lab) in enumerate(BUCKETS))
    legend += "<span>%searly visit</span>" % swatch(
        "background:repeating-linear-gradient(45deg,%s 0 2px,transparent 2px 5px);"
        "box-shadow:inset 0 0 0 1px %s;" % (RAMP[mode][1], RAMP[mode][1]))
    legend += "<span>%snobody watching</span>" % swatch(
        "background:repeating-linear-gradient(135deg,%s 0 2px,transparent 2px 6px);"
        % ink["hatch"])
    legend += "<span>%speak tariff</span>" % swatch(
        "background:%s;box-shadow:inset 0 0 0 1px %s;" % (ink["band"], ink["grid"]))
    legend += "</div>"
    return ('<div style="overflow-x:auto;">%s%s%s</div>'
            % (legend, head, body))
