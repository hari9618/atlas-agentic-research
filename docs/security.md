# Atlas — security & scale-out design

What protects the system, why each control exists, and the trade-offs taken on
purpose. Code references are relative to `apps/api/atlas/` unless noted.

## Threat model (what we defend against)

| Threat | Control |
|---|---|
| Anonymous abuse of paid LLM / search quota | Sign-in required for every run; per-plan quotas; a global research budget |
| Credential stuffing / password guessing | Argon2id; per-IP **and** per-account login limits; generic errors; audit log |
| Stolen session token | 15-min access tokens; refresh tokens rotate on every use; reuse of a rotated token revokes the whole session family |
| XSS reading long-lived credentials | Refresh token lives only in an httpOnly first-party cookie (Next.js BFF); browser JS holds only the short access token, in memory |
| CSRF on the cookie endpoints | `SameSite=Lax` + Origin / `Sec-Fetch-Site` checks + JSON-only bodies on the BFF |
| One user reading/resuming another's run (IDOR) | Run ids are namespaced by user id server-side (`routers/research.py:scoped_thread`) |
| Privilege escalation | Role in a signed token; admin-only routes behind `require_admin`; admin role granted only via `AUTH_ADMIN_EMAILS` |
| Database dump / leaked backup | Application-level AES-256-GCM encryption of every sensitive column; key never stored in the DB |
| Network sniffing to the DB | `sslmode=require` enforced in production; plaintext to a remote DB refused |
| A dead/slow third-party API stalling every run | Circuit breaker, bulkhead, deadline, Retry-After-aware retries, cache + request coalescing |
| Traffic spikes | Per-instance admission control (503 + Retry-After), per-user concurrency lease, LLM bulkhead, horizontal scaling behind a load balancer |

## Authentication (`security/`)

* **Passwords** — Argon2id (19 MiB, t=2, p=1: OWASP minimum), 8–128 chars, common
  passwords rejected (NIST 800-63B). Unknown emails still run one Argon2 verify, so
  timing doesn't reveal which accounts exist. Hashes are upgraded on login if the
  parameters are raised (`needs_rehash`).
* **Access token** — HS256 JWT, 15 min, `iss`/`aud`/`typ` checked, algorithm pinned
  (no `alg: none`, no algorithm confusion). Verified without a DB hit, so any replica
  can authenticate any request. Signing key: `AUTH_JWT_SECRET`; a previous key can be
  kept for verification during rotation.
* **Refresh token** — 256-bit random, stored only as SHA-256. Rotated on every refresh.
  Presenting an already-rotated token after a 30 s grace window (two tabs refreshing
  together is benign) is treated as theft → the family is revoked and audited.
* **Guest (demo) sessions** — real accounts with the `guest` role, a 24 h session and
  the smallest quota; purged after 7 days.
* **Account lifecycle** — change password (revokes all other sessions), sign out
  everywhere, delete account (password-confirmed; erases the user and its sessions).

### Why a BFF for the refresh token
Web (Vercel) and API (Render) are different sites, so a cookie set by the API is a
third-party cookie (blocked by Safari, being phased out elsewhere). The Next.js route
handlers (`apps/web/app/api/auth/[action]`) are first-party: they hold the refresh
token in an httpOnly cookie and give the page only the access token. Long research
streams still go **directly** browser → API with a bearer header (no serverless
timeout in the path).

## Authorization

| Route | Who |
|---|---|
| `/health*`, `/` | public |
| `/research/*`, `/llmops` reads, `/corpus/status`, `/auth/me` | any signed-in user (guest included) |
| `/llmops/improve`, `/llmops/rollback`, corpus writes/deletes, `/admin/audit` | admin |

## Encryption at rest (`security/crypto.py`, `core/checkpoint_crypto.py`)

Managed Postgres encrypts disks; that does not help when a **dump or backup** leaks.
So the application encrypts values before writing them:

