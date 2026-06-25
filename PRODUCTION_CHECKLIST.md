# NuanceAI — Production Checklist

Version 1.1.0 · Pre-deployment validation

---

## Infrastructure

- [ ] Server has at least 8GB RAM (16GB recommended with DeBERTa on CPU)
- [ ] Minimum 20GB free disk space for media recordings and DB
- [ ] TLS certificate configured — `getUserMedia` fails without HTTPS outside localhost
- [ ] Nginx or Caddy reverse proxy configured for TLS termination
- [ ] Port 8000 not exposed directly to the internet (proxy only)
- [ ] `data/` directory is writable by the backend process
- [ ] `models/` directory contains required artifacts (see below)

---

## Model Artifacts

Run `GET /api/health/detailed` and verify all components are `online` or `idle`:

- [ ] `models/deberta/best/model.pt` exists → DeBERTa v3 checkpoint
- [ ] `models/deberta/metrics.json` exists → F1 scores shown in UI
- [ ] `models/fusion/best_fusion.pt` exists → Behavioral Fusion model
- [ ] `models/classifiers/confidence_clf.pkl` exists → sklearn classifiers

If any model is missing, the system degrades gracefully:
- DeBERTa missing → rule-based NLP fallback
- Fusion missing → weighted average fallback
- Classifiers missing → default scores

---

## Python Environment

```bash
# Verify all dependencies load cleanly
cd D:\MBD
.venv\Scripts\python -c "import cv2, mediapipe, torch, whisper, psutil, fastapi, pydantic"

# Start backend and check startup log for ✓/✗ dependency report
.venv\Scripts\python -m uvicorn backend.main:app --port 8000
```

Verify startup log shows:
- [ ] `✓ cv2` — OpenCV for frame processing
- [ ] `✓ mediapipe` — Face mesh
- [ ] `✓ torch` — PyTorch for DeBERTa
- [ ] `✓ whisper` — Speech transcription
- [ ] `✓ numpy` — Numerical operations
- [ ] `✓ psutil` — Hardware metrics
- [ ] `Database initialised (SQLite WAL)`
- [ ] `NuanceAI backend ready`

---

## Frontend Build

```bash
cd frontend
npm ci              # clean install
npm run build       # Next.js production build
```

- [ ] Build completes without errors
- [ ] `NEXT_PUBLIC_API_URL` set to production API URL in `.env.local` or server env
- [ ] `NEXT_PUBLIC_WS_URL` set to production WebSocket URL (use `wss://` for HTTPS)
- [ ] No `localhost` references in compiled output (search `.next/` if uncertain)

---

## Environment Variables

Backend `.env` (or server environment):

```bash
DEBUG=False
ALLOWED_ORIGINS=["https://your-domain.com"]
WHISPER_MODEL=base          # upgrade to "small" for better accuracy
WHISPER_DEVICE=cpu          # set "cuda" if GPU available with CUDA
DATASET_AUTO_SAVE=True
```

Frontend `.env.local`:

```bash
NEXT_PUBLIC_API_URL=https://your-domain.com
NEXT_PUBLIC_WS_URL=wss://your-domain.com
```

---

## API Smoke Tests

Run these after deployment:

```bash
# Health check
curl https://your-domain.com/health
# Expected: { "status": "ok", "version": "1.1.0", "name": "NuanceAI" }

# Detailed health
curl https://your-domain.com/api/health/detailed
# Expected: { "status": "ok", "components": { ... all present ... } }

# Dashboard stats (empty is fine)
curl https://your-domain.com/api/dashboard/stats
# Expected: { "total_sessions": N, "avg_confidence": N, ... }

# Sessions list
curl https://your-domain.com/api/sessions
# Expected: { "sessions": [...], "count": N }
```

---

## Browser Compatibility

Test in all target browsers before demo:

- [ ] Chrome 120+ (primary — best `getUserMedia` support)
- [ ] Firefox 120+ (works; may show ScriptProcessorNode deprecation warning)
- [ ] Safari 17+ (requires explicit HTTPS; test on actual device)
- [ ] Edge 120+ (Chromium-based; same as Chrome)

---

## User Journey Walkthrough

Complete this checklist in a browser before any demo:

### Landing Page
- [ ] Page loads without layout shift
- [ ] Navigation links (Product, Technology, Research, Enterprise) scroll to correct anchors
- [ ] "Get started" → `/session/new`
- [ ] "View dashboard" → `/dashboard`
- [ ] "See a sample session" → `/dashboard`
- [ ] "Sign in" → `/dashboard`
- [ ] All buttons respond on click

