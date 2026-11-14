"""Account flows: register, login, guest, refresh (rotation + reuse detection), logout.

Sync functions on purpose: Argon2 and the database calls block, so the router runs
them in the thread pool and the event loop stays free for streaming runs.
"""

from __future__ import annotations

import logging
import random
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

from ..config import get_settings
from ..errors import ApiError
from .passwords import hash_password, needs_rehash, password_problem, verify_password
from .store import EmailTakenError, User, get_auth_store
from .tokens import issue_access

log = logging.getLogger("atlas.security.service")

# A rotated token presented again within this window is two tabs refreshing at once,
# not theft: answer "refresh_race" (retry with the newer cookie) instead of revoking.
REFRESH_GRACE_S = 30.0


@dataclass(frozen=True)
class Session:
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_in: int
    user: User

    def body(self) -> dict:
        return {"access_token": self.access_token, "token_type": "bearer",
                "expires_in": self.expires_in, "refresh_token": self.refresh_token,
                "refresh_expires_in": self.refresh_expires_in, "user": self.user.public()}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _refresh_ttl_s(role: str) -> int:
    s = get_settings()
    if role == "guest":
        return s.auth_guest_ttl_hours * 3600
    return s.auth_refresh_ttl_days * 86_400


def _start_session(user: User, family_id: str | None = None) -> Session:
    store = get_auth_store()
    refresh = secrets.token_urlsafe(32)
    ttl = _refresh_ttl_s(user.role)
    store.add_refresh(refresh, user_id=user.id, family_id=family_id or uuid.uuid4().hex,
                      ttl_s=ttl)
    access, expires_in = issue_access(user_id=user.id, role=user.role, email=user.email)
    return Session(access, expires_in, refresh, ttl, user)


def _role_for(email: str) -> str:
    return "admin" if email in get_settings().admin_email_set else "user"


def register(email: str, password: str, name: str | None) -> Session:
    settings = get_settings()
    if not settings.auth_allow_signup:
        raise ApiError(403, "signup_disabled", "New sign-ups are currently closed.")
    email = normalize_email(email)
    problem = password_problem(password, email)
    if problem:
        raise ApiError(422, "weak_password", problem)
    try:
        user = get_auth_store().create_user(
            email=email, name=(name or "").strip()[:80] or None,
            password_hash=hash_password(password), role=_role_for(email))
    except EmailTakenError:
        raise ApiError(409, "email_taken",
                       "An account with this email already exists. Sign in instead.") from None
    log.info("auth: registered user %s (%s)", user.id, user.role)
    return _start_session(user)


def login(email: str, password: str) -> Session:
    store = get_auth_store()
    email = normalize_email(email)
    user = store.user_by_email(email)
    # Always one Argon2 verify, user or not — equal timing, no account enumeration.
    ok = verify_password(user.password_hash if user else None, password)
    if not ok or user is None or user.disabled:
        raise ApiError(401, "invalid_credentials", "Invalid email or password.")
    # Promote/demote on login so ADMIN_EMAILS changes take effect without a migration.
    role = _role_for(email)
    if role != user.role:
        store.set_role(user.id, role)
        user = User(user.id, user.email, user.name, role, user.password_hash)
    store.touch_login(user.id, hash_password(password) if needs_rehash(user.password_hash)
                      else None)
    return _start_session(user)


def guest() -> Session:
    if not get_settings().auth_allow_guest:
        raise ApiError(403, "guest_disabled", "Demo sessions are currently disabled.")
    store = get_auth_store()
    user = store.create_user(email=None, name="Guest", password_hash=None, role="guest")
    if random.random() < 0.05:  # amortized cleanup of week-old demo accounts
        try:
            store.purge_guests(timedelta(days=7))
            store.purge_expired_tokens()
        except Exception as exc:
            log.warning("auth cleanup failed: %s", exc)
    return _start_session(user)


def refresh(token: str) -> Session:
    """Rotate a refresh token. Reuse of a rotated token revokes the whole family."""
    store = get_auth_store()
    row = store.get_refresh(token) if token else None
    invalid = ApiError(401, "invalid_token", "Your session has ended. Please sign in again.")
    if row is None:
        raise invalid
    now = time.time()
    if row.revoked_at is not None:
        if row.rotated_at is not None and now - row.rotated_at <= REFRESH_GRACE_S:
            raise ApiError(401, "refresh_race", "Session was just refreshed; retry.")
        revoked = store.revoke_family(row.family_id)
        from . import audit

        audit.record("auth.refresh_reuse_detected", user_id=row.user_id, revoked=revoked)
        log.warning("auth: refresh-token reuse for user %s — revoked %d token(s) in family",
                    row.user_id, revoked)
        raise invalid
    if row.expires_at < now:
        raise invalid
    if not store.claim_refresh(token):  # a concurrent refresh won the race
        raise ApiError(401, "refresh_race", "Session was just refreshed; retry.")
    user = store.user_by_id(row.user_id)
    if user is None or user.disabled:
        store.revoke_family(row.family_id)
        raise invalid
    return _start_session(user, family_id=row.family_id)


def logout(token: str) -> None:
    store = get_auth_store()
    row = store.get_refresh(token) if token else None
    if row is not None:
        store.revoke_family(row.family_id)


def me(user_id: str) -> User | None:
    return get_auth_store().user_by_id(user_id)


def change_password(user_id: str, current: str, new: str) -> Session:
    """Change the password and end every other session (a password change is what a
    user does when they think someone else got in)."""
    store = get_auth_store()
    user = store.user_by_id(user_id)
    if user is None or user.password_hash is None:
        raise ApiError(400, "no_password", "This account has no password to change.")
    if not verify_password(user.password_hash, current):
        raise ApiError(401, "invalid_credentials", "Your current password is incorrect.")
    problem = password_problem(new, user.email)
    if problem:
        raise ApiError(422, "weak_password", problem)
    store.set_password(user.id, hash_password(new))
    store.revoke_user(user.id)
    return _start_session(user)


def logout_all(user_id: str) -> int:
    return get_auth_store().revoke_user(user_id)


def delete_account(user_id: str, password: str | None) -> None:
    """Erase the account. Password accounts must confirm with their password."""
    store = get_auth_store()
    user = store.user_by_id(user_id)
    if user is None:
        return
    if user.password_hash is not None and not verify_password(user.password_hash,
                                                               password or ""):
        raise ApiError(401, "invalid_credentials", "Your password is incorrect.")
    store.delete_user(user.id)
