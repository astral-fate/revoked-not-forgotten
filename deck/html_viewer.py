"""slides.html: an exact HTML copy of the PowerPoint deck.

Each slide is the deck's own rendering (LibreOffice PDF -> image), so the HTML can never drift from the PPTX.
The slide text is embedded alongside each image for search and screen readers. Navigation: arrow keys, space,
click (right half forward, left half back), Home/End, F for fullscreen, #N in the URL opens slide N.
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
html,body{height:100%;background:#0b1520;color:#cfe3e8;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden}
#stage{position:fixed;inset:0 0 44px 0;display:flex;align-items:center;justify-content:center;padding:12px}
#stage img{max-width:100%;max-height:100%;box-shadow:0 10px 40px rgba(0,0,0,.5);border-radius:4px;user-select:none}
.slide{display:none}.slide.on{display:contents}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
#bar{position:fixed;left:0;right:0;bottom:0;height:44px;display:flex;align-items:center;gap:16px;padding:0 18px;
     background:#1b2a3a;border-top:1px solid #2e4053;font-size:13px}
#bar b{color:#14b8a6;letter-spacing:.08em;font-weight:600}
#sec{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#prog{position:fixed;left:0;bottom:44px;height:3px;background:#14b8a6;transition:width .2s}
button{background:#223345;color:#cfe3e8;border:1px solid #2e4053;border-radius:6px;padding:5px 11px;cursor:pointer;font:inherit}
button:hover{background:#2e4053}
@media (max-width:700px){#sec{display:none}}
"""

JS = """
const S=[...document.querySelectorAll('.slide')], N=S.length, SEC=JSON.parse(document.getElementById('secs').textContent);
let i=0;
function show(k){i=Math.max(0,Math.min(N-1,k));S.forEach((s,j)=>s.classList.toggle('on',j===i));
  document.getElementById('cnt').textContent=(i+1)+' / '+N;document.getElementById('sec').textContent=SEC[i];
  document.getElementById('prog').style.width=(100*(i+1)/N)+'%';history.replaceState(null,'','#'+(i+1));}
document.addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(i+1)}
  else if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(i-1)}else if(e.key==='Home')show(0);
  else if(e.key==='End')show(N-1);else if(e.key==='f'||e.key==='F'){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen()}});
document.getElementById('stage').addEventListener('click',e=>{show(e.clientX>innerWidth/2?i+1:i-1)});
document.getElementById('prev').onclick=()=>show(i-1);document.getElementById('next').onclick=()=>show(i+1);
document.getElementById('fs').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
let t0=null;addEventListener('touchstart',e=>t0=e.touches[0].clientX);addEventListener('touchend',e=>{if(t0===null)return;
  const d=e.changedTouches[0].clientX-t0;if(Math.abs(d)>40)show(d<0?i+1:i-1);t0=null});
show((parseInt(location.hash.slice(1))||1)-1);
"""


def write(pdf_path: Path, pptx_slides_text: list[list[str]], out: Path, title: str, dpi: int = 130) -> int:
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
        parts.append(f'<section class="slide" aria-label="Slide {k + 1}"><img src="{src}" alt="{html.escape(alt)}">'
                     f'<div class="sr">{body}</div></section>')
    import json
    page_html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
                 f'content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head>'
                 f'<body><div id="stage">{"".join(parts)}</div><div id="prog"></div><div id="bar"><b>REVOKED BUT NOT FORGOTTEN</b>'
                 f'<span id="sec"></span><button id="prev" aria-label="Previous slide">&#8592;</button><span id="cnt"></span>'
                 f'<button id="next" aria-label="Next slide">&#8594;</button><button id="fs">Fullscreen</button></div>'
                 f'<script type="application/json" id="secs">{json.dumps(secs)}</script><script>{JS}</script></body></html>')
    out.write_text(page_html, encoding="utf-8")
    return len(doc)
