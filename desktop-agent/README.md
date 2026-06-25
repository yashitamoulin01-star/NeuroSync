# NeuroSync Desktop Agent (Electron)

A lightweight companion app that captures a selected **application window or
screen** plus audio and streams it to NeuroSync for live behavioral analysis.
It behaves like OBS or screen-recording software.

## Security model

- **OS capture APIs only.** Uses Electron's `desktopCapturer` (Windows Graphics
  Capture / macOS ScreenCaptureKit under the hood) with explicit user selection.
- **Never injects** into, reads memory from, or modifies another process.
- **Explicit consent.** The user picks exactly one window/screen; nothing is
  captured until they click **Start Analysis**.
- `contextIsolation` on, `nodeIntegration` off; the renderer gets a minimal
  preload bridge (`listSources`, `config`) and nothing else.

## How it works

```
Pick a window  → POST /api/session                         create session
Start Analysis → getUserMedia(chromeMediaSource:'desktop')  OS window capture + mic
               → WebSocket /ws/session/{id}
                   frames → { type:"frame", payload:{ image_b64 } }   (500 ms)
                   audio  → { type:"audio", payload:{ pcm_b64, sample_rate:16000 } }
```

Same protocol as `backend/routers/ws_session.py`, so a desktop-captured meeting
produces an identical live dashboard and report.

## Run

```bash
cd desktop-agent
npm install      # installs Electron
npm start        # launches the agent
```

Then start the NeuroSync backend, pick a meeting window, and click **Start
Analysis**. Open the NeuroSync dashboard to watch the session live.

## Notes

- System (loopback) audio capture support varies by OS. Windows generally allows
  desktop audio via `chromeMediaSource:'desktop'`; on macOS, system audio may
  require a virtual audio device. Microphone is always captured.
- Packaging (electron-builder) and code signing are out of scope for this
  reference build; `npm start` runs it unpackaged.
- `config.js` points at `http://localhost:8000` by default.
