"""Auth, authorization, tenant isolation, quotas and admission control — end to end
through the real app (no dependency overrides: every test here is ``real_auth``)."""

from __future__ import annotations

import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from atlas.config import get_settings
from atlas.core.coordination import Coordinator, MemoryBackend, set_coordinator
from atlas.core.sqldb import SqlDb
from atlas.main import app
from atlas.security import limits, service
from atlas.security.store import AuthStore, set_auth_store
from atlas.security.tokens import AUDIENCE, ISSUER, keys

pytestmark = pytest.mark.real_auth

client = TestClient(app)
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def fresh_state(tmp_path, monkeypatch):
    """A private auth DB and limiter per test; quotas OFF unless a test turns them on."""
    store = AuthStore(SqlDb(path=tmp_path / "auth.sqlite"))
    set_auth_store(store)
    set_coordinator(Coordinator(MemoryBackend()))
    limits.RUN_SLOTS.active = 0
    monkeypatch.setattr(get_settings(), "rate_limits_enabled", False)
    yield store
    set_auth_store(None)
    set_coordinator(None)
    limits.RUN_SLOTS.active = 0


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def _register(email: str | None = None, password: str = PASSWORD) -> dict:
    r = client.post("/auth/register", json={"email": email or _email(), "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def _auth(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


def _stream(path: str, params: dict, headers: dict):
    """GET an SSE endpoint. sse-starlette caches a process-global anyio.Event bound to
    the first event loop, and each TestClient request runs a new loop — reset it."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    return client.get(path, params=params, headers=headers)


def _sse_events(r) -> list[str]:
    return [line[len("event: "):].strip() for line in r.text.splitlines()
            if line.startswith("event: ")]


# ---------------------------------------------------------------- accounts
@pytest.fixture(autouse=True)
def _llm_key(monkeypatch):
    """The research router refuses to run without an LLM key, and the suite sets none
    (as on CI). Pretend one is configured; ATLAS_OFFLINE_LLM keeps the LLM a stub."""
    from atlas.config import Settings

    monkeypatch.setattr(Settings, "llm_configured", property(lambda self: True))


def test_register_login_and_me():
    email = _email()
    reg = _register(email)
    assert reg["token_type"] == "bearer" and reg["user"]["role"] == "user"
    assert reg["refresh_token"] and reg["expires_in"] == get_settings().auth_access_ttl_s

    login = client.post("/auth/login", json={"email": email.upper(), "password": PASSWORD})
    assert login.status_code == 200  # emails are case-insensitive
    assert login.headers["cache-control"] == "no-store"

    me = client.get("/auth/me", headers=_auth(login.json()))
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == email and body["plan"]["research_per_hour"] > 0


def test_duplicate_email_and_weak_password_are_rejected():
    email = _email()
    _register(email)
    dup = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert dup.status_code == 409 and dup.json()["code"] == "email_taken"

    weak = client.post("/auth/register", json={"email": _email(), "password": "password1"})
    assert weak.status_code == 422 and weak.json()["code"] == "weak_password"
    short = client.post("/auth/register", json={"email": _email(), "password": "abc"})
    assert short.status_code == 422


def test_bad_credentials_get_one_generic_answer():
    email = _email()
    _register(email)
    wrong = client.post("/auth/login", json={"email": email, "password": "not the password"})
    unknown = client.post("/auth/login", json={"email": _email(), "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no account enumeration


def test_admin_role_comes_from_configured_emails(monkeypatch):
    email = _email()
    monkeypatch.setattr(get_settings(), "auth_admin_emails", f"other@x.io, {email}")
    assert _register(email)["user"]["role"] == "admin"


def test_guest_session_is_a_limited_role():
    r = client.post("/auth/guest", json={})
    assert r.status_code == 200
    guest = r.json()
    assert guest["user"]["role"] == "guest" and guest["user"]["email"] is None
    assert guest["refresh_expires_in"] == get_settings().auth_guest_ttl_hours * 3600
    plan = client.get("/auth/me", headers=_auth(guest)).json()["plan"]
    assert plan["research_per_hour"] == limits.PLANS["guest"].research.limit


# ---------------------------------------------------------------- refresh rotation
def test_refresh_rotates_and_detects_reuse(monkeypatch):
    first = _register()
    rotated = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rotated.status_code == 200
    second = rotated.json()
    assert second["refresh_token"] != first["refresh_token"]

    # Re-presenting the rotated token right away is a benign two-tab race…
    race = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert race.status_code == 401 and race.json()["code"] == "refresh_race"

    # …but after the grace window it means the token was copied: kill the family,
    # including the legitimate newer token.
    monkeypatch.setattr(service, "REFRESH_GRACE_S", 0.0)
    time.sleep(0.01)
    reuse = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401 and reuse.json()["code"] == "invalid_token"
    after = client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert after.status_code == 401 and after.json()["code"] == "invalid_token"


def test_logout_revokes_the_session():
    s = _register()
    out = client.post("/auth/logout", json={"refresh_token": s["refresh_token"]})
    assert out.status_code == 204
    r = client.post("/auth/refresh", json={"refresh_token": s["refresh_token"]})
    assert r.status_code == 401


# ---------------------------------------------------------------- access tokens
def _token(**overrides) -> str:
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "u1", "role": "admin", "typ": "access",
              "iat": now, "nbf": now, "exp": now + 60, **overrides}
    return jwt.encode(claims, keys()[0], algorithm="HS256")


@pytest.mark.parametrize("headers,code", [
    ({}, "not_authenticated"),
    ({"Authorization": "Bearer not-a-jwt"}, "invalid_token"),
])
def test_protected_endpoints_need_a_valid_token(headers, code):
    r = client.get("/llmops/overview", headers=headers)
    assert r.status_code == 401 and r.json()["code"] == code
    assert r.headers["www-authenticate"] == "Bearer"


def test_expired_forged_and_alg_none_tokens_are_rejected():
    expired = _token(exp=int(time.time()) - 120, iat=int(time.time()) - 300,
                     nbf=int(time.time()) - 300)
    r = client.get("/llmops/overview", headers={"Authorization": f"Bearer {expired}"})
    assert r.json()["code"] == "token_expired"

    forged = jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": "u1", "role": "admin",
                         "typ": "access", "iat": int(time.time()), "exp": int(time.time()) + 60},
                        "attacker-key-attacker-key-attacker-key!!", algorithm="HS256")
    r = client.get("/llmops/overview", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401

    unsigned = jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": "u1", "role": "admin",
                           "typ": "access", "iat": int(time.time()),
                           "exp": int(time.time()) + 60}, None, algorithm="none")
    r = client.get("/llmops/overview", headers={"Authorization": f"Bearer {unsigned}"})
    assert r.status_code == 401

    wrong_type = _token(typ="refresh")
    r = client.get("/llmops/overview", headers={"Authorization": f"Bearer {wrong_type}"})
    assert r.status_code == 401


def test_admin_only_actions_are_forbidden_to_users():
    user = _auth(_register())
    assert client.get("/llmops/overview", headers=user).status_code == 200
    for method, path, body in [("post", "/llmops/improve", None),
                               ("post", "/llmops/rollback", {"component": "risk"}),
                               ("delete", "/corpus", None),
                               ("post", "/corpus/text", {"title": "x" * 5, "text": "y" * 60})]:
        r = client.request(method.upper(), path, headers=user, json=body)
        assert r.status_code == 403 and r.json()["code"] == "forbidden", path


# ---------------------------------------------------------------- tenant isolation
def test_users_cannot_resume_each_others_runs():
    alice, bob = _auth(_register()), _auth(_register())
    tid = f"shared-{uuid.uuid4().hex[:6]}"
    r = _stream("/research/stream", {"q": "Assess Helios Robotics", "thread_id": tid,
                                               "review": 1}, alice)
    assert _sse_events(r)[-1] == "review_required"

    # Same thread id, different user: it simply doesn't exist for Bob.
    r = _stream("/research/resume", {"thread_id": tid, "action": "approve"},
                   headers=bob)
    assert "unknown_thread" in r.text

    r = _stream("/research/resume", {"thread_id": tid, "action": "approve"},
                   headers=alice)
    assert _sse_events(r)[-1] == "final"


# ---------------------------------------------------------------- quotas + admission
def test_guest_research_quota_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limits_enabled", True)
    guest = _auth(client.post("/auth/guest", json={}).json())
    allowed = limits.PLANS["guest"].research.limit
    for i in range(allowed):
        r = _stream("/research/stream", {"q": "Assess Helios Robotics",
                                                   "thread_id": f"g{i}"}, guest)
        assert r.status_code == 200, r.text
    r = _stream("/research/stream", {"q": "Assess Helios Robotics",
                                               "thread_id": "over"}, guest)
    assert r.status_code == 429
    body = r.json()
    assert body["code"] == "rate_limited" and body["retry_after"] > 0
    assert int(r.headers["retry-after"]) == body["retry_after"]


def test_login_brute_force_is_throttled(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limits_enabled", True)
    email = _email()
    _register(email)
    codes = [client.post("/auth/login", json={"email": email, "password": "wrong guess!"}
                         ).status_code for _ in range(12)]
    assert codes[0] == 401 and codes[-1] == 429


def test_full_instance_answers_503_busy(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_concurrent_runs", 1)
    limits.RUN_SLOTS.active = 1  # another run is streaming on this instance
    r = _stream("/research/stream", {"q": "Assess Helios Robotics"},
                   _auth(_register()))
    assert r.status_code == 503 and r.json()["code"] == "busy"
    assert "retry-after" in r.headers


def test_one_concurrent_run_per_user(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limits_enabled", True)
    session = _register()
    from atlas.core.coordination import get_coordinator

    # Simulate a run of this user streaming on another instance (it holds the lease).
    assert get_coordinator().acquire(f"run:{session['user']['id']}:0", "elsewhere", 60)
    r = _stream("/research/stream", {"q": "Assess Helios Robotics"},
                   _auth(session))
    assert r.status_code == 409 and r.json()["code"] == "run_in_progress"
    assert limits.RUN_SLOTS.active == 0  # the instance slot was handed back


def test_finished_runs_release_their_capacity():
    session = _auth(_register())
    r = _stream("/research/stream", {"q": "Assess Helios Robotics"}, session)
    assert _sse_events(r)[-1] == "final"
    assert limits.RUN_SLOTS.active == 0


def test_every_response_carries_a_request_id_and_security_headers():
    r = client.get("/health", headers={"X-Request-ID": "lb-req-12345678"})
    assert r.headers["x-request-id"] == "lb-req-12345678"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/health").headers["x-request-id"] != "lb-req-12345678"


def test_client_ip_comes_from_the_forwarded_chain():
    from atlas.security.limits import client_ip_from_scope

    def scope(xff=None):
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return {"headers": headers, "client": ("10.0.0.5", 1234)}

    assert client_ip_from_scope(scope()) == "10.0.0.5"  # no proxy: the TCP peer
    # browser -> Vercel BFF -> Render LB: the left-most entry is the user.
    assert client_ip_from_scope(scope("203.0.113.7, 76.76.21.9")) == "203.0.113.7"
    assert client_ip_from_scope(scope("2001:db8::1")) == "2001:db8::1"
    assert client_ip_from_scope(scope("<script>, 1.2.3.4")) == "10.0.0.5"  # junk ignored
