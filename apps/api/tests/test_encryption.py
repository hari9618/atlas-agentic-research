"""Encryption at rest: the keyring, what reaches the database, TLS to Postgres.

The "nothing readable in the database" tests look at raw storage (the SQLite file's
bytes, or the Postgres row as stored) — checking the API round-trip alone would pass
even if encryption were silently off. Postgres variants run with
``ATLAS_TEST_DATABASE_URL``.
"""

from __future__ import annotations

import os
import uuid

import pytest

from atlas.config import get_settings
from atlas.core.persistence import enforce_tls
from atlas.security import crypto
from atlas.security.crypto import DecryptionError, EncryptionConfigError, Keyring

PG_URL = os.getenv("ATLAS_TEST_DATABASE_URL", "")
needs_pg = pytest.mark.skipif(not PG_URL, reason="ATLAS_TEST_DATABASE_URL unset")


def _ring(active: str = "k1", *previous: str) -> Keyring:
    keys = {k: crypto._b64d(crypto.generate_key()) for k in (active, *previous)}
    return Keyring((active, keys[active]), [(k, keys[k]) for k in previous], "test")


# ---------------------------------------------------------------- keyring
def test_round_trip_and_fresh_nonce_every_time():
    ring = _ring()
    a, b = ring.encrypt("ada@example.com", "users.email"), ring.encrypt("ada@example.com",
                                                                        "users.email")
    assert a != b and a.startswith("enc:v1:k1:")
    assert ring.decrypt(a, "users.email") == "ada@example.com"


def test_ciphertext_is_bound_to_its_column():
    ring = _ring()
    token = ring.encrypt("secret", "users.email")
    with pytest.raises(DecryptionError):
        ring.decrypt(token, "users.name")


def test_tampering_is_detected():
    ring = _ring()
    token = ring.encrypt("secret", "c")
    flipped = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
    with pytest.raises(DecryptionError):
        ring.decrypt(flipped, "c")


def test_legacy_plaintext_passes_through():
    assert _ring().decrypt("written-before-encryption", "c") == "written-before-encryption"
    assert _ring().decrypt(None, "c") is None


def test_rotation_keeps_old_data_readable_and_lookups_working():
    k0, k1 = (crypto._b64d(crypto.generate_key()) for _ in range(2))
    old = Keyring(("k0", k0), [], "test")
    token = old.encrypt("ada@example.com", "users.email")
    index = old.blind_index("ada@example.com", "users.email")
    # New active key k1; k0 retired but kept for decryption.
    new = Keyring(("k1", k1), [("k0", k0)], "test")
    assert new.decrypt(token, "users.email") == "ada@example.com"
    assert new.needs_rotation(token)
    assert index in new.blind_indexes("ada@example.com", "users.email")
    assert new.blind_index("ada@example.com", "users.email") != index


def test_bytes_round_trip_carries_the_key_id():
    ring = _ring("k7")
    blob = ring.encrypt_bytes(b"checkpoint", "cp")
    assert ring.decrypt_bytes(blob, "cp") == b"checkpoint"
    with pytest.raises(DecryptionError):
        _ring("k7").decrypt_bytes(blob, "cp")  # same id, different key


def test_production_refuses_to_run_without_a_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "data_encryption_key", "")
    monkeypatch.setattr(get_settings(), "app_env", "production")
    crypto.reset_keyring()
    try:
        with pytest.raises(EncryptionConfigError):
            crypto.keyring()
    finally:
        crypto.reset_keyring()


def test_bad_key_material_is_rejected(monkeypatch):
    monkeypatch.setattr(get_settings(), "data_encryption_key", "dG9vLXNob3J0")
    crypto.reset_keyring()
    try:
        with pytest.raises(EncryptionConfigError):
            crypto.keyring()
    finally:
        crypto.reset_keyring()


# ---------------------------------------------------------------- TLS
@pytest.mark.parametrize("url,expected", [
    ("postgresql://u:p@db.example.com/atlas", "sslmode=require"),
    ("postgresql://u:p@db.example.com/atlas?sslmode=prefer", "sslmode=require"),
    ("postgresql://u:p@db.example.com/atlas?sslmode=verify-full", "sslmode=verify-full"),
])
def test_production_connections_require_tls(url, expected):
    assert expected in enforce_tls(url, production=True)


def test_plaintext_to_a_remote_db_is_refused_in_production():
    with pytest.raises(ValueError):
        enforce_tls("postgresql://u:p@db.example.com/atlas?sslmode=disable", production=True)


def test_local_and_dev_connections_are_left_alone():
    assert enforce_tls("postgresql://u:p@localhost:5433/atlas", production=True) == \
        "postgresql://u:p@localhost:5433/atlas"
    assert enforce_tls("postgresql://u:p@db.example.com/a", production=False) == \
        "postgresql://u:p@db.example.com/a"


