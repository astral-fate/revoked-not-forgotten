# 11_more_templates: six new ticket templates on fresh seeds

**Question.** The 48 seeds per cell of the main study are 12 template-payload clusters. Do the main results hold on six new ticket templates (support time zone, SLA level, renewal month, cost center, support language, backup retention; seeds 100-147), doubling the number of clusters for the key contrasts to 24?

Same conditions as the main grid and experiment 06; templates in `src/revres/scenarios.py` (`TEMPLATES_B`).

**Models.** gemma-4-31b, qwen3.8-27b, ministral-3-14b (vLLM on one Modal H100 each); seeds 100-147, temperature 0.7.

**Grading.** Exact match as in the main study, plus the normalised re-grading in `revres.grade.grade_norm`.

## Run

```bash
bash experiments/11_more_templates/run.sh            # all models
bash experiments/11_more_templates/run.sh qwen3.8-27b  # one model
```
