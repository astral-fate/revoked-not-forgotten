"""Architecture figure for the README: the agent team, the revocation point, the platform responses and the
experiments.  python scripts/build_architecture.py  -> docs/figures/architecture.svg (+ .png)

Conditions and experiment folders are read from the code and the repository so the figure cannot drift from them.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
from _svgkit import ACCENT, ACCENT_BG, DOWN, LINE, MUTED, PANEL, UP, Svg  # noqa: E402
from revres.env import CONDITIONS, MITIGATIONS  # noqa: E402

# the figure names these conditions and folders; fail if the code no longer has them
for c in ("revoke_silent", "revoke_notice", "revoke_retract", "revoke_lineage"):
    assert c in CONDITIONS, c
for c in ("revoke_quarantine", "taint_quarantine", "taint_quarantine_norm"):
    assert c in MITIGATIONS, c
EXPS = ["01_main_grid", "02_ablation_early_revoke", "03_ablation_strict_notice", "04_ablation_no_citation",
        "05_ablation_no_second_source", "06_platform_mitigations", "07_mixed_teams", "08_training_fix"]
for e in EXPS:
    assert os.path.isdir(os.path.join(ROOT, "experiments", e)), e

W, H = 1600, 1040
RED_BG, GREEN_BG = "#FEF2F2", "#ECFDF5"
s = Svg(W, H)
t = s.text

# ------------------------------------------------------------------ title
t(60, 58, "Revoked but not forgotten: how a revoked agent keeps steering the team", "h1")
t(60, 92, "A compromised worker's content is handed on before it is revoked. We measure whether the executor still "
          "acts on it, and which platform response removes it.", "t")
x = 60
for lab, col in (("compromised agent", DOWN), ("honest agent", UP), ("design the paper argues for", ACCENT)):
    x += s.chip(x, 110, lab, col) + 10

# ------------------------------------------------------------------ 1 the team
Y1 = 182
t(60, Y1, "1 · The agent team and the moment of revocation", "h2")

# board card with its three posters
BX, BY, BW, BH = 60, 206, 340, 222
s.box(BX, BY, BW, BH, "#FFFFFF", LINE, rx=12, sw=1.2)
t(BX + 20, BY + 32, "Shared team board", "h3")
rows = [("planner", "posts the plan for the ticket", PANEL, LINE),
        ("worker-X", "false value with a code (+ export request)", RED_BG, DOWN),
        ("worker-Y", "checks the refund; can redo X's lookup", GREEN_BG, UP)]
for i, (who, what, fill, stroke) in enumerate(rows):
    y = BY + 50 + i * 56
    s.box(BX + 16, y, BW - 32, 46, fill, stroke, rx=8, sw=1.4 if stroke != LINE else 1)
    t(BX + 30, y + 20, who, "t2b")
    t(BX + 30, y + 38, what, "s")
WY_MID = BY + 50 + 2 * 56 + 23            # vertical centre of the worker-Y row

# writer, revocation band, executor, grading
NY, NH = 262, 112
s.arrow(BX + BW, NY + NH / 2, 446, NY + NH / 2)
s.node(448, NY, 262, NH, "Writer (LLM)", "folds the board into a handoff", sub2="cites message ids; cached per seed")

RX, RW = 752, 92
s.box(RX, 206, RW, 196, "#FFF5F5", DOWN, rx=10, sw=1.6, dash=True)
t(RX + RW / 2, 232, "t3", "h3", "middle", fill=DOWN)
for i, ln in enumerate(("worker-X", "revoked")):
    t(RX + RW / 2, 258 + i * 18, ln, "t2b", "middle", fill=DOWN)

s.arrow(710, NY + NH / 2, 884, NY + NH / 2)
s.node(886, NY, 300, NH, "Executor (LLM)", "acts on the handoff with tools", sub2="update · refund · export · re-delegate · escalate")
s.arrow(1186, NY + NH / 2, 1224, NY + NH / 2)
s.node(1226, NY, 314, NH, "Graded by exact match", "false value written? record exported?", sub2="task completed? (no LLM judge)",
       fill=PANEL)

# re-delegation path from worker-Y to the executor, under the revocation band
s.path(f"M {BX + BW - 16} {WY_MID} C 620 {WY_MID + 70}, 980 {WY_MID + 70}, 1036 {NY + NH + 2}", col=UP, dash=True)
t(470, WY_MID + 82, "re-delegation: the executor asks worker-Y to redo the revoked lookup", "s", fill=UP)

# ------------------------------------------------------------------ 2 platform responses
Y2 = 532
t(60, Y2, "2 · What the platform does at t3: one condition each, adding up left to right", "h2")
steps = [("Credentials only", ["worker-X can no longer act;", "the roster shows it revoked"], False),
         ("+ Notice", ["the executor is told worker-X", "was compromised"], False),
         ("+ Retract", ["worker-X's posts are", "removed from the board"], False),
         ("+ Lineage marks", ["handoff lines that cite", "worker-X are flagged"], False),
         ("+ Quarantine", ["flagged lines are withheld", "until re-obtained"], True),
         ("Taint provenance", ["the platform finds derived lines", "by matching worker-X's content"], True)]
CW, GAP, CY, CH = 232, 17.6, 584, 116
s.chip(60 + 4 * (CW + GAP), CY - 32, "design the paper argues for: the platform enforces, the agent need not judge", ACCENT,
       w=2 * CW + GAP)
for i, (title, lines, ours) in enumerate(steps):
    x = 60 + i * (CW + GAP)
    s.box(x, CY, CW, CH, ACCENT_BG if ours else "#FFFFFF", ACCENT if ours else LINE, rx=10, sw=2 if ours else 1.2)
    t(x + 16, CY + 30, title, "h3")
    for j, ln in enumerate(lines):
        t(x + 16, CY + 58 + j * 20, ln, "s")
    if i < len(steps) - 1:
        s.arrow(x + CW + 2, CY + CH / 2, x + CW + GAP - 2, CY + CH / 2)
t(60, CY + CH + 28, "Taint provenance replaces the writer's citations: the platform matches what worker-X wrote "
                    "(normalised for case, digit grouping and spacing), so it works even when the writer cites nothing.", "s")

# ------------------------------------------------------------------ 3 experiments
Y3 = 782
t(60, Y3, "3 · Experiments", "h2")
exp_rows = [
    ("01_main_grid", "Does revocation remove the influence, and which response does? All seven conditions, every model."),
    ("02 to 05  ablations", "Why: revoke before the handoff · a notice that names derived content · no citations · no second source."),
    ("06_platform_mitigations", "Do quarantine and taint provenance work for every model, and what does a false alarm cost?"),
    ("07_mixed_teams", "Does the influence follow the agent that writes the handoff or the one that acts on it?"),
    ("08_training_fix", "Can fine-tuning the executor fix it? Base vs tuned model on held-out seeds."),
]
RY, RH = Y3 + 18, 38
for i, (folder, q) in enumerate(exp_rows):
    y = RY + i * RH
    if i % 2 == 0:
        s.box(60, y, W - 120, RH, PANEL, PANEL, rx=6)
    t(78, y + 24, folder, "m")
    t(370, y + 24, q, "t2")
y = RY + len(exp_rows) * RH + 30
t(60, y, "All services, addresses and credentials are mock. Each folder in experiments/ has its own README, config "
         "and run script; results and tests are in experiments/analysis/ and the paper.", "s", fill=MUTED)
assert y < H - 10, y

s.save(os.path.join(ROOT, "docs", "figures", "architecture.svg"))
