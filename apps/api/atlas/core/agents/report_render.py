"""Render the structured report (design §1) as markdown.

The markdown is not just for display: it is what the grounding guardrail measures
citation coverage on, what episodic memory stores, what the eval loop scores and
what the PDF falls back to. So every citation in the sections must appear in it
verbatim. Pure function; empty sections are omitted, "Not enough evidence yet."
is shown (it is an honest answer, not an empty one).
"""

from __future__ import annotations


def _cite(c: str) -> str:
    c = (c or "").strip()
    if not c:
        return ""
    return f" {c}" if c.startswith("[") else f" [{c}]"


def _bullets(items: list[str]) -> list[str]:
    return [f"- {i}" for i in items if i]


def _section(title: str, body: list[str]) -> list[str]:
    body = [b for b in body if b is not None]
    if not any(b.strip() for b in body):
        return []
    return [f"## {title}", "", *body, ""]


def render_markdown(s: dict) -> str:
    """Markdown brief from normalized sections (see report_schema.normalize_sections)."""
    out: list[str] = []
    company = s.get("company") or "Company"
    out += [f"# {company}: Investor Brief", ""]
    if s.get("headline"):
        out += [f"**{s['headline']}**", ""]
    if s.get("stance"):
        out += [f"Overall stance: **{s['stance'].capitalize()}**", ""]

    out += _section("Executive Summary", _bullets(s.get("executive_summary", [])))

    ov = s.get("company_overview") or {}
    ov_body = []
    if ov.get("what_they_do"):
        ov_body.append(f"**What they do:** {ov['what_they_do']}")
    if ov.get("business_model"):
        ov_body.append(f"**Business model:** {ov['business_model']}")
    if ov.get("products"):
        ov_body.append("**Products and services:**")
        ov_body += _bullets(ov["products"])
    if ov.get("customers"):
        ov_body.append(f"**Customers:** {ov['customers']}")
    out += _section("Company Overview", _spaced(ov_body))

    fin = s.get("financials") or {}
    fin_body = [fin["summary"]] if fin.get("summary") else []
    for m in fin.get("metrics", []):
        change = f" ({m['change']})" if m.get("change") else ""
        fin_body.append(f"- **{m['label']}:** {m['value']}{change}{_cite(m.get('citation', ''))}")
    out += _section("Financials", _spaced_block(fin_body))

    mp = s.get("market_position") or {}
    mp_body = [mp["summary"]] if mp.get("summary") else []
    if mp.get("strengths"):
        mp_body += ["", "**Strengths**", *_bullets(mp["strengths"])]
    if mp.get("weaknesses"):
        mp_body += ["", "**Weaknesses**", *_bullets(mp["weaknesses"])]
    out += _section("Market Position", mp_body)

    comp_body = []
    for c in s.get("competitors", []):
        cmp = f": {c['comparison']}" if c.get("comparison") else ""
        comp_body.append(f"- **{c['name']}** (threat: {c.get('threat', 'medium')}){cmp}"
                         f"{_cite(c.get('citation', ''))}")
    out += _section("Competitors", comp_body)

    dev_body = []
    for d in s.get("recent_developments", []):
        when = f"{d['date']} · " if d.get("date") else ""
        detail = f": {d['detail']}" if d.get("detail") else ""
        dev_body.append(f"- **{when}{d['title']}** ({d.get('sentiment', 'neutral')}){detail}"
                        f"{_cite(d.get('citation', ''))}")
    out += _section("Recent Developments", dev_body)

    sent = s.get("sentiment") or {}
    if sent.get("summary"):
        out += _section("Sentiment", [f"**Overall: {sent.get('overall', 'mixed').capitalize()}.** "
                                      f"{sent['summary']}"])

    risk_body = []
    for r in s.get("risks", []):
        detail = f": {r['detail']}" if r.get("detail") else ""
        risk_body.append(f"- **{r['title']}** (severity: {r.get('severity', 'medium')}){detail}"
                         f"{_cite(r.get('citation', ''))}")
    out += _section("Key Risks", risk_body)

    out += _section("Bull Case", _bullets(s.get("bull_case", [])))
    out += _section("Bear Case", _bullets(s.get("bear_case", [])))

    outlook = s.get("outlook") or {}
    ol_body = [outlook["summary"]] if outlook.get("summary") else []
    if outlook.get("watch_items"):
        ol_body += ["", "**What to watch**", *_bullets(outlook["watch_items"])]
    out += _section("Outlook", ol_body)

    if s.get("bottom_line"):
        out += _section("Bottom Line", [s["bottom_line"]])
    out += _section("What We're Not Sure About", _bullets(s.get("uncertainties", [])))
    return "\n".join(out).rstrip() + "\n"


def _spaced(lines: list[str]) -> list[str]:
    """Blank line between labelled paragraphs, but keep bullet lists tight."""
    out: list[str] = []
    for ln in lines:
        if out and not ln.startswith("- ") and out[-1] != "":
            out.append("")
        out.append(ln)
    return out


def _spaced_block(lines: list[str]) -> list[str]:
    """A summary paragraph followed by a bullet list."""
    if lines and not lines[0].startswith("- ") and len(lines) > 1:
        return [lines[0], "", *lines[1:]]
    return lines
