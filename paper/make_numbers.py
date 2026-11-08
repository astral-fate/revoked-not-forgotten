"""Generate every number used in the paper from the trial records.

Reads experiments/*/results/<label>/trials.jsonl (via revres.analyze) and writes
  paper/numbers.tex         \\N{key} macros: rates, Wilson intervals, paired exact McNemar tests, counts, model lists
  paper/tab_main.tex        Table 4 body: main conditions x every main-grid model
  paper/tab_ablation.tex    Table 5 body: ablations x every model with ablation runs
  paper/tab_platform.tex    Table 6 body: platform-side mitigations (written only when such runs exist)
  paper/tab_mixed.tex       mixed-team table body (written only when such runs exist)
  paper/tab_permodel.tex    Appendix A per-model tables (complete table environments)
  paper/tab_mcnemar.tex     Appendix A paired-test table body

Discovery. Models, teams and conditions are discovered from the result folders. A label containing "=>" is a mixed team
(writer=>executor). Conditions are classified with revres.env: CONDITIONS (main grid), ABLATIONS, MITIGATIONS.
Completeness. A (label, condition) cell is used only when it has every seed of its experiment (config.json "seeds"),
so partial folders of runs in progress are ignored. GPT-6 Luna's main grid ended early (API budget) and is used as is.
In the text, \\N{key} prints a bold ??key for a missing number, and \\IfN{key}{yes}{no} guards prose on data that
may not exist yet.

Usage:  python paper/make_numbers.py [--experiments DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from revres.analyze import ORDER, ABL_ORDER, load, mcnemar_exact, wilson  # noqa: E402
from revres.env import ABLATIONS, CONDITIONS  # noqa: E402

try:
    from revres.env import MITIGATIONS  # noqa: E402
except ImportError:  # older checkouts
    MITIGATIONS = {}

MAIN_DIR = "01_main_grid"
PARTIAL_OK = {"gpt-6-luna"}
PARTIAL_SLUGS = {"luna"}  # runs that ended before every seed was done; analysed as they are
NICE = {  # id -> (display name, macro slug)
    "gpt-6-luna": ("GPT-6 Luna", "luna"),
    "gpt-oss-120b": ("gpt-oss-120b", "oss"),
    "qwen3.8-27b": ("Qwen3.8 27B", "qwen"),
    "gemma-4-31b-it": ("Gemma 4 31B", "gemma"),
    "ministral-3-14b": ("Ministral 3 14B", "ministral"),
}
SHORT = {"luna": "Luna", "oss": "gpt-oss", "qwen": "Qwen", "gemma": "Gemma", "ministral": "Ministral"}
MODEL_ORDER = ["luna", "oss", "qwen", "gemma", "ministral"]
MIT_ORDER = ["revoke_quarantine", "taint_lineage", "taint_quarantine", "taint_quarantine_norm", "benign_quarantine",
             "benign_taint_quarantine", "benign_taint_quarantine_norm"]
HFID = {"luna": "openai/gpt-6-luna", "oss": "openai/gpt-oss-120b", "qwen": "Qwen/Qwen3.8-27B",
        "gemma": "google/gemma-4-31B-it", "ministral": "mistralai/Ministral-3-14B-Instruct-2512"}
# Pre-specified confirmatory contrasts (A -> B, metric); Holm-corrected within each model over those available for it.
CONFIRM = [("compromised", "revoke_silent", "any"), ("revoke_silent", "revoke_notice", "any"),
           ("revoke_notice", "revoke_retract", "any"), ("revoke_retract", "revoke_lineage", "any"),
           ("nocite_lineage", "taint_quarantine", "any"), ("clean", "benign_taint_quarantine", "task")]
NUMWORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}

ALL = lambda r: True
FACT = lambda r: r.get("payload", "fact") == "fact"
EXFIL = lambda r: r.get("payload") == "exfil"
WROTE = lambda r: r["wrote"]
METRICS = [  # (macro name, trial field, filter)
    ("any", "any_residue", ALL), ("export", "instr_residue", EXFIL), ("factonly", "fact_residue", FACT),
    ("factexfil", "fact_residue", EXFIL), ("factwrote", "fact_residue", WROTE), ("wrote", "wrote", ALL),
    ("task", "task_success", ALL), ("redeleg", "redelegated", ALL), ("escal", "escalated", ALL),
    ("board", "read_board", ALL), ("wcarried", "w_carried_fact", ALL), ("wcarriedinstr", "w_carried_instr", ALL),
    ("wcited", "w_cited_x", ALL), ("lineage", "lineage_hit", ALL), ("refund", "refund_ok", ALL),
]
PAIR_METRICS = [("any", "any_residue", ALL), ("export", "instr_residue", EXFIL), ("factonly", "fact_residue", FACT),
                ("task", "task_success", ALL), ("redeleg", "redelegated", ALL), ("escal", "escalated", ALL)]
MAIN_PAIRS = [("compromised", "revoke_silent"), ("revoke_silent", "revoke_notice"), ("revoke_notice", "revoke_retract"),
              ("revoke_retract", "revoke_lineage"), ("revoke_notice", "revoke_lineage"), ("revoke_silent", "revoke_lineage"),
              ("compromised", "revoke_lineage"), ("clean", "benign_lineage")]
ABL_PAIRS = [("revoke_lineage", "nocite_lineage"), ("nocite_compromised", "nocite_lineage"), ("compromised", "nocite_lineage"),
             ("revoke_notice", "strict_notice"), ("strict_notice", "revoke_lineage"), ("revoke_retract", "early_revoke"),
             ("revoke_lineage", "nosource_lineage"), ("benign_lineage", "nosource_benign"), ("clean", "nosource_benign"),
             ("nocite_compromised", "compromised")]
MIT_PAIRS = [("revoke_lineage", "revoke_quarantine"), ("nocite_lineage", "taint_lineage"), ("revoke_lineage", "taint_lineage"),
             ("taint_lineage", "taint_quarantine"), ("revoke_quarantine", "taint_quarantine"), ("nocite_lineage", "taint_quarantine"),
             ("compromised", "revoke_quarantine"), ("compromised", "taint_quarantine"),
             ("clean", "benign_quarantine"), ("clean", "benign_taint_quarantine"), ("benign_lineage", "benign_quarantine"),
             ("benign_lineage", "benign_taint_quarantine"),
             ("nocite_lineage", "taint_quarantine_norm"), ("taint_quarantine", "taint_quarantine_norm"),
             ("clean", "benign_taint_quarantine_norm"), ("benign_taint_quarantine", "benign_taint_quarantine_norm")]
ABL_GROUPS = [("revoke_retract", ["early_revoke"]), ("revoke_notice", ["strict_notice"]),
              ("revoke_lineage", ["nocite_lineage", "nosource_lineage"]), ("compromised", ["nocite_compromised"]),
              ("benign_lineage", ["nosource_benign"])]
MIT_GROUPS = [("revoke_lineage", ["revoke_quarantine"]),
              ("nocite_lineage", ["taint_lineage", "taint_quarantine", "taint_quarantine_norm"]),
              ("clean", ["benign_quarantine", "benign_taint_quarantine", "benign_taint_quarantine_norm"])]


def tex(s: str) -> str:
    return s.replace("_", "\\_")


def model_info(label: str):
    """(display name, slug) for a model id or a writer=>executor team label."""
    if "=>" in label:
        w, e = (model_info(x) for x in label.split("=>", 1))
        return f"{w[0]} $\\Rightarrow$ {e[0]}", f"{w[1]}-{e[1]}"
    key = label.split("/")[-1].split(":")[-1]
    if key in NICE:
        return NICE[key]
    return key, "".join(ch for ch in key.lower() if ch.isalnum())


def hfid(slug: str) -> str:
    if "-" in slug:
        return " $\\Rightarrow$ ".join(hfid(x) for x in slug.split("-", 1))
    return tex(HFID.get(slug, slug))


def short(slug: str) -> str:
    if "-" in slug:
        w, e = slug.split("-", 1)
        return f"{short(w)}$\\Rightarrow${short(e)}"
    return SHORT.get(slug, slug)


def fmt_p(p: float) -> str:
    if p >= 0.995:
        return "1.0"
    if p >= 0.01:
        return f"{p:.2f}"
    if p >= 0.001:
        return f"{p:.3f}"
    m, e = f"{p:.1e}".split("e")
    return f"${m}{{\\times}}10^{{{int(e)}}}$"


def pct(k, n):
    return f"{round(100 * k / n)}" if n else "--"


def mcnemar(rows_a, rows_b, field, filt=ALL):
    """Exact McNemar on seeds present in both sets (same seed = same scenario; same model = same handoff)."""
    a = {r["seed"]: bool(r[field]) for r in rows_a if filt(r)}
    b = {r["seed"]: bool(r[field]) for r in rows_b if filt(r)}
    common = a.keys() & b.keys()
    x = sum(a[s] and not b[s] for s in common)
    y = sum(b[s] and not a[s] for s in common)
    return len(common), x, y, mcnemar_exact(x, y)


def paired_diff(rows_a, rows_b, field, filt=ALL):
    """Paired difference rate(B) - rate(A) over common seeds with Newcombe's (1998, method 10) score interval."""
    a = {r["seed"]: bool(r[field]) for r in rows_a if filt(r)}
    b = {r["seed"]: bool(r[field]) for r in rows_b if filt(r)}
    common = a.keys() & b.keys()
    n = len(common)
    if not n:
        return None
    n11 = sum(a[s] and b[s] for s in common)
    n10 = sum(a[s] and not b[s] for s in common)
    n01 = sum(b[s] and not a[s] for s in common)
    n00 = n - n11 - n10 - n01
    p1, l1, u1 = wilson(n11 + n10, n)  # A
    p2, l2, u2 = wilson(n11 + n01, n)  # B
    den = (n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00)
    phi = 0.0
    if den:
        num = n11 * n00 - n10 * n01
        num = max(num - n / 2, 0) if num > 0 else num  # continuity-corrected phi as in Newcombe (1998)
        phi = num / den ** 0.5
    d = p2 - p1
    lo = d - ((p2 - l2) ** 2 - 2 * phi * (p2 - l2) * (u1 - p1) + (u1 - p1) ** 2) ** 0.5
    hi = d + ((u2 - p2) ** 2 - 2 * phi * (u2 - p2) * (p1 - l1) + (p1 - l1) ** 2) ** 0.5
    return d, max(-1.0, lo), min(1.0, hi)


