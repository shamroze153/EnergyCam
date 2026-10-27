"""Run one localization configuration over a task file.

Task file: JSON lines with
  instance_id, repo_dir (pre-patch snapshot), problem_statement, patch (gold)
(see prepare_tasks.py to build it from the competition data).

Examples:
  python -m graphpack.run --tasks tasks.jsonl --method retrieval --ranker bm25
  python -m graphpack.run --tasks tasks.jsonl --method oneshot --ranker graphpack --pack hybrid --budget 8000
  python -m graphpack.run --tasks tasks.jsonl --method agent --tools graph --turns 15 --start-pack 2000

Options marked "list" take comma-separated values and every combination runs
in one pass, sharing each snapshot's index:
  python -m graphpack.run --tasks tasks.jsonl --out r.jsonl --method oneshot \
      --ranker bm25,graphpack --pack bodies,hybrid --budget 2000,4000,8000,16000

Results are appended to --out (one JSON line per task and config) and runs
resume: tasks already present in --out for the same config are skipped.
"""
import argparse
import json
import os
import sys
import time

from .gold import gold_locations
from .graph import build_graph
from .llm import ChatLLM
from .localize import run_agent, run_oneshot, run_retrieval
from .metrics import score, slices
from .provided import load_provided
from .retrieval import RANKERS, Index


def config_name(c):
    if c["method"] == "retrieval":
        return f"retrieval-{c['ranker']}"
    if c["method"] == "oneshot":
        return f"oneshot-{c['ranker']}-{c['pack']}-{c['budget']}"
    return f"agent-{c['tools']}-t{c['turns']}-sp{c['start_pack']}"


def expand_configs(a):
    """Comma-separated options expand to their product, so one pass over the tasks
    (one graph build per snapshot) serves every configuration."""
    split = lambda v, cast=str: [cast(x) for x in str(v).split(",") if x != ""]
    for r in split(a.ranker):
        if r not in RANKERS:
            raise SystemExit(f"unknown ranker {r}; choose from {RANKERS}")
    base = {"method": a.method, "turns": a.turns}
    if a.method == "retrieval":
        combos = [{"ranker": r} for r in split(a.ranker)]
    elif a.method == "oneshot":
        combos = [{"ranker": r, "pack": pk, "budget": b} for b in split(a.budget, int)
                  for r in split(a.ranker) for pk in split(a.pack)]
    else:
        combos = [{"tools": tl, "start_pack": sp} for tl in split(a.tools) for sp in split(a.start_pack, int)]
    configs = [{**base, **c} for c in combos]
    for c in configs:
        c["name"] = config_name(c)
    return configs


def load_tasks(path, limit=None):
    with open(path, encoding="utf-8") as fh:
        tasks = [json.loads(l) for l in fh if l.strip()]
    return tasks[:limit] if limit else tasks


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--method", choices=["retrieval", "oneshot", "agent"], required=True)
    # each of these may be a comma-separated list; every combination is run
    p.add_argument("--ranker", default="graphpack", help=f"one or more of {', '.join(RANKERS)}")
    p.add_argument("--pack", default="hybrid", help="bodies, skeleton, hybrid")
    p.add_argument("--budget", default="8000")
    p.add_argument("--tools", default="grep", help="grep, graph")
    p.add_argument("--start-pack", default="0")
    p.add_argument("--turns", type=int, default=15)
    p.add_argument("--context-limit", type=int, default=24000)
    p.add_argument("--limit", type=int)
    p.add_argument("--model", help="overrides LLM_MODEL")
    p.add_argument("--no-provided", action="store_true",
                   help="ignore the competition graph/embeddings even if the task lists them")
    a = p.parse_args(argv)

    configs = expand_configs(a)
    done = {}
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    done.setdefault(r["config"], set()).add(r["instance_id"])
    llm = None if a.method == "retrieval" else ChatLLM(model=a.model)
    all_tasks = load_tasks(a.tasks, a.limit)
    todo = [(t, [c for c in configs if t["instance_id"] not in done.get(c["name"], set())]) for t in all_tasks]
    todo = [(t, cs) for t, cs in todo if cs]
    print(f"{len(configs)} config(s): {', '.join(c['name'] for c in configs)}\n"
          f"{len(todo)} of {len(all_tasks)} tasks still have work (results in {a.out})", file=sys.stderr)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cache = {}  # repo_dir -> Index; tasks sharing a snapshot reuse it
    for i, (t, cs) in enumerate(todo, 1):
        t0 = time.time()
        if t["repo_dir"] not in cache:
            cache.clear()  # one snapshot in memory at a time
            graph = build_graph(t["repo_dir"])
            provided = None
            if not a.no_provided and (t.get("graph_json") or t.get("emb_npz")):
                provided = load_provided(graph, t.get("graph_json"), t.get("emb_npz"))
            cache[t["repo_dir"]] = Index(graph, provided=provided)
        index = cache[t["repo_dir"]]
        index_seconds = time.time() - t0
        gold_files, gold_nodes = gold_locations(index.g, t["patch"])
        issue = t["problem_statement"]
        task_slices = slices(index.g, issue, gold_files, gold_nodes)
        for c in cs:
            try:
                if c["method"] == "retrieval":
                    rec = run_retrieval(index, issue, c["ranker"])
                elif c["method"] == "oneshot":
                    rec = run_oneshot(index, issue, llm, c["budget"], c["ranker"], c["pack"])
                else:
                    rec = run_agent(index, issue, llm, c["tools"], c["turns"], a.context_limit, c["start_pack"])
                err = None
            except Exception as e:  # keep going; the failure is recorded and counted as a miss
                rec, err = {"files": [], "nodes": [], "llm_calls": 0, "prompt_tokens": 0,
                            "completion_tokens": 0, "seconds": 0}, repr(e)[:500]
            metrics = score(rec["files"], rec["nodes"], gold_files, gold_nodes)
            shown = rec.pop("shown_ids", None)
            if shown is not None and gold_nodes:
                # did the packed context contain every gold definition at all?
                metrics["gold_in_context"] = float(set(gold_nodes) <= set(shown))
            row = {"instance_id": t["instance_id"], "config": c["name"], "error": err,
                   "gold_files": gold_files, "gold_nodes": gold_nodes,
                   "metrics": metrics, "slices": task_slices,
                   "index_seconds": index_seconds, "graph_nodes": len(index.g.nodes),
                   "provided_stats": index.provided.stats if index.provided else None,
                   **{k: v for k, v in rec.items() if k not in ("files", "nodes")},
                   "pred_files": rec["files"][:10], "pred_nodes": rec["nodes"][:20]}
            with open(a.out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            m = row["metrics"]
            print(f"[{i}/{len(todo)}] {t['instance_id']} {c['name']} file@1={m.get('file_acc@1')} "
                  f"func@5={m.get('func_acc@5', '-')} tok={row['prompt_tokens']}"
                  f"{' ERR ' + err if err else ''}", file=sys.stderr)


if __name__ == "__main__":
    main()
