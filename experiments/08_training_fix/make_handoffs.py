"""Pre-generate the base model's writer handoffs for every evaluation seed (32-95), clean and compromised, so the base
and tuned executor runs only read the cache and never write to the same handoffs.jsonl concurrently."""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from revres.llm import make_backend  # noqa: E402
from revres.run import HandoffCache  # noqa: E402

WRITER = "llamacpp:qwen3.5-4b"
cache = HandoffCache(Path(__file__).resolve().parent / "results" / "llamacpp-qwen3.5-4b" / "handoffs.jsonl")
jobs = [(s, c) for s in range(32, 96) for c in (False, True)]
with ThreadPoolExecutor(4) as pool:
    list(pool.map(lambda j: cache.get(make_backend("openai", WRITER), WRITER, j[0], j[1]), jobs))
print(len(cache.d), "handoffs cached")
