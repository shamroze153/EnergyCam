> **Draft status.** Every number marked **[R]** comes from `report/results.md` produced by the public notebook. Replace each **[R]** with the measured value before submitting; do not submit with placeholders. Delete this box before submitting.

## Abstract

Small open models running offline fail at repository-level bug fixing mostly *before* they write a patch: they never find the code that has to change. Free-form exploration (grep, open file, scroll) spends the 32k-token context of a consumer-GPU deployment quickly, and small models loop, repeat actions and run out of context. We study localization as a budgeted retrieval problem and introduce **GraphPack**, a dependency-free method that (1) seeds a typed code graph (contains/imports/calls/inherits) with lexical matches, identifier mentions and traceback frames from the issue, (2) spreads relevance with personalized PageRank, and (3) packs the ranked definitions into a fixed token budget as a *hybrid* of full bodies and one-line signatures. We propose the **localization–budget curve** and its normalised area (AUBC) as an evaluation that makes cost a first-class axis, and evaluate Gemma 4 E4B and E2B on the public development tasks of the Gemma 4 Developer Agent Competition. At a 4k-token budget, GraphPack-hybrid reaches **[R]**% function-level Acc@5 versus **[R]**% for BM25 bodies; a graph-tool agent started from a 2k-token GraphPack uses **[R]**× fewer tokens than a grep agent at **[R]** points higher accuracy. Gains concentrate on issues that do not name the faulty symbol (**[R]** points). We release the code, the per-task gold locations and all trajectories.

## 1 Introduction

The Gemma 4 Developer Agent Competition asks for an agent that fixes real Python issues on everyday hardware: one Gemma 4 checkpoint (the bonus prize requires E2B or E4B), internet off, 12 hours for ~120 issues. Pipelines decompose the job into *localize → edit → validate* (Xia et al., 2024). Frontier agents localize by exploring; for small models every opened file costs context they cannot get back, and a wrong first guess compounds over turns.

We ask: **given a token budget B, what should a small model see so that it names the right functions?** Three choices are usually confounded: *what* is ranked (lexical vs graph-propagated relevance), *how* it is rendered (bodies vs signatures), and *who* explores (one-shot context vs multi-turn agent). We separate them on one cost axis.

**Contributions.**

1. **GraphPack**: a standard-library code-graph builder, issue-seeded personalized PageRank and hybrid body/skeleton packing; CPU-only, no network, so it runs inside the competition sandbox (§3).
2. **Localization–budget curves and AUBC**: accuracy as a function of tokens consumed, so one-shot methods and multi-turn agents share one plot (§4).
3. **A study with Gemma 4 E4B and E2B**: 4 budgets × 4 context strategies and 3 agent tool sets, with error analysis by issue type and agent failure mode (§5–6).
4. **A resource**: code, per-task gold function locations, all prompts and trajectories, reproducible from one public notebook.

## 2 Related Work

**Repository-level agents and benchmarks.** SWE-bench (Jimenez et al., 2024) is the standard benchmark; SWE-agent (Yang et al., 2024) showed that the agent–computer interface strongly affects success; OpenHands (Wang et al., 2024) is an open agent platform; AutoCodeRover (Zhang et al., 2024) navigates with AST-aware search. Agentless (Xia et al., 2024) replaces exploration with a fixed hierarchical pipeline; we ask how that trade-off changes when the model is small and the budget fixed.

**Graph-based localization.** RepoGraph (Ouyang et al., 2024) builds a line-level repository graph and feeds ego-graphs to agents. LocAgent (Chen et al., 2025) parses repositories into heterogeneous graphs and fine-tunes models for graph-guided multi-hop localization. OrcaLoca (Yu et al., 2025) combines priority-based action scheduling with context pruning. They report accuracy at fixed configurations; we study the *budget* axis and the rendering choice with consumer-hardware models.

**Ranked repository maps.** Aider's repository map (Gauthier, 2023), the closest prior system, ranks symbols with PageRank over a tree-sitter reference graph within a token budget, personalised to files already in the chat and not evaluated for localization. GraphPack seeds PageRank from the issue, mixes in lexical scores, and is evaluated across budgets.

**Context use and retrieval.** Models use long contexts unevenly (Liu et al., 2024), motivating small ranked contexts. BM25 (Robertson & Zaragoza, 2009) is the standard lexical baseline; personalized PageRank (Haveliwala, 2002) spreads query relevance over a graph.

