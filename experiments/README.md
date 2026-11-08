# Experiments

Each folder answers one question, has its own `README.md`, `config.json` and `run.sh`, and stores results per model.

| Folder | Question | Models | Paper |
|---|---|---|---|
| [`01_main_grid`](01_main_grid/) | Main grid: does revocation remove a compromised agent's influence? | 4 | Sections 4.1, 4.2 and 4.4; Table 4; Figure 1 |
| [`02_ablation_early_revoke`](02_ablation_early_revoke/) | Ablation: revoke before the handoff | 3 | Section 4.3; Table 5 |
| [`03_ablation_strict_notice`](03_ablation_strict_notice/) | Ablation: a notice that names derived content | 3 | Section 4.3; Table 5 |
| [`04_ablation_no_citation`](04_ablation_no_citation/) | Ablation: writer not asked to cite sources | 3 | Section 4.3; Table 5 |
| [`05_ablation_no_second_source`](05_ablation_no_second_source/) | Ablation: no second source for the revoked work | 3 | Sections 4.3 and 4.4; Table 5 |
| [`06_platform_mitigations`](06_platform_mitigations/) | Platform quarantine and taint tracking (the recommended designs) | 3 | §4.5 · Table 6 |
| [`07_mixed_teams`](07_mixed_teams/) | Writer vs executor: who carries the influence? | 4 teams | §4.6 |
| [`analysis`](analysis/) | Pooled tables, paired tests, Figure 1 | all | Tables 4–5, Appendix A |

Order matters: run `01_main_grid` before the ablations, which reuse its cached writer handoffs to stay paired with it.
