"""The client-facing run payload (design §4 ``ResearchPayload``).

Built from graph state in one place so the SSE ``review_required`` / ``final`` events,
``/research/sync`` and the review interrupt all expose exactly the same shape.
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