**Training small SWE agents.** SWE-Gym (Pan et al., 2024) and SWE-smith (Yang et al., 2025) build training data for open models, often with LoRA (Hu et al., 2022). GraphPack is training-free and complementary: its output can be any fine-tuned agent's first observation.

## 3 Method

### 3.1 Code graph

For a repository snapshot we parse every `.py` file with Python's `ast` module and create one node per module, class and function (methods and nested functions included), keyed `path.py::Qual.name` with line span, one-line signature (decorators and header) and first docstring line. Edges:

| edge | from → to | resolution |
|---|---|---|
| contains | module → class/function, class → method | syntactic |
| imports | module → module | absolute and relative imports, `src/` layouts; intra-repo only |
| calls | function → function | `f()` resolved through local definitions and imported aliases; `x.f()` linked to all definitions named `f` (same file preferred), only if there are ≤ 5 candidates; `C()` → `C.__init__` |
| inherits | class → base class | local/imported name, else unique global name |

Call resolution is deliberately conservative: an unresolvable method name (e.g. `get`) with many candidates produces no edge rather than a hub. Building the graph takes **[R]** s for the largest development repository on a single CPU core.

### 3.2 Issue-seeded ranking

Given issue text *q*, GraphPack scores every class/function node *v* (tests excluded):

