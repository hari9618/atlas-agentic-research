"""Human-in-the-loop review flow (design §3/§4), fully offline.

Drives the real graph through the HTTP layer: stream with review → paused at
``review_required``; resume with "revise" → a new draft (revision 1) paused again;
resume with "approve" → ``final``. Plus the revision cap, input validation, and the
guarantee that ``research()`` (sync) never pauses.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

import atlas.core.graph as G
from atlas.config import get_settings
from atlas.main import app
from atlas.routers import research as research_router

client = TestClient(app)


def _tid() -> str:
    return f"test-review-{uuid.uuid4().hex[:10]}"


def _events(resp) -> list[tuple[str, dict]]:
    """Parse an SSE body into [(event, data)]."""
    out, event = [], None
    for line in resp.text.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and event:
            out.append((event, json.loads(line.split(":", 1)[1].strip())))
            event = None
    return out


@pytest.fixture(autouse=True)
def _fresh_sse_exit_event():
    """sse-starlette caches a process-global anyio.Event bound to the first event loop;
    each TestClient request runs a new loop, so reset it (known TestClient workaround)."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit_event = None


def _get(url: str, **params):
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    return client.get(url, params=params)


@pytest.fixture
def llm_configured(monkeypatch):
    """The router refuses to run without a key; pretend one is set (LLM stays offline)."""
    class _S:
        llm_configured = True

    monkeypatch.setattr(research_router, "get_settings", lambda: _S())


def test_hitl_flow_through_the_router(llm_configured):
    tid = _tid()
    r = _get("/research/stream", q="Should I invest in Helios Robotics?", thread_id=tid, review=1)
    evs = _events(r)
    names = [e for e, _ in evs]
    assert names[0] == "start" and names[-1] == "review_required"
    assert "final" not in names and "remember" not in names
    draft = evs[-1][1]
    assert draft["thread_id"] == tid and draft["revision"] == 0
    assert draft["review_status"] == "pending"
    assert draft["report_sections"]["company"] == "Helios Robotics"
    assert draft["target"] == "Helios Robotics"
    assert draft["review_history"] == []

    r = _get("/research/resume", thread_id=tid, action="revise",
             feedback="Add more detail on competitors")
    evs = _events(r)
    names = [e for e, _ in evs]
    assert names[-1] == "review_required"
    assert "revise_research" in names and "synthesize" in names
    second = evs[-1][1]
    assert second["revision"] == 1
    assert any(f["agent"] == "reviewer_followup" for f in second["findings"])
    assert "Add more detail on competitors" in second["report"]
    assert second["review_history"] == [
        {"revision": 0, "action": "revise", "feedback": "Add more detail on competitors"}]

    r = _get("/research/resume", thread_id=tid, action="approve")
    evs = _events(r)
    names = [e for e, _ in evs]
    assert names[-1] == "final" and "remember" in names
    final = evs[-1][1]
    assert final["review_status"] == "approved" and final["revision"] == 1
    assert final["report_sections"] and final["report"]
    # The payload carries the change history so the UI can rebuild it after a reload.
    assert [h["action"] for h in final["review_history"]] == ["revise", "approve"]

    # The run is finished: resuming again is an in-band SSE error, not a silent re-run.
    r = _get("/research/resume", thread_id=tid, action="approve")
    assert _single_error(r)["code"] == "not_paused"


