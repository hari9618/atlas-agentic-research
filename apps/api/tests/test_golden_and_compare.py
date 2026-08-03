"""Golden dataset integrity (Phase 7) + baseline-vs-Atlas harness (Phase 9), offline."""

from __future__ import annotations

from atlas.eval.baseline import baseline_run
from atlas.eval.compare import run_comparison
from atlas.eval.golden import ALL_GOLDEN, GOLDEN_SET, load_golden

# ---- Phase 7: dataset integrity ----

def test_golden_set_loads_and_has_categories():
    assert len(ALL_GOLDEN) >= 20
    cats = {g.category for g in ALL_GOLDEN}
    # A spread of case types, not just one company's fundamentals.
    for expected in ("risk_analysis", "competitor_analysis", "requires_web",
                     "entity_confusion", "ambiguous", "citation_grounding"):
        assert expected in cats, f"missing category: {expected}"


def test_ids_are_unique():
    ids = [g.id for g in ALL_GOLDEN]
    assert len(ids) == len(set(ids)) and all(ids)


def test_verifiable_cases_have_a_reference_answer_and_docs():
    for g in GOLDEN_SET:  # GOLDEN_SET is the verifiable subset
        assert g.verifiable and g.answer.strip(), f"{g.id} verifiable but has no answer"
        assert g.relevant_doc_ids, f"{g.id} verifiable but names no supporting docs"


def test_non_verifiable_cases_do_not_fabricate_ground_truth():
    # The whole point: behavioural cases must NOT carry an invented answer.
    behavioural = [g for g in ALL_GOLDEN if not g.verifiable]
    assert behavioural, "expected some behavioural (non-verifiable) cases"
    for g in behavioural:
        assert g.answer.strip() == "", f"{g.id} is non-verifiable but has a reference answer"
        assert g.notes.strip(), f"{g.id} non-verifiable but describes no expected behaviour"


def test_web_cases_expect_web_provenance():
    for g in ALL_GOLDEN:
        if g.requires_web:
            assert g.expected_provenance == "web"
            assert not g.relevant_doc_ids  # the corpus can't answer it


def test_load_golden_is_pure():
    assert len(load_golden()) == len(ALL_GOLDEN)


# ---- Phase 9: baseline + comparison harness ----

def test_baseline_returns_atlas_shaped_result():
    out = baseline_run("What was Helios Robotics' revenue in 2025?")
    assert {"report", "findings", "confidence"} <= set(out)
    assert isinstance(out["findings"], list)


def test_comparison_scores_both_systems_with_the_same_metrics():
    result = run_comparison(limit=2)
    assert result["n"] == 2
    agg = result["aggregate"]
    for system in ("baseline", "atlas"):
        for metric in ("faithfulness", "citation_coverage", "citation_correctness", "latency"):
            assert metric in agg[system]
    # Every row carries both systems' scores so the comparison is apples-to-apples.
    for row in result["rows"]:
        assert "baseline" in row and "atlas" in row
        assert "citation_coverage" in row["atlas"]
