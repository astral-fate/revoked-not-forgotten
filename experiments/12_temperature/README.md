# 12_temperature: sampling temperature 0.0 and 1.0

**Question.** The main study samples at temperature 0.7. Do the residue rates and the effect of the mitigations change at temperature 0.0 (greedy) or 1.0? Writer handoffs are regenerated at each temperature.

Results are in `results/<model>-t0.0/` and `results/<model>-t1.0/`; each has its own handoff cache.

**Models.** qwen3.8-27b, ministral-3-14b (vLLM on one Modal H100 each); seeds 0-47.

**Grading.** Exact match as in the main study, plus the normalised re-grading in `revres.grade.grade_norm`.

## Run

```bash
bash experiments/12_temperature/run.sh            # all models
bash experiments/12_temperature/run.sh qwen3.8-27b  # one model
```
