"""A day of one employee at their desk, as a short video.

Shamroze, 23 Nov: "make a video of the employee's progress, so it looks
like real progress -- every measure, first in, last out, when last seen".

Each frame is one look at the desk (frames/progress/<day>/<code>/, the
same square every pass, written by the loop or by progress_track.backfill)
with the clock, what the employee was doing then, the day so far in
hours, and the whole day as a coloured bar with a cursor; the last few
seconds are the day's summary. Written as WebM (VP8, which a browser
plays) beside the pictures -- this machine only, like them.

    python progress_video.py                 # today, every employee
    python progress_video.py --day 2026-11-23 --code P1
"""
import argparse
import glob
import os
from datetime import datetime

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import progress_data as pdx
import progress_track as pt

W, H = 1280, 720
FPS = 3
END_SECONDS = 4
FROM, TO = 8, 24

COLOURS = {"computer": (42, 157, 99), "phone": (229, 56, 59),
           "talking": (139, 92, 246), "desk": (111, 191, 143),
           "unseen": (232, 162, 26), "out": (58, 58, 58)}
for _k in ("meeting", "own room", "office", "cafe", "smoking", "prayer",
           "corridor", "outside"):
    COLOURS[_k] = (57, 135, 229)
LABELS = {"computer": "At the computer", "phone": "On the phone",
          "talking": "Talking at the desk", "desk": "At the desk",
          "away": "Away from the desk", "unseen": "Away from the desk",
          "out": "Not in", "before": "Not in yet", "after": "Gone for the day"}
COLOURS_EXTRA = {"before": (58, 58, 58), "after": (58, 58, 58)}


