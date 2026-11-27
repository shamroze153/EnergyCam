"""The attendance report's daily CSV into people/attendance/ (local only).

Shamroze, 27 Nov 2026: the "last 24 hour attendance" report (Data Studio)
exports the machines' punches -- id, date_time ("Nov 26, 2026, 10:28:38
AM"), machine_id, machine_location, pin (the employee code), status (0
in, 1 out) -- the same punches as HR's export under other names. This
writes them in the export's own columns, so attendance.load() reads both
and drops a punch seen twice (by its id).

    python attendance_import.py <downloaded.csv> [--keep]

The download is moved, not copied (it is employee codes and times: it
lives in people/attendance/ only, git-ignored); --keep leaves it.
"""
import csv
import os
import sys
from datetime import datetime

FOLDER = os.path.join("people", "attendance")
COLS = ["id", "emp_code", "date_time", "machine_id", "machine_location",
        "status"]


def parse_time(text):
    """"Nov 26, 2026, 10:28:38 AM" (any space) -> "2026-11-26 10:28:38"."""
    t = " ".join(str(text).replace(" ", " ").replace("\xa0", " ")
                 .replace("â€¯", " ").split())
    for fmt in ("%b %d, %Y, %I:%M:%S %p", "%Y-%m-%d %H:%M:%S",
                "%b %d, %Y, %I:%M %p"):
        try:
            return datetime.strptime(t, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def convert(rows):
    """Report rows -> export rows (COLS); a row whose time cannot be read
    is left out. Returns (rows, first, last)."""
    out = []
    for r in rows:
        when = parse_time(r.get("date_time", ""))
        if not when:
            continue
        out.append({"id": r.get("id", ""), "emp_code": r.get("pin", ""),
                    "date_time": when,
                    "machine_id": r.get("machine_id", ""),
                    "machine_location": r.get("machine_location", ""),
                    "status": r.get("status", "")})
    times = sorted(r["date_time"] for r in out)
    return out, (times[0] if times else None), (times[-1] if times else None)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    src = argv[1]
    with open(src, encoding="utf-8-sig", errors="replace") as fh:
        rows, first, last = convert(csv.DictReader(fh))
    if not rows:
        print("no punches read from", src)
        return 1
    os.makedirs(FOLDER, exist_ok=True)
    name = "live_%s_to_%s.csv" % (first[:16].replace(" ", "_").replace(":", ""),
                                  last[:16].replace(" ", "_").replace(":", ""))
    dst = os.path.join(FOLDER, name)
    with open(dst, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, COLS)
        w.writeheader()
        w.writerows(rows)
    if "--keep" not in argv:
        os.remove(src)
    print("%d punches, %s to %s -> %s" % (len(rows), first, last, dst))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
