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

    print()
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
