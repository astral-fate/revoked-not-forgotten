"""svgkit: the small drawing kit behind the research figures (architecture diagrams, before/after comparisons,
results panels). Plain SVG strings, no dependencies; a headless Chrome / Edge / Chromium renders the PNG.

    from svgkit import Svg, ACCENT, BASE, UP, DOWN, SAME
    s = Svg(1600, 900)
    s.text(60, 62, "Title", "h1")
    ...
    s.save("figure.svg")            # writes figure.svg and figure.png (2x, sharp enough for tickets and slides)

Coordinates are pixels on a 1600-wide canvas. Text classes (h1, h2, h3, t, t2, t2b, s, tag, hw, m, big) are defined
once in STYLE so every figure shares one type scale.
"""
import os, shutil, subprocess

# ---- colour tokens: each colour has one job ----------------------------------------------------------------------
INK, INK2, MUTED = "#0F172A", "#1E293B", "#475569"           # text: titles, body, secondary
LINE, GRID, PANEL, PAGE = "#CBD5E1", "#E2E8F0", "#F1F5F9", "#F8FAFC"
ACCENT, ACCENT_BG = "#2563EB", "#EFF6FF"                      # the new thing / "after"
BASE = "#64748B"                                              # the baseline / "before" (always a hollow ring or grey)
UP, DOWN, SAME = "#047857", "#B91C1C", "#94A3B8"              # better / worse / no change (always with ▲ ▼ = text)
NAVY = "#1E293B"                                              # group header bars
# secondary categorical hues, in this fixed order, for up to 4 extra series
TEAL, PURPLE, AMBER = "#0E7490", "#6D28D9", "#D97706"
GREY, BLUE, GREEN, RED = SAME, ACCENT, UP, DOWN               # aliases used by older builders

STYLE = '''<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker><style>
.h1{font-size:34px;font-weight:700;fill:#0F172A}.h2{font-size:23px;font-weight:700;fill:#0F172A}
.h3{font-size:17px;font-weight:700;fill:#0F172A}.t{font-size:15px;fill:#1E293B}.t2{font-size:14px;fill:#1E293B}
.t2b{font-size:14px;font-weight:700;fill:#0F172A}.s{font-size:13px;fill:#475569}.th{font-size:13px;font-weight:700;fill:#FFFFFF}
.tag{font-size:12px;font-weight:700;fill:#FFFFFF}.hw{font-size:19px;font-weight:700;fill:#FFFFFF}
.m{font-family:Consolas, monospace;font-size:13px;fill:#1E293B}.big{font-size:40px;font-weight:700}
</style></defs>'''

# rough text widths (px per character) for layout arithmetic, measured on Chrome renders of Segoe UI and set ~5%
# wide so estimates err towards "too long"; all-caps labels run wider, so give them extra room
CHAR_W = {"h1": 16.0, "h2": 11.5, "h3": 9.2, "t": 6.9, "t2": 6.6, "t2b": 7.1, "s": 6.1, "tag": 6.9, "hw": 9.9,
          "m": 7.2, "big": 21.0}


def text_width(s, cls="t"):
    """Estimated rendered width in px; good enough to place labels and size chips, not for kerning."""
    return len(s) * CHAR_W.get(cls, 8.0)


