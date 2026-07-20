"""/corpus — add documents to the knowledge base the agents search.

Until now the corpus could only be filled from the CLI (``make ingest``), which made
the running app read-only: you could ask questions, but not teach it anything new.
These endpoints ingest into the **live, cached index**, so a document uploaded here is
searchable by the very next research run — no restart.

Ingestion is idempotent (stable chunk ids), so re-uploading the same document is safe.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..core.rag.chunking import chunk_document
from ..core.rag.types import Document

router = APIRouter(prefix="/corpus", tags=["corpus"])
log = logging.getLogger("atlas.routers.corpus")

# Plain-text formats only: the chunker works on text, and silently indexing the
# binary of a .pdf/.docx would poison retrieval with garbage.
ALLOWED_SUFFIXES = (".md", ".txt", ".markdown")
MAX_BYTES = 2_000_000


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:60] or "document"


def _add(doc: Document) -> dict:
    """Chunk a document into the live index and report what landed."""
    from ..core.graph import get_index  # late import: keeps the router import-light

    index = get_index()
    before = len(index.chunks)
    chunks = chunk_document(doc)
    index.add_chunks(chunks)
    added = len(index.chunks) - before
    log.info("Ingested %s: %d chunks (+%d new)", doc.doc_id, len(chunks), added)
    return {
        "doc_id": doc.doc_id,
        "title": doc.title,
        "source": doc.source,
        "chunks_created": len(chunks),
        "chunks_added": added,  # 0 means it was already indexed (idempotent)
        "total_chunks": len(index.chunks),
    }


class TextRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    text: str = Field(..., min_length=50)
    source: str = Field("upload", max_length=40)
    url: str = Field("", max_length=500)


class TickerRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    form: str = Field("10-K", max_length=20)


@router.get("/status")
async def status() -> dict:
    """What the agents can currently search."""
    from ..core.graph import get_index

    index = await run_in_threadpool(get_index)
    docs: dict[str, str] = {}
    for c in index.chunks.values():
        docs.setdefault(c.doc_id, c.title or c.doc_id)
    return {
        "documents": [{"doc_id": k, "title": v} for k, v in sorted(docs.items())],
        "document_count": len(docs),
        "chunk_count": len(index.chunks),
    }


@router.post("/text")
async def add_text(req: TextRequest) -> dict:
    """Ingest pasted text (a report, a profile, notes)."""
    doc = Document(
        doc_id=_slug(req.title),
        text=req.text,
        source=req.source or "upload",
        title=req.title,
        url=req.url,
    )
    return await run_in_threadpool(_add, doc)


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    """Ingest an uploaded .md/.txt file."""
    name = file.filename or "upload.txt"
    if not name.lower().endswith(ALLOWED_SUFFIXES):
        return {"error": f"Unsupported file type. Allowed: {', '.join(ALLOWED_SUFFIXES)}"}

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        return {"error": f"File too large (max {MAX_BYTES // 1_000_000} MB)."}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "File must be UTF-8 text."}
    if len(text.strip()) < 50:
        return {"error": "File is too short to be useful evidence."}

    stem = name.rsplit(".", 1)[0]
    doc = Document(doc_id=_slug(stem), text=text, source="upload", title=stem, url=name)
    return await run_in_threadpool(_add, doc)


@router.post("/sec")
async def add_sec_filing(req: TickerRequest) -> dict:
    """Pull a real SEC filing by ticker (e.g. AAPL) and ingest it."""
    from ..core.rag.loaders.sec_edgar import fetch_latest_filing

    doc = await run_in_threadpool(fetch_latest_filing, req.ticker.upper(), form=req.form)
    if not doc:
        return {"error": f"No {req.form} found for {req.ticker.upper()}."}
    return await run_in_threadpool(_add, doc)
