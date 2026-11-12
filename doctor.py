"""Check everything that can be checked before walking the building.

A morning is lost the same way every time: somebody drives in, plugs the
cable, starts the loop, and finds out that a password is missing or a table
was never created or the disk is full. All of that is knowable from a desk.

    python doctor.py            everything that needs no camera
    python doctor.py --cameras  and then try every recorder

Nothing here changes anything. It reads, it counts, and it says what it
found, so running it costs nothing but the time it takes.
"""
import argparse
import os
import shutil
import sys

PROBLEMS = []
WARNINGS = []


def ok(label, detail=""):
    print("  ✓ %s%s" % (label, "  %s" % detail if detail else ""))


def bad(label, fix):
    print("  ✗ %s" % label)
    print("      %s" % fix)
    PROBLEMS.append(label)


def warn(label, detail=""):
    print("  ! %s%s" % (label, "  %s" % detail if detail else ""))
    WARNINGS.append(label)


def section(title):
    print("\n%s" % title)


def check_files():
    section("Files")
    for name in ("rooms.yaml", "room_loop.py", "rooms_dashboard.py",
                 "campus_view.html"):
        if os.path.exists(name):
            ok(name)
        else:
            bad("%s is missing" % name,
                "Run this from the project folder, and run pull.bat.")
    if os.path.exists(".env"):
        ok(".env")
    else:
        bad(".env is missing",
            "It holds the recorder logins and the database URL, and it is"
            " deliberately not in git. Copy it from the machine that has it.")


def check_config():
    section("rooms.yaml")
    try:
        import yaml
        cfg = yaml.safe_load(open("rooms.yaml", encoding="utf-8"))
    except Exception as e:                                  # noqa: BLE001
        bad("rooms.yaml will not parse (%s)" % e,
            "Look at the line the message names. A tab instead of spaces is"
            " the usual cause.")
        return None
    rooms = cfg.get("rooms") or []
    recorders = cfg.get("recorders") or {}
    cameras = sum(len(r.get("cameras") or r.get("channels") or [])
                  for r in rooms)
    watched = [r for r in rooms if r.get("watch", True)]
    ok("%d rooms, %d cameras, %d recorders"
       % (len(rooms), cameras, len(recorders)))
    if len(watched) < len(rooms):
        ok("%d room(s) deliberately not watched"
           % (len(rooms) - len(watched)))

    alertable = [r for r in rooms
                 if r.get("ac") in ("visible", "hidden")
                 and r.get("alert") != "never" and r.get("watch", True)]
    ok("%d room(s) can raise an air-conditioner check" % len(alertable))

    unsaid = [r["name"] for r in rooms if not r.get("meter")]
    if unsaid:
        warn("%d room(s) not assigned to a meter" % len(unsaid),
             "their hours cannot be set against either meter")
    else:
        ok("every room is assigned to a meter")

    unknown = [r["name"] for r in rooms if r.get("ac") == "unknown"]
    if unknown:
        warn("%d room(s) still say ac: unknown" % len(unknown),
             ", ".join(unknown[:4]))
    return cfg


def check_calibration(cfg):
    section("Calibration")
    if not os.path.exists("ac_units.yaml"):
        warn("nothing is calibrated yet",
             "every unit reads as unknown, which is not the same as off")
        return
    import yaml
    units = (yaml.safe_load(open("ac_units.yaml", encoding="utf-8"))
             or {}).get("rooms", {}) or {}
    rooms = {r["name"]: r for r in (cfg or {}).get("rooms", [])}
    declared = sum(int(r.get("ac_count", 1) or 1) for r in rooms.values()
                   if r.get("ac") in ("visible", "hidden")
                   and r.get("alert") != "never" and r.get("watch", True))
    measured = sum(len(c.get("units") or []) for c in units.values())
    ok("%d of about %d units measured" % (measured, declared))
    for name, cfg_room in sorted(units.items()):
        room = rooms.get(name)
        if room is None:
            bad("ac_units.yaml has %r, which is not a room" % name,
                "Check the spelling against rooms.yaml.")
            continue
        cams = room.get("cameras") or [{"recorder": room["recorder"],
                                        "channel": c}
                                       for c in room["channels"]]
        pair = (cfg_room.get("recorder", room.get("recorder")),
                cfg_room.get("channel"))
        if pair not in [(c["recorder"], c["channel"]) for c in cams]:
            bad("%s is calibrated on %s channel %s, which it is not watched on"
                % (name, pair[0], pair[1]),
                "The loop only reads a unit on a channel it visits, so this"
                " would never be read. Re-run calibrate_room.py.")
        for unit in cfg_room.get("units", []):
            if not unit.get("anchor"):
                warn("%s has no anchor" % name,
                     "a nudged camera would read it as off for ever;"
                     " re-run calibrate_room.py --live --replace")


