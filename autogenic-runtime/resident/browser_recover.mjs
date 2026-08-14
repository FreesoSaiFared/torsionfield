#!/usr/bin/env node
'use strict';

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i++) {
    const key = argv[i];
    if (!key.startsWith('--')) continue;
    out[key.slice(2)] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  }
  return out;
}

const args = parseArgs(process.argv);
const port = Number(args.port || 9222);
const chatUrl = String(args['chat-url'] || 'https://chatgpt.com/');
const userScriptUrl = String(args['userscript-url'] || 'http://127.0.0.1:17373/userscripts/torsionfield-autogenic.user.js');
const endpoint = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

class CDP {
  constructor(url, timeoutMs = 10000) {
    this.url = url;
    this.timeoutMs = timeoutMs;
    this.nextId = 0;
    this.pending = new Map();
    this.ws = null;
  }
  async open() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`CDP open timeout: ${this.url}`)), 5000);
      this.ws.onopen = () => { clearTimeout(timer); resolve(); };
      this.ws.onerror = () => { clearTimeout(timer); reject(new Error(`CDP websocket error: ${this.url}`)); };
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
      }, this.timeoutMs);
    });
  }
  close() {
    try { this.ws?.close(); } catch (_) {}
  }
}

async function fetchJson(url, timeoutMs = 3000) {
  const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
  return response.json();
}

async function targets() {
  return fetchJson(`${endpoint}/json/list`);
}

async function targetEval(target, expression, awaitPromise = false) {
  const client = new CDP(target.webSocketDebuggerUrl);
  await client.open();
  await client.call('Runtime.enable');
  const result = await client.call('Runtime.evaluate', { expression, awaitPromise, returnByValue: true });
  client.close();
  if (result.exceptionDetails) throw new Error(`Runtime exception: ${JSON.stringify(result.exceptionDetails)}`);
  return result.result?.value;
}

async function waitForTarget(predicate, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const list = await targets();
    const target = list.find(predicate);
    if (target?.webSocketDebuggerUrl) return target;
    await sleep(100);
  }
  return null;
}

async function browserClient() {
  const version = await fetchJson(`${endpoint}/json/version`);
  const client = new CDP(version.webSocketDebuggerUrl);
  await client.open();
  return { client, version };
}

async function createTarget(browser, url) {
  const created = await browser.call('Target.createTarget', { url });
  const target = await waitForTarget((item) => item.id === created.targetId, 10000);
  if (!target) throw new Error(`created target did not appear: ${url}`);
  return target;
}

async function closeTarget(browser, target) {
  if (!target?.id) return;
  try { await browser.call('Target.closeTarget', { targetId: target.id }); } catch (_) {}
}

async function servedUserScriptVersion() {
  const response = await fetch(userScriptUrl, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`userscript endpoint HTTP ${response.status}`);
  const source = await response.text();
  const match = source.match(/^\/\/\s*@version\s+([^\r\n]+)/m);
  return { version: match?.[1]?.trim() || '', bytes: new TextEncoder().encode(source).length };
}

async function openInstaller(browser) {
  const original = await createTarget(browser, userScriptUrl);
  const deadline = Date.now() + 12000;
  while (Date.now() < deadline) {
    const list = await targets();
    const current = list.find((item) => item.id === original.id);
    if (current?.url?.includes('/src/install.html?url=') && current.url.includes(encodeURI(userScriptUrl))) return current;
    if (current?.url?.includes('/src/install.html?url=')) return current;
    await sleep(100);
  }
  throw new Error('ScriptCat did not intercept the resident .user.js URL');
}

function extensionIdFromInstaller(installer) {
  const match = String(installer.url || '').match(/^chrome-extension:\/\/([^/]+)\/src\/install\.html/);
  if (!match) throw new Error(`cannot derive ScriptCat extension id from ${installer.url}`);
  return match[1];
}

async function withExtensionsPage(browser, fn) {
  const page = await createTarget(browser, 'chrome://extensions/');
  const client = new CDP(page.webSocketDebuggerUrl);
  await client.open();
  await client.call('Runtime.enable');
  const deadline = Date.now() + 10000;
  let ready = false;
  while (Date.now() < deadline) {
    const probe = await client.call('Runtime.evaluate', { expression: 'Boolean(globalThis.chrome && chrome.developerPrivate)', returnByValue: true });
    if (probe.result?.value) { ready = true; break; }
    await sleep(100);
  }
  if (!ready) {
    client.close();
    await closeTarget(browser, page);
    throw new Error('chrome.developerPrivate unavailable');
  }
  try {
    return await fn(client);
  } finally {
    client.close();
    await closeTarget(browser, page);
  }
}

