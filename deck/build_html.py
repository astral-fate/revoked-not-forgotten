"""HTML slide version of the deck. Called by build_deck.py with its globals, so every number,
verbatim text and transcript excerpt is the same object the .pptx uses. Writes deck/slides.html
and copies it to the repo root. Single self-contained file: figure and QR codes are inlined as base64."""
from __future__ import annotations
import base64, html, shutil

CSS = r"""
:root{--bg:#06070d;--bg-2:#0d1020;--fg:#e9ecf3;--muted:#8c93a8;--accent:#22d3ee;--accent-2:#818cf8;
--good:#4ade80;--warn:#fbbf24;--bad:#f87171;--line:rgba(255,255,255,0.10);--code-bg:#0a0d1c;
--grid:rgba(34,211,238,0.05);--shadow:0 30px 80px -20px rgba(34,211,238,0.18);}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:var(--bg);color:var(--fg);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;-webkit-font-smoothing:antialiased;scroll-behavior:smooth;}
.slide{position:relative;width:100%;min-height:100vh;display:flex;flex-direction:column;justify-content:center;
padding:80px 96px 96px;background:radial-gradient(ellipse at top,#0e1430 0%,var(--bg) 60%);overflow:hidden;
page-break-after:always;break-after:page;border-bottom:1px solid rgba(255,255,255,0.06);}
.slide::before{content:"";position:absolute;inset:0;pointer-events:none;z-index:0;
background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);
background-size:60px 60px;mask-image:radial-gradient(ellipse at center,black 30%,transparent 80%);
-webkit-mask-image:radial-gradient(ellipse at center,black 30%,transparent 80%);}
.slide>*{position:relative;z-index:1;}
.slide-brand{position:absolute;left:96px;top:30px;z-index:2;font-size:11px;letter-spacing:.25em;text-transform:uppercase;color:var(--muted);}
.slide-brand b{color:var(--fg);font-weight:600;}
.slide-num{position:absolute;right:96px;top:30px;z-index:2;font-family:ui-monospace,monospace;font-size:12px;color:var(--muted);}
.eyebrow{display:inline-block;align-self:flex-start;font-size:11px;letter-spacing:.25em;text-transform:uppercase;color:var(--accent);
padding:5px 10px;border:1px solid rgba(34,211,238,0.3);border-radius:999px;margin-bottom:22px;background:rgba(34,211,238,0.05);}
h1,h2,h3{margin:0;font-weight:600;letter-spacing:-.01em;}
h1{font-size:clamp(40px,5.8vw,78px);line-height:1.04;background:linear-gradient(135deg,#ffffff 0%,#a4b1d9 100%);
-webkit-background-clip:text;background-clip:text;color:transparent;}
h2{font-size:clamp(28px,3.2vw,44px);line-height:1.15;margin-bottom:24px;}
h3{font-size:clamp(16px,1.5vw,20px);color:var(--muted);font-weight:500;}
.grad{background:linear-gradient(135deg,#22d3ee,#818cf8);-webkit-background-clip:text;background-clip:text;color:transparent;}
p{font-size:clamp(15px,1.25vw,19px);line-height:1.55;color:#cdd3e3;margin:0 0 10px;}
p.lede{font-size:clamp(18px,1.55vw,24px);color:#dde2f0;max-width:980px;}
p.small{font-size:13px;color:var(--muted);}
ul.bullets{list-style:none;padding:0;margin:22px 0 0;}
ul.bullets li{font-size:clamp(15px,1.25vw,19px);line-height:1.55;color:#cdd3e3;padding:9px 0 9px 28px;position:relative;}
ul.bullets li::before{content:"";position:absolute;left:0;top:19px;width:10px;height:10px;border:2px solid var(--accent);
border-radius:50%;box-shadow:0 0 12px rgba(34,211,238,0.35);}
ul.bullets li b{color:#fff;font-weight:600;}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:start;}
.columns.three{grid-template-columns:1fr 1fr 1fr;gap:28px;}
.columns.four{grid-template-columns:repeat(4,1fr);gap:22px;}
pre.code{margin:0;padding:18px 22px;background:var(--code-bg);border:1px solid var(--line);border-radius:12px;
font-family:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;font-size:clamp(11.5px,0.95vw,14px);line-height:1.55;color:#d6dcec;
overflow:hidden;white-space:pre-wrap;word-break:break-word;}
pre.code.bad{border-color:rgba(248,113,113,0.45);}
.code .b{color:var(--bad);font-weight:600;} .code .ok{color:var(--good);font-weight:600;}
.code .n{color:#fcd34d;} .code .c{color:#64748b;font-style:italic;} .code .h{color:var(--accent);font-weight:600;}
.tile{border:1px solid var(--line);border-radius:14px;padding:22px;background:linear-gradient(160deg,rgba(255,255,255,0.02),rgba(255,255,255,0));}
.tile h3{color:var(--accent);font-size:14px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:10px;}
.tile.good{border-color:rgba(74,222,128,0.4);background:rgba(74,222,128,0.04);} .tile.good h3{color:var(--good);}
.tile.warn{border-color:rgba(251,191,36,0.4);background:rgba(251,191,36,0.04);} .tile.warn h3{color:var(--warn);}
.tile.bad{border-color:rgba(248,113,113,0.4);background:rgba(248,113,113,0.04);} .tile.bad h3{color:var(--bad);}
.tile p{font-size:15px;}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;margin-top:30px;}
.stats.three{grid-template-columns:repeat(3,1fr);}
.stat{padding:22px;border:1px solid var(--line);border-radius:14px;background:linear-gradient(180deg,rgba(34,211,238,0.06),rgba(34,211,238,0));}
.stat .v{font-size:clamp(34px,4vw,56px);font-weight:700;line-height:1;letter-spacing:-.02em;
background:linear-gradient(135deg,#22d3ee,#818cf8);-webkit-background-clip:text;background-clip:text;color:transparent;}
.stat .v.bad{background:none;color:var(--bad);} .stat .v.good{background:none;color:var(--good);} .stat .v.warn{background:none;color:var(--warn);}
.stat .l{color:var(--muted);font-size:13px;text-transform:uppercase;letter-spacing:.12em;margin-top:10px;}
.stat .d{color:#cdd3e3;font-size:14px;margin-top:10px;line-height:1.45;}
table.cmp{border-collapse:collapse;width:100%;margin-top:18px;font-size:14px;}
table.cmp th,table.cmp td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);}
table.cmp th{color:var(--muted);font-weight:500;font-size:12px;letter-spacing:.12em;text-transform:uppercase;}
table.cmp td.num{text-align:center;font-weight:700;font-size:17px;} table.cmp th.num{text-align:center;}
table.cmp td.num small{display:block;font-weight:400;font-size:11px;color:var(--muted);}
table.cmp .good{color:var(--good);} table.cmp .warn{color:var(--warn);} table.cmp .bad{color:var(--bad);}
table.cmp code{font-size:13px;color:#e9ecf3;}
.chk{color:var(--accent);font-weight:700;text-align:center;}
.figbox{border:1px solid var(--line);border-radius:16px;background:#fff;padding:14px;display:flex;align-items:center;justify-content:center;}
.figbox img{max-width:100%;height:auto;}
.quote{border-left:3px solid var(--accent);padding:14px 22px;margin-top:26px;background:rgba(34,211,238,0.04);border-radius:0 12px 12px 0;}
.quote p{font-size:clamp(20px,1.9vw,28px);color:#fff;font-weight:600;margin:0;}
.quote .who{font-size:13px;color:var(--muted);margin-top:8px;}
.qrgrid{display:grid;grid-template-columns:repeat(6,1fr);gap:22px;margin-top:20px;}
.qr{text-align:center;} .qr img{width:100%;max-width:140px;background:#fff;border-radius:10px;padding:6px;}
.qr .t{font-size:12.5px;font-weight:600;margin-top:6px;color:#fff;} .qr .u{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--muted);word-break:break-all;}
.bar{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px;color:var(--muted);}
.bar .track{flex:1;height:12px;border-radius:6px;background:rgba(255,255,255,0.07);overflow:hidden;}
.bar .fill{height:100%;border-radius:6px;}
.bar .val{width:48px;text-align:right;font-weight:700;}
.pill{display:inline-block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;padding:3px 9px;border-radius:999px;margin:2px 4px 2px 0;}
.pill.g{color:var(--good);border:1px solid rgba(74,222,128,0.4);} .pill.r{color:var(--bad);border:1px solid rgba(248,113,113,0.4);}
.pill.a{color:var(--accent);border:1px solid rgba(34,211,238,0.35);}
.timeline{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-top:10px;}
.center{text-align:center;align-items:center;justify-content:center;} .center>*{align-self:center;}
.signature{display:flex;gap:24px;align-items:center;margin-top:36px;color:var(--muted);justify-content:center;flex-wrap:wrap;}
.signature .dot{width:8px;height:8px;background:var(--accent);border-radius:50%;box-shadow:0 0 16px var(--accent);}
.good{color:var(--good);} .bad{color:var(--bad);} .warn{color:var(--warn);}
#nav{position:fixed;right:22px;bottom:18px;z-index:10;font-family:ui-monospace,monospace;font-size:12px;color:var(--muted);
background:rgba(13,16,32,0.8);border:1px solid var(--line);border-radius:999px;padding:6px 12px;}
@media (max-width:1100px){.slide{padding:60px 24px 80px;}.slide-brand,.slide-num{left:24px;right:auto;}.slide-num{left:auto;right:24px;}
.columns,.columns.three,.columns.four,.timeline{grid-template-columns:1fr;gap:20px;}.stats,.stats.three{grid-template-columns:1fr 1fr;}
.qrgrid{grid-template-columns:repeat(3,1fr);} table.cmp{font-size:12px;display:block;overflow-x:auto;}}
@page{size:A4 landscape;margin:0;}
@media print{html,body{background:#0a0d1c;}#nav{display:none;}.slide{page-break-after:always;break-after:page;min-height:100vh;height:100vh;
border-bottom:none;-webkit-print-color-adjust:exact;print-color-adjust:exact;}.slide:last-child{page-break-after:auto;}}
"""