def find_browser():
    """A headless-capable Chromium browser: $SVG_BROWSER, then Chrome / Edge / Chromium in the usual places."""
    env = os.environ.get("SVG_BROWSER")
    cands = [env] if env else []
    cands += [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    cands += [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge")]
    return next((c for c in cands if c and os.path.exists(c)), None)


def render_png(svg_path, w, h, scale=2, png_path=None):
    """Screenshot the SVG with a headless browser at `scale`x. Returns the PNG path, or None if no browser."""
    b = find_browser()
    if not b:
        print("no Chrome/Edge/Chromium found: set SVG_BROWSER to render the PNG")
        return None
    png = png_path or os.path.splitext(svg_path)[0] + ".png"
    url = "file:///" + os.path.abspath(svg_path).replace("\\", "/").lstrip("/")
    subprocess.run([b, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--force-device-scale-factor={scale}",
                    f"--window-size={w},{h}", f"--screenshot={os.path.abspath(png)}", url],
                   capture_output=True, timeout=180)
    if not os.path.exists(png):
        raise RuntimeError(f"browser did not write {png}")
    return png


class Svg:
    def __init__(self, w, h, bg=PAGE):
        self.W, self.H, self.o = w, h, []
        self.add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
                 'font-family="Segoe UI, Helvetica, Arial, sans-serif">')
        self.add(STYLE)
        self.add(f'<rect width="{w}" height="{h}" fill="{bg}"/>')
        self._back = len(self.o)          # insertion point for things that must sit behind everything else

    def add(self, s):
        self.o.append(s)

    def add_behind(self, s):
        """Insert just above the page background (gridlines drawn late but meant to sit under the marks)."""
        self.o.insert(self._back, s)
        self._back += 1

    @staticmethod
    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ---- primitives ------------------------------------------------------------------------------------------------
    def text(self, x, y, s, cls="t", anchor=None, fill=None):
        a = f' text-anchor="{anchor}"' if anchor else ""
        f = f' style="fill:{fill}"' if fill else ""
        self.add(f'<text x="{x}" y="{y}" class="{cls}"{a}{f}>{self.esc(s)}</text>')

    def lines(self, x, y, rows, cls="t", gap=21, anchor=None):
        """Several lines of text from y downward; returns the y below the last line."""
        for i, r in enumerate(rows):
            self.text(x, y + i * gap, r, cls, anchor)
        return y + len(rows) * gap

    def box(self, x, y, w, h, fill, stroke=LINE, rx=12, sw=1, dash=False):
        d = ' stroke-dasharray="7 5"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{d}/>')

    def bar(self, x, y, w, h, fill, rx=4):
        self.add(f'<rect x="{x}" y="{y}" width="{max(0, w):.1f}" height="{h}" rx="{rx}" fill="{fill}"/>')

    def arrow(self, x1, y1, x2, y2, dash=False, col="#334155"):
        d = ' stroke-dasharray="6 4"' if dash else ""
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="2"{d} '
                 'marker-end="url(#ar)"/>')

    def path(self, d, col="#334155", dash=False, arrow=True, width=2):
        da = ' stroke-dasharray="7 5"' if dash else ""
        me = ' marker-end="url(#ar)"' if arrow else ""
        self.add(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{width}"{da}{me}/>')

    def chip(self, x, y, label, col, w=None):
        """Rounded pill with white bold text; returns its width so chips can be laid in a row."""
        w = w or 14 + 7.6 * len(label)
        self.add(f'<rect x="{x}" y="{y}" width="{w:.0f}" height="22" rx="11" fill="{col}"/>')
        self.text(x + w / 2, y + 15, label, "tag", "middle")
        return w

    # ---- composite pieces -----------------------------------------------------------------------------------------
    def node(self, x, y, w, h, title, sub="", fill=GRID, stroke=LINE, sw=1, sub2="", dash=False):
        """A pipeline box: bold title, up to two small lines under it, centred."""
        self.box(x, y, w, h, fill, stroke, rx=10, sw=sw, dash=dash)
        off = -4 if not sub2 else -12
        self.text(x + w / 2, y + h / 2 + off, title, "h3", "middle")
        if sub:
            self.text(x + w / 2, y + h / 2 + off + 21, sub, "s", "middle")
        if sub2:
            self.text(x + w / 2, y + h / 2 + off + 39, sub2, "s", "middle")

    def card(self, x, y, w, h, title, col):
        """White panel with a coloured title band (used for the two sides of a before/after architecture)."""
        self.box(x, y, w, h, "#FFFFFF", col, rx=12, sw=2)
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="44" rx="12" fill="{col}"/>')
        self.add(f'<rect x="{x}" y="{y + 30}" width="{w}" height="14" fill="{col}"/>')
        self.text(x + 24, y + 30, title, "hw")

    def group_bar(self, x, y, w, label, h=34):
        """Dark full-width header that starts a group of rows (e.g. one benchmark)."""
        self.box(x, y, w, h, NAVY, NAVY, rx=6)
        self.text(x + 16, y + h / 2 + 7, label, "hw")
        return y + h

    def legend(self, x, y, items, gap=36):
        """items: (kind, colour, label), kind in 'dot' | 'ring' | 'swatch'. Laid left to right; returns end x."""
        for kind, col, lab in items:
            if kind == "ring":
                self.add(f'<circle cx="{x + 8}" cy="{y}" r="7" fill="#FFFFFF" stroke="{col}" stroke-width="2.5"/>')
            elif kind == "dot":
                self.add(f'<circle cx="{x + 8}" cy="{y}" r="8" fill="{col}" stroke="#FFFFFF" stroke-width="2"/>')
            else:
                self.bar(x, y - 7, 16, 14, col, rx=3)
            self.text(x + 24, y + 5, lab, "t2")
            x += 24 + text_width(lab, "t2") + gap
        return x

    def hbars(self, x, y, w, title, rows, vmax, fmt, label_w=230, note=None, gap=30):
        """rows: (label, value, colour[, bold]). Bars drawn to one scale (0..vmax), value printed at the bar end."""
        self.text(x, y, title, "h3")
        bw = w - label_w - 90
        for i, r in enumerate(rows):
            lab, v, col = r[:3]
            yy = y + 22 + i * gap
            self.text(x, yy + 15, lab, "t2b" if len(r) > 3 and r[3] else "t2")
            self.bar(x + label_w, yy, bw, 20, GRID)
            self.bar(x + label_w, yy, max(2, bw * v / vmax), 20, col)
            self.text(x + label_w + bw + 8, yy + 15, fmt(v), "t2b")
        if note:
            self.text(x, y + 22 + len(rows) * gap + 14, note, "s")
        return y + 22 + len(rows) * gap + (30 if note else 8)

    def table(self, x, y, w, cols, rows, head_col="#1D4ED8", row_h=40, bold_first=True, colours=None):
        """cols: (name, x_offset, align 'l'|'r'); a '|' in a name breaks the header line. colours: {(i, j): fill}."""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="44" rx="6" fill="{head_col}"/>')
        for name, dx, al in cols:
            parts = name.split("|")
            for k, ln in enumerate(parts):
                self.text(x + dx, y + 18 + k * 16 + (8 if len(parts) == 1 else 0), ln, "th", "end" if al == "r" else None)
        for i, r in enumerate(rows):
            yy = y + 44 + i * row_h
            if i % 2:
                self.add(f'<rect x="{x}" y="{yy}" width="{w}" height="{row_h}" fill="{PANEL}"/>')
            for j, (v, (_, dx, al)) in enumerate(zip(r, cols)):
                fill = (colours or {}).get((i, j))
                self.text(x + dx, yy + row_h / 2 + 5, str(v), "t2b" if (j == 0 and bold_first) or fill else "t2",
                          "end" if al == "r" else None, fill=fill)
        return y + 44 + len(rows) * row_h

    def dumbbell(self, x0, x1, cy, before, after, vmin=0.0, vmax=100.0, fmt="{:.1f}%", higher_is_better=True,
                 labels=True, r=8):
        """One before -> after row: hollow grey ring (before), filled accent dot (after), joined by a line coloured
        by direction (green better, red worse, grey unchanged). Value labels sit outside the pair so they never
        collide. Returns (delta, colour) for the change chip."""
        sx = lambda v: x0 + (x1 - x0) * (v - vmin) / (vmax - vmin)
        bx, ax = sx(before), sx(after)
        d = after - before
        better = d > 0 if higher_is_better else d < 0
        col = SAME if abs(d) < 1e-9 else (UP if better else DOWN)
        self.add(f'<line x1="{bx:.1f}" y1="{cy}" x2="{ax:.1f}" y2="{cy}" stroke="{col}" stroke-width="4" '
                 'stroke-linecap="round"/>')
        self.add(f'<circle cx="{bx:.1f}" cy="{cy}" r="{r - 1}" fill="#FFFFFF" stroke="{BASE}" stroke-width="2.5"/>')
        self.add(f'<circle cx="{ax:.1f}" cy="{cy}" r="{r}" fill="{ACCENT}" stroke="#FFFFFF" stroke-width="2"/>')
        if labels:
            if abs(d) < 1e-9:
                self.text(ax + r + 6, cy + 5, fmt.format(after), "t2b")
            else:
                (lo, lv, lo_after), (hi, hv, hi_after) = sorted([(bx, before, False), (ax, after, True)])
                self.text(lo - r - 5, cy + 5, fmt.format(lv), "t2b" if lo_after else "s", "end",
                          None if lo_after else BASE)
                self.text(hi + r + 5, cy + 5, fmt.format(hv), "t2b" if hi_after else "s", None,
                          None if hi_after else BASE)
        return d, col

    def change_chip(self, x, cy, d, col, fmt="{:.1f}", w=78):
        """▲ +x / ▼ −x / = 0 chip. The glyph and sign carry the numeric direction; the colour (from dumbbell) says
        whether that direction is good, so it stays right when lower is better (time, tokens)."""
        if col == SAME:
            lab = "= " + fmt.format(0)
        else:
            lab = f"{'▲ +' if d > 0 else '▼ −'}{fmt.format(abs(d))}"
        return self.chip(x, cy - 11, lab, col, w=w)

    def gridlines(self, xs, y0, y1, labels=None, label_y=None, cls="s"):
        """Faint dashed verticals behind the marks, optional tick labels above."""
        for i, x in enumerate(xs):
            self.add_behind(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}" stroke="{GRID}" stroke-width="1" '
                            'stroke-dasharray="3 4"/>')
            if labels:
                self.text(x, label_y if label_y is not None else y0 - 10, labels[i], cls, "middle")

    # ---- output ----------------------------------------------------------------------------------------------------
    def save(self, path, png=True, scale=2):
        """Write the SVG and (by default) a PNG beside it at `scale`x. Returns (svg_path, png_path or None)."""
        if not self.o[-1] == "</svg>":
            self.add("</svg>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.o))
        print("wrote", path)
        p = render_png(path, self.W, self.H, scale=scale) if png else None
        if p:
            print("wrote", p)
        return path, p
