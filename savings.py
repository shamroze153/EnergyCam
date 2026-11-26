"""The savings scoreboard, and what the peak hours cost room by room.

Shamroze, 18 Nov: "the savings scoreboard, and a weekly report to my email
-- a nice one" and "the peak hours' cost in a tab of its own, every room's,
so it shows this much and this much".

Two honest halves, and the page keeps them apart:

  The meters    units a day now against the bills: the last month billed,
                and the same month a year before (the same weather). They
                fall with the weather and the solar panels as well as with
                anything EnergyCam does, and the page says so.
  The cameras   what was spent cooling rooms nobody was in, and running more
                units than the people in needed -- this week against the
                week before, a usual day of each. That part is EnergyCam's.

Only days the cameras watched nearly whole count towards "a usual day"
(energy_rooms.WHOLE_DAY_H): a night the laptop slept is not a good night.
No Streamlit and no database: ledgers in, figures and HTML out.
"""
import pandas as pd

import energy_rooms as er
import energy_view as ev
import overview as ov
from overview import esc

LOCAL = "Asia/Karachi"


def save_rs(t):
    """Rupees that could have been saved: cooling with nobody in, and more
    units than the people in needed."""
    return t.get("waste_rs", 0.0) + t.get("over_rs", 0.0)


def whole(day):
    """A (date, ledger, so_far) the cameras watched nearly all of."""
    return (not day[2]) and bool(day[1]) and \
        er.totals(day[1]).get("watched_h", 0.0) >= er.WHOLE_DAY_H


def peak_whole(day, window):
    """A finished day whose peak hours the cameras watched (all but a
    quarter of an hour). 17 Nov was watched twenty hours, a whole day, but
    the laptop slept at 19:56: an hour and a half of its four peak hours."""
    if day[2] or not day[1]:
        return False
    seen = er.totals(day[1]).get("watched_peak_h")
    if seen is None:                       # an older ledger: the whole day
        return whole(day)
    return seen >= (window[1] - window[0]) - 0.25


def weeks(days):
    """The last seven finished days and the seven before them."""
    done = [d for d in days if not d[2]]
    return done[-7:], done[-14:-7]


def per_day(days, key, ok=whole, only=None):
    """A usual day's figure over the days among `days` that pass `ok` (the
    whole ones), or None. `key` is a totals() key or a function of them;
    `only`, a set of rooms to count (None: every room)."""
    full = [er.totals([r for r in d[1] if only is None or r["room"] in only])
            for d in days if ok(d)]
    if not full:
        return None
    get = key if callable(key) else (lambda t: t.get(key, 0.0))
    return sum(get(t) for t in full) / len(full)


def seen_rooms(days):
    """Rooms with any AC cost on any of `days`: the rooms the cameras were
    watching then. Before 11 Nov fourteen rooms were not in rooms.yaml at
    all, and a week holding none of them is not a cheaper week."""
    return {r["room"] for d in days for r in d[1] or [] if r.get("rs", 0) > 0}


# A week before with fewer days than this to go on gives no change at all.
LEAST_DAYS = 3


def compare(this, before, key, ok=whole):
    """This week's usual day against the week before's. The change is
    worked out on the rooms both weeks watched, so a room added since is
    not "more"."""
    a, b = per_day(this, key, ok), per_day(before, key, ok)
    n_before = sum(1 for d in before if ok(d))
    change = None
    if a is not None and b and n_before >= LEAST_DAYS:
        both = seen_rooms(this) & seen_rooms(before)
        a_c, b_c = per_day(this, key, ok, both), per_day(before, key, ok, both)
        if b_c:
            change = 100.0 * (a_c / b_c - 1)
    return {"now": a, "before": b, "change": change,
            "days": sum(1 for d in this if ok(d)), "days_before": n_before}


