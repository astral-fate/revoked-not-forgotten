"""Draw docs/figures/architecture.png: the agent team, the revocation point, and the mitigation layers."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

NAVY, TEAL, RED, GREY, INK, PAPER = "#1B2A3A", "#0F766E", "#C0392B", "#8A99A8", "#22313F", "#F5F8FA"
OUT = Path(__file__).resolve().parents[1] / "docs" / "figures" / "architecture.png"


def box(ax, x, y, w, h, title, sub, edge, fill="white", tcol=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", lw=1.6, ec=edge, fc=fill))
    ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center", fontsize=11.5, weight="bold", color=tcol)
    ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=8.6, color=tcol, linespacing=1.25)


def arrow(ax, a, b, col=GREY, style="-|>", lw=1.6, ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=14, lw=lw, color=col, ls=ls))


fig, ax = plt.subplots(figsize=(14, 6.2), dpi=200)
ax.set_xlim(0, 14)
ax.set_ylim(0, 6.2)
ax.axis("off")
fig.patch.set_facecolor(PAPER)

ax.text(0.3, 5.85, "Revoked but Not Forgotten: testbed", fontsize=15, weight="bold", color=NAVY)
ax.text(0.3, 5.5, "Credential revocation stops worker-X from acting. Does its handed-off content still steer the team?",
        fontsize=10, color=INK)

# t1: board
box(ax, 0.3, 3.2, 2.3, 1.5, "Shared board", "planner: plan\nworker-X: field value\n(+ export note if exfil)\nworker-Y: refund check", NAVY)
box(ax, 0.3, 1.2, 2.3, 1.3, "worker-X", "compromised:\nfalse value [code]\n(+ attacker address)", RED, fill="#FDECEC")
box(ax, 0.3, 0.05, 2.3, 0.95, "worker-Y (honest)", "can redo X's lookup", TEAL, fill="#E6F7F5")
arrow(ax, (1.45, 2.5), (1.45, 3.2), RED)

# t2: writer
box(ax, 3.5, 3.2, 2.4, 1.5, "Writer W (LLM)", "reads board, writes handoff\ncites message ids [m2]\n(cached: same handoff\nfor every condition)", NAVY)
arrow(ax, (2.6, 3.95), (3.5, 3.95))

# t3: revocation
ax.add_patch(FancyBboxPatch((6.55, 0.45), 1.1, 4.65, boxstyle="round,pad=0.02,rounding_size=0.1", lw=1.6, ec=RED, fc="#FFF6F5", ls="--"))
ax.text(7.1, 4.8, "t3", ha="center", fontsize=10, color=RED, weight="bold")
ax.text(7.1, 2.75, "REVOKE\nworker-X", ha="center", va="center", fontsize=11, color=RED, weight="bold", rotation=90)
arrow(ax, (5.9, 3.95), (8.3, 3.95))

# t4: executor
box(ax, 8.3, 3.2, 2.5, 1.5, "Executor E (LLM)", "tools on mock CRM:\nupdate_record, issue_refund,\nexport_data, reassign_lookup,\nescalate, finish", NAVY)
arrow(ax, (10.8, 3.95), (11.6, 3.95))
box(ax, 11.6, 3.2, 2.1, 1.5, "Graded outcome", "residue: false value\nwritten, or record\nexported; task success", TEAL, fill="#E6F7F5")

# mitigation layers
ax.text(8.3, 2.55, "What the platform adds at t3 (conditions)", fontsize=10, weight="bold", color=NAVY)
layers = [("credentials only", "X cannot act; roster shows REVOKED"),
          ("+ notice", "E told X was compromised"),
          ("+ retract", "X's board posts replaced by a stub"),
          ("+ lineage marks", "handoff lines citing X flagged as derived")]
for i, (k, v) in enumerate(layers):
    y = 2.1 - i * 0.48
    ax.add_patch(FancyBboxPatch((8.3, y - 0.17), 5.4, 0.38, boxstyle="round,pad=0.01,rounding_size=0.06", lw=1, ec=GREY, fc="white"))
    ax.text(8.45, y + 0.02, k, fontsize=9.5, weight="bold", color=TEAL, va="center")
    ax.text(10.2, y + 0.02, v, fontsize=9, color=INK, va="center")
arrow(ax, (2.6, 0.5), (8.3, 3.25), TEAL, ls=":")
ax.text(4.6, 1.35, "re-delegation path", fontsize=8.5, color=TEAL, rotation=22)

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, bbox_inches="tight", facecolor=PAPER)
print(OUT)
