"""Live agentic evaluation — runs the real agents against the real web and LLM.

Not part of the offline unit suite (``tests/``): it spends LLM tokens and search
credits. Run deliberately:

    cd apps/api && pip install -e ".[dev,agent-eval]"
    DATABASE_URL= python -m pytest evals/agentic -q            # all scenarios
    DATABASE_URL= python -m pytest evals/agentic -q -k caughtleads

Requires GROQ_API_KEY (and TAVILY_API_KEY for web research). Results are written to
``evals/agentic/results/latest.json`` for the CI artifact / trend tracking.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

# Never write eval runs into a real database or the developer's cache.
os.environ["DATABASE_URL"] = ""
os.environ.setdefault("ATLAS_CACHE_DIR", tempfile.mkdtemp(prefix="atlas-eval-cache-"))
os.environ.setdefault("ATLAS_LLMOPS_DIR", tempfile.mkdtemp(prefix="atlas-eval-llmops-"))
os.environ.setdefault("RATE_LIMITS_ENABLED", "0")
os.environ.pop("ATLAS_OFFLINE_LLM", None)
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
# Evaluate what production runs: Render uses the lightweight retrieval path (no ~1 GB
# neural reranker), and loading that model next to the judge has crashed Windows runs.
os.environ.setdefault("ATLAS_OFFLINE_EMBED", "1")

RESULTS: list[dict] = []


def pytest_collection_modifyitems(config, items):
    from atlas.config import get_settings

    if not get_settings().llm_configured:
        skip = pytest.mark.skip(reason="GROQ_API_KEY not configured — live eval skipped")
        for item in items:
            item.add_marker(skip)


@pytest.fixture
def record_result():
    def _record(row: dict) -> None:
        RESULTS.append({**row, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    return _record


def pytest_sessionfinish(session, exitstatus):
    if not RESULTS:
        return
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / "latest.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print("\n\nAgentic eval summary")
    for r in RESULTS:
        metrics = " ".join(f"{k}={v:.2f}" for k, v in r.get("metrics", {}).items())
        print(f"  {'PASS' if r['passed'] else 'FAIL'} {r['id']:<34} {metrics}")