def bill_baselines(bills, codes, month):
    """The latest month billed on every meter in `codes`, and `month` a year
    earlier, each as units a day: [{label, kind, per_day, units, rs}]."""
    if bills is None or not len(bills) or not codes:
        return []
    b = bills[bills["meter"].isin(list(codes))].copy()
    if b.empty:
        return []
    b["end"] = pd.to_datetime(b["period_end"])
    b["start"] = pd.to_datetime(b["period_start"])

    def one(period, kind):
        m = b[b["end"].dt.to_period("M") == period]
        if m["meter"].nunique() < len(set(codes)):
            return None              # a month is only whole with every meter
        days = int(((m["end"] - m["start"]).dt.days + 1).max())
        units = float(m["units"].astype(float).sum())
        if days < 20 or units <= 0:
            return None
        return {"label": period.strftime("%b %Y"), "kind": kind,
                "per_day": units / days, "units": units,
                "rs": float(m["amount_rs"].astype(float).sum())}

    out = []
    latest = b["end"].max().to_period("M")
    got = one(latest, "the last bill")
    if got:
        out.append(got)
    year_ago = month - 12
    if year_ago != latest:
        got = one(year_ago, "a year ago, the same weather")
        if got:
            out.append(got)
    return out


def scoreboard(days, est=None, bills=None, window=(18.5, 22.5)):
    """Everything the scoreboard says, from up to fourteen days of
    [(date, ledger, so_far)] (oldest first) and ev.month_estimate()."""
    this, before = weeks(days)

    def at_peak(d):
        return peak_whole(d, window)

    out = {"this": this, "before": before,
           "save": compare(this, before, save_rs),
           "waste": compare(this, before, "waste_rs"),
           "over": compare(this, before, "over_rs"),
           "peak": compare(this, before, "peak_rs", at_peak),
           "peak_waste": compare(this, before, "peak_waste_rs", at_peak),
           "rs": compare(this, before, "rs"),
           "kwh": compare(this, before, "kwh"),
           "meters": None}
    if est:
        month = pd.Timestamp(est["to"]).tz_convert(LOCAL).tz_localize(None) \
            .to_period("M")
        base = bill_baselines(bills, list(est["meters"]), month)
        for item in base:
            item["change"] = 100.0 * (est["per_day"] / item["per_day"] - 1)
        out["meters"] = {"now": est["per_day"], "bills": base, "est": est}
    return out


def week_text(days):
    """"Wed 11 – Tue 17 Nov" for a run of days."""
    if not days:
        return ""
    a, b = pd.Timestamp(days[0][0]), pd.Timestamp(days[-1][0])
    if a.month == b.month:
        return "%s – %s" % (a.strftime("%a %d").replace(" 0", " "),
                            b.strftime("%a %d %b").replace(" 0", " "))
    return "%s – %s" % (a.strftime("%a %d %b").replace(" 0", " "),
                        b.strftime("%a %d %b").replace(" 0", " "))


def rooms_over(days, key):
    """Each room's figure summed over `days`, biggest first:
    [(room, total, row)] -- row is the room's latest ledger row."""
    keep = {}
    for _, ledger, _ in days:
        for r in ledger or []:
            k = keep.setdefault(r["room"], [0.0, r])
            k[0] += key(r) if callable(key) else r.get(key, 0.0)
            k[1] = r
    out = [(n, v[0], v[1]) for n, v in keep.items()]
    out.sort(key=lambda x: (-x[1], x[0]))
    return out


def clock(h):
    """18.5 -> "6:30 pm"."""
    hh, mm = int(h), int(round((h - int(h)) * 60))
    return "%d%s %s" % (hh % 12 or 12, (":%02d" % mm) if mm else "",
                        "am" if hh < 12 else "pm")


# ===================================================================== page

