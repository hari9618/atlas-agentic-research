"""Regression tests for the evaluation / self-improvement audit.

Each test pins a bug found by running the evaluator on real reports:

* "faithfulness" was the share of findings' citation labels present in the report —
  1.0 on every real brief, true or not. It now verifies the brief's statements.
* findings carried only 500 chars of evidence, so true claims whose figures sat later
  in the chunk were scored "unsupported".
* gpt-oss cited with 【web_search#0】 brackets the UI and guardrails couldn't read.
* the optimizer's candidate prompt was served to every concurrent user run.
* retrieval context precision divided by distinct documents, capping it near 0.4.
"""

from __future__ import annotations

import math

import pytest

from atlas.core.agents import findings as F
from atlas.core.agents.report_schema import normalize_brackets, normalize_sections
from atlas.core.llmops import evaluate as E
from atlas.core.llmops import optimizer as O
from atlas.core.llmops.agent_eval import score_agent
from atlas.core.llmops.registry import PromptRegistry
from atlas.core.llmops.report_verify import report_statements, verify_report
from atlas.core.rag.types import Chunk, RetrievedChunk
from atlas.eval.ragas_eval import _num
from atlas.eval.retrieval_eval import average_precision

TENK = ("PART I BUSINESS Helios Robotics designs autonomous warehouse robots and fleet "
        "software for logistics customers worldwide. " * 4
        + "Total revenue was $4.2 billion in fiscal 2025, up 28% from $3.28 billion. "
        "The three largest customers accounted for 39% of revenue.")
NEWS = "Helios Robotics signed a $900 million five-year contract; shares rose 14%."
FINDINGS = [
    {"agent": "fundamentals", "claim": "Revenue was $4.2 billion, up 28%.",
     "citation": "Helios 10-K (sec_edgar#0)", "evidence_text": TENK},
    {"agent": "news_sentiment", "claim": "A $900 million contract was signed.",
     "citation": '"Helios deal" (news#0)', "evidence_text": NEWS},
]


# ---- report-level verification ---------------------------------------------------

def test_statements_skip_headings_uncertainties_and_placeholders():
    report = ("# Helios: Investor Brief\n\nOverall stance: **Neutral**\n\n## Executive Summary\n"
              "- Revenue reached $4.2 billion in fiscal 2025 [sec_edgar#0].\n"
              "- Not enough evidence yet.\n"
              "## What we're NOT sure about\n- Whether the margin expansion will last long.\n")
    st = report_statements(report)
    assert [s["text"] for s in st] == ["Revenue reached $4.2 billion in fiscal 2025"]
    assert st[0]["keys"] == ["sec_edgar#0"]


def test_true_statements_pass_and_invented_ones_fail():
    report = ("## Summary\n"
              "- Helios revenue reached $4.2 billion in fiscal 2025, up 28% "
              "[Helios 10-K (sec_edgar#0)].\n"
              "- Helios expects revenue of $9.9 billion by 2027 next year "
              "[Helios 10-K (sec_edgar#0)].\n")
    out = verify_report(report, FINDINGS, use_llm=False)
    assert out["faithfulness"] == 0.5 and out["citation_accuracy"] == 0.5
    assert out["unsupported"] == ["Helios expects revenue of $9.9 billion by 2027 next year"]


def test_miscitation_is_caught_even_when_the_fact_is_true():
    # True (it's in the 10-K) but attributed to the news article → grounded, miscited.
    report = "## Risks\n- The three largest customers accounted for 39% of revenue [news#0].\n"
    out = verify_report(report, FINDINGS, use_llm=False)
    assert out["faithfulness"] == 1.0
    assert out["citation_accuracy"] == 0.0
    assert out["miscited"] == ["The three largest customers accounted for 39% of revenue"]


def test_a_citation_to_unknown_evidence_counts_as_unsupported():
    report = "## Summary\n- Revenue reached $4.2 billion in fiscal 2025 [web_search#7].\n"
    out = verify_report(report, FINDINGS, use_llm=False)
    row = out["statements"][0]
    assert row["unknown_keys"] == ["web_search#7"] and row["cited"] == "unsupported"


def test_figures_late_in_a_chunk_are_found():
    # The regression: $4.2 billion sits past char 500 of the 10-K chunk.
    assert TENK.index("4.2 billion") > 500
    out = verify_report("## S\n- Revenue was $4.2 billion in fiscal 2025 [sec_edgar#0].\n",
                        FINDINGS, use_llm=False)
    assert out["faithfulness"] == 1.0


def test_parse_findings_keeps_the_whole_cited_chunk():
    chunk = RetrievedChunk(chunk=Chunk(chunk_id="c1", doc_id="d", text=TENK, source="sec_edgar",
                                       title="Helios 10-K", ordinal=0), score=1.0)
    out = F.parse_findings("fundamentals", '[{"claim": "x", "citation_index": 1}]', [chunk])
    assert out[0]["evidence_text"] == TENK  # not cut at 500 chars


