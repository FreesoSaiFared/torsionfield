#!/usr/bin/env node
'use strict';

const input = await new Promise((resolve, reject) => {
  let data = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => { data += chunk; });
  process.stdin.on('end', () => resolve(data));
  process.stdin.on('error', reject);
});

const request = JSON.parse(input || '{}');
const op = String(request.op || '');
const port = Number(request.port || 9222);
const payload = request.payload && typeof request.payload === 'object' ? request.payload : {};
const endpoint = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

class CDP {
  constructor(url, timeoutMs = 15000) {
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

async function fetchJson(url, timeoutMs = 5000) {
  const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
  return response.json();
}

async function listTargets() {
  return fetchJson(`${endpoint}/json/list`);
}

function publicTarget(target) {
  if (!target) return null;
  return {
    id: target.id,
    type: target.type,
    title: target.title,
    url: target.url,
    faviconUrl: target.faviconUrl || null,
  };
}

async function browserClient() {
  const version = await fetchJson(`${endpoint}/json/version`);
  const client = new CDP(version.webSocketDebuggerUrl);
  await client.open();
  return { client, version };
}

async function targetBySelector(selector = payload) {
  const list = await listTargets();
  let target = null;
  if (selector.target_id) target = list.find((item) => item.id === String(selector.target_id));
  else if (selector.target_url) target = list.find((item) => item.url === String(selector.target_url));
  else if (selector.url_contains) target = list.find((item) => String(item.url || '').includes(String(selector.url_contains)));
  else if (selector.title_contains) target = list.find((item) => String(item.title || '').includes(String(selector.title_contains)));
  else target = list.find((item) => item.type === 'page');
  if (!target?.webSocketDebuggerUrl) throw new Error(`target not found for selector ${JSON.stringify(selector)}`);
  return target;
}

async function withTarget(selector, fn) {
  const target = await targetBySelector(selector);
  const client = new CDP(target.webSocketDebuggerUrl, Number(payload.timeout_ms || 15000));
  await client.open();
  try {
    return await fn(client, target);
  } finally {
    client.close();
  }
}

async function waitCreatedTarget(targetId, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const target = (await listTargets()).find((item) => item.id === targetId);
    if (target?.webSocketDebuggerUrl) return target;
    await sleep(100);
  }
  return null;
}

async function main() {
  if (op === 'targets') {
    const version = await fetchJson(`${endpoint}/json/version`);
    const targets = (await listTargets()).map(publicTarget);
    return { browser: version.Browser || null, targets };
  }

  if (op === 'open') {
    const url = String(payload.url || 'about:blank');
    const { client: browser } = await browserClient();
    try {
      const created = await browser.call('Target.createTarget', { url, newWindow: Boolean(payload.new_window), background: Boolean(payload.background) });
      const target = await waitCreatedTarget(created.targetId, Number(payload.timeout_ms || 10000));
      return { target: publicTarget(target) || { id: created.targetId, type: 'page', title: '', url } };
    } finally {
      browser.close();
    }
  }

  if (op === 'close') {
    const target = await targetBySelector(payload);
    const { client: browser } = await browserClient();
    try {
      const result = await browser.call('Target.closeTarget', { targetId: target.id });
      return { closed: Boolean(result.success), target: publicTarget(target) };
    } finally {
      browser.close();
    }
  }

  if (op === 'activate') {
    const target = await targetBySelector(payload);
    const { client: browser } = await browserClient();
    try {
      await browser.call('Target.activateTarget', { targetId: target.id });
      return { activated: true, target: publicTarget(target) };
    } finally {
      browser.close();
    }
  }

  if (op === 'navigate') {
    const destination = String(payload.url || '');
    if (!destination) throw new Error('navigate requires payload.url');
    return withTarget(payload, async (client, target) => {
      await client.call('Page.enable');
      const result = await client.call('Page.navigate', { url: destination });
      if (payload.wait_ms) await sleep(Number(payload.wait_ms));
      return { target: publicTarget(target), destination, frameId: result.frameId || null, loaderId: result.loaderId || null, errorText: result.errorText || null };
    });
  }

  if (op === 'reload') {
    return withTarget(payload, async (client, target) => {
      await client.call('Page.enable');
      await client.call('Page.reload', { ignoreCache: Boolean(payload.ignore_cache) });
      if (payload.wait_ms) await sleep(Number(payload.wait_ms));
      return { reloaded: true, target: publicTarget(target) };
    });
  }

  if (op === 'evaluate') {
    const expression = String(payload.expression || '');
    if (!expression) throw new Error('evaluate requires payload.expression');
    return withTarget(payload, async (client, target) => {
      await client.call('Runtime.enable');
      const result = await client.call('Runtime.evaluate', {
        expression,
        awaitPromise: payload.await_promise !== false,
        returnByValue: true,
        userGesture: payload.user_gesture !== false,
      });
      if (result.exceptionDetails) {
        const description = result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'Runtime exception';
        throw new Error(description);
      }
      return {
        target: publicTarget(target),
        value: Object.prototype.hasOwnProperty.call(result.result || {}, 'value') ? result.result.value : null,
        type: result.result?.type || null,
        description: result.result?.description || null,
      };
    });
  }

  if (op === 'screenshot') {
    return withTarget(payload, async (client, target) => {
      await client.call('Page.enable');
      const params = {
        format: ['jpeg', 'webp'].includes(String(payload.format || '').toLowerCase()) ? String(payload.format).toLowerCase() : 'png',
        fromSurface: true,
        captureBeyondViewport: payload.full_page !== false,
      };
      if (params.format !== 'png' && payload.quality != null) params.quality = Math.max(0, Math.min(100, Number(payload.quality)));
      const shot = await client.call('Page.captureScreenshot', params);
      return { target: publicTarget(target), format: params.format, base64: shot.data, bytes: Math.floor((shot.data.length * 3) / 4) };
    });
  }

  throw new Error(`unsupported browser-control operation: ${op}`);
}

try {
  const result = await main();
  console.log(JSON.stringify({ ok: true, result }));
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: String(error?.stack || error) }));
  process.exit(1);
}
