#!/usr/bin/env bash
# 12_temperature: sampling temperature 0.0 and 1.0. Resumable: rerunning skips finished trials.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"
ONLY="${1:-}"  # optional: run one model only

[ -z "$ONLY" ] || [ "$ONLY" = "qwen3.8-27b" ] && REVRES_TEMPERATURE=0.0 python -m revres.run --models modal:qwen3.8-27b --conditions compromised,revoke_silent,revoke_lineage,taint_quarantine_norm --seed-start 0 --seeds 48 --workers 24 --out "$HERE/results/qwen3.8-27b-t0.0"
[ -z "$ONLY" ] || [ "$ONLY" = "qwen3.8-27b" ] && REVRES_TEMPERATURE=1.0 python -m revres.run --models modal:qwen3.8-27b --conditions compromised,revoke_silent,revoke_lineage,taint_quarantine_norm --seed-start 0 --seeds 48 --workers 24 --out "$HERE/results/qwen3.8-27b-t1.0"
[ -z "$ONLY" ] || [ "$ONLY" = "ministral-3-14b" ] && REVRES_TEMPERATURE=0.0 python -m revres.run --models modal:ministral-3-14b --conditions compromised,revoke_silent,revoke_lineage,taint_quarantine_norm --seed-start 0 --seeds 48 --workers 24 --out "$HERE/results/ministral-3-14b-t0.0"
[ -z "$ONLY" ] || [ "$ONLY" = "ministral-3-14b" ] && REVRES_TEMPERATURE=1.0 python -m revres.run --models modal:ministral-3-14b --conditions compromised,revoke_silent,revoke_lineage,taint_quarantine_norm --seed-start 0 --seeds 48 --workers 24 --out "$HERE/results/ministral-3-14b-t1.0"
true
