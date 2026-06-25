# NeuroSync — Architecture

Version 1.2.0-rc1 · NeuroSync Platform

---

## System Overview

NeuroSync is a self-hosted, real-time behavioral intelligence platform. It captures webcam video and microphone audio in the browser, streams them to a local FastAPI backend via WebSocket, and returns fused behavioral scores every 500ms.

```
┌─────────────────────────────────────────────────────┐
│                  Browser (Next.js 14)               │
│                                                     │
│  Landing  Dashboard  History  Results  Settings     │
│     └──────────────────────────────────┘            │
│                    AppShell                         │
│              Sidebar │ TopBar                       │
│                                                     │
│  Live Session (/session/[id])                       │
│   ├── getUserMedia → Video (5fps JPEG) ────────┐   │
│   │                                            │   │
│   ├── Web Audio API → PCM 16kHz chunks ────────┤   │
│   │                                            ▼   │
│   └── useWebSocket ─── ws://...:8000/ws/session/{id}
│                                                     │
│  api.ts (fetchWithRetry + AbortSignal.timeout)      │
│   └── REST → http://...:8000/api/*                  │
└─────────────────────────────────────────────────────┘
                         │ WebSocket (JSON)
                         │ REST (JSON)
                         ▼
┌─────────────────────────────────────────────────────┐
│               FastAPI Backend (Python)              │
│                                                     │
│  Routers:                                           │
│   ├── /ws/session/{id}  (ws_session.py)             │
│   ├── /api/session      (session.py)                │
│   ├── /api/analytics    (analytics.py)              │
│   ├── /api/sessions     (sessions_history.py)       │
│   ├── /api/dashboard    (sessions_history.py)       │
│   ├── /api/health       (sessions_history.py)       │
│   └── /api/training     (training.py)               │
│                                                     │
│  Session Manager (session_manager.py)               │
│   └── ActiveSession (per-session in-memory state)   │
│        ├── FaceAnalysisService                      │
│        ├── AudioAnalysisService                     │
│        ├── NLPAnalysisService                       │
│        └── FusionBridge                             │
│                                                     │
│  NeuroSync Platform (ml/)                           │
│   ├── MBA Engine (ml/nlp/behavioral_nlp.py)         │
│   │    └── DeBERTa v3-base + LoRA (442K params)     │
│   ├── Whisper (ml/nlp/transcriber.py) [singleton]   │
│   ├── Face Analysis (ml/face/)                      │
│   │    └── MediaPipe Face Mesh (468 landmarks)      │
│   ├── Voice Analysis (ml/audio/)                    │
│   │    └── ZCR, pitch, RMS, pause ratio             │
│   └── Behavioral Fusion (ml/fusion/)                │
│        └── MLP meta-learner over 3s sliding window  │
│                                                     │
│  SQLite WAL (data/nuanceai.db)                      │
│   ├── sessions (one row per completed session)      │
│   ├── session_frames (sampled every ~2s)            │
│   └── session_insights                              │
└─────────────────────────────────────────────────────┘
```

---

## Frontend

### Stack

| Technology | Version | Role |
|------------|---------|------|
| Next.js | 14 (App Router) | Framework |
| TypeScript | 5 | Type safety |
| Tailwind CSS | 3 | Styling |
| Lucide React | latest | Icons |
| clsx + tailwind-merge | latest | Class composition |

### Directory Layout

