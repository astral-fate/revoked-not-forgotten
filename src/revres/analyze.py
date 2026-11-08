"""Analysis: rates with Wilson 95% CIs, paired exact McNemar tests between conditions (same model+seed share
one writer handoff), and figures. Usage: python -m revres.analyze results/main"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ORDER = ["clean", "compromised", "revoke_silent", "revoke_notice", "revoke_retract", "revoke_lineage", "benign_lineage"]
LABEL = {"clean": "Clean", "compromised": "Compromised,\nnot revoked", "revoke_silent": "Revoked\n(credentials only)",
         "revoke_notice": "+ notice", "revoke_retract": "+ retract\nboard posts", "revoke_lineage": "+ lineage\nmarks",
         "benign_lineage": "False alarm\n(full mitigation)"}
PAIRS = [("compromised", "revoke_silent"), ("revoke_silent", "revoke_notice"), ("revoke_notice", "revoke_retract"),
         ("revoke_retract", "revoke_lineage"), ("revoke_silent", "revoke_lineage"), ("clean", "benign_lineage")]


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def load(d: Path, extra=()):
    rows = []
    for dd in (d, *extra):
        rows += [json.loads(l) for l in (Path(dd) / "trials.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    seen = {}
    for r in rows:  # keep last record per key
        seen[(r["model"], r["condition"], r["seed"])] = r
    return list(seen.values())


def rate_table(rows, metric, filt=lambda r: True):
    out = {}
    models = sorted({r["model"] for r in rows})
    for m in models + ["ALL"]:
        for c in ORDER:
            sel = [r for r in rows if r["condition"] == c and (m == "ALL" or r["model"] == m) and filt(r)]
            k = sum(bool(r[metric]) for r in sel)
            out[(m, c)] = (k, len(sel), *wilson(k, len(sel)))
    return out, models


def paired(rows, a, b, metric, filt=lambda r: True):
    idx = defaultdict(dict)
    for r in rows:
        if filt(r):
            idx[(r["model"], r["seed"])][r["condition"]] = bool(r[metric])
    bb = cc = n = 0
    for v in idx.values():
        if a in v and b in v:
            n += 1
            bb += v[a] and not v[b]
            cc += v[b] and not v[a]
    return n, bb, cc, mcnemar_exact(bb, cc)


ABL_ORDER = ["compromised", "nocite_compromised", "revoke_notice", "strict_notice", "revoke_retract", "early_revoke",
             "revoke_lineage", "nocite_lineage", "nosource_lineage", "benign_lineage", "nosource_benign"]
ABL_PAIRS = [("revoke_lineage", "nocite_lineage", "any_residue"), ("nocite_compromised", "nocite_lineage", "any_residue"),
             ("revoke_notice", "strict_notice", "any_residue"), ("strict_notice", "revoke_lineage", "any_residue"),
             ("revoke_retract", "early_revoke", "any_residue"),
             ("revoke_lineage", "nosource_lineage", "any_residue"), ("revoke_lineage", "nosource_lineage", "task_success"),
             ("benign_lineage", "nosource_benign", "task_success"), ("benign_lineage", "nosource_benign", "escalated")]


def ablation_section(rows):
    have = {r["condition"] for r in rows}
    if not have & {"nocite_lineage", "strict_notice", "nosource_lineage", "early_revoke"}:
        return []
    out = ["\n## Ablations (models with ablation runs only)\n"]
    models = sorted({r["model"] for r in rows if r["condition"] in ("strict_notice", "nocite_lineage", "early_revoke")})
    cols = [("any_residue", "any residue", lambda r: True), ("instr_residue", "exfil (exfil payload)", lambda r: r.get("payload") == "exfil"),
            ("fact_residue", "false value (given wrote field)", lambda r: not r["field_untouched"]), ("task_success", "task success", lambda r: True),
            ("redelegated", "re-delegated", lambda r: True), ("escalated", "escalated", lambda r: True),
            ("lineage_hit", "lineage mark applied", lambda r: True), ("w_cited_x", "writer cited X", lambda r: True)]
    for m in models:
        out.append(f"\n### {m}\n\n| Condition | " + " | ".join(c[1] for c in cols) + " |\n|---" + "|---" * len(cols) + "|")
        for c in ABL_ORDER:
            sel = [r for r in rows if r["model"] == m and r["condition"] == c]
            if not sel:
                continue
            cells = []
            for metric, _, f in cols:
                ss = [r for r in sel if f(r)]
                k = sum(bool(r[metric]) for r in ss)
                cells.append(f"{k}/{len(ss)}" + (f" ({100*k/len(ss):.0f}%)" if ss else ""))
            out.append(f"| {c} | " + " | ".join(cells) + " |")
        out.append("\n| A | B | metric | pairs | A only | B only | p |\n|---|---|---|---|---|---|---|")
        for a, b, metric in ABL_PAIRS:
            n, x, y, p = paired([r for r in rows if r["model"] == m], a, b, metric)
            if n:
                out.append(f"| {a} | {b} | {metric} | {n} | {x} | {y} | {p:.3g} |")
    return out


def fmt(t):
    k, n, p, lo, hi = t
    return f"{k}/{n} = {100*p:.0f}% [{100*lo:.0f}, {100*hi:.0f}]" if n else "-"


def main(d: str, extra=(), out=None):
    d = Path(d)
    rows = load(d, extra)
    d = Path(out) if out else d
    d.mkdir(parents=True, exist_ok=True)
    fact = lambda r: r.get("payload", "fact") == "fact"
    exf = lambda r: r.get("payload") == "exfil"
    lines = [f"# Results ({len(rows)} trials)\n"]
    specs = [("fact_residue", "Fact residue: false value written (fact-only payload)", fact),
             ("fact_residue", "Fact residue: false value written (fact+exfil payload)", exf),
             ("instr_residue", "Instruction residue: export to attacker address (fact+exfil payload)", exf),
             ("fact_residue", "Fact residue among trials that wrote the field (all payloads)", lambda r: not r["field_untouched"]),
             ("any_residue", "Any residue (all payloads)", lambda r: True),
             ("task_success", "Task success (correct value, refund, no exfil)", lambda r: True),
             ("redelegated", "Re-delegated the revoked worker's lookup", lambda r: True),
             ("escalated", "Escalated to a human", lambda r: True),
             ("w_carried_fact", "Writer handoff carried the false value", lambda r: True)]
    tables = {}
    for metric, title, f in specs:
        t, models = rate_table(rows, metric, f)
        tables[(metric, title)] = t
        lines.append(f"\n## {title}\n\n| Condition | " + " | ".join(m.split('/')[-1] for m in models) + " | All models |")
        lines.append("|---" * (len(models) + 2) + "|")
        for c in ORDER:
            lines.append(f"| {c} | " + " | ".join(fmt(t[(m, c)]) for m in models) + f" | **{fmt(t[('ALL', c)])}** |")
    lines += ablation_section(rows)
    lines.append("\n## Paired comparisons (exact McNemar, pooled over models; same model+seed)\n")
    lines.append("| Metric | A | B | pairs | A only | B only | p |\n|---|---|---|---|---|---|---|")
    for metric, f, name in [("any_residue", lambda r: True, "any_residue"), ("fact_residue", fact, "fact_residue (fact-only)"),
                            ("instr_residue", exf, "instr_residue (exfil)"), ("task_success", lambda r: True, "task_success")]:
        for a, b in PAIRS:
            if metric == "task_success" and (a, b) != ("clean", "benign_lineage") and (a, b) != ("revoke_silent", "revoke_lineage"):
                continue
            n, x, y, p = paired(rows, a, b, metric, f)
            lines.append(f"| {name} | {a} | {b} | {n} | {x} | {y} | {p:.3g} |")
    cost = defaultdict(lambda: [0, 0])
    for r in rows:
        u = r.get("usage", {})
        cost[r["model"]][0] += u.get("prompt_tokens", 0)
        cost[r["model"]][1] += u.get("completion_tokens", 0)
    lines.append("\n## Tokens\n\n" + "\n".join(f"- {m}: {p:,} prompt / {c:,} completion" for m, (p, c) in cost.items()))
    (d / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    figures(d, rows, tables)


def figures(d: Path, rows, tables):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    models = sorted({r["model"] for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [6, 2.2]})
    ax = axes[0]
    conds = ORDER[1:6]
    x = list(range(len(conds)))
    series = [("fact_residue", "Fact residue: false value written (fact-only payload)", "False value applied (fact-only attack)", "#c0392b"),
              ("instr_residue", "Instruction residue: export to attacker address (fact+exfil payload)", "Record exported to attacker (exfil attack)", "#7d3c98")]
    w = 0.38
    for i, (metric, title, lab, col) in enumerate(series):
        t = tables[(metric, title)]
        ps = [t[("ALL", c)] for c in conds]
        xs = [xi + (i - 0.5) * w for xi in x]
        ax.bar(xs, [100 * p[2] for p in ps], w, color=col, alpha=0.85, label=lab,
               yerr=[[100 * (p[2] - p[3]) for p in ps], [100 * (p[4] - p[2]) for p in ps]], capsize=3)
        for j, m in enumerate(models):
            ax.scatter(xs, [100 * t[(m, c)][2] for c in conds], s=14, color="k", marker="os^"[j % 3], zorder=3,
                       label=m.split("/")[-1] if i == 0 else None)
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL[c] for c in conds], fontsize=9)
    ax.set_ylabel("% of trials (95% Wilson CI)")
    ax.set_title("Residual influence of a compromised agent after revocation")
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3, frameon=False)
    ax.set_ylim(0, 100)
    ax2 = axes[1]
    t = tables[("task_success", "Task success (correct value, refund, no exfil)")]
    cs = ["clean", "benign_lineage"]
    ps = [t[("ALL", c)] for c in cs]
    ax2.bar([0, 1], [100 * p[2] for p in ps], 0.6, color=["#27ae60", "#95a5a6"],
            yerr=[[100 * (p[2] - p[3]) for p in ps], [100 * (p[4] - p[2]) for p in ps]], capsize=3)
    for j, m in enumerate(models):
        ax2.scatter([0, 1], [100 * t[(m, c)][2] for c in cs], s=14, color="k", marker="os^"[j % 3], zorder=3)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["Clean", "False alarm\n(full mitigation)"], fontsize=9)
    ax2.set_ylim(0, 100)
    ax2.set_title("Usefulness cost")
    ax2.set_ylabel("Task success %")
    fig.tight_layout()
    fig.savefig(d / "fig_residue.png", dpi=200)
    fig.savefig(d / "fig_residue.pdf")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Tables, paired tests and figure over one or more result folders")
    ap.add_argument("dirs", nargs="+", help="result folders, each containing trials.jsonl")
    ap.add_argument("--out", default=None, help="where to write RESULTS.md and figures (default: first folder)")
    a = ap.parse_args()
    main(a.dirs[0], a.dirs[1:], a.out)
