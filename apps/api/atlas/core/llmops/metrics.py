"""What each run score means, in words a non-specialist can read.

Every score is 0..1 and higher is better. One table drives three places, so they
can never disagree: the names and comments pushed to Langfuse, the "How good are
the reports?" panel on the Learning page, and the API overview.

Bands are the same for every score:  Good >= 0.70 · OK >= 0.40 · Weak < 0.40.
"""

from __future__ import annotations

from dataclasses import dataclass

GOOD, OK = 0.70, 0.40


@dataclass(frozen=True)
class Metric:
    key: str          # key in the run record's scores
    name: str         # exactly what people see: Langfuse score name and the table row
    question: str     # the question the score answers
    meaning: str      # what the number is, with {pct} for the value as a percentage


METRICS: tuple[Metric, ...] = (
    Metric("relevancy", "Answer relevancy",
           "Does the report actually answer the question?",
           "A judge rated how directly the report answers the question: {pct}."),
    Metric("faithfulness", "Faithfulness",
           "Is what the report says backed by the evidence?",
           "{pct} of the report's statements are supported by the evidence found."),
    Metric("context_precision", "Context precision",
           "Was the evidence the agents used on-topic?",
           "{pct} of the evidence the agents used was relevant to the question."),
    Metric("context_recall", "Context recall",
           "Did the agents find everything the question needs?",
           "Evidence was found for {pct} of the things needed to answer the question."),
    Metric("citation_accuracy", "Citation accuracy",
           "Do the citations really say what the report claims?",
           "{pct} of cited statements are supported by their own source."),
    Metric("citation_coverage", "Citation coverage",
           "Does every statement have a source?",
           "{pct} of the report's statements carry a citation."),
    Metric("overall", "Overall",
           "One number for the run.",
           "Average of answer relevancy, faithfulness and context precision: {pct}."),
)

BY_KEY = {m.key: m for m in METRICS}


def rating(value: float | None) -> str:
    """Good / OK / Weak — the same bands for every score."""
    if value is None:
        return "No data"
    if value >= GOOD:
        return "Good"
    if value >= OK:
        return "OK"
    return "Weak"


def explain(key: str, value: float | None) -> str:
    """One line a human can read, e.g.
    "0.48 out of 1 · OK. 48% of the evidence the agents used was relevant to the
    question. Good is 0.70 or more."
    """
    m = BY_KEY[key]
    if value is None:
        return f"{m.question} Not measured for this run."
    pct = f"{round(value * 100)}%"
    return (f"{value:.2f} out of 1 · {rating(value)}. {m.meaning.format(pct=pct)} "
            f"Good is {GOOD:.2f} or more; below {OK:.2f} is weak.")


def describe(means: dict[str, float | None]) -> list[dict]:
    """The Learning page panel: every score with its average and a plain reading."""
    return [{
        "key": m.key, "name": m.name, "question": m.question,
        "mean": means.get(m.key), "rating": rating(means.get(m.key)),
        "meaning": explain(m.key, means.get(m.key)),
    } for m in METRICS]
