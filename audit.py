"""Is the loop telling the truth? Read the record back and look for tells.

Asked for after a room reported "empty, and still cooling" with four people
sitting in it. That is the failure that matters most and the one nobody
sees: a false "occupied" is annoying, a false "empty" sends an alert saying
switch the cooling off in a room full of people, and it is also the shape
of a room nobody ever checks because it never raises anything.

Nothing here touches a camera. It reads what was written down and asks
whether the pattern is believable, which is a different question from
whether the code ran. A camera pointed at a wall produces a perfect,
healthy, entirely useless record, and doctor.py would call it fine.

    python audit.py                 the last 7 days
    python audit.py --days 14
    python audit.py --room "Admin Room"

Read-only. It writes nothing and changes nothing.
"""
import argparse
import os
import sys
from datetime import timedelta

import pandas as pd
import psycopg2
import yaml
from dotenv import load_dotenv

from schedule import DEFAULT_HOURS, PKT, in_operations

# A room that answers "unknown" more than this share of the time has a
# camera problem, not an occupancy pattern.
SILENT_SHARE = 0.25
# Nobody is in one room this long without leaving. Beyond it, something in
# the frame is being counted: a poster, a coat, a reflection, a screen.
STUCK_ON_HOURS = 14
# A room that is never once occupied during office hours over a week is
# either genuinely unused or is not seeing the people who use it. Both are
# worth knowing; only one is a fault.
NEVER_SEEN_DAYS = 3


def connect():
    load_dotenv()
    url = os.getenv("DASHBOARD_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        sys.exit("No DASHBOARD_DATABASE_URL in .env. This reads room"
                 " history, which the camera machine's own credential"
                 " cannot do by design.")
    return psycopg2.connect(url, sslmode=os.getenv("DB_SSLMODE", "require"),
                            connect_timeout=15)


def load(conn, days):
    since = "now() - interval '%d days'" % days
    events = pd.read_sql_query(
        "SELECT timestamp, room, status, people, ac_state FROM room_events"
        " WHERE timestamp >= %s ORDER BY room, timestamp" % since, conn)
    beats = pd.read_sql_query(
        "SELECT timestamp FROM heartbeat WHERE timestamp >= %s"
        " ORDER BY timestamp" % since, conn)
    for frame in (events, beats):
        if not frame.empty:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return events, beats


def spells(rows, until):
    """Each run of one status, as (status, people, start, end)."""
    out = []
    for i in range(len(rows)):
        row = rows.iloc[i]
        end = rows.iloc[i + 1]["timestamp"] if i + 1 < len(rows) else until
        out.append((row["status"], row["people"], row["timestamp"], end))
    return out


def coverage(beats, days, now):
    """How much of the period the loop was actually running for.

    A gap here is not a fault in the counting; it is the counting not
    happening. Reporting the rest of the audit without this would be
    grading a photograph of an empty chair.
    """
    if beats.empty:
        return 0.0, [(now - timedelta(days=days), now)]
    stamps = beats["timestamp"].tolist()
    start = now - timedelta(days=days)
    gaps, watched = [], timedelta(0)
    previous = start
    for stamp in stamps:
        if (stamp - previous) > timedelta(minutes=10):
            gaps.append((previous, stamp))
        else:
            watched += stamp - previous
        previous = stamp
    if (now - previous) > timedelta(minutes=10):
        gaps.append((previous, now))
    else:
        watched += now - previous
    whole = (now - start).total_seconds()
    return (watched.total_seconds() / whole if whole else 0.0), gaps


OUTSIDE = ("H perimeter", "Outside & plant", "Unused")


