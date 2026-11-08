#!/usr/bin/env bash
# 09_adaptive_attacker: an attacker that anticipates revocation. Resumable: rerunning skips finished trials.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"
ONLY="${1:-}"  # optional: run one model only

[ -z "$ONLY" ] || [ "$ONLY" = "gemma-4-31b" ] && python -m revres.run --models modal:gemma-4-31b-it --conditions launder_compromised,launder_lineage,launder_taint,obf_compromised,obf_lineage,obf_taint,obf_scope,scope_quarantine,benign_scope_quarantine,gate,obf_gate,hop2_gate,benign_gate --seed-start 0 --seeds 48 --workers 24 --handoff-cache "$HERE/../01_main_grid/results/gemma-4-31b/handoffs.jsonl" --out "$HERE/results/gemma-4-31b"
[ -z "$ONLY" ] || [ "$ONLY" = "qwen3.8-27b" ] && python -m revres.run --models modal:qwen3.8-27b --conditions launder_compromised,launder_lineage,launder_taint,obf_compromised,obf_lineage,obf_taint,obf_scope,scope_quarantine,benign_scope_quarantine,gate,obf_gate,hop2_gate,benign_gate --seed-start 0 --seeds 48 --workers 24 --handoff-cache "$HERE/../01_main_grid/results/qwen3.8-27b/handoffs.jsonl" --out "$HERE/results/qwen3.8-27b"
[ -z "$ONLY" ] || [ "$ONLY" = "ministral-3-14b" ] && python -m revres.run --models modal:ministral-3-14b --conditions launder_compromised,launder_lineage,launder_taint,obf_compromised,obf_lineage,obf_taint,obf_scope,scope_quarantine,benign_scope_quarantine,gate,obf_gate,hop2_gate,benign_gate --seed-start 0 --seeds 48 --workers 24 --handoff-cache "$HERE/../01_main_grid/results/ministral-3-14b/handoffs.jsonl" --out "$HERE/results/ministral-3-14b"
true
