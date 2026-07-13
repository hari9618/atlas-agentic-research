"""/research — run the multi-agent due-diligence desk.

`POST /research/sync` runs to completion and returns the final report. `GET
/research/stream` streams per-agent updates over SSE for the war-room UI (each node's
output is emitted as it completes, so the frontend can light up the agent graph live).
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from ..config import get_settings
from ..core.graph import research, run_research

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="The due-diligence question")
    thread_id: str = Field("default", description="Run id (for checkpointing/resume)")


@router.post("/sync")
async def research_sync(req: ResearchRequest) -> dict:
    if not get_settings().llm_configured:
        return {"error": "GROQ_API_KEY not configured", "report": "", "confidence": None}
    result = await run_in_threadpool(research, req.query, thread_id=req.thread_id)
    return result


@router.get("/stream")
async def research_stream(q: str, thread_id: str = "default"):
    """Server-Sent Events: one message per agent node, ending with a 'final' event."""
    async def event_gen():
        # Same precondition as /sync: signal (don't silently stub) when unconfigured.
        if not get_settings().llm_configured:
            yield {"event": "error", "data": json.dumps({"error": "GROQ_API_KEY not configured"})}
            return
        async for ev in iterate_in_threadpool(run_research(q, thread_id=thread_id)):
            yield {"event": ev["event"], "data": json.dumps(ev["data"], default=str)}

    return EventSourceResponse(event_gen())
