"""Build a typed code graph for a Python repository with the standard `ast` module.

Nodes are modules, classes and functions. Edges:
  contains  module -> class/function, class -> method
  imports   module -> module (intra-repo only)
  calls     function -> function (name-resolved, best effort)
  inherits  class -> base class
No third-party parser is needed, so it runs the same in a Kaggle notebook
with internet off.
"""
import ast
import os
from dataclasses import dataclass, field

SKIP_DIRS = {".git", ".hg", ".tox", ".nox", ".venv", "venv", "env", "build",
             "dist", "node_modules", "__pycache__", ".mypy_cache", ".eggs"}
MAX_FILE_BYTES = 1_000_000
MAX_CALL_CANDIDATES = 5   # an unresolved `x.foo()` links to at most this many `foo`s


@dataclass
class Node:
    id: str            # "path/to/file.py" for modules, "path/to/file.py::Class.method" otherwise
    kind: str          # module | class | function
    file: str
    name: str
    qualname: str
    start: int
    end: int
    signature: str = ""
    doc: str = ""
    is_test: bool = False


@dataclass
class CodeGraph:
    root: str
    nodes: dict = field(default_factory=dict)
    edges: dict = field(default_factory=dict)        # src -> {dst: edge_type}
    files: dict = field(default_factory=dict)        # rel path -> source text
    by_name: dict = field(default_factory=dict)      # simple name -> [node ids]
    _reverse: dict = None

    def add_edge(self, src, dst, etype):
        if src != dst and src in self.nodes and dst in self.nodes:
            self._reverse = None
            self.edges.setdefault(src, {}).setdefault(dst, etype)

    def neighbors(self, node_id):
        """Outgoing and incoming neighbours as (node_id, edge_type, direction)."""
        if self._reverse is None:
            self._reverse = {}
            for s, ds in self.edges.items():
                for d, t in ds.items():
                    self._reverse.setdefault(d, {})[s] = t
        out = [(d, t, "out") for d, t in self.edges.get(node_id, {}).items()]
        inc = [(s, t, "in") for s, t in self._reverse.get(node_id, {}).items()]
        return out + inc

    def source(self, node_id):
        n = self.nodes[node_id]
        lines = self.files[n.file].splitlines()
        return "\n".join(lines[n.start - 1:n.end])

    def innermost(self, file, line):
        """Innermost class/function covering `line` in `file`, else the module."""
        best = None
        for n in self.nodes.values():
            if n.file == file and n.kind != "module" and n.start <= line <= n.end:
                if best is None or (n.end - n.start) < (best.end - best.start):
                    best = n
        return best.id if best else (file if file in self.nodes else None)

    def stats(self):
        kinds, etypes = {}, {}
        for n in self.nodes.values():
            kinds[n.kind] = kinds.get(n.kind, 0) + 1
        for ds in self.edges.values():
            for t in ds.values():
                etypes[t] = etypes.get(t, 0) + 1
        return {"nodes": kinds, "edges": etypes}


def is_test_path(rel):
    parts = rel.replace("\\", "/").split("/")
    base = parts[-1]
    return (any(p in ("tests", "test", "testing") for p in parts[:-1])
            or base.startswith("test_") or base.endswith("_test.py") or base == "conftest.py")


def module_name(rel):
    p = rel[:-3].replace("\\", "/").split("/")
    if p[-1] == "__init__":
        p = p[:-1]
    if p and p[0] in ("src", "lib"):
        p = p[1:]
    return ".".join(p)


def _signature(node, src_lines):
    """The decorators and `def ...:` / `class ...:` header, joined to one line."""
    start = node.decorator_list[0].lineno - 1 if node.decorator_list else node.lineno - 1
    body_start = node.body[0].lineno - 1 if node.body else node.lineno
    header = src_lines[start:max(body_start, node.lineno)]
    return " ".join(l.strip() for l in header)[:300]


def _first_doc_line(node):
    doc = ast.get_docstring(node)
    return doc.strip().splitlines()[0][:200] if doc else ""


