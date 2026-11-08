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

PARTIAL_OK = {"gpt-6-luna"}  # runs that ended before every seed was done; analysed as they are
NICE = {  # id -> (display name, macro slug)
    "gpt-6-luna": ("GPT-6 Luna", "luna"),
    "gpt-oss-120b": ("gpt-oss-120b", "oss"),
    "qwen3.8-27b": ("Qwen3.8 27B", "qwen"),
    "gemma-4-31b-it": ("Gemma 4 31B", "gemma"),
    "ministral-3-14b": ("Ministral 3 14B", "ministral"),
}
SHORT = {"luna": "Luna", "oss": "gpt-oss", "qwen": "Qwen", "gemma": "Gemma", "ministral": "Ministral"}
MODEL_ORDER = ["luna", "oss", "qwen", "gemma", "ministral"]
MIT_ORDER = ["revoke_quarantine", "taint_lineage", "taint_quarantine", "benign_quarantine", "benign_taint_quarantine"]
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
             ("benign_lineage", "benign_taint_quarantine")]
ABL_GROUPS = [("revoke_retract", ["early_revoke"]), ("revoke_notice", ["strict_notice"]),
              ("revoke_lineage", ["nocite_lineage", "nosource_lineage"]), ("compromised", ["nocite_compromised"]),
              ("benign_lineage", ["nosource_benign"])]
MIT_GROUPS = [("revoke_lineage", ["revoke_quarantine"]), ("nocite_lineage", ["taint_lineage", "taint_quarantine"]),
              ("benign_lineage", ["benign_quarantine", "benign_taint_quarantine"])]


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