1. **Lexical score** `lex(v)`: BM25 over the node's path, qualified name and source, with identifiers split on `snake_case` and `camelCase` and both forms indexed.
2. **Seeds** `s(v)`: traceback frames `File "...", line n, in f` mapped to the innermost node covering line *n* (weight 3); identifiers in *q* that name ≤ 8 definitions (weight 1/#candidates); file paths in *q*; and the top-10 BM25 nodes (weight `lex/max lex`).
3. **Propagation**: personalized PageRank with restart distribution ∝ *s* over the undirected, weighted graph (calls 1.0, contains 1.0, inherits 0.7, imports 0.3; damping 0.85, 40 iterations), giving `ppr(v)`.
4. **Score**: `λ·norm(lex) + (1−λ)·norm(ppr)` with min–max normalisation and λ = 0.5; traceback-seeded nodes are pinned to the top.

### 3.3 Budgeted packing

The ranked list is rendered, grouped by file in order of first appearance, until the budget *B* (≈ 4 characters per token) is spent:

- **bodies**: full numbered source of each node (capped at 60 lines);
- **skeleton**: one line per node, `signature  # Qual.name, lines a–b`;
- **hybrid**: bodies until 60% of *B*, then skeleton lines for the rest.

Skeletons show many more candidates per token; bodies let the model discriminate. Hybrid tests whether a small model benefits from both.

### 3.4 Localizers

- **Retrieval only**: the ranking itself (bm25, ppr, graphpack); no LLM.
- **One-shot**: one call with the issue and the packed context; the model returns up to 10 ranked `path::Qual.name` locations as JSON. Model-named locations are resolved to graph nodes (exact id, `path:line`, or unique suffix match) and the list is backfilled with the retrieval order so that Acc@k is defined for every k.
- **Agent**: a ReAct-style loop (one JSON tool call per turn, ≤ 15 turns, observations truncated to 1.5k tokens, conversation capped at 24k tokens). *grep* tools: `search(regex)` (standing in for `run_command("grep …")`), `read_file`, `list_dir`, `submit`. *graph* tools add the competition harness's `get_code_neighbors`, `get_code_subgraph` and `search_similar_code` (same names and arguments; here backed by our graph and, for similarity, BM25), plus `find_symbol` and `skeleton(path)`. Optionally the first message includes a 2k-token GraphPack skeleton.

## 4 Experimental Setup

**Tasks.** The 129 public development tasks of the Gemma 4 Developer Agent Competition (repositories `fastapi`, `rich`, `requests`, `httpx`). Each provides an issue, a pre-patch snapshot and a reference patch. **[R: number of tasks used after filtering, and why any were dropped]**

**Gold locations.** We parse the reference patch and map every touched pre-patch line (for pure insertions, the line above) to the innermost enclosing class/function in the snapshot. Test files, non-Python files and new files are excluded from function-level gold; **[R]** tasks have at least one gold function and **[R]**% touch more than one file.

**Metrics.** *File Acc@k*: all gold files are in the top-k files. *Function Acc@k*: all gold functions are in the top-k functions (LocAgent's strict definition); we also report Hit@k (any gold function). *Gold-in-context*: every gold function was shown in the packed context, which separates retrieval failures from selection failures. Cost: prompt + completion tokens, LLM calls and wall-clock per task. 95% confidence intervals use a 2,000-sample task bootstrap.

**Localization–budget curve and AUBC.** For a method family we plot Function Acc@5 against mean tokens per task on a log₂ axis and integrate between 2k and 32k tokens, holding the curve flat outside measured points and normalising so that 1.0 means perfect accuracy at every budget. Agents, which do not have a budget knob, appear as single points on the same axes.

**Models and serving.** `gemma-4-e4b-it-qat-w4a16-ct` and `gemma-4-e2b-it-qat-w4a16-ct`, the two small checkpoints allowed by the competition, served with vLLM (max length 32,768, temperature 0, max 1,024 output tokens) on one NVIDIA L4 (24 GB) of a Kaggle L4x4 machine, offline. All prompts are listed in the released code (`graphpack/localize.py`).

**Grid.** One-shot: budgets {2k, 4k, 8k, 16k} × {bm25-bodies, graphpack-bodies, graphpack-skeleton, graphpack-hybrid}. Agents: grep, graph, graph + 2k start pack. E2B repeats bm25-bodies, graphpack-hybrid, grep agent and graph + start pack. Total compute: **[R]** GPU-hours.

## 5 Results

### 5.1 Retrieval alone

| ranker | File Acc@1 | File Acc@5 | Func Acc@5 | Func Acc@10 |
|---|---|---|---|---|
| BM25 | [R] | [R] | [R] | [R] |
| PPR (seeds only) | [R] | [R] | [R] | [R] |
| GraphPack (BM25 + PPR) | [R] | [R] | [R] | [R] |

*Table 1. Retrieval without an LLM on the development tasks (%).* **[R: one or two sentences — does graph propagation add to BM25, and on which repositories?]**

### 5.2 One-shot localization under a budget

| context (E4B) | 2k | 4k | 8k | 16k | AUBC |
|---|---|---|---|---|---|
| BM25, bodies | [R] | [R] | [R] | [R] | [R] |
| GraphPack, bodies | [R] | [R] | [R] | [R] | [R] |
| GraphPack, skeleton | [R] | [R] | [R] | [R] | [R] |
| GraphPack, hybrid | [R] | [R] | [R] | [R] | [R] |

*Table 2. Function Acc@5 (%) of Gemma 4 E4B by budget, and AUBC.* Figure 1 (`report/budget_curve.png`) plots the same data with agents as points.

**[R: Describe the shape of the curves. Questions to answer from the data: (a) Which context wins at the smallest budget? (b) Does accuracy saturate or fall at 16k (a "too much context" effect for small models)? (c) Gold-in-context vs Acc@5: how large is the selection gap, i.e. the model saw the gold function but did not rank it?]**

### 5.3 Agents

| agent (E4B) | Func Acc@5 | tokens / task | calls | invalid actions | repeated actions | ran out of context |
|---|---|---|---|---|---|---|
| grep tools | [R] | [R] | [R] | [R] | [R] | [R]% |
| graph tools | [R] | [R] | [R] | [R] | [R] | [R]% |
| graph tools + 2k pack | [R] | [R] | [R] | [R] | [R] | [R]% |
| best one-shot (for reference) | [R] | [R] | 1 | – | – | – |

*Table 3. Agent localization with Gemma 4 E4B.* **[R: Is the best agent better than the best one-shot context at equal tokens? Which failure mode dominates the grep agent?]**

### 5.4 Model scale

| method | E2B Func Acc@5 | E4B Func Acc@5 |
|---|---|---|
| BM25 bodies, 4k | [R] | [R] |
| GraphPack hybrid, 4k | [R] | [R] |
| grep agent | [R] | [R] |
| graph agent + 2k pack | [R] | [R] |

*Table 4. Effect of model size.* **[R: Does the benefit of structured context grow as the model shrinks?]**

## 6 Analysis

**By issue type.** We slice tasks by whether the issue contains a traceback, names a gold symbol, names a gold file, or needs a multi-file fix (`report/results.md`, "Slices").

| slice | n | BM25 bodies 4k | GraphPack hybrid 4k | graph agent + pack |
|---|---|---|---|---|
| traceback present | [R] | [R] | [R] | [R] |
| gold symbol named | [R] | [R] | [R] | [R] |
| no symbol, no traceback | [R] | [R] | [R] | [R] |
| multi-file fix | [R] | [R] | [R] | [R] |

*Table 5. Function Acc@5 (%) by issue slice.* Our hypothesis, stated before running, was that traceback issues are easy for every method and that graph propagation helps most on behavioural issues that name neither a file nor a symbol. **[R: confirmed or not, with numbers.]**

**Failure taxonomy.** We sample **[R: e.g. 30]** failed E4B tasks per best method and label each as: (i) gold not in context (retrieval miss), (ii) gold in context but not ranked (selection miss), (iii) gold partly found (multi-location fix), (iv) invalid/unparseable output, (v) agent loop or context exhaustion. **[R: counts and one illustrative example per category, quoting the trajectory file.]**

**Cost on consumer hardware.** Graph construction and ranking take **[R]** s per task on CPU; a one-shot call at 4k tokens takes **[R]** s on **[R GPU]**, versus **[R]** s for a 15-turn agent. For the main competition's 12-hour budget over ~120 tasks (6 minutes per task), localization cost decides how many repair attempts remain.

## 7 Limitations

The development set is small (129 tasks, four repositories), so we report bootstrap intervals. A single reference patch under-counts valid alternative fixes. Call edges are name-resolved, not type-resolved, so dynamic dispatch can hide edges. Packing approximates 4 characters per token; reported costs use server token counts. We evaluate localization, not end-to-end resolution (§8).

## 8 Use in a Full Agent and Generality

GraphPack needs only Python and NumPy, so it can ship inside a competition submission as an ADK skill whose script prints the pack as the agent's first observation, next to the harness's own graph tools, without changing the model. Nothing is specific to the development repositories or to Gemma; the graph schema maps directly onto tree-sitter parsers for other languages, and the budget-curve protocol applies to any localizer, including fine-tuned ones.

## 9 Conclusion

For a small offline model, what it reads matters as much as how it reasons. Issue-seeded graph ranking with hybrid packing lets Gemma 4 E4B localize **[R]**% of development-task bugs within **[R]** tokens. We release GraphPack, the protocol and all trajectories so small-model agents can be compared on cost as well as accuracy.

## Reproducibility

Code, notebook and results: **[link to public notebook]**, **[link to public code repository or Kaggle dataset]**. One notebook (`graphpack_experiments.ipynb`) rebuilds the task file, runs every configuration, and writes the tables in this paper. Runs are deterministic (temperature 0; fixed bootstrap seed).

## References

- Chen, Z., et al. (2025). LocAgent: Graph-Guided LLM Agents for Code Localization. *ACL 2025*. arXiv:2503.09089.
- Gauthier, P. (2023). Building a better repository map with tree sitter. Aider blog, aider.chat.
- Gemma Team, Google DeepMind (2026). Gemma 4 model card. ai.google.dev/gemma.
- Haveliwala, T. H. (2002). Topic-sensitive PageRank. *WWW 2002*.
- Hu, E. J., et al. (2022). LoRA: Low-Rank Adaptation of Large Language Models. *ICLR 2022*.
- Jimenez, C. E., et al. (2024). SWE-bench: Can Language Models Resolve Real-World GitHub Issues? *ICLR 2024*.
- Liu, N. F., et al. (2024). Lost in the Middle: How Language Models Use Long Contexts. *TACL*, 12.
- Markowitz, E., et al. (2026). Google – The Gemma 4 Developer Agent Paper Track. Kaggle.
- Ouyang, S., et al. (2024). RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph. arXiv:2410.14684.
- Pan, J., et al. (2024). Training Software Engineering Agents and Verifiers with SWE-Gym. arXiv:2412.21139.
- Robertson, S., & Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond. *Foundations and Trends in IR*, 3(4).
- Wang, X., et al. (2024). OpenHands: An Open Platform for AI Software Developers as Generalist Agents. arXiv:2407.16741.
- Xia, C. S., Deng, Y., Dunn, S., & Zhang, L. (2024). Agentless: Demystifying LLM-based Software Engineering Agents. arXiv:2407.01489.
- Yang, J., et al. (2024). SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. *NeurIPS 2024*.
- Yang, J., et al. (2025). SWE-smith: Scaling Data for Software Engineering Agents. arXiv:2504.21798.
- Yu, Z., et al. (2025). OrcaLoca: An LLM Agent Framework for Software Issue Localization. arXiv:2502.00350.
- Zhang, Y., Ruan, H., Fan, Z., & Roychoudhury, A. (2024). AutoCodeRover: Autonomous Program Improvement. *ISSTA 2024*.