### Dashboard
- [ ] KPI cards load (or show empty state if no sessions)
- [ ] Behavioral Fingerprint renders
- [ ] Session table shows rows (or empty state)
- [ ] Mode filter buttons work (All / Interview / Coaching / Presentation)
- [ ] "View all sessions" → `/history`
- [ ] "New Session" button → `/session/new`
- [ ] Backend offline banner appears if API unreachable

### New Session
- [ ] Backend health check shows "Backend ready" or "Reconnecting..."
- [ ] DeBERTa v3 badge appears when model is loaded
- [ ] All 3 session modes are selectable
- [ ] Empty name → validation error shown
- [ ] Submit with offline backend → user-friendly error
- [ ] Start button disabled while backend checking
- [ ] Successful start → redirects to `/session/{id}`

### Live Session
- [ ] Camera preview appears (if permission granted)
- [ ] Webcam denied → permission error banner (session not blocked)
- [ ] WebSocket connection indicator shows "Live" / "Reconnecting..." / "Offline"
- [ ] Behavioral Fingerprint updates live
- [ ] Metric gauges update live
- [ ] Transcript feed populates (if Whisper running)
- [ ] Insights appear in right panel
- [ ] "End Session" → confirms end → redirects to `/session/{id}/results`
- [ ] Timer increments during session

### Session Results
- [ ] Breadcrumb shows session name (or ID while loading)
- [ ] Loading skeleton shown while fetching
- [ ] Overview tab: behavioral breakdown + key findings
- [ ] Timeline tab: chart renders (or "no timeline data" message)
- [ ] Transcript tab: transcript or "no transcript" message
- [ ] Insights tab: insight cards (or "no insights" message)
- [ ] Report tab: professional report generates
- [ ] Share button → copies URL, shows "Copied!"
- [ ] Export PDF → opens Report tab then browser print dialog

### History
- [ ] Table loads with sessions (or empty state)
- [ ] Search input filters by name
- [ ] Mode filter (All / Interview / Coaching / Presentation) works
- [ ] Sort buttons (Duration, Confidence, Stress) change sort order
- [ ] Arrow indicator shows current sort direction
- [ ] Clear filters button appears when filters active
- [ ] "View" link → `/session/{id}/results`
- [ ] Result count and avg confidence shown in footer

### Settings
- [ ] System Status tab loads on first visit
- [ ] All component rows show (Backend API, Database, WebSocket, Storage, MBA Engine, Whisper, Face Analysis, Voice Analysis, Behavioral Fusion)
- [ ] Hardware gauges render (GPU or "CPU only")
- [ ] Session Activity cards show real values
- [ ] Refresh button polls health endpoint
- [ ] General tab: mode/timeout/export selects work; Save button shows "✓ Saved"
- [ ] Models tab: NLP/Whisper/GPU/FP16 settings save and persist on reload
- [ ] Alerts tab: toggles and threshold selects work; Save persists
- [ ] API tab: shows correct API/WS URLs from env vars
- [ ] Swagger/ReDoc links open correct URLs

---

## Performance

- [ ] Dashboard loads in < 3s on cold backend
- [ ] Live analytics update visible within 1s of speaking
- [ ] History loads 50 sessions in < 2s
- [ ] No memory leak after 30-minute session (check browser Task Manager)
- [ ] Backend RAM stable after 3+ sessions (check `/api/health/detailed`)

---

## Security (minimum before shared access)

- [ ] Deploy behind TLS (HTTPS)
- [ ] Add reverse proxy with HTTP basic auth or VPN access control
- [ ] Set `ALLOWED_ORIGINS` to your domain only
- [ ] Enable nginx rate limiting on `/api/*` and `/ws/*`

**Note:** NuanceAI has no built-in authentication. Anyone with network access can create sessions and view all history. Authentication is a prerequisite for any multi-user or public deployment.

---

## Demo Day Checklist

- [ ] Backend running and `/health` returns `"ok"`
- [ ] Frontend accessible in Chrome on demo device
- [ ] Webcam and microphone tested and working
- [ ] At least one completed session in history (demonstrates data persistence)
- [ ] Settings page shows component statuses
- [ ] All 5 results tabs verified with real session data
- [ ] PDF export tested (browser print dialog works)
- [ ] Backup: have screenshot of results page in case backend is unavailable
