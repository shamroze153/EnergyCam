"""Rank repository nodes for an issue and pack them into a token budget.

Pipeline (all CPU, no network):
  1. seeds   - BM25 over class/function source, plus exact identifier
               mentions and traceback frames found in the issue text
  2. spread  - personalized PageRank from the seeds over the code graph
  3. score   - mix of normalised BM25 and PPR (lambda_lex controls the mix)
  4. pack    - full bodies for the top nodes, signatures ("skeleton") for the
               next ones, grouped by file, until the token budget is spent
"""
import math
import re
from collections import Counter, defaultdict

import numpy as np

EDGE_WEIGHTS = {"contains": 1.0, "calls": 1.0, "inherits": 0.7, "imports": 0.3}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TRACE = re.compile(r'File "([^"]+)", line (\d+), in ([A-Za-z_<>][\w<>]*)')
STOP = set("""a an and are as at be but by can do does for from has have how i if in
into is it its me my no not of on or our should so that the their them then there
these this to us was we what when where which while who why will with would you your
self none true false return def class import""".split())


def approx_tokens(text):
    """~4 characters per token; good enough for budgeting and stated as such."""
    return (len(text) + 3) // 4


def split_identifier(tok):
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", tok).replace("_", " ").split()
    return [p.lower() for p in parts if p]


def tokenize(text):
    out = []
    for tok in _IDENT.findall(text):
        low = tok.lower()
        sub = split_identifier(tok)
        if low not in STOP and len(low) > 1:
            out.append(low)
        if len(sub) > 1:
            out.extend(s for s in sub if s not in STOP and len(s) > 1)
    return out


class BM25:
    def __init__(self, docs, k1=1.2, b=0.75):
        self.k1, self.b, self.n = k1, b, len(docs)
        lens = np.array([len(d) for d in docs], dtype=float)
        avg = float(lens.mean()) if len(docs) else 1.0
        self.norm = k1 * (1 - b + b * lens / max(avg, 1e-9))
        postings = defaultdict(lambda: ([], []))
        for i, d in enumerate(docs):
            for t, c in Counter(d).items():
                postings[t][0].append(i)
                postings[t][1].append(c)
        self.postings = {t: (np.array(ix), np.array(tf, dtype=float))
                         for t, (ix, tf) in postings.items()}
        self.idf = {t: math.log(1 + (self.n - len(ix) + 0.5) / (len(ix) + 0.5))
                    for t, (ix, _) in self.postings.items()}

    def scores(self, query):
        out = np.zeros(self.n)
        for t in set(query):
            if t not in self.postings:
                continue
            ix, tf = self.postings[t]
            out[ix] += self.idf[t] * tf * (self.k1 + 1) / (tf + self.norm[ix])
        return out


class Index:
    """Per-repository index: built once, reused for every issue on that snapshot."""

    def __init__(self, graph, include_tests=False):
        self.g = graph
        self.ids = [nid for nid, n in graph.nodes.items()
                    if n.kind != "module" and (include_tests or not n.is_test)]
        self.pos = {nid: i for i, nid in enumerate(self.ids)}
        docs = []
        for nid in self.ids:
            n = graph.nodes[nid]
            text = f"{n.file} {n.qualname} {graph.source(nid)}"
            docs.append(tokenize(text))
        self.bm25 = BM25(docs)
        self._build_matrix()

    def _build_matrix(self):
        # column-stochastic transition matrix over all graph nodes, undirected
        self.all_ids = list(self.g.nodes)
        self.all_pos = {nid: i for i, nid in enumerate(self.all_ids)}
        rows, cols, vals = [], [], []
        for s, ds in self.g.edges.items():
            for d, t in ds.items():
                w = EDGE_WEIGHTS.get(t, 0.5)
                i, j = self.all_pos[s], self.all_pos[d]
                rows += [i, j]
                cols += [j, i]
                vals += [w, w]
        self.rows = np.array(rows, dtype=np.int64)
        self.cols = np.array(cols, dtype=np.int64)
        vals = np.array(vals, dtype=float)
        out_w = np.zeros(len(self.all_ids))
        np.add.at(out_w, self.cols, vals)
        self.vals = vals / np.where(out_w[self.cols] > 0, out_w[self.cols], 1.0)

    def ppr(self, seeds, damping=0.85, iters=40):
        n = len(self.all_ids)
        p = np.zeros(n)
        for nid, w in seeds.items():
            if nid in self.all_pos:
                p[self.all_pos[nid]] += w
        if p.sum() == 0:
            return np.zeros(n)
        p /= p.sum()
        r = p.copy()
        for _ in range(iters):
            spread = np.zeros(n)
            np.add.at(spread, self.rows, self.vals * r[self.cols])
            r = (1 - damping) * p + damping * spread
        return r


