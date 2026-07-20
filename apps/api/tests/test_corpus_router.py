"""/corpus ingestion endpoint tests (offline) — the app must be teachable at runtime."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from atlas.main import app

client = TestClient(app)

LONG_TEXT = (
    "Northwind Robotics reported revenue of $1.2 billion in fiscal 2025, up 18% year "
    "over year, driven by its warehouse automation segment and a growing services book. "
    "Its three largest customers accounted for 31% of total revenue."
)


def test_status_reports_the_indexed_corpus():
    r = client.get("/corpus/status")
    assert r.status_code == 200
    body = r.json()
    assert {"documents", "document_count", "chunk_count"} <= set(body)
    assert body["chunk_count"] >= 0


def test_add_text_indexes_a_document():
    r = client.post(
        "/corpus/text",
        json={"title": "Northwind Robotics Profile", "text": LONG_TEXT, "source": "upload"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["chunks_created"] >= 1
    assert body["doc_id"] == "northwind_robotics_profile"


def test_reingesting_the_same_text_adds_no_duplicate_chunks():
    payload = {"title": "Dup Check Doc", "text": LONG_TEXT}
    first = client.post("/corpus/text", json=payload).json()
    second = client.post("/corpus/text", json=payload).json()
    assert first["chunks_created"] == second["chunks_created"]
    assert second["chunks_added"] == 0  # idempotent — stable chunk ids


def test_upload_accepts_a_text_file():
    file = ("northwind.md", io.BytesIO(LONG_TEXT.encode()), "text/markdown")
    r = client.post("/corpus/upload", files={"file": file})
    assert r.status_code == 200
    assert r.json()["chunks_created"] >= 1


def test_upload_rejects_binary_extensions():
    file = ("report.pdf", io.BytesIO(b"%PDF-1.4 binary"), "application/pdf")
    r = client.post("/corpus/upload", files={"file": file})
    assert "error" in r.json()  # indexing binary would poison retrieval


def test_upload_rejects_too_short_content():
    file = ("tiny.txt", io.BytesIO(b"hello"), "text/plain")
    r = client.post("/corpus/upload", files={"file": file})
    assert "error" in r.json()


def test_add_text_validates_minimum_length():
    r = client.post("/corpus/text", json={"title": "Too short", "text": "nope"})
    assert r.status_code == 422  # pydantic min_length


def test_uploaded_document_becomes_retrievable():
    client.post(
        "/corpus/text",
        json={"title": "Zephyr Dynamics Filing", "text": LONG_TEXT.replace("Northwind", "Zephyr")},
    )
    from atlas.core.graph import get_index

    hits = get_index().retrieve("Zephyr Dynamics revenue", top_k=3)
    assert any("Zephyr" in h.chunk.text for h in hits)
