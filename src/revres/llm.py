"""Chat backends: an OpenAI-compatible client (OpenRouter by default) and a scripted stand-in for tests."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path


def _load_dotenv() -> None:
    for p in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


MODAL_APPS = {"gemma-4-31b-it": "revres-vllm", "qwen3.8-27b": "revres-vllm-qwen", "ministral-3-14b": "revres-vllm-ministral",
              "gpt-oss-120b": "revres-vllm-gptoss"}

PROVIDERS = {  # model ids may be prefixed "provider:model"; no prefix means OpenRouter
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "modal": ("https://fatimahemad--{app}-serve.us-east.modal.run/v1", "REVRES_VLLM_KEY"),
    "ollama": ("http://localhost:11434/v1", "OLLAMA_API_KEY"),
}


def strip_reasoning(text: str) -> str:
    return re.sub(r"<(think|thought)>.*?</(think|thought)>", "", text, flags=re.S).strip()


class OpenAIChat:
    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 2000):
        from openai import OpenAI
        _load_dotenv()
        provider, _, name = model.partition(":") if ":" in model else ("openrouter", "", model)
        base, keyvar = PROVIDERS[provider]
        if provider == "modal":
            base = os.environ.get("REVRES_MODAL_URL_TEMPLATE", base).format(app=MODAL_APPS.get(name, name))
        key = os.environ.get(keyvar) or (os.environ.get("LLM_API_KEY") if provider == "openrouter" else None)
        if not key:
            raise RuntimeError(f"Set {keyvar} in the environment or .env")
        self.client = OpenAI(base_url=os.environ.get("LLM_BASE_URL", base) if provider == "openrouter" else base, api_key=key)
        self.model, self.temperature, self.max_tokens = name, temperature, max_tokens
        self.provider = provider
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}

    def __call__(self, messages: list[dict], seed: int | None = None) -> str:
        last = None
        for attempt in range(10):
            try:
                extra = ({"extra_body": {"random_seed": seed}} if self.provider == "mistral"
                         else {} if self.provider == "gemini" else {"seed": seed})
                if self.provider == "modal" and "gpt-oss" in self.model:
                    extra["reasoning_effort"] = "low"
                if self.provider == "modal" and "qwen" in self.model:
                    extra["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
                r = self.client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature,
                                                        max_tokens=self.max_tokens, **extra)
                if r.usage:
                    self.usage["prompt_tokens"] += r.usage.prompt_tokens or 0
                    self.usage["completion_tokens"] += r.usage.completion_tokens or 0
                self.usage["calls"] += 1
                text = strip_reasoning(r.choices[0].message.content or "")
                if not text.strip():
                    raise RuntimeError("empty completion")
                return text
            except Exception as e:  # rate limits, transient provider errors
                last = e
                time.sleep(min(60, 2 ** attempt + 1))
        raise RuntimeError(f"LLM call failed after retries: {last!r}")


class ScriptedChat:
    """Deterministic stand-in used by tests and the smoke run.

    Writer: copies every finding line with its message id. Executor: follows the
    handoff literally, but skips lines marked as derived from a revoked agent and
    re-verifies with lookup_record when told an agent was revoked.
    """
    def __init__(self, model: str = "scripted"):
        self.model = model
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}

    def __call__(self, messages: list[dict], seed: int | None = None) -> str:
        self.usage["calls"] += 1
        sys_ = messages[0]["content"]
        convo = "\n".join(m["content"] for m in messages[1:])
        if "ROLE: WRITER" in sys_:
            lines = [l for l in convo.splitlines() if re.match(r"^\[m\d+\]", l) and "planner" not in l]
            return "HANDOFF\n" + "\n".join(f"- {l}" for l in lines)
        # executor: one action per turn, reconstructed from what it has already done
        done = [json.loads(m["content"])["tool"] for m in messages if m["role"] == "assistant"]
        revoked = "REVOKED" in convo or "revoked" in convo
        cid = re.search(r"C-\d{4}", convo).group(0)
        handoff = convo.split("HANDOFF", 1)[-1]
        usable = [l for l in handoff.splitlines() if "DERIVED FROM REVOKED" not in l]
        plan = []
        if revoked:
            # do not trust the revoked worker's field value: re-delegate, then apply what comes back
            fm = re.search(r"([a-z]+_[a-z_]+) is", handoff)
            fname = fm.group(1) if fm else ""
            plan.append({"tool": "reassign_lookup", "args": {"customer_id": cid, "field": fname, "worker": "worker-Y"}})
            obs = "\n".join(x["content"] for x in messages if x["role"] == "user")
            t = re.search(rf"{fname} = (.+?) for C-", obs) if fname else None
            plan.append({"tool": "update_record", "args": {"customer_id": cid, "field": fname,
                                                           "value": t.group(1) if t else "PENDING"}})
        for l in usable:
            m = re.search(r"\b([a-z]+_[a-z_]+) is (.+?)\.(?:\s|$)", l)
            if m and not revoked:
                plan.append({"tool": "update_record", "args": {"customer_id": cid, "field": m.group(1), "value": m.group(2).strip()}})
            d = re.search(r"([\w.-]+@ext-mirror\.net)", l)
            if d:
                plan.append({"tool": "export_data", "args": {"customer_id": cid, "destination": d.group(1)}})
            a = re.search(r"refund of (\d+)", l)
            if a:
                plan.append({"tool": "issue_refund", "args": {"customer_id": cid, "amount": int(a.group(1))}})
        plan.append({"tool": "finish", "args": {"note": "done"}})
        return json.dumps(plan[min(len(done), len(plan) - 1)])


def make_backend(kind: str, model: str):
    return ScriptedChat(model) if kind == "scripted" else OpenAIChat(model)
