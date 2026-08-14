#!/usr/bin/env node
'use strict';

const input = await new Promise((resolve, reject) => {
  let data = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => { data += chunk; });
  process.stdin.on('end', () => resolve(data));
  process.stdin.on('error', reject);
});
const request = JSON.parse(input || '{}');
const op = String(request.op || 'inventory');
const port = Number(request.port || 9222);
const payload = request.payload && typeof request.payload === 'object' ? request.payload : {};
const endpoint = `http://127.0.0.1:${port}`;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

class CDP {
  constructor(url, timeoutMs = 15000) {
    this.url = url;
    this.timeoutMs = timeoutMs;
    this.nextId = 0;
    this.pending = new Map();
  }
  async open() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`CDP open timeout: ${this.url}`)), 5000);
      this.ws.onopen = () => { clearTimeout(timer); resolve(); };
      this.ws.onerror = () => { clearTimeout(timer); reject(new Error(`CDP websocket error: ${this.url}`)); };
    });
    this.ws.onmessage = event => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) return;
      const pending = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(JSON.stringify(message.error)));
      else pending.resolve(message.result);
    };
  }
  call(method, params = {}) {
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (this.pending.delete(id)) reject(new Error(`CDP timeout: ${method}`));
      }, this.timeoutMs);
    });
  }
  close() { try { this.ws?.close(); } catch (_) {} }
}

async function fetchJson(url, timeoutMs = 4000) {
  const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
  return response.json();
}
async function listTargets() { return fetchJson(`${endpoint}/json/list`); }
async function browserClient() {
  const version = await fetchJson(`${endpoint}/json/version`);
  const client = new CDP(version.webSocketDebuggerUrl);
  await client.open();
  return { client, version };
}
async function targetById(targetId) {
  const target = (await listTargets()).find(item => item.id === String(targetId));
  if (!target?.webSocketDebuggerUrl) throw new Error(`target not found: ${targetId}`);
  return target;
}
async function withTarget(targetId, fn) {
  const target = await targetById(targetId);
  const client = new CDP(target.webSocketDebuggerUrl, Number(payload.timeout_ms || 20000));
  await client.open();
  try { return await fn(client, target); } finally { client.close(); }
}

const PAGE_STATE_EXPR = String.raw`(() => {
  const norm = v => String(v == null ? '' : v).replace(/\r\n?/g,'\n').trim();
  const hash = v => { let h = 2166136261; for (const ch of String(v || '')) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0).toString(16).padStart(8,'0'); };
  const visible = n => { if (!n) return false; const s=getComputedStyle(n), r=n.getBoundingClientRect(); return s.display!=='none' && s.visibility!=='hidden' && r.width>0 && r.height>0; };
  const composer = ['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']
    .flatMap(s => [...document.querySelectorAll(s)]).filter(visible).at(-1) || null;
  const composerText = composer ? (typeof composer.value === 'string' ? composer.value : (composer.innerText || composer.textContent || '')) : '';
  const turns = [...document.querySelectorAll('[data-message-author-role]')].slice(-12).map((n,i) => {
    const role=n.getAttribute('data-message-author-role')||'';
    const content=role==='user' ? (n.querySelector('[data-testid="collapsible-user-message-content"]')||n) : n;
    const text=norm(content.innerText||content.textContent||'').slice(0,12000);
    return {index:i,role,text,hash:hash(text)};
  });
  const assistants=turns.filter(x=>x.role==='assistant'), users=turns.filter(x=>x.role==='user');
  const latestAssistant=assistants.at(-1)||null, latestUser=users.at(-1)||null;
  const stop=Boolean(document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]'));
  const path=location.pathname;
  const conv=(path.match(/\/c\/([^/?#]+)/)||[])[1]||'';
  const project=(path.match(/\/g\/(g-p-[^/]+)/)||[])[1]||'';
  const branchControls=[...document.querySelectorAll('button,[role="button"]')].map(n=>n.getAttribute('aria-label')||'').filter(v=>/branch|previous|next|response/i.test(v)).slice(0,40);
  const root=document.documentElement;
  const lastOp=root?.dataset?.tfAutogenicLastOp||'';
  const lastOpStatus=root?.dataset?.tfAutogenicLastOpStatus||'';
  const loopError=root?.dataset?.tfAutogenicLoopError||'';
  const pendingAction=Boolean(latestAssistant && /\[\[TF_ACTION\/1/.test(latestAssistant.text) && !document.querySelector('[data-tf-autogenic-executed="1"]'));
  const status = stop ? 'streaming' : lastOpStatus && lastOpStatus!=='ok' ? 'automation-error' : composerText.trim() ? 'draft' : 'idle';
  return {
    href:location.href,title:document.title,readyState:document.readyState,visibilityState:document.visibilityState,
    hidden:document.hidden,scrollY:window.scrollY,scrollHeight:document.documentElement.scrollHeight,
    conversationId:conv,projectId:project,composerText:composerText.slice(0,65536),streaming:stop,status,
    turnCount:document.querySelectorAll('[data-message-author-role]').length,turns,latestUser,latestAssistant,
    branchControls,branchSignature:[conv,latestUser?.hash||'',latestAssistant?.hash||'',branchControls.join('|')].join(':'),
    autogenic:{state:root?.dataset?.tfAutogenic||'',version:root?.dataset?.tfAutogenicVersion||'',bridge:root?.dataset?.tfExtensionBridge||'',residentElevated:root?.dataset?.tfResidentElevated||'',lastOp,lastOpStatus,loopError},
    pendingAction, capturedAt:Date.now()
  };
})()`;

