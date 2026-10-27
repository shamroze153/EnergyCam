"""Localization methods compared in the paper.

  retrieval   no LLM: rank nodes with bm25 | ppr | graphpack
  oneshot     one LLM call over a packed context (bm25 or graphpack ranking,
              bodies | skeleton | hybrid packing) under a token budget
  agent       multi-turn tool use; tools = grep (search/view/list_dir) and
              optionally graph (find_symbol/skeleton/neighbors), optionally
              starting from a small GraphPack skeleton

Every method returns the same record: ranked files, ranked node ids, and the
token / call / wall-clock cost, so they can be compared on one curve.
"""
import json
import re
import time

from .llm import parse_json
from .retrieval import approx_tokens, files_from_nodes, pack, rank

SYSTEM_ONESHOT = """You localize bugs in Python repositories.
Given an issue and excerpts of the repository, name the functions or classes that
most likely need to be edited to resolve the issue, most likely first.
Answer ONLY with JSON: {"locations": ["path/to/file.py::Class.method", "path/to/other.py::function", ...]}
Use paths and names exactly as they appear in the excerpts. Give at most 10 locations."""


def resolve_location(graph, loc):
    """Map a model-written location to a graph node id (or a file path), else None."""
    loc = loc.strip().strip("`'\" ")
    if loc in graph.nodes:
        return loc
    m = re.match(r"^(.+?\.py)(?:(::|:|#)\s*(.+))?$", loc)
    if not m:
        cands = graph.by_name.get(loc.split(".")[-1], [])
        return cands[0] if len(cands) == 1 else None
    path, rest = m.group(1), (m.group(3) or "").strip()
    path = path.lstrip("./")
    if path not in graph.files:
        hits = [f for f in graph.files if f.endswith("/" + path) or path.endswith("/" + f)]
        if len(hits) != 1:
            return None
        path = hits[0]
    if not rest:
        return path
    if rest.isdigit():
        return graph.innermost(path, int(rest)) or path
    rest = rest.split("(")[0].strip()
    nid = f"{path}::{rest}"
    if nid in graph.nodes:
        return nid
    tail = [n for n in graph.nodes.values()
            if n.file == path and (n.qualname.endswith("." + rest) or n.name == rest.split(".")[-1])]
    return tail[0].id if len(tail) == 1 else path


def _record(graph, node_ranking, cost, extra=None):
    nodes = [n for n in node_ranking if n in graph.nodes and graph.nodes[n].kind != "module"]
    files = []
    for n in node_ranking:
        f = graph.nodes[n].file if n in graph.nodes else n
        if f not in files:
            files.append(f)
    rec = {"files": files, "nodes": nodes, **cost}
    rec.update(extra or {})
    return rec


def run_retrieval(index, issue, method="graphpack"):
    t0 = time.time()
    ranked = rank(index, issue, method=method)
    return _record(index.g, ranked, {"llm_calls": 0, "prompt_tokens": 0,
                                     "completion_tokens": 0, "seconds": time.time() - t0})


def run_oneshot(index, issue, llm, budget=8000, ranker="graphpack", pack_mode="hybrid"):
    t0 = time.time()
    ranked = rank(index, issue, method=ranker)
    context, shown = pack(index.g, ranked, budget, mode=pack_mode)
    user = f"## Issue\n{issue.strip()}\n\n## Repository excerpts\n{context}\n\nReturn the JSON now."
    text, usage = llm.chat([{"role": "system", "content": SYSTEM_ONESHOT},
                            {"role": "user", "content": user}])
    parsed = parse_json(text) or {}
    locs = [resolve_location(index.g, l) for l in parsed.get("locations", []) if isinstance(l, str)]
    model_rank = [l for l in dict.fromkeys(locs) if l]
    # backfill with the retrieval order so Acc@k is defined for every k
    full = model_rank + [n for n in ranked if n not in model_rank]
    return _record(index.g, full, {
        "llm_calls": 1, "prompt_tokens": usage.get("prompt_tokens", approx_tokens(user)),
        "completion_tokens": usage.get("completion_tokens", approx_tokens(text)),
        "seconds": time.time() - t0}, {
        "model_locations": model_rank, "parse_ok": bool(parsed),
        "context_tokens": approx_tokens(context), "shown_nodes": len(shown), "shown_ids": shown,
        "shown_files": len(files_from_nodes(index.g, shown))})


# ---------------------------------------------------------------- agent

AGENT_TOOLS = {
    "search": "search(pattern): regex search over .py files, returns up to 20 'file:line: text' matches",
    "view": "view(path, start=1, end=start+79): show numbered lines of a file",
    "list_dir": "list_dir(path='.'): list a directory",
    "find_symbol": "find_symbol(name): classes/functions with this name, with signatures",
    "skeleton": "skeleton(path): every class/function signature in a file, with line ranges",
    "neighbors": "neighbors(id): callers, callees, parents, children of a node id 'file.py::Qual.name'",
    "submit": "submit(locations): finish; locations = ranked list of 'file.py::Qual.name'",
}
GREP_TOOLS = ["search", "view", "list_dir", "submit"]
GRAPH_TOOLS = GREP_TOOLS[:-1] + ["find_symbol", "skeleton", "neighbors", "submit"]

SYSTEM_AGENT = """You localize bugs in a Python repository by calling tools.
Each reply must be ONLY one JSON object: {{"thought": "...", "tool": "<name>", "args": {{...}}}}
Tools:
{tools}
Find the functions/classes that must be edited to resolve the issue, then call submit
with at most 10 locations, most likely first. You have at most {turns} tool calls."""

