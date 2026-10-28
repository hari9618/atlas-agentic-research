"""Health & readiness endpoints.

`/health` is a liveness probe (the process is up). `/health/ready` reports which
integrations are actually configured/reachable, so you can see at a glance —
in the browser or in the war-room UI — whether Groq, Langfuse, Qdrant, Postgres and
web search are wired. (Configuration only for web search: probing Tavily on every
health check would spend API credits.)
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..core.persistence import using_postgres
from ..observability import get_langfuse_handler

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness — always 200 if the process is serving."""
    return {"status": "ok", "service": "atlas-api"}


@router.get("/health/ready")
async def readiness() -> dict:
    """Readiness — per-integration configuration & reachability."""
    settings = get_settings()

    # Qdrant reachability (best-effort, short timeout).
    qdrant_ok = False
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{settings.qdrant_url}/readyz")
            qdrant_ok = resp.status_code == 200
    except Exception:
        qdrant_ok = False

    checks = {
        "llm": {
            "configured": settings.llm_configured,
            "model": settings.groq_model,
        },
        "langfuse": {
            "configured": settings.langfuse_configured,
            "active": get_langfuse_handler() is not None,
            "host": settings.langfuse_host,
        },
        "qdrant": {
            "configured": True,
            "reachable": qdrant_ok,
            "url": settings.qdrant_url,
        },
        "database": {
            "configured": bool(settings.database_url.strip()),
            # Opening the pool can block on a cold connect, so keep it off the loop.
            "backend": "postgres" if await run_in_threadpool(using_postgres) else "sqlite",
        },
        "web_search": {"configured": bool(settings.tavily_api_key.strip())},
    }

    ready = settings.llm_configured  # LLM is the only hard requirement
    return {"ready": ready, "env": settings.app_env, "checks": checks}


@router.get("/health/web")
async def web_search_probe() -> dict:
    """Live web-search check: one tiny Tavily query, result cached for 10 minutes.

    Distinguishes "key missing / invalid / out of credits / network" — failures that
    otherwise only show as research with no web evidence.
    """
    from ..core.tools.web_search import probe

    return await run_in_threadpool(probe)
