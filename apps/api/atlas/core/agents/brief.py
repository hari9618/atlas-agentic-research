"""The research brief: who is asking, about whom, and what they need to decide.

"My company is caughtleads.com — should I worry about revsquad.ai as a competitor?"
contains two companies. The old planner asked the model for "the target" and got the
first one named — the asker's own company — so the whole run researched the wrong
business. A due-diligence question always has this shape:

* **subject** — the company being evaluated (name, website domain, ticker if listed);
* **asker** — optionally, the user's own company ("my company is…", "we are…");
* **persona** — why they ask: ``investor`` (should I invest?), ``competitor`` (is it a
  threat to us?), ``buyer`` (should we buy from / partner with them?), ``job_seeker``,
  or ``general``;
* **goal** — the decision the report must help make, in one sentence;
* **extra_asks** — anything specific beyond the standard brief ("what's their pricing
  for 50 seats?", "who are their biggest customers?").

The model drafts the brief; deterministic rules then *verify* it, because the failure
above is exactly the kind a model makes confidently: domains and "my company is X"
phrases are extracted from the text itself, and if the model's subject is the asker,
the subject is swapped to the other company mentioned.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from ..rag.entity import normalize_domain, normalize_name

PERSONAS = ("investor", "competitor", "buyer", "partner", "job_seeker", "general")

_DOMAIN = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|ai|io|co|in|net|org|app|dev|tech|so|xyz|"
                     r"us|uk|de|fr|eu|ca|au|me|cloud|software|digital|agency|biz|info|"
                     r"co\.uk|co\.in))\b", re.I)
# Case-insensitive cue, case-SENSITIVE name: "I run a bakery" names no company, while
# "I run Acme" and "my company is caughtleads.com" do. "We are …" is deliberately not a
# cue ("we are considering buying from X" / "we are a 10-person startup").
_NAME = r"((?:[A-Z][\w&.-]*|[a-z0-9-]+\.[a-z]{2,24})(?:\s+[A-Z][\w&-]*){0,3})"
_ASKER = re.compile(
    r"(?i:\b(?:my|our)\s+(?:company|startup|business|firm|product|brand|team)"
    r"(?:\s+(?:is|called|named))?)\s*[:\-]?\s*" + _NAME
    + r"|(?i:\b(?:i|we)\s+(?:run|own|founded|work\s+at|am\s+at|built))\s+" + _NAME)
_NOT_ASKER = {"a", "an", "the", "this", "that", "it", "here", "there"}
# Capitalised runs inside one sentence/clause (never across ". " or ", ").
_CAP_RUN = re.compile(r"[A-Z][\w&\-]*(?:\s+[A-Z][\w&\-]*)*")
_QUESTION_WORDS = {
    "should", "i", "is", "are", "was", "what", "whats", "how", "why", "who", "when",
    "which", "can", "could", "does", "do", "did", "will", "would", "evaluate", "assess",
    "analyze", "analyse", "compare", "tell", "give", "me", "the", "a", "an", "worry",
    "invest", "research", "review", "about", "please", "my", "we", "our", "us", "ceo",
    "hey", "hi", "hello", "yes", "no", "ok",
}

_PERSONA_CUES: list[tuple[str, tuple[str, ...]]] = [
    ("competitor", ("competitor", "competetor", "compete", "competition", "threat", "worry",
                    "rival", "vs my", "against us", "eat our", "steal")),
    ("investor", ("invest", "investment", "valuation", "fund ", "funding round", "stake",
                  "returns", "buy shares", "stock")),
    ("buyer", ("vendor", "should we buy", "should we use", "should i use", "purchase",
               "buy from", "should i buy from", "use them", "sign up for",
               "sign up with", "switch to", "procure", "trust them", "is it legit",
               "reliable", "safe to use")),
    ("partner", ("partner", "partnership", "integrate with", "reseller", "collaborate")),
    ("job_seeker", ("job offer", "work there", "join them", "employer", "culture")),
]


@dataclass
class Brief:
    subject: str
    subject_domain: str = ""
    ticker: str = ""
    asker: str = ""
    asker_domain: str = ""
    persona: str = "general"
    goal: str = ""
    extra_asks: list[str] = field(default_factory=list)
    focus_areas: list[str] = field(default_factory=list)

    def to_state(self) -> dict:
        d = asdict(self)
        d["target"] = d.pop("subject")
        return d


# ------------------------------------------------------------------ deterministic cues
def find_domains(query: str) -> list[str]:
    seen: list[str] = []
    for m in _DOMAIN.finditer(query or ""):
        d = normalize_domain(m.group(1))
        if d and d not in seen:
            seen.append(d)
    return seen


def find_asker(query: str) -> str:
    """The asker's company from phrases like "my company is X" / "I work at X"."""
    m = _ASKER.search(query or "")
    if not m:
        return ""
    name = (m.group(1) or m.group(2) or "").strip(" .,?!")
    name = re.split(r"[.?!,;]\s|\s+(?:and|should|but|so|which|that|is|are)\b", name,
                    maxsplit=1, flags=re.I)[0].strip(" .,?!")
    return "" if name.lower() in _NOT_ASKER else name


def named_entities(query: str) -> list[str]:
    """Capitalised names in the question, clause by clause, question words removed."""
    out: list[str] = []
    for clause in re.split(r"[.?!,;:]\s+|\n", query or ""):
        for run in _CAP_RUN.findall(clause):
            words = [w for w in run.split() if w.lower().strip(".") not in _QUESTION_WORDS]
            name = " ".join(words).strip(" .?!,")
            if name and name not in out:
                out.append(name)
    return out


