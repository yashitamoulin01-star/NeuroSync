# NeuroSync: Behavioral Intelligence Platform

Real-time multimodal behavioral analysis for structured interviews. Fuses voice, face, and language analysis into evidence-backed behavioral intelligence, updated every 500ms over WebSocket.

---

## What it does

NeuroSync processes three independent signal streams simultaneously during an interview or coaching session:

- **Face (MediaPipe Face Mesh):** Eye contact quality, blink cadence, head pose stability, and facial tension.
- **Voice (LibROSA + custom extractors):** Pitch variance, vocal energy, pause ratio, and speech rate.
- **Language (faster-Whisper transcription + DeBERTa v3 fine-tuned with LoRA):** Confidence markers, hesitation frequency, filler word rate, and communication structure.

These streams are synchronized by a time-windowed fusion layer that produces five composite behavioral dimensions: **Confidence, Engagement, Communication, Consistency, and Composure**, which are delivered to the dashboard in real time.

After the session, a reasoning pipeline produces a structured behavioral report covering evidence ranking, contradiction detection, session arc analysis, and recruiter decision support.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Signal Acquisition (WebSocket)                                  │
│    Video frames (5fps) + Audio chunks (500ms) + PCM stream       │
└──────────┬──────────────────┬──────────────────┬────────────────┘
           │                  │                  │
    ┌──────▼──────┐   ┌───────▼───────┐  ┌───────▼──────┐
    │  Face       │   │  Audio        │  │  Language     │
    │  Analysis   │   │  Analysis     │  │  Analysis     │
    │  MediaPipe  │   │  LibROSA      │  │  Whisper →    │
    │  Face Mesh  │   │  Feature Ext. │  │  DeBERTa v3   │
    └──────┬──────┘   └───────┬───────┘  └───────┬──────┘
           │                  │                  │
           └──────────────────┴──────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  Behavioral Fusion  │
                   │  3s sliding window  │
                   │  Evidence Graph     │
                   │  Reasoning Engine   │
                   └──────────┬──────────┘
                              │
          ┌───────────────────┴──────────────────┐
          │                                      │
   ┌──────▼──────┐                    ┌──────────▼─────────┐
   │  Real-time  │                    │  Post-session       │
   │  Dashboard  │                    │  Behavioral Report  │
   │  (500ms WS) │                    │  + Decision Support │
   └─────────────┘                    └────────────────────┘
```

**Intelligence layers (above inference):**
- **ABME (Adaptive Behavioral Memory Engine):** EMA-based candidate profiles across sessions.
- **CBIP (Continual Behavioral Intelligence Platform):** Cross-candidate validated knowledge, confidence-weighted patterns, coaching effectiveness ranking, organizational intelligence, and OLS forecasting.

Production models are **immutable**. ABME and CBIP operate entirely in the Behavioral Knowledge Layer, meaning no model weights are modified at runtime.

---

## Technology Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.111 + WebSockets |
| ML (NLP) | DeBERTa v3-base, LoRA (r=16 α=32), PEFT, HuggingFace Transformers |
| ML (Audio) | faster-Whisper (CTranslate2), LibROSA, SciPy |
| ML (Vision) | MediaPipe Face Mesh, OpenCV |
| Reasoning | Evidence Graph, Behavioral State Machine, OLS forecasting, Calibration Engine |
| Database | SQLite (WAL mode) with 4 schemas: core, enterprise, behavioral memory, and CBIP |
| Frontend | Next.js 14 App Router, TypeScript, TailwindCSS, Recharts, Framer Motion |
| Auth | JWT-based enterprise authentication, RBAC (8 roles, 50+ permissions) |

---

## Model

DeBERTa v3-base fine-tuned with LoRA on a 74,288-sample behavioral text dataset.

| Metric | Value |
|---|---|
| Architecture | microsoft/deberta-v3-base + LoRA |
| Trainable parameters | 442K / 184M total |
| Training samples | 74,288 verified behavioral text samples |
| Best checkpoint | Step 18,000 |
| Macro-F1 (confidence) | 86.2% |
| Macro-F1 (stress) | 84.8% |
| Macro-F1 (hesitation) | 81.7% |
| Macro-F1 (communication) | 76.9% |
| **Overall macro-F1** | **82.4%** |

Model weights are versioned and audited. Inference is deterministic at a fixed checkpoint. No online learning, no continuous retraining from user data.

---

## Installation

### Requirements
- Python 3.11+
- Node.js 18+
- 8GB RAM recommended (4GB minimum with `tiny` Whisper model)
- CUDA GPU optional (inference runs on CPU)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

### Environment variables

```env
APP_NAME=NeuroSync AI
DEBUG=false
HOST=0.0.0.0
PORT=8000
ALLOWED_ORIGINS=["http://localhost:3000"]
WHISPER_MODEL=base        # tiny | base | small | medium
WHISPER_DEVICE=cpu        # cpu | cuda
```

---

## API

REST + WebSocket. OpenAPI docs at `http://localhost:8000/docs`.

