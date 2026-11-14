"""Run records — what the learning loop learns from.

One record per finished run: the automatic evaluation, per-agent scores, the human
review outcome (approve / revise / reject, feedback, targeted section) and the
policy versions that produced it. Findings and the debate are kept in compact form
so the synthesizer can be replayed on exactly the same inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from statistics import mean
from typing import Any

from .store import DocumentStore, now_iso

KEEP_RECORDS = 300
_EVIDENCE_CHARS = 900
_DEBATE_CHARS = 600


def _compact_findings(findings: list[dict]) -> list[dict]:
    keep = ("agent", "claim", "citation", "confidence", "unavailable")
    out = []
    for f in findings or []:
        row = {k: f[k] for k in keep if k in f}
        if f.get("evidence_text"):
            row["evidence_text"] = str(f["evidence_text"])[:_EVIDENCE_CHARS]
        out.append(row)
    return out


def review_outcome(status: str, history: list[dict]) -> str:
    """``approved`` | ``revised`` (approved after changes) | ``rejected`` | ``none``."""
    if status == "rejected":
        return "rejected"
    if status == "approved":
        return "revised" if any(h.get("action") == "revise" for h in history) else "approved"
    return "none"


def build_record(values: Mapping, *, thread_id: str, scores: dict | None,
                 policy_versions: dict[str, int]) -> dict:
    """A record from final graph state plus the run's evaluation (``None`` if unscored)."""
    history = list(values.get("review_history") or [])
    status = values.get("review_status") or "auto_approved"
    record: dict[str, Any] = {
        "thread_id": thread_id,
        "created_at": now_iso(),
        "query": values.get("query", ""),
        "target": values.get("target", ""),
        "ticker": values.get("ticker", ""),
        "brief": {k: values.get(k) for k in ("subject_domain", "asker", "asker_domain",
                                             "persona", "goal", "extra_asks")
                  if values.get(k)},
        "degraded": bool(values.get("degraded")) or any(
            f.get("unavailable") for f in values.get("findings") or []),
        "policy_versions": policy_versions,
        "review": {"status": status, "outcome": review_outcome(status, history),
                   "history": history},
        "findings": _compact_findings(values.get("findings") or []),
        "debate": [{"role": d.get("role"), "text": str(d.get("text", ""))[:_DEBATE_CHARS]}
                   for d in values.get("debate") or []],
        "scores": None,
        "agents": {},
        "report_check": {},
    }
    if scores:
        record["scores"] = {k: scores.get(k) for k in (
            "faithfulness", "relevancy", "context_precision", "citation_accuracy",
            "citation_coverage", "overall", "quality")}
        record["agents"] = scores.get("agents") or {}
        check = scores.get("report_check") or {}
        record["report_check"] = {"unsupported": list(check.get("unsupported") or [])[:4],
                                  "miscited": list(check.get("miscited") or [])[:4]}
    return record


class RunRecords:
    def __init__(self, *, root: Path | None = None, pool: Any = None) -> None:
        self._docs = DocumentStore("run", root=root, pool=pool, keep=KEEP_RECORDS)

    def save(self, record: dict) -> None:
        self._docs.put(record["thread_id"], record)

    def recent(self, limit: int = 40) -> list[dict]:
        return self._docs.list(limit)

    def stats(self, limit: int = 100) -> dict:
        records = self.recent(limit)
        outcomes = [r["review"]["outcome"] for r in records]
        overall = [r["scores"]["overall"] for r in records
                   if r.get("scores") and r["scores"].get("overall") is not None]
        return {
            "total": len(records),
            "reviewed": sum(o != "none" for o in outcomes),
            "approved": sum(o in ("approved", "revised") for o in outcomes),
            "rejected": outcomes.count("rejected"),
            "revision_requests": sum(
                1 for r in records for h in r["review"]["history"] if h.get("action") == "revise"),
            "mean_overall": round(mean(overall), 3) if overall else None,
            "recent": [{
                "id": r["thread_id"], "created_at": r.get("created_at"), "query": r["query"],
                "target": r.get("target", ""),
                "overall": (r.get("scores") or {}).get("overall"),
                "quality": (r.get("scores") or {}).get("quality"),
                "review": r["review"]["outcome"],
            } for r in records[:8]],
        }


_records: RunRecords | None = None


def get_records() -> RunRecords:
    global _records
    if _records is None:
        _records = RunRecords()
    return _records


def reset_records() -> None:
    global _records
    _records = None
