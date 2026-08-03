from pathlib import Path
import json

ROOT = Path(r"E:\Transductive_MCP_Work\torsionfield-site")
worker = ROOT / "src" / "worker.js"
wrangler = ROOT / "wrangler.jsonc"
sitemap = ROOT / "public" / "sitemap.xml"

text = worker.read_text(encoding="utf-8")
if "async function forksense" not in text:
    marker = "async function spec(e,r,u){"
    helper = "async function forksense(e,r,u){let p=u.pathname;if(p===\"/\")p=\"/forksense/index.html\";else if(p.endsWith(\"/\"))p=\"/forksense\"+p+\"index.html\";else if(!p.split(\"/\").pop().includes(\".\"))p=\"/forksense\"+p+\".html\";else p=\"/forksense\"+p;let x=await asset(e,r,p);if(x.status!==404)return x;const f=await asset(e,r,\"/forksense/index.html\");return new Response(f.body,{status:404,headers:f.headers})}\n"
    text = text.replace(marker, helper + marker, 1)
if 'host==="forksense.torsionfield.de"' not in text:
    text = text.replace('if(host==="spec.torsionfield.de")return spec(e,r,u);', 'if(host==="forksense.torsionfield.de")return forksense(e,r,u);if(host==="spec.torsionfield.de")return spec(e,r,u);', 1)
worker.write_text(text, encoding="utf-8")

cfg = wrangler.read_text(encoding="utf-8")
if 'forksense.torsionfield.de' not in cfg:
    cfg = cfg.replace('{ "pattern": "spec.torsionfield.de", "custom_domain": true },', '{ "pattern": "spec.torsionfield.de", "custom_domain": true },\n    { "pattern": "forksense.torsionfield.de", "custom_domain": true },', 1)
wrangler.write_text(cfg, encoding="utf-8")

if sitemap.exists():
    sm = sitemap.read_text(encoding="utf-8")
    entry = "  <url><loc>https://forksense.torsionfield.de/</loc></url>\n"
    if "forksense.torsionfield.de" not in sm:
        sm = sm.replace("</urlset>", entry + "</urlset>")
        sitemap.write_text(sm, encoding="utf-8")

print(json.dumps({
    "workerRoute": "forksense.torsionfield.de",
    "asset": "public/forksense/index.html",
    "manifest": "public/forksense/manifest.json",
    "updated": True
}, indent=2))
