"""Load the competition's own code graph and node embeddings for a snapshot.

Competition layout (Gemma 4 Developer Agent dataset):
  graphs/<repo>_<base_commit>.json      networkx node-link JSON, nodes keyed by
                                        dotted symbol path, edges typed ("calls")
  embeddings/<repo>_<base_commit>.npz   one 256-d float32 vector per node name

Their dotted names do not always match ours (e.g. docs_src/ examples drop the
"docs_src." prefix), so names are mapped to our node ids by exact dotted name
first and by a unique dotted suffix second. Unmapped names are counted and
reported, never guessed.
"""
import glob
import json
import os
from dataclasses import dataclass, field

import numpy as np

from .graph import module_name


@dataclass
class ProvidedData:
    edges: list = field(default_factory=list)   # (our_src_id, our_dst_id, type)
    emb: dict = field(default_factory=dict)     # our_id -> np.ndarray
    dim: int = 0
    stats: dict = field(default_factory=dict)


def dotted_names(graph):
    """{dotted name: our node id} for every class/function (and module) node."""
    out = {}
    for nid, n in graph.nodes.items():
        mod = module_name(n.file)
        name = mod if n.kind == "module" else f"{mod}.{n.qualname}"
        out[name] = nid
        if n.file.startswith(("src/", "lib/")):
            out[n.file.split("/")[0] + "." + name] = nid
    return out


class NameMapper:
    def __init__(self, graph):
        self.exact = dotted_names(graph)
        self.suffix = {}
        for name, nid in self.exact.items():
            parts = name.split(".")
            for k in range(1, len(parts) - 1):
                self.suffix.setdefault(".".join(parts[k:]), set()).add(nid)

    def __call__(self, name):
        if name in self.exact:
            return self.exact[name]
        cands = self.suffix.get(name)
        return next(iter(cands)) if cands and len(cands) == 1 else None


def find_files(comp_root, repo, base_commit):
    short = repo.split("/")[-1]
    g = glob.glob(os.path.join(comp_root, "graphs", f"{short}_{base_commit}.json")) or \
        glob.glob(os.path.join(comp_root, "graphs", f"*_{base_commit}.json"))
    e = glob.glob(os.path.join(comp_root, "embeddings", f"{short}_{base_commit}.npz")) or \
        glob.glob(os.path.join(comp_root, "embeddings", f"*_{base_commit}.npz"))
    return (g[0] if g else None), (e[0] if e else None)


def load_provided(graph, graph_json=None, emb_npz=None):
    """Map the provided graph/embeddings onto `graph`. Either file may be None."""
    data, mapper = ProvidedData(), NameMapper(graph)
    cache = {}

    def m(name):
        if name not in cache:
            cache[name] = mapper(name)
        return cache[name]

    if graph_json and os.path.exists(graph_json):
        with open(graph_json, encoding="utf-8") as fh:
            g = json.load(fh)
        links = g.get("edges", g.get("links", []))
        kept = 0
        for e in links:
            s, d = m(str(e.get("source"))), m(str(e.get("target")))
            if s and d:
                data.edges.append((s, d, str(e.get("type", "calls"))))
                kept += 1
        nodes = [str(n.get("id", n.get("name"))) for n in g.get("nodes", [])]
        data.stats.update(graph_nodes=len(nodes), graph_nodes_mapped=sum(1 for n in nodes if m(n)),
                          graph_edges=len(links), graph_edges_mapped=kept)
    if emb_npz and os.path.exists(emb_npz):
        # the npz is the competition host's own data; object arrays need pickle
        z = np.load(emb_npz, allow_pickle=True)
        for name in z.files:
            nid = m(name)
            vec = np.asarray(z[name], dtype=np.float32).ravel()
            if nid and vec.size:
                data.emb[nid] = vec
                data.dim = vec.size
        data.stats.update(emb_nodes=len(z.files), emb_nodes_mapped=len(data.emb))
    return data
