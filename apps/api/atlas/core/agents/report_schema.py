"""Normalize the synthesizer's JSON into the report contract (design §1).

LLM JSON is "mostly right": enums in the wrong case, a string where a list belongs,
a number as a string, stray keys. The frontend renders whatever is present, so it
must never receive a shape it can't handle. This module coerces types, maps enum
synonyms onto the allowed lowercase values, drops junk and unknown keys, and clamps
confidence. Pure functions only — no I/O, trivially testable.
"""

from __future__ import annotations

from typing import Any

NOT_ENOUGH = "Not enough evidence yet."

_MAX_STR = 1200
_MAX_ITEMS = 10

STANCES = {"positive", "neutral", "cautious"}
LEVELS = {"high", "medium", "low"}
TONES = {"positive", "neutral", "negative"}
OVERALL_SENTIMENT = {"positive", "mixed", "negative"}

_SYNONYMS = {
    # stance
    "bullish": "positive", "favorable": "positive", "favourable": "positive",
    "optimistic": "positive", "bearish": "cautious", "negative": "cautious",
    "pessimistic": "cautious", "caution": "cautious", "mixed": "neutral",
    "balanced": "neutral",
    # threat / severity
    "critical": "high", "severe": "high", "major": "high", "significant": "high",
    "moderate": "medium", "med": "medium", "minor": "low", "limited": "low",
}


# gpt-oss sometimes cites with CJK lenticular brackets — "【web_search#0】" — which the
# frontend's citation chips and the guardrails don't recognise. Map them to "[...]".
_FULLWIDTH = str.maketrans({"【": "[", "】": "]", "［": "[", "］": "]"})


def normalize_brackets(text: str) -> str:
    """Rewrite fullwidth citation brackets as ASCII ``[...]``."""
    return text.translate(_FULLWIDTH)


def _str(value: Any) -> str:
    """Scalar → trimmed string; dict/list → readable joined text; None → ''."""
    if value is None:
        return ""
    if isinstance(value, dict):
        value = "; ".join(_str(v) for v in value.values() if _str(v))
    elif isinstance(value, (list, tuple)):
        value = "; ".join(_str(v) for v in value if _str(v))
    return normalize_brackets(str(value)).strip()[:_MAX_STR]


def _str_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        value = [value]
    out = []
    for v in value:
        if isinstance(v, dict):  # e.g. {"point": "...", "citation": "[x]"}
            v = " ".join(_str(x) for x in v.values() if _str(x))
        s = _str(v)
        if s:
            out.append(s)
    return out[:_MAX_ITEMS]


def _enum(value: Any, allowed: set[str], default: str, extra: dict | None = None) -> str:
    s = _str(value).lower().strip(" .")
    if s in allowed:
        return s
    mapped = (extra or {}).get(s) or _SYNONYMS.get(s)
    return mapped if mapped in allowed else default


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _records(value: Any, build) -> list[dict]:
    """Normalize a list of objects with ``build``; a bare string becomes one record."""
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        rec = build(item if isinstance(item, dict) else {"_text": _str(item)})
        if rec:
            out.append(rec)
    return out[:_MAX_ITEMS]


def _cite(item: dict) -> str:
    return _str(item.get("citation") or item.get("source"))


_PLACEHOLDERS = {"not enough evidence yet", "not enough evidence", "n/a", "na", "none",
                 "unknown", "-", "tbd", "not available"}


def _placeholder(text: str) -> bool:
    """Empty, or filler like "Not enough evidence yet." / "N/A".

    The model fills a schema slot with the placeholder when it has nothing — fine for
    a text field, but as a list record it rendered a competitor literally named
    "Not enough evidence yet." (seen live). Records are dropped instead.
    """
    return _str(text).lower().strip(" .") in _PLACEHOLDERS


def _optional(value) -> str:
    """An optional field (date, change) with filler blanked: a placeholder date once
    rendered as "Not enough evidence yet. · Terms of Service published" (seen live)."""
    text = _str(value)
    return "" if _placeholder(text) else text


def _metric(m: dict) -> dict | None:
    label, value = _str(m.get("label") or m.get("name")), _str(m.get("value"))
    if not (label and value) or _placeholder(label) or _placeholder(value):
        return None
    return {"label": label, "value": value, "change": _optional(m.get("change")),
            "citation": _cite(m)}


def _competitor(c: dict) -> dict | None:
    name = _str(c.get("name") or c.get("_text"))
    if not name or _placeholder(name):
        return None
    return {"name": name, "comparison": _str(c.get("comparison") or c.get("detail")),
            "threat": _enum(c.get("threat"), LEVELS, "medium"), "citation": _cite(c)}


def _development(d: dict) -> dict | None:
    title, detail = _str(d.get("title") or d.get("_text")), _str(d.get("detail"))
    if _placeholder(title) and _placeholder(detail):
        return None
    return {"date": _optional(d.get("date")), "title": title or detail[:80], "detail": detail,
            "sentiment": _enum(d.get("sentiment"), TONES, "neutral",
                               {"bullish": "positive", "bearish": "negative", "mixed": "neutral"}),
            "citation": _cite(d)}


def _risk(r: dict) -> dict | None:
    title, detail = _str(r.get("title") or r.get("_text")), _str(r.get("detail"))
    if _placeholder(title) and _placeholder(detail):
        return None
    return {"title": title or detail[:80], "severity": _enum(r.get("severity"), LEVELS, "medium"),
            "detail": detail, "citation": _cite(r)}


