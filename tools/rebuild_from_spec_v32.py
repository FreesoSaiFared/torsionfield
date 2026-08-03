
from pathlib import Path
import json
from html import escape

ROOT = Path(r"E:\Transductive_MCP_Work\torsionfield-site")
PUBLIC = ROOT / "public"
DOCS = PUBLIC / "docs"

SPEC = "https://spec.torsionfield.de/"
PRODUCT = "https://torsionfield.de/"

nav = '''<header class="top"><nav class="nav wrap">
<a class="brand" href="https://torsionfield.de/">TORSION<i>FIELD</i></a>
<button class="menu-button" type="button" aria-label="Open navigation" data-menu-button>Menu</button>
<div class="links" data-menu>
<a href="https://torsionfield.de/#runtime">Runtime</a>
<a href="https://torsionfield.de/#first-release">First release</a>
<a href="https://spec.torsionfield.de/">Specification</a>
<a href="https://docs.torsionfield.de/">Documentation</a>
<a class="pill" href="https://torsionfield.de/#network">Join alpha</a>
</div></nav></header>'''

footer = '''<footer class="footer"><div class="wrap footer-grid">
<div><b>Torsionfield Runtime</b><p>A ScriptCat-first programmable browser runtime with local execution, explicit authority, observable effects, recovery, and optional participant-owned edge infrastructure.</p></div>
<div><a href="https://spec.torsionfield.de/">Specification v3.2</a><a href="https://docs.torsionfield.de/">Documentation</a><a href="https://github.com/FreesoSaiFared/torsionfield">Source</a></div>
</div></footer>'''

def head(title, description, canonical=None, extra=""):
    can = f'<link rel="canonical" href="{canonical}">' if canonical else ""
    return f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><meta name="description" content="{escape(description)}">
