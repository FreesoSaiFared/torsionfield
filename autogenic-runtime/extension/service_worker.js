import { TF_RESIDENT_URL, TF_RESIDENT_TOKEN } from './runtime_config.js';

const ALLOWED_PATHS = new Set([
  '/v1/action/execute', '/v1/action/get',
  '/v1/health', '/v1/exec', '/v1/process/start', '/v1/process/kill', '/v1/process/list',
  '/v1/fs/read', '/v1/fs/write', '/v1/fs/delete',
  '/v1/browser/launch', '/v1/browser/restart', '/v1/browser/status',
  '/v1/browser/targets', '/v1/browser/open', '/v1/browser/close', '/v1/browser/activate',
  '/v1/browser/navigate', '/v1/browser/reload', '/v1/browser/evaluate', '/v1/browser/screenshot',
  '/v1/userscript/refresh',
]);

function allowedSender(sender) {
  const url = String(sender?.url || sender?.tab?.url || '');
  return /^https:\/\/(chatgpt\.com|chat\.openai\.com)\//.test(url);
}

async function resident(path, args = {}) {
  if (!ALLOWED_PATHS.has(path)) throw new Error(`resident path not exported: ${path}`);
  const isHealth = path === '/v1/health';
  const response = await fetch(`${TF_RESIDENT_URL}${path}`, {
    method: isHealth ? 'GET' : 'POST',
    headers: {
      'Authorization': `Bearer ${TF_RESIDENT_TOKEN}`,
      ...(isHealth ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(isHealth ? {} : { body: JSON.stringify(args) }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || !body.ok) throw new Error(body.detail || body.error || `resident HTTP ${response.status}`);
  return Object.prototype.hasOwnProperty.call(body, 'result') ? body.result : body;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.channel !== 'TORSIONFIELD_RESIDENT_CALL') return false;
  if (!allowedSender(sender)) {
    sendResponse({ ok: false, error: 'resident bridge rejected non-ChatGPT sender' });
    return false;
  }
  resident(String(message.path || ''), message.args || {})
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ tfAutogenicVersion: chrome.runtime.getManifest().version });
});
