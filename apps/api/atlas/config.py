"""Central configuration for Atlas.

All settings load from environment variables (or a local `apps/api/.env`), with
safe defaults so the app boots even when optional integrations are unconfigured.
Only ``GROQ_API_KEY`` is truly required for the LLM to work — everything else
degrades gracefully and is reported via the /health endpoint.

Note: Atlas keeps its own .env under apps/api/ so it never collides with any other
project that happens to share this repository root.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Atlas-local .env (resolved from the apps/api working dir); ignore unknown keys.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- LLM (Groq) ----
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    # cheaper/faster model for the memory summarizer (consolidation)
    summarizer_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048

    # ---- Memory ----
    memory_consolidate_every: int = 3  # run the summarizer after every N episodes

    # ---- Observability (Langfuse) ----
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    # ---- Vector store (Qdrant) ----
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "atlas_corpus"

    # ---- Embeddings ----
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "BAAI/bge-reranker-base"

    # ---- External tools ----
    tavily_api_key: str = ""
    sec_edgar_user_agent: str = "atlas-research you@example.com"

    # ---- App ----
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # ---- Derived helpers ----
    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so we read the environment exactly once."""
    return Settings()
