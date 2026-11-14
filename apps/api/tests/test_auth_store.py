"""The auth store's guarantees on both SQL backends: unique emails, single-winner
refresh rotation, one shared signing secret. Postgres runs when
``ATLAS_TEST_DATABASE_URL`` is set (CI provides it)."""

from __future__ import annotations

import os
import threading
import uuid

import pytest

from atlas.core.sqldb import SqlDb
from atlas.security.store import AuthStore, EmailTakenError

PG_URL = os.getenv("ATLAS_TEST_DATABASE_URL", "")


@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.skipif(
    not PG_URL, reason="ATLAS_TEST_DATABASE_URL unset"))])
def store(request, tmp_path):
    if request.param == "sqlite":
        return AuthStore(SqlDb(path=tmp_path / "auth.sqlite"))
    from atlas.core.persistence import open_pg_pool

    return AuthStore(SqlDb(pool=open_pg_pool(PG_URL)))


def test_emails_are_unique(store):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    user = store.create_user(email=email, name=None, password_hash="h", role="user")
    assert store.user_by_email(email).id == user.id
    with pytest.raises(EmailTakenError):
        store.create_user(email=email, name=None, password_hash="h", role="user")
    # Guests have no email; any number of them may exist.
    store.create_user(email=None, name="Guest", password_hash=None, role="guest")
    store.create_user(email=None, name="Guest", password_hash=None, role="guest")


def test_exactly_one_concurrent_refresh_wins(store):
    user = store.create_user(email=None, name=None, password_hash=None, role="guest")
    token = f"tok-{uuid.uuid4().hex}"
    store.add_refresh(token, user_id=user.id, family_id="fam", ttl_s=60)
    wins: list[bool] = []
    lock = threading.Lock()

    def claim():
        ok = store.claim_refresh(token)
        with lock:
            wins.append(ok)

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert wins.count(True) == 1
    row = store.get_refresh(token)
    assert row.revoked_at is not None and row.rotated_at is not None


def test_revoking_a_family_kills_every_token_in_it(store):
    user = store.create_user(email=None, name=None, password_hash=None, role="guest")
    fam = uuid.uuid4().hex
    for i in range(3):
        store.add_refresh(f"t{i}-{fam}", user_id=user.id, family_id=fam, ttl_s=60)
    assert store.revoke_family(fam) == 3
    assert all(store.get_refresh(f"t{i}-{fam}").revoked_at for i in range(3))


def test_shared_secret_is_created_once(store):
    name = f"k-{uuid.uuid4().hex[:6]}"
    first = store.shared_secret(name)
    assert len(first) >= 48 and store.shared_secret(name) == first


def test_key_canary_detects_a_wrong_key(store, monkeypatch):
    from atlas.config import get_settings
    from atlas.security import crypto
    from atlas.security.crypto import EncryptionConfigError

    store.db.execute("DELETE FROM atlas_secrets WHERE name = %s", ("key_canary",))
    store.verify_key_canary()          # first boot: written
    store.verify_key_canary()          # same key: fine
    settings = get_settings()
    monkeypatch.setattr(settings, "data_encryption_key", crypto.generate_key())
    monkeypatch.setattr(settings, "data_encryption_key_id", "kX")
    crypto.reset_keyring()
    try:
        with pytest.raises(EncryptionConfigError):
            store.verify_key_canary()
    finally:
        monkeypatch.undo()
        crypto.reset_keyring()