async function evalValue(client, expression, awaitPromise = false) {
  await client.call('Runtime.enable');
  const result = await client.call('Runtime.evaluate', { expression, awaitPromise, returnByValue: true, userGesture: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'Runtime exception');
  return result.result?.value;
}

async function inventory() {
  const version = await fetchJson(`${endpoint}/json/version`);
  const targets = await listTargets();
  const pages = [];
  for (const target of targets.filter(t => t.type === 'page')) {
    const base = { id:target.id, type:target.type, title:target.title, url:target.url, faviconUrl:target.faviconUrl||null };
    if (!/^https:\/\/(chatgpt\.com|chat\.openai\.com)\//.test(String(target.url||''))) {
      pages.push({ ...base, chatgpt:false });
      continue;
    }
    try {
      const state = await withTarget(target.id, client => evalValue(client, PAGE_STATE_EXPR));
      pages.push({ ...base, chatgpt:true, state });
    } catch (error) {
      pages.push({ ...base, chatgpt:true, error:String(error?.message||error) });
    }
  }
  return { browser:version.Browser||null, webSocketDebuggerUrl:version.webSocketDebuggerUrl||null, port, pages };
}

async function setLifecycle(targetId, state) {
  return withTarget(targetId, async (client,target) => {
    await client.call('Page.enable');
    await client.call('Page.setWebLifecycleState',{state});
    return {targetId:target.id,state};
  });
}

async function stopGeneration(targetId) {
  return withTarget(targetId, async (client,target) => {
    const before = await evalValue(client, `Boolean(document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]'))`);
    if (before) await evalValue(client, `(()=>{const b=document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]'); if(b){b.click();return true;} return false;})()`);
    const deadline=Date.now()+Number(payload.timeout_ms||20000);
    let streaming=before;
    while (streaming && Date.now()<deadline) {
      await sleep(200);
      streaming=await evalValue(client, `Boolean(document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]'))`);
    }
    return {targetId:target.id,wasStreaming:Boolean(before),settled:!streaming};
  });
}

function composerScript(text, submit) {
  return `(()=>{const intended=${JSON.stringify(String(text||''))}; const visible=n=>{if(!n)return false;const s=getComputedStyle(n),r=n.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;}; const sels=['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']; let node=null; for(const s of sels){const ns=[...document.querySelectorAll(s)].filter(visible); if(ns.length){node=ns.at(-1);break;}} if(!node) throw new Error('composer-missing'); const current=typeof node.value==='string'?node.value:(node.innerText||node.textContent||''); if(current.trim() && current!==intended) throw new Error('composer-not-empty'); node.focus(); if(typeof node.value==='string'){const proto=Object.getPrototypeOf(node),d=proto&&Object.getOwnPropertyDescriptor(proto,'value'); if(d?.set)d.set.call(node,intended); else node.value=intended; node.dispatchEvent(new Event('input',{bubbles:true}));} else {let ok=false; try{ok=Boolean(document.execCommand&&document.execCommand('insertText',false,intended));}catch(_){} if(!ok){node.textContent=intended;node.dispatchEvent(new Event('input',{bubbles:true}));}} if(!${submit?'true':'false'}) return {inserted:true}; const form=node.closest('form')||document; const buttons=['button[data-testid="send-button"]','button[aria-label="Send prompt"]','button[aria-label="Send message"]','button[aria-label^="Send"]']; let b=null; for(const s of buttons){const ns=[...form.querySelectorAll(s)].filter(visible);if(ns.length){b=ns.at(-1);break;}} if(!b||b.disabled) throw new Error('send-button-not-ready'); b.click(); return {inserted:true,submitted:true};})()`;
}

async function restoreDraft(targetId, text, scrollY) {
  return withTarget(targetId, async (client,target) => {
    const result = await evalValue(client, composerScript(text,false));
    if (Number.isFinite(Number(scrollY))) await evalValue(client, `window.scrollTo(0,${Number(scrollY)}); true`);
    return {targetId:target.id,...result};
  });
}

async function requestHandoff(targetId, prompt) {
  return withTarget(targetId, async (client,target) => {
    const baseline=await evalValue(client, `document.querySelectorAll('[data-message-author-role="assistant"]').length`);
    await evalValue(client, composerScript(prompt,true));
    const deadline=Date.now()+Number(payload.timeout_ms||120000);
    let last='', stableSince=0;
    while(Date.now()<deadline){
      await sleep(500);
      const state=await evalValue(client,PAGE_STATE_EXPR);
      const count=await evalValue(client,`document.querySelectorAll('[data-message-author-role="assistant"]').length`);
      const text=state?.latestAssistant?.text||'';
      if(count>baseline && !state.streaming && text){
        if(text===last){ if(!stableSince)stableSince=Date.now(); if(Date.now()-stableSince>1200)return {targetId:target.id,handoff:text,state}; }
        else {last=text;stableSince=Date.now();}
      }
    }
    throw new Error('handoff-timeout');
  });
}

async function openUrl(url, background=false) {
  const {client}=await browserClient();
  try { const r=await client.call('Target.createTarget',{url:String(url),background:Boolean(background)}); return {targetId:r.targetId,url:String(url)}; }
  finally { client.close(); }
}

async function closeTarget(targetId) {
  const {client}=await browserClient();
  try { const r=await client.call('Target.closeTarget',{targetId:String(targetId)}); return {targetId:String(targetId),closed:Boolean(r.success)}; }
  finally { client.close(); }
}

async function activateTarget(targetId) {
  const {client}=await browserClient();
  try { await client.call('Target.activateTarget',{targetId:String(targetId)}); return {targetId:String(targetId),activated:true}; }
  finally { client.close(); }
}

async function main(){
  if(op==='inventory') return inventory();
  if(op==='freeze') return setLifecycle(payload.target_id,'frozen');
  if(op==='unfreeze') return setLifecycle(payload.target_id,'active');
  if(op==='stop') return stopGeneration(payload.target_id);
  if(op==='restore_draft') return restoreDraft(payload.target_id,payload.text||'',payload.scroll_y);
  if(op==='handoff') return requestHandoff(payload.target_id,payload.prompt||'');
  if(op==='open') return openUrl(payload.url,payload.background);
  if(op==='close') return closeTarget(payload.target_id);
  if(op==='activate') return activateTarget(payload.target_id);
  throw new Error(`unsupported reboot CDP op: ${op}`);
}

try { console.log(JSON.stringify({ok:true,result:await main()})); }
catch(error){ console.error(JSON.stringify({ok:false,error:String(error?.stack||error)})); process.exit(1); }
