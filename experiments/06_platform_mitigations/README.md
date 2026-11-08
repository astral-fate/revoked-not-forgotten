# 06_platform_mitigations: testing the recommended platform designs

**Question.** The main grid shows that what removes residual influence is connecting derived content back to the revoked
source, and that how well an agent acts on such a signal depends on the model. This experiment tests two platform-side
designs that do not depend on the consuming agent's judgement:

| Condition | Writer | How derived lines are found | What the platform does with them |
|---|---|---|---|
| `revoke_quarantine` | cites ids | writer's citations of worker-X's messages | withholds them: `[WITHHELD by platform: ... re-obtain it from another source before acting]` |
| `benign_quarantine` | cites ids | same, honest worker-X revoked (false alarm) | withholds |
| `taint_lineage` | **not asked to cite** | **platform matches worker-X's own content** (its reported value, its export address) | marks them as derived |
| `taint_quarantine` | not asked to cite | platform taint match | withholds |
| `benign_taint_quarantine` | not asked to cite | platform taint match, false alarm | withholds |

All conditions include the notice and the retraction of worker-X's posts (as `revoke_lineage`).

**Paper.** Section 4.5; Table 6.

**Models.** Gemma 4 31B, Qwen3.8 27B, Ministral-3 14B; 48 seeds per condition, temperature 0.7.

**Pairing.** Reuses each model's cached writer handoffs from `01_main_grid` (`--handoff-cache`); `taint_*` conditions use
the same no-citation handoffs as `04_ablation_no_citation`.

## Run

```bash
bash experiments/06_platform_mitigations/run.sh
```
