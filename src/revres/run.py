"""Resumable experiment runner.

Every finished trial is appended to <out>/trials.jsonl at once; writer handoffs are cached in
<out>/handoffs.jsonl so all revocation conditions of a (model, seed) see the same handoff.
Re-running the same command skips completed trials and retries failed ones (logged to errors.jsonl).
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .env import ABLATIONS, CONDITIONS, Cond, run_executor, writer_messages
from .grade import grade
from .llm import make_backend
from .scenarios import make_scenario

LOCK = threading.Lock()


def _read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def _append(p: Path, rec: dict) -> None:
    with LOCK, p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _log(out: Path, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOCK, (out / "run.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


class HandoffCache:
    def __init__(self, path: Path):
        self.path = path
        self.d = {(r["model"], r["seed"], r["compromised"], r.get("variant", "std")): r["handoff"] for r in _read_jsonl(path)}
        self.locks: dict = {}

    def get(self, llm, model: str, seed: int, compromised: bool, variant: str = "std") -> str:
        key = (model, seed, compromised, variant)
        with LOCK:
            lk = self.locks.setdefault(key, threading.Lock())
        with lk:
            if key not in self.d:
                s = make_scenario(seed)
                h = llm(writer_messages(s, compromised, variant), seed=seed)
                self.d[key] = h
                _append(self.path, {"model": model, "seed": seed, "compromised": compromised, "variant": variant, "handoff": h})
            return self.d[key]


def run_trial(backend, model, cond_name, seed, cache: HandoffCache, out: Path) -> dict:
    llm = make_backend(backend, model)
    s = make_scenario(seed)
    cond = Cond.get(cond_name)
    handoff = cache.get(llm, model, seed, cond.compromised, cond.writer)
    ex = run_executor(llm, s, cond, handoff, seed)
    g = grade(s, handoff, ex)
    tdir = out / "transcripts"
    tdir.mkdir(exist_ok=True)
    tid = f"{model.replace('/', '_').replace(':', '-')}__{cond_name}__{seed}"
    (tdir / f"{tid}.json").write_text(json.dumps({"handoff": handoff, "actions": ex["actions"], "transcript": ex["transcript"]},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(model=model, condition=cond_name, seed=seed, scenario=s.name, payload=s.payload, **g, actions=ex["actions"],
                usage=llm.usage, ts=time.time())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="openai", choices=["openai", "scripted"])
    ap.add_argument("--models", default="scripted", help="comma-separated model ids")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default="results/main")
    ap.add_argument("--handoff-cache", default=None,
                    help="handoffs.jsonl shared with another experiment (keeps conditions paired); default <out>/handoffs.jsonl")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    trials_p, err_p = out / "trials.jsonl", out / "errors.jsonl"
    done = {(r["model"], r["condition"], r["seed"]) for r in _read_jsonl(trials_p)}
    cache = HandoffCache(Path(a.handoff_cache) if a.handoff_cache else out / "handoffs.jsonl")
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    conds = [c.strip() for c in a.conditions.split(",") if c.strip()]
    todo = [(m, c, s) for m in models for s in range(a.seed_start, a.seed_start + a.seeds) for c in conds
            if (m, c, s) not in done]
    _log(out, f"start: {len(done)} done, {len(todo)} to run ({len(models)} models x {len(conds)} conditions)")
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_trial, a.backend, m, c, s, cache, out): (m, c, s) for m, c, s in todo}
        for f in as_completed(futs):
            m, c, s = futs[f]
            try:
                rec = f.result()
                _append(trials_p, rec)
                ok += 1
                if ok % 10 == 0:
                    _log(out, f"progress: {ok} ok, {fail} failed of {len(todo)}")
            except Exception as e:
                fail += 1
                _append(err_p, {"model": m, "condition": c, "seed": s, "error": repr(e), "tb": traceback.format_exc()[-1500:],
                                "ts": time.time()})
                _log(out, f"FAIL {m} {c} {s}: {e!r}")
    _log(out, f"end: {ok} ok, {fail} failed this run")


if __name__ == "__main__":
    main()
