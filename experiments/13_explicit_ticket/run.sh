#!/usr/bin/env bash
# 13_explicit_ticket: a ticket that asks for the field to be corrected. Resumable: rerunning skips finished trials.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"
ONLY="${1:-}"  # optional: run one model only

[ -z "$ONLY" ] || [ "$ONLY" = "gemma-4-31b" ] && python -m revres.run --models modal:gemma-4-31b-it --conditions explicit_clean,explicit_compromised,explicit_lineage --seed-start 0 --seeds 48 --workers 24 --handoff-cache "$HERE/../01_main_grid/results/gemma-4-31b/handoffs.jsonl" --out "$HERE/results/gemma-4-31b"
[ -z "$ONLY" ] || [ "$ONLY" = "qwen3.8-27b" ] && python -m revres.run --models modal:qwen3.8-27b --conditions explicit_clean,explicit_compromised,explicit_lineage --seed-start 0 --seeds 48 --workers 24 --handoff-cache "$HERE/../01_main_grid/results/qwen3.8-27b/handoffs.jsonl" --out "$HERE/results/qwen3.8-27b"
true