CSS = """<style>
.sv-chip{display:inline-block;font-size:12px;font-weight:650;padding:2px 9px;
border-radius:99px;margin:6px 6px 0 0;border:1px solid var(--line2);
white-space:nowrap}
.sv-chip.good{color:var(--good);border-color:var(--good)}
.sv-chip.bad{color:var(--crit);border-color:var(--crit)}
.sv-hero{display:flex;flex-wrap:wrap;gap:18px 34px;align-items:flex-end;
padding:18px 20px}
.sv-hero .lbl{font-size:11.5px;letter-spacing:.13em;text-transform:uppercase;
color:var(--t3);margin-bottom:6px}
.sv-hero .big{font-size:44px;font-weight:760;letter-spacing:-.02em;line-height:1;
font-variant-numeric:tabular-nums}
.sv-hero .sub{font-size:13.5px;color:var(--t2);margin-top:8px;line-height:1.5}
.sv-tbl{width:100%;border-collapse:collapse;font-size:13px;color:var(--t1);
font-variant-numeric:tabular-nums}
.sv-tbl th{font-size:11.5px;color:var(--t2);font-weight:600;padding:6px 8px;
text-align:right;white-space:nowrap}
.sv-tbl th:first-child,.sv-tbl td:first-child{text-align:left;padding-left:0}
.sv-tbl td{padding:7px 8px;text-align:right;border-top:1px solid var(--line);
white-space:nowrap}
.sv-tbl td.nm{white-space:normal;min-width:120px;font-weight:600;position:sticky;
left:0;background:var(--s1)}
.sv-tbl td.nm span{display:block;font-size:11px;color:var(--t3);font-weight:400}
.sv-bar{height:9px;border-radius:99px;background:var(--meter);overflow:hidden;
display:flex;min-width:90px}
.sv-bar i{display:block;height:100%}
@media (max-width:760px){.sv-tbl .wide{display:none}}
</style>""".replace("\n", "")


def chip(change, word_less="less", word_more="more", good_when_down=True):
    """"−12% less than the week before", green when it went the right way."""
    if change is None:
        return ""
    down = change < 0
    tone = "good" if down == good_when_down else "bad"
    if abs(change) < 0.5:
        return '<span class="sv-chip">about the same</span>'
    return '<span class="sv-chip %s">%s %.0f%% %s</span>' % (
        tone, "▼" if down else "▲", abs(change),
        word_less if down else word_more)


def _rs(v):
    return "—" if v is None else "Rs %s" % format(int(round(v)), ",")


def _n(v):
    return "—" if v is None else format(int(round(v)), ",")


def scoreboard_page(theme, sb):
    """The scoreboard as the dashboard draws it."""
    this = sb["this"]
    if not this:
        return ""
    s, p, rs = sb["save"], sb["peak"], sb["rs"]
    week_total = sum(save_rs(er.totals(d[1])) for d in this)
    hero = (
        '<div class="ec-card sv-hero"><div><div class="lbl">Could have been '
        'saved · %s</div><div class="big" style="color:var(--crit)">%s</div>'
        '<div class="sub">Cooling rooms nobody was in, and more units than '
        'the people in needed, all seven days.%s</div></div>'
        '<div><div class="lbl">A usual day</div><div class="big">%s</div>'
        '<div class="sub">%s%s</div></div></div>'
        % (esc(week_text(this)), _rs(week_total),
           (" At this pace <b>%s a month</b>." % _rs(s["now"] * 30))
           if s["now"] is not None else "",
           _rs(s["now"]),
           ("against %s the week before" % _rs(s["before"]))
           if s["change"] is not None else
           "the week before was not watched enough to compare yet",
           chip(s["change"], "better", "worse")))
    tiles = []
    m = sb.get("meters")
    if m:
        notes = []
        for b in m["bills"]:
            notes.append("%s (%s): %s a day %s"
                         % (esc(b["label"]), esc(b["kind"]), _n(b["per_day"]),
                            chip(b["change"])))
        tiles.append(ev.tile(
            "Units a day, 140-H meters", _n(m["now"]),
            "now, from the readings<br>" + "<br>".join(notes)
            if notes else "now, from the readings; no bill to set it against"))
    tiles.append(ev.tile(
        "Peak hours, a usual day", _rs(p["now"]),
        "the ACs from 6:30 to 10:30 pm, at the peak rate; with nobody in "
        "%s %s" % (_rs(sb["peak_waste"]["now"]), chip(p["change"]))))
    tiles.append(ev.tile(
        "AC electricity, a usual day", _rs(rs["now"]),
        "%s kWh, the cameras' estimate of every room's ACs %s"
        % (_n(sb["kwh"]["now"]), chip(rs["change"]))))
    days_note = ("%d whole day%s this week, %d the week before"
                 % (s["days"], "" if s["days"] == 1 else "s",
                    s["days_before"]))
    return "".join([
        ev.css(theme), CSS, '<div class="ec">',
        '<div class="ec-h"><span class="t">Savings scoreboard</span>'
        '<span class="c">%s · %s</span></div>' % (esc(week_text(this)),
                                                 esc(days_note)),
        hero, '<div class="en-tiles" style="margin-top:14px">',
        "".join(tiles), "</div>",
        '<div class="en-note">The meters fall with the weather and the solar '
        "panels as well as with anything done in the rooms: November is cooler "
        "than October, which is why the same month a year ago is beside it. "
        "The part that is EnergyCam's is the red figure -- what was spent "
        "cooling nobody. A usual day counts only days the cameras watched "
        "nearly whole.</div></div>"])


