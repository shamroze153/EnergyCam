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


def check_guard(namespace):
    """The door that has to exist before this page leaves the office WiFi.

    What is behind it is not a chart of kilowatts: it is which rooms people
    sat in, when each arrived and when they left, by department -- a record
    about identified people at work -- and the page can now be written to as
    well. On the office network that needs no door, because whoever is on
    the WiFi is already in the building. Reachable from home, it does.
    """
    guard = namespace["guard"]
    source = open("rooms_dashboard.py").read()

    class FakeStop(Exception):
        pass

    class Fake:
        def __init__(self, typed=None):
            self.session_state, self.typed = {}, typed
            self.stopped = self.reran = False
            self.errors = []

        def markdown(self, *a, **k): pass
        def caption(self, *a, **k): pass
        def text_input(self, *a, **k): return self.typed
        def error(self, m): self.errors.append(m)
        def rerun(self): self.reran = True; raise FakeStop()
        def stop(self): self.stopped = True; raise FakeStop()

    def run(password, typed=None, already=False):
        fake = Fake(typed)
        if already:
            fake.session_state["let_in"] = True
        saved_st, saved_setting = namespace["st"], namespace["_setting"]
        namespace["st"] = fake
        namespace["_setting"] = lambda n: (password
                                           if n == "DASHBOARD_PASSWORD"
                                           else None)
        try:
            guard()
        except FakeStop:
            pass
        finally:
            namespace["st"] = saved_st
            namespace["_setting"] = saved_setting
        return fake

    # No password: the laptop on the office desk, where a door would only be
    # one more thing to type. Open, and openly so.
    opened = run(None)
    check("with no password set the page is open", not opened.stopped)

    # Set: nothing is drawn until the word is right.
    shut = run("hunter2")
    check("with one set, the page stops before drawing anything",
          shut.stopped)
    check("and says nothing about what was wrong", not shut.errors)

    wrong = run("hunter2", typed="letmein")
    check("a wrong word does not open it",
          wrong.stopped and not wrong.session_state.get("let_in"))
    check("and it says so", bool(wrong.errors))

    right = run("hunter2", typed="hunter2")
    check("the right word opens it",
          right.session_state.get("let_in") is True)
    check("and the page is reloaded rather than half drawn", right.reran)

    back = run("hunter2", already=True)
    check("and it is not asked for again in the same session",
          not back.stopped)

    # Comparing with == leaks how much of the word was right in the time it
    # takes, which is the whole of a guessing attack.
    check("the comparison does not leak the answer in its timing",
          "hmac.compare_digest" in source)
    # The gate must run before anything draws, not after the first chart.
    check("the door is before the page, not after it",
          source.index("guard()\n") < source.index("def load_state"))


def check_quiet_night(namespace):
    """A room that changed nothing for days still has a night to draw.

    room_events records changes, so a room empty since Friday has no row at
    all inside the window the dashboard loads. The strip drew that as
    unwatched -- a grey night that says "nobody looked" over the exact hours
    this system is for. The dashboard now hands in each room's last event
    from before the window, and these checks pin the two halves: the query
    asks for that row, and day_slots draws an empty night from it.
    """
    import campus_view

    source = open("rooms_dashboard.py").read()
    check("the history query carries the state in from before the window",
          "UNION ALL" in source and "DISTINCT ON (room) timestamp" in source)

    now = pd.Timestamp("2026-11-10 14:00", tz="UTC")
    anchor = now.normalize() - pd.Timedelta(days=3)      # before the window

    # Empty since Friday, nothing since: the whole night so far is empty.
    recent = pd.DataFrame([{"timestamp": anchor, "room": "Lobby",
                            "status": "empty", "people": 0,
                            "ac_state": None}])
    slots, first, last = campus_view.day_slots(recent, "Lobby", now)
    # 14:00 is slot 56, and the slot standing exactly at now is drawn, so
    # 57 marks are behind us and the remaining 39 are still to happen.
    drawn = [v for v in slots if v is not None]
    check("a room quiet for days still draws its night", len(drawn) == 57,
          "%d of 57 slots drawn" % len(drawn))
    check("and draws it as empty, not as occupied", set(drawn) == {0},
          str(set(drawn)))
    check("nobody arrived, so there is no first seen", first is None)
    check("the future is still left blank", slots[-1] is None)

    # Occupied when the day began: drawn as occupied, but not as an arrival.
    overnight = pd.DataFrame([{"timestamp": anchor, "room": "Data Centre",
                               "status": "occupied", "people": 2,
                               "ac_state": None}])
    slots, first, last = campus_view.day_slots(overnight, "Data Centre", now)
    check("a room occupied since before midnight is drawn occupied",
          slots[0] == 1 and slots[40] == 1)
    check("but midnight is not recorded as an arrival", first is None,
          str(first))
    check("and it still counts as last seen", last == 56, str(last))

    # The other half of the same truth. Carrying the state in says what the
    # room was doing; the heartbeat says whether anybody was there to see it.
    # Without this, a night when the laptop was shut draws as a peacefully
    # empty building -- which is the more dangerous of the two wrong answers,
    # because it looks like a measurement.
    # Beats every two minutes from 09:00 until 11:28, then nothing.
    watched = [now.normalize() + pd.Timedelta(hours=9)
               + pd.Timedelta(minutes=m) for m in range(0, 150, 2)]
    slots, first, last = campus_view.day_slots(recent, "Lobby", now, watched)
    check("hours with no heartbeat are unknown, not empty",
          all(v is None for v in slots[:36]), str(slots[:36]))
    check("and hours with one are drawn", slots[36] == 0 and slots[46] == 0,
          "%r %r" % (slots[36], slots[46]))
    check("the hours after the beats stop are unknown again",
          slots[47] is None and slots[55] is None,
          "%r %r" % (slots[47], slots[55]))

    # A slot is watched if a beat lands in it; a cycle takes over two
    # minutes, so the quarter hour just entered counts on the last beat.
    edge = [now.normalize() + pd.Timedelta(hours=13, minutes=59)]
    cover = campus_view.watched_slots(edge, now)
    check("a beat near the end of a slot also vouches for the next",
          cover[55] and cover[56], "%r %r" % (cover[55], cover[56]))
    check("and not for the rest of the day",
          not cover[0] and not cover[57], "%r %r" % (cover[0], cover[57]))
    check("no heartbeats at all means nothing is claimed",
          not any(campus_view.watched_slots([], now)))
    check("and beats of None keeps the old, database-free behaviour",
          all(campus_view.watched_slots(None, now)))

    # The curve must not invent a quiet building out of an absent loop either.
    df = pd.DataFrame([{"room": "Lobby", "zone": "First floor"}])
    inside, _ = campus_view.building_curve(recent, df, now, watched)
    check("the building curve leaves unwatched hours blank",
          inside[0] is None and inside[36] == 0,
          "%r %r" % (inside[0], inside[36]))

    # Without that carried-in row the night is unknown, which is the bug.
    bare = pd.DataFrame(columns=["timestamp", "room", "status", "people",
                                 "ac_state"])
    slots, _, _ = campus_view.day_slots(bare, "Lobby", now)
    check("with nothing carried in, the night is unknown rather than empty",
          all(v is None for v in slots))


