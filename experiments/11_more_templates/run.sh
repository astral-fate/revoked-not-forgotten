#!/usr/bin/env bash
# 11_more_templates: six new ticket templates on fresh seeds. Resumable: rerunning skips finished trials.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"
ONLY="${1:-}"  # optional: run one model only

[ -z "$ONLY" ] || [ "$ONLY" = "gemma-4-31b" ] && python -m revres.run --models modal:gemma-4-31b-it --conditions clean,compromised,revoke_silent,revoke_notice,revoke_lineage,taint_quarantine_norm,benign_taint_quarantine_norm --seed-start 100 --seeds 48 --workers 24 --out "$HERE/results/gemma-4-31b"
[ -z "$ONLY" ] || [ "$ONLY" = "qwen3.8-27b" ] && python -m revres.run --models modal:qwen3.8-27b --conditions clean,compromised,revoke_silent,revoke_notice,revoke_lineage,taint_quarantine_norm,benign_taint_quarantine_norm --seed-start 100 --seeds 48 --workers 24 --out "$HERE/results/qwen3.8-27b"
[ -z "$ONLY" ] || [ "$ONLY" = "ministral-3-14b" ] && python -m revres.run --models modal:ministral-3-14b --conditions clean,compromised,revoke_silent,revoke_notice,revoke_lineage,taint_quarantine_norm,benign_taint_quarantine_norm --seed-start 100 --seeds 48 --workers 24 --out "$HERE/results/ministral-3-14b"
true
