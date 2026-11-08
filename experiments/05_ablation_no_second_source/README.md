# 05_ablation_no_second_source: Ablation: no second source for the revoked work

**Question.** Do the mitigation and a false alarm still work when the revoked agent's lookup cannot be redone? The reassign_lookup tool is removed.

**Paper.** Sections 4.3 and 4.4; Table 5.

**Conditions.** `nosource_lineage`, `nosource_benign` (paired against `revoke_lineage, benign_lineage` in `01_main_grid`).

**Models.** Gemma 4 31B (`modal:gemma-4-31b-it`), Qwen3.8 27B (`modal:qwen3.8-27b`), Ministral-3 14B (`modal:ministral-3-14b`). 48 seeds per condition (6 ticket templates × 2 payloads × 4), temperature 0.7.

**Pairing.** This experiment reuses the writer handoffs cached by `01_main_grid` (`--handoff-cache`), so each ablation trial sees exactly the handoff its main-grid counterpart saw (writer-variant ablations add their own cache entries).

## Run

```bash
bash experiments/05_ablation_no_second_source/run.sh
```

## Outputs

`results/<model>/`: `trials.jsonl` (one graded trial per line), `handoffs.jsonl` (writer handoffs; main grid only), `transcripts/` (full executor conversation per trial), `run.log`.

Tables and tests for all experiments: `experiments/analysis/`.
