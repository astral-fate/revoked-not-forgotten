"""Numbers and tables for the experiments that address the first study's limitations (08-13) and the re-grading.

Writes
  paper/numbers_ext.tex   \\N{x/...} macros
  paper/tab_ext.tex       main-text table: each limitation, the test, and the pooled result
  paper/tab_ext_app.tex   appendix table: every new condition x model
Cells are used only when complete (every seed of the experiment). Comparators from 01/04/06 use the same seeds
(paired by seed; same model, and for 09/10/13 the same cached handoffs), so McNemar tests are exact and paired.

Usage:  python paper/make_ext.py
"""
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
from make_numbers import Macros, cluster_check, fmt_p, mcnemar, pct, wilson  # noqa: E402
from revres.grade import grade_norm  # noqa: E402
from revres.scenarios import make_scenario  # noqa: E402

EXP = ROOT / "experiments"
MODELS = {"gpt-6-luna": ("GPT-6 Luna", "luna"), "gemma-4-31b": ("Gemma", "gemma"), "qwen3.8-27b": ("Qwen", "qwen"), "ministral-3-14b": ("Ministral", "ministral")}


def rows(folder: Path):
    p = folder / "trials.jsonl"
    if not p.exists():
        return {}
    out = defaultdict(dict)
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["condition"]][r["seed"]] = r  # a re-run of a seed replaces the earlier record
    return {c: list(v.values()) for c, v in out.items()}


def complete(cells, cond, n):
    rs = cells.get(cond, [])
    return rs if len({r["seed"] for r in rs}) >= n else None


def rate(rs, field="any_residue"):
    k = sum(bool(r[field]) for r in rs)
    return k, len(rs)


def fmt_rate(k, n):
    return f"{pct(k, n)}\\% ({k}/{n})"


