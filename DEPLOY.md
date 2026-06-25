# Deploying NeuroSync

Two pieces deploy to two places:

| Piece | Where | Why |
| --- | --- | --- |
| **Frontend** (`frontend/`, Next.js) | **Vercel** | Static/SSR app, perfect fit |
| **Backend** (`backend/`, FastAPI + ML) | **Render / Railway / Fly / VM** | Long-running, stateful, holds WebSockets + loads torch/MediaPipe/Whisper into memory — cannot run on Vercel serverless |

You do **not** need Supabase. The backend uses SQLite on a persistent disk (see below). Move to Postgres/Supabase only if you host the backend somewhere with no persistent filesystem — that requires rewriting `db_service.py` / `enterprise_db.py` and is not needed for a demo.

---

## 1. Backend → Render (Docker + persistent disk)

The repo ships a working `Dockerfile` and `render.yaml`.

1. Push this repo to GitHub (done).
2. Render → **New** → **Blueprint** → select the repo. It reads `render.yaml`.
3. After it provisions, set these in the service's **Environment**:
   - `ALLOWED_ORIGINS` → your Vercel URL as a JSON array, e.g. `["https://your-app.vercel.app"]`
   - (`CONNECTOR_ENCRYPTION_KEY` is auto-generated; `DATASET_DIR`, `WHISPER_DEVICE`, `INFERENCE_DEVICE` are preset.)
4. Deploy. First boot takes a minute (installing torch). Health check: `GET /health`.
5. Note the public URL, e.g. `https://neurosync-backend.onrender.com`.

**Plan/memory:** torch + mediapipe + whisper need real RAM — use at least the **Standard** plan (free/512 MB will OOM). CPU-only is fine (`INFERENCE_DEVICE=cpu`, the default).

**Data persistence:** the `render.yaml` mounts a 1 GB disk at `/app/data`, so the SQLite DB and uploads survive restarts. Don't change `CONNECTOR_ENCRYPTION_KEY` after connecting integrations or stored OAuth tokens become unreadable.

### Railway alternative
Railway also works: New Project → Deploy from repo → it builds the `Dockerfile`. Add a **Volume** mounted at `/app/data`, and set the same env vars. Railway injects `$PORT`, which the Dockerfile already honors.

---

## 2. Frontend → Vercel

1. Vercel → **New Project** → import the repo → set **Root Directory = `frontend`**.
2. Add environment variables:
   - `NEXT_PUBLIC_API_URL` = `https://neurosync-backend.onrender.com`
   - `NEXT_PUBLIC_WS_URL`  = `wss://neurosync-backend.onrender.com`
3. Deploy. Vercel auto-detects Next.js.

> The frontend calls the backend by absolute URL (CORS), so make sure the backend's
> `ALLOWED_ORIGINS` includes your Vercel domain (step 1.3). WebSockets use `wss://`
> against the same backend host.

---

## 3. Verify

- `https://<backend>/health` → `{"status":"ok",...}`
- Open the Vercel app → Dashboard should load live data (no "backend unavailable" banner).
- Start a session → the live dashboard should stream analytics.

---

## Notes & limitations

- **Trained model weights** (`*.pt`, `*.pkl`) are stored in **Git LFS** (see
  `.gitattributes`). To avoid burning GitHub's free LFS bandwidth (1 GB/month) on
  every cloud build, `render.yaml` sets `GIT_LFS_SKIP_SMUDGE=1`, so the build pulls
  only LFS pointers and the app runs in **rule-based fallback** — fine for a demo.
  To deploy the **real DeBERTa model**: remove `GIT_LFS_SKIP_SMUDGE` (and expect to
  need a paid LFS data pack), or host the weights in object storage / a GitHub
  Release and fetch them at startup.
- **Browser extension / desktop agent** are separate clients; they point at the
  backend URL via their own `config.js`. Update those before distributing.
- **OAuth / ATS / calendar** are stubbed until you register provider apps and set
  real client IDs/secrets/redirect URIs.
