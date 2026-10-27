"""Aggregate result files into the paper's tables (markdown) and curve data (CSV).

  python -m graphpack.report results/*.jsonl --out-dir report/
"""
import argparse
import csv
import json
import math
import os
import random
import re
from collections import defaultdict

from .metrics import aubc

MAIN_COLS = ["file_acc@1", "file_acc@3", "file_acc@5", "func_acc@1", "func_acc@5", "func_acc@10",
             "gold_in_context"]
SLICES = ["has_traceback", "names_gold_symbol", "names_gold_file", "multi_file"]


def load(paths):
    rows = defaultdict(list)
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    rows[r["config"]].append(r)
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_ci(xs, n=2000, seed=0):
    """95% percentile bootstrap interval of the mean (tasks resampled)."""
    xs = [x for x in xs if x is not None]
    if not xs:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def fmt(x, pct=True):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{100 * x:.1f}" if pct else f"{x:,.0f}"


def metric(rs, key):
    return [r["metrics"].get(key) for r in rs]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("results", nargs="+")
    p.add_argument("--out-dir", default="report")
    a = p.parse_args(argv)
    rows = load(a.results)
    os.makedirs(a.out_dir, exist_ok=True)
    md = ["# Results", ""]

    md += ["## Main table (Acc@k in %, mean cost per task)", "",
           "| config | n | " + " | ".join(MAIN_COLS) + " | func_acc@5 95% CI | tokens | calls | sec | errors |",
           "|---" * (len(MAIN_COLS) + 7) + "|"]
    for cfg in sorted(rows):
        rs = rows[cfg]
        lo, hi = bootstrap_ci(metric(rs, "func_acc@5"))
        tok = mean([r["prompt_tokens"] + r["completion_tokens"] for r in rs])
        md.append(f"| {cfg} | {len(rs)} | " + " | ".join(fmt(mean(metric(rs, c))) for c in MAIN_COLS)
                  + f" | {fmt(lo)}–{fmt(hi)} | {fmt(tok, False)} | {mean([r['llm_calls'] for r in rs]):.1f}"
                  + f" | {mean([r['seconds'] for r in rs]):.1f} | {sum(1 for r in rs if r.get('error'))} |")

    md += ["", "## Slices (func_acc@5 in %, n in brackets)", "",
           "| config | " + " | ".join(f"{s}=yes | {s}=no" for s in SLICES) + " |",
           "|---" * (2 * len(SLICES) + 1) + "|"]
    for cfg in sorted(rows):
        cells = []
        for s in SLICES:
            for val in (True, False):
                sub = [r for r in rows[cfg] if r["slices"][s] is val]
                cells.append(f"{fmt(mean(metric(sub, 'func_acc@5')))} ({len(sub)})")
        md.append(f"| {cfg} | " + " | ".join(cells) + " |")

    # budget curves: oneshot configs that differ only in budget
    curves = defaultdict(list)
    for cfg, rs in rows.items():
        m = re.match(r"^(oneshot-.+)-(\d+)$", cfg)
        if m:
            tok = mean([r["prompt_tokens"] + r["completion_tokens"] for r in rs])
            curves[m.group(1)].append((tok, mean(metric(rs, "func_acc@5")),
                                       mean(metric(rs, "file_acc@1")), int(m.group(2))))
    with open(os.path.join(a.out_dir, "budget_curves.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["curve", "budget", "mean_tokens", "func_acc@5", "file_acc@1"])
        for c, pts in sorted(curves.items()):
            for tok, f5, f1, b in sorted(pts, key=lambda x: x[3]):
                w.writerow([c, b, round(tok), round(f5, 4), round(f1, 4)])
    if curves:
        md += ["", "## Area under the localization-budget curve (func_acc@5, 2k–32k tokens)", "",
               "| curve | budgets | AUBC |", "|---|---|---|"]
        for c, pts in sorted(curves.items()):
            md.append(f"| {c} | {', '.join(str(x[3]) for x in sorted(pts, key=lambda x: x[3]))} | "
                      f"{aubc([(t, f5) for t, f5, _, _ in pts]):.3f} |")

    agents = {c: rs for c, rs in rows.items() if c.startswith("agent-")}
    if agents:
        md += ["", "## Agent behaviour (means per task)", "",
               "| config | turns | invalid actions | repeated actions | submitted | hit context limit |",
               "|---|---|---|---|---|---|"]
        for c, rs in sorted(agents.items()):
            md.append(f"| {c} | {mean([r.get('turns', 0) for r in rs]):.1f} | "
                      f"{mean([r.get('invalid_actions', 0) for r in rs]):.2f} | "
                      f"{mean([r.get('repeated_actions', 0) for r in rs]):.2f} | "
                      f"{fmt(mean([r.get('stop_reason') == 'submit' for r in rs]))}% | "
                      f"{fmt(mean([r.get('stop_reason') == 'context_limit' for r in rs]))}% |")

    with open(os.path.join(a.out_dir, "results.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("\n".join(md))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(5, 3.4))
        for c, pts in sorted(curves.items()):
            pts = sorted(pts)
            ax.plot([x[0] for x in pts], [100 * x[1] for x in pts], marker="o", label=c.replace("oneshot-", ""))
        for c, rs in sorted(agents.items()):  # agents are single points on the same axes
            tok = mean([r["prompt_tokens"] + r["completion_tokens"] for r in rs])
            ax.scatter([tok], [100 * mean(metric(rs, "func_acc@5"))], marker="x", label=c)
        ax.set_xscale("log", base=2)
        ax.set_xlabel("mean tokens per task (log scale)")
        ax.set_ylabel("Function Acc@5 (%)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(os.path.join(a.out_dir, "budget_curve.png"), dpi=200)
    except ImportError:
        pass


if __name__ == "__main__":
    main()
