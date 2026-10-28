"""Report-level grounding check — is what the READER sees supported by the evidence?

``claim_verify`` checks the specialists' findings. But the user reads the synthesized
brief, which paraphrases, merges and sometimes re-attributes those findings. This
module verifies the brief itself, statement by statement:

    brief ─► statements (one per bullet / paragraph line, with their [source#n] keys)
          ─► cited evidence (by key)  ─► supported / partial / unsupported

and yields three numbers, all 0..1:

* **faithfulness**       — statements supported by the retrieved evidence at all
                           (Ragas' definition: claims grounded in the context).
* **citation_accuracy**  — cited statements supported by THEIR OWN citation. Catches
                           mis-attribution, e.g. a 10-K fact cited to a news article.
* **citation_coverage**  — statements that carry a citation at all.

Partial support counts half. Verification is deterministic first (figures must match,
lexical overlap floor — see ``claim_verify._deterministic``); only the genuinely
ambiguous statements go to the LLM, in ONE batched call, so a whole brief costs a
single small-model request instead of one per claim.
"""

from __future__ import annotations

import json
import logging
import re

from ..resilience import LLM_ATTEMPTS, retry_call
from .claim_verify import (
    PARTIAL,
    SUPPORTED,
    UNSUPPORTED,
    _content_words,
    _deterministic,
    _key_figures,
)

log = logging.getLogger("atlas.llmops.report_verify")

# One bracket group containing a source#n key, e.g. "[sec_edgar#0]" or
# "[Helios 10-K (sec_edgar#1)]"; the key is what links a statement to its evidence.
_CITE = re.compile(r"\[([^\[\]]*?[\w.\-]+#\d+[^\[\]]*?)\]")
_KEY = re.compile(r"([\w.\-]+#\d+)")
_MARKER = re.compile(r"\s*\[(?:web|atlas-derived)\]")
_BULLET = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_LABEL = re.compile(r"\*\*[^*]{1,60}:\*\*\s*")  # "**What they do:**" field labels
# Sections that are about the brief, not claims about the company.
_SKIP_SECTIONS = ("not sure", "uncertain", "source", "debate transcript")
_SKIP_LINES = ("overall stance", "not enough evidence")
_MIN_WORDS = 5
_MAX_STATEMENTS = 40
_LLM_BATCH = 15
_WINDOW = 900


def _clean(line: str) -> str:
    line = _BULLET.sub("", line.strip())
    line = _LABEL.sub("", line)
    return line.replace("**", "").strip()


