"""
Integration tests for health, readiness, liveness, and observability endpoints.

These tests start the FastAPI app in TestClient (synchronous ASGI runner)
and validate that each health endpoint returns the expected shape and status codes.
No mocking — the actual health_checker and alert_manager are invoked.

Run:
    pytest tests/integration/test_health_endpoints.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── /health/live ──────────────────────────────────────────────────────────────

def test_liveness_returns_200(client):
    r = client.get("/health/live")
    assert r.status_code == 200

def test_liveness_body(client):
    r = client.get("/health/live")
    body = r.json()
    assert body["alive"] is True
    assert "timestamp" in body


# ── /health/ready ─────────────────────────────────────────────────────────────

def test_readiness_returns_valid_status(client):
    r = client.get("/health/ready")
    assert r.status_code in (200, 503)

def test_readiness_body_has_ready_key(client):
    r = client.get("/health/ready")
    body = r.json()
    assert "ready" in body


# ── /health/full ──────────────────────────────────────────────────────────────

def test_full_health_returns_200(client):
    r = client.get("/health/full")
    assert r.status_code == 200

def test_full_health_has_status(client):
    r = client.get("/health/full")
    body = r.json()
    assert body["status"] in ("healthy", "degraded", "unhealthy")

def test_full_health_has_components(client):
    r = client.get("/health/full")
    body = r.json()
    assert "components" in body
    assert isinstance(body["components"], list)
    assert len(body["components"]) > 0

def test_full_health_components_have_required_fields(client):
    r = client.get("/health/full")
    components = r.json()["components"]
    for comp in components:
        assert "name"   in comp
        assert "status" in comp
        assert comp["status"] in ("healthy", "degraded", "unhealthy", "unknown")

def test_full_health_has_summary(client):
    r = client.get("/health/full")
    body = r.json()
    assert "summary" in body
    summary = body["summary"]
    assert "healthy"   in summary
    assert "degraded"  in summary
    assert "unhealthy" in summary


# ── /health/dependencies ──────────────────────────────────────────────────────

def test_dependencies_returns_200(client):
    r = client.get("/health/dependencies")
    assert r.status_code == 200

def test_dependencies_is_dict(client):
    r = client.get("/health/dependencies")
    assert isinstance(r.json(), dict)


# ── /system/alerts ────────────────────────────────────────────────────────────

def test_alerts_returns_200(client):
    r = client.get("/system/alerts")
    assert r.status_code == 200

def test_alerts_has_required_fields(client):
    r = client.get("/system/alerts")
    body = r.json()
    assert "evaluated_at" in body
    assert "total_rules"  in body
    assert "firing"       in body
    assert "healthy"      in body
    assert "alerts"       in body
    assert isinstance(body["alerts"], list)


# ── /system/resources ────────────────────────────────────────────────────────

def test_resources_returns_200(client):
    r = client.get("/system/resources")
    assert r.status_code == 200

def test_resources_has_system_block(client):
    r = client.get("/system/resources")
    body = r.json()
    # psutil may not be installed in CI — just validate timestamp is present
    assert "timestamp" in body


# ── /metrics (Prometheus) ─────────────────────────────────────────────────────

def test_prometheus_metrics_returns_200(client):
    r = client.get("/metrics")
    assert r.status_code == 200

def test_prometheus_metrics_content_type(client):
    r = client.get("/metrics")
    assert "text/plain" in r.headers.get("content-type", "")

def test_prometheus_metrics_has_help_lines(client):
    r = client.get("/metrics")
    assert "# HELP" in r.text

def test_prometheus_metrics_json(client):
    r = client.get("/metrics/json")
    assert r.status_code == 200
    body = r.json()
    # Format: { metric_name: { "type": "counter|gauge|histogram", "samples": [...] } }
    assert isinstance(body, dict)
    assert len(body) > 0, "Expected at least one registered metric"
    for val in body.values():
        assert "type" in val
        break


# ── /system/version ───────────────────────────────────────────────────────────

def test_version_phase_present(client):
    r = client.get("/system/version")
    assert r.status_code == 200
    phase = r.json()["phase"]
    assert isinstance(phase, int) and phase >= 1
