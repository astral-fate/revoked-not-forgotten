"""Pre-flight checks for a figure SVG, run before you look at the PNG. Catches the mistakes that cost the most
re-renders: text running off the canvas, labels too small to read, internal codes left in the body, and text that
probably overlaps other text on the same baseline.

    python check_svg.py figure.svg [--footer-y 1150]

Exit code 0 = no errors (warnings may still print). It estimates text widths, so treat overlaps as "look here",
then confirm on the rendered PNG.
"""
import argparse, re, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, __import__("os").path.dirname(__file__))
from _svgkit import CHAR_W  # noqa: E402

SIZE = {"h1": 34, "h2": 23, "h3": 17, "t": 15, "t2": 14, "t2b": 14, "s": 13, "th": 13, "tag": 12, "hw": 19, "m": 13,
        "big": 40, "pill": 13, "pillb": 15, "lbl": 13, "val": 13}
CODE = re.compile(r"\b(E\d{1,2}[a-z]?|rr_e\d+\w*|m3\w*_e\d+\w*|sel_e\d+\w*|e\d+q)\b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--footer-y", type=float, default=None, help="text below this y counts as footer (codes allowed)")
    a = ap.parse_args()
    root = ET.parse(a.svg).getroot()
    W, H = float(root.get("width")), float(root.get("height"))
    footer = a.footer_y if a.footer_y is not None else H - 60
    ns = "{http://www.w3.org/2000/svg}"
    errors, warns, spans = [], [], []
    for el in root.iter(f"{ns}text"):
        s = "".join(el.itertext())
        if not s.strip():
            continue
        x, y = float(el.get("x", 0)), float(el.get("y", 0))
        cls = el.get("class", "t")
        w = len(s) * CHAR_W.get(cls, 8.0)
        anchor = el.get("text-anchor", "start")
        x0 = x - w if anchor == "end" else (x - w / 2 if anchor == "middle" else x)
        x1 = x0 + w
        if x0 < 0 or x1 > W + 2:
            errors.append(f"off canvas ({x0:.0f}..{x1:.0f} of {W:.0f}) y={y:.0f}: {s[:70]!r}")
        if y > H - 4:
            errors.append(f"below canvas y={y:.0f} of {H:.0f}: {s[:70]!r}")
        if SIZE.get(cls, 14) < 12:
            warns.append(f"small text ({SIZE.get(cls)} px): {s[:60]!r}")
        if y < footer and CODE.search(s):
            warns.append(f"internal code in body text (keep codes in the footer): {s[:70]!r}")
        spans.append((round(y), x0, x1, s))
    spans.sort()
    for i, (y, x0, x1, s) in enumerate(spans):
        for y2, a0, a1, s2 in spans[i + 1:]:
            if y2 != y:
                break
            if a0 < x1 - 4 and x0 < a1 - 4:
                warns.append(f"possible overlap at y={y}: {s[:35]!r} / {s2[:35]!r}")
    for e in errors:
        print("ERROR", e)
    for w_ in warns:
        print("WARN ", w_)
    print(f"{a.svg}: {len(spans)} text elements, {len(errors)} errors, {len(warns)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