def guess_persona(query: str) -> str:
    q = f" {(query or '').lower()} "
    for persona, cues in _PERSONA_CUES:
        if any(c in q for c in cues):
            return persona
    return "general"


def brand_of(domain: str) -> str:
    """``revsquad.ai`` → ``Revsquad`` (a readable stand-in until the site names itself)."""
    label = normalize_domain(domain).split(".")[0]
    return label[:1].upper() + label[1:] if label else ""


def _same(a: str, b: str) -> bool:
    na, nb = normalize_name(a).replace(" ", ""), normalize_name(b).replace(" ", "")
    return bool(na) and bool(nb) and (na == nb or na in nb or nb in na)


def _matches_domain(name: str, domain: str) -> bool:
    return bool(domain) and _same(name, brand_of(domain))


# ------------------------------------------------------------------ verification
def verify(brief: Brief, query: str) -> Brief:
    """Correct the model's brief with what the question itself says."""
    domains = find_domains(query)
    asker_hint = find_asker(query)
    if asker_hint and not brief.asker:
        brief.asker = asker_hint  # case-sensitive capture: a real name or a domain
    if brief.asker:
        own = normalize_domain(brief.asker) or next(
            (d for d in domains if _matches_domain(brief.asker, d)), "")
        brief.asker_domain = brief.asker_domain or own
        if normalize_domain(brief.asker):          # "caughtleads.com" given as the name
            brief.asker = brand_of(brief.asker)

    # The bug this module exists for: subject == asker while another company is named.
    subject_is_asker = brief.asker and (
        _same(brief.subject, brief.asker)
        or (brief.subject_domain and brief.subject_domain == brief.asker_domain))
    others = [d for d in domains if d != brief.asker_domain]
    if subject_is_asker or not brief.subject:
        names = [n for n in named_entities(query) if not _same(n, brief.asker or "\x00")]
        if others:
            brief.subject, brief.subject_domain = brand_of(others[0]), others[0]
        elif names:  # "Is Acme a competitor to my company Beta Labs?" → Acme
            brief.subject, brief.subject_domain = max(names, key=len), ""
        elif subject_is_asker:
            brief.subject = ""  # nothing else named: let the caller fall back
    if not brief.subject_domain:
        brief.subject_domain = next(
            (d for d in others if _matches_domain(brief.subject, d)),
            normalize_domain(brief.subject) or (others[0] if len(others) == 1 and
                                                not brief.subject else ""))
    if normalize_domain(brief.subject):            # model returned "revsquad.ai" as name
        brief.subject = brand_of(brief.subject)
    if brief.persona not in PERSONAS:
        brief.persona = "general"
    if brief.persona == "general":
        brief.persona = guess_persona(query)
    brief.extra_asks = [a for a in brief.extra_asks if a][:5]
    return brief


def offline_brief(query: str, guess_target) -> Brief:
    """No-LLM brief from cues alone (tests, outages)."""
    domains = find_domains(query)
    asker = find_asker(query)
    names = [n for n in named_entities(query) if not (asker and _same(n, asker))]
    subject = "" if domains else (max(names, key=len) if names else guess_target(query))
    b = Brief(subject=subject, persona=guess_persona(query), asker=asker)
    b = verify(b, query)
    if not b.subject:
        b.subject = guess_target(query)
    b.goal = default_goal(b)
    return b


def default_goal(b: Brief) -> str:
    who = b.subject or "the company"
    return {
        "investor": f"Decide whether {who} is a sound investment.",
        "competitor": f"Decide how much of a competitive threat {who} is"
                      + (f" to {b.asker}." if b.asker else "."),
        "buyer": f"Decide whether to buy from or rely on {who}.",
        "partner": f"Decide whether {who} is a good partner.",
        "job_seeker": f"Decide whether {who} is a good place to work.",
    }.get(b.persona, f"Understand {who}: what it does, how it is doing, and its risks.")


def refine_names(brief: Brief) -> Brief:
    """Prefer the name a company's own website uses ("RevSquad", not "Revsquad")."""
    from ..tools.website import read_site

    for attr, dom_attr in (("subject", "subject_domain"), ("asker", "asker_domain")):
        domain = getattr(brief, dom_attr)
        name = getattr(brief, attr)
        if not domain or (name and name != brand_of(domain)):
            continue  # the model or the user already gave a proper name
        site = read_site(domain)  # cached: the specialists reuse this read
        official = str(site.facts.get("name") or "").strip()
        if not official and site.pages:
            official = re.split(r"\s+[|–—:-]\s+", site.pages[0].title)[0].strip()
        if official and _same(official, brand_of(domain)) and len(official) <= 60:
            setattr(brief, attr, official)
    return brief


def describe(state: dict) -> str:
    """One paragraph of brief context for agent prompts."""
    parts = [f"Subject company: {state.get('target') or 'see question'}"
             + (f" ({state['subject_domain']})" if state.get("subject_domain") else "")]
    if state.get("asker"):
        parts.append(f"Asked by: {state['asker']}"
                     + (f" ({state['asker_domain']})" if state.get("asker_domain") else "")
                     + " — the user's OWN company; do not analyse it as the subject.")
    parts.append(f"Reader: {state.get('persona') or 'general'}")
    if state.get("goal"):
        parts.append(f"Decision to support: {state['goal']}")
    if state.get("extra_asks"):
        parts.append("Specific asks: " + "; ".join(state["extra_asks"]))
    return "\n".join(parts)
