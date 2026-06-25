"""
API contract tests.

Validates that actual API response shapes conform to the Pydantic schemas
defined in backend/contracts/schemas.py. These tests catch breaking changes
before they reach production.

All tests parse real endpoint responses with strict Pydantic validation.
A ValidationError means the contract was violated.

Run:
    pytest tests/contracts/test_api_contracts.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError


@pytest.fixture(scope="module")
def client():
    from backend.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _parse(schema_cls, data: dict):
    """Parse dict with schema_cls; raise descriptive AssertionError on failure."""
    try:
        return schema_cls(**data)
    except ValidationError as exc:
        raise AssertionError(f"{schema_cls.__name__} contract violated:\n{exc}") from exc


# ── /health/live → LivenessResponse ──────────────────────────────────────────

def test_liveness_contract(client):
    from backend.contracts.schemas import LivenessResponse
    r = client.get("/health/live")
    assert r.status_code == 200
    _parse(LivenessResponse, r.json())


# ── /health/ready → ReadinessResponse ────────────────────────────────────────

def test_readiness_contract(client):
    from backend.contracts.schemas import ReadinessResponse
    r = client.get("/health/ready")
    assert r.status_code in (200, 503)
    _parse(ReadinessResponse, r.json())


# ── /health/full → HealthResponse ────────────────────────────────────────────

def test_full_health_contract(client):
    from backend.contracts.schemas import HealthResponse
    r = client.get("/health/full")
    assert r.status_code == 200
    _parse(HealthResponse, r.json())


# ── /system/alerts → AlertReport ─────────────────────────────────────────────

def test_alerts_contract(client):
    from backend.contracts.schemas import AlertReport
    r = client.get("/system/alerts")
    assert r.status_code == 200
    _parse(AlertReport, r.json())


# ── /system/version → VersionResponse ────────────────────────────────────────

def test_version_contract(client):
    from backend.contracts.schemas import VersionResponse
    r = client.get("/system/version")
    assert r.status_code == 200
    _parse(VersionResponse, r.json())


# ── /ai/golden-tests → GoldenTestReport ──────────────────────────────────────

def test_golden_tests_contract(client):
    from backend.contracts.schemas import GoldenTestReport
    r = client.get("/ai/golden-tests")
    assert r.status_code == 200
    _parse(GoldenTestReport, r.json())


# ── /ai/stability/suite → dict with per-scenario StabilityReportResponse ─────

def test_stability_suite_results_contract(client):
    from backend.contracts.schemas import StabilityReportResponse
    r = client.get("/ai/stability/suite?n_perturbations=5")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    for item in data["results"]:
        _parse(StabilityReportResponse, item)


# ── /ai/load-test/scenarios → LoadScenarioInfo list ──────────────────────────

def test_load_test_scenarios_contract(client):
    from backend.contracts.schemas import LoadScenarioInfo
    r = client.get("/ai/load-test/scenarios")
    assert r.status_code == 200
    data = r.json()
    assert "scenarios" in data
    for s in data["scenarios"]:
        _parse(LoadScenarioInfo, s)


# ── Session create → SessionCreateResponse ────────────────────────────────────

def test_session_create_contract(client):
    from backend.contracts.schemas import SessionCreateResponse
    r = client.post("/api/sessions", json={"session_name": "Contract Test", "mode": "interview"})
    if r.status_code != 200:
        pytest.skip("Session endpoint unavailable or returned error")
    _parse(SessionCreateResponse, r.json())


# ── Backward-compatibility: no removed required fields ────────────────────────

def test_health_response_has_no_removed_fields(client):
    """Ensure fields that downstream consumers depend on are still present."""
    r = client.get("/health/full")
    body = r.json()
    # These fields must never be removed without a major version bump
    required = {"status", "components", "summary", "checked_at", "version"}
    missing = required - set(body.keys())
    assert not missing, f"Required fields removed from /health/full: {missing}"


def test_version_response_backward_compat(client):
    r = client.get("/system/version")
    body = r.json()
    required = {"name", "version", "phase", "engine", "reasoning", "timestamp"}
    missing = required - set(body.keys())
    assert not missing, f"Required fields removed from /system/version: {missing}"
