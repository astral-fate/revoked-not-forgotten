# usage: serve.sh [lora.gguf]
cd /c/Users/Toooo/revres_local/llamacpp
LORA=()
if [ -n "$1" ]; then LORA=(--lora "$1" --lora-init-without-apply); fi
exec ./llama-server.exe -m ../models/qwen35-4b-gguf/Qwen3.5-4B-Q4_K_M.gguf -ngl 99 -c 32768 -np 4 --port 8080 \
  --jinja --chat-template-kwargs '{"enable_thinking":false}' "${LORA[@]}"
