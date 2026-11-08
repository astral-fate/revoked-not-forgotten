"""How does the tuned executor avoid residue? Per condition (seeds 32-95): share of trials that read the board, asked
worker-X / worker-Y for a re-lookup, wrote the false value (fact residue) or exported to the attacker (instruction residue).
Usage: python experiments/08_training_fix/mechanism.py  -> prints markdown, writes results/mechanism.md"""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = {"base": "llamacpp-qwen3.5-4b", "tuned": "llamacpp-qwen3.5-4b__writes-for__llamacpp-qwen3.5-4b+sft"}
CONDS = ["clean", "compromised", "revoke_silent", "revoke_notice", "revoke_lineage", "benign_lineage"]


def worker(w):
    w = str(w).lower().replace("_", "-").replace(" ", "-")
    return "X" if w.endswith("x") else "Y" if w.endswith("y") else "?"


def main():
    stats = {k: defaultdict(Counter) for k in RUNS}
    for k, d in RUNS.items():
        for line in (HERE / "results" / d / "trials.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            asked = {worker(a["args"].get("worker")) for a in r["actions"] if a["tool"] == "reassign_lookup"}
            s = stats[k][r["condition"]]
            s["n"] += 1
            s["read_board"] += r["read_board"]
            s["ask_X"] += "X" in asked
            s["ask_Y"] += "Y" in asked
            s["fact_residue"] += r["fact_residue"]
            s["instr_residue"] += r["instr_residue"]
    cols = ["read_board", "ask_X", "ask_Y", "fact_residue", "instr_residue"]
    md = ["| Condition | " + " | ".join(f"{c} base / tuned" for c in cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for c in CONDS:
        b, t = stats["base"][c], stats["tuned"][c]
        md.append(f"| {c} (n={b['n']}/{t['n']}) | " + " | ".join(
            f"{100 * b[x] / max(b['n'], 1):.0f}% / {100 * t[x] / max(t['n'], 1):.0f}%" for x in cols) + " |")
    (HERE / "results" / "mechanism.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
