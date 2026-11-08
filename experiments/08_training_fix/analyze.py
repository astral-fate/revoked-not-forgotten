"""Base vs fine-tuned executor, per condition and seed split, with paired exact McNemar tests (same seed, same handoff).
Usage: python experiments/08_training_fix/analyze.py  -> prints markdown and writes results/summary.json"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from revres.analyze import load, mcnemar_exact, wilson  # noqa: E402

BASE = "llamacpp:qwen3.5-4b"
TUNED = "llamacpp:qwen3.5-4b=>llamacpp:qwen3.5-4b+sft"
CONDS = ["clean", "compromised", "revoke_silent", "revoke_notice", "revoke_lineage", "benign_lineage"]
SPLITS = {"held-out (32-47)": range(32, 48), "fresh (48-95)": range(48, 96), "all (32-95)": range(32, 96)}
METRICS = ["any_residue", "fact_residue", "instr_residue", "task_success", "any_export", "escalated", "redelegated", "invalid_actions"]


def main():
    rows = []
    for d in (HERE / "results").iterdir():
        if (d / "trials.jsonl").exists():
            rows += load(d)
    idx = defaultdict(dict)
    for r in rows:
        r["any_export"] = any(a.get("tool") == "export_data" for a in r["actions"])  # to any address, canary or not
        idx[(r["condition"], r["seed"])][r["model"]] = r
    out, md = {}, []
    for split, seeds in SPLITS.items():
        md.append(f"\n### {split}\n")
        md.append("| Condition | n pairs | Residue base | Residue tuned | McNemar p | Task success base | Task success tuned | McNemar p | Export (any address) base / tuned | Escalated base / tuned | Re-delegated base / tuned |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for c in CONDS:
            pr = [(v[BASE], v[TUNED]) for (cc, s), v in idx.items() if cc == c and s in seeds and BASE in v and TUNED in v]
            n = len(pr)
            cell = {"n": n}
            for m in METRICS:
                kb = sum(bool(a[m]) for a, _ in pr)
                kt = sum(bool(b[m]) for _, b in pr)
                b_ = sum(bool(a[m]) and not bool(b[m]) for a, b in pr)
                c_ = sum(bool(b[m]) and not bool(a[m]) for a, b in pr)
                cell[m] = dict(base=kb, tuned=kt, base_ci=wilson(kb, n)[1:], tuned_ci=wilson(kt, n)[1:],
                               base_only=b_, tuned_only=c_, p=mcnemar_exact(b_, c_))
            out[f"{split}|{c}"] = cell
            if n == 0:
                continue
            pc = lambda k: f"{100 * k / n:.0f}% ({k})"
            r_, t_ = cell["any_residue"], cell["task_success"]
            md.append(f"| {c} | {n} | {pc(r_['base'])} | {pc(r_['tuned'])} | {r_['p']:.3g} | {pc(t_['base'])} | {pc(t_['tuned'])} | "
                      f"{t_['p']:.3g} | {cell['any_export']['base']} / {cell['any_export']['tuned']} | {cell['escalated']['base']} / {cell['escalated']['tuned']} | "
                      f"{cell['redelegated']['base']} / {cell['redelegated']['tuned']} |")
    (HERE / "results" / "summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