# ---- citation brackets --------------------------------------------------------------

def test_fullwidth_citation_brackets_are_normalised():
    assert normalize_brackets("Big deal【web_search#3】【web_search#2】.") == \
        "Big deal[web_search#3][web_search#2]."
    s = normalize_sections({"company": "Reliance", "headline": "Growth【web_search#0】",
                            "executive_summary": ["Revenue up【web_search#1】"]})
    assert s["headline"] == "Growth[web_search#0]"
    assert s["executive_summary"] == ["Revenue up[web_search#1]"]


# ---- judges ------------------------------------------------------------------------

@pytest.mark.parametrize("reply,expected", [
    ("0.85", 0.85), (".7", 0.7), ("1", 1.0), ("Score: 0.6", 0.6), ("1.0", 1.0),
    ("0", 0.0), ("10/10", None), ("great", None),
])
def test_parse_score(reply, expected):
    assert E.parse_score(reply) == expected


def test_a_failing_judge_degrades_to_the_heuristic(monkeypatch):
    monkeypatch.setattr(E, "_llm_active", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("429")

    monkeypatch.setattr(E, "_judge", boom)
    rel = E._judge_relevancy("Helios Robotics revenue", "Helios Robotics revenue was $4.2B.")
    assert rel == 1.0  # heuristic, not a silent 0.0
    assert E._judge_context_precision("Helios Robotics revenue", FINDINGS) > 0.0


def test_quality_needs_faithfulness_not_just_a_good_average():
    assert E._quality_label(0.72, 0.54) == "ok"
    assert E._quality_label(0.85, 0.9) == "good"
    assert E._quality_label(0.6, 0.3) == "poor"


def test_agent_groundedness_reflects_evidence_support():
    good = score_agent([FINDINGS[0]])
    bad = score_agent([{**FINDINGS[0], "claim": "Revenue was $9.9 billion, up 70%."}])
    assert good["groundedness"] == 1.0 and bad["groundedness"] == 0.0


# ---- retrieval + ragas harness -------------------------------------------------------

def test_average_precision_is_rank_aware():
    assert average_precision([True, False, False]) == 1.0
    assert average_precision([False, True]) == 0.5
    assert average_precision([True, False, True]) == pytest.approx((1 + 2 / 3) / 2)
    assert average_precision([False, False]) == 0.0


def test_ragas_nan_counts_as_zero():
    assert _num(float("nan")) == 0.0 and _num(None) == 0.0 and _num("0.8") == 0.8
    assert not math.isnan(_num(float("nan")))


# ---- the canary never reaches live traffic --------------------------------------------

def test_candidate_prompt_is_not_served_live(tmp_path):
    reg = PromptRegistry(path=tmp_path / "r.json")
    active = reg.effective("synthesizer_system")
    reg.set_candidate("synthesizer_system", "UNPROVEN PROMPT")
    assert reg.effective("synthesizer_system") == active


def test_trial_prompt_reaches_only_its_own_run(monkeypatch):
    from atlas.core import graph as G
    from atlas.core.agents import synthesizer as S

    seen: list[str] = []

    def fake_chat(prompt, *, system=None, **kw):
        seen.append(system)
        return '{"company": "Helios", "headline": "ok", "stance": "neutral", "confidence": 0.5}'

    monkeypatch.setattr(S, "llm_ready", lambda: True)
    monkeypatch.setattr(S, "chat", fake_chat)
    G.research("Evaluate Helios Robotics", thread_id="trial-a", prompt_override="TRIAL PROMPT",
               score=False)
    G.research("Evaluate Helios Robotics", thread_id="trial-b", score=False)
    assert seen[0] == "TRIAL PROMPT"
    assert seen[-1] != "TRIAL PROMPT"  # a normal run uses the active prompt


def test_optimizer_discards_the_candidate_even_if_a_run_fails(monkeypatch, tmp_path):
    reg = PromptRegistry(path=tmp_path / "r.json")
    monkeypatch.setattr(O, "get_registry", lambda: reg)
    calls = {"n": 0}

    def fake_research(query, **kw):
        calls["n"] += 1
        if kw.get("prompt_override"):
            raise RuntimeError("Groq 429")
        return {"report": "## S\n- something vague here today.\n", "findings": []}

    from atlas.core import graph as G

    monkeypatch.setattr(G, "research", fake_research)
    with pytest.raises(RuntimeError):
        O.optimize("Evaluate Helios Robotics", max_iters=1)
    assert reg.candidate("synthesizer_system") is None  # cleaned up, not left live
