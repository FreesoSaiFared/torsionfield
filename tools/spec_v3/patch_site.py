from pathlib import Path

root = Path(r"E:\Transductive_MCP_Work\torsionfield-site")
worker = root / "src" / "worker.js"
wrangler = root / "wrangler.jsonc"

source = worker.read_text(encoding="utf-8")
needle = 'async function docs(e,r,u){let p=u.pathname;if(p==="/")p="/index.html";else if(p.endsWith("/"))p+="index.html";else if(!p.split("/").pop().includes("."))p+=".html";let x=await asset(e,r,"/docs"+p);if(x.status!==404)return x;const f=await asset(e,r,"/docs/404.html");return new Response(f.body,{status:404,headers:f.headers})}'
addition = needle + '\nasync function spec(e,r,u){let p=u.pathname;if(p==="/")p="/spec/index.html";else if(p.startsWith("/spec/")){if(p.endsWith("/"))p+="index.html";else if(!p.split("/").pop().includes("."))p+=".html"}else if(p.endsWith("/"))p="/spec"+p+"index.html";else if(!p.split("/").pop().includes("."))p="/spec"+p+".html";else p="/spec"+p;let x=await asset(e,r,p);if(x.status!==404)return x;const f=await asset(e,r,"/spec/index.html");return new Response(f.body,{status:404,headers:f.headers})}'
if 'async function spec(' not in source:
    if needle not in source:
        raise RuntimeError("docs function anchor not found")
    source = source.replace(needle, addition, 1)
route_anchor = 'if(host==="docs.torsionfield.de")return docs(e,r,u);'
if 'if(host==="spec.torsionfield.de")return spec(e,r,u);' not in source:
    source = source.replace(route_anchor, 'if(host==="spec.torsionfield.de")return spec(e,r,u);' + route_anchor, 1)
worker.write_text(source, encoding="utf-8")

config = wrangler.read_text(encoding="utf-8")
route = '    { "pattern": "spec.torsionfield.de", "custom_domain": true },\n'
if '"spec.torsionfield.de"' not in config:
    config = config.replace('    { "pattern": "docs.torsionfield.de", "custom_domain": true }', route + '    { "pattern": "docs.torsionfield.de", "custom_domain": true }', 1)
wrangler.write_text(config, encoding="utf-8")
print("patched", worker, wrangler)
