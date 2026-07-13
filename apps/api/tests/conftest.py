"""Test session setup — force Atlas fully offline & hermetic.

Even when apps/api/.env has real keys, the test suite must never hit the network or
the live LLM. These flags route every agent/CRAG path to its deterministic stub and
use the hashing embedder. Use `setdefault` so an explicit override still wins.
"""

import os

os.environ.setdefault("ATLAS_OFFLINE_LLM", "1")
os.environ.setdefault("ATLAS_OFFLINE_EMBED", "1")
# Never try to ship traces during tests.
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "")
