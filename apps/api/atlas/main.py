"""Atlas FastAPI application entrypoint.

A thin gateway: it owns process-level concerns (logging, CORS, router wiring) and
delegates real work to ``atlas.core`` (RAG, the LangGraph agents, tools), which are
built across milestones M2–M4. Keeping the app factory small makes it trivial to
spin up in tests and under uvicorn alike.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .routers import corpus, health, llmops, research


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )


def create_app() -> FastAPI:
    """Build and configure the FastAPI app. Importable from tests and uvicorn."""
    settings = get_settings()
    _configure_logging(settings.log_level)

    app = FastAPI(
        title="Atlas — Autonomous Due-Diligence Desk",
        version=__version__,
        description=(
            "A team of specialist AI agents that research a company/market, debate "
            "(bull vs bear), ground claims in retrieved evidence, and produce an "
            "investor-grade cited report with a confidence score."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(research.router)
    app.include_router(corpus.router)
    app.include_router(llmops.router)

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "service": "atlas-api",
            "version": __version__,
            "description": "Autonomous Due-Diligence Desk — multi-agent research backend",
            "docs": "/docs",
        }

    return app


app = create_app()