MAX_OBS_TOKENS = 1500


def _truncate(text, max_tokens=MAX_OBS_TOKENS):
    limit = max_tokens * 4
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


def run_tool(graph, name, args):
    try:
        if name == "search":
            pat = re.compile(str(args.get("pattern", "")))
            hits = []
            for rel, src in graph.files.items():
                for i, line in enumerate(src.splitlines(), 1):
                    if pat.search(line):
                        hits.append(f"{rel}:{i}: {line.strip()[:160]}")
                        if len(hits) >= 20:
                            return "\n".join(hits) + "\n... (more matches)"
            return "\n".join(hits) or "no matches"
        if name == "view":
            path = resolve_location(graph, str(args.get("path", "")))
            path = graph.nodes[path].file if path in graph.nodes else path
            if path not in graph.files:
                return f"no such file: {args.get('path')}"
            lines = graph.files[path].splitlines()
            start = max(int(args.get("start", 1)), 1)
            end = min(int(args.get("end", start + 79)), start + 119, len(lines))
            return "\n".join(f"{i:>5} {lines[i - 1]}" for i in range(start, end + 1)) or "(empty)"
        if name == "list_dir":
            prefix = str(args.get("path", ".")).strip("./")
            prefix = prefix + "/" if prefix else ""
            entries = sorted({f[len(prefix):].split("/")[0] + ("/" if "/" in f[len(prefix):] else "")
                              for f in graph.files if f.startswith(prefix)})
            return "\n".join(entries[:200]) or "empty or not a directory"
        if name == "find_symbol":
            ids = graph.by_name.get(str(args.get("name", "")).split(".")[-1], [])[:20]
            return "\n".join(f"{i}  {graph.nodes[i].signature}" for i in ids) or "not found"
        if name == "skeleton":
            path = resolve_location(graph, str(args.get("path", "")))
            nodes = sorted((n for n in graph.nodes.values() if n.file == path and n.kind != "module"),
                           key=lambda n: n.start)
            return "\n".join(f"{n.start}-{n.end} {n.qualname}: {n.signature}" for n in nodes) or "no file/defs"
        if name == "neighbors":
            nid = resolve_location(graph, str(args.get("id", "")))
            if nid not in graph.nodes:
                return "unknown id"
            rows = [f"{t}/{d}: {o}  {graph.nodes[o].signature}" for o, t, d in graph.neighbors(nid)]
            return "\n".join(rows[:40]) or "no neighbours"
    except (re.error, ValueError, TypeError) as e:
        return f"tool error: {e}"
    return f"unknown tool: {name}"


def run_agent(index, issue, llm, tools="grep", max_turns=15, context_limit=24000, start_pack=0):
    g = index.g
    names = GRAPH_TOOLS if tools == "graph" else GREP_TOOLS
    system = SYSTEM_AGENT.format(tools="\n".join("- " + AGENT_TOOLS[n] for n in names), turns=max_turns)
    user = f"## Issue\n{issue.strip()}"
    if start_pack:
        ctx, _ = pack(g, rank(index, issue), start_pack, mode="skeleton")
        user += f"\n\n## Likely relevant definitions (from the code graph)\n{ctx}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    t0, calls, p_tok, c_tok, submitted, trace = time.time(), 0, 0, 0, None, []
    stop_reason = "max_turns"
    for turn in range(max_turns):
        text, usage = llm.chat(messages)
        calls += 1
        p_tok += usage.get("prompt_tokens", sum(approx_tokens(m["content"]) for m in messages))
        c_tok += usage.get("completion_tokens", approx_tokens(text))
        act = parse_json(text) or {}
        tool, args = act.get("tool"), act.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        trace.append({"tool": tool, "args": args})
        if tool == "submit":
            locs = args.get("locations", [])
            submitted = [resolve_location(g, l) for l in locs if isinstance(l, str)] if isinstance(locs, list) else []
            stop_reason = "submit"
            break
        obs = "Reply with one JSON tool call." if tool not in names else _truncate(run_tool(g, tool, args))
        messages += [{"role": "assistant", "content": text}, {"role": "user", "content": f"Observation:\n{obs}"}]
        if sum(approx_tokens(m["content"]) for m in messages) > context_limit:
            stop_reason = "context_limit"
            break
    if submitted is None:  # force a final answer from what has been seen
        messages.append({"role": "user", "content": 'Stop exploring. Reply ONLY with {"tool": "submit", "args": {"locations": [...]}}'})
        text, usage = llm.chat(messages)
        calls += 1
        p_tok += usage.get("prompt_tokens", 0)
        c_tok += usage.get("completion_tokens", 0)
        act = parse_json(text) or {}
        locs = (act.get("args") or {}).get("locations", act.get("locations", []))
        submitted = [resolve_location(g, l) for l in locs if isinstance(l, str)] if isinstance(locs, list) else []
    model_rank = [l for l in dict.fromkeys(submitted) if l]
    full = model_rank + [n for n in rank(index, issue) if n not in model_rank]
    tool_counts = {}
    for step in trace:
        tool_counts[str(step["tool"])] = tool_counts.get(str(step["tool"]), 0) + 1
    return _record(g, full, {"llm_calls": calls, "prompt_tokens": p_tok, "completion_tokens": c_tok,
                             "seconds": time.time() - t0}, {
        "model_locations": model_rank, "stop_reason": stop_reason, "turns": len(trace),
        "tool_counts": tool_counts, "invalid_actions": sum(1 for s in trace if s["tool"] not in names),
        "repeated_actions": len(trace) - len({json.dumps(s, sort_keys=True) for s in trace})})
