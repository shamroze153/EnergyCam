# Gemma 4 Developer Agent — Paper Track submission kit

**Paper:** *GraphPack: Budgeted Code-Graph Context for Small Offline Coding Agents*
(draft: [`paper/writeup.md`](paper/writeup.md))

**Deadline: Thu 12 Nov 2026, 23:59 UTC = Fri 13 Nov 2026, 4:59 AM PKT.** A draft
Writeup that has not been **submitted** by then does not count.

## 1. What the competition requires (and where each item is)

| Requirement | Status / where |
|---|---|
| Join the Paper Track competition on Kaggle | **You do this** (Join / accept rules) |
| Kaggle Writeup, ≤ 3,000 words, original + unpublished | `paper/writeup.md` (~2,500 words + references, results still to fill) |
| Title and subtitle | Top of the writeup |
| Abstract | §Abstract |
| Introduction | §1 |
| Methods and experiments | §3 Method, §4 Setup, §5 Results, §6 Analysis |
| Related work and citations | §2 + References |
| Public notebook (optional, but strongly recommended for *Verifiability*) | `notebooks/graphpack_experiments.ipynb` |
| PDF version (optional) | Not needed; writing directly in the Writeup is fine |

Judges score 5 criteria equally, 0–5 each: **Novelty, Quality (generality), Relevance,
Verifiability, Clarity.** How this paper targets each:

- **Novelty**: budget as a first-class axis (localization–budget curve + AUBC), and the
  bodies vs skeleton vs hybrid packing question for *small* models; closest prior work
  (Aider repo map, LocAgent, RepoGraph, Agentless) is cited and the difference stated.
- **Quality**: method has no repo-specific parts; any Python repo, any model, any harness.
- **Relevance**: localization is the bottleneck for small offline agents, which is exactly
  the competition's problem.
- **Verifiability**: one public notebook regenerates every number; gold labels, prompts,
  trajectories released; bootstrap CIs; temperature 0.
- **Clarity**: one question, three variables, one plot.

Prize to aim for: **Overall Best Paper**, with **Best New Resource** as the second
chance (GraphPack library + gold-location labels + budget-curve protocol). The Kaggle
form may ask which award you are entering; pick the one the form allows and mention the
resource in the subtitle/abstract either way.

## 2. Timeline (17 days)

| Dates | Work |
|---|---|
| 27–29 Oct | Join competition. Upload this folder as a Kaggle Dataset (`graphpack-code`). Run notebook cells 1–2: inspect the data, build `tasks.jsonl`, run retrieval baselines (CPU only). |
| 30 Oct–3 Nov | Serve Gemma 4 E4B, run the one-shot grid (16 configs × ~129 tasks, est. 2–3 GPU-h) and the 3 agents (est. 2–3 GPU-h). |
| 4–5 Nov | E2B runs (est. 2 GPU-h). Run `report`. |
| 6–8 Nov | Fill every **[R]** in the writeup from `report/*/results.md`. Do the failure taxonomy: read ~30 failed trajectories, count categories. |
| 9–10 Nov | Make the notebook public, put the figure in the Writeup, final read, word count ≤ 3,000. |
| **11 Nov** | **Submit** (one day of margin before the deadline). |

GPU estimates are rough; Kaggle gives ~30 GPU-hours/week, and L4x4 is charged at 2×.
Runs resume where they stopped (`graphpack.run` skips finished tasks), so a session
timeout loses nothing.

## 3. How to run

Local check (no GPU, no internet):

```bash
cd gemma4-paper-track
python tests/test_smoke.py          # prints "ok"
```

On Kaggle: open `notebooks/graphpack_experiments.ipynb` (File → Import Notebook), attach it
to the main competition, choose **GPU L4x4 with Internet OFF** (L4 sessions must be offline),
add the inputs — the competition dataset, `gemma-4-e4b-it-qat-w4a16-ct` (and later
`gemma-4-e2b-it-qat-w4a16-ct`), this folder as a dataset, and the vLLM input the competition's
*Getting Started* notebook uses — and run top to bottom. The two cells marked **EDIT** need paths: run the `--inspect` cell
first, it prints the dataset tree and the keys of the task table.

Quick iteration without a GPU (a CPU session with Internet on, not L4): any
OpenAI-compatible endpoint works, e.g. Gemma 4 on Google AI Studio:

```bash
export LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
export LLM_API_KEY=<your AI Studio key>
export LLM_MODEL=gemma-4-26b-a4b-it     # use the same model id that works for gemma_room_check.py
python -m graphpack.run --tasks tasks.jsonl --out results/try.jsonl --method oneshot --budget 4000 --limit 5
```

Use this only to debug prompts. **Paper numbers must come from the local E4B/E2B runs**
(the paper is about consumer hardware).

Single commands:

```bash
python -m graphpack.run --tasks tasks.jsonl --out results/r.jsonl --method retrieval --ranker graphpack
python -m graphpack.run --tasks tasks.jsonl --out results/o.jsonl --method oneshot --ranker graphpack --pack hybrid --budget 4000
python -m graphpack.run --tasks tasks.jsonl --out results/a.jsonl --method agent --tools graph --start-pack 2000
python -m graphpack.report results/*.jsonl --out-dir report
```

## 4. Code map

| File | What it does |
|---|---|
| `graphpack/graph.py` | `ast` code graph: module/class/function nodes; contains, imports, calls, inherits edges |
| `graphpack/retrieval.py` | BM25, issue seeds (traceback/identifiers/paths), personalized PageRank, budgeted packing |
| `graphpack/gold.py` | Gold functions from the reference patch |
| `graphpack/localize.py` | Retrieval-only, one-shot and agent localizers (all prompts are here) |
| `graphpack/llm.py` | OpenAI-compatible client (vLLM / AI Studio) |
| `graphpack/metrics.py` | Acc@k, Hit@k, issue slices, AUBC |
| `graphpack/run.py`, `report.py` | Experiment runner (resumable) and tables/CSV/figure |
| `graphpack/prepare_tasks.py` | Inspect the competition data and write `tasks.jsonl` |
| `notebooks/` | Kaggle notebook (rebuild with `python notebooks/build_notebook.py`) |

## 5. Before you submit: must-check list

- [ ] **No [R] left** in the writeup, and every number matches `report/*/results.md`.
- [ ] If a hypothesis turned out false, the text says so. Negative results are fine and
      still publishable; invented numbers disqualify.
- [ ] Check the task facts against the official Data page / `HARNESS_README.md`: 129 dev
      tasks and the four repos came from a community source. (Model names and the harness
      tools are confirmed from the official Overview.)
- [ ] Open each reference once (arXiv IDs, venues) and fix any that are off.
- [ ] Notebook is **public** and linked in Project Links; code dataset is public.
- [ ] The code you publish contains nothing from EnergyCam or any `.env`/secret. Upload
      only the `gemma4-paper-track` folder (or put it in its own public GitHub repo).
- [ ] Word count ≤ 3,000 (if over, shorten §2 Related Work first).
- [ ] Figure 1 (`report/gemma4-e4b/budget_curve.png`) is attached in the Writeup.
- [ ] Clicked **Submit** (top right of the Writeup), not just Save.
