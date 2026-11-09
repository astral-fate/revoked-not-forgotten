"""slides.html: an exact HTML copy of the PowerPoint deck.

Each slide is the deck's own rendering (LibreOffice PDF -> image), so the HTML can never drift from the PPTX.
The slide text is embedded alongside each image for search and screen readers.
One scrolling page: all slides top to bottom; a sticky bar shows the section and slide number; #N links to slide N.
"""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import pymupdf
from PIL import Image

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:56px}
body{background:#0b1520;color:#cfe3e8;font-family:'Segoe UI',system-ui,sans-serif}
#bar{position:sticky;top:0;z-index:5;height:44px;display:flex;align-items:center;gap:16px;padding:0 18px;
     background:rgba(27,42,58,.96);border-bottom:1px solid #2e4053;font-size:13px;backdrop-filter:blur(6px)}
#bar b{color:#14b8a6;letter-spacing:.08em;font-weight:600;white-space:nowrap}
#sec{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#cnt{white-space:nowrap;font-variant-numeric:tabular-nums}
#prog{position:sticky;top:44px;z-index:5;height:3px;background:#14b8a6;width:0;transition:width .15s}
#stage{width:100%;max-width:1400px;margin:0 auto;padding:18px 16px 60px;display:flex;flex-direction:column;gap:22px}
.slide{position:relative;width:100%;min-width:0}
.slide img{display:block;width:100%;height:auto;border-radius:6px;box-shadow:0 10px 36px rgba(0,0,0,.45)}
.num{position:absolute;top:8px;right:10px;font-size:11px;color:#5f6f80;background:rgba(255,255,255,.75);
     border-radius:10px;padding:1px 8px;text-decoration:none}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@media (max-width:700px){#bar b{display:none}#stage{gap:12px;padding:10px 8px 40px}}
"""

JS = """
const S=[...document.querySelectorAll('.slide')], N=S.length, SEC=JSON.parse(document.getElementById('secs').textContent);
function update(){let i=0;const y=56;S.forEach((s,j)=>{if(s.getBoundingClientRect().top<=y+innerHeight*0.35)i=j});
  document.getElementById('cnt').textContent=(i+1)+' / '+N;document.getElementById('sec').textContent=SEC[i];
  document.getElementById('prog').style.width=(100*(i+1)/N)+'%';}
addEventListener('scroll',update,{passive:true});addEventListener('resize',update);update();
"""


def write(pdf_path: Path, pptx_slides_text: list[list[str]], out: Path, title: str, dpi: int = 130,
          brand: str = "REVOKED BUT NOT FORGOTTEN") -> int:
    """Render every page of the deck PDF, embed it with its text, and write a self-contained slides.html."""
    doc = pymupdf.open(str(pdf_path))
    assert len(doc) == len(pptx_slides_text), f"PDF has {len(doc)} pages, deck has {len(pptx_slides_text)} slides"
    parts, secs, cur = [], [], "Revoked but Not Forgotten"
    for k, page in enumerate(doc):
        texts = pptx_slides_text[k]
        if len(texts) >= 2 and texts[0].isdigit() and len(texts[0]) == 2:      # a section divider: "NN", "SECTION N · ..."
            cur = texts[1].replace("  ", " ")
        secs.append(cur)
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=86, method=6)
        src = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
        alt = " · ".join(t.replace("\n", " ") for t in texts[:2])
        body = html.escape(" \n".join(texts))
        parts.append(f'<section class="slide" id="{k + 1}" aria-label="Slide {k + 1}"><img src="{src}" alt="{html.escape(alt)}" '
                     f'loading="{"eager" if k < 2 else "lazy"}"><a class="num" href="#{k + 1}">{k + 1}</a>'
                     f'<div class="sr">{body}</div></section>')
    import json
    page_html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
                 f'content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head>'
                 f'<body><div id="bar"><b>{html.escape(brand)}</b><span id="sec"></span><span id="cnt"></span></div>'
                 f'<div id="prog"></div><main id="stage">{"".join(parts)}</main>'
                 f'<script type="application/json" id="secs">{json.dumps(secs)}</script><script>{JS}</script></body></html>')
    out.write_text(page_html, encoding="utf-8")
    return len(doc)
