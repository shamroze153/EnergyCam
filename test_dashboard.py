"""Check the dashboard holds together, without a database or a browser.

Written after a refactor quietly deleted nine functions. The edit replaced
everything between two markers, the file still parsed, and the page only fell
over when somebody opened it -- on a name that had been fine for a week.

A parse is not a check. Python resolves a global when the line runs, so a
missing function is invisible until the view that needs it is opened, and the
views that break are the ones nobody opens on the way past.

    python test_dashboard.py
"""
import ast
import builtins
import sys
import types

import pandas as pd

STUBS = {
    "streamlit": None,          # built below
    "streamlit_autorefresh": types.SimpleNamespace(st_autorefresh=lambda **k: None),
    "psycopg2": types.SimpleNamespace(Error=Exception, connect=None),
}
FAILURES = []


def check(label, ok, detail=""):
    print("%-4s %s%s" % ("OK" if ok else "FAIL", label,
                         "" if ok else "  -> %s" % detail))
    if not ok:
        FAILURES.append(label)


def install_stubs():
    class FakeStreamlit:
        secrets = {}

        def set_page_config(self, **kw):
            pass

        def cache_data(self, **kw):
            return lambda fn: fn

    express = types.ModuleType("plotly.express")
    express.bar = lambda *a, **k: None
    plotly = types.ModuleType("plotly")
    plotly.express = express
    STUBS["streamlit"] = FakeStreamlit()
    for name, module in list(STUBS.items()) + [("plotly", plotly),
                                               ("plotly.express", express)]:
        sys.modules.setdefault(name, module)


def load_helpers(source):
    """Run everything above the layout, which is the part with no side effects."""
    head = source.split("# " + "-" * 74)[0]
    namespace = {}
    exec(compile(head, "rooms_dashboard.py", "exec"), namespace)
    return namespace


