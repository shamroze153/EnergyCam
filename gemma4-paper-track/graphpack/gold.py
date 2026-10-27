"""Gold locations from a task's reference patch.

A location is the innermost class/function of the *pre-patch* file that a hunk
touches. Edits at module level map to the module id ("path.py"). New files
have no pre-patch location and only count at file level.
"""
import re

from .graph import is_test_path

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def changed_lines(patch):
    """{path: sorted pre-patch line numbers touched}, plus the set of new files."""
    out, new_files = {}, set()
    path, old_line, is_new = None, 0, False
    lines = patch.splitlines()
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        # a removed line that itself starts with "-- " also looks like "--- "
        if line.startswith("--- ") and nxt.startswith("+++ "):
            is_new = line[4:].strip() == "/dev/null"
            continue
        if line.startswith("+++ ") and i > 0 and lines[i - 1].startswith("--- "):
            p = line[4:].strip()
            p = p[2:] if p.startswith("b/") else p
            path = p.split("\t")[0]
            if is_new:
                new_files.add(path)
            out.setdefault(path, set())
            continue
        m = _HUNK.match(line)
        if m:
            old_line = int(m.group(1))
            continue
        if path is None or line.startswith("\\"):
            continue
        if line.startswith("-"):
            out[path].add(old_line)
            old_line += 1
        elif line.startswith("+"):
            # an insertion sits between old_line - 1 and old_line; blame the line above
            out[path].add(max(old_line - 1, 1))
        else:
            old_line += 1
    return {p: sorted(v) for p, v in out.items()}, new_files


def gold_locations(graph, patch, include_tests=False):
    """Return (gold files, gold node ids) for a patch against the graph's snapshot."""
    lines, new_files = changed_lines(patch)
    files, nodes = [], []
    for path, nums in lines.items():
        # localization is scored on Python source only: docs, changelogs and
        # (by default) test files are not where the fix lives
        if not path.endswith(".py") or (is_test_path(path) and not include_tests):
            continue
        files.append(path)
        if path in new_files or path not in graph.files:
            continue
        for ln in nums:
            nid = graph.innermost(path, ln)
            if nid and nid not in nodes:
                nodes.append(nid)
    return files, nodes
