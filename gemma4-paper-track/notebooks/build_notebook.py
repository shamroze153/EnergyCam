"""Writes graphpack_experiments.ipynb (run: python notebooks/build_notebook.py)."""
import json
import os

CELLS = [
("md", """# GraphPack experiments — Gemma 4 Developer Agent Paper Track

Reproduces every number in the paper on the 129 public development tasks of the Gemma 4 Developer
Agent Competition. Nothing needs editing.

**How to run:** Settings → Accelerator **GPU L4x4**, Internet **off**. Inputs (right panel → Add Input):
the competition data, the `graphpack-code` dataset, the models `gemma-4-e4b-it-qat-w4a16-ct` and
`gemma-4-e2b-it-qat-w4a16-ct`, and the vLLM input used by the competition's *Getting Started* notebook.
Then **Save Version → Save & Run All (Commit)**. Results: Output tab → `graphpack_results.zip`.

Without a GPU, steps 0–2 still run (retrieval-only results) and later steps stop with a message."""),
("md", "## 0. Setup and self-test"),
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
os.environ['PYTHONPATH'] = CODE_DIR   # for the `!PYTHONPATH={CODE_DIR} {sys.executable} -m graphpack...` subprocesses
os.chdir('/kaggle/working')
for d in ('results', 'logs', 'report'):
    os.makedirs(d, exist_ok=True)
print('code:', CODE_DIR, '| competition data:', COMP)
!{sys.executable} {CODE_DIR}/tests/test_smoke.py 2>&1 | tail -1"""),
("md", "## 1. Build `tasks.jsonl` (CPU, ~10 minutes)"),
("code", """!PYTHONPATH={CODE_DIR} {sys.executable} -m graphpack.prepare_tasks --competition {COMP} --extract-to /kaggle/temp/snapshots --out tasks.jsonl 2>&1 | tail -2
!wc -l tasks.jsonl"""),
("md", "## 2. Retrieval-only results (CPU, ~15 minutes)"),
("code", """!PYTHONPATH={CODE_DIR} {sys.executable} -m graphpack.run --tasks tasks.jsonl --out results/retrieval.jsonl --method retrieval --ranker bm25,ppr,graphpack,embed,graphpack-provided,graphpack-embed 2>&1 | tail -1
!PYTHONPATH={CODE_DIR} {sys.executable} -m graphpack.report results/retrieval.jsonl --out-dir report/retrieval > /dev/null
print(open('report/retrieval/results.md').read())"""),
("md", """## 3. Start Gemma 4 E4B: one vLLM server per GPU
Each L4 serves its own copy of the model; the runs below are split across them."""),
("code", """models = [p for p in find('config.json', roots=('/kaggle/input',), depth=8)
          if 'gemma' in p.lower() and 'developer-agent' not in p]
print('\\n'.join(models) or 'no Gemma model inputs found')
E4B = next((os.path.dirname(p) for p in models if 'e4b' in p.lower()), None)
E2B = next((os.path.dirname(p) for p in models if 'e2b' in p.lower()), None)
assert E4B, 'add the model gemma-4-e4b-it-qat-w4a16-ct as an input'
try:
    import vllm  # noqa
except ImportError:
    # offline: install from any attached input that carries a vLLM wheel
    wheels = find('vllm-*.whl', roots=('/kaggle/input',), depth=6)
    if wheels:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-index', '--find-links',
                        os.path.dirname(wheels[0]), wheels[0]], check=False)
    try:
        import vllm  # noqa
    except ImportError:
        raise SystemExit('vLLM is not installed and L4 sessions are offline: attach the same vLLM input '
                         'that the competition Getting Started notebook uses, then run again')
print('vllm', vllm.__version__)
try:
    import torch
    N_GPUS = max(1, torch.cuda.device_count())
except Exception:
    N_GPUS = 1
print('GPUs:', N_GPUS)
EXTRA = json.dumps({'chat_template_kwargs': {'enable_thinking': False}})

def serve_all(model_path, name):
    procs = []
    for g in range(N_GPUS):
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g))
        procs.append(subprocess.Popen(
            [sys.executable, '-m', 'vllm.entrypoints.openai.api_server', '--model', model_path,
             '--served-model-name', name, '--port', str(8000 + g), '--max-model-len', '32768',
             '--gpu-memory-utilization', '0.90'],
            env=env, stdout=open(f'logs/vllm_{name}_{g}.log', 'w'), stderr=subprocess.STDOUT))
    import urllib.request
    for g in range(N_GPUS):
        for _ in range(240):
            if procs[g].poll() is not None:
                break
            try:
                urllib.request.urlopen(f'http://localhost:{8000 + g}/v1/models', timeout=2); break
            except Exception:
                time.sleep(5)
        else:
            pass
        try:
            urllib.request.urlopen(f'http://localhost:{8000 + g}/v1/models', timeout=2)
        except Exception:
            print(open(f'logs/vllm_{name}_{g}.log').read()[-4000:])
            raise SystemExit(f'vLLM server on GPU {g} did not start; the log is printed above')
    print(name, 'ready on', N_GPUS, 'GPU(s)')
    return procs

