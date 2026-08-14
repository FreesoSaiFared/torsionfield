#!/usr/bin/env node
'use strict';

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i++) {
    if (!argv[i].startsWith('--')) continue;
    const key = argv[i].slice(2);
    out[key] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  }
  return out;
}

const args = parseArgs(process.argv);
const endpoint = `http://127.0.0.1:${Number(args.port || 9448)}`;
const expectedVersion = String(args.version || '0.2.2');
const timeoutMs = Number(args.timeout || 125000);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

class CDP {
  constructor(url, timeout = 15000) {
    this.url = url;
    this.timeout = timeout;
    this.nextId = 0;
    this.pending = new Map();
  }
  async open() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`open timeout: ${this.url}`)), 5000);
      this.ws.onopen = () => { clearTimeout(timer); resolve(); };
      this.ws.onerror = () => { clearTimeout(timer); reject(new Error(`websocket error: ${this.url}`)); };
    });
    this.ws.onmessage = (event) => {
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
      }, this.timeout);
    });
  }
  close() {
    try { this.ws?.close(); } catch (_) {}
  }
}

async function json(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
  return response.json();
}

async function waitTarget(id) {
  for (let i = 0; i < 100; i++) {
    const target = (await json(`${endpoint}/json/list`)).find((item) => item.id === id);
    if (target?.webSocketDebuggerUrl) return target;
    await sleep(100);
  }
  throw new Error(`target did not appear: ${id}`);
}

function correlation(value) {
  return String(value || '').replace(/\r\n?/g, '\n').replace(/\s+/g, ' ').trim();
}

