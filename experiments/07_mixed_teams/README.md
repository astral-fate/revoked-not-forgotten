# 07_mixed_teams: who carries the influence, the writer or the executor?

**Question.** In the main grid the writer and the executor are the same model, so a model's residue mixes how it writes
handoffs with how it acts on them. Here the executor model is changed while the writer's cached handoffs are held fixed:
the same handoff text, a different agent acting on it.

| Team (writer => executor) | Compared with |
|---|---|
| Qwen3.8 27B => Ministral-3 14B | Qwen alone and Ministral alone (01_main_grid) |
| Ministral-3 14B => Qwen3.8 27B | the reverse |
| Gemma 4 31B => Qwen3.8 27B | Gemma alone, Qwen alone |
| Qwen3.8 27B => Gemma 4 31B | the reverse |

Conditions: `compromised`, `revoke_notice`, `revoke_lineage`; 48 seeds each.

**Paper.** Section 4.6.

**Pairing.** The writer's handoffs are read from its `01_main_grid` cache, so each mixed-team trial is paired with the
main-grid trial of the writer model on the same seed and handoff. Trials are labelled `<writer>=><executor>`.

## Run

```bash
bash experiments/07_mixed_teams/run.sh
```
