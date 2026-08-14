(() => {
  'use strict';
  const CHANNEL = 'TORSIONFIELD_PAGE_CALL';
  const RESULT = 'TORSIONFIELD_PAGE_RESULT';
  window.addEventListener('message', (event) => {
    if (event.source !== window || event.data?.channel !== CHANNEL) return;
    const id = event.data.id;
    chrome.runtime.sendMessage({ channel: 'TORSIONFIELD_RESIDENT_CALL', path: event.data.path, args: event.data.args || {} }, (reply) => {
      window.postMessage({ channel: RESULT, id, ...(reply || { ok: false, error: chrome.runtime.lastError?.message || 'no reply' }) }, '*');
    });
  });
})();
