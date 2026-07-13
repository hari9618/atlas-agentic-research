"""/llmops — inspect prompt versions and run the self-improvement loop."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..core.llmops.optimizer import optimize
from ..core.llmops.registry import get_registry

router = APIRouter(prefix="/llmops", tags=["llmops"])


class OptimizeRequest(BaseModel):
    query: str = Field(..., min_length=3)
    max_iters: int = Field(1, ge=1, le=3)


@router.get("/prompts")
async def prompts() -> dict:
    reg = get_registry()
    name = "synthesizer_system"
    return {
        "name": name,
        "active_version": reg.active_version(name),
        "versions": [
            {"version": v.version, "notes": v.notes, "scores": v.scores,
             "created_at": v.created_at, "text": v.text}
            for v in reg.history(name)
        ],
    }


@router.post("/optimize")
async def run_optimize(req: OptimizeRequest) -> dict:
    if not get_settings().llm_configured:
        return {"error": "GROQ_API_KEY not configured"}
    out = await run_in_threadpool(optimize, req.query, max_iters=req.max_iters)
    final = out.pop("final", {}) or {}
    out["final_report"] = final.get("report", "")
    out["final_confidence"] = final.get("confidence")
    return out