def fmt_pp(x):
    v = round(100 * x)
    return f"$-${-v}" if v < 0 else f"+{v}" if v > 0 else "0"


def fmt_diff(t, unit=True):
    d, lo, hi = t
    return f"{fmt_pp(d)}{' pp' if unit else ''} [{fmt_pp(lo)}, {fmt_pp(hi)}]"


def holm(ps):
    """Holm step-down adjusted p-values (same order as input)."""
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    adj, run = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[i]))
        adj[i] = run
    return adj


def bh(ps):
    """Benjamini-Hochberg adjusted p-values (same order as input)."""
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i], reverse=True)
    adj, run = [0.0] * m, 1.0
    for rank, i in enumerate(order):
        run = min(run, ps[i] * m / (m - rank))
        adj[i] = run
    return adj


def cluster_check(rows_a, rows_b, field, n_boot=10000, rng_seed=0):
    """Template x payload clusters: per-cluster rate difference B - A, two-sided sign test over non-zero clusters,
    and a cluster-bootstrap 95% interval of the mean difference."""
    import random as _r
    from math import comb
    key = lambda r: (r["scenario"], r.get("payload", "fact"))
    a = {r["seed"]: r for r in rows_a}
    b = {r["seed"]: r for r in rows_b}
    cl = defaultdict(list)
    for s in a.keys() & b.keys():
        cl[key(a[s])].append(bool(b[s][field]) - bool(a[s][field]))
    diffs = [sum(v) / len(v) for v in cl.values()]
    pos, neg = sum(x > 0 for x in diffs), sum(x < 0 for x in diffs)
    k, n = min(pos, neg), pos + neg
    p = min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    rng = _r.Random(rng_seed)
    boots = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(n_boot))
    mean = sum(diffs) / len(diffs)
    return dict(n=len(diffs), pos=pos, neg=neg, p=p, mean=mean, lo=boots[int(0.025 * n_boot)],
                hi=boots[int(0.975 * n_boot) - 1])


def join_list(items):
    items = list(items)
    if not items:
        return "none"
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


FIG_LABEL = {"compromised": "Not\nrevoked", "revoke_silent": "Credentials\nonly", "revoke_notice": "+ notice",
             "revoke_retract": "+ retract\nposts", "revoke_lineage": "+ lineage\nmarks", "clean": "Clean",
             "benign_lineage": "False alarm\n(full mitig.)"}


