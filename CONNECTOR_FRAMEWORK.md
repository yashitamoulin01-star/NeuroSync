# Connector Framework & Universal Interview Integration Platform (UIIP)

> Design document for Phase X.
>
> **Built:** Connector Framework (§2–6), Upload analysis pipeline (§7.3),
> Universal Capture Layer + Input Normalizer + Media Synchronizer (§7.1 server
> side), Meeting lifecycle state machine (§7.2), Multi-person/speaker attribution
> (§7.5), and the Upcoming Interviews → Join Analysis surface.
>
> **Now also built:** ATS connector family (`backend/ats/`, §7.4 — Greenhouse /
> Lever / Workday / Ashby, export reports + sync), RTSP & virtual-camera capture
> adapters (`backend/capture/adapters/` + runner + `/api/capture/*/start`),
> the **Browser Extension** (`extension/`, Chrome MV3 — tab capture → `/ws/session`),
> and the **Desktop Agent** (`desktop-agent/`, Electron — `desktopCapturer` →
> `/ws/session`). Browser/desktop sources stream into the existing live WebSocket
> protocol, so the AI is unchanged.
>
> **Stubbed (structure real, network not wired):** all OAuth token exchanges and
> ATS push/sync calls are deterministic stubs; provider apps must be registered
> and HTTP wired per provider.

## 1. Why this exists

Today a recruiter has to *bring the interview to NeuroSync* — open `/session/new`,
point a camera and microphone at the candidate, and stream. That works for
in-person and screen-share interviews but ignores where most interviews actually
happen: Google Meet, Zoom, Microsoft Teams, Webex.

The UIIP inverts this. The recruiter shouldn't think about *where* the interview
is. The dashboard simply shows their schedule and a single **Join Analysis**
button. NeuroSync picks the right connector, requests permissions, warms the
models, and opens the live dashboard.

```
Authentication → Connectors → (Browser Ext / Desktop Agent) → Meeting Detection
   → Capture → Normalization → Streaming → Behavior Engine → Report → Memory → CBIP → Export
```

The **Connector Framework** is the first layer: a governed, per-organization way
to securely link external meeting providers. Everything downstream consumes a
normalized stream, so the Behavior Engine never learns anything provider-specific.

## 2. Design principles

1. **Pluggable, not hard-coded.** A new provider is one new file that subclasses
   `BaseConnector` and calls `@register`. No existing file changes. The registry,
   service, router, and UI discover it automatically.
2. **Provider logic stays at the edge.** OAuth quirks, capability differences, and
   metadata shapes live inside each connector. The rest of the platform — and
   especially the AI — only ever sees normalized types.
3. **Secrets are never stored in cleartext.** OAuth access/refresh tokens are
   encrypted at rest with authenticated symmetric encryption (Fernet/AES-128-CBC +
   HMAC). The raw token never leaves the service layer or appears in any API
   response.
4. **Least privilege.** Connecting/disconnecting requires `connector:manage`
   (org_admin). Viewing status requires `connector:view`. Tokens are tenant-scoped.
5. **Capability honesty.** Each connector declares exactly what it supports
   (transcript? recording? live stream? participant metadata?). The UI and
   scheduler never offer a capability the provider can't deliver.

## 3. Architecture

```
backend/connectors/
├── models.py          Provider enum, ConnectorStatus, ConnectorCapabilities,
│                      ConnectorRecord (DB-backed), provider→feature matrix
├── crypto.py          TokenCipher — Fernet encrypt/decrypt, graceful degrade
├── base.py            BaseConnector ABC — the pluggability contract
├── registry.py        ConnectorRegistry — @register, lookup, list_available()
├── providers/
│   ├── google_meet.py   Google Workspace (Meet + Calendar)
│   ├── microsoft_teams.py Microsoft 365 (Teams + Graph)
│   ├── zoom.py          Zoom Meetings
│   ├── webex.py         Cisco Webex
│   └── slack.py         Slack huddles / calls
├── schema.py          connectors table DDL + init_connectors_db()
└── service.py         ConnectorService — CRUD, connect, disconnect, refresh,
                       test, sync; the only code that touches plaintext tokens

backend/routers/connectors.py   /api/v1/connectors/* (RBAC-guarded)
```

### Data model

One row per (organization, provider) connection in the shared `nuanceai.db`
(WAL mode, consistent with every other enterprise table):

| Column | Meaning |
| --- | --- |
| `connector_id` | `conn_<uuid8>` |
| `tenant_id`, `org_id` | ownership / isolation |
| `provider` | `google_meet` \| `microsoft_teams` \| `zoom` \| `webex` \| `slack` |
| `name` | admin-chosen display name |
| `status` | `disconnected` \| `connected` \| `expired` \| `error` |
| `access_token_enc` | Fernet-encrypted access token (never returned) |
| `refresh_token_enc` | Fernet-encrypted refresh token (never returned) |
| `token_expires_at` | epoch seconds; drives `expired` status |
| `scopes_json` | granted OAuth scopes |
| `capabilities_json` | resolved capability matrix for this connection |
| `last_sync` | epoch seconds of last successful sync/test |
| `last_error` | last failure message (for the UI) |
| `created_by`, `created_at`, `updated_at` | audit fields |

`UNIQUE(org_id, provider)` — one live connection per provider per org.

### The pluggability contract (`BaseConnector`)

```python
class BaseConnector(ABC):
    provider: ClassVar[ConnectorProvider]     # registry key
    display_name: ClassVar[str]
    capabilities: ClassVar[ConnectorCapabilities]
    oauth: ClassVar[OAuthConfig]              # authorize/token URLs, scopes

    def authorize_url(self, redirect_uri, state) -> str: ...
    async def exchange_code(self, code, redirect_uri) -> TokenBundle: ...
    async def refresh(self, refresh_token) -> TokenBundle: ...
    async def test(self, access_token) -> ConnectorTestResult: ...
    async def list_upcoming_meetings(self, access_token) -> list[MeetingRef]: ...
```

