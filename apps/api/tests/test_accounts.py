"""Account lifecycle and the audit trail: password change, sign out everywhere,
account deletion, and admin-only access to the audit log."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from atlas.config import get_settings
from atlas.core.coordination import Coordinator, MemoryBackend, set_coordinator
from atlas.core.sqldb import SqlDb
from atlas.main import app
from atlas.security.store import AuthStore, set_auth_store

pytestmark = pytest.mark.real_auth
client = TestClient(app)
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    set_auth_store(AuthStore(SqlDb(path=tmp_path / "auth.sqlite")))
    set_coordinator(Coordinator(MemoryBackend()))
    monkeypatch.setattr(get_settings(), "rate_limits_enabled", False)
    yield
    set_auth_store(None)
    set_coordinator(None)


def _register(email: str | None = None) -> dict:
    r = client.post("/auth/register", json={"email": email or f"{uuid.uuid4().hex[:8]}@ex.com",
                                            "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def _h(s: dict) -> dict:
    return {"Authorization": f"Bearer {s['access_token']}"}


def test_password_change_ends_other_sessions():
    email = f"{uuid.uuid4().hex[:8]}@ex.com"
    laptop = _register(email)
    phone = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()

    bad = client.post("/auth/password", headers=_h(laptop),
                      json={"current_password": "nope nope", "new_password": "a new long secret"})
    assert bad.status_code == 401

    r = client.post("/auth/password", headers=_h(laptop),
                    json={"current_password": PASSWORD, "new_password": "a new long secret"})
    assert r.status_code == 200 and r.json()["refresh_token"]
    # The phone's session is gone; the new password works, the old one doesn't.
    assert client.post("/auth/refresh", json={"refresh_token": phone["refresh_token"]}
                       ).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": PASSWORD}
                       ).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": "a new long secret"}
                       ).status_code == 200


def test_sign_out_everywhere():
    email = f"{uuid.uuid4().hex[:8]}@ex.com"
    a = _register(email)
    b = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()
    assert client.post("/auth/logout-all", headers=_h(a)).status_code == 204
    for s in (a, b):
        assert client.post("/auth/refresh", json={"refresh_token": s["refresh_token"]}
                           ).status_code == 401


def test_account_deletion_needs_the_password_and_erases_everything():
    email = f"{uuid.uuid4().hex[:8]}@ex.com"
    s = _register(email)
    wrong = client.request("DELETE", "/auth/me", headers=_h(s), json={"password": "wrong pw!"})
    assert wrong.status_code == 401
    ok = client.request("DELETE", "/auth/me", headers=_h(s), json={"password": PASSWORD})
    assert ok.status_code == 204
    assert client.get("/auth/me", headers=_h(s)).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": PASSWORD}
                       ).status_code == 401
    # The email is free again.
    assert client.post("/auth/register", json={"email": email, "password": PASSWORD}
                       ).status_code == 201


def test_guests_can_delete_their_session_account_without_a_password():
    g = client.post("/auth/guest", json={}).json()
    assert client.request("DELETE", "/auth/me", headers=_h(g), json={}).status_code == 204


def test_audit_log_records_security_events_and_is_admin_only(monkeypatch):
    admin_email = f"admin-{uuid.uuid4().hex[:6]}@ex.com"
    monkeypatch.setattr(get_settings(), "auth_admin_emails", admin_email)
    user = _register()
    client.post("/auth/login", json={"email": "nobody@ex.com", "password": "whatever pw"})
    admin = _register(admin_email)

    assert client.get("/admin/audit", headers=_h(user)).status_code == 403
    r = client.get("/admin/audit", headers=_h(admin))
    assert r.status_code == 200
    events = [e["event"] for e in r.json()["events"]]
    assert {"auth.register", "auth.login.failed"} <= set(events)
    assert all("password" not in str(e) for e in r.json()["events"])  # no secrets logged
    only_auth = client.get("/admin/audit", headers=_h(admin), params={"event": "auth.login"})
    assert {e["event"] for e in only_auth.json()["events"]} == {"auth.login.failed"}


def test_refresh_token_theft_is_audited(monkeypatch):
    from atlas.security import service

    s = _register()
    client.post("/auth/refresh", json={"refresh_token": s["refresh_token"]})
    monkeypatch.setattr(service, "REFRESH_GRACE_S", -1.0)
    client.post("/auth/refresh", json={"refresh_token": s["refresh_token"]})
    from atlas.security import audit

    assert any(e["event"] == "auth.refresh_reuse_detected" for e in audit.recent(20))