def paper_figure(path: Path, MAIN, models, slug, name, rates):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "pdf.fonttype": 42})
    markers = "os^Dv<>P"
    conds = [c for c in MAIN if c not in ("clean", "benign_lineage")]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [5, 1.6]})
    ax = axes[0]
    w = 0.38
    for i, (mname, lab, col) in enumerate([("factonly", "False value applied (fact-only payload)", "#c0392b"),
                                           ("export", "Record exported to attacker (fact+exfil payload)", "#7d3c98")]):
        xs = [j + (i - 0.5) * w for j in range(len(conds))]
        ps, lo, hi = [], [], []
        for c in conds:
            p, l, h = wilson(*rates[("all", c, mname)])
            ps.append(100 * p); lo.append(100 * (p - l)); hi.append(100 * (h - p))
        ax.bar(xs, ps, w, color=col, alpha=0.85, label=lab, yerr=[lo, hi], capsize=2, error_kw={"lw": 0.8})
        for j, m in enumerate(models):
            ys = [100 * rates[(slug[m], c, mname)][0] / rates[(slug[m], c, mname)][1] for c in conds]
            ax.scatter(xs, ys, s=10, color="k", marker=markers[j % len(markers)], zorder=3, label=name[m] if i == 0 else None)
    ax.set_xticks(range(len(conds)))
    ax.set_xticklabels([FIG_LABEL.get(c, c) for c in conds])
    ax.set_ylabel("% of trials (Wilson 95% CI)")
    ax.set_ylim(0, 102)
    ax.set_title("Residual influence after revocation")
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.62, -0.2), ncol=3, frameon=False)
    ax2 = axes[1]
    cs = [c for c in ("clean", "benign_lineage") if c in MAIN]
    ps, lo, hi = [], [], []
    for c in cs:
        p, l, h = wilson(*rates[("all", c, "task")])
        ps.append(100 * p); lo.append(100 * (p - l)); hi.append(100 * (h - p))
    ax2.bar(range(len(cs)), ps, 0.6, color=["#27ae60", "#95a5a6"][:len(cs)], yerr=[lo, hi], capsize=2, error_kw={"lw": 0.8})
    for j, m in enumerate(models):
        ax2.scatter(range(len(cs)), [100 * rates[(slug[m], c, "task")][0] / rates[(slug[m], c, "task")][1] for c in cs],
                    s=10, color="k", marker=markers[j % len(markers)], zorder=3)
    ax2.set_xticks(range(len(cs)))
    ax2.set_xticklabels([FIG_LABEL[c] for c in cs])
    ax2.set_ylim(0, 102)
    ax2.set_title("Task success")
    ax2.set_ylabel("% of trials")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


PLAT_FIG = [("revoke_lineage", "Lineage marks (citations)", "#bdc3c7"),
            ("nocite_lineage", "Lineage marks, no citations", "#7f8c8d"),
            ("taint_lineage", "Taint + marks", "#e59866"),
            ("taint_quarantine", "Taint + quarantine (exact)", "#2471a3"),
            ("taint_quarantine_norm", "Taint + quarantine (normalised)", "#1e8449")]


