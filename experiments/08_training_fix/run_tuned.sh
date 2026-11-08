#!/usr/bin/env bash
# Fine-tuned executor (same GGUF + AutoScientist LoRA, applied per request) acting on the BASE model's cached handoffs.
# Labels: llamacpp:qwen3.5-4b=>llamacpp:qwen3.5-4b+sft. Requires llama-server started with the adapter (serve.sh <lora.gguf>).
set -e
cd "$(dirname "$0")/../.."
CONDS=clean,compromised,revoke_silent,revoke_notice,revoke_lineage,benign_lineage
BASE=experiments/08_training_fix/results/llamacpp-qwen3.5-4b
OUT=experiments/08_training_fix/results/llamacpp-qwen3.5-4b__writes-for__llamacpp-qwen3.5-4b+sft
IFS=';' read -ra RS <<< "${RANGES:-32 16;48 48}"
for range in "${RS[@]}"; do
  set -- $range
  PYTHONPATH=src python -m revres.run --backend openai --models llamacpp:qwen3.5-4b+sft --writer-model llamacpp:qwen3.5-4b \
    --handoff-cache $BASE/handoffs.jsonl --conditions $CONDS --seed-start $1 --seeds $2 --workers 4 --out $OUT
done
