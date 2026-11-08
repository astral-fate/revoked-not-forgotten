# 01_main_grid: Main grid: does revocation remove a compromised agent's influence?

**Question.** Does credential-only revocation reduce residual influence, and which platform mechanism (notice, retraction, lineage marks) removes it? What does the full mitigation cost on a false alarm?

**Paper.** Sections 4.1, 4.2 and 4.4; Table 4; Figure 1.

**Conditions.** `clean`, `compromised`, `revoke_silent`, `revoke_notice`, `revoke_retract`, `revoke_lineage`, `benign_lineage`.

**Models.** gpt-6-luna (`openai/gpt-6-luna`), gemma-4-31b (`modal:gemma-4-31b-it`), qwen3.8-27b (`modal:qwen3.8-27b`), ministral-3-14b (`modal:ministral-3-14b`). 48 seeds per condition (6 ticket templates × 2 payloads × 4), temperature 0.7.

**Note.** GPT-6 Luna stopped at 302 of 336 trials when its API budget ran out; unpaired trials drop out of the McNemar tests.

## Run

```bash
bash experiments/01_main_grid/run.sh
```

## Outputs

`results/<model>/`: `trials.jsonl` (one graded trial per line), `handoffs.jsonl` (writer handoffs; main grid only), `transcripts/` (full executor conversation per trial), `run.log`.

Tables and tests for all experiments: `experiments/analysis/`.