```
frontend/src/
├── app/
│   ├── page.tsx                        # Landing page (public)
│   ├── layout.tsx                      # Root layout — metadata, fonts
│   ├── globals.css                     # Tailwind base + design tokens
│   ├── login/page.tsx                  # Enterprise auth login
│   ├── dashboard/page.tsx              # KPI dashboard
│   ├── history/page.tsx                # Session history table
│   ├── settings/page.tsx               # System status + config
│   ├── session/
│   │   ├── new/page.tsx                # Session config + backend health check
│   │   ├── [id]/page.tsx               # Live WebSocket session + Reasoning Inspector
│   │   └── [id]/results/page.tsx       # Post-session analysis + report
│   ├── workspace/
│   │   ├── page.tsx                    # Recruiter workspace (candidate list, tiers)
│   │   └── [id]/page.tsx               # Candidate detail assessment
│   ├── governance/page.tsx             # Audit log, compliance, reports, API keys
│   ├── operations/page.tsx             # Platform health, alerts, resource gauges
│   ├── ai-platform/page.tsx            # Model registry, experiments, drift monitor
│   ├── growth/page.tsx                 # ABME growth tracking + behavioral forecasting
│   ├── knowledge/page.tsx              # CBIP knowledge base + pattern catalog
│   ├── benchmarks/page.tsx             # Inference latency, model F1, system metrics
│   ├── architecture/page.tsx           # Interactive component explorer (public)
│   └── faq/page.tsx                    # Technical FAQ (public)
├── components/
│   ├── layout/   AppShell, Sidebar (collapsible NavSection), TopBar
│   ├── charts/   BehavioralFingerprint, TimelineChart, Sparkline, MetricRing
│   ├── dashboard/ KPICard, SessionTable
│   ├── session/
│   │   ├── InsightCard, MetricGauge, TranscriptFeed
│   │   ├── ExplainabilityPanel    # 9-stage reasoning pipeline display
│   │   ├── ModelTransparencyCard  # DeBERTa model specs + per-task F1
│   │   ├── NarrativeSection       # Behavioral arc, contradictions, decision support
│   │   └── RecruiterValidationPanel  # L3/L4 CBIP recruiter annotation
│   ├── workspace/
│   │   └── EvidenceTimeline       # Per-insight evidence display
│   └── ui/       Button, Badge, Card, Spinner, ConfidenceBar, ConfidenceChip
└── lib/
    ├── api.ts          # REST + WS URLs; fetchWithRetry; all API surface
    ├── auth.ts         # Enterprise auth context (JWT, useAuth hook)
    ├── types.ts        # Shared TypeScript interfaces
    ├── utils.ts        # cn, formatDuration, formatScore, geometry helpers
    ├── demoData.ts     # DEMO_SESSION synthetic fixture
    └── hooks/
        └── useWebSocket.ts   # WebSocket lifecycle + exponential backoff
```

### Key Design Decisions

**`fetchWithRetry`** — all API calls use `AbortSignal.timeout()` (10s default) with automatic retries on 408/429/5xx responses. Exponential backoff: 500ms, 1s.

**`useWebSocket`** — manages WS lifecycle. On unexpected close: up to 10 retries with backoff capped at 30s. `intentional.current` ref prevents reconnect when user ends session.

**Media capture** — webcam: canvas JPEG at 5fps (200ms interval), 320×240, quality 0.7. Audio: `ScriptProcessorNode` → Float32 → Int16 PCM → base64 at 500ms intervals.

**No global state manager** — component-local `useState` + `useCallback` + `useEffect`. Data from API is normalized at the component boundary (see `normalizeRows` in dashboard).

---

## Backend

### Stack

| Technology | Version | Role |
|------------|---------|------|
| FastAPI | 0.115 | HTTP + WebSocket server |
| Pydantic v2 | latest | Data validation + serialization |
| SQLite (WAL) | 3.x | Session persistence |
| PyTorch (CPU) | 2.3.0 | DeBERTa inference |
| faster-whisper / whisper | latest | Speech-to-text |
| MediaPipe | latest | Face mesh |
| psutil | latest | Hardware metrics |

### Session Lifecycle

```
POST /api/session
  → SessionManager.create_session()
  → ActiveSession.__post_init__() {
      FaceAnalysisService()
      AudioAnalysisService() [shares Whisper singleton]
      NLPAnalysisService()
      FusionBridge()
      db.create_session_record()
    }
  → returns { session_id, status }

WS /ws/session/{id}
  → Per message loop:
      "frame"  → face_service.process_frame_b64() [3s timeout]
      "audio"  → audio_service.process_audio_chunk() [4s timeout]
               → audio_service.process_audio_for_transcript() [10s timeout]
               → nlp_service.analyze_transcript_chunk()
      "ping"   → "pong"
      "end"    → session_manager.end_session()
  → Every 500ms: fusion_bridge.get_fused() → "analytics_update"

DELETE /api/session/{id}
  → session_manager.end_session()
  → db.finalize_session()
  → returns SessionSummary
```

