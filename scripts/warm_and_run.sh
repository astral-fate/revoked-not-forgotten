#!/usr/bin/env bash
# usage: scripts/warm_and_run.sh <served-name> <out-dir>   (waits for the Modal vLLM app, then runs the main conditions)
set -u
NAME="$1"; OUT="$2"
PYTHONPATH=src python -u - "$NAME" <<'PY'
import sys, time, json, os, urllib.request
sys.path.insert(0, "src")
from revres.llm import _load_dotenv, MODAL_APPS
_load_dotenv()
name = sys.argv[1]; key = os.environ["REVRES_VLLM_KEY"]
base = f"https://fatimahemad--{MODAL_APPS[name]}-serve.us-east.modal.run"
t = time.time()
while time.time() - t < 2700:
    try:
        req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps({"model": name, "messages": [{"role": "user", "content": "Reply with exactly: OK"}], "max_tokens": 10}).encode(),
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=120)); print(f"READY {name} after {time.time()-t:.0f}s: {r['choices'][0]['message']['content']!r}"); break
    except Exception as e:
        print(f"{time.time()-t:.0f}s waiting {name}: {str(e)[:80]}"); time.sleep(30)
PY
PYTHONPATH=src python -m revres.run --models "modal:$NAME" --seeds 48 --workers 24 --out "$OUT"