class _FileVisitor(ast.NodeVisitor):
    def __init__(self, graph, rel, src_lines, test):
        self.g, self.rel, self.lines, self.test = graph, rel, src_lines, test
        self.stack = []            # enclosing class/function node ids
        self.calls = {}            # function id -> [(kind, name)]
        self.bases = {}            # class id -> [base names]
        self.imports = []          # (module dotted name, imported name or None, alias)

    def _parent(self):
        return self.stack[-1] if self.stack else self.rel

    def _add(self, node, kind):
        parent = self._parent()
        prefix = self.g.nodes[parent].qualname + "." if parent != self.rel else ""
        qual = prefix + node.name
        nid = f"{self.rel}::{qual}"
        self.g.nodes[nid] = Node(nid, kind, self.rel, node.name, qual, node.lineno,
                                 getattr(node, "end_lineno", node.lineno),
                                 _signature(node, self.lines), _first_doc_line(node), self.test)
        self.g.by_name.setdefault(node.name, []).append(nid)
        self.g.add_edge(parent, nid, "contains")
        return nid

    def visit_ClassDef(self, node):
        nid = self._add(node, "class")
        self.bases[nid] = [_dotted(b).split(".")[-1] for b in node.bases if _dotted(b)]
        self.stack.append(nid)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        nid = self._add(node, "function")
        self.stack.append(nid)
        calls = self.calls.setdefault(nid, [])
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Name):
                    calls.append(("name", f.id))
                elif isinstance(f, ast.Attribute):
                    calls.append(("attr", f.attr))
        # nested defs become their own nodes
        for child in node.body:
            self.visit(child)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node):
        for a in node.names:
            self.imports.append((a.name, None, a.asname or a.name.split(".")[0]))

    def visit_ImportFrom(self, node):
        base = node.module or ""
        if node.level:
            pkg = module_name(self.rel).split(".")
            # a module file's own package is its parent; __init__.py *is* the package
            if not self.rel.endswith("__init__.py"):
                pkg = pkg[:-1]
            pkg = pkg[:len(pkg) - (node.level - 1)] if node.level > 1 else pkg
            base = ".".join(pkg + ([base] if base else []))
        for a in node.names:
            self.imports.append((base, a.name, a.asname or a.name))


def _dotted(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        inner = _dotted(expr.value)
        return f"{inner}.{expr.attr}" if inner else expr.attr
    return ""


def build_graph(root, include_tests=True):
    root = os.path.abspath(root)
    g = CodeGraph(root=root)
    visitors = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root).replace("\\", "/")
            test = is_test_path(rel)
            if (test and not include_tests) or os.path.getsize(path) > MAX_FILE_BYTES:
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
                tree = ast.parse(src)
            except (SyntaxError, ValueError):
                continue
            g.files[rel] = src
            lines = src.splitlines()
            g.nodes[rel] = Node(rel, "module", rel, module_name(rel).split(".")[-1] or rel,
                                module_name(rel), 1, max(len(lines), 1),
                                doc=_first_doc_line(tree), is_test=test)
            v = _FileVisitor(g, rel, lines, test)
            for stmt in tree.body:
                v.visit(stmt)
            visitors[rel] = v

    mod_by_name = {g.nodes[rel].qualname: rel for rel in visitors}
    for rel, v in visitors.items():
        local = {}  # name visible in this module -> node id
        for nid, n in g.nodes.items():
            if n.file == rel and n.kind != "module" and "." not in n.qualname:
                local[n.name] = nid
        for mod, name, alias in v.imports:
            target_mod = mod_by_name.get(mod)
            if name and f"{mod}.{name}" in mod_by_name:      # from pkg import submodule
                target_mod, name = mod_by_name[f"{mod}.{name}"], None
            if not target_mod:
                continue
            g.add_edge(rel, target_mod, "imports")
            if name:
                tid = f"{target_mod}::{name}"
                if tid in g.nodes:
                    local[alias] = tid
            else:
                local[alias] = target_mod
        for fid, calls in v.calls.items():
            for kind, name in calls:
                if kind == "name" and name in local:
                    tgt = local[name]
                    if g.nodes[tgt].kind == "class":   # constructor call -> __init__
                        init = f"{tgt}.__init__"
                        g.add_edge(fid, init if init in g.nodes else tgt, "calls")
                    else:
                        g.add_edge(fid, tgt, "calls")
                    continue
                cands = [c for c in g.by_name.get(name, []) if g.nodes[c].kind == "function"]
                if kind == "attr":
                    same_file = [c for c in cands if g.nodes[c].file == rel]
                    cands = same_file or cands
                if 0 < len(cands) <= MAX_CALL_CANDIDATES:
                    for c in cands:
                        g.add_edge(fid, c, "calls")
        for cid, bases in v.bases.items():
            for b in bases:
                tgt = local.get(b)
                if tgt is None:
                    cands = [c for c in g.by_name.get(b, []) if g.nodes[c].kind == "class"]
                    tgt = cands[0] if len(cands) == 1 else None
                if tgt:
                    g.add_edge(cid, tgt, "inherits")
    return g
