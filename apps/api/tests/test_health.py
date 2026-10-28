"""Smoke tests for the M1 rails: the app boots and reports its status.

These don't require Groq/Langfuse/Qdrant to be configured — they assert the app
serves and that readiness reports each integration's state, which is exactly the
graceful-degradation contract from CLAUDE.md.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.main import app

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


def test_readiness_reports_database_and_web_search():
    checks = client.get("/health/ready").json()["checks"]
    assert checks["database"]["backend"] in {"postgres", "sqlite"}
    assert isinstance(checks["web_search"]["configured"], bool)


def test_settings_strip_pasted_whitespace(monkeypatch):
    from atlas.config import Settings

    monkeypatch.setenv("TAVILY_API_KEY", "  tvly-abc123\n")
    assert Settings().tavily_api_key == "tvly-abc123"


def test_web_probe_names_the_failure_without_leaking_the_key(monkeypatch):
    import importlib

    import httpx

    W = importlib.import_module("atlas.core.tools.web_search")  # the module, not the function

    def rejected(*a, **k):
        req = httpx.Request("POST", W._ENDPOINT)
        resp = httpx.Response(401, request=req)
        raise httpx.HTTPStatusError("401", request=req, response=resp)

    monkeypatch.setattr(W, "_probe_cache", None)
    monkeypatch.setattr(W, "_tavily_search", rejected)
    fake = type("S", (), {"tavily_api_key": "tvly-SECRET"})()
    monkeypatch.setattr(W, "get_settings", lambda: fake)
    out = client.get("/health/web").json()
    assert out["ok"] is False and "invalid" in out["detail"] and "SECRET" not in str(out)
    # Cached: a second hit doesn't call Tavily again.
    assert client.get("/health/web").json()["cached"] is True
