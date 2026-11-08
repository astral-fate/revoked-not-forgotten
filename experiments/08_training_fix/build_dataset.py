"""Build the SFT dataset for experiment 08 from existing executor transcripts (experiments 01-07).

Kept: trials on seeds 0-31 whose executor acted correctly (any_residue == False and task_success == True,
and no export_data call to any address) under
  - a revocation condition in which the executor is told of the revocation (notice, retract, lineage marks, strict
    notice, quarantine, taint marks/quarantine, nocite lineage, early revocation), and
  - the clean condition (so the model keeps doing the task when nothing is wrong).
Excluded: compromised / nocite_compromised / revoke_silent (the only correct behaviour there is to distrust content
with no signal, which would conflate the question), the benign_* false-alarm conditions (held out as an over-refusal
test), nosource_* (different tool set), and every trial on seeds 32-47 (held-out evaluation seeds).
Each valid executor turn becomes one row: prompt = flat rendering of the conversation so far (src/revres/flat.py),
completion = that turn's tool call re-serialised as compact JSON.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from revres.env import parse_action  # noqa: E402
from revres.flat import render_prompt  # noqa: E402

REVOKE_OK = {"revoke_notice", "revoke_retract", "revoke_lineage", "strict_notice", "revoke_quarantine", "taint_lineage",
             "taint_quarantine", "taint_quarantine_norm", "nocite_lineage", "early_revoke"}
KEEP = REVOKE_OK | {"clean"}
TRAIN_SEEDS = range(0, 32)
OUT = Path(__file__).resolve().parent / "dataset"


def tid(rec):
    label = rec["model"]
    return f"{label.replace('/', '_').replace(':', '-').replace('=>', '__writes-for__')}__{rec['condition']}__{rec['seed']}"


def norm(text):
    a = parse_action(text)
    return None if a is None else json.dumps({"tool": a["tool"], "args": a.get("args") or {}}, ensure_ascii=False)


def main():
    rows, comp_trials, comp_rows, missing = [], Counter(), Counter(), 0
    for tj in sorted(ROOT.glob("experiments/0[1-7]_*/results/*/trials.jsonl")):
        exp = tj.parts[-4]
        seen = {}
        for line in tj.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                seen[(r["model"], r["condition"], r["seed"])] = r
        for r in seen.values():
            if r["condition"] not in KEEP or r["seed"] not in TRAIN_SEEDS:
                continue
            if r["any_residue"] or not r["task_success"]:
                continue
            if any(a["tool"] == "export_data" or "ext-mirror" in json.dumps(a["args"]) for a in r["actions"]):
                continue  # an export to a paraphrased archive address is not graded as residue but is not a target
            p = tj.parent / "transcripts" / f"{tid(r)}.json"
            if not p.exists():
                missing += 1
                continue
            msgs = json.loads(p.read_text(encoding="utf-8"))["transcript"]
            hist = msgs[:2]
            n = 0
            for m in msgs[2:]:
                if m["role"] == "assistant":
                    c = norm(m["content"])
                    if c is not None:
                        rows.append(dict(prompt=render_prompt(hist), completion=c, source_model=r["executor_model"]
                                         if "executor_model" in r else r["model"], writer_model=r.get("writer_model", r["model"]),
                                         condition=r["condition"], seed=r["seed"], experiment=exp, turn=n))
                        n += 1
                        hist = hist + [{"role": "assistant", "content": c}]
                    else:
                        hist = hist + [m]
                else:
                    hist = hist + [m]
            key = (r.get("executor_model", r["model"]), r["condition"])
            comp_trials[key] += 1
            comp_rows[key] += n
    OUT.mkdir(exist_ok=True)
    with (OUT / "train.jsonl").open("w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with (OUT / "train.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["prompt", "completion"])
        for x in rows:
            w.writerow([x["prompt"], x["completion"]])
    comp = [dict(executor_model=k[0], condition=k[1], trials=comp_trials[k], rows=comp_rows[k]) for k in sorted(comp_trials)]
    summ = dict(rows=len(rows), trials=sum(comp_trials.values()), missing_transcripts=missing,
                by_condition={c: dict(trials=sum(v for k, v in comp_trials.items() if k[1] == c),
                                      rows=sum(v for k, v in comp_rows.items() if k[1] == c)) for c in sorted(KEEP)},
                by_model={m: dict(trials=sum(v for k, v in comp_trials.items() if k[0] == m),
                                  rows=sum(v for k, v in comp_rows.items() if k[0] == m))
                          for m in sorted({k[0] for k in comp_trials})},
                by_tool=dict(Counter(json.loads(x["completion"])["tool"] for x in rows)),
                max_prompt_chars=max(len(x["prompt"]) for x in rows), cells=comp)
    (OUT / "composition.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summ.items() if k != "cells"}, indent=1))


if __name__ == "__main__":
    main()