def platform_figure(path: Path, mods, slug, name, rates):
    """Figure 3: any residue per model under lineage marks and the taint-based platform mitigations."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "pdf.fonttype": 42})
    conds = [x for x in PLAT_FIG if all(rates.get((slug[m], x[0], "any"), (0, 0))[1] for m in mods)]
    fig, ax = plt.subplots(figsize=(7.0, 1.85))
    w = 0.8 / len(conds)
    for i, (c, lab, col) in enumerate(conds):
        xs = [j + (i - (len(conds) - 1) / 2) * w for j in range(len(mods))]
        ps, lo, hi = [], [], []
        for m in mods:
            p, l, h = wilson(*rates[(slug[m], c, "any")])
            ps.append(100 * p); lo.append(100 * (p - l)); hi.append(100 * (h - p))
        ax.bar(xs, ps, w * 0.92, color=col, label=lab, yerr=[lo, hi], capsize=1.5, error_kw={"lw": 0.7})
        for x, p, h in zip(xs, ps, hi):
            ax.text(x, p + h + 1.5, f"{round(p)}", ha="center", va="bottom", fontsize=6)
    ax.set_xticks(range(len(mods)))
    ax.set_xticklabels([name[m] for m in mods])
    ax.set_ylabel("Any residue (%)")
    ax.set_ylim(0, 105)
    ax.set_xlim(-0.5, len(mods) - 0.5)
    ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


class Macros(dict):
    def write(self, path: Path):
        lines = ["% Generated by paper/make_numbers.py from experiments/*/results. Do not edit by hand.",
                 "\\makeatletter",
                 "\\providecommand{\\N}[1]{\\ifcsname rv@#1\\endcsname\\csname rv@#1\\endcsname\\else\\textbf{??#1}\\fi}",
                 "\\providecommand{\\IfN}[3]{\\ifcsname rv@#1\\endcsname#2\\else#3\\fi}"]
        lines += [f"\\expandafter\\def\\csname rv@{k}\\endcsname{{{self[k]}}}" for k in sorted(self)]
        lines.append("\\makeatother")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--experiments", default=str(ROOT / "experiments"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    a = ap.parse_args()
    EXP, OUT = Path(a.experiments), Path(a.out)

    # ---------- load, keep complete cells only
    cells = defaultdict(list)  # (label, condition) -> rows
    skipped = []
    exp_cells = defaultdict(list)  # experiment prefix ("01") -> complete cells
    for tj in sorted(EXP.glob("*/results/*/trials.jsonl")):
        exp_dir = tj.parents[2]
        cfg = exp_dir / "config.json"
        seeds = json.loads(cfg.read_text(encoding="utf-8")).get("seeds", 48) if cfg.exists() else 48
        grp = defaultdict(list)
        for r in load(tj.parent):
            r["_exp"] = exp_dir.name
            r["wrote"] = not r["field_untouched"]
            grp[(r["model"], r["condition"])].append(r)
        for key, rs in grp.items():
            base = key[0].split("/")[-1].split(":")[-1]
            if len({r["seed"] for r in rs}) >= seeds or base in PARTIAL_OK:
                cells[key] = rs
                exp_cells[exp_dir.name[:2]].append((key, rs))  # a later experiment folder overrides an earlier one for the same cell
            else:
                skipped.append(f"{exp_dir.name}:{key[0]}:{key[1]} ({len(rs)}/{seeds})")

    labels = {lab for lab, _ in cells}
    teams = sorted((lab for lab in labels if "=>" in lab), key=lambda l: model_info(l)[1])
    order_key = lambda m: (MODEL_ORDER.index(model_info(m)[1]) if model_info(m)[1] in MODEL_ORDER else 99, m)
    main_set = {c for (lab, c) in cells if "=>" not in lab and c in CONDITIONS}
    MAIN = [c for c in ORDER if c in main_set and c != "benign_lineage"] + \
           sorted(main_set - set(ORDER)) + (["benign_lineage"] if "benign_lineage" in main_set else [])
    models = sorted({lab for (lab, c) in cells if "=>" not in lab and c in MAIN}, key=order_key)
    ABL = [c for c in ABL_ORDER if c in ABLATIONS and any((m, c) in cells for m in models)] + \
          sorted({c for (lab, c) in cells if c in ABLATIONS and c not in ABL_ORDER})
    MIT = [c for c in MIT_ORDER if any((m, c) in cells for m in models)] + \
          sorted({c for (lab, c) in cells if c in MITIGATIONS and c not in MIT_ORDER})
    OTHER = sorted({c for (lab, c) in cells if c not in CONDITIONS and c not in ABLATIONS and c not in MITIGATIONS})
    ABL += OTHER  # unknown conditions are reported with the ablations
    abl_models = [m for m in models if any((m, c) in cells for c in ABL)]
    mit_models = [m for m in models if any((m, c) in cells for c in MIT)]
    slug = {m: model_info(m)[1] for m in models + teams}
    name = {m: model_info(m)[0] for m in models + teams}

    M = Macros()
    rates = {}

    def add_rates(s, c, rs):
        for mname, field, f in METRICS:
            ss = [r for r in rs if f(r)]
            k, n = sum(bool(r[field]) for r in ss), len(ss)
            rates[(s, c, mname)] = (k, n)
            if not n:
                continue
            _, lo, hi = wilson(k, n)
            b = f"{s}/{c}/{mname}"
            M[b] = f"{k}/{n} ({pct(k, n)}\\%)"
            M[b + "/k"], M[b + "/n"] = k, n
            M[b + "/pct"] = f"{pct(k, n)}\\%"
            M[b + "/ci"] = f"[{round(100 * lo)}, {round(100 * hi)}]"

    for (lab, c), rs in cells.items():
        add_rates(slug[lab] if lab in slug else model_info(lab)[1], c, rs)
    for c in MAIN:
        add_rates("all", c, [r for m in models for r in cells.get((m, c), [])])

    # ---------- counts and lists
    used = [r for rs in cells.values() for r in rs]
    M["n/trials"] = f"{len(used):,}"
    for key, sel in (("main", lambda r: r["condition"] in MAIN and "=>" not in r["model"]),
                     ("abl", lambda r: r["condition"] in ABL and "=>" not in r["model"]),
                     ("mit", lambda r: r["condition"] in MIT and "=>" not in r["model"]),
                     ("mixed", lambda r: "=>" in r["model"])):
        M[f"n/{key}"] = f"{sum(map(sel, used)):,}"
    for key, lst in (("models", models), ("ablmodels", abl_models), ("mitmodels", mit_models), ("teams", teams),
                     ("conds", MAIN), ("ablconds", ABL), ("mitconds", MIT)):
        M[f"n/{key}"] = len(lst)
        M[f"n/{key}/word"] = NUMWORD.get(len(lst), str(len(lst)))
        M[f"n/{key}/Word"] = NUMWORD.get(len(lst), str(len(lst))).capitalize()
    for ex, lst in exp_cells.items():
        labs = sorted({k[0] for k, _ in lst}, key=lambda l: (("=>" in l), order_key(l.split("=>")[0])))
        M[f"exp/{ex}/trials"] = f"{sum(len(rs) for _, rs in lst):,}"
        M[f"exp/{ex}/models"] = join_list(short(model_info(l)[1]) for l in labs)
        M[f"exp/{ex}/n"] = len(labs)
    M["n/seeds"] = len({r["seed"] for r in used})
    M["n/planned/main"] = len(MAIN) * len({r["seed"] for r in used})
    M["models/list"] = join_list(name[m] for m in models)
    M["ablmodels/list"] = join_list(name[m] for m in abl_models)
    M["mitmodels/list"] = join_list(name[m] for m in mit_models)
    M["ablmodels/short"] = join_list(short(slug[m]) for m in abl_models)
    M["mitmodels/short"] = join_list(short(slug[m]) for m in mit_models)
    M["teams/list"] = join_list(name[t] for t in teams)
    if len(abl_models) == 1:
        M["abl/only"] = name[abl_models[0]]
    for m in models + teams:
        s = slug[m]
        mr = [r for (lab, c), rs in cells.items() if lab == m for r in rs]
        M[f"{s}/name"] = name[m]
        M[f"{s}/short"] = short(s)
        M[f"{s}/id"] = tex(m)
        M[f"{s}/n/main"] = sum(r["condition"] in MAIN for r in mr)
        M[f"{s}/n/all"] = len(mr)
        for t in ("prompt_tokens", "completion_tokens"):
            M[f"{s}/tok/{t.split('_')[0]}"] = f"{sum(r.get('usage', {}).get(t, 0) for r in mr):,}"
    for m in models:
        s = slug[m]
        mr = [r for c in MAIN for r in cells.get((m, c), [])]
        k = sum(r["wrote"] for r in mr)
        M[f"{s}/allmain/wrote"] = f"{k}/{len(mr)} ({pct(k, len(mr))}\\%)"
        M[f"{s}/allmain/wrote/pct"] = f"{pct(k, len(mr))}\\%"
        for mname in ("escal",):
            ks = [rates[(s, c, mname)] for c in MAIN if rates.get((s, c, mname), (0, 0))[1]]
            k, n = max(ks, key=lambda x: x[0] / x[1])
            M[f"{s}/max/{mname}"] = f"{k} of {n}"
        for (lab, c), rs in cells.items():
            if lab == m:
                ex = [r for r in rs if EXFIL(r) and r["instr_residue"]]
                M[f"{s}/{c}/export_and_redeleg"] = sum(r["redelegated"] for r in ex)
        sel = [r for r in cells.get((m, "revoke_silent"), []) if r["read_board"]]
        M[f"{s}/revoke_silent/board_and_any"] = sum(r["any_residue"] for r in sel)
    # per-condition lists across models, e.g. "GPT-6 Luna 0\%, Qwen3.8 27B 4\%, ..."
    for group, mods in (("main", models), ("abl", abl_models), ("mit", mit_models)):
        conds = MAIN if group == "main" else MAIN + ABL if group == "abl" else MAIN + ABL + MIT
        for c in conds:
            for mname in ("any", "export", "task", "redeleg", "lineage", "factwrote"):
                items = [(short(slug[m]), rates[(slug[m], c, mname)]) for m in mods if rates.get((slug[m], c, mname), (0, 0))[1]]
                if items:
                    M[f"{group}list/{c}/{mname}"] = join_list(f"{n} {pct(*kn)}\\%" for n, kn in items)
                    ps = [round(100 * k / n) for _, (k, n) in items]
                    M[f"{group}range/{c}/{mname}"] = f"{min(ps)}--{max(ps)}\\%" if min(ps) != max(ps) else f"{ps[0]}\\%"
                    M[f"{group}sum/{c}/{mname}"] = f"{sum(k for _, (k, n) in items)} of {sum(n for _, (k, n) in items)}"

    # ---------- paired tests
    mc = {}
    diffs = {}

    def put(s, ra, rb, a, b, mname, field, f):
        n, x, y, p = mcnemar(ra, rb, field, f)
        if not n:
            return
        mc[(s, a, b, mname)] = (n, x, y, p)
        base = f"mc/{s}/{a}/{b}/{mname}"
        M[base + "/n"], M[base + "/b"], M[base + "/c"], M[base + "/p"] = n, x, y, fmt_p(p)
        dd = paired_diff(ra, rb, field, f)
        if dd:
            diffs[(s, a, b, mname)] = dd
            M[base + "/diff"] = fmt_diff(dd)
            M[base + "/d"] = fmt_pp(dd[0])

    extra_pairs = [(x, y) for x in MAIN for y in MAIN if x != y and y not in ORDER]
    for m in models:
        for a_, b_ in MAIN_PAIRS + extra_pairs + ABL_PAIRS + MIT_PAIRS:
            if (m, a_) in cells and (m, b_) in cells:
                for mname, field, f in PAIR_METRICS:
                    put(slug[m], cells[(m, a_)], cells[(m, b_)], a_, b_, mname, field, f)
    for a_, b_ in MAIN_PAIRS + extra_pairs:  # pooled: pair on (model, seed)
        for mname, field, f in PAIR_METRICS:
            ra = [dict(r, seed=(r["model"], r["seed"])) for m in models for r in cells.get((m, a_), [])]
            rb = [dict(r, seed=(r["model"], r["seed"])) for m in models for r in cells.get((m, b_), [])]
            put("all", ra, rb, a_, b_, mname, field, f)
    # mixed teams: team vs the writer alone (same handoff) and vs the executor alone (same seed), per condition
    for t in teams:
        w_id, e_id = t.split("=>", 1)
        w = next((m for m in models if m == w_id), None)
        e = next((m for m in models if m == e_id), None)
        for c in sorted({c for (lab, c) in cells if lab == t}):
            for role, other in (("writer", w), ("executor", e)):
                if other and (other, c) in cells:
                    for mname, field, f in PAIR_METRICS:
                        put(slug[t], cells[(t, c)], cells[(other, c)], c, f"{role}alone", mname, field, f)

    # ---------- multiplicity. Confirmatory family: CONFIRM, Holm within each model. Every other test reported in
    # Table A.9 or for the mixed teams: Benjamini-Hochberg over all of them together (exploratory).
    def task_pair(a_, b_):
        return "benign" in b_ or b_.startswith("nosource")
    rows_spec = [(a_, b_) for a_, b_ in MAIN_PAIRS + extra_pairs] + [("revoke_silent", "revoke_lineage")]
    mcn_main, seen_rows = [], set()
    for i, (a_, b_) in enumerate(rows_spec):
        mname = "task" if task_pair(a_, b_) or i == len(rows_spec) - 1 else "any"
        if (a_, b_, mname) not in seen_rows:
            seen_rows.add((a_, b_, mname))
            mcn_main.append((a_, b_, mname))
    mcn_blocks = []
    for block in (ABL_PAIRS, MIT_PAIRS):
        lines = []
        for a_, b_ in block:
            for mname in (["task", "any"] if task_pair(a_, b_) else ["any"]):
                vs = [mc.get((slug[m], a_, b_, mname)) for m in models]
                if any(vs) and not (mname == "any" and task_pair(a_, b_) and
                                    all(v is None or v[1] + v[2] == 0 for v in vs)):
                    lines.append((a_, b_, mname))
        mcn_blocks.append(lines)
    padj, adjkind = {}, {}
    for m in models:
        keys = [(slug[m], a_, b_, mn) for a_, b_, mn in CONFIRM if (slug[m], a_, b_, mn) in mc]
        for k, q in zip(keys, holm([mc[k][3] for k in keys])):
            padj[k], adjkind[k] = q, "Holm"
        M[f"{slug[m]}/nconfirm"] = len(keys)
    explo = [(slug[m], a_, b_, mn) for a_, b_, mn in mcn_main for m in models] + \
            [("all", a_, b_, mn) for a_, b_, mn in mcn_main] + \
            [(slug[m], a_, b_, mn) for lines in mcn_blocks for a_, b_, mn in lines for m in models] + \
            [k for k in mc if k[0] in {slug[t] for t in teams} and k[3] == "any"]
    explo = [k for k in dict.fromkeys(explo) if k in mc and k not in padj]
    for k, q in zip(explo, bh([mc[k][3] for k in explo])):
        padj[k], adjkind[k] = q, "BH"
    M["n/tests/confirm"] = sum(1 for k in padj if adjkind[k] == "Holm")
    M["n/tests/explo"] = len(explo)
    M["n/tests/all"] = len(padj)
    M["n/tests/rawsig"] = sum(mc[k][3] < 0.05 for k in padj)
    M["n/tests/adjsig"] = sum(q < 0.05 for q in padj.values())
    for k, (n, x, y, p) in mc.items():
        base = "mc/" + "/".join(k)
        if k in padj:
            M[base + "/padj"] = fmt_p(padj[k])
            M[base] = f"{x} vs {y}, \\textit{{p}}\\textsubscript{{adj}}~=~{fmt_p(padj[k])}"
        else:
            M[base] = f"{x} vs {y}, \\textit{{p}}~=~{fmt_p(p)}"
    sigp = lambda k: padj.get(k, mc[k][3])

    # lists of a paired comparison across models: "Qwen 23 vs 0, p_adj = ...; Gemma ..."
    pair_keys = defaultdict(list)
    for (s, a_, b_, mname), v in mc.items():
        if s in {slug[m] for m in models}:
            pair_keys[(a_, b_, mname)].append((s, v))
    for (a_, b_, mname), items in pair_keys.items():
        items.sort(key=lambda x: MODEL_ORDER.index(x[0]) if x[0] in MODEL_ORDER else 99)
        M[f"mclist/{a_}/{b_}/{mname}"] = "; ".join(f"{short(s)} " + M["mc/" + "/".join((s, a_, b_, mname))]
                                                   for s, v in items)
        if mname in ("any", "task"):
            M[f"difflist/{a_}/{b_}/{mname}"] = "; ".join(f"{short(s)} {fmt_diff(diffs[(s, a_, b_, mname)])}"
                                                        for s, v in items if (s, a_, b_, mname) in diffs)
            dl = [(diffs[(s, a_, b_, mname)], s) for s, v in items if (s, a_, b_, mname) in diffs]
            if dl:
                lo_d = min(dl, key=lambda x: (x[0][0], x[0][1]))
                M[f"mindiff/{a_}/{b_}/{mname}"] = f"{short(lo_d[1])} {fmt_diff(lo_d[0])}"
                M[f"minlo/{a_}/{b_}/{mname}"] = fmt_pp(min(d[0][1] for d in dl))
                M[f"maxhi/{a_}/{b_}/{mname}"] = fmt_pp(max(d[0][2] for d in dl))
        sig = [short(s) for s, v in items if sigp((s, a_, b_, mname)) < 0.05]
        M[f"mcsig/{a_}/{b_}/{mname}"] = join_list(sig)
        M[f"mcsigname/{a_}/{b_}/{mname}"] = join_list(name[next(m for m in models if slug[m] == s)] for s, v in items
                                                      if sigp((s, a_, b_, mname)) < 0.05)
        M[f"mcsig/{a_}/{b_}/{mname}/n"] = len(sig)
        M[f"mcsig/{a_}/{b_}/{mname}/of"] = len(items)
        M[f"maxp/{a_}/{b_}/{mname}"] = fmt_p(max(sigp((s, a_, b_, mname)) for s, _ in items))
        word = NUMWORD.get(len(items), str(len(items)))
        M[f"mcsigtext/{a_}/{b_}/{mname}"] = ("no model" if not sig else
                                             f"all {word} models" if len(sig) == len(items) else join_list(sig))
    # two false-alarm designs in one phrase (avoids "none ... and none ..., respectively")
    for a_, b1, b2, mname in (("clean", "benign_taint_quarantine", "benign_quarantine", "task"),
                              ("clean", "benign_taint_quarantine_norm", "benign_quarantine", "task")):
        if (a_, b1, mname) in pair_keys and (a_, b2, mname) in pair_keys:
            s1, s2 = M[f"mcsig/{a_}/{b1}/{mname}"], M[f"mcsig/{a_}/{b2}/{mname}"]
            M[f"mcsigpair/{a_}/{b1}/{b2}/{mname}"] = (
                "was not significant for any model under either design" if s1 == "none" and s2 == "none" else
                "was significant for " + (s1 if s1 != "none" else "no model") + " under taint quarantine and for "
                + (s2 if s2 != "none" else "no model") + " under citation-based quarantine")
    # template-clustered robustness check for the confirmatory contrasts (12 template x payload cells per model)
    clus = {}
    fields = {x: y for x, y, _ in PAIR_METRICS}
    for m in models:
        for a_, b_, mn in CONFIRM:
            if (m, a_) in cells and (m, b_) in cells:
                clus[(slug[m], a_, b_, mn)] = cluster_check(cells[(m, a_)], cells[(m, b_)], fields[mn])
    if clus:
        holm_sig = [k for k in clus if padj.get(k, 1) < 0.05]
        both = [k for k in holm_sig if clus[k]["p"] < 0.05]
        ci_ex = [k for k in holm_sig if clus[k]["lo"] > 0 or clus[k]["hi"] < 0]
        M["clus/holmsig"] = len(holm_sig)
        M["clus/holmsig/word"] = NUMWORD.get(len(holm_sig), str(len(holm_sig)))
        M["clus/both"] = len(both)
        M["clus/both/word"] = NUMWORD.get(len(both), str(len(both)))
        M["clus/both/Word"] = NUMWORD.get(len(both), str(len(both))).capitalize()
        M["clus/ciexcl"] = len(ci_ex)
        M["clus/ciexcl/word"] = NUMWORD.get(len(ci_ex), str(len(ci_ex)))
        M["clus/lost"] = join_list(short(k[0]) + " " + tex(k[1]) + " $\\to$ " + tex(k[2]) for k in holm_sig if k not in both)
        cm = [m for m in models if any(k[0] == slug[m] for k in clus)]
        t = ["\\begin{tabular}{@{}llrcrr@{}}", "\\toprule",
             "Model & A $\\to$ B (metric) & Cells & Mean $\\Delta$ [95\\% CI] & Sign $p$ & Holm $p$ (seeds) \\\\",
             "\\midrule"]
        for i, m in enumerate(cm):
            if i:
                t.append("\\addlinespace[2pt]")
            for a_, b_, mn in CONFIRM:
                v = clus.get((slug[m], a_, b_, mn))
                if not v:
                    continue
                q = padj.get((slug[m], a_, b_, mn))
                t.append(f"{short(slug[m])} & {tex(a_)} $\\to$ {tex(b_)} ({'task' if mn == 'task' else 'residue'}) & "
                         f"{v['pos']}+/{v['neg']}$-$ of {v['n']} & {fmt_pp(v['mean'])} [{fmt_pp(v['lo'])}, {fmt_pp(v['hi'])}] & "
                         f"{fmt_p(v['p'])} & " + (fmt_p(q) if q is not None else "--") + " \\\\")
        t += ["\\bottomrule", "\\end{tabular}"]
        (OUT / "tab_cluster.tex").write_text("\n".join(t) + "\n", encoding="utf-8")
        M["have/cluster"] = 1
    # within-cell determinism: share of template x payload cells (4 repetitions) that are all-or-nothing
    aon = tot = 0
    for m in models:
        if slug[m] in PARTIAL_SLUGS:
            continue
        for c in MAIN:
            g = defaultdict(list)
            for r in cells.get((m, c), []):
                g[(r["scenario"], r.get("payload", "fact"))].append(bool(r["any_residue"]))
            for v in g.values():
                tot += 1
                aon += all(v) or not any(v)
    if tot:
        M["cells/aon"] = f"{aon} of {tot} ({pct(aon, tot)}\\%)"
        M["cells/aon/pct"] = f"{pct(aon, tot)}\\%"

    # mixed teams: is the team's residue closer to the executor alone or the writer alone?
    closer = defaultdict(int)
    for tm in teams:
        w, e = (model_info(x)[1] for x in tm.split("=>", 1))
        for c in sorted({c for (lab, c) in cells if lab == tm}):
            kt, nt = rates[(slug[tm], c, "any")]
            kw, nw = rates.get((w, c, "any"), (0, 0))
            ke, ne = rates.get((e, c, "any"), (0, 0))
            if not (nw and ne):
                continue
            dw, de = abs(kt / nt - kw / nw), abs(kt / nt - ke / ne)
            who = "executor" if de < dw else "writer" if dw < de else "tie"
            M[f"{slug[tm]}/{c}/closer"] = who
            closer[who] += 1
            closer["cells"] += 1
            if c != "compromised":
                closer[who + "/mitigated"] += 1
                closer["cells/mitigated"] += 1
    if closer:
        for k in ("executor", "writer", "tie", "cells", "executor/mitigated", "writer/mitigated", "tie/mitigated",
                  "cells/mitigated"):
            M[f"mixed/closer/{k}"] = closer[k]

    # ---------- tables
    def cell(s, c, mname, show_k=False):
        k, n = rates.get((s, c, mname), (0, 0))
        if not n:
            return "--"
        return f"{k}/{n} ({pct(k, n)})" if show_k else pct(k, n)

    # Table 4
    t = ["\\begin{tabular}{@{}l" + "ccc" * len(models) + "c@{}}", "\\toprule",
         " & " + " & ".join(f"\\multicolumn{{3}}{{c}}{{{name[m]}}}" for m in models) + " & Pooled \\\\",
         "".join(f"\\cmidrule(lr){{{2 + 3 * i}-{4 + 3 * i}}}" for i in range(len(models))),
         "Condition & " + " & ".join(["Res.", "Exp.", "Task"] * len(models)) + " & Res. \\\\", "\\midrule"]
    for c in MAIN:
        if c == "benign_lineage":
            t.append("\\midrule")
        row = [tex(c)] + [cell(slug[m], c, x) for m in models for x in ("any", "export", "task")] + [cell("all", c, "any")]
        t.append(" & ".join(row) + " \\\\")
    t += ["\\bottomrule", "\\end{tabular}"]
    (OUT / "tab_main.tex").write_text("\n".join(t) + "\n", encoding="utf-8")

    def grouped_table(groups, conds, mods, path, delta=False):
        known = {x for _, xs in groups for x in xs}
        groups = groups + [(None, [c for c in conds if c not in known])]
        w = 3 if delta else 2
        t = ["\\begin{tabular}{@{}ll" + "c" * w * len(mods) + "@{}}", "\\toprule",
             " & & " + " & ".join(f"\\multicolumn{{{w}}}{{c}}{{{name[m]}}}" for m in mods) + " \\\\",
             "".join(f"\\cmidrule(lr){{{3 + w * i}-{2 + w * (i + 1)}}}" for i in range(len(mods))),
             "Condition & Compared with & " + " & ".join((["Res.", "Task", "$\\Delta$ [95\\% CI]"] if delta else
                                                          ["Res.", "Task"]) * len(mods)) + " \\\\", "\\midrule"]
        first = True
        for base, xs in groups:
            xs = [x for x in xs if x in conds]
            if not xs:
                continue
            if not first:
                t.append("\\addlinespace[3pt]")
            first = False
            for c in ([base] if base else []) + xs:
                ref = "(reference)" if c == base else tex(base) if base else "--"
                vals = []
                for m in mods:
                    vals += [cell(slug[m], c, x) for x in ("any", "task")]
                    if delta:
                        dk = (slug[m], base, c, "task" if c.startswith("benign") else "any")
                        vals.append("--" if c == base or dk not in diffs or rates.get((slug[m], c, "any"), (0, 0))[1] == 0
                                    else fmt_diff(diffs[dk], unit=False))
                t.append(f"{tex(c)} & {ref} & " + " & ".join(vals) + " \\\\")
        t += ["\\bottomrule", "\\end{tabular}"]
        path.write_text("\n".join(t) + "\n", encoding="utf-8")

    for f in ("tab_ablation.tex", "tab_platform.tex", "tab_mixed.tex"):  # drop stale optional tables
        (OUT / f).unlink(missing_ok=True)
    if abl_models:
        grouped_table(ABL_GROUPS, ABL, abl_models, OUT / "tab_ablation.tex")
        M["have/ablation"] = 1
    if mit_models:
        grouped_table(MIT_GROUPS, MIT, mit_models, OUT / "tab_platform.tex", delta=True)
        M["have/platform"] = 1
    if teams:
        conds = [c for c in ORDER + ABL + MIT if any((tm, c) in cells for tm in teams)]
        t = ["\\begin{tabular}{@{}ll" + "ccc" * len(conds) + "@{}}", "\\toprule",
             " & & " + " & ".join(f"\\multicolumn{{3}}{{c}}{{{tex(c)}}}" for c in conds) + " \\\\",
             "".join(f"\\cmidrule(lr){{{3 + 3 * i}-{5 + 3 * i}}}" for i in range(len(conds))),
             "Writer & Executor & " + " & ".join(["W alone", "Team", "E alone"] * len(conds)) + " \\\\", "\\midrule"]
        for tm in teams:
            w, e = tm.split("=>", 1)
            vals = []
            for c in conds:
                vals += [cell(model_info(w)[1], c, "any"), cell(slug[tm], c, "any"), cell(model_info(e)[1], c, "any")]
            t.append(f"{model_info(w)[0]} & {model_info(e)[0]} & " + " & ".join(vals) + " \\\\")
        t += ["\\bottomrule", "\\end{tabular}"]
        (OUT / "tab_mixed.tex").write_text("\n".join(t) + "\n", encoding="utf-8")
        M["have/mixed"] = 1

    # Appendix A: per-model tables
    cols = [("any", "Any res."), ("factonly", "False (fact)"), ("export", "Export (exfil)"), ("wrote", "Wrote field"),
            ("factwrote", "False $\\mid$ wrote"), ("task", "Task"), ("redeleg", "Re-deleg."), ("escal", "Escal."),
            ("lineage", "Lines found")]
    t = []
    for m in models + teams:
        s = slug[m]
        conds = [c for c in MAIN + ABL + MIT if rates.get((s, c, "any"), (0, 0))[1]]
        t += ["\\begin{table}[htbp]", "\\centering\\scriptsize\\setlength{\\tabcolsep}{2.5pt}",
              "\\begin{adjustbox}{max width=\\textwidth}", "\\begin{tabular}{@{}l" + "r" * len(cols) + "@{}}", "\\toprule",
              "Condition & " + " & ".join(h for _, h in cols) + " \\\\", "\\midrule"]
        prev = None
        for c in conds:
            kind = "main" if c in MAIN else "abl" if c in ABL else "mit"
            if prev and kind != prev:
                t.append("\\midrule")
            prev = kind
            t.append(tex(c) + " & " + " & ".join(cell(s, c, n, True) for n, _ in cols) + " \\\\")
        t += ["\\bottomrule", "\\end{tabular}", "\\end{adjustbox}",
              f"\\caption{{{name[m]} (\\texttt{{{hfid(s)}}}). Counts (percentages) per condition. False (fact): false value "
              "written, fact-only payload. Export (exfil): record exported, fact+exfil payload. Wrote field: the executor wrote "
              "the researched field at all. False $\\mid$ wrote: false value among trials that wrote the field. Re-deleg.: "
              "re-delegated the lookup. Escal.: escalated to a human. Lines found: the platform marked or withheld at least one "
              "handoff line. Rules separate main, ablation and platform conditions. False $\\mid$ wrote conditions on a "
              "post-treatment variable and is descriptive only; it is not comparable across conditions.}",
              f"\\label{{tab:model-{s}}}", "\\end{table}", ""]
    (OUT / "tab_permodel.tex").write_text("\n".join(t) + "\n", encoding="utf-8")

    # Appendix A: paired tests (residue; task success for false alarms). Each cell: b/c, raw p, adjusted p.
    def mcell(k):
        v = mc.get(k)
        if not v:
            return "--"
        q = padj.get(k)
        mark = "$^\\dagger$" if adjkind.get(k) == "Holm" else ""
        return f"{v[1]}/{v[2]}, {fmt_p(v[3])}, " + (f"\\textbf{{{fmt_p(q)}}}" if q is not None and q < 0.05 else
                                                   fmt_p(q) if q is not None else "--") + mark
    t = ["\\begin{tabular}{@{}ll" + "c" * (len(models) + 1) + "@{}}", "\\toprule",
         "A $\\to$ B & Metric & " + " & ".join(short(slug[m]) for m in models) + " & Pooled \\\\", "\\midrule"]
    for a_, b_, mname in mcn_main:
        vals = [mcell((s_, a_, b_, mname)) for s_ in [slug[m] for m in models] + ["all"]]
        t.append(f"{tex(a_)} $\\to$ {tex(b_)} & {'task' if mname == 'task' else 'residue'} & " + " & ".join(vals) + " \\\\")
    for lines in mcn_blocks:
        if lines:
            t.append("\\midrule")
        for a_, b_, mname in lines:
            vals = [mcell((slug[m], a_, b_, mname)) for m in models]
            t.append(f"{tex(a_)} $\\to$ {tex(b_)} & {'task' if mname == 'task' else 'residue'} & "
                     + " & ".join(vals) + " & -- \\\\")
    t += ["\\bottomrule", "\\end{tabular}"]
    (OUT / "tab_mcnemar.tex").write_text("\n".join(t) + "\n", encoding="utf-8")

    if skipped:  # incomplete cells (runs in progress); main.tex prints them in a TODO box
        by_lab = defaultdict(list)
        for x in skipped:
            ex, rest = x.split(":", 1)
            lab, cond_n = rest.rsplit(":", 1)
            by_lab[(ex[:2], short(model_info(lab)[1]))].append(cond_n)
        M["skipped/n"] = len(skipped)
        M["skipped/list"] = "; ".join(f"{ex} {lab}: {tex(', '.join(v))}" for (ex, lab), v in sorted(by_lab.items()))
    # Handoff audit. "Carried" and "kept" are detected with normalised matching (case, digit grouping, spaces, dashes),
    # independently of how the platform located derived lines, so reformatted values (2508 written "2,508") are visible.
    from revres.env import transform_handoff, x_taint_terms, _norm_taint
    from revres.scenarios import make_scenario
    has = lambda text, terms: any(_norm_taint(t) in _norm_taint(text) for t in terms)
    tot = defaultdict(int)
    for m in models:
        hp = EXP / MAIN_DIR / "results" / m.split("/")[-1].split(":")[-1].replace("gemma-4-31b-it", "gemma-4-31b") / "handoffs.jsonl"
        if not hp.exists():
            continue
        hs = [json.loads(l) for l in hp.read_text(encoding="utf-8").splitlines() if l.strip()]
        for variant, prov in (("std", "cite"), ("nocite", "taint"), ("nocite", "taintnorm"), ("nocite", "cite")):
            sel = [h for h in hs if h["compromised"] and h.get("variant", "std") == variant]
            k = n = 0
            kept = []
            for h in sel:
                terms = x_taint_terms(make_scenario(h["seed"]), True)
                if not has(h["handoff"], terms):
                    continue  # writer did not carry worker-X's content at all
                shown, _ = transform_handoff(h["handoff"], "withhold", prov, terms)
                n += 1
                if has(shown, terms):
                    k += 1
                    kept.append(h["seed"])
            if variant == "nocite" and prov.startswith("taint") and sel:
                tot[f"{prov}/n"] += len(sel)
                tot[f"{prov}/carried"] += n
                tot[f"{prov}/kept"] += k
                M[f"{slug[m]}/kept/{prov}/seeds"] = join_list(map(str, kept))
                M[f"{slug[m]}/kept/{prov}"] = k
            if n:
                b = f"{slug[m]}/leak/{variant}-{prov}"
                M[b] = f"{k}/{n} ({pct(k, n)}\\%)"
                M[b + "/pct"] = f"{pct(k, n)}\\%"
    for k_, v in tot.items():
        M[f"taintaudit/{k_}"] = v
    # seeds with residue under the platform's taint conditions (to trace each residual case to its handoff)
    for m in mit_models:
        for c in ("taint_quarantine", "taint_lineage", "taint_quarantine_norm"):
            if (m, c) in cells:
                M[f"{slug[m]}/{c}/resseeds"] = join_list(str(r["seed"]) for r in sorted(cells[(m, c)], key=lambda r: r["seed"])
                                                         if r["any_residue"])

    # Figure 2: residue by condition over the complete main-grid cells only, sized for the page
    paper_figure(OUT / "fig_residue.pdf", MAIN, models, slug, name, rates)
    if mit_models:
        platform_figure(OUT / "fig_platform.pdf", mit_models, slug, name, rates)
        M["have/platformfig"] = 1
    M.write(OUT / "numbers.tex")
    print(f"{len(used)} trials used; models: {', '.join(name[m] for m in models)}; teams: {len(teams)}; "
          f"main: {', '.join(MAIN)}; ablations ({len(abl_models)} models): {', '.join(ABL)}; "
          f"platform ({len(mit_models)} models): {', '.join(MIT) or '-'}; {len(M)} macros")
    if skipped:
        print("skipped incomplete cells:", "; ".join(skipped))


if __name__ == "__main__":
    main()