def peak_page(theme, week, rates, window, base=None, where="Both campuses"):
    """Every room's ACs in the peak tariff's hours, day by day."""
    week = [w for w in week if w[1]]
    if not week:
        return ""
    off, on = rates
    hours_text = "%s to %s" % (clock(window[0]), clock(window[1]))
    sums = [er.totals(w[1]) for w in week]
    full = [i for i, w in enumerate(week) if peak_whole(w, window)]
    usual = (sum(sums[i]["peak_rs"] for i in full) / len(full)) if full else None
    usual_e = (sum(sums[i]["peak_waste_rs"] for i in full) / len(full)
               if full else None)
    usual_kwh = (sum(sums[i]["peak_kwh"] for i in full) / len(full)
                 if full else None)
    done = [i for i, w in enumerate(week) if not w[2]]
    last = done[-1] if done else None
    tiles = "".join([
        ev.tile("Peak hours, a usual day", _rs(usual),
                "%s kWh · from %d day%s with the peak hours watched"
                % (_n(usual_kwh), len(full), "" if len(full) == 1 else "s")),
        ev.tile("Of which, nobody in", _rs(usual_e),
                ("%.0f%% of the peak cost could have been saved"
                 % (100.0 * usual_e / usual)) if usual else "", "crit"),
        ev.tile("A month of peak hours", _rs(usual * 30 if usual else None),
                "30 usual days at Rs %s a unit -- Rs %s more than the same "
                "units off-peak" % (_n(on), _n((on - off) * usual_kwh * 30))
                if usual else ""),
        ev.tile("%s's peak hours" % (pd.Timestamp(week[last][0]).strftime("%A")
                                     if last is not None else "Yesterday"),
                _rs(sums[last]["peak_rs"]) if last is not None else "—",
                ("with nobody in %s%s" % (
                    _rs(sums[last]["peak_waste_rs"]),
                    "" if peak_whole(week[last], window) else
                    " · only %.1f h of the peak hours were watched"
                    % (sums[last].get("watched_peak_h") or 0.0)))
                if last is not None else ""),
    ])
    in_colour = "#2a9d63" if theme == "dark" else "#1f8a55"
    empty_colour = "#e8a21a" if theme == "dark" else "#d18a00"
    labels, stacks, tips, marks = [], [], [], []
    for (day, ledger, so_far), t in zip(week, sums):
        labels.append(pd.Timestamp(day).strftime("%a %d").replace(" 0", " "))
        stacks.append([max(0.0, t["peak_rs"] - t["peak_waste_rs"]),
                       t["peak_waste_rs"]])
        tips.append("%s%s · peak hours %s (%s kWh) · with nobody in %s"
                    % (pd.Timestamp(day).strftime("%a %d %b"),
                       " so far" if so_far else "", _rs(t["peak_rs"]),
                       _n(t["peak_kwh"]), _rs(t["peak_waste_rs"])))
        marks.append("so far" if so_far else (
            None if peak_whole((day, ledger, so_far), window)
            # short: on a phone a column is ~40 px ("3.5h of 4 seen" ran
            # over the next day's bar, 26 Nov)
            else "%.1f/%g h" % (t.get("watched_peak_h") or 0.0,
                                window[1] - window[0])))
    chart = "".join([
        '<div class="ec-card" style="padding:14px 16px;margin-top:14px">',
        ev.legend([(in_colour, "with people in"),
                   (empty_colour, "with nobody in")]),
        ev.columns(labels, stacks, [in_colour, empty_colour], tips,
                   height=190, marks=marks), "</div>"])

    # Room by room: the finished days' total, then each day.
    finished = [week[i] for i in done]
    ranked = rooms_over(finished, "peak_rs")
    empty_by = {n: v for n, v, _ in rooms_over(finished, "peak_waste_rs")}
    used = [x for x in ranked if x[1] >= 0.5]
    idle = len(ranked) - len(used)
    top = max([x[1] for x in used] or [1]) or 1
    per_day = {}
    for i, (_, ledger, _) in enumerate(week):
        for r in ledger:
            per_day.setdefault(r["room"], {})[i] = r.get("peak_rs", 0.0)
    head = "".join(
        '<th class="wide">%s%s</th>'
        % (esc(pd.Timestamp(d).strftime("%a %d").replace(" 0", " ")),
           "<br><span style='font-weight:400;color:var(--t3)'>so far</span>"
           if so_far else "")
        for d, _, so_far in reversed(week))
    rows = []
    for name, total, r in used:
        label = esc(ov.short(name))
        if base is not None:
            label = ('<a href="%s" target="_self" style="color:inherit;'
                     'text-decoration:none">%s</a>'
                     % (esc(ov.link(base, room=name) + "#roomdetail"), label))
        e = empty_by.get(name, 0.0)
        share = 100.0 * total / top
        cells = []
        for i in reversed(range(len(week))):
            v = per_day.get(name, {}).get(i)
            cells.append('<td class="wide"%s>%s</td>' % (
                "" if v and v >= 0.5 else ' style="color:var(--t3)"',
                _n(v) if v and v >= 0.5 else "·"))
        rows.append(
            '<tr><td class="nm">%s<span>%s · %s</span></td>'
            '<td style="font-weight:700">%s</td>'
            '<td style="color:var(--crit);font-weight:650">%s</td>'
            '<td><div class="sv-bar"><i style="width:%.1f%%;background:%s">'
            '</i><i style="width:%.1f%%;background:%s"></i></div></td>%s</tr>'
            % (label, esc(r.get("building") or ""), esc(er.badge(r)),
               _rs(total), _rs(e) if e >= 0.5 else "·",
               max(0.0, share * (1 - e / total)) if total else 0, in_colour,
               share * e / total if total else 0, empty_colour,
               "".join(cells)))
    if idle:
        rows.append('<tr><td colspan="%d" style="color:var(--t2);text-align:'
                    'left;padding-left:0">%d more room%s ran no AC in the peak '
                    "hours these days</td></tr>"
                    % (4 + len(week), idle, "" if idle == 1 else "s"))
    table = "".join([
        '<div class="ec-card" style="padding:14px 16px;margin-top:14px">',
        '<div style="overflow-x:auto"><table class="sv-tbl"><tr><th>Room</th>'
        '<th>%d days</th><th>Nobody in</th><th></th>%s</tr>%s</table></div>'
        % (len(finished), head, "".join(rows)),
        '<div class="en-note">Rupees in the peak hours only, every finished '
        "day shown; the day columns hide on a phone. Green, the ACs ran with "
        "people in; amber, with nobody in. Rooms marked “assumed” have no "
        "unit in a camera: their ACs are taken to run while people are in.</div>"
        "</div>"])
    return "".join([
        ev.css(theme), CSS, '<div class="ec">',
        '<div class="ec-h" style="margin-top:26px"><span class="t">Peak hours,'
        ' every room</span><span class="c">%s · %s, Rs %s a unit (Rs %s the '
        "rest of the day)</span></div>" % (esc(where), hours_text, _n(on),
                                          _n(off)),
        '<div class="en-tiles">', tiles, "</div>", chart, table, "</div>"])
