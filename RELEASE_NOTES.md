# NuanceAI — Release Notes

Version **1.1.0** · Release Candidate 1  
Date: 2026-06-20  
Platform: NeuroSync Platform · MBA Engine

---

## Summary

This release completes the production hardening phase and introduces the full session lifecycle — from live multimodal capture to persistent behavioral reporting. All pages use real API data; no mock data remains in production paths.

---

## What's New in 1.1.0

### Backend

- **SQLite persistence** — all completed sessions, timeline frames, and behavioral insights are stored in `data/nuanceai.db` (WAL mode) and survive backend restarts.
- **Session history API** — `GET /api/sessions`, `GET /api/sessions/{id}`, `GET /api/dashboard/stats`, `GET /api/health/detailed`.
- **Detailed health endpoint** — reports GPU VRAM usage, CPU %, RAM, uptime, all component statuses (DeBERTa, Whisper, Face, Classifiers, Fusion, Database, Storage).
- **Accurate component status** — Whisper and Face Engine statuses now reflect whether the underlying dependencies (`whisper`/`faster-whisper`, `cv2`/`mediapipe`) are actually installed.
- **Background stale-session cleanup** — sessions older than 1 hour are evicted every 10 minutes via asyncio task.
- **Request ID middleware** — every HTTP response carries an `X-Request-ID` header for log correlation.
- **Startup validation** — dependency check and model artifact scan logged at every startup.
- **Whisper pre-warm** — shared Whisper singleton loaded at startup to eliminate first-session cold start.

### Frontend

- **Settings persistence** — General, AI Models, and Alerts tabs now save to `localStorage` and restore on page load. Save buttons provide immediate visual confirmation.
- **Accurate API/WS URLs** — Settings > API tab now reads URLs from `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` environment variables instead of hardcoded strings.
- **History table** — removed duplicate Date column (date already shown in the Session name cell); column count corrected across skeleton/empty states.
- **TopBar active state** — Dashboard link now uses exact path match (`/dashboard` only), consistent with Sidebar behavior.
- **Font loading** — added `crossOrigin="anonymous"` to `fonts.googleapis.com` preconnect for correct CORS prefetch.
- **Dead code removed** — `src/lib/mockData.ts` deleted (was never imported after Phase 6).
- **Console output** — removed `console.warn` from WebSocket message handler.

### RC Audit Fixes

| Area | Issue | Fix |
|------|-------|-----|
| Settings | Save buttons had no effect | `localStorage` persistence + confirmation state |
| Settings | API/WS URLs hardcoded | Use `NEXT_PUBLIC_*` env vars |
| Settings | Swagger links hardcoded to localhost | Dynamic `${API_BASE}/docs` |
| History | Duplicate "Date" column in table | Removed |
| Backend | Whisper status always "idle" unless sessions active | Check if whisper package importable |
| Backend | Face status always hardcoded "online" | Check if cv2 + mediapipe importable |
| Frontend | `console.warn` in WebSocket hook | Removed |
| Frontend | `mockData.ts` dead file | Deleted |
| Layout | Missing `crossOrigin` on Google Fonts preconnect | Added |
| TopBar | Dashboard `startsWith` vs exact match inconsistency | Fixed to exact match |

---

## API Changelog

No breaking changes. New endpoints added:

- `GET /api/sessions` — paginated session history
- `GET /api/sessions/{id}` — session detail + timeline frames + parsed insights
- `GET /api/dashboard/stats` — aggregate KPIs
- `GET /api/health/detailed` — full system status

---

## Upgrade Path

No migration required. If upgrading from a previous installation:

1. Backend restarts automatically create the SQLite schema (`data/nuanceai.db`).
2. Existing session data in memory is not affected; only completed sessions are persisted.
3. Frontend: clear browser `localStorage` key `nuanceai_settings` if previous versions left stale state.

---

## Known Issues in This Release

See `KNOWN_LIMITATIONS.md` for the complete list. Key items:

- No authentication layer — deploy behind VPN or reverse proxy for any shared access.
- `getUserMedia` requires HTTPS in production (works on localhost).
- PDF export uses `window.print()` — browser-native styling.
- No WebSocket frame rate limiting server-side.
