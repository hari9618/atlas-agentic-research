"""Ingestion: corpus files (and optional SEC filings) → chunks → HybridIndex → disk.

Idempotent: stable chunk ids mean re-running never duplicates. Run as a module:

    python -m atlas.core.rag.ingest                 # ingest data/corpus
    python -m atlas.core.rag.ingest --ticker AAPL   # also pull Apple's latest 10-K
    python -m atlas.core.rag.ingest --offline       # hashing embedder (no download)
"""

from __future__ import annotations

import argparse
import logging

from .chunking import chunk_document
from .index import HybridIndex, build_index
from .loaders import load_corpus_dir
from .types import Document

log = logging.getLogger("atlas.rag.ingest")


def ingest_documents(docs: list[Document], *, offline: bool = False) -> HybridIndex:
    index = build_index(offline=offline)
    all_chunks = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))
    index.add_chunks(all_chunks)
    return index


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser(description="Ingest the Atlas corpus.")
    parser.add_argument("--corpus", default="data/corpus", help="corpus directory")
    parser.add_argument("--ticker", action="append", default=[], help="SEC ticker(s) to fetch")
    parser.add_argument("--form", default="10-K", help="SEC form type")
    parser.add_argument("--offline", action="store_true", help="use hashing embedder")
    args = parser.parse_args()

    docs = load_corpus_dir(args.corpus)
    log.info("Loaded %d local documents from %s", len(docs), args.corpus)

    for ticker in args.ticker:
        from .loaders.sec_edgar import fetch_latest_filing

        doc = fetch_latest_filing(ticker, form=args.form)
        if doc:
            docs.append(doc)
            log.info("Fetched %s", doc.title)

    if not docs:
        log.warning("No documents to ingest. Add files under %s.", args.corpus)
        return

    index = ingest_documents(docs, offline=args.offline)
    index.save()
    log.info("Done. Indexed %d chunks from %d documents.", len(index.chunks), len(docs))


if __name__ == "__main__":
    main()