def main():
    M = Macros()
    # ---------- load: base cells (01, 04, 06) and new experiments, per model
    base, ext = {}, {}
    for m in MODELS:
        b = {}
        for e in ("01_main_grid", "04_ablation_no_citation", "06_platform_mitigations"):
            b.update(rows(EXP / e / "results" / m))
        base[m] = b
        ext[m] = {}
        for e in ("09_adaptive_attacker", "10_two_hop", "13_explicit_ticket"):
            ext[m].update(rows(EXP / e / "results" / m))
        ext[m]["_tpl"] = rows(EXP / "11_more_templates" / "results" / m)
        for t in ("0.0", "1.0"):
            ext[m][f"_t{t}"] = rows(EXP / "12_temperature" / "results" / f"{m}-t{t}")

    # ---------- pooled comparisons (pooled over the models that have both cells complete)
    def pooled(cond_a, cond_b, src_a="base", field="any_residue", n=48, key=None):
        """Pooled rates and a stratified exact McNemar (discordant pairs summed over models; seeds paired within model)."""
        ka = kb = na = x = y = 0
        used = []
        for m in MODELS:
            gb = ext[m] if key is None else ext[m][key]
            ga = base[m] if src_a == "base" else gb
            ra, rb = complete(ga, cond_a, n), complete(gb, cond_b, n)
            if ra is None or rb is None:
                continue
            nn, xa, ya, _ = mcnemar(ra, rb, field)
            ka += sum(bool(r[field]) for r in ra)
            kb += sum(bool(r[field]) for r in rb)
            na += nn
            x += xa
            y += ya
            used.append(MODELS[m][0])
        from revres.analyze import mcnemar_exact
        if not used:
            return None
        return dict(ka=ka, kb=kb, n=na, p=mcnemar_exact(x, y), models=used)

    def put(name, res):
        if res is None:
            return
        M[f"x/{name}/a"] = fmt_rate(res["ka"], res["n"])
        M[f"x/{name}/b"] = fmt_rate(res["kb"], res["n"])
        M[f"x/{name}/apct"] = f"{pct(res['ka'], res['n'])}\\%"
        M[f"x/{name}/bpct"] = f"{pct(res['kb'], res['n'])}\\%"
        M[f"x/{name}/p"] = fmt_p(res["p"])
        M[f"x/{name}/models"] = ", ".join(res["models"])

    # The main-text table: (limitation, test, comparator label, result label, pooled result)
    # (limitation, new condition label, (comparator, new condition, comparator source), metric)
    TABLE = [
        ("Non-adaptive attacker", "launder + lineage marks", ("revoke_lineage", "launder_lineage", "base"), "any_residue"),
        ("", "launder + taint quarantine", ("taint_quarantine_norm", "launder_taint", "base"), "any_residue"),
        ("", "obfuscate + lineage marks", ("revoke_lineage", "obf_lineage", "base"), "any_residue"),
        ("", "obfuscate + taint quarantine", ("taint_quarantine_norm", "obf_taint", "base"), "any_residue"),
        ("", "scope quarantine", ("taint_quarantine_norm", "scope_quarantine", "base"), "any_residue"),
        ("", "obfuscate + scope quarantine", ("taint_quarantine_norm", "obf_scope", "base"), "any_residue"),
        ("", "action gate", ("revoke_notice", "gate", "base"), "any_residue"),
        ("", "obfuscate + action gate", ("obf_lineage", "obf_gate", "ext"), "any_residue"),
        ("False-alarm cost", "scope quarantine", ("clean", "benign_scope_quarantine", "base"), "task_success"),
        ("", "action gate", ("clean", "benign_gate", "base"), "task_success"),
        ("One writer hop", "two hops, not revoked", ("compromised", "hop2_compromised", "base"), "any_residue"),
        ("", "two hops + notice", ("revoke_notice", "hop2_notice", "base"), "any_residue"),
        ("", "two hops + lineage marks", ("revoke_lineage", "hop2_lineage", "base"), "any_residue"),
        ("", "two hops + taint quarantine", ("taint_quarantine_norm", "hop2_taint", "base"), "any_residue"),
        ("", "two hops + scope quarantine", ("taint_quarantine_norm", "hop2_scope", "base"), "any_residue"),
        ("", "two hops + action gate", ("hop2_notice", "hop2_gate", "ext"), "any_residue"),
        ("Field left unwritten", "explicit ticket, clean", ("clean", "explicit_clean", "base"), "task_success"),
        ("", "explicit ticket + lineage marks", ("revoke_lineage", "explicit_lineage", "base"), "any_residue"),
    ]
    CMP = {"revoke_lineage": "lineage marks", "taint_quarantine_norm": "taint quar.", "revoke_notice": "notice",
           "obf_lineage": "obf. + marks", "clean": "clean", "compromised": "not revoked", "hop2_notice": "2 hops + notice"}
    slug = lambda s: s.replace("_", "")
    for _, _, (ca, cb, src), field in TABLE:
        put(f"{slug(cb)}", pooled(ca, cb, src, field=field))
    # behaviour under the action gate: attempts the gate blocked, escalations, re-delegations, completion (pooled)
    for c in ("gate", "obf_gate", "hop2_gate", "benign_gate", "scope_quarantine", "obf_scope", "obf_taint"):
        rs = [r for m in MODELS for r in (complete(ext[m], c, 48) or [])]
        if not rs:
            continue
        for fld in ("attempted_residue", "escalated", "redelegated", "task_success", "any_residue"):
            k = sum(bool(r.get(fld)) for r in rs)
            M[f"x/beh/{slug(c)}/{fld.replace('_', '')}"] = f"{pct(k, len(rs))}\\%"
        M[f"x/beh/{slug(c)}/n"] = len(rs)
        M[f"x/beh/{slug(c)}/models"] = ", ".join(MODELS[m][0] for m in MODELS if complete(ext[m], c, 48))
    for m in MODELS:
        for c in ("gate", "benign_gate"):
            rs = complete(ext[m], c, 48)
            if rs:
                for fld in ("task_success", "escalated", "redelegated", "attempted_residue"):
                    M[f"x/beh/{MODELS[m][1]}/{slug(c)}/{fld.replace('_', '')}"] = f"{pct(sum(bool(r.get(fld)) for r in rs), 48)}\\%"
        rs = complete(base[m], "clean", 48)
        if rs:
            M[f"x/beh/{MODELS[m][1]}/clean/tasksuccess"] = f"{pct(sum(r['task_success'] for r in rs), 48)}\\%"
    # attack success without revocation, against the main payload
    put("laundercompromised", pooled("compromised", "launder_compromised", field="any_residue"))
    put("obfcompromised", pooled("compromised", "obf_compromised", field="any_residue"))

    # ---------- 11: new templates (seeds 100-147): rates per condition and the key contrasts, 24 clusters with 01
    tpl_rows, tpl_cl = [], []
    for c_a, c_b in (("compromised", "revoke_silent"), ("revoke_silent", "revoke_notice"), ("revoke_notice", "revoke_lineage"),
                     ("revoke_lineage", "taint_quarantine_norm")):
        ka = kb = n = x = y = 0
        da, db = [], []
        used = []
        for m in MODELS:
            g = ext[m]["_tpl"]
            ra, rb = complete(g, c_a, 48), complete(g, c_b, 48)
            if ra is None or rb is None:
                continue
            nn, xa, ya, _ = mcnemar(ra, rb, "any_residue")
            ka += sum(r["any_residue"] for r in ra); kb += sum(r["any_residue"] for r in rb); n += nn; x += xa; y += ya
            used.append(MODELS[m][0])
            # 24 clusters per model: the original 12 (seeds 0-47) and the new 12 (seeds 100-147); seeds are offset per
            # model so that rows of different models never share a key, and clusters are template x payload x model
            oa, ob = complete(base[m], c_a, 48), complete(base[m], c_b, 48)
            if oa and ob:
                off = 1000 * list(MODELS).index(m)
                tag = lambda rr: [dict(r, seed=r["seed"] + off, scenario=r["scenario"] + "/" + m) for r in rr]
                da += tag(oa + ra)
                db += tag(ob + rb)
        if not used:
            continue
        from revres.analyze import mcnemar_exact
        key = f"x/tpl/{slug(c_a)}-{slug(c_b)}"
        M[key + "/a"], M[key + "/b"], M[key + "/p"] = fmt_rate(ka, n), fmt_rate(kb, n), fmt_p(mcnemar_exact(x, y))
        M[key + "/apct"], M[key + "/bpct"] = f"{pct(ka, n)}\\%", f"{pct(kb, n)}\\%"
        tpl_rows.append((c_a, c_b, ka, kb, n, mcnemar_exact(x, y)))
        if da:
            # cluster check over template x payload x model clusters, old and new templates together
            cc = cluster_check(da, db, "any_residue")
            M[key + "/clusters"] = cc["n"]
            M[key + "/signp"] = fmt_p(cc["p"])
            M[key + "/ci"] = f"[{round(100 * cc['lo'])}, {round(100 * cc['hi'])}] pp"
            tpl_cl.append((c_a, c_b, cc))
    if tpl_rows:
        M["x/tpl/models"] = ", ".join(MODELS[m][0] for m in MODELS if complete(ext[m]["_tpl"], "revoke_silent", 48))

    # ---------- 12: temperature
    for m in MODELS:
        for t in ("0.0", "1.0"):
            g = ext[m][f"_t{t}"]
            for c in ("compromised", "revoke_silent", "revoke_lineage", "taint_quarantine_norm"):
                rs = complete(g, c, 48)
                if rs:
                    k, n = rate(rs)
                    M[f"x/temp/{MODELS[m][1]}/{t}/{slug(c)}"] = f"{pct(k, n)}\\%"
    temp_models = [m for m in MODELS if complete(ext[m]["_t0.0"], "revoke_silent", 48) and complete(ext[m]["_t1.0"], "revoke_silent", 48)]
    if temp_models:
        M["x/temp/models"] = " and ".join(MODELS[m][0] for m in temp_models)
        for c in ("compromised", "revoke_silent", "revoke_lineage", "taint_quarantine_norm"):
            for t, src in (("0.0", "_t0.0"), ("0.7", None), ("1.0", "_t1.0")):
                k = n = 0
                for m in temp_models:
                    rs = complete(base[m] if src is None else ext[m][src], c, 48)
                    if rs:
                        k += sum(r["any_residue"] for r in rs); n += len(rs)
                if n:
                    M[f"x/temp/{t}/{slug(c)}"] = f"{pct(k, n)}\\%"

    # ---------- re-grading of every logged trial (01-07 and the new experiments)
    tot = defaultdict(int)
    for f in glob.glob(str(EXP / "0[1-7]*" / "results" / "*" / "trials.jsonl")):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            g = grade_norm(make_scenario(r["seed"]), r["actions"])
            tot["n"] += 1
            tot["exact"] += r["any_residue"]
            tot["norm"] += g["any_residue_norm"]
            tot["broad"] += g["any_residue_broad"]
            tot["fp"] += g["any_residue_broad"] and (r["condition"] == "clean" or "benign" in r["condition"])
            tot["wrote"] += g["field_written"]
            tot["succ_wrote"] += r["task_success"] and g["field_written"]
    for k, v in tot.items():
        M[f"x/regrade/{k}"] = f"{v:,}"
    if tot["n"]:
        M["x/regrade/normadd"] = tot["norm"] - tot["exact"]
        M["x/regrade/broadadd"] = tot["broad"] - tot["exact"]
        M["x/regrade/broadaddpct"] = f"{100 * (tot['broad'] - tot['exact']) / tot['exact']:.1f}\\%"
    # largest executor prompt (characters), against the 8k-token context
    mx = 0
    for f in glob.glob(str(EXP / "0[1-7]*" / "results" / "*" / "transcripts" / "*.json")):
        t = json.load(open(f, encoding="utf-8"))["transcript"]
        mx = max(mx, sum(len(x["content"]) for x in t[:-1]))
    M["x/maxprompt/chars"] = f"{mx:,}"
    M["x/maxprompt/ktok"] = f"{mx / 3.5 / 1000:.1f}"

    # ---------- 08: training fix (from its own analysis)
    sp = EXP / "08_training_fix" / "results" / "summary.json"
    if sp.exists():
        S = json.loads(sp.read_text(encoding="utf-8"))
        for key, v in S.items():
            split, cond = key.split("|")
            tag = {"held-out (32-47)": "held", "fresh (48-95)": "fresh", "all (32-95)": "all"}[split]
            n = v["n"]
            for fld in ("any_residue", "task_success", "fact_residue", "instr_residue"):
                d = v.get(fld)
                if not isinstance(d, dict):
                    continue
                k = f"x/sft/{tag}/{slug(cond)}/{fld.split('_')[0]}"
                M[k + "/base"] = f"{pct(d['base'], n)}\\%"
                M[k + "/tuned"] = f"{pct(d['tuned'], n)}\\%"
                M[k + "/p"] = fmt_p(d["p"])
            M[f"x/sft/{tag}/n"] = n

    # ---------- 08 stress tests: base vs tuned executor on the new templates (100-147) and the adaptive attacker / two hops
    #            (48-95); paired by seed on the base model's handoffs
    from revres.analyze import mcnemar_exact
    R08 = EXP / "08_training_fix" / "results"
    b08 = rows(R08 / "llamacpp-qwen3.5-4b")
    t08 = rows(R08 / "llamacpp-qwen3.5-4b__writes-for__llamacpp-qwen3.5-4b+sft")
    sft_rows = []
    for tag, seeds, conds in (("tpl", range(100, 148), ["clean", "compromised", "revoke_silent", "revoke_notice",
                                                         "revoke_lineage", "benign_lineage"]),
                              ("adv", range(48, 96), ["launder_compromised", "launder_lineage", "obf_compromised",
                                                      "obf_lineage", "hop2_compromised", "hop2_notice", "hop2_lineage"])):
        for c in conds:
            a = {r["seed"]: r for r in b08.get(c, []) if r["seed"] in seeds}
            t = {r["seed"]: r for r in t08.get(c, []) if r["seed"] in seeds}
            common = sorted(a.keys() & t.keys())
            if len(common) < len(seeds):
                continue
            for fld, short_ in (("any_residue", "any"), ("task_success", "task")):
                ka = sum(bool(a[s][fld]) for s in common)
                kt = sum(bool(t[s][fld]) for s in common)
                x = sum(bool(a[s][fld]) and not t[s][fld] for s in common)
                y = sum(bool(t[s][fld]) and not a[s][fld] for s in common)
                k = f"x/sft/{tag}/{slug(c)}/{short_}"
                M[k + "/base"], M[k + "/tuned"] = f"{pct(ka, len(common))}\\%", f"{pct(kt, len(common))}\\%"
                M[k + "/p"] = fmt_p(mcnemar_exact(x, y))
                if short_ == "any":
                    sft_rows.append((tag, c, ka, kt, len(common), mcnemar_exact(x, y)))
    if sft_rows:
        L = ["\\begin{tabular}{@{}llrrr@{}}", "\\toprule", "Seeds & Condition & Base & Tuned & $p$ \\\\", "\\midrule"]
        for tag, c, ka, kt, n, p in sft_rows:
            L.append(f"{'new templates (100--147)' if tag == 'tpl' else 'fresh (48--95)'} & \\texttt{{{c.replace('_', chr(92) + '_')}}} & "
                     f"{pct(ka, n)}\\% & {pct(kt, n)}\\% & {fmt_p(p)} \\\\")
        L += ["\\bottomrule", "\\end{tabular}"]
        (HERE / "tab_sft_stress.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
        M["x/sft/stress/have"] = 1

    # ---------- tuned 4B vs GPT-6 Luna on Luna's own handoffs (seeds 32-47, never used in training); paired by seed
    vl = rows(R08 / "vs_luna")
    lu = rows(EXP / "01_main_grid" / "results" / "gpt-6-luna")
    VL_CONDS = ["clean", "compromised", "revoke_silent", "revoke_notice", "revoke_lineage", "benign_lineage"]
    vl_rows = []
    for c in VL_CONDS:
        a = {r["seed"]: r for r in lu.get(c, []) if 32 <= r["seed"] < 48}
        t = {r["seed"]: r for r in vl.get(c, []) if 32 <= r["seed"] < 48}
        com = sorted(a.keys() & t.keys())
        if len(com) < 16:
            continue
        cells = {}
        for fld, short_ in (("any_residue", "any"), ("task_success", "task")):
            ka = sum(bool(a[s][fld]) for s in com); kt = sum(bool(t[s][fld]) for s in com)
            x = sum(bool(a[s][fld]) and not t[s][fld] for s in com); y = sum(bool(t[s][fld]) and not a[s][fld] for s in com)
            p_ = mcnemar_exact(x, y)
            k = f"x/vsluna/{slug(c)}/{short_}"
            M[k + "/luna"], M[k + "/tuned"], M[k + "/p"] = f"{pct(ka, len(com))}\\%", f"{pct(kt, len(com))}\\%", fmt_p(p_)
            cells[short_] = (ka, kt, len(com), p_)
        vl_rows.append((c, cells))
    if len(vl_rows) == len(VL_CONDS):
        # pooled over the three revoked conditions (credential-only, notice, lineage marks)
        for fld, short_ in (("any_residue", "any"), ("task_success", "task")):
            ka = kt = n = x = y = 0
            for c in ("revoke_silent", "revoke_notice", "revoke_lineage"):
                a = {r["seed"]: r for r in lu[c] if 32 <= r["seed"] < 48}
                t = {r["seed"]: r for r in vl[c] if 32 <= r["seed"] < 48}
                for s in a.keys() & t.keys():
                    ka += bool(a[s][fld]); kt += bool(t[s][fld]); n += 1
                    x += bool(a[s][fld]) and not t[s][fld]; y += bool(t[s][fld]) and not a[s][fld]
            M[f"x/vsluna/revoked/{short_}/luna"] = f"{pct(ka, n)}\\%"
            M[f"x/vsluna/revoked/{short_}/tuned"] = f"{pct(kt, n)}\\%"
            M[f"x/vsluna/revoked/{short_}/p"] = fmt_p(mcnemar_exact(x, y))
            M[f"x/vsluna/revoked/{short_}/n"] = n
        L = ["\\begin{tabular}{@{}lrrrrrr@{}}", "\\toprule",
             "& \\multicolumn{3}{c}{Any residue} & \\multicolumn{3}{c}{Task success} \\\\",
             "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}",
             "Condition & GPT-6 Luna & tuned 4B & $p$ & GPT-6 Luna & tuned 4B & $p$ \\\\", "\\midrule"]
        for c, cl in vl_rows:
            (ra, rt, n, rp), (ta, tt, _, tp) = cl["any"], cl["task"]
            L.append(f"\\texttt{{{c.replace('_', chr(92) + '_')}}} & {pct(ra, n)}\\% & {pct(rt, n)}\\% & {fmt_p(rp)} & "
                     f"{pct(ta, n)}\\% & {pct(tt, n)}\\% & {fmt_p(tp)} \\\\")
        L += ["\\bottomrule", "\\end{tabular}"]
        (HERE / "tab_vs_luna.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
        M["x/vsluna/have"] = 1

    # ---------- tables
    # rows: (group, new condition, cells); the main-text table keeps the rows in MAIN_ROWS, the appendix keeps all
    MAIN_ROWS = {"launder_lineage", "launder_taint", "obf_taint", "scope_quarantine", "gate", "obf_gate", "benign_gate",
                 "hop2_lineage", "hop2_taint", "hop2_gate", "explicit_clean", "tpl:revoke_silent", "tpl:taint_quarantine_norm"}
    rows_all, grp = [], ""
    for lim, test, (ca, cb, _), field in TABLE:
        grp = lim or grp
        k = f"x/{slug(cb)}"
        if f"{k}/a" not in M:
            cells = f"& {CMP.get(ca, ca)} & \\multicolumn{{3}}{{c}}{{(running)}}"
        else:
            metric = "success" if field == "task_success" else "residue"
            cells = f"{metric} & {CMP.get(ca, ca)} & {M[k + '/apct']} & {M[k + '/bpct']} & {M[k + '/p']}"
        rows_all.append((grp, cb, f"{test} & {cells}"))
    nm = {"compromised": "not revoked", "revoke_silent": "credentials only", "revoke_notice": "+ notice",
          "revoke_lineage": "+ lineage marks", "taint_quarantine_norm": "taint quarantine"}
    for c_a, c_b, ka, kb, n, p in tpl_rows:
        rows_all.append(("Six new templates", f"tpl:{c_b}",
                         f"{nm[c_b]} & residue & {nm[c_a]} & {pct(ka, n)}\\% & {pct(kb, n)}\\% & {fmt_p(p)}"))

    def table(rows):
        out, last = [], None
        for g, _, body in rows:
            if last is not None and g != last:
                out.append("\\addlinespace[2pt]")
            out.append(f"{g if g != last else ''} & {body} \\\\")
            last = g
        head = ("\\begin{tabular}{@{}llllrrr@{}}\n\\toprule\nLimitation & New condition & Metric & Compared with & Comp. & New & "
                "$p$ \\\\\n\\midrule\n")
        return head + "\n".join(out) + "\n\\bottomrule\n\\end{tabular}\n"

    T = [r for r in rows_all if r[1] in MAIN_ROWS]
    (HERE / "tab_ext.tex").write_text(table(T), encoding="utf-8")
    (HERE / "tab_ext_full.tex").write_text(table(rows_all), encoding="utf-8")

    A = []
    conds = ["launder_compromised", "obf_compromised"] + [c for _, _, (_, c, _), _ in TABLE]
    for c in dict.fromkeys(conds):
        cells = []
        for m in MODELS:
            rs = complete(ext[m], c, 48)
            if rs:
                k, n = rate(rs)
                s, _ = rate(rs, "task_success")
                cells.append(f"{pct(k, n)} / {pct(s, n)}")
            else:
                cells.append("--")
        A.append(f"\\texttt{{{c.replace('_', chr(92) + '_')}}} & " + " & ".join(cells) + " \\\\")
    FULL = {"gpt-6-luna": "GPT-6 Luna", "gemma-4-31b": "Gemma 4 31B", "qwen3.8-27b": "Qwen3.8 27B",
            "ministral-3-14b": "Ministral 3 14B"}
    head = ("\\begin{tabular}{@{}l" + "r" * len(MODELS) + "@{}}\n\\toprule\nCondition & "
            + " & ".join(FULL[m] for m in MODELS) + " \\\\\n\\midrule\n")
    (HERE / "tab_ext_app.tex").write_text(head + "\n".join(A) + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")
    M.write(HERE / "numbers_ext.tex")
    print(f"wrote numbers_ext.tex ({len(M)} macros), tab_ext.tex ({len(T)} rows), tab_ext_app.tex")


if __name__ == "__main__":
    main()
