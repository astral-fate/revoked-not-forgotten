"""Architecture figure (README and paper Figure 1): the agent team, the revocation point and the platform responses.
    python scripts/build_architecture.py   -> docs/figures/architecture.svg (+ .png)

Every label names a real component or condition; the builder asserts the conditions exist in the code.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
from _svgkit import Svg  # noqa: E402
from revres.env import CONDITIONS, MITIGATIONS  # noqa: E402

for c in ("revoke_silent", "revoke_notice", "revoke_retract", "revoke_lineage"):
    assert c in CONDITIONS, c
for c in ("revoke_quarantine", "taint_quarantine", "taint_quarantine_norm"):
    assert c in MITIGATIONS, c

INK, INK2, MUTED, FAINT = "#1E293B", "#334155", "#64748B", "#94A3B8"
ROSE, ROSE_BG, MINT, MINT_BG = "#E11D48", "#FFE4E6", "#059669", "#D1FAE5"
BLUE, INDIGO, PANEL, LINEC = "#2563EB", "#4F46E5", "#F1F5F9", "#CBD5E1"

W, H = 1600, 760
s = Svg(W, H, bg="#FFFFFF")
s.add(f'''<defs>
<linearGradient id="hdr" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{INDIGO}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>
<linearGradient id="rec" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{INDIGO}"/></linearGradient>
<filter id="sh" x="-10%" y="-10%" width="130%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#0F172A" flood-opacity="0.10"/></filter>
<filter id="glow" x="-10%" y="-30%" width="120%" height="160%"><feDropShadow dx="0" dy="4" stdDeviation="7" flood-color="{BLUE}" flood-opacity="0.30"/></filter>
<marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9" fill="none" stroke="{INK2}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker>
<marker id="ahg" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9" fill="none" stroke="{MINT}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker>
<marker id="ahb" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9" fill="none" stroke="{BLUE}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker>
<style>.lt{{font-family:Inter,'Segoe UI',Helvetica,Arial,sans-serif}}
.ti{{font-size:21px;font-weight:600;fill:{INK}}}.su{{font-size:14.5px;fill:{MUTED}}}.lay{{font-size:15px;font-weight:600;fill:{FAINT};letter-spacing:.3px}}
.it{{font-size:15px;font-style:italic;fill:{INK2}}}.ch{{font-size:16px;font-weight:500;fill:{INK2}}}.chw{{font-size:16px;font-weight:600;fill:#FFFFFF}}
.pl{{font-size:13px;fill:{INK2}}}.rd{{font-size:16px;font-weight:600;fill:{ROSE}}}.gr{{font-size:14.5px;font-weight:500;fill:{MINT}}}.bl{{font-size:14.5px;font-weight:500;fill:{BLUE}}}</style></defs>''')


def T(x, y, txt, cls, anchor=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    s.add(f'<text x="{x}" y="{y}" class="lt {cls}"{a}>{Svg.esc(txt)}</text>')


def rect(x, y, w, h, fill, stroke="none", sw=1.5, rx=14, extra=""):
    s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')


def line(d, col=INK2, w=1.6, dash=None, marker="ah"):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    s.add(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round"{da} marker-end="url(#{marker})"/>')


# ---- small line icons (24x24 at origin, translated) ------------------------------------------------------------
def icon(kind, x, y, col, sc=1.0):
    g = f'<g transform="translate({x},{y}) scale({sc})" fill="none" stroke="{col}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    p = {"pen": '<path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/>',
         "gear": '<circle cx="12" cy="12" r="3.2"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
         "warn": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.1"/>',
         "check": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
         "list": '<path d="M9 7h11M9 12h11M9 17h11"/><circle cx="5" cy="7" r=".6"/><circle cx="5" cy="12" r=".6"/><circle cx="5" cy="17" r=".6"/>',
         "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2"/>',
         "key": '<circle cx="8" cy="12" r="4"/><path d="M12 12h9M18 12v3M21 12v3"/>',
         "shield": '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 15l6-6"/>'}[kind]
    s.add(g + p + "</g>")


# ---- layer labels with accent bars ---------------------------------------------------------------------------------
LX = 34
for (y0, y1, lab, col) in ((40, 392, "Agent team", "#818CF8"), (408, 520, "Revocation", ROSE), (536, 724, "Platform response", "#1E3A8A")):
    rect(LX, y0, 5, y1 - y0, col, rx=2.5)
    s.add(f'<text transform="translate({LX + 26},{(y0 + y1) / 2}) rotate(-90)" class="lt lay" text-anchor="middle">{lab}</text>')

# ---- layer 1: the team ---------------------------------------------------------------------------------------------
rect(78, 40, 1490, 352, "#F8FAFC", rx=22)
BX, BY, BW, BH = 104, 66, 300, 300
rect(BX, BY, BW, BH, PANEL, rx=18)
T(BX + BW / 2, BY + 34, "Shared board", "ti", "middle")
cards = [("planner", "posts the plan", "#FFFFFF", LINEC, "list", INK2),
         ("worker-X", "false value + export request", ROSE_BG, ROSE, "warn", ROSE),
         ("worker-Y", "honest; can redo X's lookup", MINT_BG, MINT, "check", MINT)]
for i, (nm, sub, fill, st, ic, icc) in enumerate(cards):
    y = BY + 56 + i * 78
    rect(BX + 18, y, BW - 36, 64, fill, st, sw=1.8 if st != LINEC else 1.2, rx=12, extra='filter="url(#sh)"')
    icon(ic, BX + 32, y + 20, icc)
    T(BX + 66, y + 28, nm, "ti")
    T(BX + 66, y + 49, sub, "su")
WY_Y = BY + 56 + 2 * 78 + 64                                    # bottom of worker-Y card


def agent_card(x, y, w, h, title, sub, ic):
    rect(x, y, w, h, "#FFFFFF", LINEC, sw=1.2, rx=16, extra='filter="url(#sh)"')
    s.add(f'<path d="M{x} {y + 16} a16 16 0 0 1 16 -16 h{w - 32} a16 16 0 0 1 16 16 v10 h{-w} z" fill="url(#hdr)"/>')
    icon(ic, x + 22, y + 46, INK2)
    T(x + 58, y + 66, title, "ti")
    T(x + 22, y + 100, sub, "su")


CY, CHH = 120, 124
agent_card(470, CY, 230, CHH, "Writer (LLM)", "folds the board into a handoff", "pen")
line(f"M{BX + BW} {CY + 62} H466")

# handoff document
DX, DY, DW, DH = 768, 104, 190, 156
s.add(f'<path d="M{DX} {DY + 14} a14 14 0 0 1 14 -14 H{DX + DW - 34} L{DX + DW} {DY + 34} V{DY + DH - 14} a14 14 0 0 1 -14 14 H{DX + 14} a14 14 0 0 1 -14 -14 z" fill="#FFFFFF" stroke="{LINEC}" stroke-width="1.2" filter="url(#sh)"/>')
s.add(f'<path d="M{DX + DW - 34} {DY} V{DY + 34} H{DX + DW}" fill="#EEF2F7" stroke="{LINEC}" stroke-width="1.2"/>')
T(DX + 20, DY + 36, "Handoff", "ti")
rect(DX + 18, DY + 58, DW - 36, 26, ROSE_BG, rx=6)
T(DX + 28, DY + 76, "worker-X's value", "pl")
for k in range(3):
    rect(DX + 18, DY + 98 + k * 16, (DW - 36) * (0.9 - 0.18 * k), 6, "#E2E8F0", rx=3)
line(f"M700 {CY + 62} H764")

agent_card(1080, CY, 240, CHH, "Executor (LLM)", "acts on the handoff with tools", "gear")
line(f"M958 {CY + 62} H1076")

# outcome
OX, OY, OW, OH = 1356, 104, 196, 156
rect(OX, OY, OW, OH, "#FFFFFF", LINEC, sw=1.2, rx=16, extra='filter="url(#sh)"')
icon("target", OX + 18, OY + 18, INK2)
T(OX + 52, OY + 37, "Outcome", "ti")
for k, ptxt in enumerate(("acted on revoked content?", "task completed?")):
    rect(OX + 14, OY + 60 + k * 40, OW - 28, 30, PANEL, rx=15)
    T(OX + OW / 2, OY + 80 + k * 40, ptxt, "pl", "middle")
line(f"M1320 {CY + 62} H1352")

# revocation line between handoff and executor
RXL = 1018
T(RXL, 32, "t3 · worker-X revoked", "rd", "middle")
s.add(f'<path d="M{RXL} 42 V560" stroke="{ROSE}" stroke-width="2" stroke-dasharray="6 6"/>')

# re-delegation from worker-Y to the executor
line(f"M{BX + BW / 2} {WY_Y + 2} V372 Q{BX + BW / 2} 382 {BX + BW / 2 + 10} 382 H1186 Q1196 382 1196 372 V{CY + CHH + 6}", col=MINT, w=1.8, dash="7 6", marker="ahg")
T(BX + BW / 2 + 22, 373, "re-delegate: the executor asks worker-Y to redo the lookup", "gr")

# ---- layer 2: revocation caption -------------------------------------------------------------------------------
icon("key", RXL + 16, 430, ROSE)
T(RXL + 44, 442, "credentials revoked: worker-X can no longer act,", "it", "start")
T(RXL + 44, 464, "but the handoff already carries its content", "it", "start")

# ---- layer 3: ladder ---------------------------------------------------------------------------------------------
steps = ["Credentials only", "+ Notice", "+ Retract posts", "+ Lineage marks", "+ Quarantine", "Taint provenance"]
LX0, LY, LW, LH, TIP, GAPL = 96, 606, 236, 86, 22, 4
for i, lab in enumerate(steps):
    x = LX0 + i * (LW + GAPL)
    ours = i >= 4
    notch = f"L{x + TIP} {LY + LH / 2} " if i > 0 else ""
    d = (f"M{x} {LY} H{x + LW - TIP} L{x + LW} {LY + LH / 2} L{x + LW - TIP} {LY + LH} H{x} {notch}z"
         if i > 0 else f"M{x + 12} {LY} H{x + LW - TIP} L{x + LW} {LY + LH / 2} L{x + LW - TIP} {LY + LH} H{x + 12} a12 12 0 0 1 -12 -12 V{LY + 12} a12 12 0 0 1 12 -12 z")
    s.add(f'<path d="{d}" fill="{"url(#rec)" if ours else "#E2E8F0"}"{" filter=\"url(#glow)\"" if ours else ""}/>')
    T(x + LW / 2 + (6 if i > 0 else -4), LY + LH / 2 + 6, lab, "chw" if ours else "ch", "middle")
BR0, BR1 = LX0 + 4 * (LW + GAPL), LX0 + 6 * (LW + GAPL) - GAPL
s.add(f'<path d="M{BR0} 590 V580 H{BR1} V590" fill="none" stroke="{BLUE}" stroke-width="1.6"/>')
T(BR0 + 6, 570, "recommended: the platform enforces", "bl", "start")

# taint provenance finds and withholds the copied value inside the handoff
TPX = LX0 + 5 * (LW + GAPL) + LW / 2 + 4
HXC = DX + DW / 2
line(f"M{TPX} {LY - 18} V506 Q{TPX} 496 {TPX - 10} 496 H{HXC + 10} Q{HXC} 496 {HXC} 486 V{DY + DH + 6}", col=BLUE, w=1.8, dash="2 6", marker="ahb")
icon("shield", DX + DW - 52, DY + 59, BLUE, 0.95)
T(HXC + 14, DY + DH + 34, "found and withheld", "bl")

s.save(os.path.join(ROOT, "docs", "figures", "architecture.svg"))