`TokenBundle`, `MeetingRef`, `ConnectorTestResult`, and `ConnectorCapabilities`
are normalized types. A connector translates the provider's API into these and
nothing else escapes the edge.

> **First-slice note:** `exchange_code`, `refresh`, `test`, and
> `list_upcoming_meetings` ship as deterministic stubs that model the real flow
> (token shape, expiry, capability gating) without making live network calls.
> Wiring real HTTP is a per-provider change inside each file — no framework change.

## 4. OAuth 2.0 flow

Authorization Code with refresh tokens, standard across all five providers:

```
Admin clicks "Connect"  →  POST /connectors/{provider}/connect
        →  service builds authorize_url(state)  →  browser redirects to provider
Provider consent screen  →  redirect back with ?code=...&state=...
        →  GET /connectors/oauth/callback  →  service.exchange_code(code)
        →  encrypt(access, refresh)  →  store  →  status=connected
```

- `state` is a signed, short-lived value binding the callback to the initiating
  org + connector, preventing CSRF and cross-org token injection.
- Refresh runs lazily (on `expired`) and on demand (admin "Refresh" button).
- Disconnect deletes encrypted tokens immediately and best-effort revokes them
  upstream.

## 5. Security model

- **At rest:** tokens encrypted with `TokenCipher` (Fernet). The key derives from
  `settings.CONNECTOR_ENCRYPTION_KEY` (set per deployment; never committed). If
  `cryptography` is unavailable, the service refuses to store tokens rather than
  persisting cleartext, and logs loudly — degrade safe, never degrade silent.
- **In transit:** all provider calls are HTTPS; the platform itself sits behind
  the existing HSTS/CSP hardening middleware.
- **In responses:** the API surface returns *status and metadata only*. There is
  no endpoint that returns a decrypted token. `to_public_dict()` omits every
  `*_enc` column.
- **Isolation:** every query is `tenant_id`-scoped; one org can never read or act
  on another org's connector.
- **Audit:** connect / disconnect / refresh emit audit events via the existing
  audit pipeline (resource_type=`connector`).

## 6. Connector Management UI

Under **Enterprise Settings → Connectors**. For each available provider the admin
can: **Connect**, **Disconnect**, **Refresh**, **Test Connection**, **View
Permissions** (granted scopes), and **View Last Sync**. Connected providers show
their capability badges (Meetings · Transcript · Recording · Live · Participants)
so the recruiter knows what "Join Analysis" will be able to do.

## 7. How the rest of Phase X plugs in (design-only)

### 7.1 Desktop Agent

A separate, lightweight native app (Tauri/Electron) — **not** part of this repo —
that behaves like OBS, never like an injector.

- **Captures** a user-selected application window, the microphone, and system
  audio *where the OS permits*, using only OS capture APIs (macOS
  ScreenCaptureKit, Windows Graphics Capture / WASAPI loopback). It **never**
  injects into or modifies another process.
- **Permissions** are explicit and OS-mediated; the agent shows a "Start
  Analysis" overlay and cannot capture without the user's grant.
- **Transport:** exposes a local, authenticated `wss://127.0.0.1` stream speaking
  the *same* frame/audio protocol as `ws_session.py`, so the existing Behavior
  Engine consumes it unchanged.
- **Meeting detection:** recognizes the foreground meeting app (Meet/Zoom/Teams/
  Webex) and reports it so the dashboard can label the session.

The agent is a *capture source*, equivalent to the browser camera. It produces
the same normalized stream a connector or upload does.

### 7.2 Meeting lifecycle state machine

A formal orchestrator state machine the connectors, agent, and dashboard drive:

```
Scheduled → Waiting → Joining → Permission Check → Media Validation → Warm-up
   → Ready → Recording → Live Analysis → (Paused ↔ Resume) → Meeting End
   → Processing → Report Generation → Behavioral Memory Update → CBIP Update → Export
```

This extends the existing `orchestrator/lifecycle.py` (CREATED→STREAMING→…→
COMPLETED) with the pre-join and post-process states. Reconnect/"Keep Recording"
maps to: Local Encryption → Reconnect → Upload → Resume Analysis.

### 7.3 Uploaded analysis pipeline

Batch upload of MP4/MOV/AVI/MKV/WebM/MP3/WAV/M4A with a processing queue, resume,
and **three separate pipelines** (video / audio / transcript) feeding the *same*
fusion + reasoning path so an uploaded report is identical to a live one. No
OAuth dependency — shippable independently of connectors.

### 7.4 ATS connectors

ATS is just another connector *family* with an export direction. Interview
results export back into the ATS; candidate records synchronize. Critically, **no
ATS-specific logic lives inside the AI** — ATS mapping is an edge concern, exactly
like meeting providers.

### 7.5 Multi-person attribution

Panel interviews (N interviewers + 1 candidate) require speaker attribution so
the report reads `Candidate / Interviewer 1/2/3`, not `Person A/B`. This is a
capture/normalization-layer feature (diarization + role assignment) that labels
the stream before it reaches the Behavior Engine — again, the AI stays agnostic.

## 8. Adding a new connector (the whole checklist)

1. Create `backend/connectors/providers/<name>.py`.
2. Subclass `BaseConnector`, set `provider`/`display_name`/`capabilities`/`oauth`.
3. Decorate the class with `@register`.
4. Import it in `providers/__init__.py` so it loads.

That's it. The DB, service, router, RBAC, and UI require no changes.
