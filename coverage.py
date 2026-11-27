"""How many of each campus's desk staff a desk camera measures (Shamroze,
27 Nov: "70 ko 157 le jaate hain, 17 ko 261 -- 100% ... workforce staff
desk par nahi baithte", with the count as it rises).

    python coverage.py            -> the counts, campus by campus

Desk staff: everybody of the campus by the attendance machines (at least
half their punches there) in the directory, less the workforce
(productivity_view.WORKFORCE: janitorial, office boys, gate and security,
valet, technicians). Measured: their employee ID is on a named desk of
that campus's cameras. Counts only -- never a name.
"""
import sys

import attendance
import desks_data
import productivity_view as prv

CAMPUSES = (("140-H", "140-H", desks_data.CAMPUS_140),
            ("141-C/D", "141", desks_data.CAMPUS_141))


def counts(data=None, names=None, roster=None):
    """[{campus, staff, workforce, measured, not_measured}] -- `measured`
    the desk staff whose ID is on a named desk of the campus's cameras."""
    data = attendance.load() if data is None else data
    names = desks_data.load_desk_names() if names is None else names
    roster = {attendance.code(r["employee_id"]): r
              for r in (roster or desks_data.load_roster())}
    out = []
    for label, prefix, recs in CAMPUSES:
        rows = [r for r in attendance.summary(prefix, data=data)
                if r["eid"] in roster]
        crew = {r["eid"] for r in rows
                if prv.crew_group(roster[r["eid"]].get("designation"))}
        staff = {r["eid"] for r in rows} - crew
        named = {attendance.code(eid) for code, (eid, _) in names.items()
                 if code.split(".")[0] in recs}
        measured = staff & named
        out.append({"campus": label, "staff": len(staff),
                    "workforce": len(crew), "measured": len(measured),
                    "not_measured": len(staff - measured)})
    return out


def main(argv):
    for c in counts():
        print("%-8s desk staff %3d, measured by desk camera %3d (%d%%), "
              "left %3d; workforce apart %d"
              % (c["campus"], c["staff"], c["measured"],
                 round(100.0 * c["measured"] / c["staff"]) if c["staff"]
                 else 0, c["not_measured"], c["workforce"]))


if __name__ == "__main__":
    main(sys.argv)