### Behavioral Fusion

```
Face (30fps → 5fps effective)   ─┐
Audio (500ms PCM chunks)        ─┤─→ FusionBridge.get_fused()
NLP (Whisper → DeBERTa)         ─┘       │
                                          │
                              3s sliding window
                                          │
                              MultimodalSynchronizer
                                          │
                              FusedAnalytics {
                                overall_confidence,
                                communication_quality,
                                engagement_score,
                                stress_level,
                                behavioral_consistency,
                                insights[],
                                ...
                              }
```

### Database Schema

```sql
sessions (
  id TEXT PK, name TEXT, mode TEXT,
  started_at REAL, ended_at REAL, duration REAL,
  avg_confidence REAL, avg_stress REAL, avg_engagement REAL,
  avg_communication REAL, avg_consistency REAL, avg_eye_contact REAL,
  avg_speaking_pace REAL, total_filler_words INT, total_words INT,
  transcript TEXT, insights_json TEXT
)

session_frames (
  id INT PK AUTOINCREMENT, session_id TEXT → sessions(id),
  ts REAL, confidence REAL, stress REAL, engagement REAL,
  communication REAL, consistency REAL, eye_contact REAL,
  is_speaking INT
)
```

Frames are sampled every 4th analytics push (~2s cadence) to avoid excessive write load.

---

## Intelligence Layer

### Reasoning Pipeline (9 stages)

Every behavioral conclusion passes through:

```
1. Signal extraction    — per-modality raw features
2. Quality assessment   — reliability tier assignment (insufficient/low/medium/high)
3. Evidence graph       — weighted signal aggregation by source quality
4. Contradiction check  — cross-modal conflict detection
5. Behavioral state     — current state classification
6. Confidence scoring   — DeBERTa + calibration → calibrated score
7. Arc assessment       — trajectory over session (improving/stable/declining)
8. Narrative generation — evidence-grounded text explanation
9. Decision support     — structured recruiter guidance
```

### ABME — Adaptive Behavioral Memory Engine

Per-candidate behavioral profiles maintained via Exponential Moving Average:

```
α = 0.15 (configurable via EMA_ALPHA constant in behavioral_memory/engine.py)
current_profile = α × new_session + (1 - α) × prior_profile

Tracks: baseline, growth_rate, consistency, session_count
Supports: cross-session behavioral forecasting (OLS regression with CI)
Storage: SQLite behavioral_memory table via db_service
```

Endpoints: `GET /api/behavior/{candidate_id}`, `POST /api/behavior/{candidate_id}/update`

### CBIP — Continual Behavioral Intelligence Platform

Organizational behavioral knowledge classified by evidence quality:

| Level | Source | Weight |
|---|---|---|
| L1 | Automated detection | 0.20 |
| L2 | Multi-session validated | 0.40 |
| L3 | Recruiter annotated | 0.70 |
| L4 | Cross-role validated | 0.85 |
| L5 | Expert consensus | 1.00 |

Pattern types: Cognitive Agility, Leadership, Communication, Stress Resilience, Growth Mindset, Collaborative Intelligence

Endpoints: `GET /api/cbip/patterns`, `GET /api/cbip/stats`, `POST /api/cbip/validate`

---

## Enterprise Platform

### Backend Routers

| Router | Prefix | Role |
|--------|--------|------|
| `enterprise_auth.py` | `/api/v1/auth` | JWT login, token refresh, session management |
| `enterprise_governance.py` | `/api/v1/governance` | Audit log, compliance, reports, feature flags, API keys |
| `enterprise_platform.py` | `/api/v1/enterprise` | Multi-tenancy, RBAC, organizations, billing |
| `ai_platform.py` | `/api/v1/ai` | Model registry, experiments, ECE calibration, drift |
| `observability.py` | `/api/v1/observability` | Health checks, Prometheus metrics |
| `system.py` | `/api/v1/system` | Settings, admin operations |

