"""
Enterprise SQLite schema — all Phase 7 tables.

Extends the existing nuanceai.db with enterprise governance tables.
All tables are created with IF NOT EXISTS so this is safe to call at startup.

Schema groups:
  Identity        — tenants, organizations, departments, teams, users, auth_sessions
  RBAC            — role_assignments, permission_overrides
  Audit           — audit_events (append-only)
  Compliance      — retention_policies, consent_records, data_requests
  Templates       — interview_templates, template_versions
  Reports         — report_versions (immutable snapshots)
  API             — api_keys, api_key_usage
  Flags           — feature_flags, flag_overrides
  Billing         — subscription_plans, usage_records, quota_limits
  Collaboration   — collab_notes, collab_threads, collab_comments
  Exports         — export_jobs
  Candidates      — candidate_profiles, coaching_records
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from backend.core.config import settings

logger = logging.getLogger("neurosync.enterprise_db")

_DB_PATH = Path(settings.DATASET_DIR) / "nuanceai.db"

_ENTERPRISE_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── Identity ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'active',     -- active | suspended | deleted
    plan        TEXT NOT NULL DEFAULT 'professional', -- free | professional | enterprise
    created_at  REAL NOT NULL DEFAULT (unixepoch()),
    config_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS organizations (
    org_id      TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL REFERENCES tenants(tenant_id),
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    branding_json    TEXT NOT NULL DEFAULT '{}',
    config_json      TEXT NOT NULL DEFAULT '{}',
    retention_days   INTEGER NOT NULL DEFAULT 365,
    created_at       REAL NOT NULL DEFAULT (unixepoch()),
    UNIQUE(tenant_id, slug)
);

CREATE TABLE IF NOT EXISTS departments (
    dept_id     TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL REFERENCES organizations(org_id),
    tenant_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  REAL NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS teams (
    team_id     TEXT PRIMARY KEY,
    dept_id     TEXT REFERENCES departments(dept_id),
    org_id      TEXT NOT NULL REFERENCES organizations(org_id),
    tenant_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  REAL NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL REFERENCES tenants(tenant_id),
    org_id        TEXT REFERENCES organizations(org_id),
    email         TEXT NOT NULL,
    password_hash TEXT,
    display_name  TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'active',   -- active | suspended | pending | deleted
    mfa_enabled   INTEGER NOT NULL DEFAULT 0,
    created_at    REAL NOT NULL DEFAULT (unixepoch()),
    last_login    REAL,
    UNIQUE(tenant_id, email)
);

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id, status);

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_token TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(user_id),
    tenant_id     TEXT NOT NULL,
    created_at    REAL NOT NULL DEFAULT (unixepoch()),
    expires_at    REAL NOT NULL,
    ip_address    TEXT,
    user_agent    TEXT,
    revoked       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id, revoked);

-- ── RBAC ──────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS role_assignments (
    assignment_id TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(user_id),
    tenant_id     TEXT NOT NULL,
    org_id        TEXT,
    role          TEXT NOT NULL,
    granted_by    TEXT,
    granted_at    REAL NOT NULL DEFAULT (unixepoch()),
    expires_at    REAL,
    UNIQUE(user_id, org_id, role)
);

CREATE INDEX IF NOT EXISTS idx_roles_user ON role_assignments(user_id, tenant_id);

CREATE TABLE IF NOT EXISTS permission_overrides (
    override_id TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(user_id),
    tenant_id   TEXT NOT NULL,
    permission  TEXT NOT NULL,
    granted     INTEGER NOT NULL DEFAULT 1,    -- 1=grant, 0=deny
    granted_by  TEXT,
    created_at  REAL NOT NULL DEFAULT (unixepoch())
);

-- ── Audit ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_events (
    event_id       TEXT PRIMARY KEY,
    tenant_id      TEXT NOT NULL,
    org_id         TEXT,
    actor_id       TEXT NOT NULL,
    actor_role     TEXT NOT NULL DEFAULT '',
    action         TEXT NOT NULL,
    resource_type  TEXT NOT NULL,
    resource_id    TEXT NOT NULL DEFAULT '',
    changes_json   TEXT,
    ip_address     TEXT NOT NULL DEFAULT '',
    user_agent     TEXT NOT NULL DEFAULT '',
    session_token  TEXT,
    severity       TEXT NOT NULL DEFAULT 'info',   -- info | warning | critical
    timestamp      REAL NOT NULL DEFAULT (unixepoch()),
    metadata_json  TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant    ON audit_events(tenant_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor     ON audit_events(actor_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource  ON audit_events(resource_type, resource_id);

-- ── Compliance ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS retention_policies (
    policy_id   TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL REFERENCES organizations(org_id),
    tenant_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    retain_days INTEGER NOT NULL,
    action_after TEXT NOT NULL DEFAULT 'soft_delete',   -- soft_delete | hard_delete | archive
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL DEFAULT (unixepoch()),
    UNIQUE(org_id, resource_type)
);

CREATE TABLE IF NOT EXISTS consent_records (
    consent_id  TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    subject_id  TEXT NOT NULL,    -- user_id or candidate_id
    purpose     TEXT NOT NULL,    -- analytics | recording | ai_processing
    granted     INTEGER NOT NULL DEFAULT 1,
    granted_at  REAL NOT NULL DEFAULT (unixepoch()),
    expires_at  REAL,
    ip_address  TEXT,
    version     TEXT NOT NULL DEFAULT '1.0'
);

CREATE INDEX IF NOT EXISTS idx_consent_subject ON consent_records(subject_id, purpose);

CREATE TABLE IF NOT EXISTS data_requests (
    request_id    TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    subject_id    TEXT NOT NULL,
    request_type  TEXT NOT NULL,   -- export | erasure | portability | rectification
    status        TEXT NOT NULL DEFAULT 'pending',
    requested_at  REAL NOT NULL DEFAULT (unixepoch()),
    completed_at  REAL,
    result_path   TEXT,
    notes         TEXT
);

-- ── Interview Templates ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS interview_templates (
    template_id   TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES organizations(org_id),
    tenant_id     TEXT NOT NULL,
    name          TEXT NOT NULL,
    interview_type TEXT NOT NULL DEFAULT 'behavioral',
    description   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'active',
    current_version INTEGER NOT NULL DEFAULT 1,
    created_by    TEXT NOT NULL,
    created_at    REAL NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS template_versions (
    version_id    TEXT PRIMARY KEY,
    template_id   TEXT NOT NULL REFERENCES interview_templates(template_id),
    version_num   INTEGER NOT NULL,
    config_json   TEXT NOT NULL,   -- questions, criteria, weights, modalities
    created_by    TEXT NOT NULL,
    created_at    REAL NOT NULL DEFAULT (unixepoch()),
    UNIQUE(template_id, version_num)
);

-- ── Reports ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS report_versions (
    report_id       TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    tenant_id       TEXT NOT NULL,
    org_id          TEXT,
    version_num     INTEGER NOT NULL DEFAULT 1,
    model_version   TEXT NOT NULL,
    reasoning_version TEXT NOT NULL,
    pipeline_hash   TEXT NOT NULL,
    scores_json     TEXT NOT NULL,
    evidence_json   TEXT NOT NULL,
    config_json     TEXT NOT NULL,
    generated_by    TEXT NOT NULL,
    generated_at    REAL NOT NULL DEFAULT (unixepoch()),
    approved_by     TEXT,
    approved_at     REAL,
    approval_status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    immutable_hash  TEXT NOT NULL,
    UNIQUE(session_id, version_num)
);

CREATE INDEX IF NOT EXISTS idx_reports_session ON report_versions(session_id);
CREATE INDEX IF NOT EXISTS idx_reports_tenant  ON report_versions(tenant_id, generated_at DESC);

-- ── API Keys ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS api_keys (
    key_id      TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    org_id      TEXT,
    created_by  TEXT NOT NULL,
    name        TEXT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    key_prefix  TEXT NOT NULL,
    scopes_json TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'active',
    expires_at  REAL,
    last_used   REAL,
    rate_limit  INTEGER NOT NULL DEFAULT 1000,
    created_at  REAL NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS api_key_usage (
    usage_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id      TEXT NOT NULL REFERENCES api_keys(key_id),
    endpoint    TEXT NOT NULL,
    method      TEXT NOT NULL,
    status_code INTEGER,
    timestamp   REAL NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_api_usage_key ON api_key_usage(key_id, timestamp DESC);

-- ── Feature Flags ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS feature_flags (
    flag_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 0,
    rollout_pct INTEGER NOT NULL DEFAULT 0,   -- 0-100
    conditions_json TEXT NOT NULL DEFAULT '{}',
    created_by  TEXT NOT NULL,
    created_at  REAL NOT NULL DEFAULT (unixepoch()),
    updated_at  REAL NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS flag_overrides (
    override_id TEXT PRIMARY KEY,
    flag_id     TEXT NOT NULL REFERENCES feature_flags(flag_id),
    tenant_id   TEXT,
    org_id      TEXT,
    user_id     TEXT,
    enabled     INTEGER NOT NULL,
    created_at  REAL NOT NULL DEFAULT (unixepoch())
);

-- ── Billing ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS subscription_plans (
    plan_id         TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL UNIQUE REFERENCES tenants(tenant_id),
    plan_name       TEXT NOT NULL DEFAULT 'professional',
    seat_limit      INTEGER NOT NULL DEFAULT 10,
    interview_limit INTEGER NOT NULL DEFAULT 500,
    storage_gb      INTEGER NOT NULL DEFAULT 10,
    api_calls_month INTEGER NOT NULL DEFAULT 10000,
    valid_from      REAL NOT NULL DEFAULT (unixepoch()),
    valid_until     REAL
);

CREATE TABLE IF NOT EXISTS usage_records (
    record_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL,
    org_id      TEXT,
    metric      TEXT NOT NULL,   -- interviews | api_calls | storage_bytes | seats
    quantity    REAL NOT NULL,
    period      TEXT NOT NULL,   -- YYYY-MM
    recorded_at REAL NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_usage_tenant ON usage_records(tenant_id, period, metric);

-- ── Collaboration ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS collab_threads (
    thread_id   TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    org_id      TEXT,
    title       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open',   -- open | resolved | closed
    created_by  TEXT NOT NULL,
    created_at  REAL NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS collab_comments (
    comment_id  TEXT PRIMARY KEY,
    thread_id   TEXT NOT NULL REFERENCES collab_threads(thread_id),
    session_id  TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    author_id   TEXT NOT NULL,
    body        TEXT NOT NULL,
    mentions    TEXT NOT NULL DEFAULT '[]',
    created_at  REAL NOT NULL DEFAULT (unixepoch()),
    updated_at  REAL NOT NULL DEFAULT (unixepoch()),
    deleted     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_comments_thread ON collab_comments(thread_id, created_at);

-- ── Export Jobs ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS export_jobs (
    job_id      TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    org_id      TEXT,
    requested_by TEXT NOT NULL,
    export_type  TEXT NOT NULL,   -- pdf | json | csv | evidence_package | audit_bundle
    resource_type TEXT NOT NULL,
    resource_ids  TEXT NOT NULL DEFAULT '[]',
    status        TEXT NOT NULL DEFAULT 'queued',
    result_path   TEXT,
    error_msg     TEXT,
    requested_at  REAL NOT NULL DEFAULT (unixepoch()),
    completed_at  REAL,
    expires_at    REAL
);

-- ── Candidate Profiles ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS candidate_profiles (
    candidate_id  TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    org_id        TEXT,
    display_name  TEXT NOT NULL,
    email         TEXT,
    sessions_json TEXT NOT NULL DEFAULT '[]',
    privacy_json  TEXT NOT NULL DEFAULT '{}',
    created_at    REAL NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_candidates_tenant ON candidate_profiles(tenant_id);
"""


def init_enterprise_db() -> None:
    """Create all Phase 7 enterprise tables in the existing database."""
    con = sqlite3.connect(str(_DB_PATH), timeout=10)
    try:
        con.executescript(_ENTERPRISE_DDL)
        con.commit()
        logger.info("Enterprise DB schema initialised (%s)", _DB_PATH)
    except Exception as exc:
        logger.error("Enterprise DB init failed: %s", exc)
        raise
    finally:
        con.close()


def get_enterprise_conn() -> sqlite3.Connection:
    """Return a WAL-mode connection with row_factory set."""
    con = sqlite3.connect(str(_DB_PATH), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con
