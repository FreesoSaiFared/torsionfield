(() => {
  'use strict';
  const VERSION = '0.2.0';
  const CALL = 'TORSIONFIELD_PAGE_CALL';
  const RESULT = 'TORSIONFIELD_PAGE_RESULT';
  const PING = 'TORSIONFIELD_BRIDGE_PING';
  const READY = 'TORSIONFIELD_BRIDGE_READY';

  function announce() {
    window.postMessage({ channel: READY, version: VERSION }, '*');
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    if (event.data?.channel === PING) {
      announce();
      return;
    }
    if (event.data?.channel !== CALL) return;
    const id = event.data.id;
    chrome.runtime.sendMessage({
      channel: 'TORSIONFIELD_RESIDENT_CALL',
      path: event.data.path,
      args: event.data.args || {},
    }, (reply) => {
      const fallback = { ok: false, error: chrome.runtime.lastError?.message || 'no reply' };
      window.postMessage({ channel: RESULT, id, ...(reply || fallback) }, '*');
    });
  });

  announce();
})();