<meta name="theme-color" content="#07100c">{can}
<link rel="icon" href="/favicon.svg"><link rel="manifest" href="/manifest.webmanifest">
<link rel="stylesheet" href="/styles.css">{extra}</head>'''

def page(title, description, body, canonical=None, extra="", scripts=True):
    tail = '<script src="/app.js" defer></script>' if scripts else ''
    return head(title, description, canonical, extra) + f'<body>{nav}<main>{body}</main>{footer}{tail}</body></html>'

def spec_link(section, label=None):
    label = label or f"Specification §{section}"
    return f'<a href="{SPEC}#section-{section}">{escape(label)} →</a>'

css = r'''
:root{--bg:#07100c;--panel:#0d1813;--panel2:#101f18;--text:#eef8f2;--muted:#a3b9ad;--line:#284337;--acid:#b7ff4a;--cyan:#61ead7;--orange:#ffad66;--danger:#ff7a73;--max:1180px;color-scheme:dark}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 78% -10%,#1d4b35 0,transparent 34rem),var(--bg);color:var(--text);font:16px/1.65 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:inherit;text-decoration:none}a:hover{color:var(--acid)}code,pre,.mono{font-family:"SFMono-Regular",Consolas,monospace}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#050a07;border:1px solid var(--line);padding:1rem;border-radius:13px;overflow:auto}
.wrap{width:min(var(--max),calc(100% - 36px));margin:auto}.top{position:sticky;top:0;z-index:30;background:#07100ce8;backdrop-filter:blur(18px);border-bottom:1px solid #ffffff12}
.nav{height:70px;display:flex;align-items:center;justify-content:space-between;gap:24px}.brand{font-weight:950;letter-spacing:.08em}.brand i{font-style:normal;color:var(--acid)}.links{display:flex;gap:21px;align-items:center;font-size:.92rem}.pill,.btn{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line);border-radius:999px;padding:.72rem 1.05rem;font-weight:750;background:#ffffff06}.btn.primary{background:var(--acid);border-color:var(--acid);color:#071006}.menu-button{display:none;background:transparent;border:1px solid var(--line);color:var(--text);border-radius:9px;padding:.5rem .7rem}
.hero{padding:92px 0 72px;display:grid;grid-template-columns:1.25fr .75fr;gap:54px;align-items:center}.eyebrow{color:var(--acid);font:800 .78rem/1.2 monospace;letter-spacing:.14em;text-transform:uppercase}.hero h1,.page-hero h1{font-size:clamp(3rem,7vw,6.7rem);line-height:.91;letter-spacing:-.065em;margin:.55rem 0 1.3rem}.lead{font-size:clamp(1.08rem,2vw,1.36rem);color:var(--muted);max-width:760px}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:27px}
.terminal{border:1px solid var(--line);border-radius:18px;background:linear-gradient(145deg,#102018,#070b09);box-shadow:0 28px 80px #0008;overflow:hidden}.terminal header{padding:12px 16px;border-bottom:1px solid var(--line);color:var(--muted);font:12px monospace}.terminal pre{border:0;border-radius:0;margin:0;background:transparent;color:#dcffe8;min-height:270px}
.section{padding:76px 0;border-top:1px solid #ffffff0d}.section h2,.article h2{font-size:clamp(2rem,4vw,3.8rem);letter-spacing:-.045em;line-height:1.02;margin:.45rem 0 1rem}.section-intro{color:var(--muted);max-width:820px;font-size:1.08rem}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:32px}.grid.two{grid-template-columns:repeat(2,1fr)}.grid.four{grid-template-columns:repeat(4,1fr)}.card{border:1px solid var(--line);background:linear-gradient(155deg,#111f19,#0a110e);border-radius:17px;padding:24px;min-height:180px}.card b,.card h3{display:block;margin:.1rem 0 .55rem;font-size:1.05rem}.card p{color:var(--muted);margin:.4rem 0}.num{font:850 2.5rem/1 monospace;color:var(--acid);margin-bottom:18px}
.band{background:var(--acid);color:#071006;padding:44px 0}.band h2{margin:0;font-size:clamp(2rem,5vw,4.7rem);letter-spacing:-.055em;line-height:.96}.split{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:start}
.flow{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:30px}.flow div{padding:17px;border:1px solid var(--line);border-radius:12px;background:#0d1813;font:750 .84rem monospace}.flow div:before{content:attr(data-n);display:block;color:var(--acid);margin-bottom:8px}
.status-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}.status-chip{font:750 .72rem monospace;border:1px solid var(--line);border-radius:999px;padding:.34rem .65rem;color:var(--muted)}.status-chip.live{color:#071006;background:var(--acid);border-color:var(--acid)}.status-chip.stage{color:var(--orange)}.status-chip.repair{color:var(--danger)}
.form{border:1px solid var(--line);background:var(--panel);padding:26px;border-radius:18px}.field{display:grid;gap:7px;margin:0 0 15px}.field label{font-size:.82rem;color:var(--muted);font-weight:700}.field input,.field select{width:100%;background:#070b09;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:12px 13px;font:inherit}.check{display:flex;gap:10px;color:var(--muted);font-size:.9rem}.status{min-height:1.5em;color:var(--acid);margin-top:12px}.honeypot{display:none!important}.submit-gap{margin-top:18px}
.docs{display:grid;grid-template-columns:270px minmax(0,1fr);gap:42px;padding:42px 0 82px}.side{position:sticky;top:94px;align-self:start;max-height:calc(100vh - 120px);overflow:auto;padding-right:12px}.side a{display:block;color:var(--muted);padding:7px 10px;border-left:2px solid transparent}.side a.active,.side a:hover{color:var(--text);border-left-color:var(--acid);background:#ffffff05}.doc-search{width:100%;background:#080d0a;border:1px solid var(--line);border-radius:9px;color:var(--text);padding:10px;margin-bottom:12px}
.article{max-width:880px}.article h1{font-size:clamp(2.7rem,6vw,5.5rem);line-height:.95;letter-spacing:-.055em;margin:.25rem 0 1.15rem}.article h2{margin-top:3rem}.article h3{margin-top:2rem}.article p,.article li{color:#c0d2c8}.article table{border-collapse:collapse;width:100%;font-size:.92rem;margin:1.4rem 0}.article th,.article td{border:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}.article th{color:var(--acid);background:#0d1813}.callout{border-left:4px solid var(--acid);background:#101b15;padding:17px 20px;margin:24px 0}.tag{font:750 .72rem monospace;color:var(--cyan);border:1px solid #61ead744;padding:3px 7px;border-radius:999px}.quote{font-size:clamp(1.4rem,3vw,2.35rem);letter-spacing:-.025em;line-height:1.2;border-left:5px solid var(--acid);padding-left:1.2rem}.compact-list{columns:2;gap:36px}.footer{padding:48px 0;color:var(--muted);border-top:1px solid var(--line)}.footer-grid{display:grid;grid-template-columns:1fr auto;gap:36px}.footer-grid div:last-child{display:grid;gap:7px}.accent{color:var(--acid)}.hide{display:none!important}
@media(max-width:930px){.hero,.split,.docs{grid-template-columns:1fr}.grid,.grid.four{grid-template-columns:1fr 1fr}.flow{grid-template-columns:1fr 1fr}.side{position:relative;top:0;max-height:none}.menu-button{display:block}.links{display:none;position:absolute;top:62px;right:18px;left:18px;flex-direction:column;align-items:stretch;background:#07100c;border:1px solid var(--line);border-radius:14px;padding:14px}.links.open{display:flex}.links a{padding:.35rem}.footer-grid{grid-template-columns:1fr}}
@media(max-width:580px){.grid,.grid.two,.grid.four,.flow{grid-template-columns:1fr}.hero{padding-top:56px}.nav{height:62px}.wrap{width:min(100% - 24px,var(--max))}.compact-list{columns:1}}
'''
(PUBLIC / "styles.css").write_text(css.strip()+"\n", encoding="utf-8")
(DOCS / "styles.css").write_text(css.strip()+"\n", encoding="utf-8")

app_js = r'''
const form=document.querySelector("#network-form");
if(form)form.addEventListener("submit",async e=>{e.preventDefault();const s=document.querySelector("#form-status"),f=new FormData(form),b={displayName:f.get("displayName"),email:f.get("email"),nodeIntent:f.get("nodeIntent"),interests:f.getAll("interests"),accepted:f.get("accepted")==="on",website:f.get("website")||""};s.textContent="Registering…";try{const r=await fetch("/api/network/register",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(b)}),j=await r.json();if(!r.ok)throw new Error(j.error||"Registration failed");s.textContent="Registered. Your local credentials remain local.";form.reset()}catch(x){s.textContent=x.message}});
const q=document.querySelector("#doc-search");if(q)q.addEventListener("input",()=>{const v=q.value.toLowerCase();document.querySelectorAll("[data-doc]").forEach(a=>a.classList.toggle("hide",!a.textContent.toLowerCase().includes(v)))});
const mb=document.querySelector("[data-menu-button]"),menu=document.querySelector("[data-menu]");if(mb&&menu)mb.addEventListener("click",()=>menu.classList.toggle("open"));
'''
(PUBLIC / "app.js").write_text(app_js.strip()+"\n", encoding="utf-8")
(DOCS / "app.js").write_text(app_js.strip()+"\n", encoding="utf-8")

home = r'''
<section class="hero wrap">
<div>
<div class="eyebrow">Torsionfield Runtime · Specification v3.2</div>
<h1>Make the browser a programmable runtime.</h1>
<p class="lead">Torsionfield begins with a ScriptCat-derived extension and a local Torsion Node. It turns webpages, authenticated AI sessions, userscripts, local tools, and optional peers into callable capabilities with explicit authority, observed effects, recovery, and rollback.</p>
<div class="actions"><a class="btn primary" href="#first-release">See the first release</a><a class="btn" href="https://spec.torsionfield.de/">Read the full specification</a></div>
<div class="status-row"><span class="status-chip live">SPECIFICATION v3.2</span><span class="status-chip">SCRIPTCAT-FIRST</span><span class="status-chip">LOCAL-FIRST</span><span class="status-chip stage">EDGE PLANE STAGED</span></div>
</div>
<div class="terminal"><header>DIRECT IMPLEMENTATION PATH</header><pre><span class="accent">01</span> select    webpage element + goal
<span class="accent">02</span> generate  through an authenticated AI page
<span class="accent">03</span> install   into the real ScriptCat registry
<span class="accent">04</span> run       against the target page
<span class="accent">05</span> observe   the requested postcondition
<span class="accent">06</span> repair    from real failure evidence
<span class="accent">07</span> retain    working version or roll back

NO CENTRAL MODEL CREDENTIALS
NO FAKE DOWNLOAD-ONLY INSTALL
NO SUCCESS WITHOUT OBSERVATION</pre></div>
</section>

<section class="band"><div class="wrap"><h2>Nothing is silently prohibited. Nothing is silently trusted. Nothing is silently verified. Nothing is silently accepted.</h2></div></section>

<section id="first-release" class="section"><div class="wrap">
<div class="eyebrow">The first complete product</div><h2>One reversible browser-to-script loop.</h2>
<p class="section-intro">The first release is not a browser fork, a distributed governance platform, or a promise of autonomous correctness. It is a working local browser runtime that can generate, install, execute, inspect, repair, and roll back a real userscript.</p>
<div class="flow"><div data-n="01 / SELECT">Choose a page, element, and desired behavior.</div><div data-n="02 / GENERATE">Use the user’s existing authenticated model session.</div><div data-n="03 / INSTALL">Write the complete script into ScriptCat’s canonical registry.</div><div data-n="04 / VERIFY">Run it and observe whether the behavior occurred.</div><div data-n="05 / REPAIR">Return exact evidence, patch, rerun, or restore.</div></div>
<div class="actions"><a class="btn" href="https://spec.torsionfield.de/#section-1">Purpose and delivery target</a><a class="btn" href="https://spec.torsionfield.de/#section-22">Acceptance criteria</a></div>
</div></section>

<section id="runtime" class="section"><div class="wrap">
<div class="eyebrow">Four cooperating planes</div><h2>The implementation has clear physical boundaries.</h2>
<div class="grid four">
<div class="card"><div class="num">01</div><b>Chat Runtime</b><p>Provider adapters control composers, submission, streaming output, attachments, and completion state on authenticated AI pages.</p></div>
<div class="card"><div class="num">02</div><b>ScriptCat Runtime</b><p>Router, Mother Script, target selection, userscript registry, mutation, protected agent tabs, and operation identity.</p></div>
<div class="card"><div class="num">03</div><b>Torsion Node</b><p>Authenticated local files, processes, tools, artifacts, durable journal, identity, and optional peer transport.</p></div>
<div class="card"><div class="num">04</div><b>Participant Edge</b><p>An optional participant-owned cloud cell for persistent endpoints, encrypted buffering, release state, and local-node handoff.</p></div>
</div>
</div></section>

<section class="section"><div class="wrap">
<div class="eyebrow">Do not collapse these decisions</div><h2>Permission, trust, assurance, and acceptance are independent.</h2>
<div class="grid four">
<div class="card"><b>Permission</b><p>May this exact operation execute under the selected authority profile?</p></div>
<div class="card"><b>Participant trust</b><p>How reliable is this participant for this task, role, consequence, device, and context?</p></div>
<div class="card"><b>Assurance</b><p>Which properties of identity, execution, observation, isolation, recovery, and attestation are actually supported?</p></div>
<div class="card"><b>Acceptance</b><p>Who is willing to rely on this exact result, for what purpose, despite what uncertainty?</p></div>
</div>
</div></section>

<section class="section"><div class="wrap split">
<div><div class="eyebrow">Runtime invariants</div><h2>Effects must be observable and recoverable.</h2>
<ul><li>Durable identities are separate from ephemeral browser tab IDs.</li><li>Non-idempotent effects are observed before retry.</li><li>Provider adapters are interaction contracts, not one selector.</li><li>Participant model credentials remain local.</li><li>Explicit unrestricted owner profiles remain expressible.</li><li>Cloudflare and peer networking remain optional.</li></ul>
<div class="actions"><a class="btn" href="https://spec.torsionfield.de/#section-2">Architectural invariants</a></div></div>
<div class="terminal"><header>OPERATION STATE</header><pre>created
→ accepted
→ routing
→ running
→ awaiting_result
→ succeeded | failed
→ unknown_outcome

UNKNOWN_OUTCOME:
the effect may have occurred,
so observe before retry.</pre></div>
</div></section>

<section class="section"><div class="wrap">
<div class="eyebrow">Capabilities</div><h2>Useful before the network exists.</h2>
<div class="grid">
<div class="card"><b>Generate and install userscripts</b><p>Full metadata, grants, match patterns, versions, enabled state, provenance, run evidence, and rollback.</p></div>
<div class="card"><b>Provider-independent chat execution</b><p>ChatGPT, Gemini, Perplexity, GitHub Copilot, Grok, AI Studio, and other pages through explicit adapters.</p></div>
<div class="card"><b>Protected agent tabs</b><p>Durable agent identity, restoration, ownership, anti-discard policy, and explicit release.</p></div>
<div class="card"><b>Local execution</b><p>Files, processes, MCP tools, artifacts, and long-running work through the Torsion Node.</p></div>
<div class="card"><b>Participant-owned edge cells</b><p>Cloudflare is the first reference binding, not the semantic identity of the capability.</p></div>
<div class="card"><b>ForkSense</b><p>Study current code, rejected proposals, forks, maintenance, and executable evidence before external integration.</p></div>
</div></div></section>

<section class="section"><div class="wrap split">
<div><div class="eyebrow">Current implementation boundary</div><h2>Architecture and evidence remain separate.</h2>
<p class="section-intro">The public specification defines the intended runtime. Dated implementation evidence records what has actually passed. The Windows semantic harness has verified tests; the complete ScriptCat extension, Torsion Node, Debian runner, and participant edge pilot remain implementation work rather than implied completion.</p>
<div class="actions"><a class="btn" href="https://spec.torsionfield.de/spec/implementation-evidence-2026-08-02.html">Read dated evidence</a><a class="btn" href="https://github.com/FreesoSaiFared/torsionfield">Inspect source</a></div></div>
<div class="card"><b>Honest status</b><p>Specification: v3.2.</p><p>Product site: live.</p><p>Repository: public.</p><p>Complete integrated runtime: not yet delivered.</p><p>Participant Edge: approved for a bounded pilot, not general availability.</p></div>
</div></section>

<section id="network" class="section"><div class="wrap split">
<div><div class="eyebrow">Alpha participation</div><h2>Register a person, not their credentials.</h2><p class="section-intro">The alpha form records interest. Provider cookies, model credentials, local files, and private keys remain local. Registration is not required for browser-only use.</p>
<ul><li>Explore or help build the ScriptCat-first runtime.</li><li>Operate a Torsion Node or test a participant-owned edge cell later.</li><li>Publish only capabilities and endpoints you explicitly select.</li></ul></div>
<form id="network-form" class="form">
<div class="field"><label for="displayName">Display name</label><input id="displayName" name="displayName" minlength="2" maxlength="80" required></div>
<div class="field"><label for="email">Email</label><input id="email" name="email" type="email" required></div>
<div class="field"><label for="nodeIntent">How will you begin?</label><select id="nodeIntent" name="nodeIntent"><option value="explore">Explore the extension</option><option value="build">Build and test the runtime</option><option value="node">Operate a Torsion Node</option><option value="edge">Test a participant edge cell</option><option value="project">Create a Transductive project</option></select></div>
<div class="field"><label>Interests</label><label class="check"><input type="checkbox" name="interests" value="userscripts"> Userscripts and site automation</label><label class="check"><input type="checkbox" name="interests" value="agents"> Browser agents and provider adapters</label><label class="check"><input type="checkbox" name="interests" value="edge"> Participant-owned edge infrastructure</label></div>
<input class="honeypot" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
<label class="check"><input name="accepted" type="checkbox" required> I understand this is an alpha-interest registration and does not upload browser credentials.</label>
<button class="btn primary submit-gap" type="submit">Register for alpha</button><div id="form-status" class="status" aria-live="polite"></div>
</form></div></section>
'''
(PUBLIC / "index.html").write_text(page(
    "Torsionfield Runtime — Programmable browser runtime",
    "Torsionfield is a ScriptCat-first programmable browser runtime with local execution, explicit authority, observable effects, recovery, and optional participant-owned edge infrastructure.",
    home, PRODUCT
), encoding="utf-8")

doc_items = [
("index","Overview"),("getting-started","Getting started"),("product-completeness","Product completeness"),
("architecture","Architecture"),("killer-features","Capabilities"),("adapters","Provider adapters"),
("node-network","Torsion Node and network"),("security","Authority and evidence"),("implementation","Implementation path"),
("prompt-commits","Prompt commits"),("incorporation","External source reuse"),("source-map","Specification map"),
("source-userscripts","Userscript foundation"),("source-agents","Browser agents"),("source-workflows","Workflow representations"),
("source-capture","Capture and recovery"),("cloudflare-free-tier","Participant Edge / Cloudflare"),("sites","First-party sites"),
("glossary","Glossary")
]
def docs_nav(active):
    links = ['<a href="https://torsionfield.de/">← Product site</a>']
    for slug,label in doc_items:
        href = "/" if slug=="index" else f"/{slug}"
        cls = ' class="active"' if slug==active else ""
        links.append(f'<a data-doc href="{href}"{cls}>{escape(label)}</a>')
    return '<aside class="side"><input id="doc-search" class="doc-search" type="search" placeholder="Filter documentation">' + "".join(links) + '</aside>'

def doc(slug,title,lead,body):
    article = f'<article class="article"><span class="tag">DOCUMENTATION · SPEC v3.2</span><h1>{escape(title)}</h1><p class="lead">{lead}</p>{body}</article>'
    canonical = f"https://docs.torsionfield.de/{'' if slug=='index' else slug}"
    html = head(f"{title} — Torsionfield Docs", lead, canonical) + f'<body>{nav}<main class="docs wrap">{docs_nav(slug)}{article}</main>{footer}<script src="/app.js" defer></script></body></html>'
    (DOCS / ("index.html" if slug=="index" else slug+".html")).write_text(html,encoding="utf-8")

doc("index","Documentation overview","A direct map from the public specification to the implementation that must actually work.",r'''
<div class="callout"><b>Start with the vertical slice.</b> A user selects a page element and goal; an authenticated AI page generates a userscript; Torsionfield installs it in ScriptCat, runs it, observes the requested effect, repairs failures, and retains or rolls back the result.</div>
<h2>Read by objective</h2>
<div class="grid"><div class="card"><b>Understand the product</b><p>Architecture, Capabilities, Product completeness.</p></div><div class="card"><b>Build the first release</b><p>Getting started, Provider adapters, Torsion Node, Implementation path.</p></div><div class="card"><b>Understand staged systems</b><p>Participant Edge, external source reuse, Prompt Commits, first-party sites.</p></div></div>
<h2>Current authority</h2><p>The public specification is the design authority. Executable repository and live-site evidence decide what currently exists. Dated implementation evidence must not be inflated into completion.</p>
<p>''' + spec_link(1,"Open specification v3.2") + '''</p>''')

doc("getting-started","Getting started","Begin with one real webpage behavior, not the complete future network.",r'''
<h2>The smallest complete run</h2><ol><li>Select a webpage and the behavior to change.</li><li>Select the exact target element when automatic discovery is ambiguous.</li><li>Open or reuse an authenticated AI conversation.</li><li>Generate one complete userscript.</li><li>Install it into the real ScriptCat registry.</li><li>Run it on the target page.</li><li>Observe the postcondition.</li><li>Repair from captured failure evidence or roll back.</li></ol>
<h2>What is not required</h2><p>No Cloudflare account, Torsion Node, peer network, browser fork, token system, or distributed governance service is required for this first result.</p>
<p>''' + spec_link(21,"Implementation work packet") + '''</p>''')

doc("product-completeness","Product completeness","Separate the first useful release from staged architecture and from implementation evidence.",r'''
<table><thead><tr><th>Layer</th><th>Required now</th><th>Status meaning</th></tr></thead><tbody>
<tr><td>ScriptCat-first browser loop</td><td>Yes</td><td>First complete product boundary.</td></tr>
<tr><td>Torsion Node local execution</td><td>Yes for full local runtime</td><td>Files, processes, tools, artifacts, durable work.</td></tr>
<tr><td>Peer network</td><td>No for browser-only value</td><td>Optional collaboration and capability exchange.</td></tr>
<tr><td>Participant Edge Plane</td><td>No</td><td>Approved bounded pilot; Cloudflare is first provider binding.</td></tr>
<tr><td>Chromium-derived integration</td><td>No</td><td>Optional stronger native assurance.</td></tr>
</tbody></table>
<h2>Completion rule</h2><p>A page, script, or action is not complete because code was generated. It is complete when the real target behavior is observed and the result can be retained or reversed.</p>
<p>''' + spec_link(24) + '''</p>''')

doc("architecture","Architecture","The runtime is split by actual execution boundary rather than by organizational role.",r'''
<h2>Planes</h2><ul><li><b>Chat Runtime:</b> provider adapters, composers, streams, messages, attachments.</li><li><b>ScriptCat:</b> router, Mother Script, registry, mutation, target selection, agent tabs.</li><li><b>Torsion Node:</b> local IPC, journal, files, processes, artifacts, identity, optional peer transport.</li><li><b>Participant Edge:</b> optional participant-owned persistent endpoint and encrypted buffer.</li></ul>
<h2>One operation</h2><pre>origin → Router → provider adapter → target effect
       → observed postcondition → evidence → origin</pre>
<p>Durable operation, agent, endpoint, and artifact identities are not browser tab IDs. Transport can restart while logical work survives.</p>
<p>''' + spec_link(4) + '''</p>''')

doc("killer-features","Capabilities","The useful capability is a closed generate–install–run–observe–repair loop.",r'''
<div class="grid">
<div class="card"><b>Native userscript installation</b><p>Install and update complete scripts in ScriptCat, not merely download files.</p></div>
<div class="card"><b>Provider adapters</b><p>Operate authenticated AI pages through verified interaction contracts.</p></div>
<div class="card"><b>Target selection</b><p>Return a verified selector bundle only to the requesting operation.</p></div>
<div class="card"><b>Transactional mutation</b><p>Stage, validate, activate, boot-check, and automatically restore.</p></div>
<div class="card"><b>Agent-tab recovery</b><p>Rebind durable agents when tabs reload, close, or move.</p></div>
<div class="card"><b>Local tools</b><p>Use Torsion Node for deterministic work that should outlive the browser turn.</p></div>
</div>
<p>''' + spec_link(8,"Mother Script and commands") + '''</p>''')

doc("adapters","Provider adapters","A provider adapter owns the complete web interaction contract for one provider surface.",r'''
<h2>Contract</h2><p>Match the right host and route; locate the composer; insert and verify text; submit and verify the effect; attach and verify files; identify messages; observe streaming output; detect completion; extract final content and diagnostics.</p>
<h2>Recovery</h2><p>Selectors are candidates with confidence and fingerprints. A matching selector that identifies the wrong semantic object is rejected. Lost submission acknowledgement remains an unknown outcome until the page is observed.</p>
<h2>Seed providers</h2><p>ChatGPT, Gemini, GitHub Copilot, DeepSeek, Grok, Perplexity, Google AI Studio, OpenRouter, T3 Chat, Mistral, Kimi, Z.ai, Qwen, configured providers, and a scored generic fallback. Claude must fail explicitly until independently implemented.</p>
<p>''' + spec_link(11) + '''</p>''')

doc("node-network","Torsion Node and network","The daemon supplies durable local execution; the network remains optional.",r'''
<h2>Torsion Node</h2><p>A resident local process provides authenticated IPC, files, processes, artifacts, a durable operation journal, identity, configurable commands, and optional libp2p transport.</p>
<h2>Credential boundary</h2><p>Each participant uses their own browser sessions, APIs, or local models. Torsionfield does not pool or centrally possess model credentials, browser cookies, or subscription access.</p>
<h2>Network role</h2><p>Peers exchange signed capabilities and task results. Cloudflare may coordinate presence and rendezvous, but it is not the mandatory data path.</p>
<p>''' + spec_link(15,"Torsion Node") + ''' · ''' + spec_link(17,"Peer and cloud control") + '''</p>''')

doc("security","Authority and evidence","The system preserves capability reach while making authority, evidence, and acceptance explicit.",r'''
<h2>Four separate questions</h2><ol><li>Is the operation permitted?</li><li>How reliable is this participant for this task?</li><li>What does the execution path actually assure?</li><li>Who accepts this exact result for which purpose?</li></ol>
<h2>Owner authority</h2><p>Restrictive profiles and explicitly unrestricted local-owner profiles are both expressible. Local authority does not silently transfer to peers, projects, verifiers, or release systems.</p>
<h2>What evidence cannot prove</h2><p>A signature authenticates a signer; hosting does not prove trusted execution; a model response is a proposal; provider execution cannot be cryptographically proven without provider receipts or a trustworthy attested path.</p>
<p>''' + spec_link(18,"Permission model") + ''' · ''' + spec_link(36,"Participant trust and acceptance") + '''</p>''')

doc("implementation","Implementation path","Implement the real first path and test the changed behavior.",r'''
<h2>Required first result</h2><pre>page goal
→ generated userscript
→ ScriptCat registry
→ target execution
→ observed effect
→ repair or rollback</pre>
<h2>Narrow evidence</h2><p>Run the normal extension build, the specific provider/target test, and one real browser interaction that distinguishes success from failure. Do not replace this with scaffolding, schemas, or a future network plan.</p>
<h2>Current boundary</h2><p>The public repository and site exist. The full integrated ScriptCat extension, Torsion Node, Debian runner, and participant edge pilot remain to be completed and verified as a single product path.</p>
<p>''' + spec_link(22,"Acceptance matrix") + '''</p>''')

doc("prompt-commits","Prompt commits","A Prompt Commit is a replayable transformation record for maintained external capability reuse.",r'''
<h2>Use only when it solves a real update problem</h2><p>Prompt Commits belong to external capability assimilation where an upstream revision must be re-read, transformed, tested, and compared. They are not required for ordinary local edits.</p>
<h2>Minimum useful record</h2><p>Pinned upstream revision, exact source boundary, intended capability, license constraint, transformation instruction, expected outputs, direct tests, and rollback.</p>
<h2>Authority</h2><p>Model output may propose a transformation; it does not authorize incorporation, licensing, deployment, or activation.</p>
<p>''' + spec_link(26) + '''</p>''')

doc("incorporation","External source reuse","Reuse maintained donor code when it is the shortest reliable route; do not turn reuse into ceremony.",r'''
<h2>Four routes</h2><ul><li>Use upstream directly.</li><li>Wrap an existing interface.</li><li>Extract one bounded component or patch.</li><li>Reimplement behavior when source reuse is unavailable or inappropriate.</li></ul>
<h2>ForkSense</h2><p>When an external-code decision is consequential, inspect current source, issues, rejected proposals, live forks, maintenance, tests, license, and executable evidence. Do not rank candidates by popularity alone.</p>
<p>''' + spec_link(25,"Capability incorporation") + ''' · ''' + spec_link(38,"ForkSense") + '''</p>''')

doc("source-map","Specification map","The 39-section specification separates direct implementation, optional native integration, staged systems, and references.",r'''
<table><thead><tr><th>Range</th><th>Subject</th></tr></thead><tbody>
<tr><td>§1–6</td><td>Mandate, invariants, ScriptCat baseline, architecture, repository, identities.</td></tr>
<tr><td>§7–14</td><td>Router, Mother Script, mutation, selection, adapters, agent tabs, CAT APIs, NetworkScripts.</td></tr>
<tr><td>§15–20</td><td>Torsion Node, identity, networking, permission, recovery, optional Chromium layer.</td></tr>
<tr><td>§21–29</td><td>Implementation, acceptance, product evolution, source reuse, sites, build variants.</td></tr>
<tr><td>§30–38</td><td>Participatory work, provider boundary, verification, TF APIs, governance, semantics, trust, edge cells, ForkSense.</td></tr>
<tr><td>§39</td><td>Primary references.</td></tr>
</tbody></table>
<p><a href="https://spec.torsionfield.de/#contents">Open the full contents →</a></p>''')

doc("source-userscripts","Userscript foundation","ScriptCat is the first implementation substrate and compatibility foundation.",r'''
<h2>Existing baseline</h2><p>ScriptCat already supplies userscript management, background scripts, CAT agent APIs, OPFS, provider/model/task/MCP facilities, and a service-worker/offscreen architecture.</p>
<h2>Torsionfield additions</h2><p>Router Core, provider adapter host, transactional script mutation and installation, agent-tab lifecycle, target selection, daemon bridge, identity/capability handling, and effect evidence.</p>
<h2>Boundary</h2><p>Privileged browser behavior belongs in the extension and is exposed through typed granted APIs; a background userscript does not directly own unrestricted browser internals.</p>
<p>''' + spec_link(3) + '''</p>''')

doc("source-agents","Browser agents","Agent tabs are durable logical actors bound to recoverable browser surfaces.",r'''
<h2>Identity</h2><p>An agent has an <code>agentId</code> independent of its current browser <code>tabId</code>. When a tab closes or reloads, Torsionfield rebinds or restores the logical agent.</p>
<h2>Protection</h2><p>The stock extension can shield input, group and pin tabs, resist discard, and restore closure. It cannot make a browser tab literally uncloseable; native close inhibition is optional Chromium work.</p>
<h2>Scheduling</h2><p>Concurrency follows user configuration, provider policy, and available resources rather than an arbitrary built-in limit.</p>
<p>''' + spec_link(12) + '''</p>''')

doc("source-workflows","Workflow representations","The first product does not need a universal workflow platform.",r'''
<h2>Direct representation</h2><p>The working userscript and its observed test are sufficient for the first vertical slice.</p>
<h2>Later convergence</h2><p>Visual recordings, userscripts, agent plans, imported macros, and NetworkScript endpoints may later share an Operation Graph when two real representations need synchronization.</p>
<h2>Rule</h2><p>Do not create a generic intermediate representation merely because one could exist. Add it when direct code no longer handles the demonstrated editing, conversion, or execution problem.</p>
<p>''' + spec_link(25,"Operation Graph staged target") + '''</p>''')

doc("source-capture","Capture and recovery","Capture only the evidence needed to distinguish success, failure, and unknown outcome.",r'''
<h2>Useful evidence</h2><p>Operation identity, adapter and target identity, before/after observations, console and stack information, relevant DOM changes, screenshot when needed, exit state, and artifact references.</p>
<h2>Recovery</h2><p>On service-worker, browser, or daemon restart, reconcile durable identities with current browser/process state. Observe uncertain effects before retry.</p>
<h2>Not required</h2><p>A generalized telemetry architecture is not a prerequisite. One ordinary trace that exposes the current failure is enough to repair the current failure.</p>
<p>''' + spec_link(19) + '''</p>''')

doc("cloudflare-free-tier","Participant Edge / Cloudflare","Cloudflare is the first reference provider for participant-owned edge cells, not the identity of the architecture.",r'''
<h2>What a cell does</h2><p>A participant edge cell can provide one stable gateway, encrypted object persistence, signed-message receipt, buffering, static diagnostics, release-state reporting, export, health, and local-node inbox/outbox behavior.</p>
<h2>What remains local</h2><p>Root identity keys, provider cookies, model credentials, project plaintext, unrestricted files/processes, high-authority signing, and user acceptance.</p>
<h2>First bounded pilot</h2><p>One Gateway Worker, one D1 schema for encrypted objects and operational metadata, one diagnostics interface, cell identity endpoint, signed-message receipt, export, health, and signed deployment declaration.</p>
<h2>Explicit exclusions</h2><p>No hidden free-tier quota pooling, no global API keys or passwords, no participant model credentials, no unrestricted remote code deployment, and no claim of trusted execution.</p>
<p>''' + spec_link(37) + ''' · <a href="https://torsionfield.de/cloudflare/">Open the public edge-plane page →</a></p>''')

doc("sites","First-party sites","Each domain has a distinct role; core first-party functions use signed protocols rather than fragile scraping.",r'''
<table><thead><tr><th>Site</th><th>Role</th></tr></thead><tbody>
<tr><td>torsionfield.de</td><td>Product, distribution, pairing, membership, releases, provenance, node and edge-cell administration.</td></tr>
<tr><td>transductive.org</td><td>General collaboration, participatory medium, public projects, workflows, and community.</td></tr>
<tr><td>transductive.science</td><td>Research campaigns, task queues, evidence contracts, executable models, result comparison, and publication.</td></tr>
<tr><td>transductive.art</td><td>Experimental ontology, media workflows, generative works, and creative collaboration.</td></tr>
</tbody></table>
<p>''' + spec_link(27) + '''</p>''')

doc("glossary","Glossary","The small set of terms needed to read the runtime without inheriting the whole specification.",r'''
<dl>
<dt><b>Mother Script</b></dt><dd>The userscript runtime that observes AI output, parses commands, invokes CAT/TF capabilities, and manages its mutable core.</dd>
<dt><b>ProviderAdapter</b></dt><dd>The complete interaction contract for an authenticated AI website.</dd>
<dt><b>operationId</b></dt><dd>Stable identity for one requested effect across retries and restarts.</dd>
<dt><b>unknown_outcome</b></dt><dd>The effect may have occurred but confirmation was lost; observe before retry.</dd>
<dt><b>Torsion Node</b></dt><dd>The optional local daemon for durable files, processes, tools, artifacts, identity, and peer transport.</dd>
<dt><b>Participant Edge Cell</b></dt><dd>An optional participant-owned persistent cloud runtime; Cloudflare is the first provider binding.</dd>
<dt><b>Acceptance</b></dt><dd>A named decision to rely on an exact result for a declared purpose despite remaining uncertainty.</dd>
<dt><b>ForkSense</b></dt><dd>Adaptive repository intelligence for external-code decisions.</dd>
</dl>''')

edge_body = r'''
<section class="page-hero wrap section">
<div class="eyebrow">Participant Edge Plane · Reference provider: Cloudflare</div>
<h1>Persistent infrastructure owned by the participant.</h1>
<p class="lead">Cloudflare is the first implementation target for an optional edge cell between the intermittently reachable local Torsion Node and the central coordination surface. It is a provider binding, not Torsionfield identity, authority, or semantic truth.</p>
<div class="status-row"><span class="status-chip stage">BOUNDED PILOT</span><span class="status-chip">NOT REQUIRED FOR LOCAL USE</span><span class="status-chip">NO HIDDEN QUOTA POOLING</span></div>
</section>
<section class="section"><div class="wrap">
<div class="eyebrow">The role</div><h2>Centralized constitution, distributed execution, cryptographically partitioned knowledge.</h2>
<div class="grid four">
<div class="card"><b>Superfluid Nexus</b><p>Namespace, membership, project topology, routing, official release channels, and governance.</p></div>
<div class="card"><b>Participant Edge Cell</b><p>Stable gateway, encrypted buffering, endpoints, diagnostics, release state, export, and health.</p></div>
<div class="card"><b>Local Runtime</b><p>Root identity, browser sessions, provider credentials, plaintext work, local files, and high authority.</p></div>
<div class="card"><b>Governed source</b><p>Git revisions, tests, accepted release artifacts, migrations, canaries, and rollback.</p></div>
</div></div></section>
<section class="section"><div class="wrap">
<div class="eyebrow">Five authorities</div><h2>OAuth is infrastructure authority only.</h2>
<div class="grid">
<div class="card"><b>Infrastructure authority</b><p>May create or modify provider resources such as Workers, D1, routes, and deployments.</p></div>
<div class="card"><b>Capability authority</b><p>May publish endpoints, accept project tasks, store objects, or participate in Torsionfield projects.</p></div>
<div class="card"><b>Decryption authority</b><p>May read protected project or task content.</p></div>
<div class="card"><b>Release authority</b><p>May accept a software revision for deployment.</p></div>
<div class="card"><b>Acceptance authority</b><p>May rely on an exact result or deployment for a declared purpose.</p></div>
</div></div></section>
<section class="section"><div class="wrap split">
<div><div class="eyebrow">First bounded pilot</div><h2>One cell, one complete path.</h2><ol><li>Gateway Worker and static diagnostics.</li><li>D1 storage for encrypted objects and operational metadata.</li><li>Cell identity and health endpoints.</li><li>Signed-message receipt and replay protection.</li><li>Local-node inbox and handoff.</li><li>Provider-independent export.</li><li>Signed deployment declaration and rollback reference.</li></ol></div>
<div class="terminal"><header>PORTABLE CAPABILITIES</header><pre>cap.edge.identity/1
cap.edge.endpoint/1
cap.edge.object-store/1
cap.edge.message-buffer/1
cap.edge.presence/1
cap.edge.static-interface/1
cap.edge.project-index/1
cap.edge.release-state/1
cap.edge.export/1
cap.edge.health/1</pre></div>
</div></section>
<section class="section"><div class="wrap">
<div class="eyebrow">What the cell never receives by default</div><h2>The network can organize a cell without owning the participant.</h2>
<div class="grid">
<div class="card"><b>No provider passwords or global keys</b><p>Authorization uses the smallest OAuth scope required by the selected cell profile.</p></div>
<div class="card"><b>No root identity keys</b><p>Root and high-authority keys remain in the signed client or local node.</p></div>
<div class="card"><b>No model cookies or credentials</b><p>Authenticated model execution remains participant-owned and local.</p></div>
<div class="card"><b>No hidden workload pooling</b><p>Shared work requires an explicit active WorkOffer and visible budget.</p></div>
<div class="card"><b>No trusted-execution claim</b><p>Provider hosting and signatures do not establish semantic correctness.</p></div>
<div class="card"><b>No permanent Cloudflare dependency</b><p>Portable contracts and export must not depend on Cloudflare identifiers.</p></div>
</div>
<div class="actions"><a class="btn primary" href="https://spec.torsionfield.de/#section-37">Read normative Participant Edge requirements</a><a class="btn" href="https://docs.torsionfield.de/cloudflare-free-tier">Implementation guide</a></div>
</div></section>
'''
(PUBLIC / "cloudflare" / "index.html").write_text(page(
    "Participant Edge Plane — Torsionfield",
    "Cloudflare is the first reference provider for participant-owned Torsionfield edge cells: persistent endpoints, encrypted buffering, release state, export, and local-node handoff.",
    edge_body, "https://torsionfield.de/cloudflare/"
), encoding="utf-8")

edge_prompt = r'''SYSTEM ROLE: TORSIONFIELD PARTICIPANT EDGE IMPLEMENTER

Implement one bounded participant-owned edge cell matching Torsionfield Runtime Specification v3.2 §37.

Use the existing repository, Cloudflare account authorization, and current Wrangler project. Do not design a generic cloud platform.

Required complete path:
1. one Gateway Worker;
2. one D1 schema for encrypted objects and operational metadata;
3. cell identity and health endpoints;
4. signed-message receipt with replay protection and stable operation identity;
5. encrypted object storage;
6. local-node inbox and handoff;
7. provider-independent export;
8. signed deployment declaration connected to source, build, migration, release, and rollback evidence.

Do not collect provider passwords, global API keys, model cookies, model credentials, user root private keys, or unrestricted local credentials.

Keep infrastructure authority, Torsionfield capability authority, decryption authority, release authority, and acceptance authority separate.

Do not use participant free-tier resources for unrelated workloads without an explicit active WorkOffer and visible budget.

Run the real Wrangler dry-run, deploy through the authenticated path, and verify the live cell endpoints. Report the exact Worker/version, resources changed, live checks, and one real remaining boundary.
'''
(PUBLIC / "cloudflare" / "chatgpt56-sol-prompt.txt").write_text(edge_prompt, encoding="utf-8")

fs = r'''
<section class="page-hero wrap section"><div class="eyebrow">ForkSense · Specification §38</div><h1>Study the repository before inheriting its assumptions.</h1><p class="lead">ForkSense examines current code, maintenance, known problems, rejected proposals, active forks, contributor work, and executable evidence before Torsionfield adopts, wraps, extracts, forks, or declines external software.</p><div class="status-row"><span class="status-chip stage">STAGED TARGET</span><span class="status-chip">DOES NOT BLOCK DIRECT WORK</span></div></section>
<section class="section"><div class="wrap">
<div class="grid four"><div class="card"><b>Current code</b><p>Default branch, releases, recent commits, tests, issues, TODOs, and actual operational use.</p></div><div class="card"><b>Rejected proposals</b><p>Distinguish technical failure, scope mismatch, timing, duplication, security, licensing, and unknown reasons.</p></div><div class="card"><b>Fork ecology</b><p>Trace ancestry, unique patches, maintenance, tests, adoption, and upstream synchronization burden.</p></div><div class="card"><b>Executable decision</b><p>Build or test the leading candidate instead of choosing by stars, prose, or popularity.</p></div></div>
</div></section>
<section class="section"><div class="wrap split"><div><div class="eyebrow">Minimum experiment</div><h2>One repository, two real candidates.</h2><ol><li>Ingest current branches, releases, issues, pull requests, reviews, and recent commits.</li><li>Find one rejected or deferred proposal and one active fork or successor.</li><li>Revise the research route once in response to evidence.</li><li>Produce two competing integration candidates.</li><li>Run a bounded build or code-level test.</li><li>Return a current recommendation with freshness, uncertainty, exit, and rollback.</li></ol></div><div class="terminal"><header>DECISION OUTPUT</header><pre>ADOPT   upstream already fits
WRAP    preserve upstream + add contract
EXTRACT reuse one bounded seam or patch
FORK    sustainable evidenced divergence
ALLY    cooperate with exact maintainers
DECLINE evidence or fit is insufficient</pre></div></div></section>
<section class="section"><div class="wrap"><h2>No social authority score.</h2><p class="section-intro">Public contributor context may route research toward relevant technical work. Stars, follows, affiliations, popularity, or inferred personal traits do not establish competence, authority, trust, or governance power.</p><div class="actions"><a class="btn primary" href="https://spec.torsionfield.de/#section-38">Read ForkSense requirements</a></div></div></section>
'''
(PUBLIC / "forksense" / "index.html").write_text(page(
    "ForkSense — Adaptive Repository Intelligence",
    "ForkSense studies current code, rejected proposals, active forks, maintenance, and executable evidence before Torsionfield integrates external software.",
    fs, "https://forksense.torsionfield.de/"
), encoding="utf-8")

sci = r'''
<section class="page-hero wrap section"><div class="eyebrow">Transductive science on Torsionfield</div><h1>Executable research branches use the same runtime.</h1><p class="lead">Scientific projects are applications of Torsionfield’s ordinary operations, artifacts, capability grants, task leases, evidence, and recovery. They do not create a second scheduler, permission system, or execution runtime.</p><div class="status-row"><span class="status-chip stage">APPLICATION LAYER</span><span class="status-chip">SCRIPTCAT-FIRST PATH UNCHANGED</span></div></section>
<section class="section"><div class="wrap"><div class="grid four"><div class="card"><b>Question</b><p>The discriminating problem and the observations that matter.</p></div><div class="card"><b>Competing branch</b><p>An executable candidate with explicit assumptions and predicted distinctions.</p></div><div class="card"><b>Experiment</b><p>A bounded task run through a declared browser, local, peer, or edge capability.</p></div><div class="card"><b>Evidence</b><p>Artifacts, receipts, replication, limits, disagreement, and acceptance remain separate.</p></div></div></div></section>
<section class="section"><div class="wrap split"><div><h2>Minimum vertical slice</h2><ol><li>Create one local project with two competing candidates.</li><li>Attach explicit assumptions and one discriminating test.</li><li>Run one bounded experiment through Torsion Node or a browser provider.</li><li>Return the artifact and execution evidence.</li><li>Have another participant or session reproduce or challenge it.</li><li>Preserve both branches and the evidence vector.</li></ol></div><div class="terminal"><header>EVIDENCE DOES NOT COLLAPSE INTO TRUTH</header><pre>implemented ≠ verified
reproduced ≠ uniquely explained
signed ≠ correct
accepted locally ≠ accepted publicly
operational closure ≠ ontological closure</pre></div></div></section>
<section class="section"><div class="wrap"><div class="actions"><a class="btn primary" href="https://transductive.science/">Transductive Science</a><a class="btn" href="https://spec.torsionfield.de/#section-30">Participatory work specification</a></div></div></section>
'''
(PUBLIC / "scientific-evolution-protocol" / "index.html").write_text(page(
    "Executable Research Branches — Torsionfield",
    "Scientific projects use Torsionfield operations, artifacts, capability grants, evidence, recovery, and acceptance without creating a second runtime.",
    sci, "https://torsionfield.de/scientific-evolution-protocol/"
), encoding="utf-8")

manifest = {
    "name":"Torsionfield Runtime",
    "short_name":"Torsionfield",
    "description":"ScriptCat-first programmable browser runtime with local execution, explicit authority, observable effects, and recovery.",
    "start_url":"/","display":"standalone","background_color":"#07100c","theme_color":"#07100c",
    "icons":[{"src":"/favicon.svg","sizes":"any","type":"image/svg+xml"}]
}
(PUBLIC/"manifest.webmanifest").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
(DOCS/"manifest.webmanifest").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
(PUBLIC/"404.html").write_text(page("Not found — Torsionfield","The requested Torsionfield page was not found.",'<section class="page-hero wrap section"><div class="eyebrow">404</div><h1>Page not found.</h1><p class="lead">Return to the product, documentation, or specification.</p><div class="actions"><a class="btn primary" href="/">Product</a><a class="btn" href="https://docs.torsionfield.de/">Docs</a><a class="btn" href="https://spec.torsionfield.de/">Specification</a></div></section>'),encoding="utf-8")
(DOCS/"404.html").write_text((PUBLIC/"404.html").read_text(encoding="utf-8"),encoding="utf-8")
(PUBLIC/"robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: https://torsionfield.de/sitemap.xml\n",encoding="utf-8")

urls = [
"https://torsionfield.de/","https://torsionfield.de/cloudflare/","https://torsionfield.de/scientific-evolution-protocol/",
"https://spec.torsionfield.de/","https://forksense.torsionfield.de/","https://docs.torsionfield.de/"
] + [f"https://docs.torsionfield.de/{slug}" for slug,_ in doc_items if slug!="index"]
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{u}</loc></url>\n' for u in urls) + '</urlset>\n'
(PUBLIC/"sitemap.xml").write_text(sitemap,encoding="utf-8")

worker = ROOT / "src" / "worker.js"
w = worker.read_text(encoding="utf-8")
w = w.replace('siteRevision:"2026.08.02-alpha.2",networkRegistration:"alpha",documentation:"online"', 'siteRevision:"2026.08.03-spec-3.2",specVersion:"3.2",networkRegistration:"alpha",documentation:"online",participantEdge:"bounded-pilot"')
w = w.replace('localFirst:true});', 'localFirst:true,specification:"https://spec.torsionfield.de/",participantEdge:{status:"bounded-pilot",referenceProvider:"cloudflare-oauth-cell/1"}});')
worker.write_text(w,encoding="utf-8")

print("Rebuilt product, docs, Participant Edge, ForkSense, science application, assets, sitemap, and API revision.")
