# Atlas — Deployment Runbook

Atlas is a small fleet of cooperating services. Everything is free / self-hostable.

## Topology

```
            ┌──────────────┐        ┌──────────────┐
  browser → │  web (Next)  │ ─────→ │  api (FastAPI)│ ──→ Groq (LLM, hosted)
            │  :3000        │  SSE   │  :8000        │
            └──────────────┘        └──────┬────────┘
                                           │
                          ┌────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                    ┌──────────┐     ┌────────────┐    ┌────────────┐
                    │ qdrant   │     │ langfuse   │    │ (sec edgar │
                    │ :6333    │     │ :3001 +pg  │    │  web, MCP) │
                    └──────────┘     └────────────┘    └────────────┘
```

## 1. Local / single-host (Docker Compose)

```bash
git clone <repo> && cd Major_Project
cp apps/api/.env.example apps/api/.env     # set GROQ_API_KEY (required)
docker compose up -d qdrant langfuse        # infra first (langfuse needs its pg)
docker compose up                            # full stack: qdrant + langfuse + api + web
```

Verify:
```bash
curl http://localhost:8000/health           # {"status":"ok",...}
curl http://localhost:8000/health/ready      # shows llm/langfuse/qdrant wiring
```

First-run notes:
- **Langfuse**: open http://localhost:3001, create a project, copy the public/secret
  keys into `apps/api/.env` (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`), restart `api`.
- **Models**: the first retrieval downloads the bge embedder + reranker (~hundreds of MB).
  In constrained/offline environments set `ATLAS_OFFLINE_EMBED=1` to use the hashing
  embedder. Production should pre-bake the models into the image (see below).

## 2. Production hardening

**Secrets** — never use the dev placeholders in `docker-compose.yml`
(`NEXTAUTH_SECRET`, `SALT`, the Postgres password). Inject real secrets via your
platform's secret manager or a non-committed `.env`. Rotate Groq + Langfuse keys.

**API** — run uvicorn behind a process manager with multiple workers and a reverse
proxy (nginx/Caddy) terminating TLS:
```bash
uvicorn atlas.main:app --host 0.0.0.0 --port 8000 --workers 4
```
Set `CORS_ORIGINS` to the real web origin (no `*`). Put the LangGraph SQLite
checkpointer on a persistent volume (or swap to the Postgres checkpointer at scale).

**Qdrant** — persist `qdrant_storage`; snapshot/back it up. For HA, use Qdrant Cloud
or a clustered deployment. Re-run ingestion to (idempotently) rebuild the collection.

**Langfuse** — persist its Postgres volume; back it up. Restrict the dashboard behind
auth / your VPN. The `api` reaches it in-cluster at `http://langfuse:3000`.

**Images** — pin versions (done), add the api Dockerfile's model pre-bake step for fast
cold starts, and scan images in CI. The `web` image builds from `apps/web/Dockerfile`.

**Pre-bake models (optional, recommended for prod):**
```dockerfile
# in apps/api/Dockerfile, after pip install:
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('BAAI/bge-small-en-v1.5'); CrossEncoder('BAAI/bge-reranker-base')"
```

## 3. CI/CD

`.github/workflows/ci.yml` runs on push/PR to main: ruff lint + the offline test suite
(`ATLAS_OFFLINE_EMBED=1`, no network/keys) with coverage. Extend with a deploy job that
builds + pushes images and rolls out (e.g. to Fly.io / Render / a VPS / k8s).

Recommended gates before deploy:
1. `make lint` clean
2. `make test` green
3. `make eval-retrieval` meets retrieval targets
4. `make eval-ragas` (with a key) meets faithfulness/relevancy/precision targets

## 4. Health, observability, rollback

- **Health**: `/health` (liveness) and `/health/ready` (per-integration) — wire both to
  your orchestrator's probes.
- **Observability**: every agent/tool/LLM call is traced in Langfuse with token + cost;
  Ragas scores are pushed as `ragas_*` scores for retrieval/answer quality.
- **Rollback**: images are version-pinned and stateless (api/web); roll back by
  redeploying the previous tag. Qdrant + Langfuse data persist across redeploys.
