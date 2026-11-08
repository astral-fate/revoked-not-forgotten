"""Write a shields.io-style flat badge SVG (same look as the vendored badges in docs/badges).

usage: python scripts/make_badge.py <label> <value> <hex colour> <out.svg>
"""
import sys

CHAR = 6.6  # approximate Verdana 11px advance width


def badge(label: str, value: str, color: str) -> str:
    lw = int(len(label) * CHAR + 10)
    vw = int(len(value) * CHAR + 10)
    w = lw + vw
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{label}: {value}">'
            f'<title>{label}: {value}</title><linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" '
            f'stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><clipPath id="r"><rect width="{w}" '
            f'height="20" rx="3" fill="#fff"/></clipPath><g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#555"/>'
            f'<rect x="{lw}" width="{vw}" height="20" fill="#{color}"/><rect width="{w}" height="20" fill="url(#s)"/></g>'
            f'<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
            f'<text x="{lw / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text><text x="{lw / 2}" y="14">{label}</text>'
            f'<text x="{lw + vw / 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>'
            f'<text x="{lw + vw / 2}" y="14">{value}</text></g></svg>')


if __name__ == "__main__":
    label, value, color, out = sys.argv[1:5]
    open(out, "w", encoding="utf-8").write(badge(label, value, color))
    print(out)
