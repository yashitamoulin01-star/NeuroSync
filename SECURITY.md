# Security Policy — NeuroSync 1.2.0-rc1

## Authentication

Enterprise platform endpoints (`/api/v1/*`) use Bearer token authentication.

**Token format:** `secrets.token_hex(32)` — 256-bit cryptographically random, stored in `auth_sessions` table.

**Password hashing:** PBKDF2-SHA256 with 260,000 iterations and a per-user 16-byte random salt. Verification uses `hmac.compare_digest` for timing-safe comparison.

**Session lifetime:** Access tokens expire after 1 hour. Sessions are revocable individually or in bulk (on account suspension/deletion). Revoked tokens are rejected at every request.

**API keys:** Long-lived scoped tokens for programmatic access. Validated via `api_key_service.validate()` alongside session tokens.

**Currently unauthenticated (documented limitation):** Core session pipeline (`/api/*` prefix), behavioral memory (`/behavior/*`), behavioral knowledge (`/cbip/*`), system probes (`/system/*`), and AI platform read endpoints (`/ai/*`). Deployment and rollback endpoints (`POST /ai/models/deploy`, `POST /ai/models/rollback`) require `PLATFORM_ADMIN` permission. See [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) for scope and planned remediation.

## Authorization

Role-Based Access Control (RBAC) with 8 roles and 50+ granular permissions.

Roles (ascending privilege): `viewer`, `interviewer`, `recruiter`, `recruiter_manager`, `org_admin`, `compliance_officer`, `platform_admin`, `system`.

All enterprise endpoints use `require_permission(Permission.X)` as a FastAPI `Depends` — authorization is server-side and cannot be bypassed by modifying requests. Tenant isolation is enforced in every enterprise SQL query via `WHERE tenant_id = ?`.

## Rate Limiting

100 requests per 60-second sliding window per source IP. Implemented in-process (`_rate_limit_records` defaultdict). Bounded to 10,000 unique IP entries with lazy eviction on overflow.

Returns HTTP 429 with a log entry on breach. Rate limit state resets on process restart — not suitable for distributed deployments (see RC2 backlog: Redis-backed rate limiting).

## Security Headers

Every API response includes:

| Header | Value |
|--------|-------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `X-XSS-Protection` | `0` (disables legacy IE filter) |
| `Content-Security-Policy` | `default-src 'self'; frame-ancestors 'none';` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=()` |
| `X-Request-ID` | Per-request correlation ID |

`Server` and `X-Powered-By` headers are stripped from all responses.

Note: these headers are set on the FastAPI backend (port 8000). The Next.js frontend (port 3000) should have its own `next.config.js` header configuration for production deployment behind a single origin.

## Input Validation

All request bodies are validated by Pydantic v2 with strict field types. The security middleware additionally checks:

- **Path traversal:** `../`, `%2e%2e`, URL-encoded variants — rejected with HTTP 400.
- **Injection patterns:** XSS (`<script>`), SQLi (`UNION SELECT`), command injection (`exec(`), JS injection (`javascript:`), eval injection — scanned in query parameters, rejected with HTTP 400.
- **Query parameter length:** 1,024 character limit per value.
- **Request body size:** 100 MB hard cap via `Content-Length` check.
- **Path length:** 512 character maximum.

All database queries use parameterized statements (`?` placeholders). No string interpolation in SQL.

## File Uploads

Validated via `validate_file_upload()` in `backend/security/hardening.py`:

- **Extension allowlist:** `.wav`, `.mp3`, `.mp4`, `.webm`, `.ogg`, `.json`, `.csv`, `.txt`
- **MIME type allowlist:** Corresponding audio/video/text MIME types only
- **Size limit:** 100 MB (shared with body size limit)
- **Filename:** Processed via `pathlib.Path(filename).suffix` — no directory component trust

## Secret Management

- No secrets committed to the repository. `.env` is in `.gitignore`.
- `.env.example` contains only placeholder/documentation values.
- All runtime configuration via environment variables (`pydantic_settings.BaseSettings`).
- No hardcoded credentials, API keys, tokens, or passwords in source code.

## Logging

- Structured JSON logging with per-request correlation IDs.
- Authentication failures logged at WARNING level with IP address.
- Security events (path traversal, injection attempts, rate limit breaches) logged at WARNING level.
- No passwords, tokens, or user credentials appear in any log output.
- Log records include `timestamp`, `level`, `name`, `message`, `correlation_id`.

## Error Handling

- All domain errors handled by `NeuroSyncError` hierarchy → structured JSON responses.
- HTTP 500 handler returns `{"detail": "Internal Server Error"}` — no stack traces, SQL errors, or filesystem paths exposed to clients.
- Unhandled exceptions caught in middleware and returned as generic 500.

## CORS

Origins restricted to `ALLOWED_ORIGINS` (default: `localhost:3000`, `localhost:3001`). Configurable via `ALLOWED_ORIGINS` environment variable. Credentials allowed (`allow_credentials=True`) for session cookie support.

## Responsible Disclosure

This is an RC1 demonstration platform. If you identify a security issue, please report it by opening a private issue or emailing the engineering team directly rather than disclosing publicly.

## Known Limitations (RC2 Targets)

1. Core session pipeline (`/api/*`) is unauthenticated — any network-accessible client can create, read, and end sessions.
2. Behavioral memory and knowledge endpoints (`/behavior/*`, `/cbip/*`) are unauthenticated and lack tenant isolation.
3. System and AI read endpoints (`/system/*`, `/ai/*` GET) are unauthenticated — expose operational metadata.
4. Rate limiting is in-process — state resets on restart, not suitable for multi-process deployment.
5. Single SQLite database — not suitable for concurrent multi-process deployment.
6. No CSRF protection (mitigated by CORS + SameSite cookie policy, but not formally enforced).
7. WebSocket connections (`/ws/*`) are unauthenticated.

## Supported Versions

| Version | Status |
|---------|--------|
| 1.2.0-rc1 | Active (current) |
| 1.1.0 | Superseded |