### RBAC

8 role levels (highest to lowest): `super_admin`, `enterprise_admin`, `org_admin`, `recruiter_lead`, `recruiter`, `analyst`, `viewer`, `candidate`

50+ permissions across domains: `sessions:*`, `candidates:*`, `reports:*`, `admin:*`, `governance:*`, `ai:*`

### Audit Log

Every governance-relevant action is logged with: `timestamp, actor_id, actor_role, action, resource, result, ip, session_context`. Log is append-only, immutable at the application layer.

---

## ML Models

### DeBERTa v3-base (MBA Engine)

- Base: `microsoft/deberta-v3-base` (184M params)
- Adaptation: LoRA r=16, α=32 on {query, key, value} projections → 442K trainable params (0.24%)
- Tasks: confidence (3-class), stress (3-class), hesitation (3-class), communication (4-class)
- Training data: 74,288 behavioral text samples
- Best checkpoint: Step 18,000 — macro-F1 82.4%

### Whisper

- Model: `base` by default (configurable via `WHISPER_MODEL`)
- Loaded as a singleton at startup; shared across all sessions
- Runs in ThreadPoolExecutor with 10s timeout per chunk

### Face Analysis

- MediaPipe Face Mesh (468 landmarks at 30fps → sampled at 5fps)
- Outputs: eye contact score, blink rate, head stability, facial tension, expression label

### Voice Analysis

- ZCR-based pitch estimation, RMS energy, pause ratio, vocal stability
- Filler word detection (keyword list) as fallback when Whisper not available

### Behavioral Fusion

- MLP meta-learner (`models/fusion/best_fusion.pt`) trained on behavioral sequences
- 3-second sliding window aligns face, audio, and NLP signals by timestamp
- Falls back to weighted average if model file absent

---

## Configuration

All configuration via environment variables or `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `WHISPER_MODEL` | `base` | Whisper model size |
| `WHISPER_DEVICE` | `cpu` | Inference device |
| `FACE_DETECTION_CONFIDENCE` | `0.7` | MediaPipe threshold |
| `WINDOW_SIZE_SECONDS` | `3.0` | Fusion window |
| `DATASET_AUTO_SAVE` | `True` | Save raw media to disk |
| `DEBERTA_MODEL` | `microsoft/deberta-v3-base` | HuggingFace model ID |
| `ALLOWED_ORIGINS` | `localhost:3000, 3001` | CORS origins |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend API base |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | Frontend WS base |

---

## Deployment

### Development (localhost)

```bash
# Backend
cd D:\MBD
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm run dev    # → http://localhost:3000
```

### Production (single server)

```bash
# Backend (production)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1

# Frontend (static export)
npm run build
npm start      # or serve via nginx
```

**Requirements for production:**
- TLS termination (HTTPS) — required for `getUserMedia` outside localhost
- Reverse proxy (nginx/Caddy) — handle static assets, TLS, rate limiting
- One worker per server (shared in-memory session state not distributed-safe)
- `data/` directory writable — SQLite + media recording

---

## Security Model

This platform is designed for **self-hosted enterprise deployment** with network-level access control.

| Concern | Current Status | Notes |
|---------|---------------|-------|
| Authentication | JWT (enterprise_auth.py) | Login, token refresh, session management |
| Authorization | RBAC (8 roles, 50+ permissions) | Per-route permission checks |
| Rate limiting | None | Add nginx + `slowapi` for production |
| Input validation | Pydantic on all routes | All request bodies validated |
| XSS | No user-generated HTML rendered | Safe by design |
| SQL injection | SQLite parameterized queries | Safe |
| CORS | Controlled allowlist | Configure for production domain |
| Data egress | All data stays on server | By design — self-hosted |
| Audit trail | Immutable append-only log | All governance actions recorded |
