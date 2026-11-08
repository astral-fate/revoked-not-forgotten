#!/usr/bin/env bash
# Ablation: revoke before the handoff
# Reproduces this experiment. Resumable: re-running skips finished trials.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/../.."
export PYTHONPATH="$ROOT/src"

python -m revres.run --models modal:gemma-4-31b-it --conditions early_revoke --seeds 48 --workers 24 \n  --handoff-cache "$HERE/../01_main_grid/results/gemma-4-31b/handoffs.jsonl" --out "$HERE/results/gemma-4-31b"
