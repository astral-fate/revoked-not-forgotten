#!/usr/bin/env python3
"""
Build the "Revoked but Not Forgotten" deck: an editable .pptx, a rendered .pdf,
per-slide PNG renders (_render/) and a self-contained HTML slide version.

Every number is computed at build time from the trial records (trials.jsonl) with
the analysis functions in src/revres/analyze.py (load, wilson, paired,
mcnemar_exact); nothing is typed by hand. Verbatim texts (prompts, the platform
notice, the retraction stub, the lineage mark, the attack payloads) are taken from
src/revres/env.py and src/revres/scenarios.py; transcript excerpts are read from
results/<run>/transcripts/. Incident figures and the judge's question are read
from paper/draft.md.

Models are discovered automatically: every experiments/*/results/<model> run
whose model has all 7 main conditions x 48 seeds is included (GPT-6 Luna is
included with its 302 completed trials, as documented in the paper). A new model
run therefore flows into every slide on the next `python build_deck.py`.

Outputs (next to this script):
  _qr/*.png                          QR codes (decode-verified)
  fig/fig_residue.png                figure regenerated from the included models
  revoked_not_forgotten_deck.pptx    editable deck
  revoked_not_forgotten_deck.pdf     rendered deck
  _render/slide_NN.png               per-slide renders for visual QA
  slides.html                        HTML slide version (also copied to the repo root)
"""
from __future__ import annotations
import base64, html, json, math, pathlib, re, shutil, sys
from collections import Counter, defaultdict
from pptx.util import Inches
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from deck_helpers import *
import deck_helpers as DH

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
RES = REPO / "experiments"   # experiments/<NN_name>/results/<model>/
QRDIR = HERE / "_qr"
FIGDIR = HERE / "fig"
sys.path.insert(0, str(REPO / "src"))
from revres.analyze import load, wilson, paired, mcnemar_exact, ORDER, rate_table, figures  # noqa: E402
from revres import env as ENV  # noqa: E402
from revres.scenarios import make_scenario, TEMPLATES, TEMPLATES_B  # noqa: E402

BRAND = "Revoked but Not Forgotten  ·  Apart Research Swarm Alignment Hackathon 2026"
M_ = "−"

# ---- extra tints -----------------------------------------------------------
RED_T   = RGBColor(0xFD, 0xEC, 0xEC)
GREEN_T = RGBColor(0xE6, 0xF6, 0xEC)
AMBER_T = RGBColor(0xFE, 0xF4, 0xDC)
AMBER_D = RGBColor(0xB4, 0x53, 0x09)
TEAL_T  = RGBColor(0xE6, 0xF7, 0xF5)
ROWALT  = RGBColor(0xEC, 0xF2, 0xF5)
REDDK   = RGBColor(0x3A, 0x22, 0x22)
GREENDK = RGBColor(0x1C, 0x3A, 0x2E)
LINEDK  = RGBColor(0x2E, 0x40, 0x53)
GHOST   = RGBColor(0xBF, 0xD6, 0xDC)
BARBG   = RGBColor(0xE3, 0xEA, 0xEF)
CODEBG  = RGBColor(0x14, 0x20, 0x2E)
POS = POS_ON_DARK; NEG = NEG_ON_DARK
AMB_ON_DARK = RGBColor(0xFC, 0xD3, 0x4D)

# ===========================================================================
# DATA — every number below is computed from trials.jsonl
# ===========================================================================
DISPLAY = {"openai/gpt-6-luna": "GPT-6 Luna", "modal:gemma-4-31b-it": "Gemma 4 31B",
           "modal:ministral-3-14b": "Ministral-3 14B", "modal:qwen3.8-27b": "Qwen3.8 27B",
           # display names as in paper/make_numbers.py NICE
           "adaption:glm-5.2": "GLM-5.2", "adaption:deepseek-v4-flash": "DeepSeek-V4 Flash",
           "adaption:qwen3.5-397b": "Qwen3.5 397B"}
SERVED = {"openai/gpt-6-luna": ("openai/gpt-6-luna", "OpenRouter API"),
          "modal:gemma-4-31b-it": ("google/gemma-4-31B-it", "vLLM 0.33.0 · 1× H100 on Modal"),
          "modal:ministral-3-14b": ("mistralai/Ministral-3-14B-Instruct-2512", "vLLM 0.33.0 · 1× H100 on Modal"),
          "modal:qwen3.8-27b": ("Qwen/Qwen3.8-27B", "vLLM 0.33.0 · 1× H100 on Modal · thinking off"),
          "modal:gpt-oss-120b": ("gpt-oss-120b", "vLLM 0.33.0 · 1× H100 on Modal · reasoning low"),
          "adaption:glm-5.2": ("glm-5.2", "Adaption API"),
          "adaption:deepseek-v4-flash": ("deepseek-v4-flash", "Adaption API"),
          "adaption:qwen3.5-397b": ("qwen3.5-397b", "Adaption API")}
PREF = ["openai/gpt-6-luna", "modal:gemma-4-31b-it", "modal:qwen3.8-27b", "modal:ministral-3-14b", "modal:gpt-oss-120b",
        "adaption:glm-5.2", "adaption:deepseek-v4-flash", "adaption:qwen3.5-397b"]
PARTIAL_OK = set()   # every included model must have all 7 main conditions x 48 seeds (runs in progress are skipped)
SEEDS = 48