async function extensionInfo(browser, id) {
  return withExtensionsPage(browser, async (page) => {
    const expression = `(async()=>{const id=${JSON.stringify(id)};return await new Promise((resolve,reject)=>chrome.developerPrivate.getExtensionInfo(id,(info)=>{const e=chrome.runtime.lastError;if(e)reject(new Error(e.message));else resolve({id:info.id,name:info.name,state:info.state,userScriptsAccess:info.userScriptsAccess||null,disableReasons:info.disableReasons||null});}));})()`;
    const result = await page.call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result?.value;
  });
}

async function enableUserScripts(browser, id) {
  return withExtensionsPage(browser, async (page) => {
    const expression = `(async()=>{const id=${JSON.stringify(id)};await chrome.developerPrivate.updateExtensionConfiguration({extensionId:id,userScriptsAccess:true});return await new Promise((resolve,reject)=>chrome.developerPrivate.getExtensionInfo(id,(info)=>{const e=chrome.runtime.lastError;if(e)reject(new Error(e.message));else resolve({id:info.id,name:info.name,state:info.state,userScriptsAccess:info.userScriptsAccess||null});}));})()`;
    const result = await page.call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result?.value;
  });
}

async function waitForScriptCatWorker(scriptCatId, timeoutMs = 12000) {
  return waitForTarget((item) => item.type === 'service_worker' && item.url.includes(`chrome-extension://${scriptCatId}/`), timeoutMs);
}

async function scriptCatRegistry(worker) {
  return targetEval(worker, `(async()=>({name:chrome.runtime.getManifest().name,version:chrome.runtime.getManifest().version,userScriptsAvailable:typeof chrome.userScripts?.getScripts==='function',scripts:typeof chrome.userScripts?.getScripts==='function'?(await chrome.userScripts.getScripts()).map(s=>({id:s.id,matches:s.matches||[],runAt:s.runAt||null,world:s.world||null})):[]}))()`, true);
}

async function installerSummary(installer, expectedVersion) {
  return targetEval(installer, `(()=>{const text=document.body?.innerText||'';const actions=[...document.querySelectorAll('button')].map(b=>({text:(b.innerText||b.textContent||'').trim(),disabled:b.disabled})).filter(x=>x.text);return {ready:document.readyState,nameSeen:text.includes('Torsionfield Autogenic Runtime Bridge'),expectedVersionSeen:text.includes(${JSON.stringify(`v${expectedVersion}`)}),containsCredentialPlaceholder:text.includes('__TF_RESIDENT_TOKEN__'),containsGMXHR:text.includes('GM_xmlhttpRequest'),actions};})()`);
}

async function clickInstallerAction(installer, expectedVersion) {
  const summary = await installerSummary(installer, expectedVersion);
  if (!summary.nameSeen || !summary.expectedVersionSeen || summary.containsCredentialPlaceholder || summary.containsGMXHR) {
    throw new Error(`installer validation failed: ${JSON.stringify(summary)}`);
  }
  const action = summary.actions.find((item) => /^(Install Script|Update Script|Reinstall Script)$/i.test(item.text) && !item.disabled);
  if (!action) return { clicked: false, summary };
  const clicked = await targetEval(installer, `(()=>{const b=[...document.querySelectorAll('button')].find(x=>/^(Install Script|Update Script|Reinstall Script)$/i.test((x.innerText||x.textContent||'').trim())&&!x.disabled);if(!b)return false;b.click();return true;})()`);
  return { clicked: Boolean(clicked), action: action.text, summary };
}

async function findOrCreateChat(browser) {
  let list = await targets();
  let page = list.find((item) => item.type === 'page' && item.url === chatUrl);
  if (page) return page;
  return createTarget(browser, chatUrl);
}

