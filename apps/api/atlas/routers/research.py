"""/research — run the multi-agent due-diligence desk (design §4).

* ``GET /research/stream`` starts a run and streams per-agent updates over SSE (one
  event per graph node, so the UI can light up agents live). With ``review=1`` the
  run pauses after drafting and ends with ``review_required``; otherwise ``final``.
* ``GET /research/resume`` continues a paused run with the reviewer's decision.
  Both are GET because the browser ``EventSource`` only supports GET.
* Bad input or a bad thread state never yields a plain 4xx on the GET streams (the
  browser ``EventSource`` can't read it): the response is a 200 SSE stream with one
  ``error`` event ``{error, code}``.
* ``POST /research/sync`` runs to completion with review off (unchanged contract,
  plus ``report_sections``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from ..config import get_settings
from ..core.graph import (
    RunNotPausedError,
    research,
    resume_research,
    run_research,
    thread_status,
)

router = APIRouter(prefix="/research", tags=["research"])
log = logging.getLogger("atlas.research")

MAX_FEEDBACK_CHARS = 2000
MIN_QUERY_CHARS = 3
MAX_QUERY_CHARS = 500
MAX_THREAD_ID_CHARS = 128
_TRUE, _FALSE = {"1", "true", "yes", "on"}, {"0", "false", "no", "off", ""}
_FRIENDLY_ERROR = ("The research run hit an error (often the free-tier rate limit). "
                   "Please try again in a few seconds.")


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="The due-diligence question")
    thread_id: str = Field("default", description="Run id (for checkpointing/resume)")


@router.post("/sync")
async def research_sync(req: ResearchRequest) -> dict:
    if not get_settings().llm_configured:
        return {"error": "GROQ_API_KEY not configured", "report": "", "confidence": None}
    try:
        return await run_in_threadpool(research, req.query, thread_id=req.thread_id)
    except Exception as e:  # degrade gracefully instead of a bare 500
        log.warning("research run failed: %s", e)
        return {"error": _FRIENDLY_ERROR, "report": "", "report_sections": None,
                "confidence": None}


def _sse(events: Iterator[dict]) -> AsyncIterator[dict]:
    """Serialize graph events as SSE; a failure mid-run becomes a friendly ``error``."""
    async def gen():
        try:
            async for ev in iterate_in_threadpool(events):
                yield {"event": ev["event"], "data": json.dumps(ev["data"], default=str)}
        except Exception as exc:
            log.warning("research stream failed: %s: %s", type(exc).__name__, exc)
            yield {"event": "error",
                   "data": json.dumps({"error": _FRIENDLY_ERROR, "code": "run_failed"})}
    return gen()


def _error_stream(error: str, code: str) -> EventSourceResponse:
    """A 200 SSE response carrying one ``error`` event, then closing.

    The browser ``EventSource`` cannot read the body of a non-200 response, so a plain
    404/422 would reach the user as a generic connection failure. Bad requests and
    bad states are therefore reported in-band with a machine-readable ``code``.
    """
    async def gen():
        yield {"event": "error", "data": json.dumps({"error": error, "code": code})}
    return EventSourceResponse(gen())


def _not_configured() -> EventSourceResponse:
    return _error_stream("GROQ_API_KEY not configured", "not_configured")


@router.get("/stream")
async def research_stream(
    q: str | None = None,
    thread_id: str | None = None,
    review: str | None = None,
):
    """Server-Sent Events: one message per agent node, ending with ``review_required``
    (paused, when ``review=1``) or ``final``. Invalid input → one ``error`` event."""
    # Validated by hand (all params optional) so FastAPI's automatic 422 can't
    # pre-empt the in-band SSE error the browser is able to read.
    query = (q or "").strip()
    if len(query) < MIN_QUERY_CHARS:
        return _error_stream(f"Please enter a question of at least {MIN_QUERY_CHARS} "
                             "characters.", "bad_request")
    if len(query) > MAX_QUERY_CHARS:
        return _error_stream(f"The question is too long (max {MAX_QUERY_CHARS} "
                             "characters).", "bad_request")
    thread = (thread_id or "default").strip()
    if not thread or len(thread) > MAX_THREAD_ID_CHARS:
        return _error_stream("Invalid thread id.", "bad_request")
    flag = (review or "0").strip().lower()
    if flag not in _TRUE | _FALSE:
        return _error_stream("review must be 1 or 0.", "bad_request")
    # Same precondition as /sync: signal (don't silently stub) when unconfigured.
    if not get_settings().llm_configured:
        return _not_configured()
    return EventSourceResponse(_sse(run_research(query, thread_id=thread,
                                                 require_review=flag in _TRUE)))


_STATE_ERRORS = {
    "finished": ("This research run has already finished; there is nothing to review.",
                 "not_paused"),
    "unknown": ("No research run was found for this thread. It may have expired — "
                "please start a new run.", "unknown_thread"),
}


@router.get("/resume")
async def research_resume(
    thread_id: str | None = None,
    action: str | None = None,
    feedback: str | None = None,
):
    """Resume a run paused at human review. Emits the same events as /stream and ends
    with another ``review_required`` (new draft) or ``final``. Invalid input or a
    thread that is not waiting for review → one ``error`` event with a ``code``."""
    thread = (thread_id or "").strip()
    act = (action or "").strip().lower()
    fb = (feedback or "").strip()
    if not thread or len(thread) > MAX_THREAD_ID_CHARS:
        return _error_stream("A valid thread id is required to resume a run.", "bad_request")
    if act not in ("approve", "revise"):
        return _error_stream("action must be 'approve' or 'revise'.", "bad_request")
    if act == "revise" and not fb:
        return _error_stream("Please describe the changes you want.", "bad_request")
    if len(fb) > MAX_FEEDBACK_CHARS:
        return _error_stream(f"Feedback is too long (max {MAX_FEEDBACK_CHARS} characters).",
                             "bad_request")
    status = await run_in_threadpool(thread_status, thread)
    if status != "paused":
        return _error_stream(*_STATE_ERRORS.get(status, _STATE_ERRORS["finished"]))
    if not get_settings().llm_configured:
        return _not_configured()
    try:
        events = await run_in_threadpool(resume_research, thread,
                                         {"action": act, "feedback": fb})
    except RunNotPausedError:  # raced with another resume of the same thread
        return _error_stream(*_STATE_ERRORS["finished"])
    except ValueError as exc:
        return _error_stream(str(exc), "bad_request")
    return EventSourceResponse(_sse(events))