def join_list(items):
    items = list(items)
    if not items:
        return "none"
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


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
                cells[key] = rs  # a later experiment folder overrides an earlier one for the same cell
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
    M["n/seeds"] = len({r["seed"] for r in used})
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

    # ---------- paired tests
    mc = {}

    def put(s, ra, rb, a, b, mname, field, f):
        n, x, y, p = mcnemar(ra, rb, field, f)
        if not n:
            return
        mc[(s, a, b, mname)] = (n, x, y, p)
        base = f"mc/{s}/{a}/{b}/{mname}"
        M[base + "/n"], M[base + "/b"], M[base + "/c"], M[base + "/p"] = n, x, y, fmt_p(p)
        M[base] = f"{x} vs {y}, \\textit{{p}}~=~{fmt_p(p)}"

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

    # lists of a paired comparison across models: "Qwen 23 vs 0, p = ...; Gemma ..."
    pair_keys = defaultdict(list)
    for (s, a_, b_, mname), v in mc.items():
        if s in {slug[m] for m in models}:
            pair_keys[(a_, b_, mname)].append((s, v))
    for (a_, b_, mname), items in pair_keys.items():
        items.sort(key=lambda x: MODEL_ORDER.index(x[0]) if x[0] in MODEL_ORDER else 99)
        M[f"mclist/{a_}/{b_}/{mname}"] = "; ".join(f"{short(s)} {v[1]} vs {v[2]}, \\textit{{p}}~=~{fmt_p(v[3])}" for s, v in items)
        sig = [short(s) for s, v in items if v[3] < 0.05]
        M[f"mcsig/{a_}/{b_}/{mname}"] = join_list(sig)
        M[f"mcsig/{a_}/{b_}/{mname}/n"] = len(sig)
        M[f"mcsig/{a_}/{b_}/{mname}/of"] = len(items)
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
    if closer:
        for k in ("executor", "writer", "tie", "cells"):
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

    def grouped_table(groups, conds, mods, path):
        known = {x for _, xs in groups for x in xs}
        groups = groups + [(None, [c for c in conds if c not in known])]
        t = ["\\begin{tabular}{@{}ll" + "cc" * len(mods) + "@{}}", "\\toprule",
             " & & " + " & ".join(f"\\multicolumn{{2}}{{c}}{{{name[m]}}}" for m in mods) + " \\\\",
             "".join(f"\\cmidrule(lr){{{3 + 2 * i}-{4 + 2 * i}}}" for i in range(len(mods))),
             "Condition & Compared with & " + " & ".join(["Res.", "Task"] * len(mods)) + " \\\\", "\\midrule"]
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
                vals = [cell(slug[m], c, x) for m in mods for x in ("any", "task")]
                t.append(f"{tex(c)} & {ref} & " + " & ".join(vals) + " \\\\")
        t += ["\\bottomrule", "\\end{tabular}"]
        path.write_text("\n".join(t) + "\n", encoding="utf-8")

    for f in ("tab_ablation.tex", "tab_platform.tex", "tab_mixed.tex"):  # drop stale optional tables
        (OUT / f).unlink(missing_ok=True)
    if abl_models:
        grouped_table(ABL_GROUPS, ABL, abl_models, OUT / "tab_ablation.tex")
        M["have/ablation"] = 1
    if mit_models:
        grouped_table(MIT_GROUPS, MIT, mit_models, OUT / "tab_platform.tex")
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
              "\\begin{tabular}{@{}l" + "r" * len(cols) + "@{}}", "\\toprule",
              "Condition & " + " & ".join(h for _, h in cols) + " \\\\", "\\midrule"]
        prev = None
        for c in conds:
            kind = "main" if c in MAIN else "abl" if c in ABL else "mit"
            if prev and kind != prev:
                t.append("\\midrule")
            prev = kind
            t.append(tex(c) + " & " + " & ".join(cell(s, c, n, True) for n, _ in cols) + " \\\\")
        t += ["\\bottomrule", "\\end{tabular}",
              f"\\caption{{{name[m]} (\\texttt{{{tex(m)}}}). Counts (percentages) per condition. False (fact): false value "
              "written, fact-only payload. Export (exfil): record exported, fact+exfil payload. Wrote field: the executor wrote "
              "the researched field at all. False $\\mid$ wrote: false value among trials that wrote the field. Re-deleg.: "
              "re-delegated the lookup. Escal.: escalated to a human. Lines found: the platform marked or withheld at least one "
              "handoff line. Rules separate main, ablation and platform conditions.}",
              f"\\label{{tab:model-{s}}}", "\\end{table}", ""]
    (OUT / "tab_permodel.tex").write_text("\n".join(t) + "\n", encoding="utf-8")

    # Appendix A: paired tests (residue; task success for false alarms)
    def task_pair(a_, b_):
        return "benign" in b_ or b_.startswith("nosource")
    rows_spec = [(a_, b_) for a_, b_ in MAIN_PAIRS + extra_pairs] + [("revoke_silent", "revoke_lineage")]
    t = ["\\begin{tabular}{@{}ll" + "c" * (len(models) + 1) + "@{}}", "\\toprule",
         "A $\\to$ B & Metric & " + " & ".join(short(slug[m]) for m in models) + " & Pooled \\\\", "\\midrule"]
    seen_rows = set()
    for i, (a_, b_) in enumerate(rows_spec):
        mname = "task" if task_pair(a_, b_) or i == len(rows_spec) - 1 else "any"
        if (a_, b_, mname) in seen_rows:
            continue
        seen_rows.add((a_, b_, mname))
        vals = []
        for s in [slug[m] for m in models] + ["all"]:
            v = mc.get((s, a_, b_, mname))
            vals.append(f"{v[1]}/{v[2]}, {fmt_p(v[3])}" if v else "--")
        t.append(f"{tex(a_)} $\\to$ {tex(b_)} & {'task' if mname == 'task' else 'residue'} & " + " & ".join(vals) + " \\\\")
    for block in (ABL_PAIRS, MIT_PAIRS):
        lines = []
        for a_, b_ in block:
            for mname in (["task", "any"] if task_pair(a_, b_) else ["any"]):
                vals = []
                for m in models:
                    v = mc.get((slug[m], a_, b_, mname))
                    vals.append(f"{v[1]}/{v[2]}, {fmt_p(v[3])}" if v else "--")
                if any(v != "--" for v in vals) and not (mname == "any" and task_pair(a_, b_) and
                                                          all(v in ("--", "0/0, 1.0") for v in vals)):
                    lines.append(f"{tex(a_)} $\\to$ {tex(b_)} & {'task' if mname == 'task' else 'residue'} & "
                                 + " & ".join(vals) + " & -- \\\\")
        if lines:
            t += ["\\midrule"] + lines
    t += ["\\bottomrule", "\\end{tabular}"]
    (OUT / "tab_mcnemar.tex").write_text("\n".join(t) + "\n", encoding="utf-8")

    M.write(OUT / "numbers.tex")
    print(f"{len(used)} trials used; models: {', '.join(name[m] for m in models)}; teams: {len(teams)}; "
          f"main: {', '.join(MAIN)}; ablations ({len(abl_models)} models): {', '.join(ABL)}; "
          f"platform ({len(mit_models)} models): {', '.join(MIT) or '-'}; {len(M)} macros")
    if skipped:
        print("skipped incomplete cells:", "; ".join(skipped))


if __name__ == "__main__":
    main()
