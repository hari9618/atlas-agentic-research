"""Access tokens: short-lived HS256 JWTs.

Access tokens are verified without a database round-trip, so any number of API
instances can authenticate a request independently — the property that lets the API
scale horizontally behind a load balancer. The trade-off is that a token stays valid
until it expires, which is why it lives 15 minutes; revocation happens on the
refresh token (see ``service.refresh``).
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass

import jwt

from ..config import get_settings

log = logging.getLogger("atlas.security.tokens")

ALGORITHM = "HS256"
ISSUER = "atlas-api"
AUDIENCE = "atlas-web"
LEEWAY_S = 10  # tolerate small clock skew between instances
_MIN_SECRET = 32


@dataclass(frozen=True)
class AccessClaims:
    user_id: str
    role: str
    email: str | None


class TokenError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_lock = threading.Lock()
_keys: tuple[str, ...] | None = None


def _resolve_keys() -> tuple[str, ...]:
    """(signing key, *verification-only keys). Resolved once per process."""
    settings = get_settings()
    primary = settings.auth_jwt_secret
    if len(primary) < _MIN_SECRET:
        if primary:
            log.warning("AUTH_JWT_SECRET is shorter than %d chars — ignoring it.", _MIN_SECRET)
        try:
            from .store import get_auth_store

            primary = get_auth_store().shared_secret("jwt_signing_key")
            log.warning("AUTH_JWT_SECRET not set — using the generated key stored in the "
                        "database. Set AUTH_JWT_SECRET in production.")
        except Exception as exc:  # no database at all: tokens die with the process
            log.warning("No AUTH_JWT_SECRET and no database (%s) — using a per-process key.",
                        exc)
            primary = secrets.token_urlsafe(48)
    previous = settings.auth_jwt_secret_previous
    return (primary, previous) if len(previous) >= _MIN_SECRET else (primary,)


def keys() -> tuple[str, ...]:
    global _keys
    with _lock:
        if _keys is None:
            _keys = _resolve_keys()
        return _keys


def reset_keys() -> None:
    global _keys
    with _lock:
        _keys = None


def issue_access(*, user_id: str, role: str, email: str | None,
                 ttl_s: int | None = None) -> tuple[str, int]:
    """Return ``(token, ttl_seconds)``."""
    ttl = ttl_s or get_settings().auth_access_ttl_s
    now = int(time.time())
    claims = {
        "iss": ISSUER, "aud": AUDIENCE, "sub": user_id, "role": role, "email": email,
        "typ": "access", "iat": now, "nbf": now, "exp": now + ttl,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(claims, keys()[0], algorithm=ALGORITHM), ttl


def decode_access(token: str) -> AccessClaims:
    """Verify signature, expiry, issuer, audience and type. Raises ``TokenError``."""
    last: Exception | None = None
    for key in keys():
        try:
            data = jwt.decode(
                token, key, algorithms=[ALGORITHM],  # pinned: never trust the header's alg
                audience=AUDIENCE, issuer=ISSUER, leeway=LEEWAY_S,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("token_expired", "Your session has expired.") from exc
        except jwt.InvalidSignatureError as exc:
            last = exc  # maybe signed with the previous key; try it
            continue
        except jwt.InvalidTokenError as exc:
            raise TokenError("invalid_token", "Invalid access token.") from exc
        if data.get("typ") != "access":
            raise TokenError("invalid_token", "Invalid access token.")
        return AccessClaims(user_id=str(data["sub"]), role=str(data.get("role", "user")),
                            email=data.get("email"))
    raise TokenError("invalid_token", "Invalid access token.") from last
