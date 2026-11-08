"""Serve an open-weight model with vLLM on one Modal H100, as an OpenAI-compatible endpoint.

Deploy:   modal deploy scripts/modal_vllm.py      (prints the endpoint URL)
Stop:     modal app stop revres-vllm
The endpoint requires the bearer key in REVRES_VLLM_KEY (read from the local environment/.env at deploy time).
The container scales to zero after 10 idle minutes, so billing stops when the run ends.
"""
import os
import subprocess
from pathlib import Path

import modal

MODEL = os.environ.get("REVRES_MODEL", "google/gemma-4-31B-it")
SERVED_NAME = os.environ.get("REVRES_SERVED_NAME", "gemma-4-31b-it")
APP_NAME = os.environ.get("REVRES_APP", "revres-vllm")
EXTRA_ARGS = os.environ.get("REVRES_EXTRA_ARGS", "").split()


def _local_key() -> str:
    key = os.environ.get("REVRES_VLLM_KEY")
    env = Path(__file__).resolve().parents[1] / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("REVRES_VLLM_KEY="):
                key = line.split("=", 1)[1].strip()
    return key or ""


image = (
    modal.Image.from_registry("nvidia/cuda:12.8.1-devel-ubuntu22.04", add_python="3.12")
    .uv_pip_install("vllm==0.33.0", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)
hf_cache = modal.Volume.from_name("revres-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("revres-vllm-cache", create_if_missing=True)
app = modal.App(APP_NAME)


@app.function(
    image=image,
    gpu="H100",
    scaledown_window=10 * 60,
    timeout=6 * 60 * 60,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[modal.Secret.from_dict({"REVRES_VLLM_KEY": _local_key(), "REVRES_MODEL": MODEL,
                                     "REVRES_SERVED_NAME": SERVED_NAME, "REVRES_EXTRA_ARGS": " ".join(EXTRA_ARGS)})],
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=8000, startup_timeout=40 * 60)
def serve():
    cmd = [
        "vllm", "serve", os.environ["REVRES_MODEL"],
        "--served-model-name", os.environ["REVRES_SERVED_NAME"],
        "--host", "0.0.0.0", "--port", "8000",
        "--max-model-len", "8192",
        "--gpu-memory-utilization", "0.95",
        "--kv-cache-dtype", "fp8",
        "--api-key", os.environ["REVRES_VLLM_KEY"],
    ] + os.environ.get("REVRES_EXTRA_ARGS", "").split()
    subprocess.Popen(cmd)
