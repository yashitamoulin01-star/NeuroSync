# NeuroSync Capture — Browser Extension (Chrome MV3)

Streams a meeting tab (Google Meet, Zoom Web, Microsoft Teams, Webex) into
NeuroSync for live behavioral analysis. The extension is a **capture/transport
layer only** — no AI runs in the browser, and it never injects into or modifies
the meeting application.

## How it works

```
Popup (user gesture)
  → POST /api/session                     create a NeuroSync session
  → chrome.tabCapture.getMediaStreamId    acquire the tab stream id
  → background → offscreen document        (MV3: getUserMedia needs DOM)
      → getUserMedia(chromeMediaSource:tab)
      → WebSocket /ws/session/{id}
          frames  → { type:"frame", payload:{ image_b64 } }   (500 ms)
          audio   → { type:"audio", payload:{ pcm_b64, sample_rate:16000 } }
```

This is the exact protocol `backend/routers/ws_session.py` already consumes, so a
captured meeting produces the same live dashboard and report as an in-app session.

## Browser support

Manifest V3 + the offscreen API work across Chromium browsers: **Chrome, Edge,
Brave, Arc, and Opera** (Chrome 116+). The extension folder loads unchanged in
all of them. Firefox support is a later addition — it needs a `browser_specific_settings`
block and (currently) an MV2-style background; the capture/transport logic in
`offscreen.js` is browser-agnostic and would be reused.

## Live status

While a capture runs, the popup reflects the AI pipeline state, published by the
offscreen document via `chrome.storage`: **Connecting → Warming models →
Recording → Live analysis**.

## Install (load unpacked)

1. Start the NeuroSync backend (`http://localhost:8000`).
2. Open `chrome://extensions`, enable **Developer mode**.
3. Click **Load unpacked** and select this `extension/` folder.
4. Join a meeting in a supported tab; click the NeuroSync icon → **Start Analysis**.
5. Open the NeuroSync dashboard to watch the live session; click **Stop Analysis**
   (or end the meeting) to finalize the report.

## Configuration

Edit `config.js` to point at a non-local backend (`API_BASE`, `WS_BASE`) or to
change frame rate / quality / audio sample rate.

## Notes & limitations

- Requires Chrome 116+ (offscreen documents + `tabCapture.getMediaStreamId`).
- Tab capture grabs the tab's composited video + audio. Per-participant framing
  and speaker attribution are handled server-side (see `backend/capture/participants.py`).
- Icons are intentionally omitted to keep the repo binary-free; Chrome shows a
  default action icon. Add `icons/` + a manifest `icons` block to brand it.
- Authentication: this reference build calls the open core session endpoints. To
  require enterprise auth, attach a bearer token to the `fetch`/WebSocket calls.
