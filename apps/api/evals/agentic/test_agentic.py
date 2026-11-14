"""End-to-end agentic tests: one live run per persona scenario, two layers of checks.

1. **Deterministic contract** — the run researched the right company for the right
   reader, produced the sections that reader needs, and its citations resolve to the
   evidence it actually retrieved (Atlas's own statement-level verifier).
2. **Judged quality (DeepEval)** — G-Eval rubrics for "answers this reader's question",
   "surfaces negatives" and a scenario-specific persona rubric, plus DeepEval's
   Faithfulness metric against the cited evidence (retrieval context).

Thresholds are deliberately modest (0.6): the free-tier model is the judge too, and
the point is catching regressions and outright failures, not grading prose.
"""

from __future__ import annotations

import uuid

import pytest
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from atlas.core.graph import research
from atlas.core.llmops.report_verify import verify_report

from .judge import GroqJudge
from .scenarios import SCENARIOS, Scenario

THRESHOLD = 0.6


def _present(sections: dict, key: str) -> bool:
    value = sections.get(key)
    if isinstance(value, dict):
        return any(v for k, v in value.items() if k not in ("overall", "overlap", "asker"))
    return bool(value)


def _metrics(s: Scenario, judge: GroqJudge) -> list:
    io = [SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT]
    return [
        GEval(name="Answers the reader's question", evaluation_params=io, model=judge,
              threshold=THRESHOLD, async_mode=False,
              criteria="Does the output give a direct, specific answer to the input question "
                       "for the kind of reader asking it, instead of generic company facts? "
                       "Penalize answers that research the wrong company."),
        # Explicit steps: with criteria alone the judge invented its own steps and once
        # marked a report down because the *question* named no negatives.
        GEval(name="Surfaces negatives", evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
              model=judge, threshold=THRESHOLD, async_mode=False,
              evaluation_steps=[
                  "List the statements in the report that describe weaknesses, customer "
                  "complaints, risks, red flags or explicitly unknown facts about the "
                  "company being researched.",
                  "Check that each is specific to this company (not generic boilerplate) "
                  "and carries a source citation or is clearly marked as uncertain.",
                  "Score high when there are at least two specific, sourced negatives or "
                  "honest unknowns; score low when the report is one-sided praise.",
              ]),
        GEval(name="Persona fit", evaluation_params=io, model=judge, threshold=THRESHOLD,
              async_mode=False, criteria=s.persona_criteria),
        FaithfulnessMetric(model=judge, threshold=THRESHOLD, async_mode=False,
                           include_reason=True),
    ]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_agent_handles_the_scenario(scenario: Scenario, record_result):
    out = research(scenario.question, thread_id=f"eval-{uuid.uuid4().hex[:8]}", record=False)
    sections = out.get("report_sections") or {}
    brief = sections.get("brief") or {}
    report = out.get("report") or ""
    findings = out.get("findings") or []

    # ---- 1. deterministic contract ----
    problems: list[str] = []
    if scenario.subject_contains not in (out.get("target") or "").lower():
        problems.append(f"researched {out.get('target')!r}, expected {scenario.subject_contains}")
    asker = (brief.get("asker") or "").lower()
    if scenario.asker_contains and scenario.asker_contains not in asker:
        problems.append(f"asker {brief.get('asker')!r}, expected {scenario.asker_contains}")
    if brief.get("persona") != scenario.persona:
        problems.append(f"persona {brief.get('persona')!r}, expected {scenario.persona}")
    missing = [k for k in scenario.must_have_sections if not _present(sections, k)]
    if missing:
        problems.append(f"missing sections: {missing}")
    check = verify_report(report, findings, use_llm=False)
    fabricated = sorted({k for r in check["statements"] for k in r["unknown_keys"]})
    if fabricated:
        problems.append(f"citations to evidence that was never retrieved: {fabricated[:5]}")

    # ---- 2. judged quality ----
    judge = GroqJudge()
    evidence = [f.get("evidence_text") for f in findings if f.get("evidence_text")]
    case = LLMTestCase(input=scenario.question, actual_output=report,
                       retrieval_context=evidence[:30] or ["(no evidence retrieved)"])
    metrics = _metrics(scenario, judge)
    judged_error = None
    try:
        assert_test(case, metrics, run_async=False)
    except AssertionError as exc:
        judged_error = str(exc)[:600]
    except Exception as exc:  # the judge itself broke: still record what the agent did
        judged_error = f"judge error: {type(exc).__name__}: {str(exc)[:400]}"

    scores = {m.__name__ if hasattr(m, "__name__") else m.name: float(m.score or 0.0)
              for m in metrics}
    scores.update({"faithfulness_atlas": check["faithfulness"],
                   "citation_accuracy_atlas": check["citation_accuracy"]})
    record_result({"id": scenario.id, "passed": not problems and judged_error is None,
                   "metrics": scores, "problems": problems, "judged_error": judged_error,
                   "target": out.get("target"), "brief": brief,
                   "confidence": out.get("confidence"), "report": report,
                   "miscited": check["miscited"], "unsupported": check["unsupported"]})
    assert not problems, "; ".join(problems)
    assert judged_error is None, judged_error
