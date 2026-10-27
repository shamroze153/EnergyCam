"""Writes graphpack_experiments.ipynb (run: python notebooks/build_notebook.py)."""
import json
import os

CELLS = [
("md", """# GraphPack experiments — Gemma 4 Developer Agent Paper Track

Reproduces every number in the paper: localization on the 129 public development tasks of the
Gemma 4 Developer Agent Competition, with Gemma 4 E4B / E2B under fixed token budgets.

**Inputs (right panel → Add Input):** the competition data (`gemma-4-developer-agent`), the
`graphpack-code` dataset, and for steps 3+ the Gemma 4 models `gemma-4-e4b-it-qat-w4a16-ct` and
`gemma-4-e2b-it-qat-w4a16-ct` plus whatever the competition's *Getting Started* notebook attaches for vLLM.

**Steps 0–2 need no GPU** (Settings → Accelerator: None). Steps 3+ need **GPU L4x4, Internet off**.
Nothing in this notebook needs editing."""),
("md", "## 0. Setup and self-test (should end with `ok`)"),
("code", """import os, sys, glob, subprocess, time, json
def find(tail, roots=('/kaggle/input', '/kaggle/working'), depth=6):
    # shallow glob, level by level: a recursive ** over the 20+ GB competition data is slow
    out = []
    for root in roots:
        for d in range(depth):
            out += glob.glob('/'.join([root] + ['*'] * d + [tail]))
    return sorted(set(out))
found = find('graphpack/__init__.py')
assert found, 'add the graphpack-code dataset as an input (right panel -> Add Input -> Your Work)'
CODE_DIR = os.path.dirname(os.path.dirname(found[0]))
COMP = [p for p in find('*gemma-4-developer-agent*', roots=('/kaggle/input',), depth=3)
        if os.path.exists(os.path.join(p, 'tasks.jsonl'))]
assert COMP, 'add the competition data as an input (right panel -> Add Input -> Competitions)'
COMP = COMP[0]
sys.path.insert(0, CODE_DIR)
os.environ['PYTHONPATH'] = CODE_DIR   # for the `!python -m graphpack...` subprocesses
os.makedirs('/kaggle/working/results', exist_ok=True)
os.chdir('/kaggle/working')
print('code:', CODE_DIR, '| competition data:', COMP)
!python {CODE_DIR}/tests/test_smoke.py 2>&1 | tail -1"""),
("md", """## 1. Build `tasks.jsonl` (CPU, ~10 minutes)
Extracts only the `.py` files of each task's snapshot and links the provided graph and embeddings."""),
("code", """!python -m graphpack.prepare_tasks --competition {COMP} --extract-to /kaggle/temp/snapshots --out tasks.jsonl 2>&1 | tail -3
!wc -l tasks.jsonl"""),
("md", """## 2. Retrieval-only results (CPU, ~15 minutes) — first real numbers for the paper
Rankers: `bm25`, `ppr` (our graph, mentions only), `graphpack`, `embed` (provided embeddings),
`graphpack-provided` (PPR over the competition's call graph), `graphpack-embed`."""),
("code", """!python -m graphpack.run --tasks tasks.jsonl --out results/retrieval.jsonl --method retrieval --ranker bm25,ppr,graphpack,embed,graphpack-provided,graphpack-embed 2>&1 | tail -1
!python -m graphpack.report results/retrieval.jsonl --out-dir report/retrieval > /dev/null
print(open('report/retrieval/results.md').read())"""),
("md", """## 3. Serve Gemma 4 E4B with vLLM (GPU L4x4, Internet off)
If this cell says vLLM is missing: open the competition's *Getting Started* notebook, add the same
vLLM input it uses (right panel), and run this cell again."""),
("code", """models = [p for p in find('config.json', roots=('/kaggle/input',), depth=8)
          if 'gemma' in p.lower() and 'developer-agent' not in p]
print('\\n'.join(models))
E4B = next((os.path.dirname(p) for p in models if 'e4b' in p.lower()), None)
E2B = next((os.path.dirname(p) for p in models if 'e2b' in p.lower()), None)
assert E4B, 'add the model gemma-4-e4b-it-qat-w4a16-ct as an input'
try:
    import vllm  # noqa
    print('vllm', vllm.__version__)
except ImportError:
    raise SystemExit('vLLM is not installed and L4 sessions are offline: attach the same vLLM input '
                     'that the competition Getting Started notebook uses, then rerun this cell')
def serve(model_path, name, port=8000, tp=1):
    # E2B/E4B fit on one 24 GB L4; tp=1 avoids head-count/tensor-parallel mismatches
    log = open(f'vllm_{name}.log', 'w')
    proc = subprocess.Popen(['vllm', 'serve', model_path, '--served-model-name', name, '--port', str(port),
                             '--max-model-len', '32768', '--tensor-parallel-size', str(tp),
                             '--gpu-memory-utilization', '0.90'], stdout=log, stderr=subprocess.STDOUT)
    import urllib.request
    for _ in range(180):
        try:
            urllib.request.urlopen(f'http://localhost:{port}/v1/models', timeout=2); break
        except Exception:
            time.sleep(5)
    else:
        raise RuntimeError(open(f'vllm_{name}.log').read()[-3000:])
    os.environ.update(LLM_BASE_URL=f'http://localhost:{port}/v1', LLM_API_KEY='EMPTY', LLM_MODEL=name)
    return proc
server = serve(E4B, 'gemma4-e4b')
!python -m graphpack.run --tasks tasks.jsonl --out results/smoke_e4b.jsonl --method oneshot --budget 2000 --limit 2 2>&1 | tail -2"""),
("md", "## 4. One-shot localization: budget × ranker × packing (main experiment, ~2–3 GPU-hours)"),
("code", """MODEL = 'gemma4-e4b'
BUDGETS = '2000,4000,8000,16000'
for ranker, packs in [('bm25', 'bodies'), ('graphpack', 'bodies,skeleton,hybrid'), ('graphpack-embed', 'hybrid')]:
    !python -m graphpack.run --tasks tasks.jsonl --out results/oneshot_{MODEL}.jsonl --method oneshot --ranker {ranker} --pack {packs} --budget {BUDGETS} --model {MODEL} 2>&1 | tail -1"""),
("md", "## 5. Agents: grep tools vs graph tools vs graph tools + 2k starting pack (~2–3 GPU-hours)"),
("code", """for tools, sp in [('grep', '0'), ('graph', '0,2000')]:
    !python -m graphpack.run --tasks tasks.jsonl --out results/agent_{MODEL}.jsonl --method agent --tools {tools} --turns 15 --start-pack {sp} --context-limit 24000 --model {MODEL} 2>&1 | tail -1"""),
("md", "## 6. Scale: repeat the key configs with E2B (~2 GPU-hours)"),
("code", """assert E2B, 'add the model gemma-4-e2b-it-qat-w4a16-ct as an input'
server.terminate(); server.wait()
server = serve(E2B, 'gemma4-e2b')
MODEL = 'gemma4-e2b'
for ranker, packs in [('bm25', 'bodies'), ('graphpack', 'hybrid')]:
    !python -m graphpack.run --tasks tasks.jsonl --out results/oneshot_{MODEL}.jsonl --method oneshot --ranker {ranker} --pack {packs} --budget {BUDGETS} --model {MODEL} 2>&1 | tail -1
for tools, sp in [('grep', '0'), ('graph', '2000')]:
    !python -m graphpack.run --tasks tasks.jsonl --out results/agent_{MODEL}.jsonl --method agent --tools {tools} --turns 15 --start-pack {sp} --model {MODEL} 2>&1 | tail -1"""),
("md", """## 7. Tables and figure for the paper
`report/<model>/results.md` has every table; `report/gemma4-e4b/budget_curve.png` is Figure 1.
Download `graphpack_results.zip` from the Output tab."""),
("code", """for m in ['gemma4-e4b', 'gemma4-e2b']:
    files = ' '.join(glob.glob(f'results/*_{m}.jsonl') + ['results/retrieval.jsonl'])
    !python -m graphpack.report {files} --out-dir report/{m} > /dev/null
    if os.path.exists(f'report/{m}/results.md'):
        print(open(f'report/{m}/results.md').read())
!cd /kaggle/working && zip -qr graphpack_results.zip results report && ls -la graphpack_results.zip"""),
]


def main():
    nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {
        "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
        "language_info": {"name": "python"}}, "cells": []}
    for i, (kind, src) in enumerate(CELLS):
        cell = {"cell_type": "markdown" if kind == "md" else "code", "id": f"c{i:02d}",
                "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graphpack_experiments.ipynb")
    with open(out, "w") as fh:
        json.dump(nb, fh, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