EDGES = {"subject", "asker", "even"}
OVERLAP = {"high", "medium", "low", "none"}


def _plan(pl: dict) -> dict | None:
    name, price = _str(pl.get("name") or pl.get("_text")), _str(pl.get("price"))
    if (not name or _placeholder(name)) and (not price or _placeholder(price)):
        return None
    return {"name": name, "price": price, "notes": _str(pl.get("notes")), "citation": _cite(pl)}


def _h2h_row(r: dict) -> dict | None:
    dim = _str(r.get("dimension") or r.get("_text"))
    if not dim or _placeholder(dim):
        return None
    return {"dimension": dim, "subject": _str(r.get("subject")), "asker": _str(r.get("asker")),
            "edge": _enum(r.get("edge"), EDGES, "even", {"them": "subject", "us": "asker",
                                                        "tie": "even", "equal": "even"}),
            "citation": _cite(r)}


def _answer(a: dict) -> dict | None:
    q, ans = _str(a.get("question") or a.get("_text")), _str(a.get("answer"))
    if not q or not ans:
        return None
    return {"question": q, "answer": ans, "citation": _cite(a)}


def clamp_confidence(value: Any, default: float = 0.5) -> float:
    try:
        v = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return default
    if v > 1.0:  # "72" or "72%" → 0.72
        v = v / 100.0
    return round(max(0.0, min(1.0, v)), 3)


def normalize_sections(raw: Any, *, company: str = "") -> dict | None:
    """Coerce an LLM reply into the §1 schema. Returns None if it isn't a usable report."""
    if not isinstance(raw, dict):
        return None
    if isinstance(raw.get("report"), dict):  # tolerate {"report": {...}} wrapping
        raw = raw["report"]

    ov, fin, mp = _dict(raw.get("company_overview")), _dict(raw.get("financials")), \
        _dict(raw.get("market_position"))
    sent, outlook = _dict(raw.get("sentiment")), _dict(raw.get("outlook"))
    verdict, pricing, h2h = _dict(raw.get("verdict")), _dict(raw.get("pricing")), \
        _dict(raw.get("head_to_head"))
    # Strengths/weaknesses are top-level now; older drafts kept them under
    # market_position — accept either so revisions of old drafts still normalize.
    strengths = _str_list(raw.get("strengths")) or _str_list(mp.get("strengths"))
    weaknesses = _str_list(raw.get("weaknesses")) or _str_list(mp.get("weaknesses"))
    sections = {
        "company": _str(raw.get("company")) or company,
        "headline": _str(raw.get("headline")),
        "stance": _enum(raw.get("stance"), STANCES, "neutral"),
        "confidence": clamp_confidence(raw.get("confidence")),
        "verdict": {"answer": _str(verdict.get("answer")),
                    "recommendation": _str(verdict.get("recommendation"))[:120]},
        "executive_summary": _str_list(raw.get("executive_summary")),
        "snapshot": _records(raw.get("snapshot"), _metric),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "pricing": {"summary": _str(pricing.get("summary")),
                    "plans": _records(pricing.get("plans"), _plan)},
        "company_overview": {
            "what_they_do": _str(ov.get("what_they_do")),
            "business_model": _str(ov.get("business_model")),
            "products": _str_list(ov.get("products")),
            "customers": _str(ov.get("customers")),
        },
        "financials": {
            "summary": _str(fin.get("summary")),
            "metrics": _records(fin.get("metrics"), _metric),
        },
        "market_position": {
            "summary": _str(mp.get("summary")),
            "strengths": strengths,
            "weaknesses": weaknesses,
        },
        "competitors": _records(raw.get("competitors"), _competitor),
        "recent_developments": _records(raw.get("recent_developments"), _development),
        "sentiment": {
            "overall": _enum(sent.get("overall") if sent else raw.get("sentiment"),
                             OVERALL_SENTIMENT, "mixed",
                             {"neutral": "mixed", "bullish": "positive", "bearish": "negative"}),
            "summary": _str(sent.get("summary")),
            "praise": _str_list(sent.get("praise")),
            "complaints": _str_list(sent.get("complaints")),
        },
        "risks": _records(raw.get("risks"), _risk),
        "bull_case": _str_list(raw.get("bull_case")),
        "bear_case": _str_list(raw.get("bear_case")),
        "outlook": {
            "summary": _str(outlook.get("summary")),
            "watch_items": _str_list(outlook.get("watch_items")),
        },
        "bottom_line": _str(raw.get("bottom_line")),
        "head_to_head": {
            "asker": _str(h2h.get("asker")),
            "overlap": _enum(h2h.get("overlap"), OVERLAP, "low",
                             {"direct": "high", "partial": "medium", "indirect": "low"}),
            "summary": _str(h2h.get("summary")),
            "rows": _records(h2h.get("rows"), _h2h_row),
        },
        "custom_answers": _records(raw.get("custom_answers"), _answer),
        "uncertainties": _str_list(raw.get("uncertainties")),
    }
    # A reply with no substantive content is a failed generation, not a report.
    substantive = (sections["headline"] or sections["executive_summary"]
                   or sections["bottom_line"])
    return sections if substantive else None
