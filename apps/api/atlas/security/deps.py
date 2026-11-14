"""FastAPI dependencies: who is calling, and may they?

``HTTPBearer`` also registers the security scheme in OpenAPI, so ``/docs`` gets an
"Authorize" button for trying protected endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..errors import ApiError
from .tokens import TokenError, decode_access

_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login")


@dataclass(frozen=True)
class Principal:
    id: str
    role: str
    email: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_guest(self) -> bool:
        return self.role == "guest"


def _unauthorized(code: str, detail: str) -> ApiError:
    return ApiError(401, code, detail, headers={"WWW-Authenticate": "Bearer"})


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise _unauthorized("not_authenticated", "Sign in to use this endpoint.")
    try:
        claims = decode_access(creds.credentials)
    except TokenError as exc:
        raise _unauthorized(exc.code, str(exc)) from None
    return Principal(id=claims.user_id, role=claims.role, email=claims.email)


async def require_admin(user: Principal = Depends(current_user)) -> Principal:
    if not user.is_admin:
        raise ApiError(403, "forbidden", "Only admins can do this.")
    return user
