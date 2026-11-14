"""Evidence for companies the press doesn't cover: website, reviews, LinkedIn, funding.

Public companies come with filings, quotes and news. A 30-person SaaS startup comes
with none of that — and that is exactly what users ask about, because a chat
assistant can already summarize NVIDIA. What *does* exist for a small company:

* its **own website** — product, pricing, customers, careers (``tools/website.py``);
* **customer and employee reviews** — G2, Capterra, Trustpilot, Glassdoor, Reddit…;
* **LinkedIn** company page and posts, found through search (never scraped);
* **funding** pages — Crunchbase, Tracxn, press about rounds;
* **"alternatives" / "X vs Y"** pages — the market's own list of competitors;
* the **asker's own website** when they say "my company is …", so a competitor
  question becomes a real side-by-side comparison.

Each specialist gets the slice that matches its job (``SPECIALIST_SOURCES``). Every
search result passes the entity guard (name *or* domain), and every result becomes a
citable chunk with provenance, so the grounding rules apply unchanged.

Budget: ~10 searches + 1–2 site reads per run, all cached (``upstreams``), so the
same company researched twice within the cache window costs nothing extra.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .entity import entity_terms, normalize_domain
from .tool_evidence import _PIECE_CHARS, _chunk
from .types import RetrievedChunk
from .web_evidence import filter_hits_for_entity, web_offline

log = logging.getLogger("atlas.rag.company_evidence")

REVIEW_SITES = ("g2.com", "capterra.com", "trustpilot.com", "trustradius.com",
                "getapp.com", "producthunt.com", "softwareadvice.com", "reddit.com")
EMPLOYEE_SITES = ("glassdoor.com", "indeed.com", "ambitionbox.com", "comparably.com")
FUNDING_SITES = ("crunchbase.com", "tracxn.com", "pitchbook.com", "cbinsights.com",
                 "techcrunch.com", "wellfound.com", "ycombinator.com", "linkedin.com")
ALTERNATIVE_SITES = ("g2.com", "capterra.com", "alternativeto.net", "getapp.com",
                     "softwareadvice.com", "saasworthy.com", "slashdot.org")

# How many website text pieces each page kind contributes (pricing matters most).
_PAGE_BUDGET = {"home": 2, "pricing": 3, "about": 2, "product": 2, "customers": 2,
                "careers": 1, "security": 1, "integrations": 1, "blog": 1}


@dataclass(frozen=True)
class Subject:
    """Who is being researched, and (optionally) who is asking."""

    name: str
    domain: str = ""
    ticker: str = ""
    asker_name: str = ""
    asker_domain: str = ""


# ------------------------------------------------------------------ website
def _pieces(text: str, n: int) -> list[str]:
    return [text[i:i + _PIECE_CHARS] for i in range(0, len(text), _PIECE_CHARS)][:n]


def website_evidence(domain: str, *, kinds: tuple[str, ...] = (), source: str =
                     "company_website", owner: str = "") -> list[RetrievedChunk]:
    """Citable pieces of a company's own pages (optionally only some page kinds)."""
    if web_offline() or not normalize_domain(domain):
        return []
    from ..tools.website import read_site

    site = read_site(domain)
    out: list[RetrievedChunk] = []
    for page in site.pages:
        if kinds and page.kind not in kinds:
            continue
        lead = f"{page.description} " if page.description else ""
        for piece in _pieces(lead + page.text, _PAGE_BUDGET.get(page.kind, 1)):
            label = f"{owner or site.domain} — {page.kind} page"
            out.append(_chunk(source, page.url, len(out), piece,
                              page.title or label, page.url, stable=True, page_kind=page.kind))
    return out


def website_audit(domain: str) -> list[RetrievedChunk]:
    """What the site does and doesn't show — observed facts, not opinions.

    Absence is evidence for a small company: no pricing page means sales-led pricing,
    no security/trust page is a procurement risk for enterprise buyers, an active
    careers page is a growth signal."""
    if web_offline() or not normalize_domain(domain):
        return []
    from ..tools.website import read_site

    site = read_site(domain)
    if not site.pages:
        text = (f"The website {domain} could not be read ({site.error or 'no pages'}); "
                "no first-party information was available.")
        return [_chunk("website_audit", domain, 0, text, f"{domain} website check",
                       f"https://{domain}")]
    kinds = {p.kind for p in site.pages}
    lines = [f"An automated read of up to 8 pages of {domain} found: "
             f"{', '.join(sorted(kinds))}. Pages not found by the crawler may still exist "
             "(e.g. behind JavaScript or under unusual paths)."]
    checks = [("pricing", "a public pricing page", "a public pricing page (pricing may "
               "be sales-led)"),
              ("security", "a security, trust or privacy page", "a security or trust page"),
              ("careers", "a careers/jobs page (hiring signal)", "a careers page"),
              ("customers", "a customers / case studies page", "a customer or case-study "
               "page")]
    for kind, has, lacks in checks:
        lines.append(f"Found {has}." if kind in kinds else f"Did not find {lacks}.")
    facts = site.facts
    if facts.get("foundingDate"):
        lines.append(f"Founding date in site metadata: {facts['foundingDate']}.")
    if facts.get("numberOfEmployees"):
        lines.append(f"Employee count in site metadata: {facts['numberOfEmployees']}.")
    if site.blocked_by_robots:
        lines.append(f"{len(site.blocked_by_robots)} page(s) not read (disallowed by robots.txt).")
    return [_chunk("website_audit", domain, 0, " ".join(lines), f"{domain} website check",
                   f"https://{domain}")]


