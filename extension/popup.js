// Popup controller — creates a NeuroSync session, acquires a tab-capture stream
// id from a user gesture, and hands off to the background/offscreen pipeline.

const els = {
  dot: document.getElementById('dot'),
  provider: document.getElementById('provider'),
  name: document.getElementById('name'),
  start: document.getElementById('start'),
  stop: document.getElementById('stop'),
  status: document.getElementById('status'),
};

let activeTab = null;
let detected = null;

function setStatus(msg) { els.status.textContent = msg || ''; }

const STATE_LABEL = {
  connecting: 'Connecting…',
  warming:    'Warming models…',
  recording:  'Recording · streaming to NeuroSync',
  live:       'Live analysis · view the dashboard',
  error:      'Capture error',
};

function renderState(state) {
  if (!state) return;
  setStatus(STATE_LABEL[state] || state);
  els.dot.classList.toggle('on', state === 'live' || state === 'recording');
}

// Reflect capture status updates published by the offscreen document.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.captureStatus) {
    const s = changes.captureStatus.newValue;
    renderState(s && s.state);
  }
});

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  activeTab = tab;
  detected = detectProvider(tab && tab.url);

  // Is a capture already running?
  const { activeSession, captureStatus } = await chrome.storage.local.get(['activeSession', 'captureStatus']);
  if (activeSession) {
    els.provider.textContent = activeSession.providerName || 'Meeting';
    els.dot.classList.add('on');
    els.start.style.display = 'none';
    els.stop.style.display = 'block';
    if (captureStatus && captureStatus.state) renderState(captureStatus.state);
    else setStatus('Analysis running · session ' + activeSession.sessionId.slice(0, 8));
    return;
  }

  if (detected) {
    els.provider.textContent = detected.name;
    els.dot.classList.add('on');
    els.start.disabled = false;
  } else {
    els.provider.textContent = 'No supported meeting in this tab';
    els.start.disabled = true;
  }
}

els.start.addEventListener('click', async () => {
  if (!activeTab) return;
  els.start.disabled = true;
  setStatus('Creating session…');
  try {
    // 1. Create a NeuroSync session.
    const res = await fetch(`${NEUROSYNC.API_BASE}/api/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_name: els.name.value.trim() || (detected ? detected.name + ' interview' : 'Meeting'),
        mode: 'interview',
      }),
    });
    if (!res.ok) throw new Error('Session create failed (' + res.status + ')');
    const { session_id } = await res.json();

    // 2. Acquire a tab-capture stream id (must be from this user gesture).
    setStatus('Requesting tab capture…');
    const streamId = await new Promise((resolve, reject) => {
      chrome.tabCapture.getMediaStreamId({ targetTabId: activeTab.id }, (id) => {
        const err = chrome.runtime.lastError;
        if (err || !id) reject(new Error(err ? err.message : 'No stream id')); else resolve(id);
      });
    });

    // 3. Hand off to background → offscreen for capture + streaming.
    await chrome.runtime.sendMessage({
      type: 'start_capture',
      streamId,
      sessionId: session_id,
      providerName: detected ? detected.name : 'Meeting',
    });

    await chrome.storage.local.set({
      activeSession: { sessionId: session_id, providerName: detected ? detected.name : 'Meeting' },
    });

    els.dot.classList.add('on');
    els.start.style.display = 'none';
    els.stop.style.display = 'block';
    setStatus('Analysis running · open the NeuroSync dashboard to watch live.');
  } catch (e) {
    setStatus('Error: ' + e.message);
    els.start.disabled = false;
  }
});

els.stop.addEventListener('click', async () => {
  setStatus('Stopping…');
  await chrome.runtime.sendMessage({ type: 'stop_capture' });
  await chrome.storage.local.remove('activeSession');
  els.stop.style.display = 'none';
  els.start.style.display = 'block';
  els.start.disabled = false;
  els.dot.classList.remove('on');
  setStatus('Stopped.');
});

init();