# ---------------------------------------------------------------- what reaches storage
def test_user_rows_hold_no_readable_email(tmp_path):
    from atlas.core.sqldb import SqlDb
    from atlas.security.store import AuthStore

    path = tmp_path / "auth.sqlite"
    store = AuthStore(SqlDb(path=path))
    store.create_user(email="grace.hopper@example.com", name="Grace Hopper",
                      password_hash="h", role="user")
    store.db.close()
    raw = path.read_bytes() + (tmp_path / "auth.sqlite-wal").read_bytes() \
        if (tmp_path / "auth.sqlite-wal").exists() else path.read_bytes()
    assert b"grace.hopper" not in raw and b"Grace Hopper" not in raw
    reopened = AuthStore(SqlDb(path=path))
    assert reopened.user_by_email("grace.hopper@example.com").name == "Grace Hopper"


def _checkpoint(secret: str) -> tuple[dict, dict, dict, dict]:
    from langgraph.checkpoint.base import empty_checkpoint

    cp = empty_checkpoint()
    cp["channel_values"] = {"query": secret, "findings": [{"claim": secret}]}
    cp["channel_versions"] = {"query": 1, "findings": 1}
    config = {"configurable": {"thread_id": f"t-{uuid.uuid4().hex[:6]}", "checkpoint_ns": ""},
              # Run metadata LangGraph would merge into stored checkpoint metadata.
              "metadata": {"atlas_query": secret}}
    metadata = {"source": "loop", "step": 1, "writes": {"node": {"report": secret}}}
    return config, cp, metadata, {"query": 1, "findings": 1}


def test_sqlite_checkpoints_are_encrypted(tmp_path):
    import sqlite3

    from atlas.core.checkpoint_crypto import encrypted_serde, encrypted_sqlite_saver_cls

    db = tmp_path / "cp.sqlite"
    saver = encrypted_sqlite_saver_cls()(sqlite3.connect(str(db), check_same_thread=False),
                                         serde=encrypted_serde())
    secret = "CONFIDENTIAL-ACQUISITION-TARGET"
    config, cp, metadata, versions = _checkpoint(secret)
    saved = saver.put(config, cp, metadata, versions)
    saver.conn.commit()
    assert secret.encode() not in db.read_bytes()
    loaded = saver.get_tuple(saved)
    assert loaded.checkpoint["channel_values"]["query"] == secret
    assert "writes" not in loaded.metadata and "atlas_query" not in loaded.metadata


@needs_pg
def test_postgres_checkpoints_are_encrypted():
    from atlas.core.persistence import open_pg_pool, postgres_saver

    pool = open_pg_pool(PG_URL)
    saver = postgres_saver(pool)
    secret = f"CONFIDENTIAL-{uuid.uuid4().hex[:6]}"
    config, cp, metadata, versions = _checkpoint(secret)
    saved = saver.put(config, cp, metadata, versions)
    thread = config["configurable"]["thread_id"]
    with pool.connection() as conn:
        rows = conn.execute("SELECT checkpoint::text AS c, metadata::text AS m FROM checkpoints "
                            "WHERE thread_id = %s", (thread,)).fetchall()
        blobs = conn.execute("SELECT blob FROM checkpoint_blobs WHERE thread_id = %s",
                             (thread,)).fetchall()
    stored = "".join(r["c"] + r["m"] for r in rows)
    assert secret not in stored  # inline str value sealed, metadata writes dropped
    assert all(secret.encode() not in bytes(b["blob"] or b"") for b in blobs)
    assert saver.get_tuple(saved).checkpoint["channel_values"]["query"] == secret


@needs_pg
def test_postgres_documents_and_episodes_are_encrypted():
    from datetime import UTC, datetime

    from atlas.core.llmops.store import DocumentStore
    from atlas.core.memory.episodic import _PostgresBackend
    from atlas.core.persistence import open_pg_pool

    pool = open_pg_pool(PG_URL)
    secret = f"REVIEWER-FEEDBACK-{uuid.uuid4().hex[:6]}"
    docs = DocumentStore(f"t{uuid.uuid4().hex[:6]}", pool=pool)
    docs.put("r1", {"feedback": secret})
    episodes = _PostgresBackend(pool)
    eid = episodes.insert(secret, "Acme", f"report {secret}", 0.7, [{"claim": secret}],
                          datetime.now(UTC), None)
    with pool.connection() as conn:
        doc_raw = conn.execute("SELECT data::text AS d FROM atlas_llmops_documents "
                               "WHERE kind = %s", (docs.kind,)).fetchone()["d"]
        ep_raw = conn.execute("SELECT query || coalesce(report,'') || findings::text AS t "
                              "FROM atlas_episodes WHERE id = %s", (eid,)).fetchone()["t"]
    assert secret not in doc_raw and secret not in ep_raw
    assert docs.get("r1")["feedback"] == secret
    row = next(r for r in episodes.recent(50) if r[0] == eid)
    assert row[1] == secret and row[5] == [{"claim": secret}]
