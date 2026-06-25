# NuanceAI — Known Limitations

Version 1.2.0-rc1 · Updated: 2026-06-24

---

## No Authentication Layer

**Severity**: High  
**Status**: Not implemented  
**Impact**: Any user with network access can create sessions, view all session history, and read all behavioral data  
**Workaround**: Deploy behind a VPN or reverse proxy with HTTP basic auth (nginx `auth_basic`)  
**Recommended fix**: Add JWT middleware to FastAPI; protect all `/api/*` and `/ws/*` routes; add a login page in the frontend

---

## `getUserMedia` Requires HTTPS in Production

**Severity**: High  
**Status**: Browser security requirement  
**Impact**: Webcam and microphone capture silently fail on plain HTTP outside localhost. The session page will load but camera and audio will be unavailable.  
**Fix**: Deploy with TLS termination (nginx + Let's Encrypt, or Cloudflare)

---

## ScriptProcessorNode Deprecated (Web Audio)

**Severity**: Medium  
**Status**: Deprecated in Web Audio API spec; functional in all current browsers (Chrome, Firefox, Safari, Edge)  
**Impact**: May show a deprecation warning in Chrome DevTools console. No functional impact.  
**Recommended fix**: Migrate audio capture to `AudioWorkletNode`. Requires HTTPS and a dedicated worker JS file.

---

## Whisper Model Accuracy

**Severity**: Medium  
**Status**: Using Whisper `base` model (74M parameters)  
**Impact**: ~85% word accuracy on clear, accented-free speech. Degrades with accents, background noise, or fast speech. Behavioral NLP scores inherit transcription errors.  
**Recommended fix**: Upgrade to `small` or `medium` model (set `WHISPER_MODEL=small` in `.env`). Add Voice Activity Detection to skip silent audio chunks.

---

## Single SQLite Database

**Severity**: Medium  
**Status**: All persistence through one SQLite WAL file at `data/nuanceai.db`  
**Impact**: Not suitable for multi-process or multi-server deployment. Concurrent writes are serialized.  
**Acceptable for**: Single-server enterprise deployment with < 50 concurrent sessions and < 100K sessions total  
**Recommended fix**: Migrate to PostgreSQL with SQLAlchemy async ORM for horizontal scaling

---

## DeBERTa Checkpoint Dependency

**Severity**: Medium  
**Status**: Full behavioral NLP scoring requires `models/deberta/best/model.pt`  
**Impact**: Without the checkpoint, NLP classification falls back to rule-based heuristics (filler word count only). Confidence, stress, hesitation, and communication scores will be less accurate.  
**Fallback**: Rule-based fallback is production-safe; results are clearly degraded but not broken  
**Fix**: Train the model: `python ml/training/deberta_trainer.py --epochs 5`

---

## PDF Export via `window.print()`

**Severity**: Low  
**Status**: Report export triggers the browser's native print dialog  
**Impact**: PDF output uses browser print CSS. Layout is professional but not pixel-perfect — page breaks depend on browser and OS.  
**Recommended fix**: Integrate `@media print` CSS rules for explicit page break control, or add a server-side PDF generation service (`puppeteer`, `weasyprint`)

---

## No WebSocket Rate Limiting

**Severity**: Low  
**Status**: No server-side frame rate enforcement  
**Impact**: A malicious or buggy client could flood the backend with WebSocket frames. Frontend caps at 5fps, but no server-side enforcement exists.  
**Workaround**: Deploy behind nginx with WebSocket rate limiting  
**Recommended fix**: Add per-session frame counter with per-second cap in `ws_session.py`

---

## Whisper Singleton — Concurrent Session Throughput

**Severity**: Low  
**Status**: All sessions share one Whisper model instance  
**Impact**: Whisper transcription is queued across concurrent sessions. At 3+ simultaneous sessions, transcription latency may exceed 10 seconds per chunk (the configured timeout).  
**Python GIL note**: Whisper runs in a `ThreadPoolExecutor` — the GIL is released during C/CUDA inference, so parallelism is partial  
**Practical limit**: ~3–5 concurrent sessions before noticeable transcript lag  
**Recommended fix**: Dedicated Whisper worker process with an asyncio queue

---

## GPU Memory (MX130 / 2GB VRAM)

**Severity**: Low (hardware-specific)  
**Status**: DeBERTa v3 + LoRA uses ~900MB VRAM; leaves ~1.1GB free  
**Impact**: Cannot run DeBERTa and Whisper on GPU simultaneously. With CUDA installed, DeBERTa runs on GPU while Whisper remains on CPU.  
**Risk**: Multiple concurrent sessions may push VRAM usage into OOM territory  
**Mitigation**: OOM exceptions are caught per-session; inference falls back to CPU automatically

---

## Settings Persistence Is Local Only

**Severity**: Low  
**Status**: Settings (session defaults, alert thresholds, model config) are stored in browser `localStorage`  
**Impact**: Settings reset in private/incognito mode or when localStorage is cleared. Settings are per-browser, not per-user.  
**Recommended fix**: Add a backend `/api/settings` endpoint to persist preferences server-side

---

## No Standalone `/reports` Route

**Severity**: Low  
**Status**: The professional behavioral report is accessible only through the Session Results page (Report tab)  
**Impact**: No dedicated URL to share a standalone report. "Share" button copies the Results page URL (which includes all 5 tabs).  
**Workaround**: Direct user to the Report tab and use browser print  
**No immediate action needed**: Acceptable for current product scope

---

## Mobile Layout Not Fully Optimized

**Severity**: Low  
**Status**: Responsive breakpoints exist but the live session layout (3-column grid) degrades on small screens  
**Impact**: Live session page is designed for desktop/laptop use (webcam sessions require a camera anyway)  
**No immediate action needed**: Enterprise interview software is not a primary mobile use case
