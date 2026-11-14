"""/auth — accounts and sessions.

Tokens are returned in the JSON body. The web app's own server (Next.js route
handlers) keeps the refresh token in a first-party httpOnly cookie and hands only the
short-lived access token to browser JavaScript — see apps/web/app/api/auth.

Every security-relevant outcome is written to the audit log (``security.audit``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from starlette.concurrency import run_in_threadpool

from ..errors import ApiError
from ..security import audit, limits, service
from ..security.deps import Principal, current_user
from ..security.limits import client_ip, enforce, plan_for

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=256)
    name: str | None = Field(None, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=1, max_length=256)


class DeleteAccount(BaseModel):
    password: str | None = Field(None, max_length=256)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


async def _audit(event: str, request: Request, **kw: object) -> None:
    await run_in_threadpool(lambda: audit.record(event, request=request, **kw))


@router.post("/register", status_code=201)
async def register(req: RegisterRequest, request: Request, response: Response) -> dict:
    await enforce(limits.REGISTER_IP, client_ip(request), what="sign-up attempts")
    session = await run_in_threadpool(service.register, req.email, req.password, req.name)
    await _audit("auth.register", request, user_id=session.user.id, role=session.user.role)
    _no_store(response)
    return session.body()


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response) -> dict:
    # Both keys: per IP stops one host spraying many accounts; per account stops a
    # botnet guessing one account's password from many IPs.
    await enforce(limits.LOGIN_IP, client_ip(request), what="sign-in attempts")
    await enforce(limits.LOGIN_ACCOUNT, service.normalize_email(req.email),
                  what="sign-in attempts")
    try:
        session = await run_in_threadpool(service.login, req.email, req.password)
    except ApiError:
        await _audit("auth.login.failed", request)
        raise
    await _audit("auth.login", request, user_id=session.user.id)
    _no_store(response)
    return session.body()


@router.post("/guest")
async def guest(request: Request, response: Response) -> dict:
    await enforce(limits.GUEST_IP, client_ip(request), what="demo sessions")
    await enforce(limits.GUEST_GLOBAL, "all", what="demo sessions right now")
    session = await run_in_threadpool(service.guest)
    await _audit("auth.guest", request, user_id=session.user.id)
    _no_store(response)
    return session.body()


@router.post("/refresh")
async def refresh(req: RefreshRequest, request: Request, response: Response) -> dict:
    await enforce(limits.REFRESH_IP, client_ip(request), what="refreshes")
    session = await run_in_threadpool(service.refresh, req.refresh_token)
    _no_store(response)
    return session.body()


@router.post("/logout", status_code=204)
async def logout(req: RefreshRequest) -> Response:
    await run_in_threadpool(service.logout, req.refresh_token)
    return Response(status_code=204)


@router.post("/logout-all", status_code=204)
async def logout_all(request: Request, user: Principal = Depends(current_user)) -> Response:
    """End every session of this account, on every device."""
    revoked = await run_in_threadpool(service.logout_all, user.id)
    await _audit("auth.logout_all", request, user_id=user.id, sessions=revoked)
    return Response(status_code=204)


@router.post("/password")
async def change_password(req: PasswordChange, request: Request, response: Response,
                          user: Principal = Depends(current_user)) -> dict:
    await enforce(limits.LOGIN_ACCOUNT, f"pw:{user.id}", what="password attempts")
    session = await run_in_threadpool(service.change_password, user.id,
                                      req.current_password, req.new_password)
    await _audit("auth.password_changed", request, user_id=user.id)
    _no_store(response)
    return session.body()


@router.delete("/me", status_code=204)
async def delete_me(req: DeleteAccount, request: Request,
                    user: Principal = Depends(current_user)) -> Response:
    """Delete the account and every session (right to erasure)."""
    await enforce(limits.LOGIN_ACCOUNT, f"del:{user.id}", what="attempts")
    await run_in_threadpool(service.delete_account, user.id, req.password)
    await _audit("auth.account_deleted", request, user_id=user.id)
    return Response(status_code=204)


@router.get("/me")
async def me(user: Principal = Depends(current_user)) -> dict:
    record = await run_in_threadpool(service.me, user.id)
    if record is None:  # deleted while the access token was still valid
        raise ApiError(401, "invalid_token", "This account no longer exists.")
    plan = plan_for(user.role)
    return {"user": record.public(),
            "plan": {"research_per_hour": plan.research.limit,
                     "concurrent_runs": plan.concurrent_runs}}
