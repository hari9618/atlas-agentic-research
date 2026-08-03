"""Golden evaluation set — a small, version-controlled benchmark for Atlas.

The cases live in ``data/golden/golden.jsonl`` (one JSON object per line) so the
benchmark is diff-able and reviewable, not buried in Python. Each case carries enough
metadata to evaluate the *right* behaviour per category:

* ``category``            - factual_lookup, company_fundamentals, competitor_analysis,
  market_analysis, risk_analysis, news_current_events, ambiguous, requires_web,
  corpus_absent, entity_confusion, citation_grounding.
* ``reference_answer``    - the ground truth, for *verifiable* cases only.
* ``relevant_doc_ids``    - supporting docs, for retrieval metrics.
* ``target_entity``       - the entity the question is about (entity-correctness).
* ``expected_provenance`` - authoritative | web.
* ``requires_web``        - the corpus can't answer it; web fallback is expected.
* ``verifiable``          - False when no exact answer can be pinned down; the case
  then tests *behaviour* (e.g. "must use web", "must not confuse entities"), never a
  fabricated ground truth.

Verifiable answers are taken directly from the sample corpus — none are invented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..paths import data_dir


@dataclass
class GoldenItem:
    question: str
    answer: str = ""  # reference answer (empty for non-verifiable behavioural cases)
    relevant_doc_ids: list[str] = field(default_factory=list)
    id: str = ""
    category: str = "factual_lookup"
    target_entity: str = ""
    expected_provenance: str = "authoritative"
    requires_web: bool = False
    verifiable: bool = True
    notes: str = ""


def golden_path():
    return data_dir() / "golden" / "golden.jsonl"


def load_golden(path=None) -> list[GoldenItem]:
    """Load the versioned golden set from JSONL."""
    p = path or golden_path()
    items: list[GoldenItem] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        items.append(GoldenItem(
            question=d["question"],
            answer=d.get("reference_answer", d.get("answer", "")),
            relevant_doc_ids=d.get("relevant_doc_ids", []),
            id=d.get("id", ""),
            category=d.get("category", "factual_lookup"),
            target_entity=d.get("target_entity", ""),
            expected_provenance=d.get("expected_provenance", "authoritative"),
            requires_web=d.get("requires_web", False),
            verifiable=d.get("verifiable", True),
            notes=d.get("notes", ""),
        ))
    return items


# Loaded once. ALL_GOLDEN includes behavioural (non-verifiable) cases; GOLDEN_SET is
# the verifiable subset that answer-quality metrics score — this is what the existing
# retrieval_eval / ragas_eval consume via .question / .answer / .relevant_doc_ids.
ALL_GOLDEN: list[GoldenItem] = load_golden()
GOLDEN_SET: list[GoldenItem] = [g for g in ALL_GOLDEN if g.verifiable]