async function main() {
  const version = await json(`${endpoint}/json/version`);
  const browser = new CDP(version.webSocketDebuggerUrl);
  await browser.open();
  const made = await browser.call('Target.createTarget', { url: 'https://chatgpt.com/' });
  const target = await waitTarget(made.targetId);
  const page = new CDP(target.webSocketDebuggerUrl);
  await page.open();
  await page.call('Runtime.enable');

  let ready = null;
  const readyDeadline = Date.now() + 45000;
  while (Date.now() < readyDeadline) {
    try {
      const result = await page.call('Runtime.evaluate', {
        expression: `({composer:Boolean(document.querySelector('#prompt-textarea[contenteditable="true"]')),autogenic:document.documentElement?.dataset?.tfAutogenic||null,version:document.documentElement?.dataset?.tfAutogenicVersion||null,bridge:document.documentElement?.dataset?.tfExtensionBridge||null,residentElevated:document.documentElement?.dataset?.tfResidentElevated||null,residentError:document.documentElement?.dataset?.tfResidentError||null})`,
        returnByValue: true,
      });
      ready = result.result?.value;
      if (ready?.composer && ready.autogenic === 'ready' && ready.version === expectedVersion && ready.residentElevated === 'true') break;
    } catch (_) {}
    await sleep(150);
  }
  if (!(ready?.composer && ready.autogenic === 'ready' && ready.version === expectedVersion && ready.residentElevated === 'true')) {
    throw new Error(`fresh ChatGPT page did not become autogenic-ready: ${JSON.stringify(ready)}`);
  }

  const nonce = `TF_LOOP_${Date.now().toString(36).toUpperCase()}`;
  const marker = `${nonce}_MACHINE_OK`;
  const prompt = [
    'TORSIONFIELD AUTOGENIC ACCEPTANCE TEST.',
    'Respond with exactly the following TF_ACTION block and nothing else. Preserve JSON and marker exactly.',
    '[[TF_ACTION/1',
    JSON.stringify({ id: nonce, op: 'exec', args: { shell: `echo ${marker}` } }),
    '[[/TF_ACTION]]',
  ].join('\n');

  const seed = await page.call('Runtime.evaluate', {
    expression: `(()=>{const intended=${JSON.stringify(prompt)};const norm=x=>String(x||'').replace(/\\r\\n?/g,'\\n').replace(/\\s+/g,' ').trim();const n=document.querySelector('#prompt-textarea[contenteditable="true"]');if(!n)return {ok:false,error:'composer-missing'};if(norm(n.innerText||n.textContent))return {ok:false,error:'composer-not-empty'};n.focus();n.textContent=intended;try{n.dispatchEvent(new InputEvent('input',{bubbles:true,composed:true,inputType:'insertText',data:intended}));}catch(_){n.dispatchEvent(new Event('input',{bubbles:true}));}return {ok:norm(n.innerText||n.textContent)===norm(intended)};})()`,
    returnByValue: true,
  });
  if (!seed.result?.value?.ok) throw new Error(`seed insertion failed: ${JSON.stringify(seed.result?.value)}`);

  let sent = false;
  for (let i = 0; i < 80; i++) {
    const result = await page.call('Runtime.evaluate', {
      expression: `(()=>{const n=document.querySelector('#prompt-textarea[contenteditable="true"]');const form=n?.closest('form')||document;const b=[...form.querySelectorAll('button[data-testid="send-button"],button[aria-label="Send prompt"],button[aria-label="Send message"],button[aria-label^="Send"]')].find(x=>{const s=getComputedStyle(x),r=x.getBoundingClientRect();return !x.disabled&&s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0});if(!b)return false;b.click();return true;})()`,
      returnByValue: true,
    });
    if (result.result?.value) { sent = true; break; }
    await sleep(50);
  }
  if (!sent) throw new Error('seed send button never became ready');

  let observed = null;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const result = await page.call('Runtime.evaluate', {
        expression: `(()=>{const users=[...document.querySelectorAll('[data-message-author-role="user"]')].map(n=>(n.innerText||n.textContent||'').trim());const assistants=[...document.querySelectorAll('[data-message-author-role="assistant"]')].map(n=>({text:(n.innerText||n.textContent||'').trim(),executed:n.dataset.tfAutogenicExecuted||null,intercepted:n.dataset.tfAutogenicIntercepted||null}));const results=users.filter(x=>x.startsWith('TORSIONFIELD MACHINE RESULT /1'));return {url:location.href,title:document.title,users,assistants,results,markerSeen:results.some(x=>x.includes(${JSON.stringify(marker)})),executed:assistants.filter(x=>x.executed==='1').length,actionAssistants:assistants.filter(x=>x.text.includes(${JSON.stringify(nonce)})).length,lastOp:document.documentElement.dataset.tfAutogenicLastOp||null,lastStatus:document.documentElement.dataset.tfAutogenicLastOpStatus||null,loopError:document.documentElement.dataset.tfAutogenicLoopError||null,composer:(document.querySelector('#prompt-textarea[contenteditable="true"]')?.innerText||'').trim()};})()`,
        returnByValue: true,
      });
      observed = result.result?.value;
      if (observed?.markerSeen && observed.results.length === 1 && observed.executed === 1) break;
    } catch (_) {}
    await sleep(250);
  }

  const result = {
    ok: Boolean(observed?.markerSeen && observed?.results?.length === 1 && observed?.executed === 1 && observed?.lastStatus === 'ok'),
    browser: version.Browser,
    expectedVersion,
    nonce,
    marker,
    url: observed?.url || null,
    title: observed?.title || null,
    userTurns: observed?.users?.length || 0,
    assistantTurns: observed?.assistants?.length || 0,
    resultTurns: observed?.results?.length || 0,
    executedCount: observed?.executed || 0,
    actionAssistantCount: observed?.actionAssistants || 0,
    markerSeen: Boolean(observed?.markerSeen),
    lastOp: observed?.lastOp || null,
    lastStatus: observed?.lastStatus || null,
    loopError: observed?.loopError || null,
    composerEmpty: !observed?.composer,
    actionPreview: observed?.assistants?.find((item) => item.text.includes(nonce))?.text?.slice(0, 1200) || null,
    resultPreview: observed?.results?.[0]?.slice(0, 1800) || null,
  };
  console.log(JSON.stringify(result));
  page.close();
  browser.close();
  if (!result.ok) process.exitCode = 2;
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: String(error?.stack || error) }));
  process.exit(1);
});
