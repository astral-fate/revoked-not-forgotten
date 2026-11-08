"""Print the values the README quotes, read from paper/numbers.tex and paper/numbers_ext.tex (no hand-typed numbers)."""
import re
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "paper"
TXT = (P / "numbers.tex").read_text(encoding="utf-8") + (P / "numbers_ext.tex").read_text(encoding="utf-8")
M = dict(re.findall(r"\\csname rv@([^\\]+)\\endcsname\{(.*)\}\s*$", TXT, flags=re.M))


def g(k):
    v = M.get(k, "?").replace("\\%", "%").replace("$", "").replace("{\\times}", "×")
    return re.sub(r"10\^\{(-?\d+)\}", r"10^\1", v)


if __name__ == "__main__":
    print(g("models/list"), "| main trials", g("n/main"), "| all trials", g("n/trials"))
    for s in ["luna", "oss", "glm", "qwen", "gemma", "ministral", "dsflash", "all"]:
        print(s, [g(f"{s}/{c}/any/pct") for c in ["compromised", "revoke_silent", "revoke_notice", "revoke_retract", "revoke_lineage"]],
              "clean→alarm", g(f"{s}/clean/task/pct"), g(f"{s}/benign_lineage/task/pct"))
    for s in ["luna", "qwen", "gemma", "ministral"]:
        print("abl/mit", s, {c: g(f"{s}/{c}/any/pct") for c in ["early_revoke", "strict_notice", "nocite_lineage", "taint_lineage",
                                                                 "revoke_quarantine", "taint_quarantine", "taint_quarantine_norm"]})
    print("taint norm range", g("mitrange/taint_quarantine_norm/any"), "| nocite range", g("mitrange/nocite_lineage/any"))
