"""Golden evaluation set over the sample corpus.

Each item has a question, the ground-truth answer, and the doc_ids that contain the
supporting evidence (used for retrieval metrics like context precision / hit-rate).
Keep this small and high-signal — it's a regression gate, not a benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GoldenItem:
    question: str
    answer: str
    relevant_doc_ids: list[str] = field(default_factory=list)


GOLDEN_SET: list[GoldenItem] = [
    GoldenItem(
        question="What was Helios Robotics' total revenue in fiscal year 2025?",
        answer="Helios Robotics reported total revenue of $4.2 billion in fiscal 2025, "
        "up 28% from $3.28 billion in 2024.",
        relevant_doc_ids=["helios_10k_fy2025"],
    ),
    GoldenItem(
        question="What is the main supply-chain risk Helios Robotics discloses?",
        answer="Helios depends on a single Taiwanese supplier for high-precision actuators; "
        "a disruption could delay shipments. Dual-sourcing is not expected before late 2026.",
        relevant_doc_ids=["helios_10k_fy2025", "helios_news_2026q1"],
    ),
    GoldenItem(
        question="Who is Helios Robotics' principal competitor and how do they compare?",
        answer="Aster Dynamics Corp., a Munich-based company and the largest warehouse-robot "
        "provider in Europe. Aster is larger ($5.6B revenue) but more hardware-heavy with a "
        "smaller, lower-margin software mix than Helios.",
        relevant_doc_ids=["aster_dynamics_profile", "helios_10k_fy2025"],
    ),
    GoldenItem(
        question="What was the largest contract Helios announced in early 2026?",
        answer="A five-year, $900 million deal in March 2026 to deploy over 12,000 robots "
        "across a major North American retailer's network; about 40% is recurring revenue.",
        relevant_doc_ids=["helios_news_2026q1"],
    ),
    GoldenItem(
        question="How does Helios' software business compare to its hardware business?",
        answer="Fleet Software revenue was $1.3B (31% of revenue), grew 46%, and carries higher "
        "margins; ARR reached $1.5B with 122% net revenue retention, versus $2.9B hardware.",
        relevant_doc_ids=["helios_10k_fy2025"],
    ),
]
