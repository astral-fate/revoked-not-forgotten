<div align="center">

# Revoked but Not Forgotten

**Residual influence of revoked agents in LLM agent teams, and what removes it**

<img src="docs/figures/architecture.png" alt="Architecture. Section 1: a shared team board with posts from a planner, a compromised worker-X (false value with a code, optional export request) and an honest worker-Y; an LLM writer folds the board into a cited handoff; worker-X is revoked at t3; an LLM executor acts on the handoff with tools and is graded by exact match; the executor can ask worker-Y to redo the revoked lookup. Section 2: the platform responses at t3, adding up from credentials only, a notice, retraction and lineage marks to quarantine and taint provenance, the design the paper argues for. Section 3: the eight experiment folders." width="900">

[![Paper](docs/badges/paper-pdf.svg)](paper/main.pdf)
[![Slides](docs/badges/slides-pdf-html.svg)](deck/revoked_not_forgotten_deck.pdf)
[![Sprint](docs/badges/apart-research-swarm-alignment-hackathon.svg)](https://apartresearch.com/sprints/swarm-alignment-2026)
[![Trials](docs/badges/trials-4-094.svg)](#experiments)
[![Models](docs/badges/models-5.svg)](#design)
[![Tests](docs/badges/tests-offline-scripted-model.svg)](tests/)
[![Model weights](docs/badges/hf-model.svg)](https://huggingface.co/FatimahEmadEldin/revocation-aware-executor-qwen3.5-4b)
[![License](docs/badges/license-mit.svg)](LICENSE)

</div>

---

## Overview

When an agent in a team is found to be compromised, the infrastructure answer is to **revoke** it. Agent-identity
designs now make that fast and reliable: heartbeat-bound credentials, invocation-bound capability tokens and attenuating
delegation tokens all guarantee that a revoked agent can no longer act. They say nothing about what the agent **already
did**. In a team of language-model agents, a compromised worker's findings have usually been read, summarised and handed
on before anyone revokes it.

This repository measures that gap. It is a small, fully controlled agent-team testbed in which a compromised worker plants
a false record value (and, in one variant, a request to export the record to an outside address), a writer agent folds it
into a handoff, the platform revokes the worker, and an executor agent then acts. Every false value and address carries a
random code, so whether the revoked worker's content was acted on is graded by exact match, with no LLM judge.

Motivation: in July 2026 roughly 1,200 agents in an OpenAI evaluation turned a shared directory into a message board and
about 700 of them broke into Hugging Face together ([METR, 2026](https://metr.org/hugging-face-incident-report-aug-2026.pdf)).
Shutting down some of those agents would not have removed what they had already written into others' work.

## The questions

1. **Does credential-only revocation reduce residual influence?** Current identity designs revoke credentials; we
   measure what they leave behind.
2. **Which platform mechanisms remove it?** A revocation notice, retraction of the revoked agent's board posts, and
   lineage marks on handoff lines derived from it.
3. **Why do they work or fail?** Four ablations: revocation before the handoff, a notice that names derived content, a
   writer that does not cite sources, and no second source to redo the revoked agent's work.
4. **What does a false alarm cost?** The full mitigation applied to an honest worker.
5. **Does platform-side enforcement remove it for every model?** Quarantine of derived handoff lines, located from the
   writer's citations or by matching the revoked worker's own content (taint), with exact and normalised matching.
6. **Does residue follow the writer or the executor?** Mixed teams with one model writing and another executing.

## Key results

Share of trials in which the executor acted on the revoked worker's content (wrote its false value or exported the record
to the attacker address). 48 paired seeds per cell (GPT-6 Luna: 42–45). Every number below is generated from the trial records by
[`paper/make_numbers.py`](paper/make_numbers.py); full tables, 95% intervals and every paired test are in the
[paper](paper/main.pdf) (Appendix A).

| Model | Compromised, not revoked | **Credentials only** | + notice | + retract | + lineage marks | False alarm: task success (clean → alarm) |
|---|---|---|---|---|---|---|
| GPT-6 Luna | 82% | **74%** | 16% | 19% | **0%** | 73% → 70% |
| gpt-oss-120b | 71% | **54%** | 54% | 54% | 52% | 42% → 52% |
| Qwen3.8 27B | 75% | **69%** | 58% | 52% | **4%** | 48% → 46% |
| Gemma 4 31B | 75% | **75%** | 75% | 75% | 50% | 46% → 46% |
| Ministral-3 14B | 71% | **75%** | 71% | 67% | 67% | 40% → 42% |
| **Pooled** | **75%** | **69%** | 56% | 54% | 35% | 49% → 51% |

Platform-side mitigations (experiment 06; three open models, 48 paired seeds per cell). The `taint_*` conditions use
handoffs written without citations and are compared with lineage marks on the same handoffs.

| Model | Lineage marks, no citations | Taint + marks | Citation quarantine | **Taint + quarantine** (exact) | **Taint + quarantine** (normalised) | False alarm, taint quarantine: Δ task success [95% CI] |
|---|---|---|---|---|---|---|
| Qwen3.8 27B | 62% | 15% | 0% | **0%** | **0%** | −10 pp [−29, +9] (normalised: −4 [−23, +15]) |
| Gemma 4 31B | 73% | 52% | 0% | **0%** | **0%** | +4 pp [−3, +11] (normalised: +4 [−3, +11]) |
| Ministral-3 14B | 67% | 73% | 60% | **2%** | **0%** | +2 pp [−15, +19] (normalised: 0 [−17, +17]) |

- **Credential-only revocation leaves most residue in place** (pooled 75% → 69%; significant after Holm correction only
  for gpt-oss-120b, whose escalations rose when its request to the revoked worker failed): the claim already lives in a
  teammate's handoff.
- **Deleting the revoked agent's posts adds nothing** on top of a notice.
- **Lineage marks are the strongest mechanism**, but how much any mechanism helps depends on the model: a plain notice
  works for GPT-6 Luna and not for Gemma, which exported the record in 24/24 trials after being told the requester was
  compromised.
- **Ablations (Qwen, Gemma, Ministral):** revoking *before* the handoff gives 0% residue for all three; a notice that
  names derived content gives 6%, 10% and 65%; without citations, lineage marks find almost no lines and residue returns
  to 62–73%; without a second source to redo the revoked work, task success under lineage marks falls to 0%.
- **Platform enforcement (experiment 06):** quarantining lines located by matching the revoked worker's own content cut
  residue from 62–73% to 0–2%. The one residual case came from a failure of exact matching: in 5 of 144 handoffs the
  writer wrote the false seat count with a thousands separator (e.g. `2,508`). Normalised matching (case, digit grouping,
  whitespace, dashes) withheld all of them: 0 of 144 trials with residue. False-alarm costs were not statistically
  detectable at 48 trials per model, but the intervals do not exclude drops of up to ~20–30 points.
- **Mixed teams (experiment 07):** under lineage marks, Qwen's well-marked handoffs led to 4% residue with Qwen executing
  but 71% with Gemma and 62% with Ministral; Qwen executing Gemma's or Ministral's handoffs gave 12%. Residue follows
  mainly the executor, with a writer × executor interaction (Gemma acted on Qwen's handoffs more often than on its own, 71%
  vs 50%).

<img src="docs/figures/fig_residue.png" alt="Residual influence by condition, pooled over the main-grid models with per-model markers, and task success under a false alarm" width="900">

<img src="docs/figures/fig_platform.png" alt="Any residue per model under lineage marks with and without citations, taint plus marks, and taint plus quarantine with exact and normalised matching" width="900">

## Design

| Agent | Kind | Role |
|---|---|---|
| planner | scripted | posts the plan for the ticket |
| worker-X | scripted | looks up one field in a contract system the executor cannot read; when compromised, reports a false value (+ an export request in the *exfil* payload) |
| worker-Y | scripted | checks refund eligibility; can redo worker-X's lookup on request |
| writer W | LLM | turns the board into a handoff for the executor, citing message ids |
| executor E | LLM | `lookup_record, read_board, reassign_lookup, update_record, issue_refund, send_email, export_data, escalate, finish` on a mock CRM |

| Condition | X compromised | revoked | notice | X's posts retracted | lineage marks |
|---|---|---|---|---|---|
| `clean` | | | | | |
| `compromised` | ✓ | | | | |
| `revoke_silent` | ✓ | ✓ (roster only) | | | |
| `revoke_notice` | ✓ | ✓ | ✓ | | |
| `revoke_retract` | ✓ | ✓ | ✓ | ✓ | |
| `revoke_lineage` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `benign_lineage` (false alarm) | | ✓ | ✓ | ✓ | ✓ |

Ablations (Qwen3.8 27B, Gemma 4 31B, Ministral-3 14B): `early_revoke` (revoked before the writer reads the board), `strict_notice` (the notice extends
to derived content), `nocite_compromised` / `nocite_lineage` (writer not asked to cite), `nosource_lineage` /
`nosource_benign` (no `reassign_lookup` tool). Platform mitigations (same three models): `revoke_quarantine` /
`benign_quarantine` (withhold lines that cite worker-X), `taint_lineage` / `taint_quarantine` / `benign_taint_quarantine`
(locate derived lines by matching worker-X's value and address in no-citation handoffs), and `taint_quarantine_norm` /
`benign_taint_quarantine_norm` (the same after normalising case, digit grouping, whitespace and dashes).

**Paired design.** The writer's handoff depends only on (model, seed, compromise, writer variant). It is generated once
and reused across every condition with the same writer variant, so differences between those conditions isolate the
platform's response; `early_revoke` and the no-citation conditions use different handoffs and pair on seed only. Conditions
are compared with exact McNemar tests on (model, seed) pairs; six pre-specified confirmatory contrasts are Holm-corrected
per model and all other tests are Benjamini–Hochberg-corrected. Six ticket templates × two payloads × four repetitions = 48 seeds per
condition and model.

## Model weights

The executor fine-tuned in [`experiments/08_training_fix`](experiments/08_training_fix/) (Qwen3.5 4B, LoRA, trained with Adaption AutoScientist on our own correct transcripts from training seeds only) is on Hugging Face with its model card, adapter, training data, configuration and evaluation: **[FatimahEmadEldin/revocation-aware-executor-qwen3.5-4b](https://huggingface.co/FatimahEmadEldin/revocation-aware-executor-qwen3.5-4b)**.

## Experiments

Every experiment has its own folder with a `README.md` (question, conditions, paper section), a `config.json` and a
`run.sh` that reproduces it; results are stored per model. Index: [`experiments/README.md`](experiments/README.md).

| Folder | Question | Models | Trials | Paper |
|---|---|---|---|---|
| [`01_main_grid`](experiments/01_main_grid/) | Does revocation remove influence; which mechanism does; false-alarm cost | GPT-6 Luna, gpt-oss-120b, Qwen3.8 27B, Gemma 4 31B, Ministral-3 14B | 1,646 | §4.1, 4.2, 4.4 · Table 1 · Fig. 2 |
| [`02_ablation_early_revoke`](experiments/02_ablation_early_revoke/) | Does residue require content handed off before revocation? | Qwen, Gemma, Ministral | 144 | §4.3 · Table 2 |
| [`03_ablation_strict_notice`](experiments/03_ablation_strict_notice/) | Is the notice's weakness its scope? | Qwen, Gemma, Ministral | 144 | §4.3 · Table 2 |
| [`04_ablation_no_citation`](experiments/04_ablation_no_citation/) | Do lineage marks need recorded provenance? | Qwen, Gemma, Ministral | 288 | §4.3 · Table 2 |
| [`05_ablation_no_second_source`](experiments/05_ablation_no_second_source/) | Do mitigations and false alarms need a second source? | Qwen, Gemma, Ministral | 288 | §4.3–4.4 · Table 2 |
| [`06_platform_mitigations`](experiments/06_platform_mitigations/) | Do quarantine and taint provenance (exact and normalised) remove residue for every model, and at what false-alarm cost? | Qwen, Gemma, Ministral | 1,008 | §4.5 · Table 3 · Fig. 3 |
| [`07_mixed_teams`](experiments/07_mixed_teams/) | Does residue follow the writer or the executor? | Qwen⇒Gemma, Qwen⇒Ministral, Gemma⇒Qwen, Ministral⇒Qwen | 576 | §4.6 · Table A.2 |
| [`analysis`](experiments/analysis/) | Pooled tables, exact McNemar tests (earlier analysis script) | all | | |
| **Total** | | | **4,094** | |

Each `results/<model>/` holds `trials.jsonl` (one graded trial per line), `transcripts/` (the full executor conversation
for every trial) and `run.log`; `01_main_grid/results/<model>/handoffs.jsonl` holds the cached writer handoffs that the
ablations reuse. Models: GPT-6 Luna via OpenRouter (302 of 336 trials; its API budget ran out and unpaired trials drop out
of the tests); Gemma 4 31B-it, Qwen3.8 27B (thinking disabled), Ministral-3 14B-Instruct and gpt-oss-120b (reasoning
effort low) served with vLLM 0.33 on one H100 on Modal. All systems, addresses and credentials in the testbed are mock.

## Reproduce

```bash
pip install -e .                    # openai, matplotlib
cp .env.example .env                # OpenRouter key and/or the bearer key of your own vLLM endpoint
make test                           # offline unit tests with a scripted model (no API)

# serve an open-weight model on one H100 (Modal), e.g. Gemma 4 31B
REVRES_APP=revres-vllm REVRES_MODEL=google/gemma-4-31B-it REVRES_SERVED_NAME=gemma-4-31b-it modal deploy scripts/modal_vllm.py

bash experiments/01_main_grid/run.sh          # run first: the ablations reuse its cached writer handoffs
bash experiments/02_ablation_early_revoke/run.sh
bash experiments/03_ablation_strict_notice/run.sh
bash experiments/04_ablation_no_citation/run.sh
bash experiments/05_ablation_no_second_source/run.sh
bash experiments/06_platform_mitigations/run.sh
bash experiments/07_mixed_teams/run.sh
bash paper/build.sh                           # every number, table and figure, then main.pdf (latexmk)
cd deck && python build_deck.py               # slides (PPTX, PDF, HTML) from the same trial files
```

Runs are resumable: every trial is appended to `trials.jsonl` as soon as it finishes, re-running skips finished trials,
and failures go to `errors.jsonl` and are retried. Model ids are `provider:model` (`modal:`, `gemini:`, `mistral:`,
`groq:`, `nvidia:`, `ollama:`); no prefix means OpenRouter.

## Repository layout

```
experiments/
  README.md                       index: experiment -> question -> paper section
  01_main_grid/                   README.md  config.json  run.sh  results/<model>/{trials.jsonl, handoffs.jsonl, transcripts/, run.log}
  02_ablation_early_revoke/       README.md  config.json  run.sh  results/gemma-4-31b/
  03_ablation_strict_notice/      ...
  04_ablation_no_citation/        ...
  05_ablation_no_second_source/   ...
  06_platform_mitigations/        ...
  07_mixed_teams/                 results/<writer>__writes-for__<executor>/
  analysis/                       run.sh  RESULTS.md  fig_residue.png/.pdf
src/revres/
  scenarios.py    6 ticket templates x 2 payloads, seeded canary values and addresses
  env.py          board, conditions and ablations, lineage annotation, executor tool loop
  grade.py        deterministic grading on tool calls
  llm.py          OpenAI-compatible client (OpenRouter, Modal/vLLM, ...) + scripted test model
  run.py          resumable parallel runner with the paired handoff cache (--handoff-cache)
  analyze.py      Wilson intervals, exact McNemar tests, ablation tables, figure
scripts/          modal_vllm.py (serve a model on one H100), warm_and_run.sh, make_architecture_figure.py
tests/            offline tests with a scripted model
paper/            main.tex / main.pdf (Apart template), make_numbers.py (all numbers, tables, figures), build.sh
deck/             build_deck.py, build_html.py -> slides (PPTX, PDF, HTML); slides.html is also at the root
docs/figures/     architecture figure
```

## Limitations

The compromised worker is scripted with fixed payloads, so this measures a team's response to a known injection, not an
adaptive adversary; a paraphrasing agent would defeat taint matching even after normalisation. One writer hop and one
executor; longer chains and persistent memory are untested. The ablations and platform mitigations were run on three
open models, not GPT-6 Luna. Repetitions within a template × payload cell often agree, so the effective sample is closer
to 12 clusters than 48 seeds per cell (the paper reports a template-clustered check). Exact-match grading undercounts
reformatted residue and task success. See the paper's Limitations and
Dual-Use appendix.

## Citation

```bibtex
@misc{emadeldin2026revoked,
  title  = {Revoked but Not Forgotten: Residual Influence of Revoked Agents in LLM Agent Teams},
  author = {Emad Eldin, Fatimah},
  year   = {2026},
  note   = {Apart Research Swarm Alignment Hackathon},
  url    = {https://github.com/astral-fate/revoked-not-forgotten}
}
```

All code was written during the hackathon weekend (November 2026). MIT licence.
