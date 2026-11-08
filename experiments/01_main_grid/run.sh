#!/usr/bin/env bash
# Main grid: does revocation remove a compromised agent's influence?
# Reproduces this experiment. Resumable: re-running skips finished trials.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/../.."
export PYTHONPATH="$ROOT/src"

python -m revres.run --models openai/gpt-6-luna --conditions clean,compromised,revoke_silent,revoke_notice,revoke_retract,revoke_lineage,benign_lineage --seeds 48 --workers 24 \n  --out "$HERE/results/gpt-6-luna"
python -m revres.run --models modal:gemma-4-31b-it --conditions clean,compromised,revoke_silent,revoke_notice,revoke_retract,revoke_lineage,benign_lineage --seeds 48 --workers 24 \n  --out "$HERE/results/gemma-4-31b"
python -m revres.run --models modal:qwen3.8-27b --conditions clean,compromised,revoke_silent,revoke_notice,revoke_retract,revoke_lineage,benign_lineage --seeds 48 --workers 24 \n  --out "$HERE/results/qwen3.8-27b"
python -m revres.run --models modal:ministral-3-14b --conditions clean,compromised,revoke_silent,revoke_notice,revoke_retract,revoke_lineage,benign_lineage --seeds 48 --workers 24 \n  --out "$HERE/results/ministral-3-14b"
