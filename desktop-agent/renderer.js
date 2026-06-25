// Renderer — source picker + capture pipeline. Mirrors the browser extension's
// streaming protocol so a desktop-captured meeting produces the same live session
// and report as any other source.

const cfg = window.neurosync.config;
const els = {
  dot: document.getElementById('dot'),
  sources: document.getElementById('sources'),
  name: document.getElementById('name'),
  start: document.getElementById('start'),
  stop: document.getElementById('stop'),
  status: document.getElementById('status'),
  refresh: document.getElementById('refresh'),
  previewWrap: document.getElementById('previewWrap'),
  preview: document.getElementById('preview'),
  health: document.getElementById('health'),
};

let selectedSource = null;
let stream = null;
let ws = null;
let frameTimer = null;
let healthTimer = null;
let audioCtx = null;
let processor = null;
let sessionId = null;
let stopping = false;
let reconnectAttempts = 0;
let framesSent = 0;
let framesWindow = 0;

const video = els.preview;
const canvas = document.createElement('canvas');

function setStatus(m) { els.status.textContent = m || ''; }

async function loadSources() {
  els.sources.innerHTML = '';
  const sources = await window.neurosync.listSources();
  for (const s of sources) {
    const div = document.createElement('div');
    div.className = 'src';
    div.innerHTML =
      `<img src="${s.thumbnail || ''}" alt="" />` +
      `<div class="nm">${s.name}</div>` +
      (s.meetingApp ? `<div class="badge">${s.meetingApp}</div>` : '');
    div.addEventListener('click', () => {
      document.querySelectorAll('.src').forEach((e) => e.classList.remove('sel'));
      div.classList.add('sel');
      selectedSource = s;
      els.start.disabled = false;
    });
    els.sources.appendChild(div);
  }
  setStatus(sources.length ? '' : 'No capturable windows found.');
}

els.refresh.addEventListener('click', loadSources);

