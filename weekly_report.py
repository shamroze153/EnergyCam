"""The weekly report, by email: the savings scoreboard, the peak hours and
the rooms worth a look, for the seven days before it was sent.

Shamroze, 18 Nov: "the savings scoreboard, a weekly report to my email -- a
nice one". The loop starts it once a week, on Monday from nine in the
morning (room_loop.weekly_mail); by hand:

    python weekly_report.py --preview report.html   write it, send nothing
    python weekly_report.py --send                  send it now
    python weekly_report.py --due                   send it if it is due

Who it goes to is REPORT_TO in .env (several, comma separated) -- never in
this file: the repository is public. It is sent from SENDER_EMAIL with
APP_PASSWORD, the same Gmail the alerts use. The figures are the
dashboard's own (ledger_data, savings), read with DASHBOARD_DATABASE_URL.

Email clients draw almost nothing of a web page: no SVG, no style sheet
worth trusting, no script. So every bar here is a table cell with a width
and a colour, every style is inline, and a plain-text copy travels with it.
"""
import argparse
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formatdate
from html import escape

PKT = timezone(timedelta(hours=5))
STATE = "weekly_report_sent.json"      # local, ignored: the week last sent
SEND_FROM_HOUR = 9                     # Monday, Karachi clock

# Light, plain colours that read in every mail client and in print.
INK, INK2, INK3 = "#1d2433", "#4a5263", "#7a8293"
LINE, PAPER, CARD = "#e4e7ec", "#f4f5f7", "#ffffff"
GREEN, AMBER, RED, BLUE = "#1f8a55", "#d18a00", "#c42b2e", "#2f6fd0"


def here():
    return os.path.dirname(os.path.abspath(__file__))


def recipients():
    raw = os.getenv("REPORT_TO") or ""
    return [a.strip() for a in raw.split(",") if a.strip()]


def week_id(now):
    y, w, _ = now.isocalendar()
    return "%d-W%02d" % (y, w)


# Tries a week before giving up until the next: a login Gmail refuses,
# repeated every few hours, is how an account gets flagged (18 Nov: this
# laptop's Kaspersky sits inside the mail connection and it drops at login).
MAX_TRIES = 2


