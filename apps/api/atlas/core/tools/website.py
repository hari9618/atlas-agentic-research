"""Company website reader — the primary source for small and private companies.

A startup with no filings, no stock and no press still has a website: what it sells,
to whom, at what price, who its customers are, whether it is hiring. This tool reads
the handful of pages that answer those questions.

It fetches a URL that came from a *user's question*, so it is built defensively:

* **SSRF guard** — only http(s) on default ports, and every hop (including redirects,
  followed manually) must resolve exclusively to public IP addresses. ``localhost``,
  ``169.254.169.254`` (cloud metadata), RFC 1918 ranges, etc. are refused.
  Residual risk: DNS rebinding between the check and the connect (documented in
  docs/security.md); responses are size-capped and never executed.
* **Polite** — honours ``robots.txt`` for our user agent, at most ``MAX_PAGES`` pages,
  sequential requests, a descriptive User-Agent.
* **Bounded** — 10 s per request, 1.5 MB per response, HTML only, text capped per page.

Discovery: links on the homepage scored by what the page is likely to contain
(pricing, about, customers, careers…); when the homepage is a JavaScript shell with
few links, common paths and ``sitemap.xml`` are tried instead.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from ..rag.entity import normalize_domain
from ..upstreams import WEBSITES

log = logging.getLogger("atlas.tools.website")

USER_AGENT = "AtlasResearchBot/1.0 (+https://atlas-web-lake.vercel.app; due-diligence research)"
MAX_PAGES = 8
MAX_BYTES = 1_500_000
MAX_TEXT = 6000
TIMEOUT_S = 10.0
MAX_REDIRECTS = 3

# Page kinds, in the order they matter for a due-diligence read.
_KINDS: list[tuple[str, tuple[str, ...]]] = [
    ("pricing", ("pricing", "plans", "price")),
    ("about", ("about", "company", "team", "who-we-are", "our-story", "leadership")),
    ("product", ("product", "features", "platform", "solutions", "how-it-works", "services")),
    ("customers", ("customers", "case-stud", "testimonials", "success", "clients", "reviews")),
    ("careers", ("careers", "jobs", "join", "hiring", "work-with-us")),
    ("security", ("security", "trust", "compliance", "privacy", "gdpr", "soc")),
    ("integrations", ("integrations", "partners", "marketplace", "apps")),
    ("blog", ("blog", "news", "press", "changelog", "updates")),
]
_FALLBACK_PATHS = ["/pricing", "/about", "/customers", "/careers", "/product", "/features",
                   "/security", "/blog"]


class UnsafeURLError(ValueError):
    """The URL points somewhere we must not fetch (private network, odd scheme/port)."""


@dataclass
class Page:
    url: str
    kind: str
    title: str
    text: str
    description: str = ""


@dataclass
class Site:
    domain: str
    pages: list[Page] = field(default_factory=list)
    facts: dict = field(default_factory=dict)      # from JSON-LD Organization markup
    blocked_by_robots: list[str] = field(default_factory=list)
    error: str = ""

    def __bool__(self) -> bool:  # an empty read is never cached (see Upstream._store)
        return bool(self.pages)


# ------------------------------------------------------------------ SSRF guard
def _public_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"cannot resolve {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURLError(f"{host} resolves to a non-public address")


def check_url(url: str) -> str:
    """Return ``url`` if it is safe to fetch, else raise ``UnsafeURLError``."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("only http(s) URLs are fetched")
    if parts.port not in (None, 80, 443):
        raise UnsafeURLError("non-standard ports are not fetched")
    if parts.username or parts.password:
        raise UnsafeURLError("credentials in URLs are not allowed")
    host = (parts.hostname or "").lower()
    if not host or not normalize_domain(host):
        raise UnsafeURLError("not a public hostname")
    _public_host(host)
    return url


def _get(client: httpx.Client, url: str) -> httpx.Response | None:
    """GET with manual, re-validated redirects and a streamed size cap."""
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        with client.stream("GET", url) as resp:
            if resp.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, resp.headers.get("location", ""))
                continue
            if resp.status_code >= 400:
                if resp.status_code in (429,) or resp.status_code >= 500:
                    resp.raise_for_status()  # transient: let the retry layer judge it
                return None
            ctype = resp.headers.get("content-type", "")
            if not any(t in ctype for t in ("text/html", "application/xhtml", "text/plain",
                                            "application/xml", "text/xml")):
                return None
            body = b""
            for chunk in resp.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    break
            resp._content = body[:MAX_BYTES]  # materialize the capped body
            resp.url_final = url  # type: ignore[attr-defined]
            return resp
    return None


# ------------------------------------------------------------------ parsing
def _kind_of(url: str) -> str:
    path = urlsplit(url).path.lower()
    if path in ("", "/"):
        return "home"
    for kind, keys in _KINDS:
        if any(k in path for k in keys):
            return kind
    return "other"


