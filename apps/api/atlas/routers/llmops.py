"""/llmops — the learning loop: overview, experiments, component policies, rollback."""

from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..core.llmops.improver import get_experiments, improve, overview
from ..core.llmops.policy import COMPONENTS, LABELS, get_policies

router = APIRouter(prefix="/llmops", tags=["llmops"])

# One experiment at a time per process: experiments spend LLM budget and release
# policies, so two concurrent ones would race on the same component.
_improving = threading.Lock()


class RollbackRequest(BaseModel):
    component: str


def _component(name: str) -> str:
    if name not in COMPONENTS:
        raise HTTPException(404, f"Unknown component {name!r}. One of: {', '.join(COMPONENTS)}")
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
async def run_improvement() -> dict:
    """Run one experiment on the top open issue (can take 30–120 s on the live LLM)."""
    if not get_settings().llm_configured:
        return {"experiment": None, "message": "GROQ_API_KEY not configured."}
    if not _improving.acquire(blocking=False):
        raise HTTPException(409, "An improvement experiment is already running.")
    try:
        return await run_in_threadpool(improve)
    finally:
        _improving.release()


@router.post("/rollback")
async def rollback(req: RollbackRequest) -> dict:
    comp = _component(req.component)
    version = await run_in_threadpool(get_policies().rollback, comp)
    return {"component": comp, "version": version}