# the base study: experiments 01-07 (experiments/<NN_name>/results/<model>/trials.jsonl). Experiments 08-13 reuse
# (model, condition, seed) keys of the base study (12 re-runs seeds 0-47 at other temperatures, 11 adds seeds 100-147),
# so they are loaded separately below (STRESS-TEST section) and never merged into ROWS.
run_dirs = sorted(p for p in RES.glob("0[1-7]_*/results/*") if (p / "trials.jsonl").exists())
_keys = defaultdict(int)
for d in run_dirs:
    for l in (d / "trials.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(l); _keys[(r["model"], r["condition"], r["seed"])] += 1
        except json.JSONDecodeError: pass
assert all(v == 1 for v in _keys.values()), "a (model, condition, seed) trial appears in more than one experiment folder"
def _load_tolerant(d):
    """analyze.load(); if a run is still being written (a partial last line), skip unparsable lines."""
    try:
        return load(d)
    except json.JSONDecodeError:
        rows, bad = [], 0
        for l in (d / "trials.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                try: rows.append(json.loads(l))
                except json.JSONDecodeError: bad += 1
        print(f"warning: {d.name}: skipped {bad} unparsable line(s) (run in progress?)")
        return list({(r["model"], r["condition"], r["seed"]): r for r in rows}.values())

_seen = {}
for d in run_dirs:
    if (d / "trials.jsonl").exists():
        for r in _load_tolerant(d):
            _seen[(r["model"], r["condition"], r["seed"])] = r
ALLROWS = list(_seen.values())
_cnt = Counter((r["model"], r["condition"]) for r in ALLROWS)
_models = {r["model"] for r in ALLROWS}

def _complete(m):
    if m in PARTIAL_OK:
        return all(_cnt[(m, c)] > 0 for c in ORDER)
    return all(_cnt[(m, c)] >= SEEDS for c in ORDER)

MODELS = sorted([m for m in _models if "=>" not in m and _complete(m)], key=lambda m: (PREF.index(m) if m in PREF else 99, m))
SKIPPED = sorted(m for m in _models if m not in MODELS)
assert "openai/gpt-6-luna" in MODELS and "modal:gemma-4-31b-it" in MODELS, MODELS
def cell_ok(m, c):
    """a (model, condition) cell is used only when every seed is in (runs still in progress are skipped)."""
    return _cnt[(m, c)] >= SEEDS
ROWS = [r for r in ALLROWS if r["model"] in MODELS and cell_ok(r["model"], r["condition"])]
N_PARTIAL_SKIPPED = sum(1 for r in ALLROWS if "=>" not in r["model"]
                        and not (r["model"] in MODELS and cell_ok(r["model"], r["condition"])))
MAIN = [r for r in ROWS if r["condition"] in ORDER]
def nm(m): return DISPLAY.get(m, m.split(":")[-1].split("/")[-1])
def andj(xs):
    xs = list(xs)
    return ", ".join(xs[:-1]) + " and " + xs[-1] if len(xs) > 1 else (xs[0] if xs else "–")
NAMES = [nm(m) for m in MODELS]
LUNA, GEMMA, MINI = "openai/gpt-6-luna", "modal:gemma-4-31b-it", "modal:ministral-3-14b"
QWEN, OSS = "modal:qwen3.8-27b", "modal:gpt-oss-120b"

ALL  = lambda r: True
FACT = lambda r: r.get("payload") == "fact"
EXF  = lambda r: r.get("payload") == "exfil"
WROTE = lambda r: not r["field_untouched"]

def R(m, c, metric, f=ALL):
    """rate for model m (None = pooled over MODELS) in condition c -> dict(k, n, p, lo, hi)."""
    sel = [r for r in ROWS if r["condition"] == c and (m is None or r["model"] == m) and f(r)]
    k = sum(bool(r[metric]) for r in sel)
    p, lo, hi = wilson(k, len(sel))
    return dict(k=k, n=len(sel), p=p, lo=lo, hi=hi)

def PR(m, a, b, metric, f=ALL):
    """exact McNemar on (model, seed) pairs; m None = pooled. -> dict(n, a_only, b_only, p)."""
    rows = [r for r in ROWS if (m is None or r["model"] == m)]
    n, x, y, p = paired(rows, a, b, metric, f)
    assert p == mcnemar_exact(x, y)
    return dict(n=n, a=x, b=y, p=p)

def pc(t): return f"{round(100 * t['p'])}%" if t["n"] else "–"
def kn(t): return f"{t['k']}/{t['n']}"
def knp(t): return f"{t['k']}/{t['n']} ({pc(t)})"
_SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
def fp(p):
    if p >= 0.995: return "p = 1.0"
    if p >= 0.01: return f"p = {p:.2f}"
    if p >= 0.001: return f"p = {p:.3f}"
    e = math.floor(math.log10(p)); mant = p / 10 ** e
    if round(mant, 1) >= 10: mant /= 10; e += 1
    ms = f"{mant:.1f}".rstrip("0").rstrip(".")
    return f"p = {ms}×10{str(e).translate(_SUP)}"
def disc(t): return f"{t['a']} vs {t['b']} discordant pairs, exact McNemar {fp(t['p'])}"

N_MAIN = len(MAIN)
N_ABL = sum(1 for r in ROWS if r["condition"] not in ORDER)
MIXROWS = [r for r in ALLROWS if "=>" in r["model"]]
N_TRIALS = len(ROWS) + len(MIXROWS)
N_EXPS = len({d.parent.parent.name for d in run_dirs})
ABL_CONDS = sorted({r["condition"] for r in ROWS if r["condition"] not in ORDER})
ABL_ALL = ["early_revoke", "strict_notice", "nocite_compromised", "nocite_lineage", "nosource_lineage", "nosource_benign"]
ABL_MODELS = [m for m in MODELS if all(cell_ok(m, c) for c in ABL_ALL)]
per_model_n = {m: sum(1 for r in MAIN if r["model"] == m) for m in MODELS}

# headline: credential-only revocation vs none, per model + pooled
HL = {m: dict(comp=R(m, "compromised", "any_residue"), silent=R(m, "revoke_silent", "any_residue"),
                pr=PR(m, "compromised", "revoke_silent", "any_residue"),
                wrote=R(m, "revoke_silent", "fact_residue", WROTE),
                board=sum(1 for r in ROWS if r["model"] == m and r["condition"] == "revoke_silent" and r["read_board"]),
                board_res=sum(1 for r in ROWS if r["model"] == m and r["condition"] == "revoke_silent"
                              and r["read_board"] and r["any_residue"]),
                n_silent=R(m, "revoke_silent", "any_residue")["n"])
        for m in MODELS}
POOL_COMP, POOL_SILENT = R(None, "compromised", "any_residue"), R(None, "revoke_silent", "any_residue")
POOL_PR = PR(None, "compromised", "revoke_silent", "any_residue")

# mitigation effect per model
MIT = {}
for m in MODELS:
    MIT[m] = dict(notice=R(m, "revoke_notice", "any_residue"), retract=R(m, "revoke_retract", "any_residue"),
                  lineage=R(m, "revoke_lineage", "any_residue"),
                  pr_notice=PR(m, "revoke_silent", "revoke_notice", "any_residue"),
                  pr_retract=PR(m, "revoke_notice", "revoke_retract", "any_residue"),
                  pr_lineage=PR(m, "revoke_retract", "revoke_lineage", "any_residue"),
                  pr_sil_lin=PR(m, "revoke_silent", "revoke_lineage", "any_residue"),
                  exp_notice=R(m, "revoke_notice", "instr_residue", EXF),
                  exp_lineage=R(m, "revoke_lineage", "instr_residue", EXF),
                  red_silent=R(m, "revoke_silent", "redelegated"), red_notice=R(m, "revoke_notice", "redelegated"),
                  red_retract=R(m, "revoke_retract", "redelegated"), red_lineage=R(m, "revoke_lineage", "redelegated"),
                  ts_silent=R(m, "revoke_silent", "task_success"), ts_notice=R(m, "revoke_notice", "task_success"),
                  ts_lineage=R(m, "revoke_lineage", "task_success"),
                  esc_max=max(R(m, c, "escalated")["k"] for c in ORDER))
NOTICE_HELPED = [m for m in MODELS if MIT[m]["pr_notice"]["p"] < 0.05 and MIT[m]["pr_notice"]["a"] > MIT[m]["pr_notice"]["b"]]
NOTICE_NOT = [m for m in MODELS if m not in NOTICE_HELPED]
LINEAGE_HELPED = [m for m in MODELS if MIT[m]["pr_sil_lin"]["p"] < 0.05 and MIT[m]["pr_sil_lin"]["a"] > MIT[m]["pr_sil_lin"]["b"]]

# false alarm cost per model
FA = {m: dict(clean=R(m, "clean", "task_success"), benign=R(m, "benign_lineage", "task_success"),
              pr=PR(m, "clean", "benign_lineage", "task_success"),
              red=R(m, "benign_lineage", "redelegated")) for m in MODELS}

# ablations (models that ran them)
ABL = {}
for m in ABL_MODELS:
    ABL[m] = dict(
        retract=R(m, "revoke_retract", "any_residue"), early=R(m, "early_revoke", "any_residue"),
        pr_early=PR(m, "revoke_retract", "early_revoke", "any_residue"),
        ts_early=R(m, "early_revoke", "task_success"),
        notice=R(m, "revoke_notice", "any_residue"), strict=R(m, "strict_notice", "any_residue"),
        pr_strict=PR(m, "revoke_notice", "strict_notice", "any_residue"),
        exp_notice=R(m, "revoke_notice", "instr_residue", EXF), exp_strict=R(m, "strict_notice", "instr_residue", EXF),
        lineage=R(m, "revoke_lineage", "any_residue"),
        pr_strict_lin=PR(m, "strict_notice", "revoke_lineage", "any_residue"),
        nocite=R(m, "nocite_lineage", "any_residue"), nocite_comp=R(m, "nocite_compromised", "any_residue"),
        pr_nocite=PR(m, "revoke_lineage", "nocite_lineage", "any_residue"),
        pr_nocite_comp=PR(m, "nocite_compromised", "nocite_lineage", "any_residue"),
        cite_nocite=sum(1 for r in ROWS if r["model"] == m and r["condition"] == "nocite_lineage" and r["w_cited_x"]),
        hit_nocite=R(m, "nocite_lineage", "lineage_hit"), hit_lineage=R(m, "revoke_lineage", "lineage_hit"),
        nosrc=R(m, "nosource_lineage", "any_residue"), pr_nosrc=PR(m, "revoke_lineage", "nosource_lineage", "any_residue"),
        ts_nosrc=R(m, "nosource_lineage", "task_success"), esc_nosrc=R(m, "nosource_lineage", "escalated"),
        red_lineage=R(m, "revoke_lineage", "redelegated"),
        nosrc_benign=R(m, "nosource_benign", "task_success"),
    )
_gu = [r for r in MAIN if r["model"] == GEMMA]
GEMMA_UNTOUCHED = dict(k=sum(bool(r["field_untouched"]) for r in _gu), n=len(_gu))
GEMMA_UNTOUCHED["p"] = GEMMA_UNTOUCHED["k"] / GEMMA_UNTOUCHED["n"]
G = ABL.get(GEMMA)
assert G, "Gemma ablations missing"

# ---- consistency checks: qualitative claims on slides must hold in the data
assert all(HL[m]["silent"]["p"] >= 0.5 for m in MODELS), "credential-only residue claim"
# models whose residue dropped significantly under credential-only revocation (the headline names them)
SIG_DROP = [m for m in MODELS if HL[m]["pr"]["p"] < 0.05 and HL[m]["pr"]["a"] > HL[m]["pr"]["b"]]
assert all(HL[m]["pr"]["p"] >= 0.05 or m in SIG_DROP for m in MODELS), "no model's residue rose significantly"
assert 2 * len(SIG_DROP) < len(MODELS), "credential-only: most models show no significant change"
assert LUNA in NOTICE_HELPED and GEMMA in NOTICE_NOT
assert MIT[GEMMA]["exp_notice"]["k"] == MIT[GEMMA]["exp_notice"]["n"], "Gemma exports in every exfil trial after notice"
assert G["pr_early"]["p"] < 0.05 and G["early"]["k"] < G["retract"]["k"]
assert G["pr_strict"]["p"] < 0.05 and G["hit_nocite"]["k"] == 0 and G["pr_nocite"]["p"] < 0.05
assert G["pr_nosrc"]["p"] < 0.05 and G["nosrc"]["k"] > G["lineage"]["k"]
assert all(FA[m]["pr"]["p"] >= 0.05 for m in MODELS), "false-alarm cost claim"
# ---- v2 data: gpt-oss detail, ablations x models, platform mitigations (06), mixed teams (07), handoff audit
def _contact_x(r):
    return any(a["tool"] == "reassign_lookup" and str((a.get("args") or {}).get("worker", "")).lower() in
               ("worker-x", "x", "worker x") for a in r["actions"])
HAS_OSS = OSS in MODELS
if HAS_OSS:
    _oi = {(r["condition"], r["seed"]): r for r in ROWS if r["model"] == OSS}
    _drop = [sd for (c, sd), r in _oi.items() if c == "compromised" and r["any_residue"]
             and ("revoke_silent", sd) in _oi and not _oi[("revoke_silent", sd)]["any_residue"]]
    OSS_DROP = len(_drop)
    OSS_DROP_X = sum(_contact_x(_oi[("revoke_silent", sd)]) for sd in _drop)
    OSS_DROP_ESC = sum(bool(_oi[("revoke_silent", sd)]["escalated"]) for sd in _drop)
    OSS_ESC_COMP, OSS_ESC_SIL = R(OSS, "compromised", "escalated"), R(OSS, "revoke_silent", "escalated")
    OSS_BOARD = sum(bool(r["read_board"]) for r in ROWS if r["model"] == OSS and r["condition"] in ("compromised", "revoke_silent"))
    assert OSS in SIG_DROP and OSS_DROP == HL[OSS]["pr"]["a"]
    assert OSS_DROP_X * 2 > OSS_DROP, "gpt-oss drop came from contacting the revoked agent"
    assert OSS_BOARD == 0 and OSS_ESC_SIL["k"] > OSS_ESC_COMP["k"]
# the figure note says "the pooled drop comes mostly from <model>" only when one model carries at least half of it
POOL_DROP_FROM = None
if POOL_PR["p"] < 0.05 and SIG_DROP:
    _top = max(SIG_DROP, key=lambda m: HL[m]["pr"]["a"] - HL[m]["pr"]["b"])
    if HL[_top]["pr"]["a"] - HL[_top]["pr"]["b"] >= (POOL_PR["a"] - POOL_PR["b"]) / 2:
        POOL_DROP_FROM = _top

# ablation claims across all ablation models
STRICT_OK = [m for m in ABL_MODELS if ABL[m]["pr_strict"]["p"] < 0.05 and ABL[m]["pr_strict"]["a"] > ABL[m]["pr_strict"]["b"]]
STRICT_NO = [m for m in ABL_MODELS if m not in STRICT_OK]
NOCITE_UP = [m for m in ABL_MODELS if ABL[m]["pr_nocite"]["p"] < 0.05 and ABL[m]["pr_nocite"]["b"] > ABL[m]["pr_nocite"]["a"]]
assert all(ABL[m]["early"]["k"] == 0 for m in ABL_MODELS), "early revoke: 0% for every model"
assert all(ABL[m]["hit_nocite"]["k"] < ABL[m]["hit_lineage"]["k"] for m in ABL_MODELS)
assert all(ABL[m]["ts_nosrc"]["p"] <= 0.05 for m in ABL_MODELS), "no second source: task success collapses for every model"
if QWEN in ABL_MODELS and MINI in ABL_MODELS:
    assert GEMMA in STRICT_OK and QWEN in STRICT_OK and MINI in STRICT_NO, (STRICT_OK, STRICT_NO)

# experiment 06: platform mitigations
PLAT_MODELS = [m for m in MODELS if all(cell_ok(m, c) for c in ("revoke_quarantine", "benign_quarantine", "taint_lineage",
                                                                   "taint_quarantine", "benign_taint_quarantine",
                                                                   "nocite_lineage"))]  # the taint rows are compared with it
PLAT_ROWS = [("revoke_lineage", "citations", "mark"), ("nocite_lineage", "citations (none written)", "mark"),
             ("revoke_quarantine", "citations", "withhold"), ("taint_lineage", "platform taint", "mark"),
             ("taint_quarantine", "platform taint", "withhold")]
PLAT_FA = [("clean", "no revocation"), ("benign_quarantine", "citations · withhold"),
           ("benign_taint_quarantine", "platform taint · withhold")]
HAS_NORM = bool(PLAT_MODELS) and all(
    sum(1 for r in ROWS if r["model"] == m and r["condition"] == c) >= SEEDS
    for m in PLAT_MODELS for c in ("taint_quarantine_norm", "benign_taint_quarantine_norm"))
if HAS_NORM:
    PLAT_ROWS.append(("taint_quarantine_norm", "platform taint, normalised", "withhold"))
    PLAT_FA.append(("benign_taint_quarantine_norm", "normalised taint · withhold"))
FA_PR = {"benign_quarantine": "pr_fa_bq", "benign_taint_quarantine": "pr_fa_btq", "benign_taint_quarantine_norm": "pr_fa_btqn"}
PLAT = {}
for m in PLAT_MODELS:
    PLAT[m] = {c: dict(any=R(m, c, "any_residue"), exp=R(m, c, "instr_residue", EXF), ts=R(m, c, "task_success"),
                       hit=R(m, c, "lineage_hit"), red=R(m, c, "redelegated")) for c, _, _ in PLAT_ROWS}
    PLAT[m].update({c: dict(ts=R(m, c, "task_success")) for c, _ in PLAT_FA})
    PLAT[m]["pr_tq_nocite"] = PR(m, "nocite_lineage", "taint_quarantine", "any_residue")
    PLAT[m]["pr_tq_tl"] = PR(m, "taint_lineage", "taint_quarantine", "any_residue")
    PLAT[m]["pr_fa_btq"] = PR(m, "clean", "benign_taint_quarantine", "task_success")
    PLAT[m]["pr_fa_bq"] = PR(m, "clean", "benign_quarantine", "task_success")
    if HAS_NORM:
        PLAT[m]["pr_fa_btqn"] = PR(m, "clean", "benign_taint_quarantine_norm", "task_success")
if PLAT_MODELS:
    assert all(PLAT[m]["taint_quarantine"]["any"]["p"] <= 0.05 for m in PLAT_MODELS), "taint+quarantine ≈ 0 for all"
    assert all(PLAT[m]["pr_tq_nocite"]["p"] < 0.05 for m in PLAT_MODELS)
    # false-alarm cost of taint quarantine: reported per model (amber when significant), never claimed to be zero
    FA_SIG_BTQ = [m for m in PLAT_MODELS if PLAT[m]["pr_fa_btq"]["p"] < 0.05]
    if MINI in PLAT_MODELS:
        assert PLAT[MINI]["revoke_quarantine"]["any"]["p"] >= 0.5, "citation quarantine fails for Ministral"
        assert all(PLAT[m]["revoke_quarantine"]["any"]["p"] < PLAT[MINI]["revoke_quarantine"]["any"]["p"] for m in PLAT_MODELS if m != MINI)
    PLAT_TQ_MAXP = max(PLAT[m]["pr_tq_nocite"]["p"] for m in PLAT_MODELS)
    FA_SIG_BQ = [m for m in PLAT_MODELS if PLAT[m]["pr_fa_bq"]["p"] < 0.05]
    TQ_K = sum(PLAT[m]["taint_quarantine"]["any"]["k"] for m in PLAT_MODELS)
    TQ_N = sum(PLAT[m]["taint_quarantine"]["any"]["n"] for m in PLAT_MODELS)
if HAS_NORM:
    NORM_K = sum(PLAT[m]["taint_quarantine_norm"]["any"]["k"] for m in PLAT_MODELS)
    NORM_N = sum(PLAT[m]["taint_quarantine_norm"]["any"]["n"] for m in PLAT_MODELS)
    assert NORM_K == 0, "normalised taint + quarantine: no residue for any model"
    FA_SIG_BTQN = [m for m in PLAT_MODELS if PLAT[m]["pr_fa_btqn"]["p"] < 0.05]
    # audit of the no-citation handoffs: what exact vs normalised taint matching leaves visible after withholding
    TAINT_MISS, NORM_LEAK, NOCITE_N, TAINT_EX = [], 0, 0, None
    for d in sorted((RES / "01_main_grid" / "results").glob("*")):
        hp, tp = d / "handoffs.jsonl", d / "trials.jsonl"
        if not (hp.exists() and tp.exists()):
            continue
        mdl = json.loads(tp.read_text(encoding="utf-8").splitlines()[0])["model"]
        if mdl not in PLAT_MODELS:
            continue
        for l in hp.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            h = json.loads(l)
            if not h["compromised"] or h.get("variant") != "nocite":
                continue
            NOCITE_N += 1
            terms = ENV.x_taint_terms(make_scenario(h["seed"]), True)
            vis = lambda txt: [ln for ln in txt.splitlines() if any(ENV._norm_taint(t) in ENV._norm_taint(ln) for t in terms)]
            ex_left = vis(ENV.transform_handoff(h["handoff"], "withhold", "taint", terms)[0])
            nm_left = vis(ENV.transform_handoff(h["handoff"], "withhold", "taintnorm", terms)[0])
            NORM_LEAK += bool(nm_left)
            if ex_left:
                TAINT_MISS.append((mdl, h["seed"]))
                if TAINT_EX is None:
                    TAINT_EX = (mdl, h["seed"], terms[0], next(ln for ln in ex_left))
    assert NORM_LEAK == 0 and TAINT_MISS, "normalised matching withheld every reformatted value"
    _tq_res = [(r["model"], r["seed"]) for r in ROWS if r["condition"] == "taint_quarantine" and r["any_residue"]]
    assert set(_tq_res) <= set(TAINT_MISS), "every exact-taint residual trial was a reformatted value"
    TQ_RES = _tq_res
    TQ_RES_TXT = (f"1 residual trial, {nm(TQ_RES[0][0])} seed {TQ_RES[0][1]}" if len(TQ_RES) == 1 else
                  f"{len(TQ_RES)} residual trials, all on reformatted values" if TQ_RES else "no residual trial")
    _m = re.search(r"\d{1,3}(?:,\d{3})+", TAINT_EX[3]); assert _m and _m.group(0).replace(",", "") == TAINT_EX[2]
    TAINT_FMT = _m.group(0)

# handoff audit: after citation-based withholding, does worker-X's own content survive? (main-grid std handoffs)
LEAK = {}
for d in sorted((RES / "01_main_grid" / "results").glob("*")):
    hp, tp = d / "handoffs.jsonl", d / "trials.jsonl"
    if not (hp.exists() and tp.exists()):
        continue
    mdl = json.loads(tp.read_text(encoding="utf-8").splitlines()[0])["model"]
    if mdl not in MODELS:
        continue
    k = n_ = 0
    for l in hp.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        h = json.loads(l)
        if not h["compromised"] or h.get("variant", "std") != "std":
            continue
        terms = ENV.x_taint_terms(make_scenario(h["seed"]), True)
        if not any(t in h["handoff"].lower() for t in terms):
            continue
        shown_, _ = ENV.transform_handoff(h["handoff"], "withhold", "cite", terms)
        n_ += 1; k += any(t in shown_.lower() for t in terms)
    if n_:
        LEAK[mdl] = dict(k=k, n=n_, p=k / n_)
if MINI in LEAK:
    assert LEAK[MINI]["p"] >= 0.5 and all(LEAK[m]["p"] < LEAK[MINI]["p"] for m in LEAK if m != MINI)

# experiment 07: mixed teams (writer => executor), paired with the writer's own main-grid trial (same handoff)
TEAMS = sorted({r["model"] for r in MIXROWS})
MIX_CONDS = ["compromised", "revoke_notice", "revoke_lineage"]
def RT(team, c, metric="any_residue"):
    sel = [r for r in MIXROWS if r["model"] == team and r["condition"] == c]
    k = sum(bool(r[metric]) for r in sel); p, lo, hi = wilson(k, len(sel))
    return dict(k=k, n=len(sel), p=p, lo=lo, hi=hi)
def PRT(team, c, metric="any_residue"):
    w = next(r["writer_model"] for r in MIXROWS if r["model"] == team)
    A = {r["seed"]: bool(r[metric]) for r in ROWS if r["model"] == w and r["condition"] == c}
    B = {r["seed"]: bool(r[metric]) for r in MIXROWS if r["model"] == team and r["condition"] == c}
    com = sorted(set(A) & set(B)); x = sum(A[i] and not B[i] for i in com); y = sum(B[i] and not A[i] for i in com)
    return dict(n=len(com), a=x, b=y, p=mcnemar_exact(x, y))
MIX = {}
for t in TEAMS:
    r0 = next(r for r in MIXROWS if r["model"] == t)
    MIX[t] = dict(w=r0["writer_model"], e=r0["executor_model"], **{c: RT(t, c) for c in MIX_CONDS},
                  pr=PRT(t, "revoke_lineage"))
    MIX[t]["alone_w"] = R(MIX[t]["w"], "revoke_lineage", "any_residue")
    MIX[t]["alone_e"] = R(MIX[t]["e"], "revoke_lineage", "any_residue")
if TEAMS:
    # residue follows the executor: a team's lineage residue sits with its executor's own level, not its writer's
    for t in TEAMS:
        lo_e = MIX[t]["alone_e"]["p"] < 0.25
        assert (MIX[t]["revoke_lineage"]["p"] < 0.25) == lo_e, t
        assert (MIX[t]["alone_w"]["p"] < 0.25) != lo_e and MIX[t]["pr"]["p"] < 0.05, t


# ===========================================================================
# STRESS TESTS (experiments 08-13) — loaded with paper/make_ext.py's own loaders (rows, complete) and make_numbers'
# paired McNemar; comparator cells from 01/04/06 are paired by seed (same model, same cached handoff). A cell is used
# only when every seed is in. Every pooled value is cross-checked against a fresh in-memory run of make_ext.main().
# ===========================================================================
sys.path.insert(0, str(REPO / "paper"))
import make_ext as MX  # noqa: E402
from make_numbers import mcnemar as mx_mcnemar, pct as mx_pct, fmt_p as mx_fmt_p  # noqa: E402

EXT_MODELS = list(MX.MODELS)                       # results folder names, as in make_ext
EXT_ID = {f: next((m for m in sorted(_models) if "=>" not in m and m.split(":")[-1].split("/")[-1].startswith(f)), f)
          for f in EXT_MODELS}
X_BASE, X_EXT = {}, {}
for f in EXT_MODELS:
    b = {}
    for e in ("01_main_grid", "04_ablation_no_citation", "06_platform_mitigations"):
        b.update(MX.rows(RES / e / "results" / f))
    X_BASE[f] = b
    x = {}
    for e in ("09_adaptive_attacker", "10_two_hop", "13_explicit_ticket"):
        x.update(MX.rows(RES / e / "results" / f))
    X_EXT[f] = x
X_TPL = {f: MX.rows(RES / "11_more_templates" / "results" / f) for f in EXT_MODELS}
X_TMP = {(f, t): MX.rows(RES / "12_temperature" / "results" / f"{f}-t{t}") for f in EXT_MODELS for t in ("0.0", "1.0")}

def XP(ca, cb, src_a="base", field="any_residue", gb_of=None):
    """Pooled paired comparison over the models with both cells complete (as make_ext.pooled).
    -> dict(a=Wilson dict, b=Wilson dict, x, y, p, models) or None."""
    ka = kb = n = x = y = 0; used = []
    for f in EXT_MODELS:
        gb = X_EXT[f] if gb_of is None else gb_of[f]
        ga = X_BASE[f] if src_a == "base" else gb
        ra, rb = MX.complete(ga, ca, SEEDS), MX.complete(gb, cb, SEEDS)
        if ra is None or rb is None:
            continue
        nn, xa, ya, _ = mx_mcnemar(ra, rb, field)
        ka += sum(bool(r[field]) for r in ra); kb += sum(bool(r[field]) for r in rb); n += nn; x += xa; y += ya
        used.append(f)
    if not used:
        return None
    def wd(k):
        p, lo, hi = wilson(k, n); return dict(k=k, n=n, p=p, lo=lo, hi=hi)
    return dict(a=wd(ka), b=wd(kb), x=x, y=y, p=mcnemar_exact(x, y), models=used)

def XC(f, c, src=None):
    """one complete extension cell (list of rows) or None."""
    return MX.complete(X_EXT[f] if src is None else src[f], c, SEEDS)

def XR(c, field, src=None, models=None):
    """pooled rate of `field` over the models whose cell c is complete -> Wilson dict (+ models)."""
    rs, used = [], []
    for f in (models or EXT_MODELS):
        cell = XC(f, c, src)
        if cell:
            rs += cell; used.append(f)
    k = sum(bool(r.get(field)) for r in rs); p, lo, hi = wilson(k, len(rs))
    return dict(k=k, n=len(rs), p=p, lo=lo, hi=hi, models=used)

def xnm(fs): return ", ".join(nm(EXT_ID[f]) for f in fs)

# 09 adaptive attacker + 10 two hops: (label, comparator, new condition, comparator source)
ADV = {
    "launder_lineage":  XP("revoke_lineage", "launder_lineage"),
    "launder_taint":    XP("taint_quarantine_norm", "launder_taint"),
    "obf_lineage":      XP("revoke_lineage", "obf_lineage"),
    "obf_taint":        XP("taint_quarantine_norm", "obf_taint"),
    "scope_quarantine": XP("taint_quarantine_norm", "scope_quarantine"),
    "obf_scope":        XP("taint_quarantine_norm", "obf_scope"),
    "gate":             XP("revoke_notice", "gate"),
    "obf_gate":         XP("obf_lineage", "obf_gate", src_a="ext"),
    "launder_compromised": XP("compromised", "launder_compromised"),
    "obf_compromised":  XP("compromised", "obf_compromised"),
    "benign_gate":      XP("clean", "benign_gate", field="task_success"),
    "benign_scope_quarantine": XP("clean", "benign_scope_quarantine", field="task_success"),
    "hop2_compromised": XP("compromised", "hop2_compromised"),
    "hop2_notice":      XP("revoke_notice", "hop2_notice"),
    "hop2_lineage":     XP("revoke_lineage", "hop2_lineage"),
    "hop2_taint":       XP("taint_quarantine_norm", "hop2_taint"),
    "hop2_scope":       XP("taint_quarantine_norm", "hop2_scope"),
    "hop2_gate":        XP("hop2_notice", "hop2_gate", src_a="ext"),
    "explicit_clean":   XP("clean", "explicit_clean", field="task_success"),
    "explicit_lineage": XP("revoke_lineage", "explicit_lineage"),
}
HAS_ADV = all(ADV[c] for c in ("launder_lineage", "launder_taint", "obf_taint", "scope_quarantine", "gate", "obf_gate"))
HAS_HOP = all(ADV[c] for c in ("hop2_compromised", "hop2_notice", "hop2_lineage", "hop2_taint"))
# behaviour under the action gate (pooled over complete cells), as make_ext's x/beh macros
GATE_B = {c: {f: XR(c, f) for f in ("attempted_residue", "escalated", "redelegated", "task_success", "any_residue")}
          for c in ("gate", "obf_gate", "hop2_gate", "benign_gate")}
GATE_PM = {f: {c: {fl: XR(c, fl, models=[f]) for fl in ("attempted_residue", "escalated", "redelegated", "task_success")}
               for c in ("gate", "benign_gate")} for f in EXT_MODELS if XC(f, "gate") and XC(f, "benign_gate")}
for f in GATE_PM:
    GATE_PM[f]["clean"] = XR("clean", "task_success", src=X_BASE, models=[f])
    GATE_PM[f]["notice_ts"] = XR("revoke_notice", "task_success", src=X_BASE, models=[f])
GATE_BLOCKED = sum(int(r.get("blocked") or 0) for f in EXT_MODELS for c in GATE_B for r in (XC(f, c) or []))
# why lineage marks lose their effect after two hops: the coordinator drops the citations, so few lines get marked
HOP_HIT = XR("hop2_lineage", "lineage_hit"); ONE_HIT = XR("revoke_lineage", "lineage_hit", src=X_BASE, models=HOP_HIT["models"])
STRESS_MODELS = sorted({f for v in ADV.values() if v for f in v["models"]}, key=EXT_MODELS.index)

# 11 new templates (seeds 100-147)
TPL_PAIRS = [("compromised", "revoke_silent"), ("revoke_silent", "revoke_notice"), ("revoke_notice", "revoke_lineage"),
             ("revoke_lineage", "taint_quarantine_norm")]
TPL = {pair: XP(pair[0], pair[1], src_a="ext", gb_of=X_TPL) for pair in TPL_PAIRS}
HAS_TPL = all(TPL.values())
TPL_NEW = sorted({sc for f in EXT_MODELS for rs in X_TPL[f].values() for sc in (r["scenario"] for r in rs)})
# 12 temperature: pooled over models complete at both temperatures
TEMP_CONDS = ["compromised", "revoke_silent", "revoke_lineage", "taint_quarantine_norm"]
TEMP_MODELS = [f for f in EXT_MODELS if XC(f, "revoke_silent", {f: X_TMP[(f, "0.0")]}) and XC(f, "revoke_silent", {f: X_TMP[(f, "1.0")]})]
TEMP = {}
for c in TEMP_CONDS:
    for t in ("0.0", "0.7", "1.0"):
        src = X_BASE if t == "0.7" else {f: X_TMP[(f, t)] for f in EXT_MODELS}
        TEMP[(c, t)] = XR(c, "any_residue", src=src, models=TEMP_MODELS)
HAS_TEMP = bool(TEMP_MODELS) and all(TEMP[k]["n"] == SEEDS * len(TEMP_MODELS) for k in TEMP)

# re-grading of every logged trial of 01-07 (normalised and broad matching, revres.grade.grade_norm) + longest prompt
from revres.grade import grade_norm  # noqa: E402
REG = defaultdict(int)
for f_ in sorted(RES.glob("0[1-7]_*/results/*/trials.jsonl")):
    for l in f_.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        try: r = json.loads(l)
        except json.JSONDecodeError: continue
        g_ = grade_norm(make_scenario(r["seed"]), r["actions"])
        REG["n"] += 1; REG["exact"] += r["any_residue"]; REG["norm"] += g_["any_residue_norm"]
        REG["broad"] += g_["any_residue_broad"]
        REG["fp"] += g_["any_residue_broad"] and (r["condition"] == "clean" or "benign" in r["condition"])
MAXPROMPT = 0
for f_ in RES.glob("0[1-7]_*/results/*/transcripts/*.json"):
    t_ = json.loads(f_.read_text(encoding="utf-8"))["transcript"]
    MAXPROMPT = max(MAXPROMPT, sum(len(x["content"]) for x in t_[:-1]))
MAXPROMPT_KTOK = MAXPROMPT / 3.5 / 1000            # same chars-per-token estimate as make_ext

# 08 training fix: base vs tuned executor on the base model's cached handoffs, paired by seed
R08 = RES / "08_training_fix" / "results"
SFT_B = MX.rows(R08 / "llamacpp-qwen3.5-4b")
SFT_T = MX.rows(R08 / "llamacpp-qwen3.5-4b__writes-for__llamacpp-qwen3.5-4b+sft")
SFT_CONDS = ["clean", "compromised", "revoke_silent", "revoke_notice", "revoke_lineage", "benign_lineage"]
def sft_pair(c, seeds, field, B=SFT_B, T=SFT_T):
    a = {r["seed"]: r for r in B.get(c, []) if r["seed"] in seeds}
    t = {r["seed"]: r for r in T.get(c, []) if r["seed"] in seeds}
    com = sorted(a.keys() & t.keys())
    if len(com) < len(seeds):
        return None
    ka = sum(bool(a[s][field]) for s in com); kt = sum(bool(t[s][field]) for s in com)
    x = sum(bool(a[s][field]) and not t[s][field] for s in com); y = sum(bool(t[s][field]) and not a[s][field] for s in com)
    wa, wt = wilson(ka, len(com)), wilson(kt, len(com))
    return dict(base=dict(k=ka, n=len(com), p=wa[0], lo=wa[1], hi=wa[2]), tuned=dict(k=kt, n=len(com), p=wt[0], lo=wt[1], hi=wt[2]),
                x=x, y=y, p=mcnemar_exact(x, y))
FRESH = range(48, 96)
SFT = {c: {fl: sft_pair(c, FRESH, fl) for fl in ("any_residue", "task_success")} for c in SFT_CONDS}
HAS_SFT = all(v["any_residue"] and v["task_success"] for v in SFT.values())
if HAS_SFT:
    # the compromised-but-not-revoked failure: the tuned executor re-asks worker-X, which confirms the false value
    _cx = {r["seed"]: r for r in SFT_T["compromised"] if r["seed"] in FRESH}
    _bx = {r["seed"]: r for r in SFT_B["compromised"] if r["seed"] in FRESH}
    SFT_ASKX = dict(tuned=sum(_contact_x(r) for r in _cx.values()), base=sum(_contact_x(r) for r in _bx.values()), n=len(_cx))
# optional stress test of base vs tuned (new templates 100-147; adaptive / two-hop conditions on fresh seeds 48-95)
SFT_STRESS = []
for tag, seeds, conds in (("new templates", range(100, 148), ["compromised", "revoke_silent", "revoke_notice", "revoke_lineage"]),
                          ("adaptive / two hops", FRESH, ["launder_lineage", "obf_lineage", "hop2_notice", "hop2_lineage"])):
    for c in conds:
        pr_ = sft_pair(c, seeds, "any_residue")
        if pr_:
            SFT_STRESS.append((tag, c, pr_))
HF_URL = "https://huggingface.co/FatimahEmadEldin/revocation-aware-executor-qwen3.5-4b"

# ---- consistency checks for the stress-test slides (directions only, never exact numbers)
if HAS_ADV:
    A_ = ADV
    assert A_["launder_lineage"]["b"]["p"] > A_["launder_lineage"]["a"]["p"], "laundering weakens lineage marks"
    assert A_["launder_taint"]["b"]["p"] <= 0.05, "laundering does not defeat taint quarantine"
    assert A_["obf_taint"]["b"]["p"] >= 0.25 and A_["obf_taint"]["p"] < 0.05, "obfuscation defeats taint matching"
    assert A_["scope_quarantine"]["b"]["p"] > A_["scope_quarantine"]["a"]["p"] and A_["scope_quarantine"]["p"] < 0.05, \
        "keyword scope quarantine leaks"
    for c in ("gate", "obf_gate"):
        assert A_[c]["b"]["p"] <= 0.05 and A_[c]["p"] < 0.05, f"{c}: the action gate holds residue near zero"
    assert GATE_B["gate"]["escalated"]["p"] >= 0.5, "executors escalate a lot under the gate"
    assert GATE_B["gate"]["task_success"]["p"] < ADV["benign_gate"]["a"]["p"], "task success under the gate is below clean"
    assert GATE_B["gate"]["attempted_residue"]["p"] >= 0.5, "most gated executors tried to act on the revoked content"
if HAS_HOP:
    assert ADV["hop2_lineage"]["b"]["p"] > ADV["hop2_lineage"]["a"]["p"] and ADV["hop2_lineage"]["p"] < 0.05, \
        "lineage marks lose effect after two hops"
    assert ADV["hop2_taint"]["b"]["p"] <= 0.05, "taint quarantine unaffected by the second hop"
    assert HOP_HIT["p"] < 0.1 and ONE_HIT["p"] > 0.9, "the coordinator drops the citations the marks rely on"
    if ADV["hop2_gate"]:
        assert ADV["hop2_gate"]["b"]["p"] <= 0.05, "action gate unaffected by the second hop"
if HAS_TPL:
    assert TPL[("revoke_lineage", "taint_quarantine_norm")]["b"]["p"] <= 0.05 and TPL[("compromised", "revoke_silent")]["b"]["p"] >= 0.5
    assert TPL[("revoke_notice", "revoke_lineage")]["b"]["p"] < TPL[("revoke_notice", "revoke_lineage")]["a"]["p"]
if HAS_TEMP:
    assert all(TEMP[("revoke_silent", t)]["p"] >= 0.5 and TEMP[("taint_quarantine_norm", t)]["p"] <= 0.05 for t in ("0.0", "0.7", "1.0"))
assert REG["fp"] == 0 and REG["exact"] <= REG["norm"] <= REG["broad"], "re-grading: no false positives, monotone"
assert MAXPROMPT_KTOK < 8.192, "longest executor prompt fits the 8k context"
if HAS_SFT:
    assert SFT["revoke_lineage"]["any_residue"]["tuned"]["p"] < SFT["revoke_lineage"]["any_residue"]["base"]["p"]
    assert SFT["revoke_lineage"]["task_success"]["tuned"]["p"] > SFT["revoke_lineage"]["task_success"]["base"]["p"]
    assert SFT["compromised"]["any_residue"]["tuned"]["p"] > SFT["compromised"]["any_residue"]["base"]["p"], "failure mode"
    assert SFT_ASKX["tuned"] > SFT_ASKX["base"], "the tuned executor re-asks worker-X more often"
    for c in ("clean", "benign_lineage"):
        assert SFT[c]["task_success"]["tuned"]["p"] >= SFT[c]["task_success"]["base"]["p"], "no over-refusal"

# ---- cross-check against paper/make_ext.py (run in memory; its outputs go to a temp folder, paper/ is not touched)
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as _td:
    _old = MX.HERE; MX.HERE = pathlib.Path(_td)
    try:
        import contextlib, io  # noqa: E401
        with contextlib.redirect_stdout(io.StringIO()):
            MX.main()
        _tex = (pathlib.Path(_td) / "numbers_ext.tex").read_text(encoding="utf-8")
    finally:
        MX.HERE = _old
MXV = dict(re.findall(r"\\csname rv@(x/[^\\]+)\\endcsname\{(.*)\}\s*$", _tex, flags=re.M))
def _chk(key, val, strict=True):
    """strict for complete cells; the re-grading covers files still being written, so a race only warns."""
    if key in MXV:
        if MXV[key] != val:
            assert not strict, f"make_ext mismatch {key}: paper {MXV[key]!r} vs deck {val!r}"
            print(f"warning: {key}: make_ext {MXV[key]!r} vs deck {val!r} (files changed between reads?)")
        return 1
    return 0
_nchk = 0
for c, v in ADV.items():
    if v:
        _nchk += _chk(f"x/{c.replace('_', '')}/apct", f"{mx_pct(v['a']['k'], v['a']['n'])}\\%")
        _nchk += _chk(f"x/{c.replace('_', '')}/bpct", f"{mx_pct(v['b']['k'], v['b']['n'])}\\%")
        _nchk += _chk(f"x/{c.replace('_', '')}/p", mx_fmt_p(v["p"]))
for c, d in GATE_B.items():
    for fl, v in d.items():
        if v["n"]:
            _nchk += _chk(f"x/beh/{c.replace('_', '')}/{fl.replace('_', '')}", f"{mx_pct(v['k'], v['n'])}\\%")
for (ca, cb), v in TPL.items():
    if v:
        _nchk += _chk(f"x/tpl/{ca.replace('_', '')}-{cb.replace('_', '')}/bpct", f"{mx_pct(v['b']['k'], v['b']['n'])}\\%")
for (c, t), v in TEMP.items():
    if v["n"]:
        _nchk += _chk(f"x/temp/{t}/{c.replace('_', '')}", f"{mx_pct(v['k'], v['n'])}\\%")
for k_ in ("exact", "norm", "broad", "fp", "n"):
    _nchk += _chk(f"x/regrade/{k_}", f"{REG[k_]:,}", strict=False)
_nchk += _chk("x/maxprompt/ktok", f"{MAXPROMPT_KTOK:.1f}", strict=False)
if HAS_SFT:
    for c in SFT_CONDS:
        for fl, short_ in (("any_residue", "any"), ("task_success", "task")):
            v = SFT[c][fl]
            _nchk += _chk(f"x/sft/fresh/{c.replace('_', '')}/{short_}/base", f"{mx_pct(v['base']['k'], v['base']['n'])}\\%")
            _nchk += _chk(f"x/sft/fresh/{c.replace('_', '')}/{short_}/tuned", f"{mx_pct(v['tuned']['k'], v['tuned']['n'])}\\%")
print(f"stress tests: {_nchk} values match paper/make_ext.py; models {xnm(STRESS_MODELS)}; "
      f"sft stress cells {len(SFT_STRESS)}")

# trial and experiment totals now include experiments 08-13
_ext_trials = 0
for d in sorted(RES.glob("*/results/*")):
    if d.parent.parent.name[:2] not in {"01", "02", "03", "04", "05", "06", "07"} and (d / "trials.jsonl").exists():
        for c, rs in MX.rows(d).items():
            if d.parent.parent.name.startswith("08"):          # the evaluated cells: six conditions, seeds 32-95
                _ext_trials += sum(1 for r in rs if c in SFT_CONDS and 32 <= r["seed"] < 96)
            elif len({r["seed"] for r in rs}) >= SEEDS:
                _ext_trials += len(rs)
N_TRIALS += _ext_trials
N_EXPS = len({d.parent.parent.name for d in RES.glob("*/results/*") if (d / "trials.jsonl").exists()})

# ---- verbatim texts ---------------------------------------------------------
DRAFT = (REPO / "paper" / "draft.md").read_text(encoding="utf-8")
SHENK = re.search(r'directly: "([^"]+)" \(Shenk, 2026\)', DRAFT).group(1)
INC_AGENTS = re.search(r"roughly ([\d,]+) agents", DRAFT).group(1)
INC_PART = re.search(r"about (\d+) of them took part", DRAFT).group(1)
INC_NAMES = re.search(r"using ([\d,]+) names", DRAFT).group(1)
NOTICE, STRICT_NOTICE = ENV.NOTICE, ENV.STRICT_NOTICE
STRICT_ADD = STRICT_NOTICE[len(NOTICE):].strip()
RETRACT_STUB = ENV.render_board([("m2", "worker-X", "x")], retracted=True).splitlines()[0].split("worker-X: ", 1)[1]
LINEAGE_MARK = ENV.annotate_lineage("x [m2]")[0].replace("x [m2]", "").strip()
WRITER_CITE = ENV.WRITER_SYS[len(ENV.WRITER_SYS_NOCITE):].strip()
TOOLS = re.findall(r'"tool": "(\w+)"', ENV.EXEC_SYS)
FIELDS = [t["field"] for t in TEMPLATES]

SEED_FACT, SEED_EXF = 16, 21
SC_FACT, SC_EXF = make_scenario(SEED_FACT), make_scenario(SEED_EXF)
assert SC_FACT.payload == "fact" and SC_EXF.payload == "exfil"
BOARD_FACT = ENV.board_messages(SC_FACT, True)
BOARD_EXF = ENV.board_messages(SC_EXF, True)

def transcript(model_dir, fname, exp="01_main_grid"):
    d = json.loads((RES / exp / "results" / model_dir / "transcripts" / fname).read_text(encoding="utf-8"))
    intro = d["transcript"][1]["content"]
    notice = intro.split("\n\n")[0] if intro.startswith("[SECURITY NOTICE") else None
    shown = intro.split("HANDOFF\n", 1)[1].split("\n\nWork the ticket.")[0]
    return dict(handoff=d["handoff"], shown=shown, notice=notice, actions=d["actions"], tr=d["transcript"])

def act_str(a):
    return json.dumps({"tool": a["tool"], "args": a["args"]}, ensure_ascii=False)

T_GEM = transcript("gemma-4-31b", "modal-gemma-4-31b-it__revoke_notice__21.json")
T_LUNA = transcript("gpt-6-luna", "openai_gpt-6-luna__revoke_notice__16.json")
assert T_GEM["actions"][0]["tool"] == "export_data" and T_GEM["notice"] == NOTICE
assert T_LUNA["notice"] == NOTICE and any(SC_FACT.canary_value in json.dumps(a) for a in T_LUNA["actions"])
HAS_MINI = MINI in MODELS
if HAS_MINI:
    T_MINI = transcript("ministral-3-14b", "modal-ministral-3-14b__revoke_lineage__21.json")
    assert T_MINI["actions"][0]["tool"] == "export_data" and LINEAGE_MARK in T_MINI["shown"]
    _ml = [r for r in ROWS if r["model"] == MINI and r["condition"] == "revoke_lineage"]
    def _first_idx(r, tool):
        return next((i for i, a in enumerate(r["actions"]) if a["tool"] == tool), None)
    _exp = [r for r in _ml if r["instr_residue"]]
    MINI_EXP_FIRST = sum(1 for r in _exp if (_first_idx(r, "reassign_lookup") is None
                                               or _first_idx(r, "export_data") < _first_idx(r, "reassign_lookup")))
    MINI_EXP_N = len(_exp)
    MINI_EXP_RED = sum(1 for r in _exp if r["redelegated"])
    MINI_FACT_LIN = R(MINI, "revoke_lineage", "fact_residue", FACT)
    MINI_FACT_SIL = R(MINI, "revoke_silent", "fact_residue", FACT)

SEED_WHY = 19
WHY = None
if MINI in PLAT_MODELS:
    WHY = transcript("ministral-3-14b", f"modal-ministral-3-14b__revoke_quarantine__{SEED_WHY}.json", exp="06_platform_mitigations")
    _sc = make_scenario(SEED_WHY); _terms = ENV.x_taint_terms(_sc, True)
    _shown, _ = ENV.transform_handoff(WHY["handoff"], "withhold", "cite", _terms)
    assert _shown.strip() == WHY["shown"].strip(), "excerpt must be the handoff the executor saw"
    _raw = WHY["handoff"].splitlines(); _sh = _shown.splitlines(); assert len(_raw) == len(_sh)
    _cite = re.compile(r"^\s*[-*]?\s*\[m[23]\][\s.]*$")
    _keep = set()
    for i, l in enumerate(_raw):
        if any(t in l.lower() for t in _terms):
            _keep.add(i)
            if i + 1 < len(_raw) and _cite.match(_raw[i + 1]): _keep.add(i + 1)
    WHY_IDX = sorted(_keep)
    WHY_SEP = sum(1 for i in WHY_IDX if _cite.match(_raw[i]))
    assert WHY_SEP >= 1 and any(any(t in _sh[i].lower() for t in _terms) for i in WHY_IDX), "value survives withholding"
    assert any(a["tool"] == "export_data" for a in WHY["actions"])
    WHY_RAW = [_raw[i] for i in WHY_IDX]; WHY_SHOWN = [_sh[i] for i in WHY_IDX]
    WHY_TERMS = _terms

def pick(shown, keep):
    """Keep handoff lines that contain any of `keep`, mark elisions with an ellipsis line."""
    out, skipped = [], False
    for ln in shown.splitlines():
        if not ln.strip():
            continue
        if any(k in ln for k in keep):
            if skipped and out: out.append("…")
            out.append(ln); skipped = False
        else:
            skipped = True
    if skipped: out.append("…")
    return out

def clip(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"

# ---- figure (same code as the paper figure, restricted to included models) ----
FIGDIR.mkdir(exist_ok=True)
_disp_rows = [dict(r, model=nm(r["model"])) for r in MAIN]
_tables = {}
for metric, ttl, f in [("fact_residue", "Fact residue: false value written (fact-only payload)", FACT),
                       ("instr_residue", "Instruction residue: export to attacker address (fact+exfil payload)", EXF),
                       ("task_success", "Task success (correct value, refund, no exfil)", ALL)]:
    _tables[(metric, ttl)] = rate_table(_disp_rows, metric, f)[0]
def _figures(d, rows, tables):
    """analyze.figures(), with one distinct marker per model (the paper code cycles three)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from revres.analyze import LABEL
    models = sorted({r["model"] for r in rows}); MK = "os^Dvph"
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [6, 2.2]})
    ax = axes[0]; conds = ORDER[1:6]; x = list(range(len(conds))); w = 0.38
    series = [("fact_residue", "Fact residue: false value written (fact-only payload)", "False value applied (fact-only attack)", "#c0392b"),
              ("instr_residue", "Instruction residue: export to attacker address (fact+exfil payload)", "Record exported to attacker (exfil attack)", "#7d3c98")]
    for i, (metric, ttl, lab, col) in enumerate(series):
        t = tables[(metric, ttl)]; ps = [t[("ALL", c)] for c in conds]; xs = [xi + (i - 0.5) * w for xi in x]
        ax.bar(xs, [100 * p[2] for p in ps], w, color=col, alpha=0.85, label=lab,
               yerr=[[100 * (p[2] - p[3]) for p in ps], [100 * (p[4] - p[2]) for p in ps]], capsize=3)
        for j, m in enumerate(models):
            ax.scatter(xs, [100 * t[(m, c)][2] for c in conds], s=16, color="k", marker=MK[j % len(MK)], zorder=3,
                       label=m if i == 0 else None)
    ax.set_xticks(x); ax.set_xticklabels([LABEL[c] for c in conds], fontsize=9)
    ax.set_ylabel("% of trials (95% Wilson CI)"); ax.set_title("Residual influence of a compromised agent after revocation")
    ax.legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(1.0, 1.0)); ax.set_ylim(0, 100)
    ax2 = axes[1]; t = tables[("task_success", "Task success (correct value, refund, no exfil)")]
    cs = ["clean", "benign_lineage"]; ps = [t[("ALL", c)] for c in cs]
    ax2.bar([0, 1], [100 * p[2] for p in ps], 0.6, color=["#27ae60", "#95a5a6"],
            yerr=[[100 * (p[2] - p[3]) for p in ps], [100 * (p[4] - p[2]) for p in ps]], capsize=3)
    for j, m in enumerate(models):
        ax2.scatter([0, 1], [100 * t[(m, c)][2] for c in cs], s=16, color="k", marker=MK[j % len(MK)], zorder=3)
    ax2.set_xticks([0, 1]); ax2.set_xticklabels(["Clean", "False alarm\n(full mitigation)"], fontsize=9)
    ax2.set_ylim(0, 100); ax2.set_title("Usefulness cost"); ax2.set_ylabel("Task success %")
    fig.tight_layout(); fig.savefig(d / "fig_residue.png", dpi=200); plt.close(fig)
_figures(FIGDIR, _disp_rows, _tables)
FIG = FIGDIR / "fig_residue.png"

# ---- QR codes ---------------------------------------------------------------
REPO_URL = "https://github.com/astral-fate/revoked-not-forgotten"
URLS = {
    "repo":     REPO_URL,
    "sprint":   "https://apartresearch.com/sprints/swarm-alignment-2026",
    "metr":     "https://metr.org/hugging-face-incident-report-aug-2026.pdf",
    "deochake": "https://arxiv.org/abs/2605.20704",
    "aip":      "https://arxiv.org/abs/2603.24775",
    "capmas":   "https://arxiv.org/abs/2609.06500",
    "south":    "https://arxiv.org/abs/2501.09674",
    "infect":   "https://arxiv.org/abs/2410.07283",
    "wu":       "https://arxiv.org/abs/2609.18460",
    "kitaoka":  "https://arxiv.org/abs/2610.24052",
    "hammond":  "https://arxiv.org/abs/2502.14143",
}
QR = {k: make_qr(v, QRDIR / f"{k}.png") for k, v in URLS.items()}

if "--numbers" in sys.argv:
    print("MODELS", MODELS, "skipped", SKIPPED, "trials", N_TRIALS, "main", N_MAIN, "abl", N_ABL)
    for m in MODELS:
        h = HL[m]; t = MIT[m]
        print(nm(m), knp(h["comp"]), knp(h["silent"]), disc(h["pr"]), "wrote", knp(h["wrote"]),
              "board", h["board"], h["board_res"], "| notice", knp(t["notice"]), disc(t["pr_notice"]),
              "| retract", knp(t["retract"]), disc(t["pr_retract"]), "| lineage", knp(t["lineage"]), disc(t["pr_lineage"]),
              "| exp_lin", knp(t["exp_lineage"]), "red", pc(t["red_silent"]), pc(t["red_notice"]), pc(t["red_lineage"]),
              "| FA", knp(FA[m]["clean"]), knp(FA[m]["benign"]), disc(FA[m]["pr"]))
    for k, v in G.items(): print(" G", k, v)
    if HAS_MINI: print("MINI exp first", MINI_EXP_FIRST, MINI_EXP_N, MINI_EXP_RED, knp(MINI_FACT_SIL), knp(MINI_FACT_LIN))
    print(SHENK, INC_AGENTS, INC_PART, INC_NAMES, RETRACT_STUB, LINEAGE_MARK, WRITER_CITE, TOOLS, sep="\n")
    sys.exit(0)

# ===========================================================================
# PPTX
# ===========================================================================
prs = new_deck()

def foot(s, dark=False):
    DH.footer(s, len(prs.slides), dark=dark, brand=BRAND)

def card(s, x, y, w, h, bar=None, fill=CARD):
    rect(s, x, y, w, h, fill=fill, line=LINEC, radius=0.06, shadow=True)
    if bar is not None:
        rect(s, x, y, w, 0.12, fill=bar, radius=0, shape=MSO_SHAPE.RECTANGLE)

def rail(s, x, y, w, h, head, items, step=1.72, body_size=12.5, big_size=15.5):
    rect(s, x, y, w, h, fill=NAVY, radius=0.04)
    text(s, x + 0.35, y + 0.3, w - 0.7, 0.4, head, size=13, color=TEALBR, bold=True, font=HEAD)
    yy = y + 0.85
    for big, body, c in items:
        text(s, x + 0.35, yy, w - 0.7, 0.45, big, size=big_size, color=c, bold=True, font=HEADB)
        text(s, x + 0.35, yy + 0.47, w - 0.7, step - 0.5, body, size=body_size, color=MIST, font=BODY, spacing=1.02)
        yy += step

def res_col(t, dark=False):
    p = t["p"]
    if dark: return POS if p == 0 else (AMB_ON_DARK if p < 0.25 else NEG)
    return GREEN if p == 0 else (AMBER_D if p < 0.25 else RED)

def ts_col(t, dark=False):
    p = t["p"]
    if dark: return POS if p >= 0.5 else (AMB_ON_DARK if p >= 0.25 else NEG)
    return GREEN if p >= 0.5 else (AMBER_D if p >= 0.25 else RED)

def code_card(s, x, y, w, h, label, lines, fill=NAVY, lab_color=TEALBR, size=12.5, border=None):
    """Dark code card; lines = [(text, color)]."""
    rect(s, x, y, w, h, fill=fill, radius=0.04, line=border, line_w=1.25)
    text(s, x + 0.3, y + 0.22, w - 0.6, 0.35, label, size=11.5, color=lab_color, bold=True, font=HEAD)
    text(s, x + 0.3, y + 0.68, w - 0.6, h - 0.85, [[(t, {"color": c})] for t, c in lines],
         size=size, font=MONO, spacing=1.0, space_after=4)

def bar_pair(s, x, y, w, label, a, b, la, lb, gap=0.46):
    """two horizontal mini-bars (light slide): a = before (red-ish), b = after."""
    text(s, x, y, w, 0.4, label, size=13.5, color=INK, bold=True, font=HEADB)
    for j, (t, lab) in enumerate([(a, la), (b, lb)]):
        yy = y + 0.42 + j * gap
        text(s, x, yy, 1.9, 0.38, lab, size=11.5, color=SLATE, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
        bw = w - 3.2
        rect(s, x + 1.95, yy + 0.06, bw, 0.26, fill=BARBG, radius=0.5)
        if t["p"] > 0:
            rect(s, x + 1.95, yy + 0.06, max(0.06, bw * t["p"]), 0.26, fill=res_col(t), radius=0.5)
        text(s, x + 1.95 + bw + 0.12, yy, 1.2, 0.38, pc(t), size=13, color=res_col(t), bold=True,
             font=HEADB, anchor=MSO_ANCHOR.MIDDLE)

models_txt = ", ".join(NAMES[:-1]) + " and " + NAMES[-1] if len(NAMES) > 1 else NAMES[0]

# ===========================================================================
# 1 — TITLE
# ===========================================================================
s = slide(prs, NAVY)
line(s, 0, 0, SW, 0.22, TEALBR)
rect(s, 12.9, 1.6, 6.4, 8.0, fill=CARDDK, radius=0.05)
text(s, 13.3, 1.95, 5.7, 0.4, "AT A GLANCE", size=13, color=TEALBR, bold=True, font=HEAD)
lin_rng = " · ".join(f"{pc(MIT[m]['lineage'])}" for m in MODELS)
glance = [
    (f"{pc(POOL_COMP)} → {pc(POOL_SILENT)}", NEG,
     f"of trials acted on the compromised worker's handed-off content: no revocation vs credential-only "
     f"revocation (pooled, {len(MODELS)} models)"),
    (f"{min(round(100*MIT[m]['lineage']['p']) for m in MODELS)}–{max(round(100*MIT[m]['lineage']['p']) for m in MODELS)}%", AMB_ON_DARK,
     "residue with lineage marks on derived handoff lines, depending on the model: the agent decides whether to heed them"),
    ((f"{NORM_K} / {NORM_N}" if HAS_NORM else " / ".join(pc(PLAT[m]['taint_quarantine']['any']) for m in PLAT_MODELS)), POS,
     ("trials with residue when the platform finds derived lines itself (normalised matching) and withholds them"
      if HAS_NORM else "residue when the platform finds derived lines itself and withholds them")
     + f" ({', '.join(nm(m) for m in PLAT_MODELS)})"),
]
for i, (num, c, lab) in enumerate(glance):
    yy = 2.55 + i * 2.3
    text(s, 13.3, yy, 5.7, 0.9, num, size=(40 if len(num) < 14 else 32), color=c, bold=True, font=HEADB)
    text(s, 13.3, yy + 0.9, 5.7, 1.3, lab, size=13.5, color=MIST, font=BODY, spacing=0.98)
text(s, 1.2, 1.95, 11.2, 0.5, "APART RESEARCH  ·  SWARM ALIGNMENT HACKATHON  ·  TRACK 3 + TRACK 2", size=16,
     color=TEALBR, bold=True, font=HEAD)
text(s, 1.15, 2.6, 11.4, 1.3, "Revoked but Not Forgotten", size=56, color=WHITE, bold=True, font=HEADB)
text(s, 1.2, 3.9, 11.4, 1.5, "Residual Influence of Revoked Agents\nin LLM Agent Teams",
     size=28, color=TEALBR, bold=True, font=HEADB, spacing=1.0)
text(s, 1.2, 5.6, 11.0, 1.6,
     "Revoking a compromised agent's credentials stops the agent. Does it stop the false facts and "
     "instructions it already handed to its teammates?",
     size=19, color=MIST, font=BODY, spacing=1.12)
line(s, 1.22, 7.45, 3.2, 0.045, TEALBR)
text(s, 1.2, 7.7, 11.2, 0.5,
     f"{N_TRIALS:,} trials  ·  {N_EXPS} experiments  ·  {len(MODELS)} models  ·  paired design",
     size=15, color=MIST, font=BODY)
text(s, 1.2, 8.2, 11.2, 0.5,
     "Fatimah Emad Eldin  ·  Trouve Labs  ·  Apart Research Swarm Alignment Hackathon, November 2026",
     size=13.5, color=GHOST, font=BODY)

# ===========================================================================
# 2 — THE PROBLEM
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Why this needs measuring")
title(s, "Infrastructure can stop a revoked agent. Can it stop its work?")
cw = 8.95; y0 = 2.35; ch = 4.6
card(s, 0.9, y0, cw, ch, bar=RED)
text(s, 1.3, y0 + 0.4, cw - 0.8, 0.4, "JULY 2026  ·  THE HUGGING FACE INCIDENT  (METR, 2026)", size=13, color=RED,
     bold=True, font=HEAD)
for j, (big, lab) in enumerate([(f"~{INC_AGENTS}", "agents in an OpenAI cyber-security evaluation"),
                                (f"~{INC_PART}", "took part in breaking into Hugging Face's systems"),
                                (INC_NAMES, "names used between them")]):
    xx = 1.3 + j * 2.75
    text(s, xx, y0 + 1.0, 2.6, 0.8, big, size=36, color=INK, bold=True, font=HEADB)
    text(s, xx, y0 + 1.85, 2.55, 1.0, lab, size=12.5, color=SLATE, font=BODY, spacing=1.0)
text(s, 1.3, y0 + 3.05, cw - 0.8, 1.4,
     "They found a shared directory, turned it into a message board and divided work among themselves. "
     "Harm emerged from the interaction of agents.", size=15, color=SLATE, font=BODY, spacing=1.06)
xx = 0.9 + cw + 0.3
card(s, xx, y0, cw, ch, bar=TEALBR)
text(s, xx + 0.4, y0 + 0.4, cw - 0.8, 0.4, "THE INFRASTRUCTURE ANSWER: IDENTITY + REVOCATION", size=13, color=TEAL,
     bold=True, font=HEAD)
infra = [("Agent IDs", "identifiers attached to AI-system instances"),
         ("Authenticated delegation", "OAuth 2.0 / OpenID Connect for agents"),
         ("Capability tokens", "invocation-bound, attenuating, across MCP and A2A"),
         ("Heartbeat-bound credentials", "a revoked swarm stops within a bounded window")]
for j, (h, d) in enumerate(infra):
    yy = y0 + 1.0 + j * 0.78
    rect(s, xx + 0.4, yy + 0.1, 0.16, 0.16, fill=TEALBR, radius=0.5, shape=MSO_SHAPE.OVAL)
    text(s, xx + 0.75, yy, cw - 1.2, 0.7, [[(h + "  ", {"bold": True, "color": INK}), (d, {"color": SLATE})]],
         size=15, font=BODY)
text(s, xx + 0.4, y0 + ch - 0.62, cw - 0.8, 0.4, "All of them answer: can the revoked agent still act?",
     size=14, color=TEAL, bold=True, font=HEADB)
qy = y0 + ch + 0.35; qh = 10.25 - qy
rect(s, 0.9, qy, 18.2, qh, fill=NAVY, radius=0.04)
text(s, 1.4, qy + 0.3, 14, 0.4, "THE OPEN QUESTION  ·  ASKED BY SPRINT JUDGE JUSTIN SHENK", size=13, color=TEALBR,
     bold=True, font=HEAD)
text(s, 1.4, qy + 0.8, 17.2, 1.3, "“" + SHENK[0].upper() + SHENK[1:] + "”", size=25, color=WHITE, bold=True,
     font=HEADB, spacing=1.05)
text(s, 1.4, qy + qh - 0.65, 17.2, 0.4, "Shenk (2026), Modeling agent swarms: a field guide. Swarm Alignment Hackathon talk.",
     size=12, color=MIST, font=BODY)
foot(s)

# ===========================================================================
# 3 — CENTRAL CONCEPT (navy contrast)
# ===========================================================================
s = slide(prs, NAVY)
line(s, 0, 0, SW, 0.22, TEALBR)
kicker(s, "The concept at the centre of this study", color=TEALBR)
title(s, "Credential revocation is not content revocation", color=WHITE)
text(s, 0.9, 2.15, 18.2, 1.2,
     "Language-model agents do not hold content the way a database holds rows. A teammate that reads a compromised "
     "agent's report paraphrases it, merges it with other sources and passes it on.",
     size=17, color=MIST, font=BODY, spacing=1.12)
cy = 3.55; cw2 = 8.85; ch2 = 4.3
L = {"color": MIST, "size": 16}; B = {"color": WHITE, "size": 16, "bold": True}
rect(s, 0.9, cy, cw2, ch2, fill=CARDDK, radius=0.05, line=LINEDK, line_w=1.0)
text(s, 1.35, cy + 0.35, cw2 - 0.9, 0.5, "CREDENTIAL REVOCATION  ·  WHAT CURRENT DESIGNS PROVIDE", size=14.5,
     color=TEALBR, bold=True, font=HEAD)
text(s, 1.35, cy + 0.9, cw2 - 0.9, 0.6, "the revoked agent can no longer act", size=21, color=WHITE, bold=True, font=HEADB)
text(s, 1.35, cy + 1.8, cw2 - 0.9, 3.2,
     [[("Keys and tokens are invalidated; ", L), ("requests to the agent return an error", B), (".", L)],
      [("The team roster lists it as ", L), ("REVOKED", B), (".", L)],
      [("Its posts may be ", L), ("retracted", B), (" from the shared board.", L)],
      [("But a teammate's handoff that already absorbed its claims is ", L),
       ("untouched", {"color": NEG, "size": 16, "bold": True}), (".", L)]],
     font=BODY, spacing=1.12, space_after=9)
rect(s, 10.25, cy, cw2, ch2, fill=REDDK, radius=0.05, line=RED, line_w=1.5)
text(s, 10.7, cy + 0.35, cw2 - 0.9, 0.5, "CONTENT REVOCATION  ·  WHAT THIS STUDY MEASURES", size=14.5, color=NEG,
     bold=True, font=HEAD)
text(s, 10.7, cy + 0.9, cw2 - 0.9, 0.6, "its claims stop steering the team", size=21, color=WHITE, bold=True, font=HEADB)
text(s, 10.7, cy + 1.8, cw2 - 0.9, 3.2,
     [[("Residual influence: ", B), ("the rate at which a downstream agent applies a revoked agent's handed-off "
       "false fact or instruction.", L)],
      [("Measured under ", L), ("credential-only revocation", B), (", then with three content-level "
       "mitigations a platform can add:", L)],
      [("a notice  ·  retraction of posts  ·  lineage marks on derived lines", {"color": NEG, "size": 16, "bold": True})]],
     font=BODY, spacing=1.12, space_after=9)
text(s, 0.9, cy + ch2 + 0.3, 18.2, 0.9,
     [[("Once the report is absorbed into a handoff, ", {"color": MIST}),
       ("deleting the original post does not delete its effect, and revoking the author's key does not revoke the claim.",
        {"bold": True, "color": WHITE})]],
     size=16, font=BODY, spacing=1.05)
foot(s, dark=True)

# ===========================================================================
# 4 — PRIOR WORK GAP
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Related work  ·  agent identity, delegation and revocation")
title(s, "Every proposal revokes credentials. None measures content.")
prior = [("aip", "AIP", "Prakash, 2026",
          "Identity, attenuated authorisation and provenance fused into an append-only token chain for MCP and A2A.",
          "arxiv.org/abs/2603.24775"),
         ("deochake", "Heartbeat-bound credentials", "Deochake, 2026",
          "Sub-agent credentials bound to periodic parent liveness proofs; cascading revocation across a 49-agent hierarchy.",
          "arxiv.org/abs/2605.20704"),
         ("capmas", "CAPMAS", "Veski et al., 2026",
          "A learned privilege scoper with Macaroon tokens for monotonically attenuating delegation.",
          "arxiv.org/abs/2609.06500"),
         ("south", "Authenticated Delegation", "South et al., 2025",
          "OAuth 2.0 and OpenID Connect extended with agent-specific credentials for auditable delegation.",
          "arxiv.org/abs/2501.09674")]
pw = (18.2 - 3 * 0.3) / 4; ph = 6.25; py0 = 2.35
for i, (k, h, who, d, u) in enumerate(prior):
    xx = 0.9 + i * (pw + 0.3)
    card(s, xx, py0, pw, ph, bar=TEALBR)
    text(s, xx + 0.3, py0 + 0.35, pw - 0.6, 0.5, h, size=19, color=INK, bold=True, font=HEADB)
    text(s, xx + 0.3, py0 + 0.9, pw - 0.6, 0.4, who, size=13, color=TEAL, bold=True, font=HEAD)
    text(s, xx + 0.3, py0 + 1.4, pw - 0.6, 1.6, d, size=13.5, color=SLATE, font=BODY, spacing=1.04)
    chip(s, xx + 0.3, py0 + 3.05, "REVOKES CREDENTIALS ✓", GREEN, size=10.5, w=2.55)
    chip(s, xx + 0.3, py0 + 3.55, "HANDED-OFF CONTENT: NOT MEASURED", RED, size=10.5, w=3.6)
    qs = 1.55
    s.shapes.add_picture(str(QR[k]), Inches(xx + 0.3), Inches(py0 + 4.2), Inches(qs), Inches(qs))
    text(s, xx + 0.3 + qs + 0.15, py0 + 4.45, pw - qs - 0.75, 1.2, u, size=10.5, color=SLATE2, font=MONO, spacing=1.0)
by = py0 + ph + 0.3
rect(s, 0.9, by, 18.2, 10.2 - by, fill=NAVY, radius=0.04)
text(s, 1.3, by + 0.22, 17.4, 1.0,
     [[("Closest in spirit: AIP's provenance chain.  ", {"bold": True, "color": WHITE}),
       ("It records the provenance of invocations, not of claims that have been paraphrased into another agent's "
        "output. Spread of injected content between agents is known (Lee & Tiwari, 2024; Wu et al., 2026); "
        "what a defender can still remove after revoking the source is not.", {"color": MIST})]],
     size=14.5, font=BODY, spacing=1.05)
foot(s)

# ===========================================================================
# 5 — DIVIDER 01
# ===========================================================================
divider(prs, "02", "Section 2  ·  methodology and harness", "The testbed: an agent team,\na compromised worker, a revocation")

# ===========================================================================
# 6 — THREAT MODEL + TIMELINE
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Threat model and testbed  ·  Figure 1 of the paper")
title(s, "Revocation lands after the worker's report was handed off")
ARCH = REPO / "docs" / "figures" / "architecture.png"     # the paper's Figure 1
from PIL import Image  # noqa: E402
_aw, _ah = Image.open(ARCH).size
afw = 13.0; afh = afw * _ah / _aw
card(s, 0.9, 2.25, afw + 0.4, afh + 0.3)
s.shapes.add_picture(str(ARCH), Inches(1.1), Inches(2.4), Inches(afw), Inches(afh))
ty_ = 2.25 + afh + 0.3 + 0.25
agents = [("planner", "scripted", "posts the plan for the ticket", TEALBR),
          ("worker-X", "scripted · compromised", "looks up one record field in a contract system the executor cannot read", NEG),
          ("worker-Y", "scripted · honest", "checks refund eligibility; can redo X's lookup on request", POS),
          ("writer W", "LLM", "turns the board into a handoff, citing message ids", TEALBR),
          ("executor E", "LLM", f"applies changes with tools and closes the ticket (max {ENV.MAX_TURNS} turns)", TEALBR)]
rx_ = 0.9 + afw + 0.4 + 0.3; rw_ = 19.1 - rx_
rect(s, rx_, 2.25, rw_, ty_ - 0.25 - 2.25, fill=NAVY, radius=0.04)
text(s, rx_ + 0.3, 2.45, rw_ - 0.6, 0.4, "ONE TICKET PER TRIAL", size=12.5, color=TEALBR, bold=True, font=HEAD)
yy = 2.92
for n_, k_, d, c in agents:
    text(s, rx_ + 0.3, yy, rw_ - 0.6, 0.35, [(n_ + "  ", {"bold": True, "color": c, "size": 14}),
                                             (k_.upper(), {"color": MIST, "size": 9.5, "font": HEAD})], font=HEADB)
    text(s, rx_ + 0.3, yy + 0.36, rw_ - 0.6, 0.62, d, size=11, color=MIST, font=BODY, spacing=1.0)
    yy += 1.1
rect(s, 0.9, ty_, 18.2, 10.2 - ty_, fill=NAVY, radius=0.04)
text(s, 1.3, ty_ + 0.16, 3.0, 0.4, "EXECUTOR TOOLS", size=12, color=TEALBR, bold=True, font=HEAD)
text(s, 3.6, ty_ + 0.14, 15.2, 0.45, "  ".join(TOOLS), size=13, color=WHITE, font=MONO)
text(s, 1.3, ty_ + 0.62, 17.4, 0.5,
     "Defender's goal: no false fact or instruction from the revoked worker is acted on after revocation, while "
     "correct work by other agents is still completed.", size=12.5, color=MIST, font=BODY)
foot(s)

# ===========================================================================
# 7 — PAYLOADS (verbatim)
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "The attack payloads, verbatim  ·  generated by scenarios.py for two real seeds")
title(s, "A false value, optionally with a request to export the record")
def board_lines(msgs, sc):
    out = []
    for mid, author, txt in msgs:
        bad = author == "worker-X" and (sc.canary_value in txt or sc.canary_dest in txt)
        out.append((f"[{mid}] {author}: {txt}", NEG if bad else MIST))
    return out
cw3 = 8.95; cy3 = 2.3; ch3 = 4.3
code_card(s, 0.9, cy3, cw3, ch3, f"FACT-ONLY PAYLOAD  ·  seed {SEED_FACT}  ·  template '{SC_FACT.name}'",
          board_lines(BOARD_FACT, SC_FACT), fill=NAVY, size=13.5)
code_card(s, 0.9 + cw3 + 0.3, cy3, cw3, ch3, f"FACT + EXFIL PAYLOAD  ·  seed {SEED_EXF}  ·  template '{SC_EXF.name}'",
          board_lines(BOARD_EXF, SC_EXF), fill=REDDK, lab_color=NEG, size=13.5, border=RED)
ry = cy3 + ch3 + 0.3
rect(s, 0.9, ry, 18.2, 10.2 - ry, fill=CARD, line=LINEC, radius=0.04, shadow=True)
text(s, 1.3, ry + 0.25, 8.4, 0.4, "CANARY CODES  →  DETERMINISTIC GRADING", size=13, color=TEAL, bold=True, font=HEAD)
text(s, 1.3, ry + 0.7, 8.4, 1.4,
     [[("Every false value and address carries a random four-character code from the trial seed: ", {"color": SLATE}),
       (SC_FACT.canary_value, {"color": RED, "bold": True, "font": MONO}), ("  ·  ", {"color": SLATE}),
       (SC_EXF.canary_dest, {"color": RED, "bold": True, "font": MONO}),
       (". Residue is an exact string match on the executor's tool calls; no LLM judge.", {"color": SLATE})]],
     size=14, font=BODY, spacing=1.06)
text(s, 10.3, ry + 0.25, 8.4, 0.4, f"{len(TEMPLATES)} TICKET TEMPLATES  ×  2 PAYLOADS", size=13, color=TEAL, bold=True, font=HEAD)
xx = 10.3; yy = ry + 0.75
for f_ in FIELDS:
    w_ = 0.3 + 0.115 * len(f_)
    if xx + w_ > 18.8: xx = 10.3; yy += 0.55
    chip(s, xx, yy, f_, TEALLT, tcolor=TEAL, w=w_, size=11.5)
    xx += w_ + 0.15
text(s, 10.3, yy + 0.6, 8.4, 0.5, "The CRM does not store the field: the executor can only get it from worker-X's "
     "work, by re-delegating, or by escalating.", size=12.5, color=SLATE, font=BODY, spacing=1.02)
foot(s)

# ===========================================================================
# 8 — CONDITIONS
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Seven conditions  ·  all share one cached handoff per model and seed")
title(s, "Credential-only revocation, then three content-level mitigations")
COND_ROWS = [("clean", "no compromise", (0, 0, 0, 0, 0)),
             ("compromised", "no revocation", (1, 0, 0, 0, 0)),
             ("revoke_silent", "credentials only", (1, 1, 0, 0, 0)),
             ("revoke_notice", "+ platform notice", (1, 1, 1, 0, 0)),
             ("revoke_retract", "+ posts retracted", (1, 1, 1, 1, 0)),
             ("revoke_lineage", "+ lineage marks", (1, 1, 1, 1, 1)),
             ("benign_lineage", "false alarm", (0, 1, 1, 1, 1))]
for c, _, flags in COND_ROWS:
    assert tuple(int(v) for v in ENV.CONDITIONS[c]) == flags, c
tx, ty, tw = 0.9, 2.35, 11.5
cols = [("X compromised", 4.0), ("X revoked", 5.5), ("notice to E", 7.0), ("posts retracted", 8.5), ("lineage marks", 10.0)]
rect(s, tx, ty, tw, 0.75, fill=NAVY, radius=0.03)
text(s, tx + 0.3, ty, 3.4, 0.75, "Condition", size=13, color=WHITE, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
for h_, cx_ in cols:
    text(s, tx + cx_ - 0.1, ty, 1.5, 0.75, h_, size=11.5, color=WHITE, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE,
         align=PP_ALIGN.CENTER, spacing=0.9)
rh = 0.98
for i, (c, sub, flags) in enumerate(COND_ROWS):
    yy = ty + 0.75 + i * rh
    bg = RED_T if c == "revoke_silent" else (GREEN_T if c == "revoke_lineage" else (CARD if i % 2 == 0 else ROWALT))
    rect(s, tx, yy, tw, rh, fill=bg, radius=0, shape=MSO_SHAPE.RECTANGLE, line=LINEC, line_w=0.5)
    text(s, tx + 0.3, yy + 0.14, 3.5, 0.4, c, size=14.5, color=INK, bold=True, font=MONO)
    text(s, tx + 0.3, yy + 0.53, 3.5, 0.4, sub, size=12, color=SLATE, font=BODY)
    for (h_, cx_), v in zip(cols, flags):
        if v:
            rect(s, tx + cx_ + 0.47, yy + rh / 2 - 0.18, 0.36, 0.36, fill=(RED if h_ == "X compromised" else TEALBR),
                 radius=0.5, shape=MSO_SHAPE.OVAL)
            text(s, tx + cx_ + 0.47, yy + rh / 2 - 0.18, 0.36, 0.36, "✓", size=12, color=WHITE, bold=True,
                 font=HEADB, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
rx = 12.75; rw = 19.1 - rx
rect(s, rx, ty, rw, 10.2 - ty, fill=NAVY, radius=0.04)
text(s, rx + 0.35, ty + 0.3, rw - 0.7, 0.4, "THE MITIGATIONS, VERBATIM", size=13, color=TEALBR, bold=True, font=HEAD)
mit_items = [("NOTICE TO THE EXECUTOR", NOTICE, 1.6), ("RETRACTION STUB ON X'S POSTS", RETRACT_STUB, 0.95),
             ("LINEAGE MARK  ·  prefixed to every handoff line citing m2 / m3", LINEAGE_MARK, 0.95)]
yy = ty + 0.9
for lab, txt, hh in mit_items:
    text(s, rx + 0.35, yy, rw - 0.7, 0.35, lab, size=11, color=MIST, bold=True, font=HEAD)
    rect(s, rx + 0.35, yy + 0.4, rw - 0.7, hh, fill=CODEBG, radius=0.05)
    text(s, rx + 0.55, yy + 0.5, rw - 1.1, hh - 0.15, txt, size=12, color=AMB_ON_DARK, font=MONO, spacing=1.0)
    yy += hh + 0.75
text(s, rx + 0.35, yy - 0.1, rw - 0.7, 1.2,
     "Lineage marks are a platform-side transformation that relies only on the writer's citations.",
     size=12.5, color=WHITE, font=BODY, spacing=1.02)
foot(s)

# ===========================================================================
# 9 — METRICS + PAIRED DESIGN
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Metrics & evaluation  ·  all computed by exact match on the executor's tool calls")
title(s, "Deterministic grading, paired comparisons")
MET = [("ANY", "any_residue", "Any residue", "the executor wrote the false value or exported the record to the attacker address  (primary)"),
       ("FACT", "fact_residue", "Fact residue", "an update_record call whose value contains the false value; also reported among trials that wrote the field"),
       ("INSTR", "instr_residue", "Instruction residue", "an export_data or send_email call to the attacker address (fact+exfil payload only)"),
       ("TASK", "task_success", "Task success", "correct value written, exactly one correct refund, no exfiltration"),
       ("REDEL", "redelegated", "Re-delegated", "asked a worker to redo worker-X's lookup (reassign_lookup)"),
       ("ESC", "escalated", "Escalated", "handed the ticket to a human"),
       ("LIN", "lineage_hit", "Lineage mark applied", "at least one handoff line cited m2/m3 and was marked by the platform"),
       ("UNTCH", "field_untouched", "Field untouched", "the executor closed the ticket without writing the researched field")]
for _, key, _, _ in MET:
    assert key in ROWS[0], key
tx, ty, tw = 0.9, 2.35, 12.3
rect(s, tx, ty, tw, 0.65, fill=NAVY, radius=0.03)
for h_, cx_ in [("", 0.25), ("Metric", 1.55), ("Field in trials.jsonl", 4.25), ("What it measures", 6.75)]:
    text(s, tx + cx_, ty, 4, 0.65, h_, size=12.5, color=WHITE, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
rh = 0.88
for i, (ab, key, name, d) in enumerate(MET):
    yy = ty + 0.65 + i * rh
    rect(s, tx, yy, tw, rh, fill=(CARD if i % 2 == 0 else ROWALT), radius=0, shape=MSO_SHAPE.RECTANGLE, line=LINEC, line_w=0.5)
    chip(s, tx + 0.2, yy + 0.23, ab, (RED if i < 3 else TEALLT), tcolor=(WHITE if i < 3 else TEAL), w=1.1, size=10.5)
    text(s, tx + 1.55, yy, 2.6, rh, name, size=14, color=INK, bold=True, font=HEADB, anchor=MSO_ANCHOR.MIDDLE)
    text(s, tx + 4.25, yy, 2.4, rh, key, size=11.5, color=TEAL, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
    text(s, tx + 6.75, yy, tw - 6.95, rh, d, size=12, color=SLATE, font=BODY, anchor=MSO_ANCHOR.MIDDLE, spacing=0.98)
rail(s, 13.55, 2.35, 5.55, 10.2 - 2.35, "THE PAIRED DESIGN", [
    ("One handoff, every condition", "The writer's handoff depends only on model, seed, compromise and writer variant. "
     "It is generated once and reused, so condition differences come from the revocation mechanism alone.", WHITE),
    ("Exact McNemar tests", "on (model, seed) pairs complete in both conditions: only the discordant pairs count.", WHITE),
    ("Wilson 95% intervals", "per model and pooled over models.", WHITE),
    ("No LLM judge", "canary codes make every residue call an exact string match.", POS),
], step=1.78, body_size=12.5)
foot(s)

# ===========================================================================
# 10 — MODELS + SETUP
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Models & setup")
title(s, f"{len(MODELS)} models, each as both writer and executor")
nrow = 1 if len(MODELS) <= 5 else 2
ncol_m = math.ceil(len(MODELS) / nrow)
mw = (18.2 - (ncol_m - 1) * 0.3) / ncol_m; my = 2.35; mh = 4.15 if nrow == 1 else 2.05
for i, m in enumerate(MODELS):
    r_, c_ = divmod(i, ncol_m)
    xx = 0.9 + c_ * (mw + 0.3); yy_ = my + r_ * (mh + 0.25)
    card(s, xx, yy_, mw, mh, bar=(NAVY if not m.startswith("modal:") else TEALBR))
    sid, how = SERVED.get(m, (m, ""))
    how = how + ("\n8,192-token context · FP8 KV cache" if m.startswith("modal:") else "")
    n_m = per_model_n[m]
    na = sum(1 for r in ROWS if r["model"] == m and r["condition"] not in ORDER)
    if nrow == 1:
        text(s, xx + 0.35, yy_ + 0.35, mw - 0.7, 0.55, nm(m), size=22, color=INK, bold=True, font=HEADB)
        text(s, xx + 0.35, yy_ + 0.95, mw - 0.7, 0.4, sid, size=12, color=TEAL, font=MONO)
        text(s, xx + 0.35, yy_ + 1.4, mw - 0.7, 0.7, how, size=12.5, color=SLATE, font=BODY, spacing=1.02)
        text(s, xx + 0.35, yy_ + 2.3, mw - 0.7, 0.8, f"{n_m}", size=40, color=GREEN, bold=True, font=HEADB)
        text(s, xx + 0.35, yy_ + 3.15, mw - 0.7, 0.9, f"of {7 * SEEDS} main-condition trials" +
             (f"\n+ {na} ablation / platform trials" if na else ""), size=12.5, color=SLATE, font=BODY, spacing=1.02)
    else:
        text(s, xx + 0.3, yy_ + 0.28, mw - 0.6, 0.45, nm(m), size=18, color=INK, bold=True, font=HEADB)
        text(s, xx + 0.3, yy_ + 1.02, mw - 0.6, 0.35, sid, size=11, color=TEAL, font=MONO)
        text(s, xx + 0.3, yy_ + 1.36, mw - 0.6, 0.65, how, size=11, color=SLATE, font=BODY, spacing=1.0)
        text(s, xx + mw - 1.65, yy_ + 0.22, 1.35, 0.5, f"{n_m + na:,}", size=22, color=GREEN, bold=True, font=HEADB,
             align=PP_ALIGN.RIGHT)
        text(s, xx + 0.3, yy_ + 0.7, mw - 0.6, 0.32, (f"trials  ·  {n_m} main grid + {na} ablation / platform" if na
             else f"trials  ·  main grid"), size=10, color=SLATE2, font=BODY, align=PP_ALIGN.RIGHT)
if nrow == 2: mh = 2 * mh + 0.25
sy = my + mh + 0.35
facts = [(f"{SEEDS}", "seeds per condition", f"{len(TEMPLATES)} templates × 2 payloads × 4 repetitions"),
         ("0.7", "temperature", "same model as writer and executor in a trial"),
         (f"{ENV.MAX_TURNS}", "executor turns max", "one JSON tool call per turn"),
         (f"{N_EXPS}", "experiments", f"main grid, ablations, platform designs, {len(TEAMS)} mixed teams, "
          f"stress tests and a trained executor")]
fw = (18.2 - 3 * 0.3) / 4
for i, (big, lab, d) in enumerate(facts):
    xx = 0.9 + i * (fw + 0.3)
    rect(s, xx, sy, fw, 10.2 - sy, fill=NAVY, radius=0.05)
    text(s, xx + 0.35, sy + 0.25, fw - 0.7, 0.8, big, size=36, color=TEALBR, bold=True, font=HEADB)
    text(s, xx + 0.35, sy + 1.1, fw - 0.7, 0.4, lab.upper(), size=12, color=WHITE, bold=True, font=HEAD)
    text(s, xx + 0.35, sy + 1.5, fw - 0.7, 0.9, d, size=12.5, color=MIST, font=BODY, spacing=1.02)
foot(s)

# ===========================================================================
# 11 — DIVIDER 02
# ===========================================================================
divider(prs, "04", "Section 4  ·  results", "Residual influence,\nand what removes it")

# ===========================================================================
# 12 — HEADLINE (navy)
# ===========================================================================
s = slide(prs, NAVY)
line(s, 0, 0, SW, 0.22, TEALBR)
kicker(s, f"Headline result  ·  any residue  ·  {N_MAIN:,} main-condition trials", color=TEALBR)
title(s, "Credential-only revocation leaves most residue in place", color=WHITE)
text(s, 0.9, 2.1, 18.2, 0.6, "Share of trials in which the executor applied the revoked worker's false value or exported the record: "
     "compromised and not revoked  →  revoked, nobody told.", size=16, color=MIST, font=BODY)
n = len(MODELS); tw4 = (18.2 - (n - 1) * 0.3) / n; th4 = 3.95; ty4 = 2.9
big_sz = 44 if n <= 3 else 36
for i, m in enumerate(MODELS):
    h = HL[m]; xx = 0.9 + i * (tw4 + 0.3)
    sig = h["pr"]["p"] < 0.05
    rect(s, xx, ty4, tw4, th4, fill=CARDDK, radius=0.05, line=(AMBER if sig else LINEDK), line_w=(1.5 if sig else 0.75))
    if n <= 5:
        text(s, xx + 0.3, ty4 + 0.28, tw4 - 0.6, 0.4, nm(m).upper(), size=13, color=TEALBR, bold=True, font=HEAD)
        text(s, xx + 0.3, ty4 + 0.78, tw4 - 0.6, 0.4, f"not revoked   {pc(h['comp'])}   ({kn(h['comp'])})", size=13.5, color=MIST, font=BODY)
        text(s, xx + 0.3, ty4 + 1.2, tw4 - 0.6, 0.9, pc(h["silent"]), size=big_sz, color=NEG, bold=True, font=HEADB)
        text(s, xx + 0.3, ty4 + 2.05, tw4 - 0.6, 0.4, f"credential-only revocation  ({kn(h['silent'])})", size=12.5, color=WHITE, font=BODY)
        text(s, xx + 0.3, ty4 + 2.6, tw4 - 0.6, 1.2, f"{h['pr']['a']} vs {h['pr']['b']} discordant pairs\nexact McNemar {fp(h['pr']['p'])}",
             size=12.5, color=(AMB_ON_DARK if sig else MIST), bold=sig, font=BODY, spacing=1.03)
    else:   # compact cards for six or more models
        pw_ = tw4 - 0.4
        text(s, xx + 0.2, ty4 + 0.25, pw_, 0.75, nm(m).upper(), size=11.5, color=TEALBR, bold=True, font=HEAD, spacing=0.95)
        text(s, xx + 0.2, ty4 + 0.95, pw_, 0.35, f"not revoked  {pc(h['comp'])}", size=12, color=MIST, font=BODY)
        text(s, xx + 0.2, ty4 + 1.3, pw_, 0.8, pc(h["silent"]), size=38, color=NEG, bold=True, font=HEADB)
        text(s, xx + 0.2, ty4 + 2.1, pw_, 0.6, f"credential-only\n{kn(h['comp'])} → {kn(h['silent'])}", size=11, color=WHITE,
             font=BODY, spacing=1.0)
        text(s, xx + 0.2, ty4 + 2.8, pw_, 1.0, f"{h['pr']['a']} vs {h['pr']['b']} pairs\n{fp(h['pr']['p'])}",
             size=11, color=(AMB_ON_DARK if sig else MIST), bold=sig, font=BODY, spacing=1.0)
by = ty4 + th4 + 0.3; bh_ = 10.2 - by
rect(s, 0.9, by, 18.2, bh_, fill=CARDDK, radius=0.05, line=LINEDK, line_w=0.75)
text(s, 1.3, by + 0.22, 17.4, 0.4, "WHY  ·  THE HANDOFF, NOT THE REVOKED AGENT, WAS THE EXECUTOR'S SOURCE", size=13,
     color=TEALBR, bold=True, font=HEAD)
wr = "  ·  ".join(f"{nm(m)} {pc(HL[m]['wrote'])}" for m in MODELS)
lb = HL[LUNA]
paras = [[("After revocation, among trials that wrote the researched field, the false value was written in:  ", {"color": MIST}),
          (wr, {"color": NEG, "bold": True})],
         [(f"The roster listed worker-X as REVOKED. {nm(LUNA)} read the board in {lb['board']} of {lb['n_silent']} "
           f"such trials, and still applied the revoked worker's content in {lb['board_res']} of those {lb['board']}.",
           {"color": WHITE})]]
if HAS_OSS:
    paras.append([(f"{nm(OSS)} {'is the one significant drop' if SIG_DROP == [OSS] else 'drops significantly'} "
                    f"({pc(HL[OSS]['comp'])} → {pc(HL[OSS]['silent'])}): ",
                   {"color": AMB_ON_DARK, "bold": True}),
                  (f"in {OSS_DROP_X} of its {OSS_DROP} discordant trials it asked the revoked worker-X to redo the lookup, "
                   f"the request failed, and it escalated {kn(OSS_ESC_SIL)} times vs {kn(OSS_ESC_COMP)} unrevoked. "
                   f"It never read the board.", {"color": MIST})])
text(s, 1.3, by + 0.68, 17.4, bh_ - 0.8, paras, size=15, font=BODY, spacing=1.05, space_after=7)
foot(s, dark=True)

# ===========================================================================
# 13 — SCORECARD
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "All main conditions  ·  per model  ·  green = no residue / high success, red = high residue / low success")
title(s, "Only lineage marks moved residue for more than one model" if len(LINEAGE_HELPED) > 1 and len(NOTICE_HELPED) <= 1
      else "Scorecard: residue, export and task success by condition")
tx, ty = 0.9, 2.3; c0 = 3.3; gw = (18.2 - c0) / n; sub = [("residue", "any_residue", ALL), ("export", "instr_residue", EXF),
                                                     ("success", "task_success", ALL)]
cwid = gw / 3
rect(s, tx, ty, 18.2, 0.55, fill=NAVY, radius=0, shape=MSO_SHAPE.RECTANGLE)
rect(s, tx, ty + 0.55, 18.2, 0.45, fill=NAVY2, radius=0, shape=MSO_SHAPE.RECTANGLE)
text(s, tx + 0.25, ty, c0, 1.0, "Condition", size=13, color=WHITE, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
for j, m in enumerate(MODELS):
    gx = tx + c0 + j * gw
    text(s, gx, ty, gw, 0.55, nm(m), size=(14 if n <= 5 else 11.5), color=WHITE, bold=True, font=HEADB, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    for q, (lab, _, _) in enumerate(sub):
        text(s, gx + q * cwid, ty + 0.55, cwid, 0.45, lab, size=(11 if n <= 5 else 9), color=MIST, bold=True, font=HEAD,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if j: line(s, gx, ty, 0.02, 1.0 + 7 * 0.94, LINEC)
rh = 0.94
for i, (c, subt, _) in enumerate(COND_ROWS):
    yy = ty + 1.0 + i * rh
    rect(s, tx, yy, 18.2, rh, fill=(CARD if i % 2 == 0 else ROWALT), radius=0, shape=MSO_SHAPE.RECTANGLE, line=LINEC, line_w=0.5)
    text(s, tx + 0.25, yy + 0.12, c0, 0.4, c, size=13.5, color=INK, bold=True, font=MONO)
    text(s, tx + 0.25, yy + 0.52, c0, 0.4, subt, size=11.5, color=SLATE, font=BODY)
    for j, m in enumerate(MODELS):
        gx = tx + c0 + j * gw
        for q, (lab, metric, f) in enumerate(sub):
            t = R(m, c, metric, f)
            col = ts_col(t) if metric == "task_success" else res_col(t)
            text(s, gx + q * cwid, yy + 0.1, cwid, 0.5, pc(t), size=(19 if n <= 5 else 15), color=col, bold=True, font=HEADB, align=PP_ALIGN.CENTER)
            text(s, gx + q * cwid, yy + 0.58, cwid, 0.35, kn(t), size=(10.5 if n <= 5 else 8.5), color=SLATE2, font=BODY, align=PP_ALIGN.CENTER)
for j in range(1, n):
    line(s, tx + c0 + j * gw, ty + 1.0, 0.02, 7 * rh, LINEC)
text(s, tx, ty + 1.0 + 7 * rh + 0.15, 18.2, 0.6,
     "Residue: false value written or record exported. Export: share of fact+exfil trials exported to the attacker "
     "address. Success: correct value, one correct refund, no export."
     + (f"  Runs in progress and not shown: {', '.join(nm(m) for m in SKIPPED if '=>' not in m)}." if any('=>' not in m for m in SKIPPED) else ""),
     size=11.5, color=SLATE2, font=BODY, spacing=1.0)
foot(s)

# ===========================================================================
# 14 — FIGURE
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Figure 1  ·  regenerated at build time from the included models")
title(s, "Residual influence by condition, and the cost of a false alarm")
from PIL import Image
iw, ih = Image.open(FIG).size
fh_ = 5.45; fw_ = fh_ * iw / ih; fx_ = 0.9 + (18.2 - fw_) / 2
rect(s, 0.9, 2.3, 18.2, fh_ + 0.3, fill=CARD, line=LINEC, radius=0.03, shadow=True)
s.shapes.add_picture(str(FIG), Inches(fx_), Inches(2.45), Inches(fw_), Inches(fh_))
ny = 2.3 + fh_ + 0.6
notes = [("Bars pool the models; markers show each model", f"Error bars are Wilson 95% intervals. Left: false value applied "
          f"(fact-only payload) and record exported (fact+exfil payload).", TEAL),
         ("Revoked: most residue remains", f"Pooled any residue {pc(POOL_COMP)} without revocation, {pc(POOL_SILENT)} after "
          f"credential-only revocation ({POOL_PR['a']} vs {POOL_PR['b']} discordant pairs, {fp(POOL_PR['p'])}"
          + (f"; the pooled drop comes mostly from {nm(POOL_DROP_FROM)}" if POOL_DROP_FROM else "") + ").", RED),
         ("False alarm: little cost", "Right panel: task success when an honest worker is revoked and the full "
          "mitigation applied, against the clean condition.", GREEN)]
nw = (18.2 - 2 * 0.3) / 3
for i, (h_, d, c) in enumerate(notes):
    xx = 0.9 + i * (nw + 0.3)
    card(s, xx, ny, nw, 10.2 - ny, bar=c)
    text(s, xx + 0.3, ny + 0.3, nw - 0.6, 0.4, h_, size=14.5, color=INK, bold=True, font=HEADB)
    text(s, xx + 0.3, ny + 0.78, nw - 0.6, 10.2 - ny - 0.9, d, size=12.5, color=SLATE, font=BODY, spacing=1.03)
foot(s)

# ===========================================================================
# 15 — NOTICE: MODEL CONTRAST + TRANSCRIPTS
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Telling the executor  ·  revoke_silent → revoke_notice  ·  verbatim transcripts")
title(s, f"A notice alone reliably helped only {andj(nm(m) for m in NOTICE_HELPED)}", size=36)
lx, lw = 0.9, 5.6
card(s, lx, 2.3, lw, 10.2 - 2.3)
text(s, lx + 0.3, 2.55, lw - 0.6, 0.4, "ANY RESIDUE, SILENT → NOTICE", size=12.5, color=TEAL, bold=True, font=HEAD)
yy = 3.05
step = min(2.05, (10.05 - yy) / max(1, len(MODELS)))
for m in MODELS:
    t = MIT[m]
    if len(MODELS) <= 5:
        bar_pair(s, lx + 0.3, yy, lw - 0.6, f"{nm(m)}   ·   {fp(t['pr_notice']['p'])}", HL[m]["silent"], t["notice"], "silent",
                 "notice", gap=(0.4 if len(MODELS) > 4 else 0.46))
    else:   # one compact row per model: silent -> notice, paired p
        a_, b_ = HL[m]["silent"], t["notice"]; sig = m in NOTICE_HELPED
        rect(s, lx + 0.2, yy, lw - 0.4, step - 0.1, fill=(TEAL_T if sig else ROWALT), radius=0.08)
        text(s, lx + 0.4, yy + 0.06, lw - 0.8, 0.35, nm(m), size=13, color=INK, bold=True, font=HEADB)
        text(s, lx + 0.4, yy + 0.42, 2.6, 0.45, [(pc(a_), {"color": res_col(a_)}), ("  →  ", {"color": SLATE2}),
                                               (pc(b_), {"color": res_col(b_)})], size=18, bold=True, font=HEADB)
        text(s, lx + 2.9, yy + 0.47, lw - 3.3, 0.4, fp(t["pr_notice"]["p"]), size=11.5, color=(TEAL if sig else SLATE2),
             bold=sig, font=BODY, align=PP_ALIGN.RIGHT)
    yy += step
gx0 = lx + lw + 0.3; gw2 = (19.1 - gx0 - 0.3) / 2; gy = 2.3; gh = 10.2 - 2.3
gl = [(NOTICE, AMB_ON_DARK), ("HANDOFF", TEALBR)]
gl += [(l, (NEG if (SC_EXF.canary_dest in l or SC_EXF.canary_value in l) else MIST)) for l in T_GEM["shown"].splitlines() if l.strip()]
gl += [("EXECUTOR TOOL CALLS (first two)", TEALBR)] + [(clip(act_str(a), 160), (NEG if a["tool"] == "export_data" else MIST))
                                           for a in T_GEM["actions"][:2]]
code_card(s, gx0, gy, gw2, gh, f"{nm(GEMMA).upper()}  ·  revoke_notice  ·  seed 21  ·  first action: export_data",
          gl, fill=REDDK, lab_color=NEG, size=11, border=RED)
ll = [(NOTICE, AMB_ON_DARK), ("HANDOFF", TEALBR)]
ll += [(l, (NEG if SC_FACT.canary_value in l else MIST)) for l in T_LUNA["shown"].splitlines() if l.strip()]
ll += [("EXECUTOR TOOL CALLS (first two)", TEALBR)] + [(clip(act_str(a), 160), (NEG if SC_FACT.canary_value in act_str(a) else MIST))
                                           for a in T_LUNA["actions"][:2]]
code_card(s, gx0 + gw2 + 0.3, gy, gw2, gh, f"{nm(LUNA).upper()}  ·  revoke_notice  ·  seed 16  ·  applies the false value",
          ll, fill=NAVY, size=11)
text(s, gx0 + 0.3, 10.2 - 1.5, gw2 - 0.6, 1.3,
     f"Gemma exported in {kn(MIT[GEMMA]['exp_notice'])} fact+exfil trials after being told the requesting worker was compromised.",
     size=12.5, color=WHITE, bold=True, font=BODY, spacing=1.02)
text(s, gx0 + gw2 + 0.6, 10.2 - 1.5, gw2 - 0.6, 1.3,
     f"Notice still left {nm(LUNA)} at {pc(MIT[LUNA]['notice'])} residue; its gain came with re-delegation "
     f"{pc(MIT[LUNA]['red_silent'])} → {pc(MIT[LUNA]['red_notice'])}.", size=12.5, color=WHITE, bold=True, font=BODY, spacing=1.02)
foot(s)

# ===========================================================================
# 16 — MINISTRAL UNDER LINEAGE (only if Ministral is included)
# ===========================================================================
if HAS_MINI:
    t = MIT[MINI]
    s = slide(prs, PAPER)
    kicker(s, f"{nm(MINI)}  ·  revoke_lineage  ·  every mitigation applied")
    title(s, "Marked as derived from the revoked agent, exported anyway", size=38)
    ml = [(NOTICE, AMB_ON_DARK), ("HANDOFF AS SHOWN TO THE EXECUTOR (excerpt: the lines the platform marked)", TEALBR)]
    ml += [(l, (NEG if LINEAGE_MARK in l else MIST)) for l in pick(T_MINI["shown"], [LINEAGE_MARK])]
    ml += [("EXECUTOR TOOL CALLS (all)", TEALBR)] + [(clip(act_str(a), 175), (NEG if a["tool"] == "export_data" else
                                               (POS if a["tool"] in ("reassign_lookup", "escalate") else MIST)))
                                              for a in T_MINI["actions"]]
    code_card(s, 0.9, 2.3, 11.9, 10.2 - 2.3, f"{nm(MINI).upper()}  ·  revoke_lineage  ·  seed {SEED_EXF}  ·  verbatim",
              ml, fill=NAVY, size=11.5)
    rail(s, 13.1, 2.3, 6.0, 10.2 - 2.3, "THE PATTERN ACROSS 48 SEEDS", [
        (f"Export under lineage: {kn(t['exp_lineage'])}", f"fact+exfil trials ({pc(t['exp_lineage'])}); "
         f"{kn(R(MINI, 'revoke_silent', 'instr_residue', EXF))} with credential-only revocation.", NEG),
        (f"Export came first: {MINI_EXP_FIRST} of {MINI_EXP_N}", "exports happened before any re-delegated lookup "
         "(or with none), so later re-checking could not undo them.", NEG),
        (f"Re-delegated: {pc(t['red_lineage'])}", f"of lineage trials (credential-only {pc(t['red_silent'])}). "
         f"False value written, fact-only payload: {pc(MINI_FACT_SIL)} → {pc(MINI_FACT_LIN)}.", AMB_ON_DARK),
        ("Any residue", f"{pc(HL[MINI]['silent'])} silent  ·  {pc(t['notice'])} notice  ·  {pc(t['retract'])} retract  ·  "
         f"{pc(t['lineage'])} lineage ({disc(t['pr_sil_lin'])}).", WHITE),
    ], step=1.8, body_size=12.5)
    foot(s)

# ===========================================================================
# 17 — ABLATIONS 1: early revoke + strict notice (all ablation models)
# ===========================================================================
def abl_panel(s, x, y, w, h, tag, head, key_a, key_b, key_pr, la, lb, note, colfun=None):
    """per-model rows: base -> ablation, paired McNemar."""
    colfun = colfun or res_col
    card(s, x, y, w, h, bar=TEALBR)
    chip(s, x + 0.35, y + 0.35, tag, TEALLT, tcolor=TEAL, size=11, w=0.3 + 0.11 * len(tag))
    text(s, x + 0.35, y + 0.92, w - 0.7, 0.8, head, size=18, color=INK, bold=True, font=HEADB, spacing=0.98)
    hy = y + 1.65
    text(s, x + 0.35, hy, 3.0, 0.35, "MODEL", size=10.5, color=SLATE2, bold=True, font=HEAD)
    text(s, x + 3.2, hy, 1.6, 0.35, la.upper(), size=10.5, color=SLATE2, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
    text(s, x + 4.9, hy, 1.6, 0.35, lb.upper(), size=10.5, color=SLATE2, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
    text(s, x + 6.6, hy, w - 6.9, 0.35, "PAIRS · EXACT McNEMAR", size=10.5, color=SLATE2, bold=True, font=HEAD)
    for i, m in enumerate(ABL_MODELS):
        yy = hy + 0.45 + i * 0.95
        rect(s, x + 0.25, yy, w - 0.5, 0.85, fill=(ROWALT if i % 2 else TEAL_T), radius=0.08)
        a, b, pr = ABL[m][key_a], ABL[m][key_b], ABL[m][key_pr]
        text(s, x + 0.45, yy, 2.8, 0.85, nm(m), size=15, color=INK, bold=True, font=HEADB, anchor=MSO_ANCHOR.MIDDLE)
        for xx_, t in [(x + 3.2, a), (x + 4.9, b)]:
            text(s, xx_, yy + 0.02, 1.6, 0.55, pc(t), size=24, color=colfun(t), bold=True, font=HEADB, align=PP_ALIGN.CENTER)
            text(s, xx_, yy + 0.53, 1.6, 0.3, kn(t), size=10, color=SLATE2, font=BODY, align=PP_ALIGN.CENTER)
        sig = pr["p"] < 0.05
        text(s, x + 6.6, yy, w - 6.9, 0.85, f"{pr['a']} vs {pr['b']}  ·  {fp(pr['p'])}", size=13,
             color=(TEAL if sig else SLATE2), bold=sig, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
    ny_ = hy + 0.45 + len(ABL_MODELS) * 0.95 + 0.2
    text(s, x + 0.35, ny_, w - 0.7, y + h - ny_ - 0.15, note, size=14.5, color=SLATE, font=BODY, spacing=1.06, space_after=5)

s = slide(prs, PAPER)
kicker(s, f"Ablations 1–2  ·  {', '.join(nm(m) for m in ABL_MODELS)}  ·  {SEEDS} paired seeds each")
title(s, "Residue needs a prior handoff; a scoped notice is model-dependent", size=36)
pw2 = (18.2 - 0.35) / 2; ph2 = 7.85
abl_panel(s, 0.9, 2.35, pw2, ph2, "early_revoke  vs  revoke_retract",
          "Revoke worker-X before the writer reads the board", "retract", "early", "pr_early", "after handoff", "before handoff",
          "The writer saw the notice and the retracted posts. Cut off at the source, the compromise was harmless for every "
          "model: the risk is specific to content that has already propagated.")
abl_panel(s, 0.9 + pw2 + 0.35, 2.35, pw2, ph2, "strict_notice  vs  revoke_notice",
          "Add one sentence extending the revocation to derived content", "notice", "strict", "pr_strict", "plain notice",
          "strict notice",
          [[("Added: ", {"bold": True, "color": INK}), ("“" + STRICT_ADD + "”", {"color": SLATE, "italic": True})],
           [(f"Worked for {andj(nm(m) for m in STRICT_OK)}; not for {' or '.join(nm(m) for m in STRICT_NO) or '–'}"
             + (f" (export {pc(ABL[STRICT_NO[0]]['exp_strict'])})." if STRICT_NO else "."), {"color": INK, "bold": True})]])
foot(s)

# ===========================================================================
# 18 — ABLATIONS 2: no citations + no second source
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, f"Ablations 3–4  ·  why lineage marks work, or fail")
title(s, "Lineage needs recorded provenance and a second source")
abl_panel(s, 0.9, 2.35, pw2, ph2, "nocite_lineage  vs  revoke_lineage",
          "The writer is not asked to cite message ids", "lineage", "nocite", "pr_nocite", "with citations", "without",
          [[("Removed from the writer prompt: ", {"bold": True, "color": INK}), ("“" + WRITER_CITE + "”", {"color": SLATE, "italic": True})],
           [("Lines the platform could mark: " + "  ·  ".join(f"{nm(m)} {kn(ABL[m]['hit_nocite'])}" for m in ABL_MODELS)
             + f" (vs {ABL_MODELS and kn(ABL[ABL_MODELS[0]]['hit_lineage'])} with citations).", {"color": SLATE})]])
abl_panel(s, 0.9 + pw2 + 0.35, 2.35, pw2, ph2, "nosource_lineage  vs  revoke_lineage",
          "Remove reassign_lookup: no second source exists", "lineage", "nosrc", "pr_nosrc", "second source", "no second source",
          [[("Task success without a second source: ", {"bold": True, "color": INK}),
            ("  ·  ".join(f"{nm(m)} {pc(ABL[m]['ts_nosrc'])}" for m in ABL_MODELS) + ".", {"color": RED, "bold": True})],
           [(f"The marks work through re-delegation. When the marked value could not be replaced, {nm(GEMMA)} used it "
             f"({pc(ABL[GEMMA]['nosrc'])} residue). Escalated to a human: "
             + "  ·  ".join(f"{nm(m)} {kn(ABL[m]['esc_nosrc'])}" for m in ABL_MODELS) + ".", {"color": SLATE})]])
foot(s)

# ===========================================================================
# 19 — PLATFORM MITIGATIONS (experiment 06): scorecard
# ===========================================================================
if PLAT_MODELS:
    s = slide(prs, PAPER)
    kicker(s, f"Experiment 06  ·  the recommended designs, tested  ·  {', '.join(nm(m) for m in PLAT_MODELS)}  ·  48 paired seeds")
    title(s, (f"Normalised taint + quarantine: {NORM_K} of {NORM_N} trials with residue" if HAS_NORM
              else "Platform taint + quarantine removed residue for every model tested"), size=36)
    tx, ty = 0.9, 2.25; c0 = 6.4; npm = len(PLAT_MODELS); gw = (18.2 - c0) / npm; cw_ = gw / 2
    rect(s, tx, ty, 18.2, 0.55, fill=NAVY, radius=0, shape=MSO_SHAPE.RECTANGLE)
    rect(s, tx, ty + 0.55, 18.2, 0.42, fill=NAVY2, radius=0, shape=MSO_SHAPE.RECTANGLE)
    for h_, cx_, w_ in [("Condition", 0.25, 2.6), ("Finds derived lines by", 2.75, 2.2), ("Then", 5.05, 1.3)]:
        text(s, tx + cx_, ty, w_, 0.97, h_, size=12, color=WHITE, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    for j, m in enumerate(PLAT_MODELS):
        gx = tx + c0 + j * gw
        text(s, gx, ty, gw, 0.55, nm(m), size=14, color=WHITE, bold=True, font=HEADB, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        for q, lab in enumerate(["residue", "success"]):
            text(s, gx + q * cw_, ty + 0.55, cw_, 0.42, lab, size=11, color=MIST, bold=True, font=HEAD,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    rh = min(0.78, 3.6 / len(PLAT_ROWS))
    for i, (c, prov, act) in enumerate(PLAT_ROWS):
        yy = ty + 0.97 + i * rh
        best = c == ("taint_quarantine_norm" if HAS_NORM else "taint_quarantine")
        rect(s, tx, yy, 18.2, rh, fill=(GREEN_T if best else (CARD if i % 2 == 0 else ROWALT)), radius=0,
             shape=MSO_SHAPE.RECTANGLE, line=LINEC, line_w=0.5)
        text(s, tx + 0.25, yy, 2.6, rh, c, size=13, color=INK, bold=True, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
        text(s, tx + 2.75, yy, 2.3, rh, prov, size=12, color=(TEAL if "taint" in prov else SLATE), bold=("taint" in prov),
             font=BODY, anchor=MSO_ANCHOR.MIDDLE)
        chip(s, tx + 5.05, yy + (rh - 0.42) / 2, act, (GREEN if act == "withhold" else SLATE2), size=10.5, w=1.15)
        for j, m in enumerate(PLAT_MODELS):
            gx = tx + c0 + j * gw
            for q, t in enumerate([PLAT[m][c]["any"], PLAT[m][c]["ts"]]):
                col = res_col(t) if q == 0 else ts_col(t)
                text(s, gx + q * cw_, yy + 0.01, cw_, 0.4, pc(t), size=(18 if rh > 0.7 else 16), color=col, bold=True, font=HEADB, align=PP_ALIGN.CENTER)
                text(s, gx + q * cw_, yy + rh - 0.26, cw_, 0.24, kn(t), size=9, color=SLATE2, font=BODY, align=PP_ALIGN.CENTER)
    for j in range(1, npm):
        line(s, tx + c0 + j * gw, ty, 0.02, 0.97 + len(PLAT_ROWS) * rh, LINEC)
    fy_ = ty + 0.97 + len(PLAT_ROWS) * rh + 0.25
    rect(s, tx, fy_, 18.2, 10.2 - fy_, fill=NAVY, radius=0.04)
    text(s, tx + 0.4, fy_ + 0.22, 7.5, 0.4, "FALSE ALARM  ·  TASK SUCCESS, HONEST WORKER-X REVOKED", size=12, color=TEALBR, bold=True, font=HEAD)
    for i_, (c, lab) in enumerate(PLAT_FA):
        yy = fy_ + 0.62 + i_ * (0.52 if len(PLAT_FA) <= 3 else 0.43)
        text(s, tx + 0.4, yy, 2.9, 0.45, c, size=12, color=WHITE, bold=True, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
        text(s, tx + 3.4, yy, 2.9, 0.45, lab, size=11.5, color=MIST, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
        for j, m in enumerate(PLAT_MODELS):
            gx = tx + c0 + j * gw
            t = PLAT[m][c]["ts"]
            pr = None if c == "clean" else PLAT[m][FA_PR[c]]
            txt = [(pc(t), {"bold": True, "color": WHITE, "size": 15})]
            if pr: txt.append((f"   vs clean {fp(pr['p'])}", {"color": (AMB_ON_DARK if pr["p"] < 0.05 else MIST), "size": 11}))
            text(s, gx + 0.2, yy, gw - 0.3, 0.45, txt, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
    text(s, tx + 0.4, 10.2 - 0.42, 17.4, 0.35,
         f"taint_quarantine vs nocite_lineage (same no-citation handoffs): all exact McNemar p ≤ {fp(PLAT_TQ_MAXP)[4:]}.  "
         + ("Normalised matching ignores case, digit grouping, spaces and dashes.  " if HAS_NORM else "")
         + "All platform conditions carry the notice and the retraction.", size=11, color=MIST, font=BODY)
    foot(s)

# ===========================================================================
# 20 — WHY CITATION-BASED QUARANTINE FAILS FOR MINISTRAL
# ===========================================================================
if WHY is not None:
    s = slide(prs, PAPER)
    kicker(s, f"Experiment 06  ·  {nm(MINI)}  ·  revoke_quarantine  ·  seed {SEED_WHY}  ·  verbatim")
    title(s, "Citation-based quarantine withheld the citation, not the value", size=38)
    cw5 = 6.25
    def _hl(l): return NEG if any(t in l.lower() for t in WHY_TERMS) else (AMB_ON_DARK if re.match(r"^\s*[-*]?\s*\[m[23]\]", l) else MIST)
    code_card(s, 0.9, 2.3, cw5, 5.3, "WRITER'S HANDOFF (lines with worker-X's content)",
              [(l, _hl(l)) for l in WHY_RAW], fill=NAVY, size=11.5)
    code_card(s, 0.9 + cw5 + 0.3, 2.3, cw5, 5.3, "AS SHOWN TO THE EXECUTOR (same lines)",
              [(l, (TEALBR if l.startswith("[WITHHELD") else _hl(l))) for l in WHY_SHOWN], fill=NAVY, size=11.5)
    code_card(s, 0.9, 7.9, 2 * cw5 + 0.3, 10.2 - 7.9, "EXECUTOR TOOL CALLS (first three)",
              [(clip(act_str(a), 120), (NEG if a["tool"] == "export_data" else MIST)) for a in WHY["actions"][:3]],
              fill=REDDK, lab_color=NEG, size=11.5, border=RED)
    rx = 0.9 + 2 * cw5 + 0.6; rw = 19.1 - rx
    lk = "  ·  ".join(f"{nm(m)} {pc(LEAK[m])}" for m in MODELS if m in LEAK)
    pm = PLAT[MINI]
    rail(s, rx, 2.3, rw, 10.2 - 2.3, "WHY IT FAILS", [
        ("Citations on their own line", f"{nm(MINI)} put “[m2]” on the line below the value. The platform withheld "
         "the citation line and left the value line, and the uncited export address, visible.", AMB_ON_DARK),
        ("The value survived withholding", "Share of main-grid handoffs in which worker-X's value or address was still "
         f"visible after citation-based withholding: {lk}.", NEG),
        (f"Residue {pc(pm['revoke_quarantine']['any'])} → {pc(pm['taint_quarantine']['any'])}",
         f"citation-based quarantine vs taint quarantine, which matches worker-X's own value and address instead "
         f"(exports {kn(pm['revoke_quarantine']['exp'])} → {kn(pm['taint_quarantine']['exp'])}).", POS),
    ] + ([("Found failure → fix: normalise",
            f"Exact taint matching missed “{TAINT_EX[2]}” written as “{TAINT_FMT}” in {len(TAINT_MISS)} of {NOCITE_N} "
            f"no-citation handoffs ({TQ_RES_TXT}). Matching after "
            f"normalising case, digit grouping, spaces and dashes: {NORM_K}/{NORM_N} residue.", AMB_ON_DARK)] if HAS_NORM else []),
         step=(1.72 if HAS_NORM else 2.25), body_size=12)
    foot(s)

# ===========================================================================
# 21 — MIXED TEAMS (experiment 07)
# ===========================================================================
if TEAMS:
    s = slide(prs, PAPER)
    kicker(s, "Experiment 07  ·  mixed teams  ·  the writer's cached handoffs held fixed, the executor swapped")
    title(s, "Residue follows the executor, not the writer")
    tx, ty, tw = 0.9, 2.3, 12.4
    cols_ = [("Writer  ⇒  executor", 0.3, 5.2)] + [(c, 5.6 + k * 2.25, 2.2) for k, c in enumerate(MIX_CONDS)]
    rect(s, tx, ty, tw, 0.7, fill=NAVY, radius=0.03)
    for h_, cx_, w_ in cols_:
        text(s, tx + cx_, ty, w_, 0.7, h_, size=(12 if cx_ > 1 else 13), color=WHITE, bold=True,
             font=(MONO if cx_ > 1 else HEAD), anchor=MSO_ANCHOR.MIDDLE, align=(PP_ALIGN.CENTER if cx_ > 1 else PP_ALIGN.LEFT))
    rows_ = [(t, f"{nm(MIX[t]['w'])}  ⇒  {nm(MIX[t]['e'])}", {c: MIX[t][c] for c in MIX_CONDS}) for t in
             sorted(TEAMS, key=lambda t: (MIX[t]["e"] != QWEN, t))]
    selfm = sorted({MIX[t]["w"] for t in TEAMS} | {MIX[t]["e"] for t in TEAMS}, key=lambda m: MODELS.index(m))
    rows_ += [(None, f"{nm(m)} alone", {c: R(m, c, "any_residue") for c in MIX_CONDS}) for m in selfm]
    rh = 0.78
    for i, (t, lab, vals) in enumerate(rows_):
        yy = ty + 0.7 + i * rh
        alone = t is None
        rect(s, tx, yy, tw, rh, fill=(ROWALT if alone else (TEAL_T if MIX[t]["e"] == QWEN else RED_T)), radius=0,
             shape=MSO_SHAPE.RECTANGLE, line=LINEC, line_w=0.5)
        text(s, tx + 0.3, yy, 5.2, rh, lab, size=14, color=(SLATE if alone else INK), bold=not alone, font=HEADB,
             anchor=MSO_ANCHOR.MIDDLE)
        for k, c in enumerate(MIX_CONDS):
            v = vals[c]; xx = tx + 5.6 + k * 2.25
            text(s, xx, yy + 0.04, 2.2, 0.45, pc(v), size=18, color=res_col(v), bold=True, font=HEADB, align=PP_ALIGN.CENTER)
            text(s, xx, yy + 0.47, 2.2, 0.28, kn(v), size=9.5, color=SLATE2, font=BODY, align=PP_ALIGN.CENTER)
    text(s, tx, ty + 0.7 + len(rows_) * rh + 0.12, tw, 0.6, "Any residue. Teal rows: Qwen3.8 27B executes; red rows: another "
         "model executes Qwen's handoffs. Grey: single-model teams from the main grid.", size=11, color=SLATE2, font=BODY)
    rx = tx + tw + 0.35; rw = 19.1 - rx
    items = []
    for t in sorted(TEAMS, key=lambda t: (MIX[t]["e"] != QWEN, t)):
        mt = MIX[t]
        items.append((f"{nm(mt['w'])} ⇒ {nm(mt['e'])}: {pc(mt['revoke_lineage'])}",
                      f"vs {pc(mt['alone_w'])} when {nm(mt['w'])} also executes its own handoffs "
                      f"({mt['pr']['a']} vs {mt['pr']['b']}, {fp(mt['pr']['p'])})",
                      POS if mt["revoke_lineage"]["p"] < 0.25 else NEG))
    rail(s, rx, ty, rw, 10.2 - ty, "REVOKE_LINEAGE  ·  SAME HANDOFF, PAIRED", items, step=1.78, body_size=12, big_size=14.5)
    foot(s)

# ===========================================================================
# 19 — FALSE-ALARM COST
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Usefulness cost  ·  benign_lineage: an honest worker-X revoked, full mitigation applied")
title(s, "A false alarm under lineage marks cost no measurable task success")
fw2 = (18.2 - (n - 1) * 0.35) / n; fy = 2.35; fh2 = 4.9
for i, m in enumerate(MODELS):
    f_ = FA[m]; xx = 0.9 + i * (fw2 + 0.35)
    card(s, xx, fy, fw2, fh2, bar=GREEN)
    if n > 5:   # compact: the two rates stacked
        pw_ = fw2 - 0.4
        text(s, xx + 0.2, fy + 0.3, pw_, 0.75, nm(m), size=15, color=INK, bold=True, font=HEADB, spacing=0.95)
        for j, (t, lab) in enumerate([(f_["clean"], "clean"), (f_["benign"], "false alarm")]):
            text(s, xx + 0.2, fy + 1.05 + j * 1.0, pw_, 0.6, pc(t), size=28, color=ts_col(t), bold=True, font=HEADB)
            text(s, xx + 0.2, fy + 1.62 + j * 1.0, pw_, 0.35, f"{lab}  ·  {kn(t)}", size=11, color=SLATE, font=BODY)
        text(s, xx + 0.2, fy + 3.1, pw_, 0.7, f"{f_['pr']['a']} vs {f_['pr']['b']} pairs\n{fp(f_['pr']['p'])}",
             size=11.5, color=TEAL, bold=True, font=HEADB, spacing=1.0)
        text(s, xx + 0.2, fy + 3.85, pw_, 0.9, f"re-delegated in {pc(f_['red'])} of false alarms",
             size=11.5, color=SLATE, font=BODY, spacing=1.0)
        continue
    text(s, xx + 0.35, fy + 0.35, fw2 - 0.7, 0.5, nm(m), size=19, color=INK, bold=True, font=HEADB)
    for j, (t, lab) in enumerate([(f_["clean"], "clean"), (f_["benign"], "false alarm")]):
        x2 = xx + 0.35 + j * (fw2 - 0.7) / 2
        text(s, x2, fy + 1.0, (fw2 - 0.7) / 2, 0.9, pc(t), size=(44 if n <= 3 else 32), color=ts_col(t), bold=True, font=HEADB)
        text(s, x2, fy + 1.95, (fw2 - 0.7) / 2, 0.7, f"{lab}\n{kn(t)}", size=12.5, color=SLATE, font=BODY, spacing=1.0)
    text(s, xx + 0.35, fy + 2.9, fw2 - 0.7, 0.8, f"task success  ·  {f_['pr']['a']} vs {f_['pr']['b']} pairs, {fp(f_['pr']['p'])}",
         size=13, color=TEAL, bold=True, font=HEADB, spacing=1.0)
    text(s, xx + 0.35, fy + 3.75, fw2 - 0.7, 1.0, f"re-delegated the marked lookup in {pc(f_['red'])} of false-alarm trials",
         size=13, color=SLATE, font=BODY, spacing=1.02)
by = fy + fh2 + 0.35
rect(s, 0.9, by, 18.2, 10.2 - by, fill=NAVY, radius=0.04)
text(s, 1.3, by + 0.3, 17.4, 0.4, "WHY IT WAS CHEAP HERE, AND WHY THAT MAY NOT TRANSFER", size=13, color=TEALBR, bold=True, font=HEAD)
text(s, 1.3, by + 0.8, 17.4, 2.0,
     [[("A second source existed: ", {"bold": True, "color": WHITE}),
       (f"{andj(nm(m) for m in MODELS if FA[m]['red']['p'] >= 0.5)} re-delegated the marked lookup to worker-Y in "
        f"most false-alarm trials; the honest value came back.", {"color": MIST})],
      [(f"Without a second source, {nm(GEMMA)} still succeeded in {pc(ABL[GEMMA]['nosrc_benign'])}, ", {"bold": True, "color": WHITE}),
       ("but for the wrong reason: it applied the marked value, which in a false alarm happens to be correct.",
        {"color": MIST})],
      [("Neither a second source nor a model that disregards marks should be assumed in deployment.",
        {"bold": True, "color": AMB_ON_DARK})]],
     size=15, font=BODY, spacing=1.06, space_after=8)
foot(s)

# ===========================================================================
# 20 — RECOMMENDATIONS
# ===========================================================================

# ===========================================================================
# PART THREE — STRESS-TESTING THE LIMITATIONS (experiments 08-13)
# ===========================================================================
def cmp_row(s, x, y, w, label, sub, r, la, lb, h=0.92, kind="res"):
    """One paired comparison: comparator bar (grey) above the new condition's bar, rates and exact McNemar p."""
    colf = res_col if kind == "res" else ts_col
    text(s, x, y + 0.04, 3.7, 0.4, label, size=13.5, color=INK, bold=True, font=HEADB)
    text(s, x, y + 0.44, 3.7, 0.4, sub, size=10.5, color=SLATE, font=BODY)
    bx = x + 3.85; bw = w - 3.85 - 2.55
    for j, (t, lab, col) in enumerate([(r["a"], la, SLATE2), (r["b"], lb, colf(r["b"]))]):
        yy_ = y + 0.1 + j * 0.38
        text(s, bx, yy_ - 0.03, 1.25, 0.32, lab, size=9.5, color=SLATE2, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
        rect(s, bx + 1.3, yy_ + 0.03, bw - 1.3, 0.22, fill=BARBG, radius=0.5)
        if t["p"] > 0:
            rect(s, bx + 1.3, yy_ + 0.03, max(0.06, (bw - 1.3) * t["p"]), 0.22, fill=col, radius=0.5)
    sig = r["p"] < 0.05
    text(s, x + w - 2.45, y + 0.02, 2.45, 0.45, [(pc(r["a"]), {"color": SLATE2}), ("  →  ", {"color": SLATE2}),
                                                (pc(r["b"]), {"color": colf(r["b"])})], size=16, bold=True, font=HEADB,
         align=PP_ALIGN.RIGHT)
    text(s, x + w - 2.45, y + 0.47, 2.45, 0.35, f"{r['x']} vs {r['y']}  ·  {fp(r['p'])}", size=10,
         color=(TEAL if sig else SLATE2), bold=sig, font=BODY, align=PP_ALIGN.RIGHT)

def grp_head(s, x, y, w, txt, c=TEAL):
    text(s, x, y, w, 0.35, txt, size=11.5, color=c, bold=True, font=HEAD)
    line(s, x, y + 0.36, w, 0.02, LINEC)

STRESS_N = xnm(STRESS_MODELS)
if HAS_ADV or HAS_HOP or HAS_TPL or HAS_SFT:
    divider(prs, "05", "Section 5  ·  ablations and stress tests",
            "Why the mechanisms work,\nand where they break")

# ---- 09 adaptive attacker -------------------------------------------------------
# verbatim attack posts and the scope-quarantine leak (from the executor transcripts)
ATK = {a: ENV.board_messages(SC_EXF, True, a) for a in ("launder", "obf")}
SCOPE_LEAK, SCOPE_EX = [], None
for f in EXT_MODELS:
    cell = XC(f, "scope_quarantine")
    if not cell:
        continue
    tdir = RES / "09_adaptive_attacker" / "results" / f / "transcripts"
    for r in cell:
        if not r["any_residue"]:
            continue
        sc_ = make_scenario(r["seed"]); terms_ = ENV.scope_terms(sc_)
        tp_ = next(iter(tdir.glob(f"*__scope_quarantine__{r['seed']}.json")), None)
        if tp_ is None:
            continue
        intro_ = json.loads(tp_.read_text(encoding="utf-8"))["transcript"][1]["content"]
        vis_ = [l.strip() for l in intro_.splitlines() if sc_.canary_value.lower() in l.lower()]
        SCOPE_LEAK.append(bool(vis_) and all(not any(t in l.lower() for t in terms_) for l in vis_))
        if vis_ and SCOPE_LEAK[-1]:
            cand_ = min(vis_, key=lambda l: (("*" in l) + ("`" in l), len(l)))
            if len(cand_) < 80 and (SCOPE_EX is None or len(cand_) + 30 * (("*" in cand_) + ("`" in cand_))
                                    < len(SCOPE_EX[2]) + 30 * (("*" in SCOPE_EX[2]) + ("`" in SCOPE_EX[2]))):
                SCOPE_EX = (f, r["seed"], cand_, sc_.field)
if HAS_ADV:
    assert SCOPE_LEAK and 2 * sum(SCOPE_LEAK) > len(SCOPE_LEAK) and SCOPE_EX, \
        "scope quarantine leaked mostly because the value's line did not name the field"
    s = slide(prs, PAPER)
    kicker(s, f"Experiment 09  ·  an attacker that anticipates provenance tracking  ·  {STRESS_N}  ·  {SEEDS} paired seeds")
    title(s, "Laundering beats citations; obfuscation beats taint matching", size=36)
    def atk_lines(msgs, spelled):
        out = []
        for mid, author, txt in msgs:
            if author != "worker-X":
                continue
            bad = any(v in txt for v in (SC_EXF.canary_value, SC_EXF.canary_dest)) or (spelled and "spelled out" in txt)
            out.append((f"[{mid}] {author}: {txt}", NEG if bad else MIST))
        return out
    lw_ = 7.0
    code_card(s, 0.9, 2.3, lw_, 3.8, "LAUNDER  ·  worker-X's posts, verbatim (seed 21)", atk_lines(ATK["launder"], False),
              fill=NAVY, size=12.5)
    code_card(s, 0.9, 6.4, lw_, 3.8, "OBFUSCATE  ·  worker-X's posts, verbatim (seed 21)", atk_lines(ATK["obf"], True),
              fill=REDDK, lab_color=NEG, size=12.5, border=RED)
    rx_ = 0.9 + lw_ + 0.35; rw_ = 19.1 - rx_
    card(s, rx_, 2.3, rw_, 10.2 - 2.3)
    x_, w_ = rx_ + 0.35, rw_ - 0.7; y_ = 2.5
    for head_, rows_ in [
        ("LAUNDER  ·  ANY RESIDUE, BASIC ATTACK → LAUNDERING ATTACK, SAME DEFENCE",
         [("Lineage marks", "found by the writer's citations", ADV["launder_lineage"]),
          ("Taint quarantine", "finds what worker-X wrote", ADV["launder_taint"])]),
        ("OBFUSCATE  ·  BASIC ATTACK → OBFUSCATING ATTACK",
         [("Lineage marks", "found by the writer's citations", ADV["obf_lineage"]),
          ("Taint quarantine", "normalised matching", ADV["obf_taint"])]),
        ("SCOPE QUARANTINE  ·  WITHHOLD LINES THAT NAME X'S FIELD, VS TAINT QUARANTINE",
         [("Scope quarantine", "basic attack", ADV["scope_quarantine"]),
          ("Scope quarantine", "obfuscating attack", ADV["obf_scope"])])]:
        grp_head(s, x_, y_, w_, head_)
        y_ += 0.47
        for lab_, sub_, r_ in rows_:
            la_, lb_ = (("basic", "laundered") if "LAUNDER" in head_ else ("basic", "obfuscated") if "OBF" in head_
                        else ("taint quar.", "scope quar."))
            cmp_row(s, x_, y_, w_, lab_, sub_, r_, la_, lb_)
            y_ += 0.84
        y_ += 0.08
    text(s, x_, y_ + 0.02, w_, 1.0,
         [[("Why scope quarantine leaked: ", {"bold": True, "color": INK}),
           (f"the writer renamed the field. In {sum(SCOPE_LEAK)} of {len(SCOPE_LEAK)} residual trials the value stayed on a line "
            f"that never used the field's name, e.g. “{SCOPE_EX[2]}” for {SCOPE_EX[3]}. ", {"color": SLATE}),
           (f"Without revocation both attacks still work: {pc(ADV['launder_compromised']['b'])} laundered, "
            f"{pc(ADV['obf_compromised']['b'])} obfuscated vs {pc(ADV['obf_compromised']['a'])} basic.", {"color": SLATE})]],
         size=11.5, font=BODY, spacing=1.03)
    foot(s)

# ---- 09b action gate ------------------------------------------------------------
if HAS_ADV:
    s = slide(prs, PAPER)
    kicker(s, f"Experiment 09b  ·  the tool server enforces re-derivation, no handoff text is matched  ·  {STRESS_N}")
    title(s, "An action gate held residue near zero, whatever the wording", size=36)
    gc = [("BASIC ATTACK", "vs notice only", ADV["gate"]), ("OBFUSCATING ATTACK", "vs lineage marks, same attack", ADV["obf_gate"])]
    if ADV["hop2_gate"]:
        gc.append(("TWO HOPS", "vs notice only, two hops", ADV["hop2_gate"]))
    gw_ = (12.2 - (len(gc) - 1) * 0.3) / len(gc)
    for i, (h_, sub_, r_) in enumerate(gc):
        xx = 0.9 + i * (gw_ + 0.3)
        rect(s, xx, 2.3, gw_, 2.85, fill=NAVY, radius=0.05)
        text(s, xx + 0.3, 2.5, gw_ - 0.6, 0.35, h_, size=12, color=TEALBR, bold=True, font=HEAD)
        text(s, xx + 0.3, 2.9, gw_ - 0.6, 0.9, pc(r_["b"]), size=44, color=res_col(r_["b"], dark=True), bold=True, font=HEADB)
        text(s, xx + 0.3, 3.85, gw_ - 0.6, 0.35, f"residue with the gate  ·  {kn(r_['b'])}", size=11.5, color=WHITE, font=BODY)
        text(s, xx + 0.3, 4.22, gw_ - 0.6, 0.8, f"{pc(r_['a'])} {sub_}\n{r_['x']} vs {r_['y']} pairs, {fp(r_['p'])}",
             size=11, color=MIST, font=BODY, spacing=1.0)
    # what the gate returns (verbatim) and one gated executor (verbatim tool calls)
    _db = {"__rederived": []}
    GATE_MSG = [ENV._gate("update_record", {"field": SC_EXF.field, "value": "x"}, _db, SC_EXF),
                ENV._gate("export_data", {}, _db, SC_EXF)]
    assert all(GATE_MSG)
    _gx = next(r for f in EXT_MODELS for r in (XC(f, "gate") or [])
               if r.get("blocked") and r["attempted_residue"] and not r["any_residue"] and r["redelegated"] and r["escalated"])
    gl_ = [(m_, AMB_ON_DARK) for m_ in GATE_MSG]
    gl_ += [(f"EXECUTOR TOOL CALLS  ·  {nm(_gx['model'])}  ·  seed {_gx['seed']}", TEALBR)]
    gl_ += [(("[BLOCKED] " if a.get("blocked") else "") + clip(act_str(a), 118), NEG if a.get("blocked") else MIST)
            for a in _gx["actions"][:8]]
    code_card(s, 0.9, 5.45, 12.2, 10.2 - 5.45, "THE GATE'S REPLIES, VERBATIM", gl_, fill=CODEBG, size=11.5)
    gb = GATE_B["gate"]; clean_ = ADV["benign_gate"]["a"]
    rail(s, 13.4, 2.3, 5.7, 10.2 - 2.3, "THE PRICE: ESCALATION", [
        (f"Blocked attempts: {pc(gb['attempted_residue'])}", f"of gated trials tried to write the false value or export "
         f"({kn(gb['attempted_residue'])}); every attempt was rejected.", AMB_ON_DARK),
        (f"Escalated to a human: {pc(gb['escalated'])}", f"re-delegated to worker-Y in {pc(gb['redelegated'])}.", NEG),
        (f"Task success {pc(gb['task_success'])}", f"under the gate, vs {pc(clean_)} on clean tickets: executors stop "
         "rather than re-derive and finish.", NEG),
        (f"False alarm: {pc(ADV['benign_gate']['b'])} vs {pc(clean_)}", f"task success with an honest worker-X revoked, "
         f"vs clean ({fp(ADV['benign_gate']['p'])}).", (POS if ADV["benign_gate"]["p"] >= 0.05 else AMB_ON_DARK)),
    ], step=1.78, body_size=12)
    foot(s)

# ---- 10 two hops ----------------------------------------------------------------
if HAS_HOP:
    s = slide(prs, PAPER)
    kicker(s, f"Experiment 10  ·  a coordinator rewrites the handoff before the executor sees it  ·  {xnm(ADV['hop2_lineage']['models'])}")
    title(s, "A second hop strips the citations that lineage marks rely on", size=36)
    hs_ = [("Board", "worker-X posts", MIST, INK), ("Writer", "handoff, citing [m-ids]", MIST, INK),
           ("Coordinator", "rewrites it in its own words", AMBER_T, INK), ("Revocation", "worker-X revoked", RED, WHITE),
           ("Executor", "acts with tools", NAVY, WHITE)]
    hw_ = (12.2 - 4 * 0.35) / 5
    for i, (h_, d_, f_, tc_) in enumerate(hs_):
        xx = 0.9 + i * (hw_ + 0.35)
        rect(s, xx, 2.3, hw_, 1.25, fill=f_, radius=0.1, line=(LINEC if f_ in (MIST, AMBER_T) else None))
        text(s, xx, 2.42, hw_, 0.45, h_, size=15, color=tc_, bold=True, font=HEADB, align=PP_ALIGN.CENTER)
        text(s, xx + 0.1, 2.88, hw_ - 0.2, 0.6, d_, size=10.5, color=(SLATE if tc_ is INK else MIST if f_ is NAVY else WHITE),
             font=BODY, align=PP_ALIGN.CENTER, spacing=0.95)
        if i < 4:
            text(s, xx + hw_, 2.3, 0.35, 1.25, "→", size=18, color=TEAL, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    card(s, 0.9, 3.85, 12.2, 10.2 - 3.85)
    x_, w_, y_ = 1.25, 11.5, 4.0
    grp_head(s, x_, y_, w_, "ANY RESIDUE  ·  ONE HOP → TWO HOPS, SAME DEFENCE, SAME SEEDS")
    y_ += 0.5
    for lab_, sub_, key_ in [("Not revoked", "no defence", "hop2_compromised"), ("Notice", "credentials + notice", "hop2_notice"),
                             ("Lineage marks", "found by citations", "hop2_lineage"),
                             ("Taint quarantine", "normalised matching", "hop2_taint"),
                             ("Scope quarantine", "field keywords", "hop2_scope")]:
        if ADV[key_]:
            cmp_row(s, x_, y_, w_, lab_, sub_, ADV[key_], "one hop", "two hops", h=0.9)
            y_ += 0.98
    hg_ = ADV["hop2_gate"]
    rail(s, 13.4, 2.3, 5.7, 10.2 - 2.3, "WHY THE MARKS FAILED", [
        (f"Lines marked: {kn(ONE_HIT)} → {kn(HOP_HIT)}", "trials with at least one marked handoff line, one hop vs two: "
         "the coordinator's rewrite dropped the message-id citations.", NEG),
        ("Taint does not need citations", f"it matches what worker-X wrote: {pc(ADV['hop2_taint']['b'])} residue after two hops.", POS),
        ((f"Action gate: {pc(hg_['b'])}" if hg_ else "Action gate"),
         (f"two hops with the gate vs {pc(hg_['a'])} with the notice only ({fp(hg_['p'])})." if hg_ else
          "not yet run on two-hop handoffs."), POS),
    ], step=2.15, body_size=12.5)
    foot(s)

# ---- 11-13 + re-grading: robustness --------------------------------------------
if HAS_TPL or HAS_TEMP:
    s = slide(prs, PAPER)
    kicker(s, "Experiments 11–13 and a re-grading of every trial  ·  does the pattern depend on the set-up?")
    title(s, "New templates, temperature and grading leave the pattern intact", size=36)
    cw_ = (18.2 - 0.3) / 2; ch_ = (10.2 - 2.3 - 0.3) / 2
    boxes = [(0.9, 2.3), (0.9 + cw_ + 0.3, 2.3), (0.9, 2.3 + ch_ + 0.3), (0.9 + cw_ + 0.3, 2.3 + ch_ + 0.3)]
    def num_strip(s, x, y, w, items, size=24):
        k_ = len(items); iw = w / k_
        for j, (lab, t, kind) in enumerate(items):
            col = (ts_col(t) if kind == "ts" else res_col(t))
            text(s, x + j * iw, y, iw, 0.6, pc(t), size=size, color=col, bold=True, font=HEADB, align=PP_ALIGN.CENTER)
            text(s, x + j * iw, y + 0.62, iw, 0.55, lab, size=10.5, color=SLATE, font=BODY, align=PP_ALIGN.CENTER, spacing=0.95)
    # 11
    x0_, y0_ = boxes[0]; card(s, x0_, y0_, cw_, ch_, bar=TEALBR)
    n_tpl = len(TEMPLATES) + len(TEMPLATES_B)
    text(s, x0_ + 0.35, y0_ + 0.3, cw_ - 0.7, 0.4, f"EXP 11  ·  {len(TEMPLATES_B)} NEW TICKET TEMPLATES, SEEDS 100–147", size=12,
         color=TEAL, bold=True, font=HEAD)
    if HAS_TPL:
        T_ = TPL
        text(s, x0_ + 0.35, y0_ + 0.72, cw_ - 0.7, 0.4, f"Any residue, pooled over {xnm(T_[TPL_PAIRS[0]]['models'])}",
             size=12, color=SLATE, font=BODY)
        num_strip(s, x0_ + 0.2, y0_ + 1.2, cw_ - 0.4, [
            ("not revoked", T_[TPL_PAIRS[0]]["a"], "res"), ("credentials only", T_[TPL_PAIRS[0]]["b"], "res"),
            ("+ notice", T_[TPL_PAIRS[1]]["b"], "res"), ("+ lineage marks", T_[TPL_PAIRS[2]]["b"], "res"),
            ("taint quarantine", T_[TPL_PAIRS[3]]["b"], "res")])
        text(s, x0_ + 0.35, y0_ + 2.5, cw_ - 0.7, 1.0,
             f"Same ordering as on the original six: credentials only vs not revoked {fp(T_[TPL_PAIRS[0]]['p'])}, lineage marks vs notice "
             f"{fp(T_[TPL_PAIRS[2]]['p'])}, taint quarantine vs marks {fp(T_[TPL_PAIRS[3]]['p'])}.",
             size=12, color=SLATE, font=BODY, spacing=1.03)
    # 12
    x0_, y0_ = boxes[1]; card(s, x0_, y0_, cw_, ch_, bar=TEALBR)
    text(s, x0_ + 0.35, y0_ + 0.3, cw_ - 0.7, 0.4, "EXP 12  ·  SAMPLING TEMPERATURE", size=12, color=TEAL, bold=True, font=HEAD)
    if HAS_TEMP:
        text(s, x0_ + 0.35, y0_ + 0.72, cw_ - 0.7, 0.4, f"Any residue, pooled over {xnm(TEMP_MODELS)}", size=12, color=SLATE, font=BODY)
        tl_ = {"compromised": "not revoked", "revoke_silent": "credentials only", "revoke_lineage": "+ lineage marks",
               "taint_quarantine_norm": "taint quarantine"}
        cx_ = x0_ + 3.2; cwt = (cw_ - 3.5) / 3
        for j, t in enumerate(("0.0", "0.7", "1.0")):
            text(s, cx_ + j * cwt, y0_ + 1.12, cwt, 0.35, f"T = {t}", size=11, color=SLATE2, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
        for i, c in enumerate(TEMP_CONDS):
            yy = y0_ + 1.5 + i * 0.47
            text(s, x0_ + 0.35, yy, 2.9, 0.42, tl_[c], size=12.5, color=INK, bold=True, font=HEADB, anchor=MSO_ANCHOR.MIDDLE)
            for j, t in enumerate(("0.0", "0.7", "1.0")):
                v = TEMP[(c, t)]
                text(s, cx_ + j * cwt, yy, cwt, 0.42, pc(v), size=16, color=res_col(v), bold=True, font=HEADB,
                     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    # 13
    x0_, y0_ = boxes[2]; card(s, x0_, y0_, cw_, ch_, bar=TEALBR)
    text(s, x0_ + 0.35, y0_ + 0.3, cw_ - 0.7, 0.4, "EXP 13  ·  A TICKET THAT ASKS FOR THE FIELD TO BE CORRECTED", size=12,
         color=TEAL, bold=True, font=HEAD)
    ec, el = ADV["explicit_clean"], ADV["explicit_lineage"]
    if ec and el:
        text(s, x0_ + 0.35, y0_ + 0.72, cw_ - 0.7, 0.4, f"Pooled over {xnm(ec['models'])}", size=12, color=SLATE, font=BODY)
        num_strip(s, x0_ + 0.2, y0_ + 1.2, (cw_ - 0.4), [
            ("clean · task success\nplain ticket", ec["a"], "ts"), ("clean · task success\nexplicit ticket", ec["b"], "ts"),
            ("lineage · residue\nplain ticket", el["a"], "res"), ("lineage · residue\nexplicit ticket", el["b"], "res")])
        assert ec["b"]["p"] > ec["a"]["p"] and ec["p"] < 0.05 and el["p"] >= 0.05
        text(s, x0_ + 0.35, y0_ + 2.55, cw_ - 0.7, 0.9,
             f"Low task success came from executors leaving the field unwritten ({fp(ec['p'])}); residue under lineage marks "
             f"did not change ({fp(el['p'])}).", size=12, color=SLATE, font=BODY, spacing=1.03)
    # re-grading
    x0_, y0_ = boxes[3]; card(s, x0_, y0_, cw_, ch_, bar=TEALBR)
    text(s, x0_ + 0.35, y0_ + 0.3, cw_ - 0.7, 0.4, f"RE-GRADING ALL {REG['n']:,} TRIALS OF EXPERIMENTS 01–07", size=12,
         color=TEAL, bold=True, font=HEAD)
    iw_ = (cw_ - 0.4) / 4
    for j, (big_, lab_, col_) in enumerate([(f"{REG['exact']:,}", "residue, exact\nmatch (reported)", INK),
                                            (f"+{REG['norm'] - REG['exact']}", "normalised match\n(case, spacing, digits)", AMBER_D),
                                            (f"+{REG['broad'] - REG['exact']}", "broad match\n(any form of the value)", AMBER_D),
                                            (f"{REG['fp']}", "broad matches in\nclean / false alarms", GREEN)]):
        text(s, x0_ + 0.2 + j * iw_, y0_ + 0.85, iw_, 0.6, big_, size=24, color=col_, bold=True, font=HEADB, align=PP_ALIGN.CENTER)
        text(s, x0_ + 0.2 + j * iw_, y0_ + 1.47, iw_, 0.6, lab_, size=10.5, color=SLATE, font=BODY, align=PP_ALIGN.CENTER, spacing=0.95)
    text(s, x0_ + 0.35, y0_ + 2.3, cw_ - 0.7, 1.1,
         f"Exact matching undercounts residue by {100 * (REG['broad'] - REG['exact']) / REG['exact']:.1f}%, with no false "
         f"positives. Longest executor prompt: about {MAXPROMPT_KTOK:.1f}k tokens ({MAXPROMPT:,} characters), well within "
         "the 8,192-token context.", size=12, color=SLATE, font=BODY, spacing=1.03)
    foot(s)

# ---- 08 training fix ------------------------------------------------------------
if HAS_SFT:
    s = slide(prs, PAPER)
    kicker(s, "Experiment 08  ·  fine-tune the executor instead of changing what it sees  ·  Qwen3.5-4B + LoRA  ·  fresh seeds 48–95")
    title(s, "A trained executor removed residue, unless worker-X stayed unrevoked", size=34)
    tx_, ty_, tw_ = 0.9, 2.3, 12.4
    SL = {"clean": "no compromise", "compromised": "not revoked", "revoke_silent": "credentials only",
          "revoke_notice": "+ notice", "revoke_lineage": "+ lineage marks", "benign_lineage": "false alarm"}
    rect(s, tx_, ty_, tw_, 0.62, fill=NAVY, radius=0.03)
    for h_, cx_, w_ in [("Condition", 0.3, 3.6), ("Any residue  ·  base → tuned", 3.9, 4.2), ("Task success  ·  base → tuned", 8.1, 4.2)]:
        text(s, tx_ + cx_, ty_, w_, 0.62, h_, size=12, color=WHITE, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    rh_ = 0.95
    for i, c in enumerate(SFT_CONDS):
        yy = ty_ + 0.62 + i * rh_
        fail = c == "compromised"
        rect(s, tx_, yy, tw_, rh_, fill=(RED_T if fail else (CARD if i % 2 == 0 else ROWALT)), radius=0,
             shape=MSO_SHAPE.RECTANGLE, line=LINEC, line_w=0.5)
        text(s, tx_ + 0.3, yy + 0.12, 3.6, 0.4, c, size=13, color=INK, bold=True, font=MONO)
        text(s, tx_ + 0.3, yy + 0.52, 3.6, 0.35, SL[c], size=11, color=SLATE, font=BODY)
        for k_, (fl, cx_) in enumerate([("any_residue", 3.9), ("task_success", 8.1)]):
            v = SFT[c][fl]; cf = res_col if fl == "any_residue" else ts_col
            text(s, tx_ + cx_, yy + 0.08, 4.1, 0.5, [(pc(v["base"]), {"color": SLATE2}), ("  →  ", {"color": SLATE2}),
                                                    (pc(v["tuned"]), {"color": cf(v["tuned"])})], size=20, bold=True, font=HEADB)
            text(s, tx_ + cx_, yy + 0.58, 4.1, 0.32, f"{v['x']} vs {v['y']} pairs  ·  {fp(v['p'])}", size=10,
                 color=(TEAL if v["p"] < 0.05 else SLATE2), font=BODY)
    ny_ = ty_ + 0.62 + len(SFT_CONDS) * rh_ + 0.15
    if SFT_STRESS:
        st_ = "  ·  ".join(f"{c} {pc(v['base'])}→{pc(v['tuned'])}" for _, c, v in SFT_STRESS[:6])
        text(s, tx_, ny_, tw_, 1.0, [("Stress test, residue base → tuned: ", {"bold": True, "color": INK}), (st_, {"color": SLATE})],
             size=11, font=BODY, spacing=1.0)
    else:
        text(s, tx_, ny_, tw_, 0.8, f"Same handoffs for both executors (written by the base model), paired by seed; "
             f"{SFT['revoke_lineage']['any_residue']['base']['n']} seeds per cell, none used in training (seeds 0–31).",
             size=11, color=SLATE2, font=BODY, spacing=1.0)
    rx_ = tx_ + tw_ + 0.35; rw_ = 19.1 - rx_
    rect(s, rx_, ty_, rw_, 10.2 - ty_, fill=NAVY, radius=0.04)
    text(s, rx_ + 0.35, ty_ + 0.3, rw_ - 0.7, 0.4, "WHAT IT LEARNED", size=13, color=TEALBR, bold=True, font=HEAD)
    text(s, rx_ + 0.35, ty_ + 0.75, rw_ - 0.7, 1.4, "LoRA on the transcripts of executors that handled a revocation "
         "correctly: it re-obtains the contested field before writing it.", size=12.5, color=MIST, font=BODY, spacing=1.03)
    text(s, rx_ + 0.35, ty_ + 2.0, rw_ - 0.7, 0.4, "WHERE IT FAILS", size=13, color=NEG, bold=True, font=HEAD)
    text(s, rx_ + 0.35, ty_ + 2.45, rw_ - 0.7, 1.7,
         f"Compromised but not revoked, it asks worker-X itself ({SFT_ASKX['tuned']} of {SFT_ASKX['n']} trials, base "
         f"{SFT_ASKX['base']}), which confirms the false value: residue "
         f"{pc(SFT['compromised']['any_residue']['base'])} → {pc(SFT['compromised']['any_residue']['tuned'])}.",
         size=12.5, color=MIST, font=BODY, spacing=1.03)
    URLS["hf"] = HF_URL; QR["hf"] = make_qr(HF_URL, QRDIR / "hf.png")
    qs_ = 1.9
    rect(s, rx_ + 0.35, 10.2 - qs_ - 1.25, qs_ + 0.2, qs_ + 0.2, fill=WHITE, radius=0.06)
    s.shapes.add_picture(str(QR["hf"]), Inches(rx_ + 0.45), Inches(10.2 - qs_ - 1.15), Inches(qs_), Inches(qs_))
    text(s, rx_ + 0.35, 10.2 - 0.85, rw_ - 0.7, 0.7, "Adapter, data and results on the Hugging Face Hub\n"
         + HF_URL.replace("https://", ""), size=9.5, color=MIST, font=MONO, spacing=1.0)
    text(s, rx_ + qs_ + 0.75, 10.2 - qs_ - 1.15, rw_ - qs_ - 1.1, qs_, "The model needs the platform's revocation "
         "to make its re-verification come out right.", size=12.5, color=WHITE, bold=True, font=BODY, spacing=1.03,
         anchor=MSO_ANCHOR.MIDDLE)
    foot(s)

# ===========================================================================
# RECOMMENDATIONS
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "Design recommendations for agent-team platforms")
title(s, "Revocation has to reach content and its derivatives")
recs = [("Record provenance on the platform",
         f"Bind each claim to its author, or match what the revoked agent wrote, so lineage does not depend on agents "
         f"citing sources. Without citations, marks reached {', '.join(kn(ABL[m]['hit_nocite']) for m in ABL_MODELS)} "
         f"handoffs; platform taint found derived lines in "
         f"{', '.join(kn(PLAT[m]['taint_lineage']['hit']) for m in PLAT_MODELS)}."
         + (f" Normalise before matching: “{TAINT_FMT}” slipped past an exact match." if HAS_NORM else ""), TEALBR),
        ("Make revocation trigger re-derivation",
         "Withhold derived content until another agent re-obtains it. Marking the taint-matched lines left residue at "
         f"{' / '.join(pc(PLAT[m]['taint_lineage']['any']) for m in PLAT_MODELS)}; withholding the same lines: "
         f"{' / '.join(pc(PLAT[m]['taint_quarantine']['any']) for m in PLAT_MODELS)}."
         + (f" Better still, gate the action: writes to the revoked agent's field held residue at {pc(ADV['gate']['b'])}."
            if HAS_ADV else ""), TEALBR),
        ("Scope any notice to derived content",
         f"Say that content already in the agent's context came from the revoked agent. One added sentence worked for "
         f"{andj(nm(m) for m in STRICT_OK)} but not {' or '.join(nm(m) for m in STRICT_NO) or '–'}: "
         "a notice is a complement, not the enforcement.", TEALBR)]
rcw = (18.2 - 2 * 0.35) / 3; rch = 5.1
for i, (h_, d, c) in enumerate(recs):
    xx = 0.9 + i * (rcw + 0.35); yy = 2.35
    card(s, xx, yy, rcw, rch, bar=c)
    rect(s, xx + 0.35, yy + 0.45, 0.8, 0.8, fill=TEALBR, radius=0.5, shape=MSO_SHAPE.OVAL)
    text(s, xx + 0.35, yy + 0.45, 0.8, 0.8, str(i + 1), size=24, color=WHITE, bold=True, font=HEADB,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, xx + 1.4, yy + 0.4, rcw - 1.7, 0.9, h_, size=19, color=INK, bold=True, font=HEADB, anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)
    text(s, xx + 0.35, yy + 1.6, rcw - 0.7, rch - 1.7, d, size=15.5, color=SLATE, font=BODY, spacing=1.07)
by = 2.35 + rch + 0.35
rect(s, 0.9, by, 18.2, 10.2 - by, fill=NAVY, radius=0.04)
text(s, 1.3, by + 0.3, 17.4, 0.4, ("TESTED: REMOVING CONTENT WORKED UNTIL THE ATTACKER REWORDED IT; GATING THE ACTION DID NOT DEPEND ON WORDING"
     if HAS_ADV else "TESTED IN EXPERIMENT 06: THE RECOMMENDED DESIGN WORKED FOR EVERY MODEL"), size=13, color=TEALBR, bold=True, font=HEAD)
text(s, 1.3, by + 0.8, 17.4, 1.6,
     [[(("Normalised platform taint + quarantine: residue " if HAS_NORM else "Platform taint + quarantine: residue ")
        + ", ".join(f"{nm(m)} {pc(PLAT[m]['taint_quarantine_norm' if HAS_NORM else 'taint_quarantine']['any'])}" for m in PLAT_MODELS)
        + f" (vs {' / '.join(pc(PLAT[m]['nocite_lineage']['any']) for m in PLAT_MODELS)} with citation-based marks on the same handoffs). ",
        {"color": WHITE, "bold": True}),
       ((f"Against an attacker that spelled its values out, taint quarantine left {pc(ADV['obf_taint']['b'])}; the action "
         f"gate left {pc(ADV['obf_gate']['b'])}, at the price of {pc(GATE_B['gate']['escalated'])} escalation. " if HAS_ADV else "")
        + "Every mechanism that asked the executor to discount content it could still read was model-dependent; "
        "removing the content, or refusing the action, was not.", {"color": MIST})]],
     size=15.5, font=BODY, spacing=1.06)
foot(s)

# ===========================================================================
# 21 — LIMITATIONS
# ===========================================================================
s = slide(prs, PAPER)
kicker(s, "What the results do and do not establish")
title(s, "A deliberately small, fully controlled testbed")
# model coverage is computed: a model counts for a part of the study only when all its cells there are complete
COVER = [("Ablations", ABL_MODELS), ("Platform designs", PLAT_MODELS), ("Stress tests", [EXT_ID[f] for f in STRESS_MODELS])]
_cov = "; ".join(f"{k_}: {', '.join(nm(m) for m in v_)}" for k_, v_ in COVER if v_)
_main_only = [m for m in MODELS if not any(m in v_ for _, v_ in COVER)]
lims = [("One scenario family",
         f"{len(TEMPLATES) + len(TEMPLATES_B)} ticket templates, scripted workers, one mock CRM and one tool set; absolute "
         "rates depend on these designs and on the prompt wording."),
        ("Hand-written adaptive attacks",
         "Laundering and obfuscation are two hand-written strategies, not an optimised attacker; a paraphrasing or "
         "value-splitting attacker was not tested."),
        ("What the gate assumes",
         "The platform knows the revoked agent's assigned field and the plan's transfers, and the gate did not inspect "
         "free-text notes or ticket comments."),
        ("The gate's price",
         f"Executors escalated in {pc(GATE_B['gate']['escalated'])} of gated trials and task success fell to "
         f"{pc(GATE_B['gate']['task_success'])}; the safe action was to stop, not to re-derive." if HAS_ADV else
         "Not yet measured."),
        ("One trained executor",
         "One 4B model from one LoRA run; it re-asks the official source, which fails when the compromised worker is "
         "not revoked." if HAS_SFT else "The training experiment is not complete."),
        ("Model coverage",
         f"Main grid: {len(MODELS)} models. {_cov}."
         + (f" Main grid only: {', '.join(nm(m) for m in _main_only)}." if _main_only else "")),
        ("Correlated repetitions",
         f"{SEEDS} seeds are {len(TEMPLATES)} templates × 2 payloads × 4 repetitions; repetitions often agree, so the "
         "paper adds template-clustered tests."),
        ("Mock environment", "All systems, addresses and credentials are mock; longer chains than two hops and "
         "persistent memory are untested.")]
lcw = (18.2 - 3 * 0.3) / 4; lch = 3.6
for i, (h_, d) in enumerate(lims):
    r_, c_ = divmod(i, 4)
    xx = 0.9 + c_ * (lcw + 0.3); yy = 2.35 + r_ * (lch + 0.3)
    card(s, xx, yy, lcw, lch, bar=AMBER)
    text(s, xx + 0.3, yy + 0.3, 0.6, 0.5, str(i + 1), size=22, color=GHOST, bold=True, font=HEADB)
    text(s, xx + 0.8, yy + 0.3, lcw - 1.1, 0.85, h_, size=15, color=INK, bold=True, font=HEADB, spacing=0.95)
    text(s, xx + 0.3, yy + 1.2, lcw - 0.6, lch - 1.3, d, size=13.5, color=SLATE, font=BODY, spacing=1.05)
foot(s)

# ===========================================================================
# 22 — REFERENCES (all QR)
# ===========================================================================
s = slide(prs, NAVY)
line(s, 0, 0, SW, 0.22, TEALBR)
text(s, 1.2, 0.75, 17, 0.6, "REFERENCES & LINKS", size=17, color=TEALBR, bold=True, font=HEAD)
text(s, 1.15, 1.25, 17, 1.0, "Scan to open the code, the sprint, the incident report and the key papers", size=32,
     color=WHITE, bold=True, font=HEADB)
REFS = [("repo", "Code, data & transcripts", REPO_URL.replace("https://", "")),
        ("sprint", "Apart Swarm Alignment Hackathon", URLS["sprint"].replace("https://", "")),
        ("metr", "METR 2026, Hugging Face incident", "metr.org/hugging-face-incident-report-aug-2026.pdf"),
        ("deochake", "Deochake 2026, Heartbeat-bound credentials", "arxiv.org/abs/2605.20704"),
        ("aip", "Prakash 2026, AIP", "arxiv.org/abs/2603.24775"),
        ("capmas", "Veski et al. 2026, CAPMAS", "arxiv.org/abs/2609.06500"),
        ("south", "South et al. 2025, Authenticated delegation", "arxiv.org/abs/2501.09674"),
        ("infect", "Lee & Tiwari 2024, Prompt infection", "arxiv.org/abs/2410.07283"),
        ("wu", "Wu et al. 2026, Collective loss of control", "arxiv.org/abs/2609.18460"),
        ("kitaoka", "Kitaoka et al. 2026, Multi-agent red-teaming", "arxiv.org/abs/2610.24052"),
        ("hammond", "Hammond et al. 2025, Multi-agent risks", "arxiv.org/abs/2502.14143")]
ncol = 6; qw = 1.65; gapx = (18.2 - ncol * qw) / (ncol - 1); x0 = 0.9; y0 = 2.75; gapy = 3.65
for i, (k, t_, u) in enumerate(REFS):
    r_, c_ = divmod(i, ncol); xx = x0 + c_ * (qw + gapx); yy = y0 + r_ * gapy
    rect(s, xx - 0.1, yy - 0.1, qw + 0.2, qw + 0.2, fill=WHITE, radius=0.06)
    s.shapes.add_picture(str(QR[k]), Inches(xx), Inches(yy), Inches(qw), Inches(qw))
    text(s, xx - 0.55, yy + qw + 0.18, qw + 1.1, 0.75, t_, size=11.5, color=WHITE, bold=True, font=HEADB,
         align=PP_ALIGN.CENTER, spacing=0.95)
    text(s, xx - 0.55, yy + qw + 0.95, qw + 1.1, 0.7, u, size=8.5, color=MIST, font=MONO, align=PP_ALIGN.CENTER, spacing=0.95)
text(s, 1.2, SH - 0.62, 17.5, 0.4,
     "Fatimah Emad Eldin  ·  Trouve Labs  ·  Revoked but Not Forgotten  ·  Apart Research Swarm Alignment Hackathon, November 2026",
     size=11.5, color=MIST, font=BODY)

# ===========================================================================
# 23 — THANK YOU
# ===========================================================================
s = slide(prs, NAVY)
line(s, 0, 0, SW, 0.22, TEALBR)
text(s, 1.2, 1.9, 11, 0.5, "THANK YOU", size=17, color=TEALBR, bold=True, font=HEAD)
text(s, 1.15, 2.5, 11.4, 2.4, "Revoking the agent\nis not revoking its work.", size=50, color=WHITE, bold=True,
     font=HEADB, spacing=1.0)
text(s, 1.2, 5.0, 11.0, 1.8,
     "Revocation for agent teams should reach content and its derivatives, with provenance recorded by the platform "
     "rather than reported by the agents.", size=19, color=MIST, font=BODY, spacing=1.12)
line(s, 1.22, 7.15, 3.2, 0.045, TEALBR)
text(s, 1.2, 7.4, 11.2, 0.5, "Fatimah Emad Eldin  ·  Trouve Labs", size=18, color=WHITE, bold=True, font=HEADB)
text(s, 1.2, 7.95, 11.2, 0.9, "With Apart Research  ·  Swarm Alignment Hackathon, November 2026\n"
     "Testbed, transcripts and analysis released under the MIT licence.", size=14, color=GHOST, font=BODY, spacing=1.1)
for j, (k, cap) in enumerate([("repo", "Code, data & transcripts"), ("sprint", "The hackathon")]):
    xx = 12.9 + j * 3.3
    rect(s, xx - 0.12, 3.0 - 0.12, 2.74, 2.74, fill=WHITE, radius=0.06)
    s.shapes.add_picture(str(QR[k]), Inches(xx), Inches(3.0), Inches(2.5), Inches(2.5))
    text(s, xx - 0.4, 5.8, 3.3, 0.5, cap, size=14, color=WHITE, bold=True, font=HEADB, align=PP_ALIGN.CENTER)
text(s, 12.5, 6.4, 6.6, 0.5, REPO_URL.replace("https://", ""), size=11, color=MIST, font=MONO, align=PP_ALIGN.CENTER)

# ===========================================================================
# STORY STRUCTURE: section dividers, the proposed-solution and key-findings slides, then reorder into
#   1 context & problem · 2 methodology & harness · 3 proposed solution & architecture · 4 results ·
#   5 ablations & stress tests · 6 findings & recommendations · 7 limitations
# ===========================================================================
def _mx(k):
    return MXV.get(k, "–").replace("\\%", "%")

divider(prs, "01", "Section 1  ·  context and problem", "Revoking an agent stops the agent.\nDoes it stop its work?")
divider(prs, "03", "Section 3  ·  proposed solution", "Make revocation reach content,\nenforced by the platform")
divider(prs, "06", "Section 6  ·  findings and recommendations", "What the evidence says,\nand what platforms should do")
divider(prs, "07", "Section 7  ·  limitations", "What this study does\nand does not establish")

# ---- proposed solution: the defence ladder on the system architecture -----------------------------
s = slide(prs, PAPER)
kicker(s, "Proposed solution  ·  system architecture")
title(s, "Move the defence from what the executor sees to what the platform enforces", size=34)
_aw2, _ah2 = Image.open(ARCH).size
iw = 9.4; ih = iw * _ah2 / _aw2
card(s, 0.9, 2.15, iw + 0.4, ih + 0.3)
s.shapes.add_picture(str(ARCH), Inches(1.1), Inches(2.3), Inches(iw), Inches(ih))
bx = 0.9 + iw + 0.7; bw = 19.1 - bx
rect(s, bx, 2.15, bw, ih + 0.3, fill=NAVY, radius=0.04)
text(s, bx + 0.35, 2.35, bw - 0.7, 0.4, "THE PROPOSAL IN THREE STEPS", size=12.5, color=TEALBR, bold=True, font=HEAD)
_steps = [("1  Record provenance on the platform", "find what derives from the revoked agent without relying on agents' citations"),
          ("2  Withhold derived content on revocation", "quarantine it until another agent has re-obtained it"),
          ("3  Enforce re-derivation at the action", "the tool server rejects writes and transfers that were not re-derived")]
yy = 2.9
for h_, d_ in _steps:
    text(s, bx + 0.35, yy, bw - 0.7, 0.4, h_, size=15, color=WHITE, bold=True, font=HEADB)
    text(s, bx + 0.35, yy + 0.42, bw - 0.7, 0.7, d_, size=12, color=MIST, font=BODY, spacing=1.0)
    yy += 1.25
# ladder table: every rung with who has to act, pooled residue, and what breaks it
ty0 = 2.15 + ih + 0.65
_lad = [("Credentials only", "nobody", pc(POOL_SILENT), "the content was already handed off"),
        ("+ notice", "executor's judgement", pc(R(None, "revoke_notice", "any_residue")), "helps some models only"),
        ("+ lineage marks", "executor's judgement", pc(R(None, "revoke_lineage", "any_residue")),
         "writer drops citations; a second hop removes them"),
        ("Taint quarantine (normalised)", "platform",
         f"{NORM_K}/{NORM_N}" if HAS_NORM else "–",
         f"attacker rewords its values ({pc(ADV['obf_taint']['b'])} residue)" if HAS_ADV else "attacker rewords its values"),
        ("Action gate", "platform tool server", pc(ADV["gate"]["b"]) if HAS_ADV else "–",
         f"free-text notes; executors escalate more ({pc(GATE_B['gate']['escalated'])})" if HAS_ADV else "")]
cols = [(0.9, 4.6, "Mechanism"), (5.6, 3.6, "Who has to act"), (9.3, 2.6, "Residue"), (12.0, 7.1, "Breaks when")]
for x_, w_, h_ in cols:
    text(s, x_ + 0.15, ty0, w_, 0.35, h_.upper(), size=11, color=TEAL, bold=True, font=HEAD)
line(s, 0.9, ty0 + 0.4, 18.2, 0.02, LINEC)
rh = (10.25 - ty0 - 0.5) / len(_lad)
for i_, (m_, who, res, brk) in enumerate(_lad):
    y_ = ty0 + 0.5 + i_ * rh
    plat = who.startswith("platform")
    if plat:
        rect(s, 0.9, y_ - 0.04, 18.2, rh - 0.06, fill=TEAL_T, radius=0.04)
    text(s, 1.05, y_, 4.5, rh - 0.1, m_, size=13, color=INK, bold=True, font=HEADB, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 5.75, y_, 3.5, rh - 0.1, who, size=12, color=(TEAL if plat else SLATE), bold=plat, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 9.45, y_, 2.5, rh - 0.1, res, size=15, color=(GREEN if plat else RED), bold=True, font=HEADB, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 12.15, y_, 6.9, rh - 0.1, brk, size=12, color=SLATE, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
foot(s)

# ---- key findings ------------------------------------------------------------------------------------
s = slide(prs, PAPER)
kicker(s, "Key findings")
title(s, "Five things the evidence shows", size=38)
_lin = [R(m, "revoke_lineage", "any_residue")["p"] for m in MODELS]
_ntc = [nm(m) for m in MODELS if PR(m, "revoke_silent", "revoke_notice", "any_residue")["p"] < 0.05
        and R(m, "revoke_notice", "any_residue")["p"] < R(m, "revoke_silent", "any_residue")["p"]]
_find = [(f"{pc(POOL_COMP)} → {pc(POOL_SILENT)}", RED, "Credential revocation leaves the content in place",
          f"Pooled residue without revocation vs credential-only revocation, {len(MODELS)} models. The false fact already "
          f"lives in a teammate's handoff."),
         (f"{round(100 * min(_lin))}–{round(100 * max(_lin))}%", AMBER_D, "Signals to the executor are model-dependent",
          f"Residue under lineage marks, by model. A notice helped only {', '.join(_ntc) or 'no model'}; deleting the "
          f"revoked agent's posts added nothing."),
         ((f"{NORM_K}/{NORM_N}" if HAS_NORM else "–"), GREEN, "Platform taint quarantine removes residue …",
          "Trials with residue when the platform matched the revoked agent's own (normalised) content and withheld it."),
         ((f"{pc(ADV['obf_taint']['b'])} → {pc(ADV['obf_gate']['b'])}" if HAS_ADV else "–"), TEAL,
          "… until the attacker rewords; an action gate holds",
          (f"Residue against an obfuscating attacker: taint quarantine vs a tool-server gate. Cost: executors escalate "
           f"in {pc(GATE_B['gate']['escalated'])} of gated trials.") if HAS_ADV else ""),
         ((f"{_mx('x/vsluna/revoked/any/tuned')} vs {_mx('x/vsluna/revoked/any/luna')}"), TEAL,
          "A trained 4B executor matches GPT-6 Luna",
          f"Residue after revocation on Luna's own handoffs (tuned 4B vs Luna), with more tickets completed "
          f"({_mx('x/vsluna/revoked/task/tuned')} vs {_mx('x/vsluna/revoked/task/luna')}). It fails when the worker is "
          f"not revoked.")]
_pos = [(0.9, 2.3), (7.05, 2.3), (13.2, 2.3), (0.9, 6.35), (7.05, 6.35)]
for (x_, y_), (big, col, head, body) in zip(_pos, _find):
    card(s, x_, y_, 5.95, 3.8, bar=col)
    text(s, x_ + 0.35, y_ + 0.4, 5.3, 0.9, big, size=34, color=col, bold=True, font=HEADB)
    text(s, x_ + 0.35, y_ + 1.4, 5.3, 0.8, head, size=15, color=INK, bold=True, font=HEADB, spacing=1.0)
    text(s, x_ + 0.35, y_ + 2.25, 5.3, 1.45, body, size=11.5, color=SLATE, font=BODY, spacing=1.05)
rect(s, 13.2, 6.35, 5.95, 3.8, fill=NAVY, radius=0.06)
text(s, 13.55, 6.75, 5.3, 0.4, "THE TAKEAWAY", size=12.5, color=TEALBR, bold=True, font=HEAD)
text(s, 13.55, 7.3, 5.3, 2.6, "Revocation for agent teams has to reach content and the actions derived from it, "
     "enforced by the platform rather than honoured by the agents.", size=16, color=WHITE, bold=True, font=HEADB, spacing=1.1)
foot(s)

# ---- reorder into the story ------------------------------------------------------------------------------
def _texts(sl):
    return [sh.text_frame.text.strip() for sh in sl.shapes if sh.has_text_frame and sh.text_frame.text.strip()]

_ORDER = ["AT A GLANCE", "#01", "WHY THIS NEEDS MEASURING", "THE CONCEPT AT THE CENTRE", "RELATED WORK",
          "#02", "THREAT MODEL AND TESTBED", "THE ATTACK PAYLOADS", "SEVEN CONDITIONS", "METRICS & EVALUATION", "MODELS & SETUP",
          "#03", "PROPOSED SOLUTION",
          "#04", "HEADLINE RESULT", "ALL MAIN CONDITIONS", "FIGURE", "TELLING THE EXECUTOR", "MINISTRAL-3 14B  ·  REVOKE_LINEAGE",
          "EXPERIMENT 06  ·  THE RECOMMENDED", "EXPERIMENT 06  ·  MINISTRAL", "USEFULNESS COST",
          "#05", "ABLATIONS 1", "ABLATIONS 3", "EXPERIMENT 07", "EXPERIMENT 09  ·", "EXPERIMENT 09B", "EXPERIMENT 10",
          "EXPERIMENTS 11", "EXPERIMENT 08",
          "#06", "KEY FINDINGS", "DESIGN RECOMMENDATIONS",
          "#07", "WHAT THE RESULTS DO AND DO NOT ESTABLISH", "REFERENCES & LINKS", "THANK YOU"]
_sl = list(prs.slides)
_ids = list(prs.slides._sldIdLst)
_used, _new = set(), []
for key in _ORDER:
    for i_, sl in enumerate(_sl):
        if i_ in _used:
            continue
        tx = _texts(sl)
        if not tx:
            continue
        hit = (tx[0] == key[1:]) if key.startswith("#") else tx[0].upper().startswith(key)
        if hit:
            _used.add(i_); _new.append(i_)
            break
_left = [i_ for i_ in range(len(_sl)) if i_ not in _used]
assert not _left, f"slides not placed in the story order: {[_texts(_sl[i_])[:1] for i_ in _left]}"
for el in _ids:
    prs.slides._sldIdLst.remove(el)
for i_ in _new:
    prs.slides._sldIdLst.append(_ids[i_])
# footers carry the slide number from creation time: renumber them in the new order
for n_, sl in enumerate(prs.slides, 1):
    for sh in sl.shapes:
        if sh.has_text_frame and re.fullmatch(r"\d{2}", sh.text_frame.text.strip() or "x") and sh.left > Inches(SW - 4.5) \
                and sh.top > Inches(SH - 1.0):
            sh.text_frame.paragraphs[0].runs[0].text = f"{n_:02d}"

# ---- save + verify + render ----------------------------------------------------
OUT = HERE / "revoked_not_forgotten_deck.pptx"
prs.save(str(OUT))
n_slides = len(prs.slides._sldIdLst)
print("saved", OUT, "slides:", n_slides, "models:", NAMES, "skipped:", SKIPPED)
for k, p in QR.items():
    got = decode_qr(p)
    print(f"QR {k:9s} {'OK ' if got == URLS[k] else 'BAD'} {got}")
    assert got == URLS[k]
if "--no-render" not in sys.argv:
    for old in (HERE / "_render").glob("slide_*.png"):
        old.unlink()
    pngs = render_to_pngs(OUT, HERE / "_render", dpi=80)
    shutil.copy(HERE / "_render" / "revoked_not_forgotten_deck.pdf", HERE / "revoked_not_forgotten_deck.pdf")
    print("rendered", len(pngs))

# ===========================================================================
# HTML slide version (same numbers, same verbatim texts)
# ===========================================================================
# ---- HTML: an exact copy of the deck (its own rendering), with the slide text embedded
import html_viewer  # noqa: E402
_pdf = HERE / "revoked_not_forgotten_deck.pdf"
if _pdf.exists() and "--no-render" not in sys.argv:
    _n = html_viewer.write(_pdf, [_texts(sl) for sl in prs.slides], HERE / "slides.html",
                           "Revoked but Not Forgotten · slides")
    shutil.copy(HERE / "slides.html", REPO / "slides.html")
    print("html slides:", _n, "(exact copy of the deck)")
