"""/llmops — the learning loop: overview, experiments, component policies, rollback.

Reads need a signed-in user; anything that changes agent behaviour (running an
experiment, rolling a policy back) is admin-only.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..core.coordination import get_coordinator
from ..core.llmops.improver import get_experiments, improve, overview
from ..core.llmops.policy import COMPONENTS, LABELS, get_policies
from ..errors import ApiError
from ..security import audit, limits
from ..security.deps import Principal, current_user, require_admin

router = APIRouter(prefix="/llmops", tags=["llmops"], dependencies=[Depends(current_user)])

# One experiment at a time across ALL instances: experiments spend LLM budget and
# release policies, so two concurrent ones would race on the same component. A lease
# (not a process lock) because behind a load balancer the second request may land on
# another instance. The TTL frees it if the holder crashes mid-experiment.
_IMPROVE_LEASE = "llmops:improve"
_IMPROVE_TTL_S = 15 * 60


class RollbackRequest(BaseModel):
    component: str


def _component(name: str) -> str:
    if name not in COMPONENTS:
        raise ApiError(404, "unknown_component",
                       f"Unknown component {name!r}. One of: {', '.join(COMPONENTS)}")
    return name


@router.get("/overview")
async def get_overview() -> dict:
    return await run_in_threadpool(overview)


@router.get("/experiments")
async def list_experiments(limit: int = 30) -> list[dict]:
    return await run_in_threadpool(get_experiments().list, max(1, min(limit, 100)))


@router.get("/components/{name}")
async def component_history(name: str) -> dict:
    pol = get_policies()
    comp = _component(name)
    return {"name": comp, "label": LABELS[comp], "active_version": pol.active_version(comp),
            "versions": pol.versions(comp)}


@router.post("/improve")
async def run_improvement(request: Request, admin: Principal = Depends(require_admin)) -> dict:
    """Run one experiment on the top open issue (can take 30–120 s on the live LLM)."""
    if not get_settings().llm_configured:
        return {"experiment": None, "message": "GROQ_API_KEY not configured."}
    await limits.enforce(limits.IMPROVE, admin.id, what="experiments")
    coordinator = get_coordinator()
    owner = secrets.token_hex(8)
    if not await run_in_threadpool(coordinator.acquire, _IMPROVE_LEASE, owner, _IMPROVE_TTL_S):
        raise ApiError(409, "experiment_running", "An improvement experiment is already running.")
    try:
        result = await run_in_threadpool(improve)
        exp = (result or {}).get("experiment") or {}
        await run_in_threadpool(lambda: audit.record(
            "admin.llmops.improve", user_id=admin.id, request=request,
            component=exp.get("component"), decision=exp.get("decision")))
        return result
    finally:
        await run_in_threadpool(coordinator.release, _IMPROVE_LEASE, owner)


@router.post("/experiments/{exp_id}/approve")
async def approve(exp_id: str, request: Request,
                  admin: Principal = Depends(require_admin)) -> dict:
    """Release the change an experiment validated, after reading its lesson text."""
    from ..core.llmops.improver import approve_experiment

    try:
        out = await run_in_threadpool(lambda: approve_experiment(exp_id, approver=admin.id))
    except ValueError as exc:
        raise ApiError(409, "not_awaiting_approval", str(exc)) from None
    await run_in_threadpool(lambda: audit.record(
        "admin.llmops.approve", user_id=admin.id, request=request, experiment=exp_id, **out))
    return out


@router.post("/experiments/{exp_id}/reject")
async def reject(exp_id: str, request: Request,
                 admin: Principal = Depends(require_admin)) -> dict:
    from ..core.llmops.improver import reject_experiment

    try:
        out = await run_in_threadpool(lambda: reject_experiment(exp_id, approver=admin.id))
    except ValueError as exc:
        raise ApiError(409, "not_awaiting_approval", str(exc)) from None
    await run_in_threadpool(lambda: audit.record(
        "admin.llmops.reject", user_id=admin.id, request=request, experiment=exp_id))
    return out


@router.post("/rollback")
async def rollback(req: RollbackRequest, request: Request,
                   admin: Principal = Depends(require_admin)) -> dict:
    comp = _component(req.component)
    version = await run_in_threadpool(get_policies().rollback, comp)
    await run_in_threadpool(lambda: audit.record(
        "admin.llmops.rollback", user_id=admin.id, request=request, component=comp,
        version=version))
    return {"component": comp, "version": version}
