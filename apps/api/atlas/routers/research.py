"""/research — run the multi-agent due-diligence desk (design §4).

* ``GET /research/stream`` starts a run and streams per-agent updates over SSE (one
  event per graph node, so the UI can light up agents live). With ``review=1`` the
  run pauses after drafting and ends with ``review_required``; otherwise ``final``.
* ``GET /research/resume`` continues a paused run with the reviewer's decision:
  ``approve``, ``revise`` (feedback, optionally aimed at one report ``section``) or
  ``reject`` (optional reason; the report is not remembered).
  Both are GET because the browser ``EventSource`` only supports GET.
* Bad input or a bad thread state never yields a plain 4xx on the GET streams (the
  browser ``EventSource`` can't read it): the response is a 200 SSE stream with one
  ``error`` event ``{error, code}``.
* ``POST /research/sync`` runs to completion with review off (unchanged contract,
  plus ``report_sections``).

Access control: every endpoint needs a signed-in user (``Authorization: Bearer``).
Run ids are namespaced by user id before they reach the graph, so one user can never
resume, read or race another user's run, whatever id they send. Auth, rate-limit and
capacity failures are real HTTP statuses (401/409/429/503 with ``Retry-After``) — the
web client reads streams with ``fetch``, so it can see them; input problems stay
in-band so the stream contract is unchanged.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator

from fastapi import APIRouter, Depends
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
from ..core.payload import client_view
from ..security import limits
from ..security.deps import Principal, current_user
from ..security.limits import RunTicket, admit_run, enforce, plan_for

router = APIRouter(prefix="/research", tags=["research"])
log = logging.getLogger("atlas.research")

MAX_FEEDBACK_CHARS = 2000
MIN_QUERY_CHARS = 3
MAX_QUERY_CHARS = 500
MAX_THREAD_ID_CHARS = 128
# Report sections a reviewer may aim feedback at (report_schema keys).
REVIEW_SECTIONS = frozenset({
    "headline", "executive_summary", "company_overview", "financials",
    "market_position", "competitors", "recent_developments", "sentiment", "risks",
    "bull_case", "bear_case", "outlook", "bottom_line", "uncertainties",
    "verdict", "snapshot", "strengths", "weaknesses", "pricing", "head_to_head",
    "custom_answers",
})
_TRUE, _FALSE = {"1", "true", "yes", "on"}, {"0", "false", "no", "off", ""}
_FRIENDLY_ERROR = ("The research run hit an error (often the free-tier rate limit). "
                   "Please try again in a few seconds.")


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=MAX_QUERY_CHARS,
                       description="The due-diligence question")
    thread_id: str = Field("default", max_length=MAX_THREAD_ID_CHARS,
                           description="Run id (for checkpointing/resume)")


def scoped_thread(user: Principal, thread_id: str) -> str:
    """The graph thread id for ``user``'s run ``thread_id`` (tenant isolation)."""
    return f"{user.id}:{thread_id}"


def _public(data: dict, thread_id: str) -> dict:
    """What the client sees: payload stripped (``client_view``) and its own run id back
    in place of the internal user-scoped one."""
    view = client_view(data)
    if isinstance(view, dict) and "thread_id" in view:
        view = {**view, "thread_id": thread_id}
    return view


async def _start_research(user: Principal) -> RunTicket:
    """Quota checks, then capacity: per-user plan, global LLM budget, run admission."""
    await enforce(plan_for(user.role).research, user.id, what="research runs")
    await enforce(limits.RESEARCH_GLOBAL, "all", what="research runs on Atlas right now")
    return await admit_run(user.id, user.role)


@router.post("/sync")
async def research_sync(req: ResearchRequest, user: Principal = Depends(current_user)) -> dict:
    if not get_settings().llm_configured:
        return {"error": "GROQ_API_KEY not configured", "report": "", "confidence": None}
    ticket = await _start_research(user)
    try:
        return _public(await run_in_threadpool(
            research, req.query, thread_id=scoped_thread(user, req.thread_id)), req.thread_id)
    except Exception as e:  # degrade gracefully instead of a bare 500
        log.warning("research run failed: %s", e)
        return {"error": _FRIENDLY_ERROR, "report": "", "report_sections": None,
                "confidence": None}
    finally:
        ticket.release()


def _sse(events: Iterator[dict], thread_id: str,
         ticket: RunTicket | None = None) -> AsyncIterator[dict]:
    """Serialize graph events as SSE; a failure mid-run becomes a friendly ``error``.

    The run's capacity ticket is released when the stream ends for any reason:
    finished, paused for review, failed, or the client went away (sse-starlette
    cancels the generator on disconnect, which runs the ``finally``)."""
    async def gen():
        try:
            async for ev in iterate_in_threadpool(events):
                yield {"event": ev["event"],
                       "data": json.dumps(_public(ev["data"], thread_id), default=str)}
        except Exception as exc:
            log.warning("research stream failed: %s: %s", type(exc).__name__, exc)
            yield {"event": "error",
                   "data": json.dumps({"error": _FRIENDLY_ERROR, "code": "run_failed"})}
        finally:
            if ticket is not None:
                ticket.release()
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
    user: Principal = Depends(current_user),
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
    ticket = await _start_research(user)
    return EventSourceResponse(_sse(run_research(query, thread_id=scoped_thread(user, thread),
                                                 require_review=flag in _TRUE),
                                    thread, ticket))


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
    section: str | None = None,
    user: Principal = Depends(current_user),
):
    """Resume a run paused at human review. Emits the same events as /stream and ends
    with another ``review_required`` (new draft) or ``final``. Invalid input or a
    thread that is not waiting for review → one ``error`` event with a ``code``."""
    thread = (thread_id or "").strip()
    act = (action or "").strip().lower()
    fb = (feedback or "").strip()
    sec = (section or "").strip()
    if not thread or len(thread) > MAX_THREAD_ID_CHARS:
        return _error_stream("A valid thread id is required to resume a run.", "bad_request")
    if act not in ("approve", "revise", "reject"):
        return _error_stream("action must be 'approve', 'revise' or 'reject'.", "bad_request")
    if sec and sec not in REVIEW_SECTIONS:
        return _error_stream("Unknown report section.", "bad_request")
    if act == "revise" and not fb:
        return _error_stream("Please describe the changes you want.", "bad_request")
    if len(fb) > MAX_FEEDBACK_CHARS:
        return _error_stream(f"Feedback is too long (max {MAX_FEEDBACK_CHARS} characters).",
                             "bad_request")
    public_thread, thread = thread, scoped_thread(user, thread)
    status = await run_in_threadpool(thread_status, thread)
    if status != "paused":
        return _error_stream(*_STATE_ERRORS.get(status, _STATE_ERRORS["finished"]))
    if not get_settings().llm_configured:
        return _not_configured()
    await enforce(plan_for(user.role).resume, user.id, what="review actions")
    ticket = await admit_run(user.id, user.role)
    try:
        events = await run_in_threadpool(resume_research, thread,
                                         {"action": act, "feedback": fb,
                                          "section": sec})
    except RunNotPausedError:  # raced with another resume of the same thread
        ticket.release()
        return _error_stream(*_STATE_ERRORS["finished"])
    except ValueError as exc:
        ticket.release()
        return _error_stream(str(exc), "bad_request")
    except BaseException:
        ticket.release()
        raise
    return EventSourceResponse(_sse(events, public_thread, ticket))