def check_env():
    section("Logins and the database")
    from dotenv import load_dotenv
    load_dotenv()
    import yaml
    cfg = yaml.safe_load(open("rooms.yaml", encoding="utf-8"))
    for key, rec in (cfg.get("recorders") or {}).items():
        names = [rec.get("user_env"), rec.get("pass_env")]
        missing = [n for n in names if n and not os.getenv(n)]
        if missing:
            bad("%s has no login (%s not in .env)" % (key, ", ".join(missing)),
                "Add the view-only account, not the administrator one.")
        else:
            ok("%s login present" % key)

    if not os.getenv("DATABASE_URL"):
        bad("DATABASE_URL is not in .env",
            "The loop cannot record anything without it.")
        return
    ok("DATABASE_URL present")

    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("DATABASE_URL"),
                                sslmode=os.getenv("DB_SSLMODE", "require"),
                                connect_timeout=10)
    except Exception as e:                                  # noqa: BLE001
        bad("the database will not answer (%s)" % type(e).__name__,
            "Check the internet connection. This does not need the camera"
            " cable.")
        return
    try:
        cur = conn.cursor()
        for table, why in (("room_events", "sql/04_rooms.sql"),
                           ("heartbeat", "sql/01_schema.sql"),
                           ("meter_readings", "sql/06_meters.sql")):
            cur.execute("SELECT to_regclass(%s)", ("public." + table,))
            if cur.fetchone()[0]:
                cur.execute("SELECT count(*) FROM %s" % table)
                ok("%s exists" % table, "%s rows" % cur.fetchone()[0])
            else:
                warn("%s does not exist" % table,
                     "an administrator runs %s once" % why)
        cur.execute("SELECT max(timestamp) FROM heartbeat")
        beat = cur.fetchone()[0]
        if beat is None:
            warn("the loop has never reported")
        else:
            import datetime
            age = (datetime.datetime.now(datetime.timezone.utc)
                   - beat).total_seconds() / 60
            if age < 5:
                ok("the loop is running", "last beat %.0f min ago" % age)
            else:
                warn("the loop last reported %.0f minutes ago" % age,
                     "nothing is being recorded while it is down")
        cur.close()
    finally:
        conn.close()


def check_alerts():
    section("Alerts")
    import alerts
    if alerts.configured():
        ok("alerts can be sent", "to %s" % ", ".join(alerts.recipients()))
    else:
        warn("alerts are not configured",
             "missing %s; the loop will print what it would have sent"
             % alerts.why_not_configured())


def check_machine():
    section("This machine")
    free = shutil.disk_usage(".").free / 1e9
    if free < 2:
        bad("%.1f GB free" % free,
            "The loop writes frames and the model needs room. Clear space.")
    else:
        ok("%.1f GB free" % free)
    from privacy_blur import DETECTOR
    if os.path.exists(DETECTOR):
        ok("the detector's weights are here", DETECTOR)
    else:
        warn("%s is not here" % DETECTOR,
             "it downloads on the first run (22 MB), which needs the"
             " internet")
    for folder, limit in (("evidence", 400), ("frames", None)):
        if os.path.isdir(folder):
            n = len([f for f in os.listdir(folder) if f.endswith(".jpg")])
            size = sum(os.path.getsize(os.path.join(folder, f))
                       for f in os.listdir(folder)
                       if f.endswith(".jpg")) / 1e6
            note = "%d pictures, %.0f MB" % (n, size)
            if limit and n > limit * 1.2:
                warn("%s/ is above its limit" % folder, note)
            else:
                ok("%s/" % folder, note + " — not blurred, keep local")


def check_cameras(cfg):
    section("Recorders")
    from dotenv import load_dotenv
    load_dotenv()
    from room_loop import (is_private, load_rooms, recorder_login, wants_main,
                           widen)
    from test_camera import build_url, grab
    recorders, rooms = load_rooms("rooms.yaml")
    seen = {}
    for room in rooms:
        # A room in its private hours (the 141 gym, 15:00-20:00) is never the
        # camera a recorder is tested on.
        if is_private(room.private):
            continue
        for rec_name, channel in room.cameras:
            seen.setdefault(rec_name, (room, channel))
    for key, (room, channel) in sorted(seen.items()):
        rec = recorders[key]
        try:
            user, password = recorder_login(key, rec)
        except SystemExit:
            bad("%s: no login" % key, "add it to .env")
            continue
        url = build_url(rec["host"], channel, user, password,
                        wants_main(room, rec),
                        rec.get("brand", "hikvision"))
        frame, why = grab(url, max_seconds=8.0)
        if frame is None:
            bad("%s (%s) did not answer: %s" % (key, rec["host"], why),
                "Is the cable in, and is this machine on that network?")
        else:
            # What the loop will actually work on. dvr2 and xvr3 send
            # 960x1080 anamorphic, which is widened to 1920x1080 before
            # anything looks at it; judging the raw size would condemn the
            # two recorders that are fine.
            wide = widen(frame)
            note = "%dx%d from channel %d" % (wide.shape[1], wide.shape[0],
                                              channel)
            if wide.shape[:2] != frame.shape[:2]:
                note += " (sent %dx%d, widened)" % (frame.shape[1],
                                                    frame.shape[0])
            ok("%s (%s)" % (key, rec["host"]), note)
            if wide.shape[1] < 1000:
                warn("  %s is only %d wide" % (room.name, wide.shape[1]),
                     "a unit's display cannot be read at that size;"
                     " this room needs stream: main in rooms.yaml")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cameras", action="store_true",
                    help="also try each recorder (needs the cable)")
    args = ap.parse_args()

    check_files()
    cfg = check_config()
    if cfg:
        check_calibration(cfg)
    check_env()
    check_alerts()
    check_machine()
    if args.cameras:
        check_cameras(cfg)

    print()
    if PROBLEMS:
        print("%d thing(s) will stop the loop:" % len(PROBLEMS))
        for p in PROBLEMS:
            print("   - %s" % p)
    if WARNINGS:
        print("%d thing(s) worth knowing:" % len(WARNINGS))
        for w in WARNINGS:
            print("   - %s" % w)
    if not PROBLEMS and not WARNINGS:
        print("Nothing to fix.")
    elif not PROBLEMS:
        print("\nNothing will stop the loop.")
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    sys.exit(main())
