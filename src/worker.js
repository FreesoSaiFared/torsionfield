const H={"Content-Security-Policy":"default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'","Referrer-Policy":"strict-origin-when-cross-origin","Permissions-Policy":"camera=(), microphone=(), geolocation=(), payment=()","X-Content-Type-Options":"nosniff","X-Frame-Options":"DENY"};
function wrap(r,x={}){const h=new Headers(r.headers);for(const[k,v]of Object.entries(H))h.set(k,v);for(const[k,v]of Object.entries(x))h.set(k,v);return new Response(r.body,{status:r.status,statusText:r.statusText,headers:h})}
function json(d,s=200){return wrap(new Response(JSON.stringify(d),{status:s,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}}))}
function email(v){return typeof v==="string"&&v.length<=254&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)}
async function asset(e,r,p){const u=new URL(r.url);u.pathname=p;return wrap(await e.ASSETS.fetch(new Request(u,r)))}
async function docs(e,r,u){let p=u.pathname;if(p==="/")p="/index.html";else if(p.endsWith("/"))p+="index.html";else if(!p.split("/").pop().includes("."))p+=".html";let x=await asset(e,r,"/docs"+p);if(x.status!==404)return x;const f=await asset(e,r,"/docs/404.html");return new Response(f.body,{status:404,headers:f.headers})}
async function forksense(e,r,u){let p=u.pathname;if(p==="/")p="/forksense/index.html";else if(p.endsWith("/"))p="/forksense"+p+"index.html";else if(!p.split("/").pop().includes("."))p="/forksense"+p+".html";else p="/forksense"+p;let x=await asset(e,r,p);if(x.status!==404)return x;const f=await asset(e,r,"/forksense/index.html");return new Response(f.body,{status:404,headers:f.headers})}
async function spec(e,r,u){let p=u.pathname;if(p==="/")p="/spec/index.html";else if(p.startsWith("/spec/")){if(p.endsWith("/"))p+="index.html";else if(!p.split("/").pop().includes("."))p+=".html"}else if(p.endsWith("/"))p="/spec"+p+"index.html";else if(!p.split("/").pop().includes("."))p="/spec"+p+".html";else p="/spec"+p;let x=await asset(e,r,p);if(x.status!==404)return x;const f=await asset(e,r,"/spec/index.html");return new Response(f.body,{status:404,headers:f.headers})}
async function trackedCorpus(e,r,kind="hitchhikers-upstream"){
  const evidence=kind==="evidence-audit";
  const filename=evidence?"evidence-audit.json":"hitchhikers-upstream.json";
  const expected=evidence?"torsionfield-evidence-audit/1":"torsionfield-source-watch/1";
  const source="https://raw.githubusercontent.com/FreesoSaiFared/torsionfield/main/public/research/"+filename;
  try{
    const upstream=await fetch(source,{cf:{cacheTtl:180,cacheEverything:true}});
    if(!upstream.ok)throw new Error("source HTTP "+upstream.status);
    const d=await upstream.json();
    if(d?.schema!==expected||!/^[a-f0-9]{40}$/.test(d.upstreamSha||""))throw new Error("invalid upstream metadata");
    if(evidence?(!Array.isArray(d.claims)||!Array.isArray(d.interpretationChecks)):(d.upstreamRepo!=="steveash/hitchhikers-guide-to-ai-native-engineering"||!Array.isArray(d.events)))throw new Error("unexpected evidence schema");
    return wrap(new Response(JSON.stringify(d),{headers:{"content-type":"application/json; charset=utf-8","cache-control":"public, max-age=180"}}));
  }catch(err){
    console.error("tracked corpus unavailable:",err);
    const fallback=await asset(e,r,"/research/"+filename);
    if(fallback.status===200)return fallback;
    return json({ok:false,error:"UPSTREAM_WATCH_UNAVAILABLE"},503);
  }
}
async function editorialManifest(e,r,name){
  const file=name==="articles"?"research-feed.json":"research/editorial.json";
  const schema="torsionfield-editorial/1";
  try{
    const origin="https://raw.githubusercontent.com/FreesoSaiFared/torsionfield/main/public/"+file;
    const response=await fetch(origin,{cf:{cacheTtl:300,cacheEverything:true}});
    if(!response.ok)throw new Error("editorial source HTTP "+response.status);
    const data=await response.json();
    if(name==="articles"){
      if(!Array.isArray(data.items)||!Array.isArray(data.sources))throw new Error("invalid articles");
    }else if(data?.schema!==schema||typeof data.entries!=="object")throw new Error("invalid editorial manifest");
    return wrap(new Response(JSON.stringify(data),{headers:{"content-type":"application/json; charset=utf-8","cache-control":"public,max-age=300"}}));
  }catch(error){
    console.error("Editorial manifest source error:",error);
    const fallback=await asset(e,r,"/"+file);
    if(fallback.status===200)return fallback;
    return json({error:"EDITORIAL_SOURCE_UNAVAILABLE"},503);
  }
}
export default{async fetch(r,e){const u=new URL(r.url),host=u.hostname.toLowerCase();
if(r.method==="GET"&&(host==="torsionfield.de"||host.endsWith(".workers.dev"))){
 if(u.pathname==="/api/research/articles")return editorialManifest(e,r,"articles");
 if(u.pathname==="/api/research/editorial")return editorialManifest(e,r,"editorial");
}
if(u.pathname==="/api/research/evidence"&&r.method==="GET"&&(host==="torsionfield.de"||host.endsWith(".workers.dev")))return trackedCorpus(e,r,"evidence-audit");
if(u.pathname==="/api/research/hitchhikers"&&r.method==="GET"&&(host==="torsionfield.de"||host.endsWith(".workers.dev")))return trackedCorpus(e,r);
if(host==="www.torsionfield.de")return Response.redirect(`https://torsionfield.de${u.pathname}${u.search}`,308);
if(u.pathname==="/api/status")return json({product:"Torsionfield Runtime",siteRevision:"2026.08.03-spec-3.2",specVersion:"3.2",networkRegistration:"alpha",documentation:"online",participantEdge:"bounded-pilot"});
if(u.pathname==="/api/site-manifest")return json({protocol:"torsionfield-site/1",domains:{product:"https://torsionfield.de",docs:"https://docs.torsionfield.de",community:"https://transductive.org",science:"https://transductive.science",art:"https://transductive.art"},localFirst:true,specification:"https://spec.torsionfield.de/",participantEdge:{status:"bounded-pilot",referenceProvider:"cloudflare-oauth-cell/1"}});
if(u.pathname==="/api/network/register"&&r.method==="POST"){let b;try{b=await r.json()}catch{return json({ok:false,error:"INVALID_JSON"},400)}if(b.website)return json({ok:true});const em=String(b.email||"").trim().toLowerCase(),n=String(b.displayName||"").trim(),intent=String(b.nodeIntent||"explore").slice(0,40),ints=Array.isArray(b.interests)?b.interests.slice(0,12).map(String):[];if(!email(em)||n.length<2||n.length>80||b.accepted!==true)return json({ok:false,error:"VALIDATION_FAILED"},400);const now=new Date().toISOString();try{await e.NETWORK_DB.prepare(`INSERT INTO network_registrations(id,email,display_name,interests,node_intent,source_host,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'pending',?,?) ON CONFLICT(email) DO UPDATE SET display_name=excluded.display_name,interests=excluded.interests,node_intent=excluded.node_intent,updated_at=excluded.updated_at`).bind(crypto.randomUUID(),em,n,JSON.stringify(ints),intent,host,now,now).run();return json({ok:true,status:"pending"},201)}catch(err){console.error(err);return json({ok:false,error:"REGISTRATION_UNAVAILABLE"},503)}}
if(host==="forksense.torsionfield.de")return forksense(e,r,u);if(host==="spec.torsionfield.de")return spec(e,r,u);if(host==="docs.torsionfield.de")return docs(e,r,u);if(u.pathname==="/docs"||u.pathname.startsWith("/docs/"))return Response.redirect(`https://docs.torsionfield.de${u.pathname.replace(/^\/docs/,"")||"/"}`,308);if(host==="torsionfield.de"||host.endsWith(".workers.dev")){let p=u.pathname;if(p==="/")p="/index.html";else if(p.endsWith("/"))p+="index.html";let direct=await asset(e,r,p);if(direct.status!==404){if(p.startsWith('/cinematic-matter/'))return wrap(direct,{'Content-Security-Policy':H['Content-Security-Policy'].replace("script-src 'self'","script-src 'self' 'wasm-unsafe-eval'")});return direct;}}let x=await e.ASSETS.fetch(r);if(x.status!==404)return wrap(x);const f=await e.ASSETS.fetch(new Request(new URL("/404.html",r.url),r));const h=wrap(f).headers;return new Response(f.body,{status:404,headers:h})}};