def test_revision_cap_auto_approves_with_a_note(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_revisions", 1)
    tid = _tid()
    evs = list(G.run_research("Assess Helios Robotics", thread_id=tid, require_review=True))
    assert evs[-1]["event"] == "review_required"
    evs = list(G.resume_research(tid, {"action": "revise", "feedback": "More risks"}))
    final = evs[-1]
    assert final["event"] == "final"  # cap reached → no second pause
    assert final["data"]["review_status"] == "auto_approved" and final["data"]["revision"] == 1
    assert any("Revision limit reached" in u for u in final["data"]["uncertainties"])
    assert "Revision limit reached" in final["data"]["report"]


def test_sync_research_never_pauses():
    out = G.research("Evaluate Helios Robotics", thread_id=_tid())
    assert out["review_status"] == "auto_approved" and out["revision"] == 0
    assert out["report_sections"] and out["report"]


def test_reused_thread_does_not_leak_previous_findings():
    tid = _tid()
    first = G.research("Evaluate Helios Robotics", thread_id=tid)
    second = G.research("Evaluate Aster Dynamics", thread_id=tid)
    assert len(second["findings"]) == len(first["findings"])
    assert all("Aster" in f["claim"] for f in second["findings"])


def _single_error(resp) -> dict:
    """EventSource can't read non-200 bodies: bad input must be a 200 + one error event."""
    assert resp.status_code == 200
    evs = _events(resp)
    assert len(evs) == 1 and evs[0][0] == "error", evs
    assert evs[0][1]["error"]  # human-readable reason
    return evs[0][1]


@pytest.mark.parametrize("params,code", [
    ({"thread_id": "x", "action": "delete"}, "bad_request"),
    ({"thread_id": "x"}, "bad_request"),                                  # missing action
    ({"action": "approve"}, "bad_request"),                               # missing thread
    ({"thread_id": "x", "action": "revise"}, "bad_request"),              # no feedback
    ({"thread_id": "x", "action": "revise", "feedback": "   "}, "bad_request"),
    ({"thread_id": "x", "action": "revise", "feedback": "x" * 5000}, "bad_request"),
    ({"thread_id": "never-seen-thread-id", "action": "approve"}, "unknown_thread"),
])
def test_resume_errors_are_in_band_sse(params, code):
    assert _single_error(_get("/research/resume", **params))["code"] == code


@pytest.mark.parametrize("params", [
    {}, {"q": ""}, {"q": "ab"}, {"q": "x" * 600}, {"q": "Assess Helios", "review": "maybe"},
])
def test_stream_errors_are_in_band_sse(params):
    assert _single_error(_get("/research/stream", **params))["code"] == "bad_request"


def test_resume_engine_validation():

    with pytest.raises(ValueError):
        G.resume_research("x", {"action": "revise", "feedback": "  "})
    with pytest.raises(G.RunNotPausedError):
        G.resume_research(f"never-{uuid.uuid4().hex}", {"action": "approve"})


def test_stream_failure_becomes_a_friendly_error_event(llm_configured, monkeypatch):
    def broken(*a, **k):
        yield {"event": "start", "data": {}}
        raise RuntimeError("internal detail that must not leak")

    monkeypatch.setattr(research_router, "run_research", broken)
    r = _get("/research/stream", q="Assess Helios", thread_id=_tid())
    evs = _events(r)
    assert evs[-1][0] == "error" and evs[-1][1]["code"] == "run_failed"
    assert "internal detail" not in evs[-1][1]["error"]


def test_reject_ends_the_run_without_remembering_it(llm_configured):
    tid = _tid()
    assert _events(_get("/research/stream", q="Assess Helios Robotics", thread_id=tid,
                        review=1))[-1][0] == "review_required"
    evs = _events(_get("/research/resume", thread_id=tid, action="reject",
                       feedback="Numbers look unreliable", section="financials"))
    names = [e for e, _ in evs]
    assert names[-1] == "final"
    assert "remember" not in names  # a rejected report never becomes episodic memory
    final = evs[-1][1]
    assert final["review_status"] == "rejected"
    assert final["review_history"] == [{"revision": 0, "action": "reject",
                                        "feedback": "Numbers look unreliable",
                                        "section": "financials"}]


def test_section_targeted_revision_reaches_the_writer(llm_configured):
    tid = _tid()
    _events(_get("/research/stream", q="Assess Helios Robotics", thread_id=tid, review=1))
    evs = _events(_get("/research/resume", thread_id=tid, action="revise",
                       feedback="Name the main rivals", section="competitors"))
    draft = evs[-1][1]
    assert evs[-1][0] == "review_required" and draft["revision"] == 1
    assert draft["review_history"][-1] == {"revision": 0, "action": "revise",
                                           "feedback": "Name the main rivals",
                                           "section": "competitors"}


def test_unknown_review_section_is_rejected_in_band():
    r = _get("/research/resume", thread_id="x", action="revise", feedback="more",
             section="not_a_section")
    assert _single_error(r)["code"] == "bad_request"


def test_finished_runs_are_recorded_for_the_learning_loop(llm_configured):
    from atlas.core.llmops.records import get_records

    tid = _tid()
    _events(_get("/research/stream", q="Assess Helios Robotics", thread_id=tid, review=1))
    _events(_get("/research/resume", thread_id=tid, action="revise", feedback="More on debt",
                 section="risks"))
    _events(_get("/research/resume", thread_id=tid, action="approve"))
    from atlas.core.graph import drain_recorder

    drain_recorder()  # runs are recorded off the stream, in the background
    # Records keep the internal, user-scoped run id (see routers/research.scoped_thread).
    record = next(r for r in get_records().recent(50) if r["thread_id"] == f"test-user:{tid}")
    assert record["review"]["outcome"] == "revised"
    assert record["review"]["history"][0]["section"] == "risks"
    assert set(record["policy_versions"]) == {"fundamentals", "news_sentiment", "risk",
                                              "market", "synthesizer"}
    assert record["findings"]  # kept for replaying the synthesizer


def test_streamed_events_omit_server_only_evidence(llm_configured):
    r = _get("/research/stream", q="Assess Helios Robotics", thread_id=_tid(), review=1)
    for _, data in _events(r):
        for f in data.get("findings") or []:
            assert "evidence_text" not in f and "evidence_id" not in f