# ------------------------------------------------------------------ search-based
def _search(subject: Subject, query: str, source: str, *, sites: tuple[str, ...] = (),
            max_results: int = 4, keep: int = 3) -> list[RetrievedChunk]:
    if web_offline():
        return []
    from ..tools.web_search import web_search

    try:
        hits = web_search(query, max_results=max_results, include_domains=sites)
    except Exception as exc:  # web_search already degrades; belt and braces
        log.warning("%s search failed: %s", source, exc)
        return []
    entity = entity_terms(subject.name, subject.ticker, subject.domain)
    hits = filter_hits_for_entity(hits or [], entity, label=source)
    out = []
    for hit in hits[:keep]:
        text = (hit.get("content") or "").strip()
        if text:
            out.append(_chunk(source, hit.get("url", "") or query, len(out),
                              text[:_PIECE_CHARS * 2], (hit.get("title") or source).strip(),
                              hit.get("url", ""), stable=True))
    return out


def _q(subject: Subject) -> str:
    """How to name the company in a search: brand plus domain disambiguates."""
    return f'"{subject.name}" {subject.domain}'.strip() if subject.domain else \
        f'"{subject.name}"'


def review_evidence(s: Subject) -> list[RetrievedChunk]:
    return _search(s, f"{_q(s)} reviews customers pros cons", "reviews",
                   sites=REVIEW_SITES, max_results=6, keep=4)


def complaint_evidence(s: Subject) -> list[RetrievedChunk]:
    return _search(s, f"{_q(s)} complaints problems issues cancel refund bad experience",
                   "reviews", sites=REVIEW_SITES, max_results=6, keep=3)


def employee_evidence(s: Subject) -> list[RetrievedChunk]:
    return _search(s, f"{_q(s)} employee reviews culture management", "employee_reviews",
                   sites=EMPLOYEE_SITES, keep=2)


def linkedin_evidence(s: Subject) -> list[RetrievedChunk]:
    # Public LinkedIn pages as indexed by search — headcount band, HQ, posts, hiring.
    return _search(s, f"{_q(s)} company employees hiring", "linkedin",
                   sites=("linkedin.com",), keep=3)


def funding_evidence(s: Subject) -> list[RetrievedChunk]:
    return _search(s, f"{_q(s)} funding raised investors seed series revenue", "funding",
                   sites=FUNDING_SITES, keep=3)


def red_flag_evidence(s: Subject) -> list[RetrievedChunk]:
    return _search(s, f"{_q(s)} lawsuit OR layoffs OR breach OR outage OR shutdown OR "
                   "acquired", "company_news", keep=3)


def alternatives_evidence(s: Subject) -> list[RetrievedChunk]:
    return _search(s, f"{_q(s)} alternatives competitors vs", "alternatives",
                   sites=ALTERNATIVE_SITES, max_results=6, keep=4)


def asker_evidence(s: Subject) -> list[RetrievedChunk]:
    """The asker's own positioning (home + pricing), for a head-to-head comparison."""
    if not s.asker_domain or normalize_domain(s.asker_domain) == normalize_domain(s.domain):
        return []
    return website_evidence(s.asker_domain, kinds=("home", "pricing", "product"),
                            source="asker_website", owner=s.asker_name or s.asker_domain)


# ------------------------------------------------------------------ per specialist
def company_evidence_for(agent: str, s: Subject) -> list[RetrievedChunk]:
    """The private-company evidence slice for one specialist."""
    if not s.name and not s.domain:
        return []
    if agent == "fundamentals":      # what they do, how they make money, how big
        return (website_evidence(s.domain, kinds=("home", "about", "product", "pricing",
                                                  "customers"))
                + funding_evidence(s) + linkedin_evidence(s))
    if agent == "news_sentiment":    # what customers say, what's happening now
        return review_evidence(s) + linkedin_evidence(s)[:1]
    if agent == "risk":              # the negatives a sales page never shows
        return (complaint_evidence(s) + employee_evidence(s) + red_flag_evidence(s)
                + website_audit(s.domain))
    if agent == "market":            # who else does this, and versus the asker
        return (alternatives_evidence(s)
                + website_evidence(s.domain, kinds=("home", "pricing"))[:3]
                + asker_evidence(s))
    return []
