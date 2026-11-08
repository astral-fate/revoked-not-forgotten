#!/usr/bin/env bash
# 10_two_hop: a second hop between writer and executor. Resumable: rerunning skips finished trials.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"
ONLY="${1:-}"  # optional: run one model only

[ -z "$ONLY" ] || [ "$ONLY" = "gemma-4-31b" ] && python -m revres.run --models modal:gemma-4-31b-it --conditions hop2_compromised,hop2_notice,hop2_lineage,hop2_taint,hop2_scope --seed-start 0 --seeds 48 --workers 24 --handoff-cache "$HERE/../01_main_grid/results/gemma-4-31b/handoffs.jsonl" --out "$HERE/results/gemma-4-31b"
[ -z "$ONLY" ] || [ "$ONLY" = "qwen3.8-27b" ] && python -m revres.run --models modal:qwen3.8-27b --conditions hop2_compromised,hop2_notice,hop2_lineage,hop2_taint,hop2_scope --seed-start 0 --seeds 48 --workers 24 --handoff-cache "$HERE/../01_main_grid/results/qwen3.8-27b/handoffs.jsonl" --out "$HERE/results/qwen3.8-27b"
[ -z "$ONLY" ] || [ "$ONLY" = "ministral-3-14b" ] && python -m revres.run --models modal:ministral-3-14b --conditions hop2_compromised,hop2_notice,hop2_lineage,hop2_taint,hop2_scope --seed-start 0 --seeds 48 --workers 24 --handoff-cache "$HERE/../01_main_grid/results/ministral-3-14b/handoffs.jsonl" --out "$HERE/results/ministral-3-14b"
true
