#!/usr/bin/env bash
# Base Qwen3.5-4B (local llama-server, Q4_K_M) as writer AND executor. Held-out seeds 32-47 first, then fresh 48-95.
# Requires: llama-server on :8080 (see README, serve.sh). Resumable: re-run to finish/retry.
set -e
cd "$(dirname "$0")/../.."
CONDS=clean,compromised,revoke_silent,revoke_notice,revoke_lineage,benign_lineage
OUT=experiments/08_training_fix/results/llamacpp-qwen3.5-4b
for range in "32 16" "48 48"; do
  set -- $range
  PYTHONPATH=src python -m revres.run --backend openai --models llamacpp:qwen3.5-4b --conditions $CONDS \
    --seed-start $1 --seeds $2 --workers 4 --out $OUT
done
