"""Diagnosis — turn run records into attributed, ranked failure patterns.

A bad report has a cause, and the cause usually isn't the report writer: an analyst
that found thin or ungrounded evidence poisons everything downstream. Each issue is
therefore attributed to ONE component (a specialist or the synthesizer) and to the
lever that can fix it. Human review is the strongest signal: a reviewer's feedback
outweighs an automatic score, and a rejection outweighs a revision request.

Deterministic on purpose — no LLM — so the ranking is cheap, testable and stable.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass

from .policy import MAX_EXEMPLARS, SPECIALIST_COMPONENTS, Policy

# Score floors below which a run counts as a failure of that component.
AGENT_GROUNDEDNESS_FLOOR = 0.6
AGENT_RICHNESS_FLOOR = 0.67     # fewer than 2 of the 3 target solid findings
REPORT_FLOORS = {"faithfulness": 0.7, "citation_accuracy": 0.6, "relevancy": 0.6}
EXEMPLAR_SCORE = 0.8            # an agent output this good, in an approved run, is a model

WEIGHT = {"reject": 3.0, "revise": 2.0, "score": 1.0, "opportunity": 0.5}

# Report sections → the component that produces their content.
SECTION_COMPONENT = {
    "company_overview": "fundamentals", "financials": "fundamentals",
    "recent_developments": "news_sentiment", "sentiment": "news_sentiment",
    "risks": "risk",
    "market_position": "market", "competitors": "market",
    "snapshot": "fundamentals", "pricing": "fundamentals",
    "strengths": "market", "head_to_head": "market",
    "weaknesses": "risk",
}

_FEEDBACK_KEYWORDS = {
    "fundamentals": ("revenue", "margin", "profit", "financial", "earning", "valuation",
                     "business model", "cash", "funding", "growth", "income"),
    "news_sentiment": ("news", "recent", "latest", "date", "announce", "sentiment", "deal",
                       "launch", "partnership"),
    "risk": ("risk", "debt", "regulat", "litigation", "lawsuit", "concentration", "supplier",
             "supply", "liquidity"),
    "market": ("competitor", "competition", "market share", "rival", "peer", "compare",
               "position"),
}


@dataclass
class Issue:
    component: str
    kind: str
    lever: str          # lesson | retrieval | exemplars
    weight: float
    detail: str         # one concrete example (feedback text, failing statement, score)
    record_id: str = ""


def attribute_feedback(feedback: str, section: str = "") -> str:
    """The component a piece of reviewer feedback is about."""
    if section in SECTION_COMPONENT:
        return SECTION_COMPONENT[section]
    text = feedback.lower()
    hits = {c: sum(k in text for k in kws) for c, kws in _FEEDBACK_KEYWORDS.items()}
    best = max(hits, key=hits.get)
    return best if hits[best] else "synthesizer"


def _agent_unavailable(findings: list[dict], agent: str) -> bool:
    mine = [f for f in findings if f.get("agent") == agent]
    return bool(mine) and all(f.get("unavailable") for f in mine)


def _trusted_reviewer(record: dict) -> bool:
    """Feedback teaches every user's agents, so only signed-up accounts count: demo
    (guest) sessions are anonymous and free to mint. Unscoped runs (CLI, tests, admin
    tooling) are trusted."""
    thread = str(record.get("thread_id") or "")
    if ":" not in thread:
        return True
    try:
        from ...security.store import get_auth_store

        user = get_auth_store().user_by_id(thread.split(":", 1)[0])
    except Exception:
        return False
    return user is not None and user.role in ("user", "admin") and not user.disabled


def diagnose_record(record: dict) -> list[Issue]:
    rid = record.get("thread_id", "")
    issues: list[Issue] = []
    if record.get("degraded"):
        return issues  # an outage run says nothing about prompt quality

    # 1. Human review: every revise / reject with feedback is a labelled failure.
    history = record.get("review", {}).get("history", [])
    for h in history if _trusted_reviewer(record) else []:
        action = h.get("action")
        feedback = (h.get("feedback") or "").strip()
        if action in ("revise", "reject") and feedback:
            comp = attribute_feedback(feedback, h.get("section") or "")
            issues.append(Issue(comp, "reviewer_feedback", "lesson", WEIGHT[action],
                                feedback[:240], rid))

    # 2. Specialists, from their own scores (an outage is infrastructure, not quality).
    findings = record.get("findings") or []
    for agent, s in (record.get("agents") or {}).items():
        if agent not in SPECIALIST_COMPONENTS or _agent_unavailable(findings, agent):
            continue
        if s.get("groundedness", 1.0) < AGENT_GROUNDEDNESS_FLOOR:
            issues.append(Issue(agent, "ungrounded_findings", "lesson", WEIGHT["score"],
                                f"groundedness {s['groundedness']:.2f}", rid))
        if s.get("richness", 1.0) < AGENT_RICHNESS_FLOOR:
            issues.append(Issue(agent, "thin_findings", "retrieval", WEIGHT["score"],
                                f"{s.get('n_findings', 0)} solid findings", rid))

    # 3. The report writer, from the report-level checks.
    scores = record.get("scores") or {}
    check = record.get("report_check") or {}
    if scores.get("faithfulness") is not None and \
            scores["faithfulness"] < REPORT_FLOORS["faithfulness"]:
        example = (check.get("unsupported") or [f"faithfulness {scores['faithfulness']:.2f}"])[0]
        issues.append(Issue("synthesizer", "unsupported_statements", "lesson", WEIGHT["score"],
                            str(example)[:240], rid))
    if scores.get("citation_accuracy") is not None and \
            scores["citation_accuracy"] < REPORT_FLOORS["citation_accuracy"]:
        example = (check.get("miscited") or [f"citation accuracy "
                                             f"{scores['citation_accuracy']:.2f}"])[0]
        issues.append(Issue("synthesizer", "miscited_statements", "lesson", WEIGHT["score"],
                            str(example)[:240], rid))
    if scores.get("relevancy") is not None and scores["relevancy"] < REPORT_FLOORS["relevancy"]:
        issues.append(Issue("synthesizer", "off_question", "lesson", WEIGHT["score"],
                            f"relevancy {scores['relevancy']:.2f} for: {record.get('query', '')}"
                            [:240], rid))
    return issues


def exemplar_candidates(records: list[dict], component: str) -> list[dict]:
    """Verified-strong findings for ``component`` from human-approved runs, best first."""
    out: list[tuple[float, dict]] = []
    for r in records:
        if r.get("review", {}).get("outcome") not in ("approved", "revised"):
            continue
        s = (r.get("agents") or {}).get(component) or {}
        if s.get("score", 0) < EXEMPLAR_SCORE:
            continue
        for f in r.get("findings") or []:
            claim = str(f.get("claim", "")).strip()
            if (f.get("agent") == component and f.get("citation") not in (None, "", "n/a")
                    and len(claim) > 40 and re.search(r"\d", claim)):
                out.append((s["score"], {"claim": claim[:300],
                                         "evidence": str(f.get("evidence_text", ""))[:300]}))
    out.sort(key=lambda t: -t[0])
    seen, unique = set(), []
    for _, ex in out:
        if ex["claim"] not in seen:
            seen.add(ex["claim"])
            unique.append(ex)
    return unique


def open_issues(records: list[dict], policies: dict[str, Policy] | None = None) -> list[dict]:
    """Aggregate issues across runs → ranked patterns ``{component, kind, lever, count,
    weight, examples, example}``. Exemplar gaps are added as low-weight opportunities."""
    groups: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"count": 0, "weight": 0.0, "examples": [], "lever": "lesson", "records": []})
    for r in records:
        for i in diagnose_record(r):
            g = groups[(i.component, i.kind)]
            g["count"] += 1
            g["weight"] += i.weight
            g["lever"] = i.lever
            if i.detail and i.detail not in g["examples"]:
                g["examples"].append(i.detail)
            g["records"].append(i.record_id)

    for comp in SPECIALIST_COMPONENTS:
        have = len((policies or {}).get(comp, Policy()).exemplars)
        n = len(exemplar_candidates(records, comp))
        if have < MAX_EXEMPLARS and n:
            g = groups[(comp, "missing_exemplars")]
            g.update(count=n, weight=WEIGHT["opportunity"] * min(n, 3), lever="exemplars",
                     examples=[f"{n} verified strong findings available from approved runs"])

    ranked = [{"component": c, "kind": k, "lever": g["lever"], "count": g["count"],
               "weight": round(g["weight"], 2), "examples": g["examples"][:4],
               "example": (g["examples"] or [""])[0], "records": g["records"][:8]}
              for (c, k), g in groups.items()]
    ranked.sort(key=lambda x: (-x["weight"], -x["count"]))
    return ranked


def issue_dict(i: Issue) -> dict:
    return asdict(i)