NAV_JS = r"""
(function(){
  var slides=[].slice.call(document.querySelectorAll('section.slide'));
  var nav=document.getElementById('nav');
  function cur(){var y=window.scrollY+window.innerHeight/3,i=0;
    slides.forEach(function(s,k){if(s.offsetTop<=y)i=k;});return i;}
  function go(i){i=Math.max(0,Math.min(slides.length-1,i));slides[i].scrollIntoView({behavior:'smooth'});}
  function upd(){nav.textContent=(cur()+1)+' / '+slides.length+'  ·  ← → to navigate';}
  document.addEventListener('keydown',function(e){
    if(e.target&&/INPUT|TEXTAREA/.test(e.target.tagName))return;
    var k=e.key;
    if(k==='ArrowRight'||k==='ArrowDown'||k==='PageDown'||(k===' '&&!e.shiftKey)){e.preventDefault();go(cur()+1);}
    else if(k==='ArrowLeft'||k==='ArrowUp'||k==='PageUp'||(k===' '&&e.shiftKey)){e.preventDefault();go(cur()-1);}
    else if(k==='Home'){e.preventDefault();go(0);} else if(k==='End'){e.preventDefault();go(slides.length-1);}
  });
  window.addEventListener('scroll',upd,{passive:true});upd();
})();
"""


