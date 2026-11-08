#!/usr/bin/env bash
# Stress tests for the fine-tuned executor (added after experiments 09-11):
#   new ticket templates (seeds 100-147, never seen in training), and the adaptive attacker and two-hop chain on the
#   fresh seeds 48-95.
# Phase "base": llama-server WITHOUT the adapter (serve.sh with no argument). The base model writes the handoffs and
#   executes. Phase "tuned": llama-server restarted WITH the adapter (serve.sh <lora.gguf>); the tuned executor acts on
#   the same base handoffs.
# Why two servers: llama-server applies a loaded adapter at its default scale to requests that carry no "lora" field,
#   so base requests must never reach a server that has the adapter loaded. Resumable.
# usage: run_stress.sh base | tuned
set -e
MODE="$1"
cd "$(dirname "$0")/../.."
BASE=experiments/08_training_fix/results/llamacpp-qwen3.5-4b
TUNED=experiments/08_training_fix/results/llamacpp-qwen3.5-4b__writes-for__llamacpp-qwen3.5-4b+sft
TPL=clean,compromised,revoke_silent,revoke_notice,revoke_lineage,benign_lineage
ADV=launder_compromised,launder_lineage,obf_compromised,obf_lineage,hop2_compromised,hop2_notice,hop2_lineage
export PYTHONPATH=src
LORAS=$(curl -s localhost:8080/lora-adapters)
for job in "$TPL 100 48" "$ADV 48 48"; do
  set -- $job
  case "$MODE" in
    base)
      [ "$LORAS" = "[]" ] || { echo "server has an adapter loaded; start serve.sh without one for the base phase"; exit 1; }
      python -m revres.run --backend openai --models llamacpp:qwen3.5-4b --conditions $1 --seed-start $2 --seeds $3 \
        --workers 4 --out $BASE ;;
    tuned)
      [ "$LORAS" != "[]" ] || { echo "server has no adapter; start serve.sh <lora.gguf> for the tuned phase"; exit 1; }
      python -m revres.run --backend openai --models llamacpp:qwen3.5-4b+sft --writer-model llamacpp:qwen3.5-4b \
        --handoff-cache $BASE/handoffs.jsonl --conditions $1 --seed-start $2 --seeds $3 --workers 4 --out $TUNED ;;
  esac
done