def check_head_count(namespace):
    """How many people are in the campus, and what the figure is allowed to claim.

    This is the number everybody looks at first, so it is the easiest one to
    believe without reading. Three things it must never do: count the car
    park as indoors, present the last thing a stopped loop saw as "right
    now", or report a flat total when some rooms were never looked at.
    """
    parts = namespace["head_count_parts"]
    stale = namespace["STALE_AFTER_MINUTES"] + 1

    df = pd.DataFrame([
        {"room": "Marketing", "zone": "Ground floor", "status": "occupied",
         "people": 4},
        {"room": "HR Room", "zone": "First floor", "status": "occupied",
         "people": 3},
        {"room": "Lobby", "zone": "First floor", "status": "empty",
         "people": 0},
        {"room": "P2 Parking", "zone": "Outside & plant",
         "status": "occupied", "people": 9},
    ])
    label, value, note = parts(df, 1.0)
    check("the headcount counts indoor rooms only", value == "7",
          "%s (%s)" % (value, note))
    check("and says so in words", label == "IN CAMPUS RIGHT NOW", label)
    check("the car park is counted apart, not added in", "9 outside" in note,
          note)
    check("and the busy rooms are named", "2 rooms busy" in note, note)

    # A room nobody looked at contributes nobody, so the sum is a floor.
    # Printing it as a total would quietly under-report the building.
    quiet = pd.concat([df, pd.DataFrame([
        {"room": "Dead Camera", "zone": "Ground floor", "status": "unknown",
         "people": None}])], ignore_index=True)
    label, value, note = parts(quiet, 1.0)
    check("a room that did not answer makes the count a floor",
          value == "at least 7", value)
    check("and the page says how many did not answer",
          "1 room did not answer" in note, note)

    # NaN is the other way a room says nothing, and it must count the same.
    nan = quiet.copy()
    nan.loc[nan["room"] == "Dead Camera", "status"] = float("nan")
    check("a missing status counts as not answered",
          parts(nan, 1.0)[1] == "at least 7", parts(nan, 1.0)[1])

    # With the loop stopped the figure is history, and saying "right now"
    # over it would be the page telling its own lie.
    check("a silent loop stops the figure claiming the present",
          parts(df, stale)[0] == "IN CAMPUS WHEN LAST SEEN",
          parts(df, stale)[0])
    check("and never having reported counts as silent",
          parts(df, None)[0] == "IN CAMPUS WHEN LAST SEEN",
          parts(df, None)[0])

    # An empty building is zero, not a dash: zero is a fact worth printing.
    none = df.copy()
    none["status"] = "empty"
    check("an empty campus reads nought, not a dash",
          parts(none, 1.0)[1] == "0", parts(none, 1.0)[1])
    check("with nobody outside, the note leaves outside out",
          "outside" not in parts(none, 1.0)[2], parts(none, 1.0)[2])

    # The band renders the same three strings, so the two cannot drift.
    html = namespace["head_count"](quiet, 1.0)
    check("the band prints the headcount it was given",
          "at least 7" in html and "IN CAMPUS RIGHT NOW" in html
          and "did not answer" in html)
    check("and the word people is on the page",
          ">people<" in html.replace("</span>", "<"))


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
              "show_numbers", "head_count", "head_count_parts"]
    missing = [n for n in wanted if "def %s(" % n not in source]
    check("every view and helper is still here", not missing,
          ", ".join(missing))

    check_guard(namespace)
    check_quiet_night(namespace)
    check_head_count(namespace)

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

    # 96 marks, not 64: the strip runs midnight to midnight now. The count
    # is taken from the module rather than written out, so that moving the
    # window again cannot leave this check passing against the old day.
    want = ((campus_view.DAY_END_HOUR - campus_view.DAY_START_HOUR) * 60
            // campus_view.SLOT_MINUTES)
    check("the day strip has one mark per quarter hour, all day",
       len(by["Marketing"]["slots"]) == want == 96,
       "%d marks, wanted %d" % (len(by["Marketing"]["slots"]), want))
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