**Core session lifecycle:**
```
POST /api/session          Create a new analysis session
WS   /ws/session/{id}      Connect for real-time streaming
GET  /api/sessions/{id}    Retrieve completed session with timeline
GET  /api/sessions/{id}/narrative   Behavioral narrative + decision support
```

**Intelligence:**
```
GET  /api/sessions/{id}/narrative   Full narrative with arc, contradictions, decision support
GET  /cbip/coaching/{candidate_id}  Evidence-ranked coaching recommendations
GET  /cbip/forecast/{candidate_id}  OLS growth projection with confidence intervals
GET  /cbip/knowledge/stats          Platform knowledge confidence
GET  /cbip/org/{org_id}             Organisation behavioral intelligence
```

**Enterprise:**
```
GET  /api/v1/enterprise/users           User management
GET  /api/v1/enterprise/audit           Immutable audit log
GET  /api/v1/enterprise/compliance      GDPR + compliance reports
GET  /api/v1/ai/models                  Model registry
GET  /api/v1/ai/drift                   Drift detection (PSI/KL)
GET  /api/system/version                Platform version + build metadata
GET  /api/health/detailed               Full component health check
```

---

## Behavioral Intelligence

### Reasoning Pipeline

Every analytical conclusion passes through:

1. **Evidence Extraction:** Per-modality signal extraction with quality weights
2. **Evidence Graph:** Cross-modal consistency check
3. **Contradiction Detection:** Flagged when face, voice, and language conflict
4. **Behavioral Reasoner:** Asymptotic scoring model (approaches limits, never clamps)
5. **Temporal Analysis:** Session arc, trend detection, and peak/trough identification
6. **State Machine:** Behavioral state transitions (settled, stressed, recovering, etc.)
7. **Context Rules:** Mode-specific adjustments (interview vs coaching vs presentation)
8. **Confidence Calibration:** ECE-calibrated reliability tiers (insufficient, low, medium, high)
9. **Decision Trace:** Every conclusion is reconstructable from its inputs

### Behavioral Memory (ABME)

Per-candidate EMA-based profiles accumulate across sessions:
- Confidence baseline, stress reactivity, and communication style
- Session-to-session delta tracking
- Coaching delivery and outcome tracking

### Platform Knowledge (CBIP)

Cross-candidate knowledge layer, updated by a five-level Validation Pyramid:

| Level | Source | Confidence Weight |
|---|---|---|
| L1 | Session observation (auto) | 0.20 |
| L2 | Candidate self-feedback | 0.45 |
| L3 | Recruiter analysis rating | 0.70 |
| L4 | Hiring decision | 0.90 |
| L5 | Long-term performance outcome | 1.00 |

Six behavioral archetypes are tracked as confidence-weighted patterns. Organization intelligence aggregates session signals per org. OLS-based growth forecasting with ±1.5σ confidence intervals.

**Hard constraint:** CBIP accumulates validated observations. It never modifies model weights, never performs online learning, and never adjusts model calibration. Production models evolve only through a governed MLOps pipeline.

