"""Writes graphpack_experiments.ipynb (run: python notebooks/build_notebook.py)."""
import json
import os

CELLS = [
("md", """# GraphPack experiments — Gemma 4 Developer Agent Paper Track

Reproduces every number in the paper: localization on the competition's public dev tasks
with Gemma 4 E4B / E2B under fixed token budgets.

**Before running:** Settings → Accelerator **GPU L4x4**, Internet **off** (L4 sessions must be offline;
graphpack itself needs only Python + NumPy). Add Input → the competition dataset, the Gemma 4
model(s) (`gemma-4-e4b-it-qat-w4a16-ct`, `gemma-4-e2b-it-qat-w4a16-ct`), the `graphpack-code`
dataset, and whatever the competition's *Getting Started* notebook attaches to provide vLLM offline.
Results land in `/kaggle/working/results/` and `/kaggle/working/report/`."""),
("code", """import os, sys, glob, subprocess, time, json
# where the graphpack code is (Kaggle Dataset upload or a git clone)
def find(tail, roots=('/kaggle/input', '/kaggle/working'), depth=6):
    # shallow glob, level by level: a recursive ** over the 20+ GB competition data is slow
    out = []
    for root in roots:
        for d in range(depth):
            out += glob.glob('/'.join([root] + ['*'] * d + [tail]))
    return sorted(set(out))
# finds graphpack/ wherever Kaggle mounted the uploaded code dataset
found = find('graphpack/__init__.py')
assert found, 'add the graphpack code as an input dataset (folder containing graphpack/)'
CODE_DIR = os.path.dirname(os.path.dirname(found[0]))
sys.path.insert(0, CODE_DIR)
os.environ['PYTHONPATH'] = CODE_DIR   # for the `!python -m graphpack...` subprocesses
os.chdir('/kaggle/working')
os.makedirs('results', exist_ok=True)
print(CODE_DIR)
!python {CODE_DIR}/tests/test_smoke.py"""),
("md", """## 1. Look at the competition data, then build `tasks.jsonl`
Each task needs: an id, the issue text, the gold patch, and a directory with the **pre-patch** repository.
Run the inspect cell, read the printed keys, and set `SRC` / `REPO_TEMPLATE` / field names below."""),
("code", """COMP = [p for p in find('*gemma-4-developer-agent*', roots=('/kaggle/input',), depth=3) if os.path.isdir(p)]
print(COMP)
!python -m graphpack.prepare_tasks --inspect {COMP[0] if COMP else '/kaggle/input'}"""),
("code", """# EDIT these three lines after looking at the inspect output
SRC = f'{COMP[0]}/dev/tasks.jsonl'                       # the task table
REPO_TEMPLATE = COMP[0] + '/dev/repos/{instance_id}'     # pre-patch snapshot per task
EXTRA = ''   # e.g. '--field-problem-statement issue --field-patch gold_patch'
!python -m graphpack.prepare_tasks --src {SRC} --repo-template "{REPO_TEMPLATE}" {EXTRA} --out tasks.jsonl
!wc -l tasks.jsonl"""),
("md", "## 2. Retrieval-only baselines (CPU, minutes)"),
("code", """for r in ['bm25', 'ppr', 'graphpack']:
    !python -m graphpack.run --tasks tasks.jsonl --out results/retrieval.jsonl --method retrieval --ranker {r}
!python -m graphpack.report results/*.jsonl --out-dir report"""),
("md", """## 3. Serve Gemma 4 with vLLM
Point `MODEL_PATH` at the model you added as input (the folder with `config.json`).
Use the same checkpoint family the main competition allows (E4B, and E2B for the scale comparison)."""),
("code", """MODEL_PATH = [p for p in find('config.json', roots=('/kaggle/input',), depth=8) if 'gemma' in p.lower()
              and 'developer-agent' not in p]
MODEL_PATH_ALL = MODEL_PATH
print(MODEL_PATH)   # pick the E4B one below if several are listed
MODEL_PATH = os.path.dirname(next((p for p in MODEL_PATH if 'e4b' in p.lower()), MODEL_PATH[0]))   # EDIT if wrong
try:
    import vllm  # noqa
    print('vllm', vllm.__version__)
except ImportError:
    raise SystemExit('vLLM is not installed and L4 sessions are offline: attach the same vLLM input '
                     '(wheels/utility script) that the competition Getting Started notebook uses, then rerun')
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
server = serve(MODEL_PATH, 'gemma4-e4b')"""),
("md", "## 4. One-shot localization: budget × ranker × packing (main experiment)"),
("code", """MODEL = 'gemma4-e4b'
GRID = [('bm25', 'bodies'), ('graphpack', 'bodies'), ('graphpack', 'skeleton'), ('graphpack', 'hybrid')]
for budget in [2000, 4000, 8000, 16000]:
    for ranker, mode in GRID:
        !python -m graphpack.run --tasks tasks.jsonl --out results/oneshot_{MODEL}.jsonl --method oneshot \\
            --ranker {ranker} --pack {mode} --budget {budget} --model {MODEL}"""),
("md", "## 5. Agents: grep tools vs graph tools vs graph tools + 2k starting pack"),
("code", """for tools, sp in [('grep', 0), ('graph', 0), ('graph', 2000)]:
    !python -m graphpack.run --tasks tasks.jsonl --out results/agent_{MODEL}.jsonl --method agent \\
        --tools {tools} --turns 15 --start-pack {sp} --context-limit 24000 --model {MODEL}"""),
("md", """## 6. Scale: repeat the key configs with E2B
Stop the E4B server first, add the E2B model as input, then run."""),
("code", """server.terminate(); server.wait()
E2B_PATH = [p for p in MODEL_PATH_ALL if 'e2b' in p.lower()]
print(E2B_PATH)
E2B_PATH = os.path.dirname(E2B_PATH[0])   # EDIT if the wrong one is picked
server = serve(E2B_PATH, 'gemma4-e2b')
MODEL = 'gemma4-e2b'
for budget in [2000, 4000, 8000, 16000]:
    for ranker, mode in [('bm25', 'bodies'), ('graphpack', 'hybrid')]:
        !python -m graphpack.run --tasks tasks.jsonl --out results/oneshot_{MODEL}.jsonl --method oneshot \\
            --ranker {ranker} --pack {mode} --budget {budget} --model {MODEL}
for tools, sp in [('grep', 0), ('graph', 2000)]:
    !python -m graphpack.run --tasks tasks.jsonl --out results/agent_{MODEL}.jsonl --method agent \\
        --tools {tools} --turns 15 --start-pack {sp} --model {MODEL}"""),
("md", """## 7. Tables and figure for the paper
`report/results.md` has every table; `report/budget_curve.png` is Figure 1.
Config names do not contain the model, so report each model's files separately."""),
("code", """for m in ['gemma4-e4b', 'gemma4-e2b']:
    files = ' '.join(glob.glob(f'results/*{m}.jsonl') + ['results/retrieval.jsonl'])
    !python -m graphpack.report {files} --out-dir report/{m}
!python -m graphpack.report results/retrieval.jsonl --out-dir report/retrieval
!cd /kaggle/working && zip -qr graphpack_results.zip results report && ls -la"""),
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
