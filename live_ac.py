"""Air conditioning, right now: which units run, where, and what they draw.

Asked for on 12 Nov, standing in 141-C Cafe: "show that six ACs are running
in here at this moment, and how much energy that is". This is the panel that
answers it, at the top of every campus page, for whoever opens it -- the
office boy deciding which room to walk to, and the CEO asking what the
building is burning this minute.

What it can say is what the cameras can read, and it says so:

  * a unit seen running is counted, and its kilowatts are its rating (its
    tons where rooms.yaml has them, the site's typical unit where not);
  * a unit seen off is shown off;
  * a unit no camera can see is drawn as not visible, never as off.

Where the database does not yet hold how many units run (an older row, or
before sql/09_ac_units.sql), a room read "on" is shown as running with its
count unknown, and only one unit is put into the kilowatts: a floor, not a
guess.

No Streamlit and no database: frames in, HTML out, like the other views.
"""
import pandas as pd

import energy_view as ev
import overview as ov
from overview import esc

CSS = """<style>
.la-hero{display:flex;flex-wrap:wrap;gap:12px 28px;align-items:flex-end}
.la-hero .n{font-size:40px;font-weight:760;letter-spacing:-.02em;line-height:1;
font-variant-numeric:tabular-nums}
.la-hero .n small{font-size:15px;font-weight:600;color:var(--t3);margin-left:6px}
.la-hero .k{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;
color:var(--t3);margin-bottom:7px}
.la-sub{font-size:13.5px;color:var(--t2);margin-top:10px;line-height:1.5}
.la-list{margin-top:14px;border-top:1px solid var(--line)}
.la-row{display:grid;grid-template-columns:minmax(150px,1.3fr) minmax(120px,1fr)
minmax(130px,1fr) 92px;gap:12px;align-items:center;padding:10px 2px;
border-bottom:1px solid var(--line)}
.la-row .nm{display:block;min-width:0}
.la-row .nm b{display:block;font-weight:650;font-size:14px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.la-row .nm span{font-size:12px;color:var(--t3)}
.la-dots{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.la-dots i{width:13px;height:13px;border-radius:50%%;display:inline-block}
.la-dots i.on{background:%(on)s;box-shadow:0 0 0 3px %(on_ring)s}
.la-dots i.off{border:2px solid var(--t3)}
.la-dots i.unseen{border:2px dashed var(--line2)}
.la-dots i.maybe{background:%(on)s;opacity:.45}
.la-row .st{font-size:13px}
.la-row .st b{font-weight:650}
.la-row .kw{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.la-row .kw span{display:block;font-size:11.5px;color:var(--t3);font-weight:400}
.la-row.waste{background:var(--crit-bg);border-left:3px solid var(--crit);
padding-left:10px;border-radius:6px}
.la-row.waste .st b{color:var(--crit)}
.la-tag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;
color:#fff;background:var(--crit);border-radius:99px;padding:2px 9px;margin-left:6px}
.la-key{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--t3);
margin-top:12px}
.la-key i{width:10px;height:10px;border-radius:50%%;display:inline-block;
margin-right:5px;vertical-align:-1px}
@media (max-width:760px){.la-row{grid-template-columns:1fr 84px}
.la-row .kw{grid-column:2;grid-row:1}
.la-row .dt,.la-row .st{grid-column:1/-1}.la-hero .n{font-size:32px}}
</style>""".replace("\n", "")


def colours(theme):
    return {"on": "#2a9d63" if theme == "dark" else "#1f8a55",
            "on_ring": "rgba(42,157,99,.22)" if theme == "dark"
            else "rgba(31,138,85,.16)"}