els.start.addEventListener('click', async () => {
  if (!selectedSource) return;
  els.start.disabled = true;
  setStatus('Creating session…');
  try {
    const res = await fetch(`${cfg.API_BASE}/api/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_name: els.name.value.trim() || (selectedSource.meetingApp || 'Desktop') + ' interview',
        mode: 'interview',
      }),
    });
    if (!res.ok) throw new Error('Session create failed (' + res.status + ')');
    sessionId = (await res.json()).session_id;

    setStatus('Starting capture…');
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { mandatory: { chromeMediaSource: 'desktop' } },
      video: { mandatory: { chromeMediaSource: 'desktop', chromeMediaSourceId: selectedSource.id } },
    });

    // Microphone (the interviewer's side) is captured separately and mixed in.
    try {
      const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
      mic.getAudioTracks().forEach((t) => stream.addTrack(t));
    } catch (_) { /* mic optional */ }

    video.srcObject = stream;
    els.previewWrap.style.display = 'block';
    await video.play().catch(() => {});

    stopping = false;
    reconnectAttempts = 0;
    connectWs();
    startHealthLoop();
    stream.getVideoTracks()[0].addEventListener('ended', () => stop(true));
  } catch (e) {
    // Permission validation: surface actionable guidance.
    const msg = (e && e.name === 'NotAllowedError')
      ? 'Permission denied. Grant screen/audio capture access and try again.'
      : (e && e.message) || 'Capture failed';
    setStatus('Error: ' + msg);
    els.start.disabled = false;
  }
});

function connectWs() {
  ws = new WebSocket(`${cfg.WS_BASE}/ws/session/${sessionId}`);
  ws.onopen = () => {
    reconnectAttempts = 0;
    stopFrameAudio();        // clean teardown before (re)starting loops
    startFrameLoop();
    startAudioLoop();
    onRunning();
  };
  ws.onmessage = (ev) => {
    try { if (JSON.parse(ev.data).type === 'analytics_update') els.dot.classList.add('on'); } catch (_) {}
  };
  ws.onclose = () => {
    stopFrameAudio();
    if (stopping) return;
    // Unexpected close: the backend keeps the session PAUSED and resumes on
    // reconnect, so we reconnect to the SAME session id with backoff.
    if (reconnectAttempts < 6 && stream) {
      const delay = Math.min(1000 * 2 ** reconnectAttempts, 8000);
      reconnectAttempts++;
      setStatus('Reconnecting (' + reconnectAttempts + ')…');
      setTimeout(() => { if (!stopping && stream) connectWs(); }, delay);
    } else if (!stopping) {
      setStatus('Connection lost. Stop and start again to resume.');
    }
  };
  ws.onerror = () => { try { ws.close(); } catch (_) {} };
}

function startHealthLoop() {
  if (healthTimer) clearInterval(healthTimer);
  healthTimer = setInterval(() => {
    const wsState = ws && ws.readyState === WebSocket.OPEN ? 'connected'
      : ws && ws.readyState === WebSocket.CONNECTING ? 'connecting' : 'down';
    els.health.textContent = `${framesWindow} fps · WS ${wsState} · ${framesSent} frames sent`;
    framesWindow = 0;
  }, 1000);
}

function stopFrameAudio() {
  if (frameTimer) { clearInterval(frameTimer); frameTimer = null; }
  if (processor) { try { processor.disconnect(); } catch (_) {} processor = null; }
  if (audioCtx) { try { audioCtx.close(); } catch (_) {} audioCtx = null; }
}

els.stop.addEventListener('click', () => stop(true));

function onRunning() {
  els.dot.classList.add('on');
  els.start.style.display = 'none';
  els.stop.style.display = 'block';
  setStatus('Analysis running · session ' + sessionId.slice(0, 8) + ' · open the NeuroSync dashboard.');
}

function startFrameLoop() {
  frameTimer = setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) return;
    canvas.width = Math.min(w, 640);
    canvas.height = Math.round(canvas.width * (h / w));
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const b64 = canvas.toDataURL('image/jpeg', cfg.FRAME_QUALITY).split(',')[1];
    ws.send(JSON.stringify({ type: 'frame', session_id: sessionId, payload: { image_b64: b64 } }));
    framesSent++; framesWindow++;
  }, cfg.FRAME_INTERVAL_MS);
}

function startAudioLoop() {
  const target = cfg.AUDIO_SAMPLE_RATE;
  try {
    audioCtx = new AudioContext();
    const source = audioCtx.createMediaStreamSource(stream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    source.connect(processor);
    processor.connect(audioCtx.destination);
    processor.onaudioprocess = (e) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      const input = e.inputBuffer.getChannelData(0);
      const pcm = downsample(input, audioCtx.sampleRate, target);
      ws.send(JSON.stringify({
        type: 'audio', session_id: sessionId,
        payload: { pcm_b64: int16ToBase64(pcm), sample_rate: target },
      }));
    };
  } catch (e) { console.warn('audio tap unavailable', e); }
}

function downsample(input, inRate, outRate) {
  if (outRate >= inRate) { const o = new Int16Array(input.length); for (let i=0;i<input.length;i++) o[i]=clamp(input[i]); return o; }
  const ratio = inRate / outRate, len = Math.floor(input.length / ratio), o = new Int16Array(len);
  for (let i = 0; i < len; i++) o[i] = clamp(input[Math.floor(i * ratio)]);
  return o;
}
function clamp(f) { const s = Math.max(-1, Math.min(1, f)); return s < 0 ? s * 0x8000 : s * 0x7fff; }
function int16ToBase64(int16) {
  const bytes = new Uint8Array(int16.buffer); let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

function stop(notify) {
  stopping = true;
  if (healthTimer) { clearInterval(healthTimer); healthTimer = null; }
  stopFrameAudio();
  if (ws && ws.readyState === WebSocket.OPEN) {
    try { ws.send(JSON.stringify({ type: 'end', session_id: sessionId })); ws.close(); } catch (_) {}
  }
  ws = null;
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  els.previewWrap.style.display = 'none';
  els.health.textContent = '';
  els.dot.classList.remove('on');
  els.stop.style.display = 'none';
  els.start.style.display = 'block';
  els.start.disabled = !selectedSource;
  if (notify) setStatus('Stopped.');
}

loadSources();