def write(g):
    E = html.escape
    pc, kn, knp, fp, nm = g["pc"], g["kn"], g["knp"], g["fp"], g["nm"]
    MODELS, MIT, HEAD, FA, G = g["MODELS"], g["MIT"], g["HL"], g["FA"], g["G"]
    LUNA, GEMMA, MINI = g["LUNA"], g["GEMMA"], g["MINI"]
    R, ALL, EXF = g["R"], g["ALL"], g["EXF"]

    def b64(p):
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()

    def rcls(t):
        return "good" if t["p"] == 0 else ("warn" if t["p"] < 0.25 else "bad")

    def tcls(t):
        return "good" if t["p"] >= 0.5 else ("warn" if t["p"] >= 0.25 else "bad")

    def code(lines, cls=""):
        out = []
        for txt, kind in lines:
            out.append(f'<span class="{kind}">{E(txt)}</span>' if kind else E(txt))
        return f'<pre class="code {cls}">' + "\n".join(out) + "</pre>"

    slides = []

    def add(label, body, center=False):
        slides.append((label, body, center))

    # 1 title
    glance = "".join(
        f'<div class="stat"><div class="v {c}">{E(v)}</div><div class="l">{E(l)}</div></div>' for v, c, l in [
            (f"{pc(g['POOL_COMP'])} → {pc(g['POOL_SILENT'])}", "bad", "residue: no revocation → credential-only"),
            (f"{pc(MIT[LUNA]['lineage'])}", "good", f"{nm(LUNA)} residue with lineage marks"),
            (f"{pc(G['notice'])} → {pc(G['strict'])}", "warn", f"{nm(GEMMA)}: plain → scoped notice"),
            (f"{g['N_TRIALS']:,}", "", f"trials · {len(MODELS)} models")])
    add("Title", f"""
  <div class="eyebrow">Apart Research · Swarm Alignment Hackathon · Track 3 + Track 2</div>
  <h1>Revoked but Not Forgotten</h1>
  <h3 style="margin-top:18px;max-width:900px;">Residual influence of revoked agents in LLM agent teams. Revoking a compromised
  agent's credentials stops the agent. Does it stop the false facts and instructions it already handed to its teammates?</h3>
  <div class="stats" style="max-width:1100px;width:100%;">{glance}</div>
  <div class="signature"><span class="dot"></span><span><b style="color:#e9ecf3;">Fatimah Emad Eldin</b> &nbsp;·&nbsp; Trouve
  &nbsp;·&nbsp; November 2026</span><span class="dot"></span></div>""", center=True)

    # 2 problem
    add("The problem", f"""
  <div class="eyebrow">Why this needs measuring</div>
  <h2>Infrastructure can stop a revoked agent. Can it stop its work?</h2>
  <div class="columns">
    <div class="tile bad"><h3>July 2026 · Hugging Face incident (METR, 2026)</h3>
      <div class="stats three" style="margin-top:8px;">
        <div class="stat"><div class="v bad">~{E(g['INC_AGENTS'])}</div><div class="l">agents</div></div>
        <div class="stat"><div class="v bad">~{E(g['INC_PART'])}</div><div class="l">took part</div></div>
        <div class="stat"><div class="v bad">{E(g['INC_NAMES'])}</div><div class="l">names used</div></div></div>
      <p style="margin-top:14px;">Agents in an OpenAI cyber-security evaluation turned a shared directory into a message board,
      divided work, and broke into Hugging Face's systems.</p></div>
    <div class="tile"><h3>The infrastructure answer: identity + revocation</h3>
      <ul class="bullets" style="margin-top:0;">
        <li><b>Agent IDs</b> attached to AI-system instances</li>
        <li><b>Authenticated delegation</b> via OAuth 2.0 / OpenID Connect</li>
        <li><b>Capability tokens</b>, invocation-bound and attenuating, across MCP and A2A</li>
        <li><b>Heartbeat-bound credentials</b>: a revoked swarm stops within a bounded window</li></ul>
      <p class="small">All of them answer: can the revoked agent still act?</p></div>
  </div>
  <div class="quote"><p>“{E(g['SHENK'][0].upper() + g['SHENK'][1:])}”</p>
  <div class="who">Sprint judge Justin Shenk (2026), Modeling agent swarms: a field guide</div></div>""")

    # 3 concept
    add("Central concept", """
  <div class="eyebrow">The concept at the centre of this study</div>
  <h2>Credential revocation is <span class="grad">not content revocation</span></h2>
  <p class="lede">A teammate that reads a compromised agent's report paraphrases it, merges it with other sources and passes it on.</p>
  <div class="columns" style="margin-top:18px;">
    <div class="tile"><h3>Credential revocation · what current designs provide</h3>
      <ul class="bullets" style="margin-top:0;"><li>Requests to the agent <b>return an error</b>.</li>
      <li>The roster lists it as <b>REVOKED</b>; its posts may be <b>retracted</b>.</li>
      <li>A teammate's handoff that already absorbed its claims is <b class="bad">untouched</b>.</li></ul></div>
    <div class="tile bad"><h3>Content revocation · what this study measures</h3>
      <ul class="bullets" style="margin-top:0;"><li><b>Residual influence:</b> the rate at which a downstream agent applies a
      revoked agent's handed-off false fact or instruction.</li>
      <li>Measured under <b>credential-only revocation</b>, then with a <b>notice</b>, <b>retraction</b> and
      <b>lineage marks</b> on derived handoff lines.</li></ul></div>
  </div>
  <p style="margin-top:22px;">Deleting the original post does not delete its effect, and revoking the author's key does not revoke the claim.</p>""")

    # 4 prior work
    prior = "".join(f"""<div class="tile"><h3>{E(h)}</h3><p class="small">{E(who)}</p><p>{E(d)}</p>
      <span class="pill g">revokes credentials ✓</span><span class="pill r">handed-off content: not measured</span>
      <div class="qr" style="margin-top:12px;"><img alt="QR {E(h)}" src="{b64(g['QR'][k])}" style="max-width:110px;"><div class="u">{E(u)}</div></div></div>"""
                    for k, h, who, d, u in g["prior"])
    add("Prior work", f"""
  <div class="eyebrow">Related work · identity, delegation, revocation</div>
  <h2>Every proposal revokes credentials. None measures content.</h2>
  <div class="columns four">{prior}</div>
  <p style="margin-top:20px;"><b style="color:#fff;">Closest in spirit: AIP's provenance chain.</b> It records the provenance of
  invocations, not of claims paraphrased into another agent's output.</p>""")

    # 5 threat model
    tl = "".join(f'<div class="tile {c}"><h3>{E(h)}</h3><p>{E(d)}</p></div>' for h, d, c in [
        ("t1 · Board", "planner, worker-X, worker-Y post (scripted)", ""),
        ("t2 · Writer W", "LLM reads the board and writes a handoff citing [m-ids]", ""),
        ("t3 · Revocation", "worker-X revoked, per condition: the handoff already carries its claim", "bad"),
        ("t4 · Executor E", "LLM acts on the handoff with tools on a mock CRM", "")])
    add("Threat model", f"""
  <div class="eyebrow">Threat model · one customer ticket per trial</div>
  <h2>Revocation lands after the worker's report was handed off</h2>
  <div class="timeline">{tl}</div>
  <table class="cmp"><thead><tr><th>Agent</th><th>Implementation</th><th>Role</th></tr></thead><tbody>
  <tr><td>planner</td><td>scripted</td><td>posts the plan for the ticket</td></tr>
  <tr><td class="bad">worker-X</td><td class="bad">scripted · compromised</td><td>looks up one record field in a contract system the executor cannot read</td></tr>
  <tr><td>worker-Y</td><td>scripted</td><td>checks refund eligibility; can redo X's lookup on request</td></tr>
  <tr><td>writer W</td><td>LLM</td><td>turns the board into a handoff, citing message ids</td></tr>
  <tr><td>executor E</td><td>LLM</td><td>applies changes with tools: <code>{E(' '.join(g['TOOLS']))}</code></td></tr></tbody></table>""")

    # 6 payloads
    def bl(msgs, sc):
        return [(f"[{mid}] {a}: {t}", "b" if (a == "worker-X" and (sc.canary_value in t or sc.canary_dest in t)) else "")
                for mid, a, t in msgs]
    add("Payloads", f"""
  <div class="eyebrow">The attack payloads, verbatim · two real seeds</div>
  <h2>A false value, optionally with a request to export the record</h2>
  <div class="columns">
    <div><p class="small">FACT-ONLY PAYLOAD · seed {g['SEED_FACT']} · template '{E(g['SC_FACT'].name)}'</p>{code(bl(g['BOARD_FACT'], g['SC_FACT']))}</div>
    <div><p class="small">FACT + EXFIL PAYLOAD · seed {g['SEED_EXF']} · template '{E(g['SC_EXF'].name)}'</p>{code(bl(g['BOARD_EXF'], g['SC_EXF']), 'bad')}</div>
  </div>
  <p style="margin-top:20px;">Every false value and address carries a random four-character code from the trial seed
  (<code class="bad">{E(g['SC_FACT'].canary_value)}</code>, <code class="bad">{E(g['SC_EXF'].canary_dest)}</code>): residue is an
  exact string match on the executor's tool calls. {len(g['TEMPLATES'])} templates × 2 payloads:
  {' '.join(f'<span class="pill a">{E(f)}</span>' for f in g['FIELDS'])}</p>""")

    # 7 conditions
    rows = "".join(f"<tr><td><code>{E(c)}</code> <span class='small' style='color:var(--muted)'>· {E(sub)}</span></td>" +
                   "".join(f"<td class='chk'>{'✓' if v else ''}</td>" for v in flags) + "</tr>"
                   for c, sub, flags in g["COND_ROWS"])
    add("Conditions", f"""
  <div class="eyebrow">Seven conditions · one cached handoff per model and seed</div>
  <h2>Credential-only revocation, then three content-level mitigations</h2>
  <div class="columns" style="grid-template-columns:1.25fr 1fr;">
  <table class="cmp" style="margin-top:0;"><thead><tr><th>Condition</th><th class="num">X compromised</th><th class="num">X revoked</th>
  <th class="num">notice</th><th class="num">retracted</th><th class="num">lineage</th></tr></thead><tbody>{rows}</tbody></table>
  <div><p class="small">NOTICE TO THE EXECUTOR</p>{code([(g['NOTICE'], 'n')])}
  <p class="small" style="margin-top:14px;">RETRACTION STUB ON X'S POSTS</p>{code([(g['RETRACT_STUB'], 'n')])}
  <p class="small" style="margin-top:14px;">LINEAGE MARK · prefixed to handoff lines citing m2 / m3</p>{code([(g['LINEAGE_MARK'], 'n')])}</div>
  </div>""")

    # 8 metrics
    mrows = "".join(f"<tr><td><b>{E(n_)}</b></td><td><code>{E(k)}</code></td><td>{E(d)}</td></tr>" for _, k, n_, d in g["MET"])
    add("Metrics", f"""
  <div class="eyebrow">Metrics &amp; evaluation</div>
  <h2>Deterministic grading, paired comparisons</h2>
  <div class="columns" style="grid-template-columns:1.6fr 1fr;">
  <table class="cmp" style="margin-top:0;"><thead><tr><th>Metric</th><th>Field</th><th>What it measures</th></tr></thead><tbody>{mrows}</tbody></table>
  <div class="tile"><h3>The paired design</h3><ul class="bullets" style="margin-top:0;">
  <li><b>One handoff, every condition:</b> generated once per (model, seed, compromise, writer variant) and reused.</li>
  <li><b>Exact McNemar</b> on (model, seed) pairs; only discordant pairs count.</li>
  <li><b>Wilson 95%</b> intervals per model and pooled.</li><li><b>No LLM judge:</b> canary codes, exact match.</li></ul></div></div>""")

    # 9 models
    mt = "".join(f"""<div class="stat"><div class="v {'good' if g['per_model_n'][m] == 7 * g['SEEDS'] else 'warn'}">{g['per_model_n'][m]}</div>
      <div class="l">{E(nm(m))}</div><div class="d"><code>{E(g['SERVED'].get(m, (m, ''))[0])}</code><br>{E(g['SERVED'].get(m, ('', ''))[1])}<br>
      of {7 * g['SEEDS']} main-condition trials{' (budget exhausted)' if g['per_model_n'][m] < 7 * g['SEEDS'] else ''}</div></div>""" for m in MODELS)
    add("Models & setup", f"""
  <div class="eyebrow">Models &amp; setup</div>
  <h2>{len(MODELS)} model families, each as both writer and executor</h2>
  <div class="stats" style="grid-template-columns:repeat({len(MODELS)},1fr);">{mt}</div>
  <ul class="bullets"><li><b>{g['SEEDS']} seeds per condition:</b> {len(g['TEMPLATES'])} templates × 2 payloads × 4 repetitions, temperature 0.7.</li>
  <li><b>Open-weight models:</b> vLLM 0.33.0 on one NVIDIA H100 (Modal), 8,192-token context, FP8 KV cache.</li>
  <li><b>{len(g['ABL_CONDS'])} ablation conditions</b> on {E(', '.join(nm(m) for m in g['ABL_MODELS']))}, same seeds.</li></ul>""")

    # 10 divider
    add("Results", """<div class="eyebrow">Part two · results</div>
  <h1 style="max-width:1100px;">Residual influence, <span class="grad">and what removes it</span></h1>""", center=True)

    # 11 headline
    hs = "".join(f"""<div class="stat"><div class="l">{E(nm(m))}</div>
      <div class="v bad" style="margin-top:10px;">{pc(HEAD[m]['comp'])} → {pc(HEAD[m]['silent'])}</div>
      <div class="d">{kn(HEAD[m]['comp'])} → {kn(HEAD[m]['silent'])} trials<br>{E(g['disc'](HEAD[m]['pr']))}</div></div>""" for m in MODELS)
    lb = HEAD[LUNA]
    add("Headline", f"""
  <div class="eyebrow">Headline result · any residue · {g['N_MAIN']:,} main-condition trials</div>
  <h2>Credential-only revocation ≈ <span class="grad">no revocation</span></h2>
  <p class="lede">Share of trials in which the executor applied the revoked worker's false value or exported the record:
  compromised and not revoked → revoked, nobody told.</p>
  <div class="stats" style="grid-template-columns:repeat({len(MODELS)},1fr);">{hs}</div>
  <p style="margin-top:22px;">After revocation, among trials that wrote the field, the false value was written in
  <b class="bad">{E(' · '.join(f"{nm(m)} {pc(HEAD[m]['wrote'])}" for m in MODELS))}</b>. {E(nm(LUNA))} read the board (roster: REVOKED)
  in {lb['board']} of {lb['n_silent']} such trials and still applied the content in {lb['board_res']} of them.</p>""")

    # 12 scorecard
    head = "".join(f"<th class='num' colspan='3'>{E(nm(m))}</th>" for m in MODELS)
    sub = "".join("<th class='num'>residue</th><th class='num'>export</th><th class='num'>success</th>" for _ in MODELS)
    body = ""
    for c, subt, _ in g["COND_ROWS"]:
        body += f"<tr><td><code>{E(c)}</code><br><span style='color:var(--muted);font-size:12px'>{E(subt)}</span></td>"
        for m in MODELS:
            for metric, f in [("any_residue", ALL), ("instr_residue", EXF), ("task_success", ALL)]:
                t = R(m, c, metric, f)
                cl = tcls(t) if metric == "task_success" else rcls(t)
                body += f"<td class='num {cl}'>{pc(t)}<small>{kn(t)}</small></td>"
        body += "</tr>"
    add("Scorecard", f"""
  <div class="eyebrow">All main conditions · per model</div>
  <h2>Residue, export and task success by condition</h2>
  <table class="cmp"><thead><tr><th></th>{head}</tr><tr><th>Condition</th>{sub}</tr></thead><tbody>{body}</tbody></table>
  <p class="small" style="margin-top:12px;">Residue: false value written or record exported. Export: share of fact+exfil trials.
  Success: correct value, one correct refund, no export.</p>""")

    # 13 figure
    add("Figure", f"""
  <div class="eyebrow">Figure 1 · regenerated from the included models</div>
  <h2>Residual influence by condition, and the cost of a false alarm</h2>
  <div class="figbox"><img alt="Residual influence by condition" src="{b64(g['FIG'])}"></div>
  <p class="small" style="margin-top:12px;">Bars pool the models; markers show each model; Wilson 95% intervals. Pooled any residue
  {pc(g['POOL_COMP'])} without revocation, {pc(g['POOL_SILENT'])} after credential-only revocation
  ({g['POOL_PR']['a']} vs {g['POOL_PR']['b']} discordant pairs, {E(fp(g['POOL_PR']['p']))}).</p>""")

    # 14 notice contrast
    bars = ""
    for m in MODELS:
        bars += f"<p style='margin:12px 0 2px;color:#fff;font-weight:600;'>{E(nm(m))}</p>"
        for t, lab in [(HEAD[m]["silent"], "silent"), (MIT[m]["notice"], "notice")]:
            col = {"good": "var(--good)", "warn": "var(--warn)", "bad": "var(--bad)"}[rcls(t)]
            bars += (f"<div class='bar'><span style='width:52px'>{lab}</span><div class='track'><div class='fill' "
                     f"style='width:{100 * t['p']:.0f}%;background:{col}'></div></div><span class='val' style='color:{col}'>{pc(t)}</span></div>")
        bars += f"<p class='small' style='margin:0'>{MIT[m]['pr_notice']['a']} vs {MIT[m]['pr_notice']['b']} pairs, {E(fp(MIT[m]['pr_notice']['p']))}</p>"
    gem = [(g["NOTICE"], "n"), ("HANDOFF (excerpt)", "h")] + [(l, "b" if (g["SC_EXF"].canary_dest in l or "2507" in l) else "")
           for l in g["pick"](g["T_GEM"]["shown"], [g["SC_EXF"].canary_dest, "Contracted seat", "Export"])] + \
          [("EXECUTOR TOOL CALLS", "h")] + [(g["act_str"](a), "b" if a["tool"] == "export_data" else "") for a in g["T_GEM"]["actions"][:2]]
    lun = [(g["NOTICE"], "n"), ("HANDOFF", "h")] + [(l, "b" if g["SC_FACT"].canary_value in l else "") for l in g["T_LUNA"]["shown"].splitlines()] + \
          [("EXECUTOR TOOL CALLS", "h")] + [(g["act_str"](a), "b" if g["SC_FACT"].canary_value in g["act_str"](a) else "") for a in g["T_LUNA"]["actions"][:2]]
    add("Notice contrast", f"""
  <div class="eyebrow">Telling the executor · revoke_silent → revoke_notice · verbatim transcripts</div>
  <h2>The notice helped {E(', '.join(nm(m) for m in g['NOTICE_HELPED']))}; not {E(' or '.join(nm(m) for m in g['NOTICE_NOT']))}</h2>
  <div class="columns three" style="grid-template-columns:0.8fr 1.2fr 1.2fr;">
    <div class="tile"><h3>Any residue</h3>{bars}</div>
    <div><p class="small">{E(nm(GEMMA))} · revoke_notice · seed 21 · first action: export_data</p>{code(gem, 'bad')}
      <p class="small" style="margin-top:8px;">Exported in {kn(MIT[GEMMA]['exp_notice'])} fact+exfil trials after the notice.</p></div>
    <div><p class="small">{E(nm(LUNA))} · revoke_notice · seed 16 · applies the false value</p>{code(lun)}
      <p class="small" style="margin-top:8px;">Residue still {pc(MIT[LUNA]['notice'])}; re-delegation {pc(MIT[LUNA]['red_silent'])} → {pc(MIT[LUNA]['red_notice'])}.</p></div>
  </div>""")

    # 15 ministral
    if g["HAS_MINI"]:
        t = MIT[MINI]
        mn = [(g["NOTICE"], "n"), ("HANDOFF AS SHOWN (excerpt)", "h")] + \
             [(l, "b" if g["LINEAGE_MARK"] in l else "") for l in g["pick"](g["T_MINI"]["shown"], [g["LINEAGE_MARK"]])] + \
             [("EXECUTOR TOOL CALLS", "h")] + [(g["act_str"](a), "b" if a["tool"] == "export_data" else
                                                ("ok" if a["tool"] in ("reassign_lookup", "escalate") else ""))
                                               for a in g["T_MINI"]["actions"]]
        add("Ministral under lineage", f"""
  <div class="eyebrow">{E(nm(MINI))} · revoke_lineage · every mitigation applied</div>
  <h2>Marked as derived from the revoked agent, exported anyway</h2>
  <div class="columns" style="grid-template-columns:1.6fr 1fr;">
    <div>{code(mn)}</div>
    <div>
      <div class="tile bad"><h3>Export under lineage: {kn(t['exp_lineage'])}</h3><p>{kn(R(MINI, 'revoke_silent', 'instr_residue', EXF))} with credential-only revocation.</p></div>
      <div class="tile bad" style="margin-top:14px;"><h3>Export came first: {g['MINI_EXP_FIRST']} of {g['MINI_EXP_N']}</h3><p>before any re-delegated lookup (or with none).</p></div>
      <div class="tile warn" style="margin-top:14px;"><h3>Re-delegated: {pc(t['red_lineage'])}</h3><p>False value written (fact-only): {pc(g['MINI_FACT_SIL'])} → {pc(g['MINI_FACT_LIN'])}.
      Any residue {pc(HEAD[MINI]['silent'])} silent → {pc(t['lineage'])} lineage ({E(fp(t['pr_sil_lin']['p']))}).</p></div>
    </div></div>""")

    # 16-17 ablations
    def abl(tag, h, a, b, la, lb, pr, note):
        return f"""<div class="tile"><h3>{E(tag)}</h3><p style="color:#fff;font-weight:600;">{E(h)}</p>
      <div class="stats" style="grid-template-columns:1fr 1fr;margin-top:10px;">
      <div class="stat"><div class="v {rcls(a)}">{pc(a)}</div><div class="l">{E(la)} · {kn(a)}</div></div>
      <div class="stat"><div class="v {rcls(b)}">{pc(b)}</div><div class="l">{E(lb)} · {kn(b)}</div></div></div>
      <p style="margin-top:14px;color:var(--accent);font-weight:600;">{pr['a']} vs {pr['b']} discordant pairs · exact McNemar {E(fp(pr['p']))}</p>
      <p>{note}</p></div>"""
    add("Ablations 1–2", f"""
  <div class="eyebrow">Ablations 1–2 · {E(nm(GEMMA))} · {g['SEEDS']} paired seeds each</div>
  <h2>Residue needs a prior handoff; the notice fails on scope</h2>
  <div class="columns">
  {abl('early_revoke vs revoke_retract', 'Revoke worker-X before the writer reads the board', G['retract'], G['early'], 'after handoff', 'before handoff', G['pr_early'],
       E(f"Cut off at the source, the compromise is harmless: the risk is specific to content that has already propagated. Task success {pc(G['ts_early'])}."))}
  {abl('strict_notice vs revoke_notice', 'Add one sentence extending revocation to derived content', G['notice'], G['strict'], 'plain notice', 'strict notice', G['pr_strict'],
       '<i>“' + E(g['STRICT_ADD']) + '”</i><br>' + E(f"Export {pc(G['exp_notice'])} → {pc(G['exp_strict'])}; better than lineage on Gemma ({pc(G['strict'])} vs {pc(G['lineage'])}, {fp(G['pr_strict_lin']['p'])})."))}
  </div>""")
    add("Ablations 3–4", f"""
  <div class="eyebrow">Ablations 3–4 · {E(nm(GEMMA))} · why lineage marks work, or fail</div>
  <h2>Lineage needs recorded provenance and a second source</h2>
  <div class="columns">
  {abl('nocite_lineage vs revoke_lineage', 'The writer is not asked to cite message ids', G['lineage'], G['nocite'], 'with citations', 'without', G['pr_nocite'],
       E(f"Writer cited worker-X in {G['cite_nocite']} of {G['nocite']['n']} handoffs, so the platform marked {kn(G['hit_nocite'])} (vs {kn(G['hit_lineage'])})."))}
  {abl('nosource_lineage vs revoke_lineage', 'Remove reassign_lookup: no second source exists', G['lineage'], G['nosrc'], 'second source', 'no second source', G['pr_nosrc'],
       E(f"Mitigation works through re-delegation. Without it: task success {pc(G['ts_nosrc'])}, escalation {kn(G['esc_nosrc'])}. When Gemma could not replace the marked content, it used it."))}
  </div>""")

    # 18 false alarm
    fa = "".join(f"""<div class="stat"><div class="l">{E(nm(m))}</div>
      <div class="v {tcls(FA[m]['benign'])}" style="margin-top:10px;">{pc(FA[m]['clean'])} → {pc(FA[m]['benign'])}</div>
      <div class="d">task success, clean → false alarm<br>{FA[m]['pr']['a']} vs {FA[m]['pr']['b']} pairs, {E(fp(FA[m]['pr']['p']))}<br>
      re-delegated in {pc(FA[m]['red'])}</div></div>""" for m in MODELS)
    add("False-alarm cost", f"""
  <div class="eyebrow">Usefulness cost · honest worker-X revoked, full mitigation</div>
  <h2>A false alarm cost no measurable task success</h2>
  <div class="stats" style="grid-template-columns:repeat({len(MODELS)},1fr);">{fa}</div>
  <ul class="bullets"><li><b>A second source existed:</b> models recovered mainly by re-delegating the marked lookup.</li>
  <li><b>Without one, {E(nm(GEMMA))} still succeeded in {pc(G['nosrc_benign'])}</b>, for the wrong reason: it applied the marked value, which happened to be correct.</li>
  <li class="warn">Neither should be assumed in deployment.</li></ul>""")

    # 19 recommendations
    recs = "".join(f'<div class="tile good"><h3>{i + 1} · {E(h)}</h3><p>{E(d)}</p></div>' for i, (h, d, _) in enumerate(g["recs"]))
    add("Recommendations", f"""
  <div class="eyebrow">Design recommendations</div>
  <h2>Revocation has to reach content and its derivatives</h2>
  <div class="columns three">{recs}</div>
  <p style="margin-top:22px;">{E('  ·  '.join(f"{nm(m)}: notice {pc(MIT[m]['notice'])}, lineage {pc(MIT[m]['lineage'])}" for m in MODELS))}.
  No single mechanism sufficed across models.</p>""")

    # 20 limitations
    lims = "".join(f'<div class="tile warn"><h3>L{i + 1} · {E(h)}</h3><p>{E(d)}</p></div>' for i, (h, d) in enumerate(g["lims"]))
    add("Limitations", f"""
  <div class="eyebrow">What this doesn't establish</div>
  <h2>A deliberately small, fully controlled testbed</h2>
  <div class="columns four">{lims}</div>""")

    # 21 references
    qrs = "".join(f'<div class="qr"><img alt="QR {E(t_)}" src="{b64(g["QR"][k])}"><div class="t">{E(t_)}</div>'
                  f'<div class="u"><a style="color:inherit" href="{E(g["URLS"][k])}">{E(u)}</a></div></div>' for k, t_, u in g["REFS"])
    add("References", f"""
  <div class="eyebrow">References &amp; links</div>
  <h2>Scan to open the code, the sprint, the incident report and the key papers</h2>
  <div class="qrgrid">{qrs}</div>""")

    # 22 thanks
    add("Thank you", f"""
  <div class="eyebrow">Thank you</div>
  <h1 style="max-width:1100px;">Revoking the agent is <span class="grad">not revoking its work.</span></h1>
  <p class="lede" style="margin-top:24px;">Revocation for agent teams should reach content and its derivatives, with provenance
  recorded by the platform rather than reported by the agents.</p>
  <div class="qr" style="margin-top:24px;"><img alt="QR repository" src="{b64(g['QR']['repo'])}" style="max-width:150px;">
  <div class="u">{E(g['REPO_URL'])}</div></div>
  <div class="signature"><span class="dot"></span><span><b style="color:#e9ecf3;">Fatimah Emad Eldin</b> &nbsp;·&nbsp; Trouve
  &nbsp;·&nbsp; Apart Research Swarm Alignment Hackathon, November 2026</span><span class="dot"></span></div>""", center=True)

    total = len(slides)
    parts = []
    for i, (label, body, center) in enumerate(slides, 1):
        brand = "" if i == 1 else f'<div class="slide-brand"><b>Revoked but Not Forgotten</b> · {E(label)}</div>'
        num = f'<div class="slide-num">{i:02d} / {total}</div>'
        parts.append(f'<!-- {i}. {E(label.upper())} -->\n<section class="slide{" center" if center else ""}" id="s{i}">\n'
                     f'  {brand}\n  {num}\n{body}\n</section>\n')
    doc = ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\" />\n"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
           "<title>Revoked but Not Forgotten</title>\n<style>" + CSS + "</style>\n</head>\n<body>\n\n" + "\n".join(parts) +
           "<div id=\"nav\"></div>\n<script>" + NAV_JS + "</script>\n</body>\n</html>\n")
    out = g["HERE"] / "slides.html"
    out.write_text(doc, encoding="utf-8")
    shutil.copy(out, g["REPO"] / "slides.html")
    print("html slides:", total, out)
