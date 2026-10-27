"""Localization metrics, issue slices, and the area under the budget curve."""
import math
import re

from .retrieval import _IDENT, _TRACE

KS = (1, 3, 5, 10)


def acc_all(pred, gold, k):
    """1 if every gold item is in the top-k predictions (LocAgent-style Acc@k)."""
    return float(bool(gold) and set(gold) <= set(pred[:k]))


def hit_any(pred, gold, k):
    return float(bool(set(gold) & set(pred[:k])))


def score(pred_files, pred_nodes, gold_files, gold_nodes):
    m = {}
    for k in KS:
        m[f"file_acc@{k}"] = acc_all(pred_files, gold_files, k)
        if gold_nodes:
            m[f"func_acc@{k}"] = acc_all(pred_nodes, gold_nodes, k)
            m[f"func_hit@{k}"] = hit_any(pred_nodes, gold_nodes, k)
    return m


def slices(graph, issue, gold_files, gold_nodes):
    """Issue properties used for the error analysis in the paper."""
    names = {graph.nodes[n].name for n in gold_nodes if n in graph.nodes}
    idents = set(_IDENT.findall(issue))
    return {
        "has_traceback": bool(_TRACE.search(issue)),
        "names_gold_symbol": bool(names & idents),
        "names_gold_file": any(f in issue or f.split("/")[-1] in issue for f in gold_files),
        "multi_file": len(gold_files) > 1,
        "has_code_block": "```" in issue or bool(re.search(r"^\s*>>>", issue, re.M)),
        "issue_tokens": len(issue) // 4,
    }


def aubc(points, lo=2000, hi=32000):
    """Normalised area under (log2 tokens, accuracy), clamped to [lo, hi] tokens.

    points: [(mean_tokens, accuracy)]. Outside the measured range the curve is
    held flat at the nearest measured value, so methods measured on different
    budget grids stay comparable. 1.0 = perfect accuracy at every budget.
    """
    pts = sorted((max(lo, min(hi, t)), a) for t, a in points)
    if not pts:
        return float("nan")
    xs = [math.log2(lo)] + [math.log2(t) for t, _ in pts] + [math.log2(hi)]
    ys = [pts[0][1]] + [a for _, a in pts] + [pts[-1][1]]
    area = sum((xs[i + 1] - xs[i]) * (ys[i] + ys[i + 1]) / 2 for i in range(len(xs) - 1))
    return area / (math.log2(hi) - math.log2(lo))