def _state(path=None):
    try:
        with open(path or os.path.join(here(), STATE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(state, path=None):
    with open(path or os.path.join(here(), STATE), "w",
              encoding="utf-8") as f:
        json.dump(state, f)


def last_sent(path=None):
    s = _state(path)
    return s.get("week") if s.get("sent") else None


def failures(week, path=None):
    s = _state(path)
    return int(s.get("failed", 0)) if s.get("failed_week") == week else 0


def mark_sent(now, path=None):
    s = _state(path)
    s.update(week=week_id(now), sent=now.isoformat())
    _save(s, path)


def mark_failed(now, path=None):
    s, week = _state(path), week_id(now)
    s["failed"] = failures(week, path) + 1
    s["failed_week"] = week
    _save(s, path)


def due(now, sent=None, to=None, tries=None):
    """The week to send for, if this week's report has not gone yet and it
    is Monday nine o'clock or later; else None. A laptop off on Monday sends
    it when it is next on, that week -- but not after MAX_TRIES failures."""
    to = recipients() if to is None else to
    if not to:
        return None
    local = now.astimezone(PKT)
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=SEND_FROM_HOUR, minute=0, second=0, microsecond=0)
    if local < monday:
        return None
    week = week_id(local)
    sent = last_sent() if sent is None else sent
    tries = failures(week) if tries is None else tries
    return None if sent == week or tries >= MAX_TRIES else week


# ===================================================================== data

def collect(now, url=None):
    """Fourteen days of rooms (both campuses) and the meters, as the page
    reads them."""
    import pandas as pd
    import psycopg2

    import analysis_view as av
    import energy_view as ev
    import ledger_data as ld
    import meters_view
    import savings

    url = url or os.getenv("DASHBOARD_DATABASE_URL") or os.getenv(
        "DATABASE_URL")
    local = pd.Timestamp(now).tz_convert("Asia/Karachi")
    end = local.normalize()
    start = end - pd.Timedelta(days=14)
    rooms, a = ld.rooms_frame(), ld.assumptions()
    rates = ld.rates_of(a)
    conn = psycopg2.connect(url, sslmode=os.getenv("DB_SSLMODE") or "require",
                            connect_timeout=15)
    try:
        events = ld.events_between(conn, start.tz_convert("UTC"),
                                   end.tz_convert("UTC"))
        beats = ld.beats_between(conn,
                                 start.tz_convert("UTC") - pd.Timedelta(
                                     minutes=10),
                                 end.tz_convert("UTC") + pd.Timedelta(
                                     minutes=10))
        meters, readings, bills = meters_view.load(conn, 60)
    finally:
        conn.close()
    days = []
    for back in range(14, 0, -1):
        d0 = end - pd.Timedelta(days=back)
        days.append((d0.date(), ld.ledger_for(
            rooms, events, beats, a, d0.tz_convert("UTC"),
            (d0 + pd.Timedelta(days=1)).tz_convert("UTC")), False))
    est = ev.month_estimate(readings, meters, rates, av.peak_window(a))
    return {"days": days, "sb": savings.scoreboard(days, est, bills,
                                                   av.peak_window(a)),
            "rates": rates, "window": av.peak_window(a), "est": est,
            "meters": meters, "now": local}


# ===================================================================== mail

def rs(v):
    return "&mdash;" if v is None else "Rs&nbsp;" + format(int(round(v)), ",")


def n(v):
    return "&mdash;" if v is None else format(int(round(v)), ",")


def change_html(change, less="less", more="more", good_when_down=True):
    if change is None:
        return ""
    if abs(change) < 0.5:
        return '<span style="color:%s">about the same</span>' % INK3
    down = change < 0
    colour = GREEN if down == good_when_down else RED
    return ('<span style="color:%s;font-weight:700">%s&nbsp;%.0f%%&nbsp;%s'
            '</span>' % (colour, "&#9660;" if down else "&#9650;",
                         abs(change), less if down else more))


def bar(parts, width=100):
    """A bar of [(share 0-100, colour)] as one table row: mail-safe."""
    cells = "".join(
        '<td style="background:%s;height:10px;width:%.1f%%;font-size:0;'
        'line-height:0">&nbsp;</td>' % (c, w) for w, c in parts if w > 0.2)
    rest = max(0.0, 100 - sum(w for w, _ in parts if w > 0.2))
    if rest > 0.2:
        cells += ('<td style="background:%s;height:10px;width:%.1f%%;'
                  'font-size:0;line-height:0">&nbsp;</td>' % (PAPER, rest))
    return ('<table role="presentation" cellpadding="0" cellspacing="0" '
            'style="width:%d%%;border-collapse:collapse;border-radius:5px;'
            'overflow:hidden"><tr>%s</tr></table>' % (width, cells))


def tile(label, value, note, colour=INK):
    return ('<td valign="top" style="width:50%%;padding:6px">'
            '<div style="background:%s;border:1px solid %s;border-radius:12px;'
            'padding:14px 16px"><div style="font-size:11px;letter-spacing:'
            '.08em;text-transform:uppercase;color:%s;font-weight:700">%s</div>'
            '<div style="font-size:24px;font-weight:800;color:%s;margin-top:4px'
            '">%s</div><div style="font-size:12.5px;color:%s;margin-top:4px;'
            'line-height:1.5">%s</div></div></td>'
            % (CARD, LINE, INK3, label, colour, value, INK2, note))


def section(title, caption, body):
    return ('<tr><td style="padding:22px 6px 6px"><div style="font-size:17px;'
            'font-weight:800;color:%s">%s</div><div style="font-size:12.5px;'
            'color:%s;margin-top:2px">%s</div></td></tr><tr><td style="padding:'
            '6px"><div style="background:%s;border:1px solid %s;border-radius:'
            '12px;padding:12px 16px">%s</div></td></tr>'
            % (INK, title, INK3, caption, CARD, LINE, body))


def tips(data):
    """Three things worth doing this week, from what the week showed."""
    import energy_rooms as er
    import overview as ov
    import savings
    this = data["sb"]["this"]
    out = []
    worst = savings.rooms_over(this, savings.save_rs)
    if worst and worst[0][1] >= 1:
        name, total, row = worst[0]
        hours = er.hourly([r for _, led, _ in this for r in led
                           if r["room"] == name])
        runs = er.waste_stretches(hours)
        when = ("mostly %s to %s" % (savings.clock(runs[0][0]),
                                     savings.clock(runs[0][1] % 24))
                if runs else "")
        if row.get("basis") == er.ASSUMED:
            # Nobody sees its unit: the money is what it would cost if the
            # AC ran between visits. Said as a question, not as a finding
            # (18 Nov: Room 18's "12 am to 5 am" is people seen there off
            # and on every night -- somebody sleeping, or a chair).
            night = runs and runs[0][0] < 6
            out.append(
                "<b>%s</b>: <b>%s</b> this week if its AC ran while the room "
                "sat empty between visits%s. No camera sees its unit, so this "
                "is worth a look%s."
                % (escape(ov.short(name)), rs(total),
                   (", " + when) if when else "",
                   " -- people are seen there at night: is somebody sleeping "
                   "there, with the AC on?" if night else ""))
        else:
            out.append("<b>%s</b>'s AC ran with nobody in: <b>%s</b> this "
                       "week%s. Ask whoever is last out to switch it off."
                       % (escape(ov.short(name)), rs(total),
                          (", " + when) if when else ""))
    told = {worst[0][0]} if worst else set()
    peak = [x for x in savings.rooms_over(this, "peak_waste_rs")
            if x[0] not in told]
    if peak and peak[0][1] >= 1:
        told.add(peak[0][0])
        out.append("<b>%s</b> was cooled with nobody in during the peak hours "
                   "(%s a unit): <b>%s</b> this week."
                   % (escape(ov.short(peak[0][0])), rs(data["rates"][1]),
                      rs(peak[0][1])))
    over = savings.rooms_over(this, "over_rs")
    if over and over[0][1] >= 1:
        out.append("<b>%s</b> ran more units than its people needed: "
                   "<b>%s</b> this week. One unit fewer when it is quiet."
                   % (escape(ov.short(over[0][0])), rs(over[0][1])))
    return out


def compose(data):
    """(subject, html, text) for the week in `data`."""
    import energy_rooms as er
    import overview as ov
    import savings

    sb, rates, window = data["sb"], data["rates"], data["window"]
    this = sb["this"]
    span = savings.week_text(this)
    save_week = sum(savings.save_rs(er.totals(d[1])) for d in this)
    s, p = sb["save"], sb["peak"]
    subject = "EnergyCam weekly report, %s: %s could have been saved" % (
        span.replace("–", "-"), "Rs " + format(int(round(save_week)), ","))

    hero = (
        '<tr><td style="padding:6px"><div style="background:%s;border-radius:'
        '14px;padding:20px 22px;color:#fff"><div style="font-size:11px;'
        'letter-spacing:.12em;text-transform:uppercase;opacity:.85;'
        'font-weight:700">Could have been saved this week</div><div style="'
        'font-size:40px;font-weight:800;margin-top:4px">%s</div><div style="'
        'font-size:13.5px;margin-top:6px;line-height:1.5;opacity:.95">Cooling '
        "rooms nobody was in, and more units than the people in needed. %s"
        "</div></div></td></tr>"
        % (RED, rs(save_week),
           ("A usual day %s; at this pace <b>%s a month</b>."
            % (rs(s["now"]), rs(s["now"] * 30))) if s["now"] is not None
           else ""))

    tiles_ = []
    m = sb.get("meters")
    if m:
        notes = "<br>".join("%s (%s): %s a day %s" % (
            escape(b["label"]), escape(b["kind"]), n(b["per_day"]),
            change_html(b["change"])) for b in m["bills"])
        tiles_.append(tile("Units a day, 140-H meters", n(m["now"]),
                           "now, from the readings<br>" + notes))
    tiles_.append(tile(
        "Could have been saved, a day", rs(s["now"]),
        ("the week before %s<br>%s" % (rs(s["before"]),
                                       change_html(s["change"], "better",
                                                   "worse")))
        if s["change"] is not None else
        "the week before was not watched enough to compare yet", RED))
    tiles_.append(tile(
        "Peak hours, a day", rs(p["now"]),
        "%s to %s at %s a unit<br>with nobody in %s %s"
        % (savings.clock(window[0]), savings.clock(window[1]), rs(rates[1]),
           rs(sb["peak_waste"]["now"]), change_html(p["change"]))))
    tiles_.append(tile(
        "AC electricity, a day", rs(sb["rs"]["now"]),
        "%s kWh, every room's ACs, both campuses (the cameras' estimate)<br>%s"
        % (n(sb["kwh"]["now"]), change_html(sb["rs"]["change"]))))
    grid = "".join("<tr>%s</tr>" % "".join(tiles_[i:i + 2])
                   for i in range(0, len(tiles_), 2))
    board = ('<tr><td><table role="presentation" cellpadding="0" '
             'cellspacing="0" style="width:100%%">%s</table></td></tr>' % grid)

    # Day by day.
    sums = [(d, er.totals(d[1])) for d in this]
    top = max([t["rs"] for _, t in sums] or [1]) or 1
    rows = []
    for (day, _, _), t in sums:
        partial = t.get("watched_h", 24) < er.WHOLE_DAY_H
        rows.append(
            '<tr><td style="padding:6px 8px 6px 0;font-size:13px;color:%s;'
            'white-space:nowrap;width:70px">%s</td><td style="padding:6px 0">'
            '%s</td><td style="padding:6px 0 6px 10px;text-align:right;'
            'font-size:13px;font-weight:700;color:%s;white-space:nowrap">%s'
            '</td><td style="padding:6px 0 6px 10px;text-align:right;'
            'font-size:12.5px;color:%s;white-space:nowrap">%s</td></tr>'
            % (INK, escape(pd_day(day)),
               bar([(100.0 * (t["rs"] - savings.save_rs(t)) / top, GREEN),
                    (100.0 * savings.save_rs(t) / top, AMBER)]),
               INK, rs(t["rs"]), RED if not partial else INK3,
               (rs(savings.save_rs(t)) if not partial else
                "%.0fh watched" % t.get("watched_h", 0))))
    days_html = ('<table role="presentation" cellpadding="0" cellspacing="0" '
                 'style="width:100%%">%s</table><div style="font-size:12px;'
                 'color:%s;margin-top:8px">Green, the ACs with people in; '
                 'amber, what could have been saved. On the right, the AC '
                 'cost and the saving.</div>' % ("".join(rows), INK3))

    def room_table(items, value_label, extra, colour):
        if not items:
            return '<div style="color:%s;font-size:13px">Nothing this week.' \
                   '</div>' % INK3
        top_ = max(v for _, v, _ in items) or 1
        out = []
        for name, value, row in items:
            out.append(
                '<tr><td style="padding:7px 8px 7px 0;font-size:13px;color:%s;'
                'font-weight:650">%s<div style="font-size:11.5px;color:%s;'
                'font-weight:400">%s</div></td><td style="padding:7px 0;'
                'width:38%%">%s</td><td style="padding:7px 0 7px 10px;'
                'text-align:right;font-size:13px;font-weight:700;color:%s;'
                'white-space:nowrap">%s</td></tr>'
                % (INK, escape(ov.short(name)), INK3,
                   escape(extra(name, row)), bar([(100.0 * value / top_,
                                                    colour)]),
                   INK, rs(value)))
        return ('<table role="presentation" cellpadding="0" cellspacing="0" '
                'style="width:100%%"><tr><td style="font-size:11px;color:%s;'
                'padding-bottom:4px">Room</td><td></td><td style="font-size:'
                '11px;color:%s;text-align:right;padding-bottom:4px">%s</td>'
                '</tr>%s</table>' % (INK3, INK3, value_label, "".join(out)))

    empty_peak = {k: v for k, v, _ in savings.rooms_over(this,
                                                         "peak_waste_rs")}
    peak_rooms = [x for x in savings.rooms_over(this, "peak_rs")
                  if x[1] >= 1][:10]
    peak_html = room_table(
        peak_rooms, "7 days",
        lambda name, row: "%s · with nobody in %s" % (
            row.get("building") or "",
            "Rs " + format(int(round(empty_peak.get(name, 0))), ",")),
        BLUE)
    waste_rooms = [x for x in savings.rooms_over(this, savings.save_rs)
                   if x[1] >= 1][:10]
    waste_html = room_table(
        waste_rooms, "could save",
        lambda name, row: "%s · %s" % (row.get("building") or "",
                                        er.badge(row)), RED)

    meters_html = ""
    est = data.get("est")
    if est:
        labels = {r["code"]: r["label"] for _, r in data["meters"].iterrows()}
        each = "".join(
            '<tr><td style="padding:5px 0;font-size:13px;color:%s">%s</td>'
            '<td style="padding:5px 0;text-align:right;font-size:13px;'
            'font-weight:700;color:%s">%s units a day</td></tr>'
            % (INK, escape(labels.get(k, k)), INK, n(v))
            for k, v in est["meters"].items())
        meters_html = section(
            "The 140-H meters", "from the readings typed in, %s"
            % escape(savings.week_text([(est["from"].tz_convert(
                "Asia/Karachi").date(), None, False), (est["to"].tz_convert(
                    "Asia/Karachi").date(), None, False)])),
            '<table role="presentation" cellpadding="0" cellspacing="0" '
            'style="width:100%%">%s<tr><td style="padding:8px 0 0;font-size:'
            '13px;color:%s;border-top:1px solid %s">A month at this pace'
            '</td><td style="padding:8px 0 0;text-align:right;font-size:13px;'
            'font-weight:800;color:%s;border-top:1px solid %s">%s units, '
            'about %s</td></tr></table><div style="font-size:12px;color:%s;'
            'margin-top:8px">Off-peak %s units at %s, peak %s at %s -- a '
            'rough split. The ground floor meter is after the solar panels.'
            '</div>'
            % (each, INK2, LINE, INK, LINE, n(est["month"]), rs(est["rs"]),
               INK3, n(est["off_units"]), rs(rates[0]), n(est["peak_units"]),
               rs(rates[1])))

    todo = tips(data)
    todo_html = section(
        "Worth doing this week", "from what the cameras saw",
        "".join('<div style="font-size:13.5px;color:%s;line-height:1.55;'
                'padding:5px 0">&#8226; %s</div>' % (INK, t) for t in todo)
    ) if todo else ""

    whole_days = s["days"]
    html_ = "".join([
        '<!doctype html><html><head><meta charset="utf-8"><meta name="'
        'viewport" content="width=device-width,initial-scale=1"><title>'
        'EnergyCam weekly report</title></head>',
        '<body style="margin:0;padding:0;background:%s;font-family:-apple-'
        "system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:%s\">" %
        (PAPER, INK),
        '<table role="presentation" cellpadding="0" cellspacing="0" style="'
        'width:100%%;background:%s"><tr><td align="center" style="padding:'
        '18px 10px">' % PAPER,
        '<table role="presentation" cellpadding="0" cellspacing="0" style="'
        'width:100%;max-width:660px">',
        '<tr><td style="padding:6px 6px 14px"><div style="font-size:13px;'
        'font-weight:800;letter-spacing:.06em;color:%s">ENERGYCAM'
        '<span style="color:%s;font-weight:600;letter-spacing:0"> · Disrupt'
        '</span></div><div style="font-size:24px;font-weight:800;color:%s;'
        'margin-top:6px">Weekly report</div><div style="font-size:13.5px;'
        'color:%s;margin-top:2px">%s · both campuses · against the week before'
        '</div></td></tr>' % (RED, INK3, INK, INK2, escape(span)),
        hero, board,
        section("Day by day", "the ACs' cost each day, the part that could "
                "have been saved in amber", days_html),
        section("Peak hours, every room", "%s to %s, %s a unit instead of %s"
                % (savings.clock(window[0]), savings.clock(window[1]),
                   rs(rates[1]), rs(rates[0])), peak_html),
        section("Where it could have been saved", "cooling nobody, and more "
                "units than the people needed", waste_html),
        meters_html, todo_html,
        '<tr><td style="padding:20px 6px 6px;font-size:11.5px;color:%s;'
        'line-height:1.6">Rooms: counted by the cameras already on the '
        'buildings; a room whose AC no camera reads is taken to run while '
        'people are in ("assumed"). A usual day is the average of the days '
        'the cameras watched nearly whole: %d this week, %d the week before. '
        'The meters fall with the weather and the solar panels too, which is '
        'why the same month a year ago stands beside the last bill. No '
        'picture leaves the building.<br>Sent by EnergyCam every Monday '
        'morning.</td></tr>' % (INK3, whole_days, s["days_before"]),
        "</table></td></tr></table></body></html>"])

    lines = ["EnergyCam weekly report, %s" % span, "",
             "Could have been saved this week: %s" % strip(rs(save_week))]
    if s["now"] is not None:
        lines.append("A usual day %s%s; a month at this pace %s." % (
            strip(rs(s["now"])),
            (" (the week before %s, %+.0f%%)" % (strip(rs(s["before"])),
                                                 s["change"]))
            if s["change"] is not None else "",
            strip(rs(s["now"] * 30))))
    if m:
        lines.append("140-H meters: %s units a day now." % strip(n(m["now"])))
        for b in m["bills"]:
            lines.append("  %s (%s): %s a day, %+.0f%%." % (
                b["label"], b["kind"], strip(n(b["per_day"])), b["change"]))
    lines.append("Peak hours a day: %s, with nobody in %s." % (
        strip(rs(p["now"])), strip(rs(sb["peak_waste"]["now"]))))
    lines += ["", "Peak hours, room by room (7 days):"]
    lines += ["  %-34s %s" % (ov.short(nm), strip(rs(v)))
              for nm, v, _ in peak_rooms]
    lines += ["", "Could have been saved, room by room (7 days):"]
    lines += ["  %-34s %s" % (ov.short(nm), strip(rs(v)))
              for nm, v, _ in waste_rooms]
    if todo:
        lines += ["", "Worth doing this week:"]
        lines += ["  - " + strip(t) for t in todo]
    return subject, html_, "\n".join(lines) + "\n"


def pd_day(day):
    import pandas as pd
    return pd.Timestamp(day).strftime("%a %d").replace(" 0", " ")


def strip(text):
    """Mail HTML to plain text, for the text copy."""
    import re
    from html import unescape
    return unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ")


def deliver(subject, html_, text, to, host="smtp.gmail.com", port=465):
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("APP_PASSWORD")
    if not sender or not password:
        raise RuntimeError("SENDER_EMAIL and APP_PASSWORD are not in .env")
    message = EmailMessage()
    message["From"] = "EnergyCam <%s>" % sender
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message.set_content(text)
    message.add_alternative(html_, subtype="html")
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(),
                          timeout=30) as server:
        server.login(sender, password)
        server.send_message(message)
    return len(to)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--preview", metavar="FILE",
                        help="write the report's HTML here; send nothing")
    parser.add_argument("--send", action="store_true", help="send it now")
    parser.add_argument("--due", action="store_true",
                        help="send it only if this week's has not gone")
    args = parser.parse_args(argv)
    os.chdir(here())
    sys.path.insert(0, here())
    from dotenv import load_dotenv
    load_dotenv(os.path.join(here(), ".env"))
    now = datetime.now(PKT)
    if args.due and not due(now):
        print("weekly report: not due (%s)" % (
            "no REPORT_TO in .env" if not recipients() else
            "already sent for %s, tried %d times, or before Monday 9:00"
            % (week_id(now), MAX_TRIES)))
        return 0
    if not (args.preview or args.send or args.due):
        parser.print_help()
        return 0
    data = collect(now)
    subject, html_, text = compose(data)
    if args.preview:
        with open(args.preview, "w", encoding="utf-8") as f:
            f.write(html_)
        print("weekly report written to %s: %s" % (args.preview, subject))
    if args.send or args.due:
        to = recipients()
        if not to:
            print("weekly report: no REPORT_TO in .env, nothing sent")
            return 1
        try:
            deliver(subject, html_, text, to)
        except Exception as e:                              # noqa: BLE001
            # Never the password: only the kind of error.
            mark_failed(now)
            print("weekly report: could not send (%s); %d of %d tries this "
                  "week" % (type(e).__name__, failures(week_id(now)),
                            MAX_TRIES))
            return 1
        mark_sent(now)
        print("weekly report sent to %d address(es): %s" % (len(to), subject))
    return 0


if __name__ == "__main__":
    sys.exit(main())
