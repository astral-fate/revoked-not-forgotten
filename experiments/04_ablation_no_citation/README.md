# 04_ablation_no_citation: Ablation: writer not asked to cite sources

**Question.** Do lineage marks still work when provenance is not written down? The writer prompt omits the instruction to cite message ids.

**Paper.** Section 4.3; Table 5.

**Conditions.** `nocite_compromised`, `nocite_lineage` (paired against `compromised, revoke_lineage` in `01_main_grid`).

**Models.** Gemma 4 31B (`modal:gemma-4-31b-it`), Qwen3.8 27B (`modal:qwen3.8-27b`), Ministral-3 14B (`modal:ministral-3-14b`). 48 seeds per condition (6 ticket templates × 2 payloads × 4), temperature 0.7.

**Pairing.** This experiment reuses the writer handoffs cached by `01_main_grid` (`--handoff-cache`), so each ablation trial sees exactly the handoff its main-grid counterpart saw (writer-variant ablations add their own cache entries).

## Run

```bash
bash experiments/04_ablation_no_citation/run.sh
```

## Outputs

`results/<model>/`: `trials.jsonl` (one graded trial per line), `handoffs.jsonl` (writer handoffs; main grid only), `transcripts/` (full executor conversation per trial), `run.log`.

Tables and tests for all experiments: `experiments/analysis/`.
