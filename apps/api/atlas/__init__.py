"""Atlas — Autonomous Due-Diligence Desk (backend package)."""

import os as _os

__version__ = "0.1.0"

# The lightweight profile (ATLAS_OFFLINE_EMBED=1: hashing embedder, no neural reranker,
# what Render's free tier runs) never uses PyTorch. LangChain's retrievers package still
# pulls in `transformers`, which imports torch when it is installed: ~1 GB of RAM and
# most of a cold start on a 0.1-CPU instance. USE_TORCH=0 tells transformers to skip it.
if _os.getenv("ATLAS_OFFLINE_EMBED") == "1":
    _os.environ.setdefault("USE_TORCH", "0")