def _int(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def rows(df, seen_units):
    """One dict per room with a unit some camera can read, in display order.

    seen_units: room -> how many of its units ac_units.yaml can read.
    """
    out = []
    for _, r in df.iterrows():
        if not r.get("has_unit"):
            continue
        seen = int(seen_units.get(r["room"], 0) or 0)
        if not seen:
            continue
        count = int(r.get("ac_count") or 1)
        seen = min(seen, count)
        state = r.get("ac_state")
        state = state if state in ("on", "off") else None
        running = _int(r.get("ac_units_on"))
        if running is not None:
            running = max(0, min(running, seen))
        kw_each = float(r.get("unit_kw") or 1.2)
        if state == "on":
            counted = running if running else 1
            exact = running is not None and running > 0
        else:
            counted, exact = 0, True
        status = r.get("status")
        people = _int(r.get("people"))
        tons = r.get("ac_tons")
        tons = float(tons) if tons is not None and pd.notna(tons) else None
        out.append({
            "room": r["room"], "zone": r.get("zone") or "",
            "count": count, "seen": seen, "state": state,
            "running": running, "counted": counted, "exact": exact,
            "kw": counted * kw_each, "kw_each": kw_each,
            "tons": tons,
            "status": status, "people": people,
            "alerts": bool(r.get("alerts", True)),
            "waste": (state == "on" and status == "empty"
                      and bool(r.get("alerts", True))),
        })
    out.sort(key=lambda x: (not x["waste"], x["state"] != "on",
                            x["state"] is None, -x["kw"], x["room"]))
    return out


def dots(r):
    """One mark per unit: running, off, not seen."""
    marks = []
    for i in range(r["count"]):
        if i >= r["seen"]:
            marks.append("unseen")
        elif r["state"] == "on" and r["running"] is None:
            marks.append("on" if i == 0 else "maybe")
        elif r["state"] == "on" and i < r["counted"]:
            marks.append("on")
        elif r["state"] is None and r["running"] is None:
            marks.append("unseen")
        else:
            marks.append("off")
    return "".join('<i class="%s"></i>' % m for m in marks)


def status_text(r):
    if r["state"] == "on":
        if r["running"] is not None:
            what = "<b>%d of %d running</b>" % (r["running"], r["count"])
        else:
            what = "<b>running</b> &middot; how many not recorded yet"
    elif r["state"] == "off":
        what = "all off" if r["seen"] == r["count"] else \
            "%d seen, all off" % r["seen"]
    else:
        if r["running"] == 0:
            what = "%d seen off &middot; %d not visible" % (
                r["seen"], r["count"] - r["seen"])
        elif r["seen"] < r["count"]:
            # Read off, but units no camera sees may be running: the loop
            # reports that as unknown, and so does this.
            what = "the one%s seen off, or not readable" % (
                "s" if r["seen"] > 1 else "")
        else:
            what = "not readable right now"
    who = ("nobody in" if r["status"] == "empty"
           else "%d %s in" % (r["people"], "person" if r["people"] == 1
                              else "people")
           if r["people"] else "")
    return what, who


def page(theme, items, rate, peak, total_units, base, typical_kw=1.2):
    """The panel. rate: Rs a unit now; peak: whether that is the peak rate."""
    c = colours(theme)
    h = [ev.css(theme), CSS % c, '<div class="ec">',
         '<div class="ec-h" style="margin-top:22px"><span class="t">Air '
         'conditioning, right now</span><span class="c">what the cameras can'
         ' see running</span></div><div class="ec-card">']
    if not items:
        h.append('<div class="la-sub" style="margin-top:0">No unit on this '
                 'campus can be read by a camera yet. Units are added one room '
                 'at a time, on site, by switching them on and off.</div>'
                 '</div></div>')
        return "".join(h)
    running = [r for r in items if r["state"] == "on"]
    units_on = sum(r["counted"] for r in running)
    floor = any(not r["exact"] for r in running)
    kw = sum(r["kw"] for r in running)
    waste = [r for r in items if r["waste"]]
    h.append('<div class="la-hero"><div><div class="k">Units running</div>'
             '<div class="n">%s%d<small>of %d readable</small></div></div>'
             '<div><div class="k">Drawing about</div><div class="n">%s%s'
             '<small>kW</small></div></div>'
             '<div><div class="k">Costing about</div><div class="n">Rs %s'
             '<small>an hour%s</small></div></div></div>'
             % ("&ge;" if floor else "", units_on,
                sum(r["seen"] for r in items),
                "&ge;" if floor else "", ("%.1f" % kw).rstrip("0").rstrip("."),
                format(int(round(kw * rate)), ","),
                ", peak rate" if peak else ""))
    if waste:
        h.append('<div class="la-sub"><b style="color:var(--crit)">%d room%s '
                 'with nobody in and the AC running</b> &mdash; at the top of '
                 'the list. Somebody nearby can switch %s off.</div>'
                 % (len(waste), "" if len(waste) == 1 else "s",
                    "it" if len(waste) == 1 else "them"))
    elif running:
        h.append('<div class="la-sub">Every room with a unit running has '
                 'people in it.</div>')
    h.append('<div class="la-list">')
    for r in items:
        what, who = status_text(r)
        size = ("%s ton" % ("%g" % float(r["tons"]))) if r["tons"] else \
            "%.1f kW" % r["kw_each"]
        h.append(
            '<div class="la-row%s"><a class="nm" target="_self" '
            'href="%s#roomdetail"><b>%s%s</b><span>%d unit%s &middot; %s'
            ' each</span></a><div class="la-dots dt">%s</div>'
            '<div class="st">%s%s</div><div class="kw">%s<span>%s</span>'
            '</div></div>'
            % (" waste" if r["waste"] else "",
               esc(ov.link(base, room=r["room"])), esc(ov.short(r["room"])),
               '<span class="la-tag">SWITCH OFF</span>' if r["waste"] else "",
               r["count"], "" if r["count"] == 1 else "s", size, dots(r),
               what, (" &middot; " + who) if who else "",
               ("%s%.1f kW" % ("&ge;" if not r["exact"] else "", r["kw"]))
               if r["state"] == "on" else "&mdash;",
               ("Rs %s/h" % format(int(round(r["kw"] * rate)), ","))
               if r["state"] == "on" else ""))
    h.append('</div><div class="la-key"><span><i style="background:%s"></i>'
             'running</span><span><i style="border:2px solid var(--t3)"></i>'
             'off</span><span><i style="border:2px dashed var(--line2)"></i>'
             'no camera sees it</span></div>' % c["on"])
    h.append('<div class="en-note">The cameras can read %d of the %d units on '
             'this campus; the rest are not in any camera\'s view, so they are '
             'left out here rather than guessed. kW is each running unit\'s '
             'size (its tons where known, else a typical %.1f kW split); the '
             'rupees are that at Rs %.0f a unit.%s</div></div></div>'
             % (sum(r["seen"] for r in items), total_units, typical_kw, rate,
                " &ge; marks a room read as running whose count is not"
                " recorded yet; it is counted as one unit." if floor else ""))
    return "".join(h)
