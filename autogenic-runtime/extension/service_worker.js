import { TF_RESIDENT_URL, TF_RESIDENT_TOKEN } from './runtime_config.js';

async function resident(path, args = {}) {
  const response = await fetch(`${TF_RESIDENT_URL}${path}`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${TF_RESIDENT_TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || !body.ok) throw new Error(body.detail || body.error || `resident HTTP ${response.status}`);
  return body.result;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.channel !== 'TORSIONFIELD_RESIDENT_CALL') return false;
  resident(String(message.path || ''), message.args || {})
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ tfAutogenicVersion: chrome.runtime.getManifest().version });
});
