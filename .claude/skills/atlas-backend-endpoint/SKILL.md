---
name: atlas-backend-endpoint
description: >
  Add or modify a FastAPI endpoint in the Atlas backend the Atlas way — typed
  Pydantic v2 models, a router under atlas/routers, config via get_settings(),
  graceful degradation, and SSE for anything long-running. Use when the
  backend-engineer needs to add an HTTP route (e.g. /research, report fetch,
  health additions). Primarily for the backend-engineer subagent.
---

# Skill: Atlas backend endpoint

Follow these steps to add an endpoint that matches Atlas conventions.

## 1. Decide the response style
- **Quick/synchronous** (config, lookups) → normal JSON response.
- **Long-running multi-agent run** (research) → **SSE stream** so the war-room UI
  shows live agent activity. Use `sse-starlette`'s `EventSourceResponse`.

## 2. Define typed models (Pydantic v2)
```python
from pydantic import BaseModel, Field

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Company / market question")
    rounds: int = Field(2, ge=1, le=5, description="Debate rounds")
```

## 3. Create the router
```python
# atlas/routers/research.py
from __future__ import annotations
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from ..config import get_settings
from ..observability import langchain_callbacks

router = APIRouter(prefix="/research", tags=["research"])

@router.post("")
async def run_research(req: ResearchRequest):
    settings = get_settings()
    if not settings.llm_configured:
        # graceful: never 500 on missing config — tell the caller what's wrong
        return {"error": "GROQ_API_KEY not configured"}

    async def event_stream():
        # call into atlas.core graph; yield {"event","data"} per agent step
        # pass callbacks=langchain_callbacks() into the graph invocation
        yield {"event": "status", "data": "planning"}
        ...
    return EventSourceResponse(event_stream())
```

## 4. Register it
In `atlas/main.py`: `app.include_router(research.router)`.

## 5. Conventions to honor
- `from __future__ import annotations` at top; full type hints.
- Read all config from `get_settings()` — no literals for keys/URLs.
- Pass `langchain_callbacks()` into any graph/LLM invocation so it's traced.
- Don't block the event loop on a full run — stream, or offload.

## 6. Verify
- Add/extend a test in `apps/api/tests` (pytest, async).
- `ruff check apps/api` and `pytest` must pass.
- Report the exact `curl`/`httpie` command to exercise the endpoint.
