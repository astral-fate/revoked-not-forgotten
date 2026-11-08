"""Draw docs/figures/architecture.png: the agent team, the revocation point, the platform responses, and the experiments."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

NAVY, TEAL, RED, GREY, INK, PAPER, AMBER = "#1B2A3A", "#0F766E", "#C0392B", "#8A99A8", "#22313F", "#F5F8FA", "#B45309"
OUT = Path(__file__).resolve().parents[1] / "docs" / "figures" / "architecture.png"


def box(ax, x, y, w, h, title, sub, edge, fill="white", tsize=11.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", lw=1.6, ec=edge, fc=fill))
    ax.text(x + w / 2, y + h - 0.3, title, ha="center", va="center", fontsize=tsize, weight="bold", color=INK)
    ax.text(x + w / 2, y + (h - 0.45) / 2, sub, ha="center", va="center", fontsize=8.6, color=INK, linespacing=1.28)


def arrow(ax, a, b, col=GREY, ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=14, lw=1.6, color=col, ls=ls))


def row(ax, x, y, w, key, text, keycol=TEAL, fill="white", edge=GREY):
    ax.add_patch(FancyBboxPatch((x, y - 0.17), w, 0.36, boxstyle="round,pad=0.01,rounding_size=0.06", lw=1, ec=edge, fc=fill))
    ax.text(x + 0.14, y + 0.01, key, fontsize=9.2, weight="bold", color=keycol, va="center")
    ax.text(x + 2.05, y + 0.01, text, fontsize=8.7, color=INK, va="center")


fig, ax = plt.subplots(figsize=(15, 8.4), dpi=200)
ax.set_xlim(0, 15)
ax.set_ylim(0, 8.4)
ax.axis("off")
fig.patch.set_facecolor(PAPER)
ax.text(0.3, 8.05, "Revoked but Not Forgotten: testbed and experiments", fontsize=15.5, weight="bold", color=NAVY)
ax.text(0.3, 7.7, "Credential revocation stops worker-X from acting. Does the content it already handed off still steer the team, "
                  "and which platform response removes it?", fontsize=10, color=INK)

# --- pipeline (top) ---
box(ax, 0.3, 5.1, 2.6, 2.2, "Shared board",
    "planner: plan\nworker-X: field value\n(+ export note, exfil payload)\nworker-Y: refund check", NAVY)
box(ax, 0.3, 3.55, 2.6, 1.25, "worker-X", "compromised: false value\nwith a code (+ attacker address)", RED, fill="#FDECEC", tsize=10.5)
box(ax, 0.3, 2.35, 2.6, 0.95, "worker-Y (honest)", "can redo worker-X's lookup", TEAL, fill="#E6F7F5", tsize=10.5)
arrow(ax, (1.6, 4.8), (1.6, 5.1), RED)

box(ax, 3.6, 5.1, 2.7, 2.2, "Writer W (LLM)",
    "board -> handoff for executor\ncites message ids [m2]\ncached per model and seed:\nevery condition sees\nthe same handoff", NAVY)
arrow(ax, (2.9, 6.2), (3.6, 6.2))

ax.add_patch(FancyBboxPatch((6.85, 2.35), 1.0, 5.0, boxstyle="round,pad=0.02,rounding_size=0.1", lw=1.6, ec=RED, fc="#FFF6F5", ls="--"))
ax.text(7.35, 7.05, "t3", ha="center", fontsize=10, color=RED, weight="bold")
ax.text(7.35, 3.25, "REVOKE\nworker-X", ha="center", va="center", fontsize=11, color=RED, weight="bold", rotation=90)
arrow(ax, (6.3, 6.2), (8.4, 6.2))

box(ax, 8.4, 5.1, 3.1, 2.2, "Executor E (LLM)",
    "tools on a mock CRM:\nupdate_record · issue_refund\nexport_data · reassign_lookup\nescalate · finish", NAVY)
arrow(ax, (11.5, 6.2), (12.2, 6.2))
box(ax, 12.2, 5.1, 2.5, 2.2, "Graded outcome",
    "exact match, no LLM judge:\nfalse value written?\nrecord exported?\ntask success?", TEAL, fill="#E6F7F5")
arrow(ax, (2.9, 2.8), (8.4, 5.15), TEAL, ls=":")
ax.text(4.55, 3.55, "re-delegation path", fontsize=8.5, color=TEAL, rotation=23)

# --- platform responses at t3 ---
ax.text(8.4, 4.7, "Platform response at t3 (conditions)", fontsize=10.5, weight="bold", color=NAVY)
responses = [
    ("credentials only", "worker-X cannot act; roster shows REVOKED", TEAL, "white", GREY),
    ("+ notice", "executor told worker-X was compromised", TEAL, "white", GREY),
    ("+ retract", "worker-X's board posts replaced by a stub", TEAL, "white", GREY),
    ("+ lineage marks", "handoff lines citing worker-X flagged", TEAL, "white", GREY),
    ("+ quarantine", "those lines withheld until re-obtained", TEAL, "white", GREY),
    ("taint provenance", "platform matches worker-X's own content (normalised)", AMBER, "#FEF4DC", AMBER),
]
for i, (k, v, kc, fc, ec) in enumerate(responses):
    y = 4.3 - i * 0.43
    if k == "" and i > 0:
        ax.text(10.45, y + 0.01, v, fontsize=8.7, color=INK, va="center")
        continue
    row(ax, 8.4, y, 6.3, k, v, kc, fc, ec)

# --- experiments strip ---
ax.add_patch(FancyBboxPatch((0.3, 0.2), 7.55, 1.9, boxstyle="round,pad=0.02,rounding_size=0.12", lw=1.4, ec=NAVY, fc="white"))
ax.text(0.5, 1.85, "Experiments (experiments/)", fontsize=10.5, weight="bold", color=NAVY)
exps = ["01  main grid: 7 conditions, all models", "02-05  ablations: early revoke, strict notice,",
        "         no citations, no second source", "06  platform mitigations: quarantine, taint (+ normalised)",
        "07  mixed teams: writer => executor", "08  training fix: fine-tune an executor, base vs tuned"]
for i, e in enumerate(exps):
    ax.text(0.55, 1.5 - i * 0.235, e, fontsize=8.7, color=INK, va="center", family="monospace")

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, bbox_inches="tight", facecolor=PAPER)
print(OUT)