def stop_all(procs):
    for p in procs:
        p.terminate()
    for p in procs:
        p.wait()

def run_parallel(name, args, model, workers_per_gpu=2):
    n = N_GPUS * workers_per_gpu
    procs = []
    for k in range(n):
        env = dict(os.environ, LLM_BASE_URL=f'http://localhost:{8000 + k % N_GPUS}/v1', LLM_API_KEY='EMPTY',
                   LLM_MODEL=model, LLM_EXTRA_BODY=EXTRA, PYTHONPATH=CODE_DIR)
        cmd = [sys.executable, '-m', 'graphpack.run', '--tasks', 'tasks.jsonl', '--shard', f'{k}/{n}',
               '--out', f'results/{name}_{model}.shard{k}.jsonl', '--model', model] + args
        procs.append(subprocess.Popen(cmd, env=env, stdout=open(f'logs/{name}_{model}_{k}.log', 'w'),
                                      stderr=subprocess.STDOUT))
    t0 = time.time()
    for p in procs:
        p.wait()
    rows = sum(1 for f in glob.glob(f'results/{name}_{model}.shard*.jsonl') for _ in open(f))
    print(f'{name} {model}: {rows} result rows in {(time.time() - t0) / 60:.0f} min')

server = serve_all(E4B, 'gemma4-e4b')"""),
("md", "## 4. Check that the model's replies parse (2 tasks) before spending GPU hours"),
("code", """env = dict(os.environ, LLM_BASE_URL='http://localhost:8000/v1', LLM_API_KEY='EMPTY', LLM_MODEL='gemma4-e4b', LLM_EXTRA_BODY=EXTRA)
subprocess.run([sys.executable, '-m', 'graphpack.run', '--tasks', 'tasks.jsonl', '--out', 'results/smoke.jsonl',
                '--method', 'oneshot', '--budget', '2000', '--limit', '2'], env=env)
smoke = [json.loads(l) for l in open('results/smoke.jsonl')]
for r in smoke:
    print(r['instance_id'], 'parse_ok =', r.get('parse_ok'), '| model said:', r.get('model_locations'), '| error:', r.get('error'))
if not any(r.get('parse_ok') for r in smoke):
    raise SystemExit('The model replies did not parse as JSON; check results/smoke.jsonl and logs/vllm_*.log')"""),
("md", "## 5. E4B one-shot grid (budget × ranker × packing) and agents"),
("code", """B = '2000,4000,8000,16000'
run_parallel('oneshot', ['--method', 'oneshot', '--ranker', 'bm25', '--pack', 'bodies', '--budget', B], 'gemma4-e4b')
run_parallel('oneshot', ['--method', 'oneshot', '--ranker', 'graphpack', '--pack', 'bodies,skeleton,hybrid', '--budget', B], 'gemma4-e4b')
run_parallel('agent', ['--method', 'agent', '--tools', 'grep', '--start-pack', '0', '--turns', '15'], 'gemma4-e4b')
run_parallel('agent', ['--method', 'agent', '--tools', 'graph', '--start-pack', '0,2000', '--turns', '15'], 'gemma4-e4b')
stop_all(server)"""),
("md", "## 6. E2B: the key configurations again (model scale)"),
("code", """if E2B:
    server = serve_all(E2B, 'gemma4-e2b')
    run_parallel('oneshot', ['--method', 'oneshot', '--ranker', 'bm25', '--pack', 'bodies', '--budget', B], 'gemma4-e2b')
    run_parallel('oneshot', ['--method', 'oneshot', '--ranker', 'graphpack', '--pack', 'hybrid', '--budget', B], 'gemma4-e2b')
    run_parallel('agent', ['--method', 'agent', '--tools', 'grep', '--start-pack', '0', '--turns', '15'], 'gemma4-e2b')
    run_parallel('agent', ['--method', 'agent', '--tools', 'graph', '--start-pack', '2000', '--turns', '15'], 'gemma4-e2b')
    stop_all(server)
else:
    print('E2B model not attached: skipping the model-scale runs')"""),
("md", "## 7. Tables, figure and the results archive"),
("code", """for m in ['gemma4-e4b', 'gemma4-e2b']:
    files = sorted(glob.glob(f'results/*_{m}.shard*.jsonl'))
    if not files:
        continue
    files_arg = ' '.join(files + ['results/retrieval.jsonl'])
    !PYTHONPATH={CODE_DIR} {sys.executable} -m graphpack.report {files_arg} --out-dir report/{m} > /dev/null
    print(open(f'report/{m}/results.md').read())
!cd /kaggle/working && zip -qr graphpack_results.zip results report logs && ls -la graphpack_results.zip"""),
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