def _text_of(html: str) -> tuple[str, str, str, list[str], dict]:
    """(title, description, main text, links, org facts) from an HTML page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    facts = _org_facts(soup)
    links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    meta = soup.find("meta", attrs={"name": "description"}) or \
        soup.find("meta", attrs={"property": "og:description"})
    description = (meta.get("content") or "").strip() if meta else ""
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "form",
                     "iframe", "template"]):
        tag.decompose()
    hidden = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0", re.I)
    for tag in list(soup.find_all(True)):
        if getattr(tag, "decomposed", False):  # inside an already-removed parent
            continue
        attrs = tag.attrs or {}
        if ("hidden" in attrs or attrs.get("aria-hidden") == "true"
                or hidden.search(str(attrs.get("style", "")))):
            tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return title[:200], description[:400], text[:MAX_TEXT], links, facts


def _org_facts(soup) -> dict:
    """Founding date, size, location from schema.org Organization JSON-LD, if any."""
    facts: dict = {}
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if not isinstance(item, dict) or "Organization" not in str(item.get("@type", "")):
                continue
            for key in ("name", "foundingDate", "numberOfEmployees", "founder", "address",
                        "sameAs"):
                if item.get(key) and key not in facts:
                    facts[key] = item[key]
    return facts


def _same_site(url: str, domain: str) -> bool:
    host = normalize_domain(url)
    return bool(host) and (host == domain or host.endswith("." + domain))


def _rank_links(base: str, links: list[str], domain: str) -> list[str]:
    seen, scored = set(), []
    for href in links:
        url = urljoin(base, href.split("#")[0]).rstrip("/")
        if not url.startswith("http") or not _same_site(url, domain) or url in seen:
            continue
        if re.search(r"\.(pdf|png|jpe?g|gif|svg|zip|mp4|webp)$", url, re.I):
            continue
        seen.add(url)
        kind = _kind_of(url)
        if kind in ("home", "other"):
            continue
        rank = next(i for i, (k, _) in enumerate(_KINDS) if k == kind)
        depth = urlsplit(url).path.count("/")
        scored.append((rank, depth, url))
    best: dict[str, str] = {}
    for _, _, url in sorted(scored):  # one page per kind, the shallowest
        best.setdefault(_kind_of(url), url)
    return list(best.values())


def _robots(client: httpx.Client, root: str) -> RobotFileParser:
    rp = RobotFileParser()
    try:
        resp = _get(client, f"{root}/robots.txt")
        rp.parse((resp.text if resp is not None else "").splitlines())
    except Exception:
        rp.parse([])  # unreachable robots.txt → no restrictions declared
    return rp


# ------------------------------------------------------------------ crawl
def _crawl(domain: str, max_pages: int) -> Site:
    site = Site(domain=domain)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(headers=headers, timeout=TIMEOUT_S, follow_redirects=False) as client:
        root = f"https://{domain}"
        robots = _robots(client, root)
        home = None
        for candidate in (root, f"https://www.{domain}", f"http://{domain}"):
            try:
                home = _get(client, candidate)
            except UnsafeURLError:
                raise
            except httpx.HTTPError:
                home = None
            if home is not None:
                break
        if home is None:
            site.error = "website unreachable"
            return site
        base = getattr(home, "url_final", root)
        title, desc, text, links, facts = _text_of(home.text)
        site.facts = facts
        site.pages.append(Page(base, "home", title, text, desc))

        targets = _rank_links(base, links, domain)
        if len(targets) < 3:  # JS shell: try conventional paths
            known = {_kind_of(u) for u in targets}
            targets += [urljoin(base, p) for p in _FALLBACK_PATHS if _kind_of(p) not in known]
        for url in targets[: max_pages - 1]:
            if not robots.can_fetch(USER_AGENT, url):
                site.blocked_by_robots.append(url)
                continue
            try:
                resp = _get(client, url)
            except (httpx.HTTPError, UnsafeURLError) as exc:
                log.info("website %s: skip %s (%s)", domain, url, type(exc).__name__)
                continue
            if resp is None:
                continue
            t, d, body, _, _ = _text_of(resp.text)
            if len(body) < 80:  # empty JS shell page: nothing to cite
                continue
            site.pages.append(Page(getattr(resp, "url_final", url), _kind_of(url), t, body, d))
    log.info("website %s: %d pages (%s)", domain, len(site.pages),
             ", ".join(p.kind for p in site.pages))
    return site


def read_site(domain_or_url: str, *, max_pages: int = MAX_PAGES) -> Site:
    """Read a company's site. Never raises: problems are reported in ``Site.error``."""
    domain = normalize_domain(domain_or_url)
    if not domain:
        return Site(domain="", error="not a valid domain")
    try:
        check_url(f"https://{domain}")
        return WEBSITES.call(_crawl, domain, max_pages, cache_key=(domain, max_pages),
                             label=f"tool.website.{domain}")
    except UnsafeURLError as exc:
        log.warning("website %s refused: %s", domain, exc)
        return Site(domain=domain, error=f"refused: {exc}")
    except Exception as exc:
        log.warning("website %s failed: %s", domain, exc)
        return Site(domain=domain, error="website unreachable")