def _font(size, bold=False):
    for name in (("segoeuib.ttf", "arialbd.ttf") if bold
                 else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(os.path.join(
                os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def hm(minutes):
    m = int(round(minutes))
    return "%dh %02dm" % (m // 60, m % 60)


def _bar(draw, line, day, x, y, w, h, now=None):
    base = datetime.strptime(day, "%Y-%m-%d")
    span = float((TO - FROM) * 3600)

    def pos(t):
        sec = (t - base).total_seconds() - FROM * 3600
        return x + w * min(1.0, max(0.0, sec / span))
    draw.rounded_rectangle([x, y, x + w, y + h], 4, fill=(40, 40, 40))
    for s, e, k, _ in line:
        a, b = pos(s.to_pydatetime()), pos(e.to_pydatetime())
        if b > a:
            draw.rectangle([a, y, b, y + h], fill=COLOURS.get(k, (90, 90, 90)))
    small = _font(15)
    for hour in range(FROM, TO + 1, 2):
        hx = x + w * (hour - FROM) / float(TO - FROM)
        draw.text((hx, y + h + 6), "%02d" % (hour % 24), font=small,
                  fill=(150, 150, 150), anchor="mt")
    if now is not None:
        cx = pos(now)
        draw.rectangle([cx - 2, y - 8, cx + 2, y + h + 8], fill=(255, 255, 255))


def _so_far(line, until):
    out = {"computer": 0.0, "phone": 0.0, "talking": 0.0, "desk": 0.0,
           "away": 0.0}
    for s, e, k, _ in line:
        s, e = s.to_pydatetime(), e.to_pydatetime()
        if s >= until:
            break
        e = min(e, until)
        mins = (e - s).total_seconds() / 60.0
        if k in out:
            out[k] += mins
        elif k not in ("out",):
            out["away"] += mins
    return out


def frame_for(person, day, summary, crop, when, state):
    img = Image.new("RGB", (W, H), (17, 17, 17))
    d = ImageDraw.Draw(img)
    who = person.get("name") or "Employee %s" % person["code"]
    d.text((40, 26), "%s  ·  %s" % (who, person.get("department", "")),
           font=_font(30, True), fill=(240, 240, 236))
    d.text((W - 40, 34), datetime.strptime(day, "%Y-%m-%d").strftime(
        "%a %d %b %Y") + "  ·  EnergyCam Progress", font=_font(18),
        fill=(150, 150, 150), anchor="ra")
    if crop is not None:
        pic = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        img.paste(pic.resize((540, 540)), (40, 86))
    first, last = summary.get("first_in"), summary.get("last_out")
    if state == "away" and first is not None and \
            when < first.to_pydatetime():
        state = "before"
    elif state == "away" and last is not None and \
            when > last.to_pydatetime():
        state = "after"
    elif state == "away" and first is None:
        state = "before"
    colour = COLOURS.get(state) or COLOURS_EXTRA.get(state) or \
        COLOURS["unseen"]
    d.rectangle([40, 86, 580, 626], outline=colour, width=4)
    d.text((630, 90), when.strftime("%H:%M"), font=_font(96, True),
           fill=(255, 255, 255))
    d.rounded_rectangle([634, 214, 1000, 262], 22, fill=colour)
    d.text((817, 238), LABELS.get(state, state), font=_font(24, True),
           fill=(255, 255, 255), anchor="mm")
    so = _so_far(summary["line"], when)
    rows = [("At the computer", so["computer"] + so["desk"], "computer"),
            ("On the phone", so["phone"], "phone"),
            ("Talking at the desk", so["talking"], "talking"),
            ("Away from the desk", so["away"], "unseen")]
    total = max(1.0, sum(r[1] for r in rows))
    y = 300
    for label, mins, key in rows:
        d.text((634, y), label, font=_font(20), fill=(200, 200, 196))
        d.text((1240, y), hm(mins), font=_font(20, True),
               fill=(240, 240, 236), anchor="ra")
        d.rounded_rectangle([634, y + 32, 1240, y + 40], 4, fill=(45, 45, 45))
        d.rounded_rectangle([634, y + 32, 634 + 606 * mins / total, y + 40],
                            4, fill=COLOURS[key])
        y += 66
    d.text((634, y + 6), "First in %s" % (first.strftime("%H:%M")
                                          if first is not None and
                                          first.to_pydatetime() <= when
                                          else "--"),
           font=_font(18), fill=(150, 150, 150))
    _bar(d, summary["line"], day, 40, 662, W - 80, 16, when)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def end_card(person, day, summary, check):
    img = Image.new("RGB", (W, H), (17, 17, 17))
    d = ImageDraw.Draw(img)
    who = person.get("name") or "Employee %s" % person["code"]
    d.text((W // 2, 70), "%s · the day" % who, font=_font(40, True),
           fill=(240, 240, 236), anchor="mm")
    d.text((W // 2, 112), "%s  ·  %s" % (person.get("department", ""),
                                         datetime.strptime(day, "%Y-%m-%d")
                                         .strftime("%A %d %B %Y")),
           font=_font(20), fill=(150, 150, 150), anchor="mm")
    m, est = summary["minutes"], summary["estimate"]

    def t(x):
        return x.strftime("%H:%M") if x is not None else "--"
    away = sum(v for k, v in m.items() if k not in pt.AT_DESK)
    cells = [("First in", t(summary["first_in"])),
             ("Last out", t(summary["last_out"])),
             ("Last seen", t(summary["last_seen"])),
             ("At the desk", hm(sum(m[k] for k in pt.AT_DESK))),
             ("Computer", hm(est["computer"])),
             ("Phone", hm(est["phone"])),
             ("Talking", hm(est["talking"])),
             ("Away from desk", hm(away))]
    for i, (k, v) in enumerate(cells):
        cx = 160 + (i % 4) * 320
        cy = 230 + (i // 4) * 170
        d.rounded_rectangle([cx - 140, cy - 60, cx + 140, cy + 70], 18,
                            fill=(30, 30, 30))
        d.text((cx, cy - 25), k, font=_font(20), fill=(150, 150, 150),
               anchor="mm")
        d.text((cx, cy + 22), v, font=_font(40, True), fill=(255, 255, 255),
               anchor="mm")
    note = ("Away places are not yet identified (no camera match is trusted"
            " yet). ")
    if check and check.get("frames"):
        note += "Desk readings checked by eye: %s of %s agree." % (
            check.get("agree"), check.get("frames"))
    d.text((W // 2, 560), note, font=_font(18), fill=(150, 150, 150),
           anchor="mm")
    _bar(d, summary["line"], day, 40, 640, W - 80, 18)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def make(person, day, out=None):
    """Write the day's video for one employee; returns its path or None."""
    folder = os.path.join(pt.CROPS, day, person["code"])
    shots = sorted(glob.glob(os.path.join(folder, "*_desk_*.jpg")))
    shots = [s for s in shots
             if "%02d" % FROM <= os.path.basename(s)[:2] <= "23"]
    if not shots:
        return None
    summary = pdx.day_activity(person, day)
    out = out or os.path.join(pt.CROPS, day, "%s_day.webm" % person["code"])
    writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"VP80"), FPS,
                             (W, H))
    if not writer.isOpened():
        return None
    base = datetime.strptime(day, "%Y-%m-%d")
    for path in shots:
        name = os.path.basename(path)
        hhmmss, state = name.split("_desk_")[0], name.split("_desk_")[1][:-4]
        when = base.replace(hour=int(hhmmss[:2]), minute=int(hhmmss[2:4]),
                            second=int(hhmmss[4:6]))
        writer.write(frame_for(person, day, summary, cv2.imread(path), when,
                               state))
    card = end_card(person, day, summary, person.get("check"))
    for _ in range(FPS * END_SECONDS):
        writer.write(card)
    writer.release()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--day", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--code")
    args = ap.parse_args()
    for person in (pdx.load() or {}).get("people") or []:
        if args.code and person["code"] != args.code:
            continue
        print(person["code"], make(person, args.day) or "no pictures")


if __name__ == "__main__":
    main()