async function chatHandshake(page) {
  return targetEval(page, `({url:location.href,title:document.title,ready:document.readyState,tfAutogenic:document.documentElement?.dataset?.tfAutogenic||null,tfAutogenicVersion:document.documentElement?.dataset?.tfAutogenicVersion||null,tfExtensionBridge:document.documentElement?.dataset?.tfExtensionBridge||null,tfResidentPid:document.documentElement?.dataset?.tfResidentPid||null,tfResidentElevated:document.documentElement?.dataset?.tfResidentElevated||null,tfResidentError:document.documentElement?.dataset?.tfResidentError||null,hasGlobal:typeof globalThis.Torsionfield!=='undefined'})`);
}

async function reloadAndWait(page, expectedVersion, timeoutMs = 15000) {
  const client = new CDP(page.webSocketDebuggerUrl);
  await client.open();
  await client.call('Page.enable');
  await client.call('Page.reload', { ignoreCache: true });
  const deadline = Date.now() + timeoutMs;
  let value = null;
  while (Date.now() < deadline) {
    await sleep(150);
    try {
      const result = await client.call('Runtime.evaluate', { expression: `({url:location.href,title:document.title,ready:document.readyState,tfAutogenic:document.documentElement?.dataset?.tfAutogenic||null,tfAutogenicVersion:document.documentElement?.dataset?.tfAutogenicVersion||null,tfExtensionBridge:document.documentElement?.dataset?.tfExtensionBridge||null,tfResidentPid:document.documentElement?.dataset?.tfResidentPid||null,tfResidentElevated:document.documentElement?.dataset?.tfResidentElevated||null,tfResidentError:document.documentElement?.dataset?.tfResidentError||null,hasGlobal:typeof globalThis.Torsionfield!=='undefined'})`, returnByValue: true });
      value = result.result?.value;
      if (value?.tfAutogenic === 'ready' && value?.tfAutogenicVersion === expectedVersion && value?.tfResidentElevated === 'true') break;
    } catch (_) {}
  }
  client.close();
  return value;
}

async function main() {
  const served = await servedUserScriptVersion();
  if (!served.version) throw new Error('resident userscript has no @version');
  const { client: browser, version: browserVersion } = await browserClient();
  let installer = await openInstaller(browser);
  const scriptCatId = extensionIdFromInstaller(installer);
  let scInfo = await extensionInfo(browser, scriptCatId);
  if (!scInfo.userScriptsAccess?.isEnabled) {
    scInfo = await enableUserScripts(browser, scriptCatId);
    await closeTarget(browser, installer);
    installer = await openInstaller(browser);
  }

  let worker = await waitForScriptCatWorker(scriptCatId, 12000);
  if (!worker) throw new Error('ScriptCat service worker did not wake');
  let registry = await scriptCatRegistry(worker);

  let chat = await findOrCreateChat(browser);
  let handshake = await reloadAndWait(chat, served.version, 10000);
  let installerAction = { clicked: false };

  if (!(handshake?.tfAutogenic === 'ready' && handshake?.tfAutogenicVersion === served.version && handshake?.tfResidentElevated === 'true')) {
    installerAction = await clickInstallerAction(installer, served.version);
    if (!installerAction.clicked) throw new Error(`autogenic script unavailable after reload and installer had no applicable action: ${JSON.stringify(handshake)}`);
    await sleep(1800);
    worker = await waitForScriptCatWorker(scriptCatId, 12000);
    if (!worker) throw new Error('ScriptCat worker absent after script install/update');
    registry = await scriptCatRegistry(worker);
    chat = await findOrCreateChat(browser);
    handshake = await reloadAndWait(chat, served.version, 15000);
  }

  for (const target of (await targets()).filter((item) => item.type === 'page' && item.url.includes('/src/install.html?url=') && item.url.includes('torsionfield-autogenic.user.js'))) {
    await closeTarget(browser, target);
  }
  browser.close();

  const ok = handshake?.tfAutogenic === 'ready' && handshake?.tfAutogenicVersion === served.version && handshake?.tfExtensionBridge === 'ready' && handshake?.tfResidentElevated === 'true';
  const result = {
    ok,
    browser: browserVersion.Browser,
    expectedUserScriptVersion: served.version,
    scriptCat: { id: scriptCatId, name: scInfo.name, state: scInfo.state, userScriptsAccess: scInfo.userScriptsAccess, registeredCount: registry.scripts?.length || 0 },
    installerAction,
    chat: handshake,
  };
  console.log(JSON.stringify(result));
  if (!ok) process.exitCode = 2;
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: String(error?.stack || error) }));
  process.exit(1);
});
