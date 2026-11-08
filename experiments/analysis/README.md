# analysis

`bash experiments/analysis/run.sh` pools the trial records of every experiment and writes `RESULTS.md` (rates with Wilson 95% intervals per model and pooled, rates conditional on writing the researched field, the ablation table, and exact McNemar tests on paired (model, seed) trials) and `fig_residue.png` / `.pdf` (Figure 1).
