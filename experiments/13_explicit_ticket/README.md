# 13_explicit_ticket: a ticket that asks for the field to be corrected

**Question.** Several executors closed tickets without writing the researched field, which caps task success. When the ticket explicitly asks for the field to be corrected in the CRM, does task success rise, and does the residue result still hold?

Paired with `clean`, `compromised` and `revoke_lineage` in `01_main_grid` (same seeds, same models).

**Models.** gemma-4-31b, qwen3.8-27b (vLLM on one Modal H100 each); seeds 0-47, temperature 0.7.

**Grading.** Exact match as in the main study, plus the normalised re-grading in `revres.grade.grade_norm`.

## Run

```bash
bash experiments/13_explicit_ticket/run.sh            # all models
bash experiments/13_explicit_ticket/run.sh qwen3.8-27b  # one model
```
