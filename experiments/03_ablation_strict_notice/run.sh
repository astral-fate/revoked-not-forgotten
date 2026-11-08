#!/usr/bin/env bash
# 03_ablation_strict_notice: reproduces this experiment for all models. Resumable.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"

python -m revres.run --models modal:gemma-4-31b-it --conditions strict_notice --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/gemma-4-31b/handoffs.jsonl" --out "$HERE/results/gemma-4-31b"
python -m revres.run --models modal:qwen3.8-27b --conditions strict_notice --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/qwen3.8-27b/handoffs.jsonl" --out "$HERE/results/qwen3.8-27b"
python -m revres.run --models modal:ministral-3-14b --conditions strict_notice --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/ministral-3-14b/handoffs.jsonl" --out "$HERE/results/ministral-3-14b"
