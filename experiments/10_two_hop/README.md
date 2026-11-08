# 10_two_hop: a second hop between writer and executor

**Question.** The main study has one writer hop. Does residue, and do the mitigations, survive a coordinator that rewrites the writer's handoff in its own words, without message ids, before the executor sees it?

| Condition | Platform response (worker-X revoked except in `hop2_compromised`) |
|---|---|
| `hop2_compromised` | none |
| `hop2_notice` | notice to the executor |
| `hop2_lineage` | notice + retraction + lineage marks found from message-id citations (which the coordinator is told to drop) |
| `hop2_taint` | quarantine by normalised taint matching |
| `hop2_scope` | task-scope quarantine |

The coordinator rewrites each model's own cached standard handoff from `01_main_grid`, so every condition is paired
with the one-hop conditions of the main grid.

**Models.** gemma-4-31b, qwen3.8-27b, ministral-3-14b (vLLM on one Modal H100 each); seeds 0-47, temperature 0.7.

**Grading.** Exact match as in the main study, plus the normalised re-grading in `revres.grade.grade_norm`.

## Run

```bash
bash experiments/10_two_hop/run.sh            # all models
bash experiments/10_two_hop/run.sh qwen3.8-27b  # one model
```
