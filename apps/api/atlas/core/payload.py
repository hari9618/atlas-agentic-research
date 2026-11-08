"""The client-facing run payload (design §4 ``ResearchPayload``).

Built from graph state in one place so the SSE ``review_required`` / ``final`` events,
``/research/sync`` and the review interrupt all expose exactly the same shape.

``client_view`` is applied at the HTTP edge only: it drops server-side fields (the
full evidence text behind each finding, up to 2 kB apiece) that the evaluators need
but the browser never reads — they made every streamed event several times larger.
"""

from __future__ import annotations

from collections.abc import Mapping


def research_payload(values: Mapping) -> dict:
    return {
        "report": values.get("report", "") or "",
        "report_sections": values.get("report_sections"),
        "confidence": values.get("confidence"),
        "uncertainties": values.get("uncertainties", []) or [],
        "citations": values.get("citations", []) or [],
        "findings": values.get("findings", []) or [],
        "debate": values.get("debate", []) or [],
        "plan": values.get("plan", []) or [],
        "target": values.get("target", "") or "",
        # {revision, action, feedback} per review decision — lets the UI rebuild the
        # change history after a reload.
        "review_history": values.get("review_history", []) or [],
    }


_SERVER_ONLY = frozenset({"evidence_text", "evidence_id"})


def client_view(data: dict) -> dict:
    """``data`` without server-only finding fields (safe on any event payload)."""
    findings = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(findings, list):
        return data
    slim = [{k: v for k, v in f.items() if k not in _SERVER_ONLY} if isinstance(f, dict) else f
            for f in findings]
    return {**data, "findings": slim}
