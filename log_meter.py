"""Write down what the two K-Electric meters said.

Thirty seconds a day, and it is the thing that turns the money on the
dashboard from an assumption into a measurement. Everything there now rests
on two guesses -- 1.2 kW per unit, Rs 55 per kWh -- and the page is careful
to call the result "at stake" rather than a bill. A month of readings beside
the hours rooms sat empty and cooled replaces the first guess; the monthly
bills replace the second.

    python log_meter.py gf 48231                 the number on the meter
    python log_meter.py first 142 --units        units for the day instead
    python log_meter.py gf 48231 --temp 34       with the day's high
    python log_meter.py --show                   the last fortnight
    python log_meter.py --bill gf 4120 238000 --from 2026-10-01 --to 2026-10-31

Either number is fine. Give the cumulative figure off the meter's face and
the daily units are worked out from the one before; give the units straight
from the K-Electric app and they are taken as they are. Which one you gave is
kept, so a mistyped digit can be found later rather than quietly becoming a
day the building used four thousand units.

Take it at roughly the same time each day. A day here runs from one reading
to the next rather than from midnight, which is the right way round: the
night, the part worth measuring, then sits inside one reading instead of
being split across two.
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone

import psycopg2
from dotenv import load_dotenv

from schedule import PKT

# What the two meters are called, and the short names worth typing.
ALIASES = {
    "gf": "gf_basement", "ground": "gf_basement", "basement": "gf_basement",
    "gf_basement": "gf_basement",
    "first": "first_cafe", "1st": "first_cafe", "cafe": "first_cafe",
    "first_cafe": "first_cafe",
}
# A day's consumption outside this is almost certainly a typo, and a typo
# here is worse than a missing day: it goes into an average and quietly
# moves every figure built on it.
SANE_UNITS = (1, 3000)


def connect():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not in .env")
    return psycopg2.connect(url, sslmode=os.getenv("DB_SSLMODE", "require"),
                            connect_timeout=10)


def meter_of(name):
    code = ALIASES.get(name.strip().lower())
    if not code:
        sys.exit("I do not know a meter called %r. Use gf or first." % name)
    return code


def previous(cur, code, before):
    cur.execute("SELECT taken, reading FROM meter_readings"
                " WHERE meter = %s AND reading IS NOT NULL AND taken < %s"
                " ORDER BY taken DESC LIMIT 1", (code, before))
    return cur.fetchone()


def add_reading(args):
    code = meter_of(args.meter)
    taken = (datetime.fromisoformat(args.at).replace(tzinfo=PKT)
             if args.at else datetime.now(PKT))
    conn = connect()
    try:
        cur = conn.cursor()
        reading = None if args.units else args.value
        units = args.value if args.units else None

        if reading is not None:
            last = previous(cur, code, taken)
            if last:
                when, before = last
                gap = (taken - when).total_seconds() / 3600.0
                step = float(reading) - float(before)
                if step < 0:
                    sys.exit(
                        ">> %s is LOWER than the last reading of %s taken %s."
                        "\n   A meter does not count backwards, so either a"
                        " digit is wrong or the meter was replaced.\n   If it"
                        " really was replaced, record today with --units"
                        " instead and carry on from tomorrow."
                        % (reading, before, when.astimezone(PKT)
                           .strftime("%d %b %H:%M")))
                units = step
                print(">> %.1f units since %s (%.1f hours)"
                      % (step, when.astimezone(PKT).strftime("%d %b %H:%M"),
                         gap))
            else:
                print(">> first reading for this meter, so there is nothing"
                      " to measure against yet. Tomorrow's gives the first"
                      " day's units.")

        if units is not None and not (SANE_UNITS[0] <= float(units)
                                      <= SANE_UNITS[1]):
            print(">> %.1f units for one day is outside %d-%d, which usually"
                  " means a digit is wrong." % (float(units), *SANE_UNITS))
            if input(">> write it anyway? [y/N] ").strip().lower() not in \
                    ("y", "yes"):
                sys.exit(">> nothing written")

        cur.execute(
            "INSERT INTO meter_readings (meter, taken, reading, units,"
            " max_temp, note) VALUES (%s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (meter, taken) DO UPDATE SET reading ="
            " EXCLUDED.reading, units = EXCLUDED.units,"
            " max_temp = EXCLUDED.max_temp, note = EXCLUDED.note",
            (code, taken, reading, units, args.temp, args.note))
        conn.commit()
        print(">> %s, %s: %s" % (code, taken.strftime("%d %b %H:%M"),
                                 "reading %s" % reading if reading is not None
                                 else "%s units" % units))

        # The other meter, if it has not been done today. Two meters is
        # exactly the number where one gets forgotten.
        other = "first_cafe" if code == "gf_basement" else "gf_basement"
        cur.execute("SELECT max(taken) FROM meter_readings WHERE meter = %s",
                    (other,))
        last = cur.fetchone()[0]
        if last is None or (taken - last).total_seconds() > 20 * 3600:
            print(">> %s has not been read today. Do it while you are there."
                  % other)
        cur.close()
    finally:
        conn.close()


def add_bill(args):
    code = meter_of(args.meter)
    conn = connect()
    try:
        cur = conn.cursor()
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
        cur.execute(
            "INSERT INTO meter_bills (meter, period_start, period_end, units,"
            " amount_rs, note) VALUES (%s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (meter, period_start, period_end) DO UPDATE SET"
            " units = EXCLUDED.units, amount_rs = EXCLUDED.amount_rs,"
            " note = EXCLUDED.note",
            (code, start, end, args.units_billed, args.amount, args.note))
        conn.commit()
        rate = float(args.amount) / float(args.units_billed)
        print(">> %s, %s to %s: %s units, Rs %s"
              % (code, start, end, args.units_billed, args.amount))
        print(">> that is Rs %.2f per unit on this bill." % rate)
        print(">> rooms.yaml assumes Rs %s. %s"
              % (assumed_tariff(),
                 "Close enough." if abs(rate - assumed_tariff()) < 5
                 else "Worth changing the assumption to match."))
        cur.close()
    finally:
        conn.close()


def assumed_tariff(path="rooms.yaml"):
    import yaml
    return float((yaml.safe_load(open(path)) or {})
                 .get("assumptions", {}).get("tariff_rs_per_kwh", 0) or 0)


def show(args):
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT meter, taken, reading, units, max_temp FROM meter_readings"
            " WHERE taken >= %s ORDER BY taken DESC, meter",
            (datetime.now(timezone.utc) - timedelta(days=args.days),))
        rows = cur.fetchall()
        if not rows:
            print(">> nothing recorded in the last %d days." % args.days)
            return
        print("%-12s %-16s %10s %9s %7s" % ("meter", "taken", "reading",
                                            "units", "max C"))
        for meter, taken, reading, units, temp in rows:
            print("%-12s %-16s %10s %9s %7s"
                  % (meter, taken.astimezone(PKT).strftime("%d %b %H:%M"),
                     "" if reading is None else "%.0f" % reading,
                     "" if units is None else "%.1f" % units,
                     "" if temp is None else "%.0f" % temp))
        cur.execute("SELECT meter, period_start, period_end, units, amount_rs"
                    " FROM meter_bills ORDER BY period_end DESC LIMIT 6")
        bills = cur.fetchall()
        if bills:
            print("\nbills")
            for meter, a, b, units, amount in bills:
                print("  %-12s %s to %s  %8.0f units  Rs %10.0f  "
                      "(Rs %.2f/unit)"
                      % (meter, a, b, units, amount, float(amount)/float(units)))
        cur.close()
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("meter", nargs="?", help="gf or first")
    ap.add_argument("value", nargs="?", type=float,
                    help="the meter's reading, or units with --units")
    ap.add_argument("amount", nargs="?", type=float,
                    help="with --bill: the rupees on the bill")
    ap.add_argument("--units", action="store_true",
                    help="the number given is units for the day, not the"
                         " cumulative reading")
    ap.add_argument("--temp", type=float,
                    help="the day's high in C. Weather drives an air"
                         " conditioner harder than people do, so without this"
                         " a cool week looks like a saving")
    ap.add_argument("--at", help="when it was read, YYYY-MM-DDTHH:MM"
                                 " (default: now)")
    ap.add_argument("--note")
    ap.add_argument("--show", action="store_true", help="the last fortnight")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--bill", action="store_true",
                    help="record a monthly bill instead of a reading")
    ap.add_argument("--from", dest="start", help="with --bill")
    ap.add_argument("--to", dest="end", help="with --bill")
    args = ap.parse_args()

    if args.show:
        return show(args)
    if args.bill:
        if not (args.meter and args.value and args.amount
                and args.start and args.end):
            sys.exit("--bill needs: meter units rupees --from DATE --to DATE")
        args.units_billed = args.value
        return add_bill(args)
    if not (args.meter and args.value is not None):
        ap.print_help()
        sys.exit(1)
    return add_reading(args)


if __name__ == "__main__":
    main()
