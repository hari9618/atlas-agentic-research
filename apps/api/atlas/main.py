"""Atlas FastAPI application entrypoint.

A thin gateway: it owns process-level concerns (logging, CORS, router wiring) and
delegates real work to ``atlas.core`` (RAG, the LangGraph agents, tools), which are
built across milestones M2–M4. Keeping the app factory small makes it trivial to
spin up in tests and under uvicorn alike.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .errors import install_error_handlers
from .middleware import RequestContextMiddleware
from .routers import admin, auth, corpus, health, llmops, research


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )


def _check_security_config(settings) -> None:
    """Refuse to boot in production with a configuration that would silently store
    data unencrypted or sign tokens with a throwaway key. A crash here fails the
    deploy's health check, so the previous (healthy) release keeps serving."""
    from .security.crypto import keyring

    log = logging.getLogger("atlas.main")
    ring = keyring()  # raises EncryptionConfigError in production without a key
    if settings.is_production:
        if len(settings.auth_jwt_secret) < 32:
            log.warning("AUTH_JWT_SECRET is not set: tokens are signed with a key stored "
                        "in the database. Set it in the host's secret store.")
        if "*" in settings.cors_origin_list:
            raise RuntimeError("CORS_ORIGINS='*' is not allowed in production")
    # Wrong key for this database → refuse to boot (only against Postgres: the shared,
    # durable store; local SQLite dev/test databases are throwaway).
    from .core.persistence import get_pg_pool

    if get_pg_pool() is not None:
        from .security.store import get_auth_store

        get_auth_store().verify_key_canary()
    log.info("Security: encryption keyring=%s (active key %s)", ring.source, ring.active.kid)


def warm_up() -> None:
    """Load the retrieval stack in the background once the server is up.

    Startup only imports what answering a request needs, so a sleeping free-tier
    instance can serve sign-ups as soon as it boots; the heavier retrieval imports
    then load here instead of inside the first research run.
    """
    log = logging.getLogger("atlas.main")

    def _load() -> None:
        try:
            import langchain.retrievers  # noqa: F401
            log.info("warm-up: retrieval stack loaded")
        except Exception as exc:  # never let warm-up take the server down
            log.warning("warm-up skipped: %s", exc)

    threading.Thread(target=_load, name="atlas-warm-up", daemon=True).start()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    warm_up()
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI app. Importable from tests and uvicorn."""
    settings = get_settings()
    _configure_logging(settings.log_level)
    _check_security_config(settings)

    app = FastAPI(
        title="Atlas — Autonomous Due-Diligence Desk",
        version=__version__,
        description=(
            "A team of specialist AI agents that research a company/market, debate "
            "(bull vs bear), ground claims in retrieved evidence, and produce an "
            "investor-grade cited report with a confidence score."
        ),
        lifespan=_lifespan,
    )

    install_error_handlers(app)
    # Order matters: the last added runs first. CORS must wrap everything so even a
    # 429 from the request-context layer carries CORS headers the browser can read.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        # Auth is a bearer header, not cookies — the API never needs credentials mode.
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["Retry-After", "X-Request-ID"],
        max_age=600,
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
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
