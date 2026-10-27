"""Run one localization configuration over a task file.

Task file: JSON lines with
  instance_id, repo_dir (pre-patch snapshot), problem_statement, patch (gold)
(see prepare_tasks.py to build it from the competition data).

Examples:
  python -m graphpack.run --tasks tasks.jsonl --method retrieval --ranker bm25
  python -m graphpack.run --tasks tasks.jsonl --method oneshot --ranker graphpack --pack hybrid --budget 8000
  python -m graphpack.run --tasks tasks.jsonl --method agent --tools graph --turns 15 --start-pack 2000

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
from .retrieval import Index


def config_name(a):
    if a.method == "retrieval":
        return f"retrieval-{a.ranker}"
    if a.method == "oneshot":
        return f"oneshot-{a.ranker}-{a.pack}-{a.budget}"
    return f"agent-{a.tools}-t{a.turns}-sp{a.start_pack}"


def load_tasks(path, limit=None):
    with open(path, encoding="utf-8") as fh:
        tasks = [json.loads(l) for l in fh if l.strip()]
    return tasks[:limit] if limit else tasks


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--method", choices=["retrieval", "oneshot", "agent"], required=True)
    p.add_argument("--ranker", choices=["bm25", "ppr", "graphpack"], default="graphpack")
    p.add_argument("--pack", choices=["bodies", "skeleton", "hybrid"], default="hybrid")
    p.add_argument("--budget", type=int, default=8000)
    p.add_argument("--tools", choices=["grep", "graph"], default="grep")
    p.add_argument("--turns", type=int, default=15)
    p.add_argument("--context-limit", type=int, default=24000)
    p.add_argument("--start-pack", type=int, default=0)
    p.add_argument("--limit", type=int)
    p.add_argument("--model", help="overrides LLM_MODEL")
    a = p.parse_args(argv)

    name = config_name(a)
    done = set()
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as fh:
            rows = [json.loads(l) for l in fh if l.strip()]
        done = {r["instance_id"] for r in rows if r["config"] == name}
    llm = None if a.method == "retrieval" else ChatLLM(model=a.model)
    cache = {}  # repo_dir -> Index; tasks sharing a snapshot reuse it
    tasks = [t for t in load_tasks(a.tasks, a.limit) if t["instance_id"] not in done]
    print(f"{name}: {len(tasks)} tasks to run ({len(done)} already in {a.out})", file=sys.stderr)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    for i, t in enumerate(tasks, 1):
        t0 = time.time()
        if t["repo_dir"] not in cache:
            cache.clear()  # one snapshot in memory at a time
            cache[t["repo_dir"]] = Index(build_graph(t["repo_dir"]))
        index = cache[t["repo_dir"]]
        index_seconds = time.time() - t0
        gold_files, gold_nodes = gold_locations(index.g, t["patch"])
        issue = t["problem_statement"]
        try:
            if a.method == "retrieval":
                rec = run_retrieval(index, issue, a.ranker)
            elif a.method == "oneshot":
                rec = run_oneshot(index, issue, llm, a.budget, a.ranker, a.pack)
            else:
                rec = run_agent(index, issue, llm, a.tools, a.turns, a.context_limit, a.start_pack)
            err = None
        except Exception as e:  # keep going; the failure is recorded and counted as a miss
            rec, err = {"files": [], "nodes": [], "llm_calls": 0, "prompt_tokens": 0,
                        "completion_tokens": 0, "seconds": 0}, repr(e)[:500]
        metrics = score(rec["files"], rec["nodes"], gold_files, gold_nodes)
        shown = rec.pop("shown_ids", None)
        if shown is not None and gold_nodes:
            # did the packed context contain every gold definition at all?
            metrics["gold_in_context"] = float(set(gold_nodes) <= set(shown))
        row = {"instance_id": t["instance_id"], "config": name, "error": err,
               "gold_files": gold_files, "gold_nodes": gold_nodes,
               "metrics": metrics,
               "slices": slices(index.g, issue, gold_files, gold_nodes),
               "index_seconds": index_seconds, "graph_nodes": len(index.g.nodes),
               **{k: v for k, v in rec.items() if k not in ("files", "nodes")},
               "pred_files": rec["files"][:10], "pred_nodes": rec["nodes"][:20]}
        with open(a.out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        m = row["metrics"]
        print(f"[{i}/{len(tasks)}] {t['instance_id']} file@1={m.get('file_acc@1')} "
              f"func@5={m.get('func_acc@5', '-')} tok={row['prompt_tokens']}"
              f"{' ERR ' + err if err else ''}", file=sys.stderr)


if __name__ == "__main__":
    main()
