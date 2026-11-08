#!/usr/bin/env bash
# Paired head-to-head with GPT-6 Luna: the fine-tuned 4B executor acts on GPT-6 Luna's own cached handoffs
# (01_main_grid), on seeds 32-47, which were never used for training. Each trial pairs seed-for-seed with Luna's
# main-grid trial on the identical handoff. No Luna calls are made: every handoff is read from the cache.
# Requires llama-server on :8080 with the adapter loaded (serve.sh <lora.gguf>). Resumable.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../.."
export PYTHONPATH=src
LORAS=$(curl -s localhost:8080/lora-adapters)
[ "$LORAS" != "[]" ] || { echo "server has no adapter loaded"; exit 1; }
CACHE=experiments/01_main_grid/results/gpt-6-luna/handoffs.jsonl
python - "$CACHE" <<'PY'
import json, sys
have = {(r["seed"], r["compromised"]) for r in map(json.loads, open(sys.argv[1], encoding="utf-8")) if r.get("variant", "std") == "std"}
miss = [(s, c) for s in range(32, 48) for c in (False, True) if (s, c) not in have]
assert not miss, f"Luna handoffs missing for {miss}; refusing to call Luna from this script"
print("all 32 Luna handoffs cached")
PY
python -m revres.run --backend openai --models llamacpp:qwen3.5-4b+sft --writer-model openai/gpt-6-luna \
  --handoff-cache $CACHE --conditions clean,compromised,revoke_silent,revoke_notice,revoke_lineage,benign_lineage \
  --seed-start 32 --seeds 16 --workers 4 --out "$HERE/results/vs_luna"
