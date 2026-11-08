"""The learning loop: policies, run records, diagnosis, proposals, paired replay,
the release decision, automatic rollback and the /llmops API — all offline."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atlas.core.llmops import improver as I
from atlas.core.llmops.diagnose import attribute_feedback, diagnose_record, open_issues
from atlas.core.llmops.policy import (
    MAX_LESSONS,
    TOP_K_RANGE,
    Policy,
    PolicyStore,
    prompt_block,
)
from atlas.core.llmops.proposer import propose
from atlas.core.llmops.records import RunRecords, build_record, review_outcome
from atlas.core.llmops.replay import Trial, benchmark
from atlas.core.llmops.store import DocumentStore

VERSIONS = {"fundamentals": 1, "news_sentiment": 1, "risk": 1, "market": 1, "synthesizer": 1}
GOOD_FINDING = {"agent": "fundamentals", "claim": "Revenue reached $4.2 billion in fiscal 2025, "
                "up 28% year over year.", "citation": "Helios 10-K (sec_edgar#0)",
                "evidence_text": "Total revenue was $4.2 billion in fiscal 2025, up 28%."}


@pytest.fixture
def stores(tmp_path):
    return {"records": RunRecords(root=tmp_path), "policies": PolicyStore(root=tmp_path),
            "experiments": DocumentStore("experiment", root=tmp_path)}


def record(thread_id="t1", *, target="Helios Robotics", history=(), status="auto_approved",
           scores=None, agents=None, findings=None, versions=None):
    values = {"query": f"Evaluate {target}", "target": target, "review_status": status,
              "review_history": list(history),
              "findings": findings if findings is not None else [GOOD_FINDING],
              "debate": [{"role": "bull", "text": "Growing fast."}]}
    s = None
    if scores or agents:
        s = {"faithfulness": 0.9, "relevancy": 0.9, "context_precision": 0.9,
             "citation_accuracy": 0.9, "citation_coverage": 1.0, "overall": 0.9,
             "quality": "good", "agents": agents or {}, "report_check": {}, **(scores or {})}
    return build_record(values, thread_id=thread_id, scores=s,
                        policy_versions=versions or dict(VERSIONS))


# ---------------------------------------------------------------- policies

def test_policy_versions_release_and_roll_back(tmp_path):
    store = PolicyStore(root=tmp_path)
    assert store.active_version("risk") == 1
    v2 = store.release("risk", Policy(lessons=["Quantify each risk."], top_k=6), notes="test")
    assert v2 == 2 and store.active("risk").lessons == ["Quantify each risk."]
    assert PolicyStore(root=tmp_path).active("risk").top_k == 6  # durable
    assert store.rollback("risk") == 1
    assert store.active("risk").lessons == []
    assert [v["version"] for v in store.versions("risk")] == [1, 2]  # history is kept


def test_policies_are_bounded():
    p = Policy(lessons=[f"rule {i}" for i in range(20)], top_k=99).bounded()
    assert len(p.lessons) == MAX_LESSONS and p.lessons[-1] == "rule 19"
    assert p.top_k == TOP_K_RANGE[1]


def test_prompt_block_renders_lessons_and_exemplars():
    assert prompt_block(Policy()) == ""
    block = prompt_block(Policy(lessons=["Date every event."],
                                exemplars=[{"claim": "Revenue rose 28%."}]))
    assert "Date every event." in block and "Revenue rose 28%." in block


def test_specialists_and_writer_read_the_active_policy(monkeypatch, tmp_path):
    from atlas.core.agents import specialists as SP
    from atlas.core.agents import synthesizer as SY

    seen = {}
    monkeypatch.setattr(SP, "llm_ready", lambda: True)
    monkeypatch.setattr(SP, "chat", lambda prompt, *, system=None, **kw:
                        seen.setdefault("system", system) and "[]")
    SP.extract_findings("risk", {"query": "Assess Helios", "target": "Helios"}, [],
                        Policy(lessons=["Quantify each risk."]))
    assert "Quantify each risk." in seen["system"]
    assert "Report rule." in SY.system_prompt(Policy(system="Base.", lessons=["Report rule."]))


# ---------------------------------------------------------------- records & diagnosis

def test_review_outcome():
    assert review_outcome("approved", []) == "approved"
    assert review_outcome("approved", [{"action": "revise"}]) == "revised"
    assert review_outcome("rejected", []) == "rejected"
    assert review_outcome("auto_approved", []) == "none"


@pytest.mark.parametrize("feedback,section,component", [
    ("Add the debt maturity profile", "", "risk"),
    ("Who are the main competitors?", "", "market"),
    ("Show revenue and margin trends", "", "fundamentals"),
    ("Give dates for the latest news", "", "news_sentiment"),
    ("Make it shorter and clearer", "", "synthesizer"),
    ("This is wrong", "risks", "risk"),  # an explicit section beats keywords
])
def test_feedback_is_attributed_to_the_responsible_component(feedback, section, component):
    assert attribute_feedback(feedback, section) == component


def test_human_feedback_outweighs_automatic_scores():
    r = record(history=[{"revision": 0, "action": "reject", "feedback": "Debt is missing",
                         "section": "risks"}],
               status="rejected", scores={"faithfulness": 0.5},
               agents={"market": {"groundedness": 0.4, "richness": 1.0, "score": 0.5}})
    issues = open_issues([r])
    assert issues[0]["component"] == "risk" and issues[0]["kind"] == "reviewer_feedback"
    kinds = {(i["component"], i["kind"]) for i in issues}
    assert ("synthesizer", "unsupported_statements") in kinds
    assert ("market", "ungrounded_findings") in kinds


def test_an_agent_outage_is_not_blamed_on_its_policy():
    r = record(findings=[{"agent": "risk", "claim": "x", "citation": "n/a",
                          "unavailable": True}],
               agents={"risk": {"groundedness": 0.0, "richness": 0.0, "score": 0.0}})
    assert not [i for i in diagnose_record(r) if i.component == "risk"]


# ---------------------------------------------------------------- proposals

def test_thin_output_proposes_deeper_retrieval_then_a_lesson_at_the_ceiling():
    issue = {"component": "market", "kind": "thin_findings", "lever": "retrieval",
             "examples": ["1 solid finding"], "example": "1 solid finding"}
    p = propose(issue, Policy(top_k=4), [])
    assert p.lever == "retrieval" and p.policy.top_k == 6
    at_max = propose(issue, Policy(top_k=TOP_K_RANGE[1]), [])
    assert at_max.lever == "lesson" and at_max.policy.lessons


def test_exemplars_come_only_from_human_approved_runs():
    approved = record("a", status="approved",
                      agents={"fundamentals": {"score": 0.9, "groundedness": 1, "richness": 1}})
    unreviewed = record("b", agents={"fundamentals": {"score": 0.95}})
    issue = {"component": "fundamentals", "kind": "missing_exemplars", "lever": "exemplars"}
    p = propose(issue, Policy(), [unreviewed, approved])
    assert p.lever == "exemplars"
    assert p.policy.exemplars[0]["claim"].startswith("Revenue reached $4.2 billion")
    assert propose(issue, Policy(), [unreviewed]) is None


def test_a_duplicate_lesson_is_not_proposed():
    issue = {"component": "synthesizer", "kind": "off_question", "lever": "lesson",
             "examples": ["relevancy 0.3"], "example": "relevancy 0.3"}
    first = propose(issue, Policy(), [])
    assert propose(issue, first.policy, []) is None


# ---------------------------------------------------------------- decision & replay

@pytest.mark.parametrize("deltas,released", [
    ([0.05, 0.06, 0.04], True),     # consistent gain
    ([0.20, 0.30, -0.15], False),   # big average, but one question got much worse
    ([0.01, 0.02, 0.00], False),    # noise-sized gain
    ([0.30], False),                # one lucky trial is not evidence
])
def test_paired_decision_rule(deltas, released):
    trials = [Trial(f"q{i}", "", 0.5, 0.5 + d) for i, d in enumerate(deltas)]
    assert I.decide(trials)[0] is released


def test_benchmark_picks_distinct_companies_issue_runs_first():
    rs = [record("a", target="A"), record("b", target="A"), record("c", target="B"),
          record("d", target="C")]
    picked = benchmark(rs, 2, prefer=["d"])
    assert [r["thread_id"] for r in picked] == ["d", "a"]


# ---------------------------------------------------------------- the loop end to end

def _fill(stores, n=3):
    for i, target in enumerate(["Helios Robotics", "Aster Dynamics", "Vega Labs"][:n]):
        stores["records"].save(record(
            f"run{i}", target=target, status="revised",
            history=[{"revision": 0, "action": "revise", "feedback": "Quantify the debt risk",
                      "section": "risks"}, {"revision": 1, "action": "approve", "feedback": ""}]))


def test_improve_releases_a_change_that_wins_on_every_question(stores):
    _fill(stores)
    out = I.improve(**stores, runner=lambda comp, r, base, cand: (0.6, 0.7))
    exp = out["experiment"]
    assert exp["decision"] == "released" and exp["component"] == "risk"
    assert exp["lever"] == "lesson" and len(exp["trials"]) == 3
    assert exp["version_before"] == 1 and exp["version_after"] == 2
    assert stores["policies"].active("risk").lessons  # live policy changed
    assert stores["experiments"].get(exp["id"])["decision"] == "released"


def test_improve_rejects_a_change_and_keeps_the_active_policy(stores):
    _fill(stores)
    out = I.improve(**stores, runner=lambda comp, r, base, cand: (0.7, 0.68))
    assert out["experiment"]["decision"] == "rejected"
    assert stores["policies"].active_version("risk") == 1
    assert stores["policies"].active("risk").lessons == []
    # The same pattern is not retried right away.
    again = I.improve(**stores, runner=lambda comp, r, base, cand: (0.7, 0.9))
    assert (again["experiment"] or {}).get("issue_kind") != "reviewer_feedback" or \
        again["experiment"]["component"] != "risk"


def test_improve_needs_several_companies_to_test_fairly(stores):
    _fill(stores, n=1)
    out = I.improve(**stores, runner=lambda *a: (0.5, 0.9))
    assert out["experiment"] is None and "at least" in out["message"]


def test_failed_trials_are_skipped_not_fatal(stores):
    _fill(stores)
    calls = {"n": 0}

    def flaky(comp, r, base, cand):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Groq 429")
        return 0.6, 0.7

    exp = I.improve(**stores, runner=flaky)["experiment"]
    assert len(exp["trials"]) == 2 and exp["decision"] == "released"


def test_live_regression_rolls_a_release_back(stores):
    pol = stores["policies"]
    v2 = pol.release("market", Policy(lessons=["Name rivals."]), notes="experiment: test")
    for i in range(3):
        stores["records"].save(record(f"old{i}", scores={"overall": 0.8},
                                      versions={**VERSIONS, "market": 1}))
        stores["records"].save(record(f"new{i}", scores={"overall": 0.6},
                                      versions={**VERSIONS, "market": v2}))
    events = I.check_regressions(**stores)
    assert events and events[0]["decision"] == "rolled_back"
    assert pol.active_version("market") == 1


def test_no_rollback_without_enough_live_evidence(stores):
    pol = stores["policies"]
    v2 = pol.release("market", Policy(lessons=["Name rivals."]), notes="experiment: test")
    stores["records"].save(record("new0", scores={"overall": 0.1},
                                  versions={**VERSIONS, "market": v2}))
    assert I.check_regressions(**stores) == []
    assert pol.active_version("market") == v2


# ---------------------------------------------------------------- API

def test_llmops_api(monkeypatch, stores):
    from atlas.main import app
    from atlas.routers import llmops as R

    monkeypatch.setattr(R, "overview", lambda: I.overview(**stores))
    monkeypatch.setattr(R, "get_policies", lambda: stores["policies"])
    client = TestClient(app)

    body = client.get("/llmops/overview").json()
    assert {c["name"] for c in body["components"]} == {
        "fundamentals", "news_sentiment", "risk", "market", "synthesizer"}
    assert body["runs"]["total"] == 0 and body["experiments"] == []

    stores["policies"].release("risk", Policy(top_k=6), notes="experiment: t")
    hist = client.get("/llmops/components/risk").json()
    assert hist["active_version"] == 2 and len(hist["versions"]) == 2
    assert client.post("/llmops/rollback", json={"component": "risk"}).json()["version"] == 1
    assert client.get("/llmops/components/nope").status_code == 404


def test_replay_drives_the_real_agents_offline():
    """The pair runners wire into the real specialist and writer (stubbed LLM): the same
    inputs under two policies give two scores, and identical stubs mean no gain."""
    from atlas.core.llmops.replay import paired_trials

    rec = record("r1", target="Helios Robotics")
    risk = paired_trials("risk", Policy(), Policy(top_k=6), [rec])
    writer = paired_trials("synthesizer", Policy(system="Base."),
                           Policy(system="Base.", lessons=["Answer first."]), [rec])
    for trials in (risk, writer):
        assert len(trials) == 1
        t = trials[0]
        assert 0.0 <= t.baseline <= 1.0 and 0.0 <= t.candidate <= 1.0
    assert risk[0].delta == 0.0  # offline stubs are policy-blind
