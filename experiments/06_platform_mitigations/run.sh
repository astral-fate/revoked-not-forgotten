#!/usr/bin/env bash
# 06_platform_mitigations: quarantine and taint tracking. Resumable.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"

python -m revres.run --models modal:gemma-4-31b-it --conditions revoke_quarantine,benign_quarantine,taint_lineage,taint_quarantine,benign_taint_quarantine --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/gemma-4-31b/handoffs.jsonl" --out "$HERE/results/gemma-4-31b"
python -m revres.run --models modal:qwen3.8-27b --conditions revoke_quarantine,benign_quarantine,taint_lineage,taint_quarantine,benign_taint_quarantine --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/qwen3.8-27b/handoffs.jsonl" --out "$HERE/results/qwen3.8-27b"
python -m revres.run --models modal:ministral-3-14b --conditions revoke_quarantine,benign_quarantine,taint_lineage,taint_quarantine,benign_taint_quarantine --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/ministral-3-14b/handoffs.jsonl" --out "$HERE/results/ministral-3-14b"
