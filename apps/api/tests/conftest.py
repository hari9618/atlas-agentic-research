"""Test session setup — force Atlas fully offline & hermetic.

Even when apps/api/.env has real keys, the test suite must never hit the network or
the live LLM. These flags route every agent/CRAG path to its deterministic stub and
use the hashing embedder. Use `setdefault` so an explicit override still wins.
"""

import os
import tempfile

os.environ.setdefault("ATLAS_OFFLINE_LLM", "1")
os.environ.setdefault("ATLAS_OFFLINE_EMBED", "1")
# Retry backoff waits are zero in tests so error-path tests never sleep.
os.environ.setdefault("ATLAS_RETRY_BASE_WAIT", "0")
os.environ.setdefault("ATLAS_RETRY_MAX_WAIT", "0")
# Never try to ship traces during tests.
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "")
# Durable state stays on local SQLite/JSON in tests, even if .env or the shell sets a
# DATABASE_URL (an env var beats .env in pydantic-settings). Postgres integration
# tests opt in explicitly via ATLAS_TEST_DATABASE_URL (tests/test_persistence_pg.py).
os.environ["DATABASE_URL"] = ""
# Provider keys too. A developer's .env holds real keys, which once made 5 tests pass
# locally and fail on CI (which has none): the research router refuses to run without
# a key. Blanking them here makes local runs behave exactly like CI; tests that need
# the "key configured" path patch it explicitly (the LLM itself stays offline).
os.environ["GROQ_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""
# The learning loop's records/policies/experiments go to a throwaway directory, so
# test runs never pollute the real data/cache/llmops history.
os.environ["ATLAS_LLMOPS_DIR"] = tempfile.mkdtemp(prefix="atlas-llmops-")
# Checkpoints, episodic memory and the auth DB too: graph tests used to write into the
# real data/cache, polluting dev memory and making recall order-dependent.
os.environ["ATLAS_CACHE_DIR"] = tempfile.mkdtemp(prefix="atlas-cache-")
# Quotas are exercised by their own tests (tests/test_security.py), which turn them on;
# elsewhere a suite that runs dozens of research runs as one user must not trip them.
os.environ.setdefault("RATE_LIMITS_ENABLED", "0")
# A fixed signing key, so token tests never fall back to a database-stored one.
os.environ.setdefault("AUTH_JWT_SECRET", "test-signing-key-0123456789-abcdefghijklmnopqrstuvwxyz")
# A fixed data-encryption key (32 zero-ish bytes, urlsafe base64) so encrypted test
# rows never depend on a developer's local key file.
os.environ.setdefault("DATA_ENCRYPTION_KEY", "dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMzJieXQ")

import pytest


@pytest.fixture(autouse=True)
def _fresh_upstreams():
    """Upstream caches/breakers are process-global; a cached search result or an open
    circuit from one test must never leak into the next."""
    from atlas.core.upstreams import reset_all

    reset_all()
    yield
    reset_all()


@pytest.fixture(autouse=True)
def _signed_in(request):
    """Router tests written before auth act as a signed-in admin. Tests that exercise
    real authentication opt out with ``@pytest.mark.real_auth``."""
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    from atlas.main import app
    from atlas.security.deps import Principal, current_user

    app.dependency_overrides[current_user] = lambda: Principal(
        id="test-user", role="admin", email="tester@example.com")
    yield
    app.dependency_overrides.pop(current_user, None)
