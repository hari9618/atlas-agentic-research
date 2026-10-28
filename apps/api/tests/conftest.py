"""Test session setup — force Atlas fully offline & hermetic.

Even when apps/api/.env has real keys, the test suite must never hit the network or
the live LLM. These flags route every agent/CRAG path to its deterministic stub and
use the hashing embedder. Use `setdefault` so an explicit override still wins.
"""

import os

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
