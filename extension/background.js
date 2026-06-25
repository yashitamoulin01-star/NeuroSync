// Service worker — orchestrates the offscreen capture document. The service
// worker cannot use getUserMedia itself (no DOM), so all media work happens in
// an offscreen document; this worker only manages its lifecycle and relays
// start/stop messages.

importScripts('config.js');

async function ensureOffscreen() {
  const has = await chrome.offscreen.hasDocument?.();
  if (has) return;
  await chrome.offscreen.createDocument({
    url: 'offscreen.html',
    reasons: ['USER_MEDIA'],
    justification: 'Capture the selected meeting tab and stream frames/audio to NeuroSync.',
  });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if (msg.type === 'start_capture') {
      await ensureOffscreen();
      // Give the offscreen document a tick to register its listener.
      setTimeout(() => {
        chrome.runtime.sendMessage({
          target: 'offscreen',
          type: 'offscreen_start',
          streamId: msg.streamId,
          sessionId: msg.sessionId,
          wsBase: NEUROSYNC.WS_BASE,
          apiBase: NEUROSYNC.API_BASE,
          frameInterval: NEUROSYNC.FRAME_INTERVAL_MS,
          frameQuality: NEUROSYNC.FRAME_QUALITY,
          sampleRate: NEUROSYNC.AUDIO_SAMPLE_RATE,
        });
      }, 150);
      sendResponse({ ok: true });
    } else if (msg.type === 'stop_capture') {
      chrome.runtime.sendMessage({ target: 'offscreen', type: 'offscreen_stop' });
      setTimeout(() => chrome.offscreen.closeDocument?.().catch(() => {}), 500);
      sendResponse({ ok: true });
    } else if (msg.type === 'capture_ended') {
      // Offscreen reported the stream ended on its own.
      chrome.storage.local.remove('activeSession');
      chrome.offscreen.closeDocument?.().catch(() => {});
    }
  })();
  return true; // async sendResponse
});