def report_statements(report: str) -> list[dict]:
    """Split a rendered brief into checkable statements with their citation keys."""
    section, out = "", []
    for raw in (report or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or line.startswith("---"):
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip().lower()
            continue
        if any(s in section for s in _SKIP_SECTIONS):
            continue
        line = _clean(line)
        keys = [k for group in _CITE.findall(line) for k in _KEY.findall(group)]
        text = _MARKER.sub("", _CITE.sub("", line)).strip(" .;")
        if any(s in text.lower() for s in _SKIP_LINES) or len(text.split()) < _MIN_WORDS:
            continue
        out.append({"text": text, "keys": list(dict.fromkeys(keys))})
    return out[:_MAX_STATEMENTS]


def evidence_map(findings: list[dict]) -> dict[str, str]:
    """source#n key → the evidence text the findings carried for it."""
    out: dict[str, str] = {}
    for f in findings or []:
        m = _KEY.search(str(f.get("citation") or ""))
        text = str(f.get("evidence_text") or "")
        if m and len(text) > len(out.get(m.group(1), "")):
            out[m.group(1)] = text
    return out


def _focus(evidence: str, claim: str, size: int = _WINDOW) -> str:
    """The window of ``evidence`` most likely to hold the claim (for the LLM judge)."""
    if len(evidence) <= size:
        return evidence
    for fig in _key_figures(claim):  # centre on a claimed figure if present
        num = re.sub(r"[%bmk]$", "", fig)
        i = evidence.find(num)
        if i >= 0:
            start = max(0, i - size // 2)
            return evidence[start:start + size]
    words = _content_words(claim)
    best, best_start = -1, 0
    for start in range(0, len(evidence) - size + 1, size // 3):
        hits = len(words & _content_words(evidence[start:start + size]))
        if hits > best:
            best, best_start = hits, start
    return evidence[best_start:best_start + size]


def _best_evidence(claim: str, evmap: dict[str, str], k: int = 2) -> str:
    """For an uncited statement: the k evidence texts that overlap it most."""
    words = _content_words(claim)
    ranked = sorted(evmap.values(), key=lambda t: len(words & _content_words(t)), reverse=True)
    return "\n".join(ranked[:k])


def _llm_batch(items: list[tuple[str, str]]) -> list[str | None]:
    """One judge call for many (claim, evidence) pairs. None where it gave no verdict."""
    from ...config import get_settings
    from ...llm import get_llm
    from ...observability import langchain_callbacks

    blocks = "\n\n".join(
        f"#{i + 1}\nCLAIM: {claim}\nEVIDENCE: {_focus(ev, claim)}"
        for i, (claim, ev) in enumerate(items)
    )
    prompt = (
        "For each numbered item, decide whether the EVIDENCE supports the CLAIM. "
        "supported = the evidence states it (paraphrase is fine); partial = some of it is "
        "stated, some is not; unsupported = the evidence does not state it or contradicts it. "
        f'Return ONLY a JSON array of {len(items)} strings, in order, e.g. '
        '["supported","partial"].\n\n' + blocks
    )
    llm = get_llm(temperature=0.0, model=get_settings().summarizer_model)
    resp = retry_call(llm.invoke, prompt, attempts=LLM_ATTEMPTS, label="ops.verify_report",
                      config={"callbacks": langchain_callbacks(), "run_name": "ops.verify_report"})
    text = (resp.content if hasattr(resp, "content") else str(resp)).lower()
    try:
        arr = json.loads(text[text.index("["): text.rindex("]") + 1])
    except (ValueError, json.JSONDecodeError):
        return [None] * len(items)
    allowed = {SUPPORTED, PARTIAL, UNSUPPORTED}
    verdicts = [v if isinstance(v, str) and v in allowed else None for v in arr]
    return (verdicts + [None] * len(items))[: len(items)]


def _credit(verdict: str) -> float:
    return 1.0 if verdict == SUPPORTED else 0.5 if verdict == PARTIAL else 0.0


def verify_report(report: str, findings: list[dict], *, use_llm: bool) -> dict:
    """Verify every statement in the brief. Returns per-statement verdicts + metrics."""
    statements = report_statements(report)
    evmap = evidence_map(findings)
    rows: list[dict] = []
    pending: list[tuple[int, str, str, str]] = []  # (row index, field, claim, evidence)

    for st in statements:
        text, keys = st["text"], st["keys"]
        known = [k for k in keys if k in evmap]
        row = {"statement": text, "keys": keys,
               "unknown_keys": [k for k in keys if k not in evmap],
               "cited": None, "grounded": None, "method": "deterministic"}
        # 1) citation accuracy — against the statement's OWN cited evidence
        if keys:
            if known:
                cited_ev = "\n".join(evmap[k] for k in known)
                verdict, _, confident = _deterministic(text, cited_ev)
                row["cited"] = verdict
                if not confident and use_llm:
                    pending.append((len(rows), "cited", text, cited_ev))
            else:  # every key it cites is unknown: a fabricated or dangling citation
                row["cited"] = UNSUPPORTED
        # 2) faithfulness — supported by ANY retrieved evidence
        if row["cited"] == SUPPORTED:
            row["grounded"] = SUPPORTED
        elif evmap:
            pool = _best_evidence(text, evmap)
            verdict, _, confident = _deterministic(text, pool)
            row["grounded"] = verdict
            if not confident and use_llm:
                pending.append((len(rows), "grounded", text, pool))
        else:
            row["grounded"] = UNSUPPORTED
        rows.append(row)

    if pending:
        for start in range(0, len(pending), _LLM_BATCH):
            batch = pending[start:start + _LLM_BATCH]
            try:
                verdicts = _llm_batch([(claim, ev) for _, _, claim, ev in batch])
            except Exception as exc:  # judge unavailable → keep deterministic verdicts
                log.warning("report verification judge failed: %s", exc)
                break
            for (i, field, _, _), v in zip(batch, verdicts, strict=False):
                if v:
                    rows[i][field], rows[i]["method"] = v, "llm"
        # A statement its own citation supports is grounded, whatever the pool said.
        for r in rows:
            if r["cited"] == SUPPORTED:
                r["grounded"] = SUPPORTED

    n = len(rows)
    cited = [r for r in rows if r["cited"] is not None]
    return {
        "statements": rows,
        "total_statements": n,
        "cited_statements": len(cited),
        "faithfulness": round(sum(_credit(r["grounded"]) for r in rows) / n, 3) if n else 0.0,
        "citation_accuracy": round(sum(_credit(r["cited"]) for r in cited) / len(cited), 3)
        if cited else 0.0,
        "citation_coverage": round(len(cited) / n, 3) if n else 0.0,
        "unsupported": [r["statement"] for r in rows if r["grounded"] == UNSUPPORTED][:10],
        "miscited": [r["statement"] for r in rows if r["cited"] == UNSUPPORTED][:10],
    }
