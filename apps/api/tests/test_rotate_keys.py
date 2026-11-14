"""Key rotation re-encrypts stored rows and keeps them readable and findable."""

from __future__ import annotations

import uuid

from atlas.config import get_settings
from atlas.core.sqldb import SqlDb
from atlas.security import crypto
from atlas.security.rotate_keys import rotate_users
from atlas.security.store import AuthStore, set_auth_store


def test_rotation_rewrites_users_under_the_new_key(tmp_path, monkeypatch):
    settings = get_settings()
    old_key = settings.data_encryption_key
    store = AuthStore(SqlDb(path=tmp_path / "auth.sqlite"))
    set_auth_store(store)
    try:
        email = f"{uuid.uuid4().hex[:8]}@example.com"
        store.create_user(email=email, name="Ada", password_hash="h", role="user")

        new_key = crypto.generate_key()
        monkeypatch.setattr(settings, "data_encryption_key", new_key)
        monkeypatch.setattr(settings, "data_encryption_key_id", "k2")
        monkeypatch.setattr(settings, "data_encryption_keys_previous", f"k1:{old_key}")
        crypto.reset_keyring()

        assert store.user_by_email(email).name == "Ada"  # found mid-rotation via old index
        assert rotate_users(dry_run=True) == 1
        assert rotate_users(dry_run=False) == 1
        assert rotate_users(dry_run=False) == 0  # idempotent
        row = store.all_users()[0]
        assert row["email_enc"].startswith("enc:v1:k2:")

        # The old key can now be dropped entirely.
        monkeypatch.setattr(settings, "data_encryption_keys_previous", "")
        crypto.reset_keyring()
        assert store.user_by_email(email).name == "Ada"
    finally:
        set_auth_store(None)
        crypto.reset_keyring()
