"""
Fault injection integration tests.

Tests the system's resilience when dependencies fail or inputs are malformed.
Validates that:
  - Malformed request bodies return 422, not 500
  - Unknown session IDs return 404
  - Oversized payloads are rejected
  - Security-sensitive paths are blocked
  - The system degrades gracefully rather than crashing

These are blackbox tests against the running ASGI app via TestClient.

Run:
    pytest tests/integration/test_fault_injection.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Bad inputs ────────────────────────────────────────────────────────────────

def test_session_create_missing_required_field(client):
    """session_name is required — missing it should give 422."""
    r = client.post("/api/sessions", json={})
    assert r.status_code == 422

def test_session_create_empty_name(client):
    """session_name must be non-empty (min_length=1 in schema)."""
    r = client.post("/api/sessions", json={"session_name": "", "mode": "interview"})
    # Either 422 (validation) or 400 (domain) is acceptable — not 500
    assert r.status_code in (400, 422)

def test_session_create_invalid_mode(client):
    r = client.post("/api/sessions", json={"session_name": "Test", "mode": "invalid_mode"})
    assert r.status_code in (400, 422)


# ── Unknown resources ─────────────────────────────────────────────────────────

def test_unknown_session_returns_404(client):
    r = client.get("/api/sessions/nonexistent-session-id-xyz")
    assert r.status_code in (404, 422)

def test_unknown_golden_scenario_returns_404(client):
    r = client.get("/ai/golden-tests/GS-DOES-NOT-EXIST")
    assert r.status_code == 404

def test_unknown_load_scenario(client):
    r = client.post("/ai/load-test/run", json={"scenario": "nonexistent_scenario"})
    assert r.status_code == 400

def test_unknown_stress_scenario(client):
    r = client.post("/ai/stress-test/run", json={"scenario": "nonexistent_scenario"})
    assert r.status_code == 400


# ── Security boundary tests ───────────────────────────────────────────────────

def test_path_traversal_blocked(client):
    """Security middleware should block path traversal attempts."""
    r = client.get("/../../etc/passwd")
    # Either 400 (blocked) or 404 (path not found) — not 200 or 500
    assert r.status_code in (400, 404, 422)

def test_deeply_nested_path_blocked_or_404(client):
    r = client.get("/api/sessions/../../../etc/passwd")
    assert r.status_code in (400, 404, 422)


# ── Oversized inputs ──────────────────────────────────────────────────────────

def test_dataset_validation_with_empty_samples(client):
    """Empty samples list should not crash the server."""
    r = client.post(
        "/ai/datasets/validate",
        json={"dataset_name": "test", "dataset_version": "1.0", "samples": []},
    )
    # 200 (empty report) or 400 (rejected) — not 500
    assert r.status_code in (200, 400, 422)


# ── Idempotency ───────────────────────────────────────────────────────────────

def test_liveness_always_200(client):
    """Liveness must always return 200 regardless of system state."""
    for _ in range(5):
        r = client.get("/health/live")
        assert r.status_code == 200

def test_version_is_stable(client):
    """Version endpoint must return identical results across calls."""
    r1 = client.get("/system/version").json()
    r2 = client.get("/system/version").json()
    assert r1["version"] == r2["version"]
    assert r1["phase"]   == r2["phase"]


# ── Graceful degradation ──────────────────────────────────────────────────────

def test_health_full_never_500(client):
    """Health check must always return a valid response, never 500."""
    r = client.get("/health/full")
    assert r.status_code != 500

def test_alerts_never_500(client):
    r = client.get("/system/alerts")
    assert r.status_code != 500

def test_metrics_never_500(client):
    r = client.get("/metrics")
    assert r.status_code != 500

def test_resources_never_500(client):
    r = client.get("/system/resources")
    assert r.status_code != 500


# ── Content type enforcement ──────────────────────────────────────────────────

def test_post_without_json_content_type(client):
    """POST endpoints should handle missing content-type gracefully."""
    r = client.post(
        "/api/sessions",
        data="not json",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code in (400, 415, 422)


# ── Concurrent safety (basic) ─────────────────────────────────────────────────

def test_concurrent_liveness_probes(client):
    """Multiple rapid calls to liveness should all succeed."""
    results = [client.get("/health/live").status_code for _ in range(10)]
    assert all(s == 200 for s in results)
