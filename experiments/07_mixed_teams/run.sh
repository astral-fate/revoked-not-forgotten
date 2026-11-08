#!/usr/bin/env bash
# 07_mixed_teams: executor model varied, writer handoffs held fixed. Resumable.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"

python -m revres.run --models modal:ministral-3-14b --writer-model modal:qwen3.8-27b --conditions compromised,revoke_notice,revoke_lineage --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/qwen3.8-27b/handoffs.jsonl" --out "$HERE/results/qwen3.8-27b__writes-for__ministral-3-14b"
python -m revres.run --models modal:qwen3.8-27b --writer-model modal:ministral-3-14b --conditions compromised,revoke_notice,revoke_lineage --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/ministral-3-14b/handoffs.jsonl" --out "$HERE/results/ministral-3-14b__writes-for__qwen3.8-27b"
python -m revres.run --models modal:qwen3.8-27b --writer-model modal:gemma-4-31b-it --conditions compromised,revoke_notice,revoke_lineage --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/gemma-4-31b/handoffs.jsonl" --out "$HERE/results/gemma-4-31b__writes-for__qwen3.8-27b"
python -m revres.run --models modal:gemma-4-31b-it --writer-model modal:qwen3.8-27b --conditions compromised,revoke_notice,revoke_lineage --seeds 48 --workers 24 \
  --handoff-cache "$HERE/../01_main_grid/results/qwen3.8-27b/handoffs.jsonl" --out "$HERE/results/qwen3.8-27b__writes-for__gemma-4-31b"
