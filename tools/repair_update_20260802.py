from pathlib import Path
import json, re
ROOT=Path(r"E:\Transductive_MCP_Work\torsionfield-site")
PUBLIC=ROOT/"public"; DOCS=PUBLIC/"docs"; SPEC=PUBLIC/"spec"

p=DOCS/"implementation.html"; t=p.read_text(encoding="utf-8")
new='<h2>Current single goal</h2><p>Apply the verified semantic calls to the real ScriptCat fork, beginning only with canonical userscript install and update. The upstream is pinned at <code>413bee9593259179e9db72be61d98f060fcf5738</code>. Stable identity must survive ten updates, rollback must restore prior source, and the same acceptance campaign must run on the host and a repaired Debian 13 executor.</p><h2>Executable harness status</h2><p>The Node.js harness has passed 7/7 tests and an authenticated loopback smoke test. It is a contract-and-acceptance model, not a substitute for ScriptCat source assimilation. The Debian executor is currently <b>NEEDS_REPAIR</b>.</p><h2>ScriptCat patch dossier</h2><p>The controlling dossier now has a pinned upstream commit, full source archive and exact source-symbol search evidence. The next packet must name every changed file, symbol, manifest permission, migration, test and rebase risk for the two initial calls.</p><h2>Closure deliverables</h2>'
t,n=re.subn(r'<h2>Current single goal</h2>.*?<h2>Closure deliverables</h2>',new,t,count=1,flags=re.S)
if n!=1 and 'Executable harness status' not in t: raise RuntimeError("implementation section not replaced")
p.write_text(t,encoding="utf-8")

p=DOCS/"index.html"; t=p.read_text(encoding="utf-8")
old='<div class="callout"><b>Version 2.1 product architecture.</b> This documentation describes the intended final product and separately marks what remains to be implemented, verified or packaged.</div>'
new='<div class="callout"><b>Version 3.2 architecture plus dated implementation evidence.</b> Normative design remains separate from executable results. The 2 August evidence records a verified Node.js semantic harness, 7/7 tests, an HTTP smoke test and a Debian 13 <b>NEEDS_REPAIR</b> boundary.</div><p><a href="https://spec.torsionfield.de/spec/implementation-evidence-2026-08-02.html">Read the implementation evidence</a> or use the <a href="/cloudflare-free-tier">Cloudflare free-tier composition guide</a>.</p>'
if old in t: t=t.replace(old,new,1)
elif 'Version 3.2 architecture plus dated implementation evidence' not in t: raise RuntimeError("docs index marker missing")
p.write_text(t,encoding="utf-8")

for p in DOCS.glob("*.html"):
    t=p.read_text(encoding="utf-8")
    t=t.replace('Alpha product architecture &#8212; 31 July 2026.','Alpha implementation programme - 2 August 2026.')
    t=t.replace('Alpha product architecture - 31 July 2026.','Alpha implementation programme - 2 August 2026.')
    p.write_text(t,encoding="utf-8")

p=PUBLIC/"index.html"; t=p.read_text(encoding="utf-8")
if 'href="/cloudflare/">Cloudflare field guide</a>' not in t:
    t=t.replace('<a href="/scientific-evolution-protocol/">Science protocol</a>','<a href="/scientific-evolution-protocol/">Science protocol</a><a href="/cloudflare/">Cloudflare field guide</a>',1)
if '<b>Cloudflare free-tier composer</b>' not in t:
    marker='<div class="card"><b>Scientific evolution protocol</b><p>Persist hypotheses, competing model branches, evidence, donated compute and independent verification as executable project objects.</p><p><a href="/scientific-evolution-protocol/">Read the protocol &#8594;</a></p></div>'
    if marker not in t: raise RuntimeError("product marker missing")
    t=t.replace(marker,marker+'<div class="card"><b>Cloudflare free-tier composer</b><p>Verified service limits, quota-aware deployment combinations and a reusable reasoning prompt for turning app ideas into honest service graphs.</p><p><a href="/cloudflare/">Open the field guide</a></p></div>',1)
t=t.replace('Alpha product architecture &#8212; 31 July 2026.','Alpha implementation programme - 2 August 2026.')
t=t.replace('Alpha product architecture - 31 July 2026.','Alpha implementation programme - 2 August 2026.')
p.write_text(t,encoding="utf-8")

p=SPEC/"index.html"; t=p.read_text(encoding="utf-8")
if 'implementation-evidence-2026-08-02' not in t:
    md='<a href="/spec/torsionfield-runtime-spec-v3.2.md" download>Markdown</a>'
    if md in t: t=t.replace(md,md+'<a href="/spec/implementation-evidence-2026-08-02.html">Implementation evidence</a>',1)
    note='<p class="cover-note">'
    if note in t: t=t.replace(note,'<p class="cover-note"><strong>Non-normative implementation update:</strong> a Node.js semantic harness passed 7/7 host tests and HTTP smoke; Debian 13 remains NEEDS_REPAIR. <a href="/spec/implementation-evidence-2026-08-02.html">Evidence.</a></p>'+note,1)
p.write_text(t,encoding="utf-8")

p=SPEC/"manifest.json"; m=json.loads(p.read_text(encoding="utf-8"))
m["implementationEvidence"]={"date":"2026-08-02","status":"VERIFIED_HOST","debian13":"NEEDS_REPAIR","path":"/spec/implementation-evidence-2026-08-02.html","upstreamCommit":"413bee9593259179e9db72be61d98f060fcf5738","archiveSha256":"0f7b10780a7ab9c71b6697c7510b0e1ae56f2d8851af029ddfe84beadbd9bcea"}
p.write_text(json.dumps(m,indent=2)+"\n",encoding="utf-8")

p=PUBLIC/"sitemap.xml"; t=p.read_text(encoding="utf-8")
for u in ["https://torsionfield.de/cloudflare/","https://docs.torsionfield.de/cloudflare-free-tier","https://spec.torsionfield.de/spec/implementation-evidence-2026-08-02.html"]:
    tag="<url><loc>"+u+"</loc></url>"
    if tag not in t: t=t.replace("</urlset>",tag+"</urlset>")
p.write_text(t,encoding="utf-8")

p=ROOT/"src"/"worker.js"; t=p.read_text(encoding="utf-8").replace('siteRevision:"2026.07.31-alpha.1"','siteRevision:"2026.08.02-alpha.2"'); p.write_text(t,encoding="utf-8")
p=PUBLIC/"styles.css"; t=p.read_text(encoding="utf-8")
addition="\n.table-scroll{overflow-x:auto;margin:1.2rem 0 2rem}.matrix{width:100%;border-collapse:collapse;font-size:.92rem}.matrix th,.matrix td{border:1px solid var(--line,#2d3834);padding:.8rem;vertical-align:top;text-align:left}.matrix thead th{position:sticky;top:0;background:var(--panel,#111816)}.prompt-block{white-space:pre-wrap;max-height:52rem;overflow:auto;font-size:.82rem;line-height:1.45}\n"
if ".table-scroll" not in t: p.write_text(t+addition,encoding="utf-8")
print("Repair continuation completed.")