def findings(events, rooms, known, hours, now):
    """The five patterns, from the record alone.

    Separated from the printing so it can be run against a record whose
    right answer is known. These are conclusions about somebody's building,
    and "it ran without crashing" is not evidence that they are correct.
    """
    silent, stuck, never, nights, flat = [], [], [], [], []
    for room in rooms:
        mine = events[events["room"] == room]
        if mine.empty:
            never.append((room, "no events at all"))
            continue
        runs = spells(mine, now)
        total = sum((e - s).total_seconds() for _, _, s, e in runs) or 1

        unknown = sum((e - s).total_seconds() for st, _, s, e in runs
                      if st == "unknown")
        if unknown / total > SILENT_SHARE:
            silent.append((room, unknown / total * 100))

        longest = max(((e - s).total_seconds() / 3600, s, e)
                      for st, _, s, e in runs if st == "occupied") \
            if any(st == "occupied" for st, _, _, _ in runs) else None
        if longest and longest[0] >= STUCK_ON_HOURS:
            stuck.append((room, longest[0], longest[1]))

        # Seen during office hours at all?
        seen = [s for st, _, s, _ in runs
                if st == "occupied" and in_operations(s.tz_convert(PKT), hours)]
        if not seen and known.get(room, {}).get("zone") not in (
                "H perimeter", "Outside & plant", "Unused"):
            never.append((room, "never occupied in operating hours"))
        elif seen and (now - max(seen)).days >= NEVER_SEEN_DAYS:
            never.append((room, "not seen in operating hours for %d days"
                          % (now - max(seen)).days))

        # Occupied deep at night, which is either the finding or a ghost.
        dark = sum((e - s).total_seconds() / 3600 for st, _, s, e in runs
                   if st == "occupied"
                   and 1 <= s.tz_convert(PKT).hour < 5)
        if dark >= 2:
            nights.append((room, dark))

        counts = {int(p) for st, p, _, _ in runs
                  if st == "occupied" and pd.notna(p)}
        if len(counts) == 1 and sum(1 for st, _, _, _ in runs
                                    if st == "occupied") >= 8:
            flat.append((room, counts.pop()))
    return silent, stuck, never, nights, flat


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--room")
    args = ap.parse_args()

    config = yaml.safe_load(open("rooms.yaml", encoding="utf-8"))
    hours = config.get("hours") or DEFAULT_HOURS
    known = {r["name"]: r for r in config["rooms"]}

    conn = connect()
    try:
        events, beats = load(conn, args.days)
    finally:
        conn.close()

    now = pd.Timestamp.now(tz="UTC")
    print("EnergyCam audit — last %d days, to %s"
          % (args.days, now.tz_convert(PKT).strftime("%a %d %b %H:%M")))
    print("=" * 66)

    share, gaps = coverage(beats, args.days, now)
    print("\n1. WAS ANYTHING WATCHING")
    print("   the loop was running %.0f%% of the period" % (share * 100))
    if gaps:
        print("   %d gap(s); the longest:" % len(gaps))
        for a, b in sorted(gaps, key=lambda g: g[1] - g[0], reverse=True)[:5]:
            print("     %s → %s  (%.1f h)"
                  % (a.tz_convert(PKT).strftime("%a %d %b %H:%M"),
                     b.tz_convert(PKT).strftime("%a %d %b %H:%M"),
                     (b - a).total_seconds() / 3600))
        print("   Everything below is only about the time that was watched.")

    if events.empty:
        print("\nNo room events in this period. Nothing else can be said.")
        return 0

    rooms = sorted(set(events["room"]) | set(known))
    if args.room:
        rooms = [r for r in rooms if r == args.room]
        if not rooms:
            sys.exit("No such room: %s" % args.room)

    silent, stuck, never, nights, flat = findings(events, rooms, known,
                                                  hours, now)
    def section(number, title, rows, line, note):
        print("\n%d. %s" % (number, title))
        if not rows:
            print("   nothing")
            return
        for row in rows[:12]:
            print("   " + line(row))
        if len(rows) > 12:
            print("   ... and %d more" % (len(rows) - 12))
        print("   %s" % note)

    section(2, "CAMERAS NOT ANSWERING", silent,
            lambda r: "%-28s unknown %.0f%% of the time" % r,
            "A room that cannot be seen is not an empty room. Check the"
            " recorder and the channel.")

    section(3, "OCCUPIED FOR IMPLAUSIBLY LONG (likely a false person)", stuck,
            lambda r: "%-28s %.0f h from %s" % (
                r[0], r[1], r[2].tz_convert(PKT).strftime("%a %H:%M")),
            "Nobody sits that long. Run check_room.py on these when the"
            " building is empty: a poster, a coat, a screen or a"
            " reflection is being counted, and rooms.yaml takes an"
            " ignore zone for it.")

    section(4, "NEVER SEEN WITH ANYBODY IN IT (likely a missed person)",
            never, lambda r: "%-28s %s" % r,
            "Either genuinely unused, or the camera does not cover where"
            " people actually sit — which is what Admin Room turned out to"
            " be. This is the dangerous one: it reports empty, and the"
            " alert says switch the cooling off.")

    section(5, "SOMEBODY THERE BETWEEN 01:00 AND 05:00", nights,
            lambda r: "%-28s %.1f h" % r,
            "If real, this is the finding the project exists for. If not,"
            " it is the same false person as section 3. --evidence keeps"
            " a picture of each; look before believing either.")

    section(6, "THE SAME COUNT EVERY TIME", flat,
            lambda r: "%-28s always %d people" % r,
            "A real room varies. A count that never moves is usually one"
            " fixed thing being detected rather than people.")

    print("\n" + "=" * 66)
    print("Sections 3 and 6 are false people; section 4 is missed people.")
    print("Section 4 is the one worth fixing first: it is the only one that"
          " makes the system ask somebody to switch off a room in use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
