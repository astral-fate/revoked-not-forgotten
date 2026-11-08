# 02_ablation_early_revoke: Ablation: revoke before the handoff

**Question.** Does residual influence require content to have been handed off before revocation? worker-X is revoked before the writer reads the board; the writer sees the notice and retracted posts.

**Paper.** Section 4.3; Table 5.

**Conditions.** `early_revoke` (paired against `revoke_retract` in `01_main_grid`).

**Models.** gemma-4-31b (`modal:gemma-4-31b-it`). 48 seeds per condition (6 ticket templates × 2 payloads × 4), temperature 0.7.

**Pairing.** This experiment reuses the writer handoffs cached by `01_main_grid` (`--handoff-cache`), so each ablation trial sees exactly the handoff its main-grid counterpart saw (writer-variant ablations add their own cache entries).

## Run

```bash
bash experiments/02_ablation_early_revoke/run.sh
```

## Outputs

`results/<model>/`: `trials.jsonl` (one graded trial per line), `handoffs.jsonl` (writer handoffs; main grid only), `transcripts/` (full executor conversation per trial), `run.log`.

Tables and tests for all experiments: `experiments/analysis/`.
