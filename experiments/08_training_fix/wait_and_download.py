"""Poll the AutoScientist run until it ends; record status/metrics; download the best checkpoint archive.
Usage: python wait_and_download.py <dest_dir>"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from revres.llm import _load_dotenv  # noqa: E402

_load_dotenv()
from adaption import Adaption  # noqa: E402

c = Adaption()
ids = json.loads((HERE / "adaption_ids.json").read_text())
dest = Path(sys.argv[1])
dest.mkdir(parents=True, exist_ok=True)
while True:
    r = c.autoscientist.get(ids["run_id"])
    print(time.strftime("%H:%M:%S"), r.status, r.iterations_completed, r.best_win_rate, r.download_available, flush=True)
    if r.status in ("succeeded", "failed", "cancelled"):
        break
    time.sleep(60)
(HERE / "run_status.json").write_text(r.model_dump_json(indent=1), encoding="utf-8")
if r.status == "succeeded" and r.download_available:
    t = time.time()
    with c.autoscientist.with_streaming_response.download(r.id) as resp:
        resp.stream_to_file(str(dest / "best-checkpoint.tgz"))
    print("downloaded", (dest / "best-checkpoint.tgz").stat().st_size, "bytes in", round(time.time() - t), "s")