* AES-256-GCM, random nonce per value, **column name as associated data** (a
  ciphertext moved to another column won't decrypt), HKDF-derived subkeys per purpose.
* Format `enc:v1:<key-id>:<payload>` → **key rotation without downtime**: add the new
  key, keep the old one in `DATA_ENCRYPTION_KEYS_PREVIOUS`, run
  `python -m atlas.security.rotate_keys`, then drop the old key.
* **Blind index** (HMAC) for email lookup; computed under every known key so logins
  work mid-rotation.
* **Boot-time key check** — a canary encrypted on first boot must decrypt at startup;
  a wrong key refuses to start (the previous healthy release keeps serving).
* Production **refuses to start without `DATA_ENCRYPTION_KEY`**.

What is encrypted:

| Data | Where |
|---|---|
| Email, name | `atlas_users.email_enc`, `name_enc` (+ `email_hash` blind index) |
| Run state: question, findings, debate, draft, feedback | LangGraph checkpoints — blobs via `EncryptedSerializer`; inline string values sealed; metadata reduced to `source/step/parents` (the stock saver copies node outputs and run labels into plain JSONB) |
| Run records, policies (exemplars), experiments | `atlas_llmops_documents.data` |
| Episodic memory (query, target, report, findings) | `atlas_episodes` |

Verified by tests that scan raw storage (`tests/test_encryption.py`) and by a manual
production-mode run that found zero plaintext hits across all tables.

**Not encrypted, deliberately:** embedding vectors (similarity search needs them;
they are vectors, not text), timestamps/ids/roles (needed for queries), password
hashes (already one-way), the audit log's IP addresses (the point of a security log).

## Abuse limits & admission control (`security/limits.py`, `core/coordination.py`)

GCRA rate limiting (a token bucket stored as one timestamp) on a shared backend —
Redis (Lua, server clock) → Postgres (one atomic upsert, DB clock, UNLOGGED table) →
memory. Limits are therefore global across replicas, not per instance.

| Rule | Limit |
|---|---|
| Any request, per IP | 240 / min |
| Login, per IP / per account | 10 / min · 8 / 15 min |
| Sign-up, per IP | 5 / h |
| Guest sessions, per IP / global | 6 / h · 120 / h |
| Research runs, guest / user / admin | 3 / 12 / 60 per hour |
| Research runs, whole deployment | 300 / h (caps LLM spend) |
| Concurrent runs per user | 1 (admin 3) — a shared lease |
| Concurrent runs per instance | `MAX_CONCURRENT_RUNS` (503 + Retry-After beyond) |

All 429/503 responses carry `Retry-After` and `{code, retry_after}`.

**Client IP** is the left-most `X-Forwarded-For` entry. It can be forged by a direct
caller, which is why per-IP limits are only the first layer: per-account limits and
the global budgets bound what forging achieves. **Fail-open:** if Redis/Postgres is
down, limit checks allow the request (logged) — the per-instance admission cap still
holds.

## Upstream resilience (`core/upstreams.py`, `core/resilience.py`)

Each provider (Tavily, Yahoo, Stooq, SEC EDGAR) goes through: TTL cache → single-flight
(identical concurrent calls share one request) → circuit breaker (opens after 5
consecutive failures, one half-open probe after 30 s) → bulkhead (max concurrent calls)
→ retries (transient errors only, exponential backoff + jitter, honours `Retry-After`,
overall deadline). LLM calls go through a per-process bulkhead plus the SDK's own
Retry-After-aware retries. State and counters: `GET /health/upstreams`.

## Scale-out

The API is stateless: JWT auth, Postgres checkpoints (a review can resume on another
replica), shared limits/leases, a distributed lease for learning-loop experiments.
`docker compose up --scale api=3` runs N replicas behind nginx (`infra/nginx`):
`least_conn` (runs are long streams of uneven length), SSE-safe proxying (no buffering,
600 s read timeout), failover to another replica on a refused connection or a full
(503) replica — never on POST, never after a response started — and an edge per-IP
limit. On Render, raise the instance count; set `REDIS_URL` for the shared limiter.

Remaining single-instance piece: the in-memory BM25 index when Qdrant is not
configured — with several replicas, point `QDRANT_URL` at a shared Qdrant so corpus
uploads are visible to all of them.

## Operations

* **Audit log** (`atlas_audit_log`, `GET /admin/audit`): sign-ups, sign-ins and
  failures, token reuse, sign-outs, password changes, deletions, admin actions. User
  ids only (no emails), 90-day retention.
* **Request IDs**: honoured from the balancer or minted, returned in `X-Request-ID`,
  on every access-log line.
* **Security headers**: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
  no-referrer`, HSTS in production. CORS: explicit origins, methods and headers;
  no credentials mode (bearer auth).
* **Container**: non-root user, healthcheck, graceful shutdown.
* **CI**: lint, the full suite against real Postgres 16 + Redis 7 service containers,
  `pip-audit` for known CVEs. **Deploy smoke tests** assert 401 without a token, a
  working guest session, 403 on admin routes for a guest, encryption keyed from the
  secret store, and that the web app redirects anonymous visitors to sign-in.

## Production configuration (Render)

| Variable | Required | Notes |
|---|---|---|
| `DATA_ENCRYPTION_KEY` | **yes** | `python -m atlas.security.crypto`; store only in Render's secret env |
| `AUTH_JWT_SECRET` | recommended | ≥ 32 random chars |
| `AUTH_ADMIN_EMAILS` | for admin features | comma-separated |
| `REDIS_URL` | when > 1 instance | Render Key Value / Upstash |
| `DATABASE_URL` | yes | TLS enforced automatically |