---

## Enterprise

- **Multi-tenancy:** Organization isolation with per-org signal aggregation
- **RBAC:** 8 roles, 50+ permissions (super_admin to viewer)
- **Immutable audit log:** SHA-256 chained entries, append-only
- **AI Governance:** Mandatory disclosures, confidence thresholds, and human review triggers
- **GDPR compliance:** Data retention policies and right-to-erasure endpoints
- **API key management:** Scoped programmatic access
- **Feature flags:** Per-tenant capability control

---

## Known Limitations

See `KNOWN_LIMITATIONS.md` for a full honest assessment. Key constraints:

- SQLite is not suitable for horizontal multi-node scaling. A PostgreSQL migration is partially modelled but not implemented.
- `ScriptProcessor` (Web Audio API, deprecated) is used for audio capture. An AudioWorklet replacement is pending.
- WCAG 2.1 AA accessibility compliance is not yet met.
- No HTTPS enforcement in the application layer (requires a reverse proxy).
- Session-level analysis only. Question-level segmentation is a planned future capability.

---

## Structure

```
MBD/
├── backend/
│   ├── main.py                   FastAPI app entry point + lifespan
│   ├── core/                     Config, errors, events, interfaces, registry
│   ├── ml_bridge/                Fusion bridge (face + audio + NLP → fused analytics)
│   ├── models/                   Pydantic schemas + evidence models
│   ├── reasoning/                Full reasoning pipeline (evidence → score → explanation)
│   │   ├── pipeline.py           Orchestrates all 9 reasoning stages
│   │   ├── reasoner.py           Asymptotic behavioral scorer
│   │   ├── extractors.py         Per-modality evidence extraction
│   │   ├── rules/                Context-aware adjustments
│   │   ├── state_machine/        Behavioral state transitions
│   │   ├── calibration/          Confidence calibration (ECE)
│   │   ├── explainability/       Human-readable explanations
│   │   └── audit/                Decision trace (reproducibility)
│   ├── behavioral_memory/        ABME — per-candidate EMA profiles
│   ├── behavioral_knowledge/     CBIP — platform-wide validated knowledge
│   ├── routers/                  REST endpoints + WebSocket handler
│   ├── services/                 Session manager, DB service, metrics
│   ├── orchestrator/             Session lifecycle state machine
│   ├── ai/                       AI platform: model registry, experiment tracking, drift
│   ├── analytics/                Session analytics and aggregation
│   ├── authorization/            RBAC engine
│   └── authentication/           JWT auth + enterprise SSO stubs
├── frontend/
│   ├── src/app/                  Next.js 14 App Router pages
│   ├── src/components/           UI components + layout
│   └── src/lib/                  API client, hooks, utilities
└── ml/
    ├── nlp/                      DeBERTa + LoRA inference
    ├── audio/                    Feature extractors
    └── face/                     MediaPipe wrappers
```

---

## Design Decisions

**Why SQLite instead of PostgreSQL?**
The platform uses SQLite with WAL mode for single-node deployments. All DB code uses stdlib `sqlite3` directly without an ORM. A future PostgreSQL migration is modelled through the `DATABASE_URL` configuration field.

**Why no online learning?**
Production models must be stable, auditable, and reproducible. NeuroSync separates the inference layer (immutable models) from the knowledge layer (CBIP). The knowledge layer accumulates validated observations and never touches model weights. This makes the system's behavior predictable, its claims defensible, and its outputs trustworthy.

**Why evidence-based reasoning instead of a single classifier?**
A single confidence score from one classifier cannot explain itself. The reasoning pipeline extracts evidence per modality, weights by quality, detects contradictions, tracks temporal evolution, and produces a calibrated confidence tier, making every conclusion traceable.

**Why WebSocket instead of polling?**
Polling at 500ms intervals would generate a large number of redundant requests. WebSocket maintains a persistent connection and pushes only when new analytics are available, reducing server load and improving latency.

---

## License

Internal research and development. Not licensed for production deployment or redistribution without explicit authorization.
