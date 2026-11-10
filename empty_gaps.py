"""How long rooms actually sit empty, and what a threshold would have cost.

The question this answers is the one that decides the whole working-hours
policy: wait thirty minutes before doing anything about an empty room, and
how often would somebody have walked back in at minute thirty-one?

That is not a question anybody should answer from intuition, and it is not
a question about air conditioners. It is a question about how this building
is used, and the building has already written the answer down. Every empty
period since the loop started is in room_events.

    python empty_gaps.py                     every room, last 28 days
    python empty_gaps.py --room "Marketing"  one room
    python empty_gaps.py --days 60

Two numbers per candidate threshold:

    acted    how many times the room would have been dealt with
    regret   how many of those had somebody back within the grace period

A threshold with a high "acted" and a near-zero "regret" is free. One with a
high "regret" is how this system gets switched off by somebody who came back
to a warm room, which costs more than every unit it ever saved.

It needs the database, not the cameras, so it runs from anywhere.
"""
import argparse
import os
import sys
from datetime import timedelta

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from schedule import PKT, in_operations

CANDIDATES = [10, 15, 20, 30, 45, 60, 90]
# Somebody back within this of the threshold is somebody the threshold got
# wrong. Beyond it they were genuinely gone and the room was genuinely idle.
GRACE_MINUTES = 15


def connect():
    load_dotenv()
    url = os.getenv("DASHBOARD_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not in .env")
    return psycopg2.connect(url, sslmode=os.getenv("DB_SSLMODE", "require"),
                            connect_timeout=10)


def gaps(events, hours=None):
    """Every empty period: which room, when, how long, and in what hours.

    A period is only counted once it has ended. One that is still running
    has no length yet, and guessing one would quietly stretch every average
    towards whatever time the report happened to be run.
    """
    out = []
    for room, rows in events.groupby("room"):
        rows = rows.sort_values("timestamp")
        began = None
        for _, r in rows.iterrows():
            if r["status"] == "empty":
                if began is None:
                    began = r["timestamp"]
            else:
                if began is not None:
                    out.append({
                        "room": room, "began": began, "ended": r["timestamp"],
                        "minutes": (r["timestamp"] - began).total_seconds() / 60,
                        "working": in_operations(began.tz_convert(PKT), hours),
                    })
                    began = None
    return pd.DataFrame(out)


def table(periods, label, grace=GRACE_MINUTES):
    """What each candidate threshold would have done to these periods."""
    if periods.empty:
        print("  no completed empty periods %s" % label)
        return
    total = len(periods)
    print("\n  %s — %d empty periods" % (label, total))
    print("  %-10s %7s %8s %9s %14s" % ("wait", "acted", "regret",
                                        "regret %", "hours saved"))
    for t in CANDIDATES:
        acted = periods[periods["minutes"] >= t]
        if acted.empty:
            print("  %-10s %7d %8s %9s %14s" % ("%d min" % t, 0, "-", "-", "-"))
            continue
        regret = acted[acted["minutes"] < t + grace]
        # Minutes the room sat empty past the threshold: what would not have
        # been cooled for nothing. Not a saving in rupees -- that needs a
        # calibrated unit and a meter -- but it is the quantity to compare.
        saved = (acted["minutes"] - t).sum() / 60
        print("  %-10s %7d %8d %8.0f%% %13.1f"
              % ("%d min" % t, len(acted), len(regret),
                 100.0 * len(regret) / len(acted), saved))


def shape(periods):
    """Where the empty periods bunch up, which is what settles the threshold."""
    buckets = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 45), (45, 60),
               (60, 120), (120, 10 ** 9)]
    print("\n  how long they last")
    total = len(periods)
    for low, high in buckets:
        n = len(periods[(periods["minutes"] >= low)
                        & (periods["minutes"] < high)])
        bar = "█" * int(round(40.0 * n / max(1, total)))
        name = ("%d–%d min" % (low, high) if high < 10 ** 9
                else "over %d min" % low)
        print("  %-12s %5d  %-40s %4.0f%%"
              % (name, n, bar, 100.0 * n / max(1, total)))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--room", action="append")
    ap.add_argument("--grace", type=int, default=GRACE_MINUTES,
                    help="somebody back within this of the threshold counts"
                         " as the threshold getting it wrong (default %d)"
                         % GRACE_MINUTES)
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load(open("rooms.yaml", encoding="utf-8"))
    hours = cfg.get("hours")
    cooled = {r["name"] for r in cfg["rooms"]
              if r.get("ac") in ("visible", "hidden")
              and r.get("alert") != "never"}

    conn = connect()
    try:
        events = pd.read_sql_query(
            "SELECT timestamp, room, status FROM room_events"
            " WHERE timestamp >= now() - interval '%d days'"
            " ORDER BY room, timestamp" % args.days, conn)
    finally:
        conn.close()
    if events.empty:
        sys.exit("No events in the last %d days. The loop has to have been"
                 " running for this to answer anything." % args.days)
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True)

    span = (events["timestamp"].max() - events["timestamp"].min())
    print(">> %d events over %.1f days, %d rooms"
          % (len(events), span.total_seconds() / 86400,
             events["room"].nunique()))

    periods = gaps(events, hours)
    if args.room:
        wanted = {n.lower() for n in args.room}
        periods = periods[periods["room"].str.lower().isin(wanted)]
    else:
        # Only rooms where a threshold would do anything. A corridor's empty
        # periods are not a question anybody is asking.
        periods = periods[periods["room"].isin(cooled)]
    if periods.empty:
        sys.exit("No completed empty periods to look at yet.")

    print(">> %d completed empty periods in %d room(s) with a unit"
          % (len(periods), periods["room"].nunique()))
    print(">> \"regret\" means somebody was back within %d min of the"
          " threshold" % args.grace)

    shape(periods)
    table(periods[periods["working"]], "inside operating hours", args.grace)
    table(periods[~periods["working"]], "outside operating hours", args.grace)

    print("\n  by room, inside operating hours")
    print("  %-26s %7s %9s %9s" % ("room", "periods", "median", "under 15m"))
    day = periods[periods["working"]]
    for room, rows in sorted(day.groupby("room"),
                             key=lambda kv: -len(kv[1])):
        quick = len(rows[rows["minutes"] < 15])
        print("  %-26s %7d %8.0fm %8.0f%%"
              % (room[:26], len(rows), rows["minutes"].median(),
                 100.0 * quick / len(rows)))

    print("\n>> Read it like this: pick the shortest wait whose regret column"
          "\n>> is near zero. That is the building telling you its own"
          "\n>> threshold, which is worth more than anybody's judgement about"
          "\n>> how long a lunch break is.")


if __name__ == "__main__":
    main()