def mentions(graph, issue):
    """Nodes named in the issue: traceback frames (strong) and identifiers (weak)."""
    found = defaultdict(float)
    for path, line, func in _TRACE.findall(issue):
        path = path.replace("\\", "/")
        for rel in graph.files:
            if path.endswith("/" + rel) or path == rel:
                nid = graph.innermost(rel, int(line))
                if nid:
                    found[nid] += 3.0
    for tok in set(_IDENT.findall(issue)):
        if len(tok) < 4 or tok.lower() in STOP:
            continue
        cands = graph.by_name.get(tok, [])
        if 0 < len(cands) <= 8:
            for c in cands:
                found[c] += 1.0 / len(cands)
    for rel in graph.files:  # explicit file paths such as "httpx/_client.py"
        if rel in issue:
            found[rel] += 1.0
    return dict(found)


def _minmax(x):
    if len(x) == 0 or x.max() == x.min():
        return np.zeros_like(x)
    return (x - x.min()) / (x.max() - x.min())


def rank(index, issue, method="graphpack", lambda_lex=0.5, n_seeds=10):
    """Return node ids (classes/functions) ranked for the issue.

    method: bm25 | ppr | graphpack (bm25 + mentions seeding PPR, mixed)
    """
    lex = index.bm25.scores(tokenize(issue))
    if method == "bm25":
        order = np.argsort(-lex, kind="stable")
        return [index.ids[i] for i in order if lex[i] > 0]

    seeds = mentions(index.g, issue)
    if method == "graphpack":
        for i in np.argsort(-lex, kind="stable")[:n_seeds]:
            if lex[i] > 0:
                seeds[index.ids[i]] = seeds.get(index.ids[i], 0) + lex[i] / lex.max()
    pr_all = index.ppr(seeds)
    pr = np.array([pr_all[index.all_pos[nid]] for nid in index.ids])
    if method == "ppr":
        score = pr
    else:
        score = lambda_lex * _minmax(lex) + (1 - lambda_lex) * _minmax(pr)
        # nodes named in a traceback stay on top regardless of the mix
        for nid, w in seeds.items():
            if nid in index.pos and w >= 3.0:
                score[index.pos[nid]] += 1.0
    order = np.argsort(-score, kind="stable")
    return [index.ids[i] for i in order if score[i] > 0]


def files_from_nodes(graph, node_ids):
    seen, out = set(), []
    for nid in node_ids:
        f = graph.nodes[nid].file
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _numbered(graph, nid, max_lines):
    n = graph.nodes[nid]
    lines = graph.files[n.file].splitlines()[n.start - 1:n.end]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"    ... ({n.end - n.start + 1 - max_lines} more lines)"]
    return "\n".join(f"{n.start + i:>5} {l}" for i, l in enumerate(lines))


def pack(graph, ranked, budget, mode="hybrid", body_share=0.6, max_body_lines=60):
    """Render ranked nodes into at most `budget` (approximate) tokens.

    mode: bodies   - full bodies only
          skeleton - one signature line per node only
          hybrid   - bodies until body_share of the budget, then signatures
    Returns (text, list of node ids actually shown).
    """
    body_budget = budget if mode == "bodies" else (0 if mode == "skeleton" else budget * body_share)
    used, shown = 0, []
    blocks = defaultdict(list)  # file -> rendered pieces, in rank order of first appearance
    file_order = []
    for nid in ranked:
        n = graph.nodes[nid]
        if n.kind == "class" and mode != "skeleton" and used < body_budget:
            # a class body repeats its methods; show the header, methods come separately
            piece = f"{n.start:>5} {n.signature}  # class, lines {n.start}-{n.end}"
        elif used < body_budget:
            piece = _numbered(graph, nid, max_body_lines)
        elif mode == "bodies":
            break
        else:
            piece = f"{n.start:>5} {n.signature}  # {n.qualname}, lines {n.start}-{n.end}"
        cost = approx_tokens(piece) + (approx_tokens(f"### {n.file}") if n.file not in blocks else 0)
        if used + cost > budget:
            if mode == "skeleton" or used >= body_budget:
                break
            continue  # a big body did not fit; smaller ones still might
        if n.file not in blocks:
            file_order.append(n.file)
        blocks[n.file].append(piece)
        used += cost
        shown.append(nid)
    text = "\n\n".join(f"### {f}\n" + "\n".join(blocks[f]) for f in file_order)
    return text, shown
