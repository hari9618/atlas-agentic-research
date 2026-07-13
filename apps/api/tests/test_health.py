"""Smoke tests for the M1 rails: the app boots and reports its status.

These don't require Groq/Langfuse/Qdrant to be configured — they assert the app
serves and that readiness reports each integration's state, which is exactly the
graceful-degradation contract from CLAUDE.md.
"""

from __future__ import annotations

from atlas.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_liveness() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "atlas-api"}


def test_health_readiness_reports_integrations() -> None:
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert "ready" in body
    assert set(body["checks"]) >= {"llm", "langfuse", "qdrant"}


def test_root_identifies_service() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "atlas-api"
