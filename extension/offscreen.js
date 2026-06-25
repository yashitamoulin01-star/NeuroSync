// Offscreen document — the only place with DOM + getUserMedia. Captures the tab
// stream and forwards frames (JPEG) and audio (16 kHz int16 PCM) to the NeuroSync
// backend over the same WebSocket protocol a live in-app session uses.

let stream = null;
let ws = null;
let frameTimer = null;
let audioCtx = null;
let processor = null;
let cfg = null;

const video = document.getElementById('v');
const canvas = document.getElementById('c');

// Publish capture status so the popup can reflect it live.
function setState(state) {
  try { chrome.storage.local.set({ captureStatus: { state, ts: Date.now() } }); } catch (_) {}
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.target !== 'offscreen') return;
  if (msg.type === 'offscreen_start') start(msg);
  else if (msg.type === 'offscreen_stop') stop(true);
});

async function start(config) {
  cfg = config;
  setState('connecting');
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: config.streamId } },
      audio: { mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: config.streamId } },
    });
  } catch (e) {
    console.error('NeuroSync capture: getUserMedia failed', e);
    setState('error');
    chrome.runtime.sendMessage({ type: 'capture_ended' });
    return;
  }

  // Keep the meeting audio audible to the user while we tap it.
  try {
    const ctx = new AudioContext();
    ctx.createMediaStreamSource(stream).connect(ctx.destination);
  } catch (_) { /* non-fatal */ }

  video.srcObject = stream;
  await video.play().catch(() => {});

  setState('warming');
  ws = new WebSocket(`${config.wsBase}/ws/session/${config.sessionId}`);
  ws.onopen = () => {
    setState('recording');
    startFrameLoop();
    startAudioLoop();
  };
  ws.onmessage = (ev) => {
    // First analytics frame from the backend means live analysis is flowing.
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'analytics_update') setState('live');
    } catch (_) { /* ignore non-JSON */ }
  };
  ws.onclose = () => stop(false);

  // If the user ends the meeting / closes the tab, the track ends.
  stream.getVideoTracks()[0].addEventListener('ended', () => stop(true));
}

function startFrameLoop() {
  const interval = cfg.frameInterval || 500;
  frameTimer = setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) return;
    canvas.width = Math.min(w, 640);
    canvas.height = Math.round(canvas.width * (h / w));
    const g = canvas.getContext('2d');
    g.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', cfg.frameQuality || 0.6);
    const b64 = dataUrl.split(',')[1];
    ws.send(JSON.stringify({ type: 'frame', session_id: cfg.sessionId, payload: { image_b64: b64 } }));
  }, interval);
}

function startAudioLoop() {
  const targetRate = cfg.sampleRate || 16000;
  try {
    audioCtx = new AudioContext();
    const source = audioCtx.createMediaStreamSource(stream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    source.connect(processor);
    processor.connect(audioCtx.destination);
    processor.onaudioprocess = (e) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      const input = e.inputBuffer.getChannelData(0);
      const pcm = downsampleToInt16(input, audioCtx.sampleRate, targetRate);
      if (!pcm) return;
      ws.send(JSON.stringify({
        type: 'audio', session_id: cfg.sessionId,
        payload: { pcm_b64: int16ToBase64(pcm), sample_rate: targetRate },
      }));
    };
  } catch (e) {
    console.warn('NeuroSync capture: audio tap unavailable', e);
  }
}

function downsampleToInt16(input, inRate, outRate) {
  if (outRate >= inRate) {
    const out = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) out[i] = clamp16(input[i]);
    return out;
  }
  const ratio = inRate / outRate;
  const outLen = Math.floor(input.length / ratio);
  const out = new Int16Array(outLen);
  for (let i = 0; i < outLen; i++) out[i] = clamp16(input[Math.floor(i * ratio)]);
  return out;
}

function clamp16(f) {
  const s = Math.max(-1, Math.min(1, f));
  return s < 0 ? s * 0x8000 : s * 0x7fff;
}

function int16ToBase64(int16) {
  const bytes = new Uint8Array(int16.buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function stop(notify) {
  if (frameTimer) { clearInterval(frameTimer); frameTimer = null; }
  if (processor) { try { processor.disconnect(); } catch (_) {} processor = null; }
  if (audioCtx) { try { audioCtx.close(); } catch (_) {} audioCtx = null; }
  if (ws && ws.readyState === WebSocket.OPEN) {
    try { ws.send(JSON.stringify({ type: 'end', session_id: cfg && cfg.sessionId })); } catch (_) {}
    try { ws.close(); } catch (_) {}
  }
  ws = null;
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  try { chrome.storage.local.remove('captureStatus'); } catch (_) {}
  if (notify) chrome.runtime.sendMessage({ type: 'capture_ended' });
}