def every_name_resolves(source, namespace):
    """The check that would have caught the deletion.

    Collects every name the file binds -- imports, assignments, functions,
    their arguments, comprehension and lambda variables, except-as names --
    and every name it reads, and reports anything read but never bound.
    """
    tree = ast.parse(source)
    known = set(namespace) | set(dir(builtins)) | {
        "st", "pd", "np", "os", "time", "px", "psycopg2", "yaml", "quote",
        "timedelta", "timezone"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            known.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            known.add(node.name)
            args = node.args
            for arg in (list(args.args) + list(args.kwonlyargs)
                        + list(args.posonlyargs)):
                known.add(arg.arg)
            for extra in (args.vararg, args.kwarg):
                if extra:
                    known.add(extra.arg)
        elif isinstance(node, ast.Lambda):
            args = node.args
            for arg in (list(args.args) + list(args.kwonlyargs)
                        + list(args.posonlyargs)):
                known.add(arg.arg)
        elif isinstance(node, ast.ClassDef):
            known.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                known.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            known.add(node.name)
    read = {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return sorted(read - known)


def defined_before_use(source):
    """A function called at module level above its own definition.

    Read from the syntax tree, not by searching the text: the first attempt
    matched the name inside a comment that mentioned it, and a check that
    cries wolf gets switched off. Only calls that actually run at import time
    count -- a call inside a function body is fine wherever it sits.
    """
    tree = ast.parse(source)
    defined = {node.name: node.lineno for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    called = {}
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
            continue                      # bodies run later, not now
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.setdefault(node.func.id, node.lineno)
    return ["%s defined line %d, called line %d" % (name, defined[name], line)
            for name, line in called.items()
            if name in defined and defined[name] > line]


def main():
    install_stubs()
    source = open("rooms_dashboard.py").read()

    try:
        namespace = load_helpers(source)
        check("the helper half of the file imports", True)
    except Exception as e:
        check("the helper half of the file imports", False, repr(e))
        return 1

    unresolved = every_name_resolves(source, namespace)
    check("every name the file reads is bound somewhere", not unresolved,
          ", ".join(unresolved))

    late = defined_before_use(source)
    check("nothing is called above where it is defined", not late,
          "; ".join(late))

    wanted = ["figure_row", "money", "wasted_minutes", "against_baseline",
              "hour_pattern", "pattern_row", "settles_at", "daily_spans",
              "day_calendar", "status_row", "ac_pill", "room_card",
              "header_band", "money_strip", "wordmark", "grade",
              "show_room_day", "show_arrivals", "show_cameras", "show_stills",
              "show_numbers"]
    missing = [n for n in wanted if "def %s(" % n not in source]
    check("every view and helper is still here", not missing,
          ", ".join(missing))

    # Both palettes have to carry every key, or a theme switch dies on a
    # KeyError the first time somebody picks the other one.
    themes = namespace["THEMES"]
    keys = {name: set(t) for name, t in themes.items()}
    check("both palettes carry the same keys",
          keys["dark"] == keys["light"],
          str(keys["dark"] ^ keys["light"]))
    levels = {name: set(t["ink"]) for name, t in themes.items()}
    check("both palettes carry the same levels",
          levels["dark"] == levels["light"],
          str(levels["dark"] ^ levels["light"]))

    # And every level the grader can return must exist in the palette.
    produced = {"Red", "Amber", "Green", "Cool", "Fault"}
    check("every level the grader returns has a colour",
          produced <= levels["dark"], str(produced - levels["dark"]))
    check("every level has a place in the sort order",
          produced <= set(namespace["RANK"]),
          str(produced - set(namespace["RANK"])))

    # A room can be drawn in either theme without raising.
    rooms = namespace["load_rooms_config"]()
    now = pd.Timestamp("2026-11-06 13:00", tz="UTC")
    for mode in ("dark", "light"):
        namespace["use_theme"](mode)
        try:
            for level in produced:
                row = rooms.iloc[0].to_dict()
                row.update(dict(status="empty", people=0, ac_state=None,
                                level=level, headline="Empty 14 min",
                                sub="", age="1 min ago",
                                slots=["empty"] * 96, empty_since=now,
                                occupied_since=pd.NaT, timestamp=now,
                                empty_after=45))
                namespace["status_row"](pd.Series(row))
                namespace["ac_pill"](pd.Series(row))
            namespace["wordmark"](mode)
            check("a room draws in %s" % mode, True)
        except Exception as e:
            check("a room draws in %s" % mode, False, repr(e))

    print("-- the campus view builds from real-shaped data")
    # The layout was settled from mock-ups; what has to be checked is the
    # join between the database and that layout. A page that silently grades
    # every room the same looks perfectly fine and says nothing.
    import json

    import campus_view

    now = pd.Timestamp("2026-11-05 20:15", tz="UTC")

    def ago(mins):
        return now - pd.Timedelta(minutes=mins)

    spec = [
        ("Marketing",   True,  True,  "empty",    0, 74,  "on"),
        ("Wellows",     True,  True,  "empty",    0, 96,  "off"),
        ("AutoOS",      True,  True,  "empty",    0, 130, "off"),
        ("Admin Room",  True,  True,  "occupied", 2, 0,   "on"),
        ("Old Finance", True,  True,  "occupied", 1, 0,   "off"),
        ("Board Room",  True,  True,  "empty",    0, 43,  None),
        ("UPS Room",    True,  False, "empty",    0, 200, "on"),
        ("H Stairs",    False, True,  "occupied", 1, 0,   None),
        ("P2 Parking",  False, True,  "empty",    0, 88,  None),
        ("Dead Camera", False, True,  "unknown",  0, 0,   None),
    ]
    df = pd.DataFrame([{
        "room": r, "zone": "Offices", "campus": "140-H", "has_unit": u,
        "alerts": a,
        "caption": "unit in frame" if u else "nothing to switch off",
        "ac": "visible" if u else "none",
        "empty_after": 45 if u else None,
        "status": s, "people": p,
        "empty_since": None if s != "empty" else ago(e),
        "ac_state": ac, "timestamp": ago(1),
        "occupied_since": ago(30) if s == "occupied" else None,
    } for r, u, a, s, p, e, ac in spec])

    # Wellows was seen running after it emptied and off later: somebody went.
    # AutoOS was off the whole time, so nobody did, and it must not be
    # credited with a visit that never happened.
    ev = []
    for r, u, a, s, p, e, ac in spec:
        if r == "Wellows":
            ev += [{"timestamp": ago(96), "room": r, "status": "empty",
                    "people": 0, "ac_state": "on"},
                   {"timestamp": ago(23), "room": r, "status": "empty",
                    "people": 0, "ac_state": "off"}]
        elif r == "AutoOS":
            ev += [{"timestamp": ago(130), "room": r, "status": "empty",
                    "people": 0, "ac_state": "off"}]
        else:
            ev += [{"timestamp": ago(max(e, 1) if s == "empty" else 240),
                    "room": r, "status": s, "people": p, "ac_state": ac}]
    recent = pd.DataFrame(ev)
    recent["timestamp"] = pd.to_datetime(recent["timestamp"], utc=True)

    rows = campus_view.rows(df, recent, now, namespace["grade"], namespace["spell"],
                            namespace["minutes_since"], None)
    by = {r["name"]: r for r in rows}
    check("every room comes through", len(rows) == len(spec))
    check("empty and cooling wants doing", by["Marketing"]["grade"] == "act")
    check("somebody went and switched Wellows off",
       by["Wellows"]["grade"] == "sorted")
    check("and the note says when",
       bool(by["Wellows"]["note"]) and "switched off" in by["Wellows"]["note"])
    check("a unit off all along is not credited with a visit",
       by["AutoOS"]["grade"] == "good" and by["AutoOS"]["note"] is None)
    check("a room in use is not flagged", by["Admin Room"]["grade"] == "busy")
    check("sitting with the unit off is a comfort problem",
       by["Old Finance"]["grade"] == "cold")
    check("an uncalibrated unit is unknown, not off",
       by["Board Room"]["grade"] == "unknown")
    # The distinction that matters: a camera that did not answer is not a
    # unit nobody has calibrated. Conflating them hides a dead camera behind
    # a sentence about air conditioners, and sends somebody to a room when
    # what needs looking at is a recorder.
    check("a room no camera answered for is silent, not unknown",
       by["Dead Camera"]["grade"] == "silent")
    check("and it is not reported as empty",
       by["Dead Camera"]["state"] == "unknown")
    check("a room cooled on purpose is never flagged",
       by["UPS Room"]["grade"] == "onpurpose")

    # Asked for twice: a room with no unit carries no air conditioner
    # anywhere on the page, not even a question mark.
    for name in ("H Stairs", "P2 Parking", "Dead Camera"):
        check("%s: no unit, no AC state" % name,
           by[name]["unit"] is False and by[name]["ac"] is None)
    check("and no such room is graded as a unit",
       {by[n]["grade"] for n in ("H Stairs", "P2 Parking")}
       <= {"busy", "watch"})

    check("the day strip has one mark per quarter hour",
       len(by["Marketing"]["slots"]) == 64)
    check("first seen never comes after last seen",
       all(r["first"] is None or r["last"] is None or r["first"] <= r["last"]
           for r in rows))

    html = campus_view.page(rows, {"campus": "140-H", "live": "live",
                                   "healthy": True, "stake": "Rs 0",
                                   "stake_label": "x", "saved": "Rs 0",
                                   "saved_label": "y", "when": "now"})
    check("no placeholder is left in the page",
       "__DATA__" not in html and "__BANNER__" not in html)
    check("and its data is valid JSON",
       bool(json.loads(html.split("const PAGE = ", 1)[1]
                       .split(";\nconst ROOMS", 1)[0].replace("<\\/", "</"))))

    print()
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
