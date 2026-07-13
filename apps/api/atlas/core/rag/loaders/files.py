"""Load local corpus files (.md / .txt) into Documents.

Supports a tiny YAML-ish frontmatter block for metadata, so a sample filing can
declare its title/source/url without any parser dependency:

    ---
    title: Acme Corp 10-K (FY2025)
    source: sec_edgar
    url: https://www.sec.gov/...
    ---
    <body text>
"""

from __future__ import annotations

from pathlib import Path

from ....paths import corpus_dir
from ..types import Document


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()
    return meta, parts[2].strip()


def load_corpus_dir(corpus_path: str | Path | None = None) -> list[Document]:
    """Load every .md/.txt file under the corpus dir into a Document.

    Defaults to the repo-root-anchored <repo>/data/corpus so it works regardless
    of the current working directory.
    """
    root = Path(corpus_path) if corpus_path is not None else corpus_dir()
    docs: list[Document] = []
    for path in sorted(root.glob("**/*")):
        if path.suffix.lower() not in {".md", ".txt"} or not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        docs.append(
            Document(
                doc_id=meta.get("doc_id", path.stem),
                text=body,
                source=meta.get("source", "upload"),
                title=meta.get("title", path.stem.replace("_", " ")),
                url=meta.get("url", str(path)),
                metadata={k: v for k, v in meta.items()
                          if k not in {"doc_id", "source", "title", "url"}},
            )
        )
    return docs
