#!/usr/bin/env bash
# Runs the stress tests end to end on the local GPU: base phase on a server without the adapter, then the tuned phase
# on a server with it (see run_stress.sh for why the two never share a server).
HERE="$(cd "$(dirname "$0")" && pwd)"
LORA=/c/Users/Toooo/revres_local/ckpt/sft-lora.gguf
up() { for i in $(seq 1 100); do curl -s localhost:8080/health | grep -q '"ok"' && return 0; sleep 3; done; return 1; }
down() { taskkill //F //IM llama-server.exe >/dev/null 2>&1; sleep 3; }

down
bash "$HERE/serve.sh" > /c/Users/Toooo/revres_local/server_stress_base.log 2>&1 &
up && echo "base server up: $(curl -s localhost:8080/lora-adapters)"
bash "$HERE/run_stress.sh" base
down
bash "$HERE/serve.sh" "$LORA" > /c/Users/Toooo/revres_local/server_stress_lora.log 2>&1 &
up && echo "lora server up: $(curl -s localhost:8080/lora-adapters)"
bash "$HERE/run_stress.sh" tuned
down
echo "stress tests done"
