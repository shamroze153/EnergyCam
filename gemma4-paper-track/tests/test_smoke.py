"""End-to-end checks on a tiny generated repository (no network, no GPU).

  python -m pytest tests -q        or        python tests/test_smoke.py
"""
import json
import os
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graphpack import report, run  # noqa: E402
from graphpack.gold import changed_lines, gold_locations  # noqa: E402
from graphpack.graph import build_graph  # noqa: E402
from graphpack.llm import ScriptedLLM, parse_json  # noqa: E402
from graphpack.localize import resolve_location, run_agent, run_oneshot  # noqa: E402
from graphpack.metrics import aubc, score  # noqa: E402
from graphpack.retrieval import Index, pack, rank  # noqa: E402

FILES = {
    "shop/__init__.py": "from .cart import Cart\n",
    "shop/pricing.py": textwrap.dedent('''\
        """Price helpers."""


        def apply_discount(total, percent):
            """Return total after a percentage discount."""
            return total - total * percent / 10


        def add_tax(total, rate=0.17):
            return total * (1 + rate)
        '''),
    "shop/cart.py": textwrap.dedent('''\
        from .pricing import apply_discount, add_tax


        class Cart:
            def __init__(self):
                self.items = []

            def add(self, name, price):
                self.items.append((name, price))

            def checkout(self, coupon=0):
                total = sum(p for _, p in self.items)
                return add_tax(apply_discount(total, coupon))
        '''),
    "tests/test_cart.py": textwrap.dedent('''\
        from shop.cart import Cart


        def test_checkout():
            c = Cart()
            c.add("pen", 100)
            assert round(c.checkout(10), 2) == 105.3
        '''),
}

PATCH = textwrap.dedent('''\
    diff --git a/shop/pricing.py b/shop/pricing.py
    --- a/shop/pricing.py
    +++ b/shop/pricing.py
    @@ -4,4 +4,4 @@
     def apply_discount(total, percent):
         """Return total after a percentage discount."""
    -    return total - total * percent / 10
    +    return total - total * percent / 100

    ''')

ISSUE = "Cart checkout with a 10% coupon charges almost nothing: the discount is ten times too big."


def make_repo(root):
    for rel, src in FILES.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(src)


def test_all():
    with tempfile.TemporaryDirectory() as tmp:
        repo = os.path.join(tmp, "repo")
        make_repo(repo)
        g = build_graph(repo)
        assert "shop/pricing.py::apply_discount" in g.nodes
        assert g.edges["shop/cart.py::Cart.checkout"]["shop/pricing.py::apply_discount"] == "calls"
        assert g.edges["shop/cart.py"]["shop/pricing.py"] == "imports"
        assert g.edges["tests/test_cart.py::test_checkout"]["shop/cart.py::Cart.__init__"] == "calls"

        lines, new = changed_lines(PATCH)
        assert lines == {"shop/pricing.py": [6]} and not new
        files, nodes = gold_locations(g, PATCH)
        assert files == ["shop/pricing.py"] and nodes == ["shop/pricing.py::apply_discount"]

        index = Index(g)
        ranked = rank(index, ISSUE, "graphpack")
        assert "shop/pricing.py::apply_discount" in ranked[:3], ranked
        text, shown = pack(g, ranked, 300, mode="hybrid")
        assert "### shop/pricing.py" in text and shown

        assert resolve_location(g, "shop/pricing.py::apply_discount") == "shop/pricing.py::apply_discount"
        assert resolve_location(g, "./shop/pricing.py:6") == "shop/pricing.py::apply_discount"
        assert resolve_location(g, "shop/cart.py::checkout") == "shop/cart.py::Cart.checkout"
        assert parse_json('sure!\n```json\n{"a": 1}\n```') == {"a": 1}

        llm = ScriptedLLM(['{"locations": ["shop/pricing.py::apply_discount"]}'])
        rec = run_oneshot(index, ISSUE, llm, budget=500)
        assert rec["nodes"][0] == "shop/pricing.py::apply_discount" and rec["parse_ok"]
        assert score(rec["files"], rec["nodes"], files, nodes)["func_acc@1"] == 1.0

        llm = ScriptedLLM([
            '{"thought": "look", "tool": "search", "args": {"pattern": "percent"}}',
            '{"thought": "look", "tool": "get_code_neighbors", "args": {"node": "shop/cart.py::Cart.checkout", "edge_type": "calls"}}',
            '{"thought": "done", "tool": "submit", "args": {"locations": ["shop/pricing.py::apply_discount"]}}',
        ])
        rec = run_agent(index, ISSUE, llm, tools="graph", max_turns=5, start_pack=200)
        assert rec["stop_reason"] == "submit" and rec["turns"] == 3
        assert rec["nodes"][0] == "shop/pricing.py::apply_discount"
        assert "percent / 10" in llm.calls[1][-1]["content"]          # search observation
        assert "apply_discount" in llm.calls[2][-1]["content"]        # neighbors observation
        from graphpack.localize import run_tool
        assert "Cart.checkout -calls-> shop/pricing.py::apply_discount" in run_tool(
            index, "get_code_subgraph", {"nodes": ["shop/cart.py::Cart.checkout", "shop/pricing.py::apply_discount"]})
        assert "105.3" not in run_tool(index, "read_file", {"filepath": "shop/pricing.py", "start_line": 4, "end_line": 6})
        assert run_tool(index, "search_similar_code", {"query": "discount percent"}).startswith("shop/pricing.py::apply_discount")

        # CLI round trip: run -> results.jsonl -> report
        tasks = os.path.join(tmp, "tasks.jsonl")
        with open(tasks, "w") as fh:
            fh.write(json.dumps({"instance_id": "shop-1", "repo_dir": repo,
                                 "problem_statement": ISSUE, "patch": PATCH}) + "\n")
        out = os.path.join(tmp, "res.jsonl")
        for ranker in ("bm25", "graphpack"):
            run.main(["--tasks", tasks, "--out", out, "--method", "retrieval", "--ranker", ranker])
            run.main(["--tasks", tasks, "--out", out, "--method", "retrieval", "--ranker", ranker])  # resumes
        rows = [json.loads(l) for l in open(out)]
        assert [r["config"] for r in rows] == ["retrieval-bm25", "retrieval-graphpack"]  # reruns resumed
        report.main([out, "--out-dir", os.path.join(tmp, "rep")])
        assert os.path.exists(os.path.join(tmp, "rep", "results.md"))

    assert abs(aubc([(2000, 0.5), (32000, 0.5)]) - 0.5) < 1e-9


if __name__ == "__main__":
    test_all()
    print("ok")
