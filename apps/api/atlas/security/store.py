"""Durable auth state: users, refresh-token families and the shared signing secret.

Refresh tokens are stored only as SHA-256 hashes — a database leak yields nothing
replayable (the tokens are 256-bit random, so a fast hash is fine; no salt needed).
Emails and names are encrypted (AES-256-GCM, ``security.crypto``); the email is found
by its blind index (an HMAC), so the database never holds a readable address.
Each login starts a *family*; every refresh rotates the token within it. Presenting a
token that was already rotated means it was copied — the whole family is revoked
(OAuth 2.0 Security BCP, "refresh token rotation with reuse detection").
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ..core.sqldb import SqlDb
from ..paths import cache_dir
from .crypto import DecryptionError, EncryptionConfigError, keyring

_DDL = [
    """CREATE TABLE IF NOT EXISTS atlas_users (
        id TEXT PRIMARY KEY,
        email_hash TEXT UNIQUE,
        email_enc TEXT,
        name_enc TEXT,
        password_hash TEXT,
        role TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_login_at TEXT,
        disabled INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS atlas_refresh_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        family_id TEXT NOT NULL,
        created_at DOUBLE PRECISION NOT NULL,
        expires_at DOUBLE PRECISION NOT NULL,
        revoked_at DOUBLE PRECISION,
        rotated_at DOUBLE PRECISION
    )""",
    "CREATE INDEX IF NOT EXISTS atlas_refresh_tokens_family ON atlas_refresh_tokens (family_id)",
    "CREATE INDEX IF NOT EXISTS atlas_refresh_tokens_user ON atlas_refresh_tokens (user_id)",
    """CREATE TABLE IF NOT EXISTS atlas_secrets (
        name TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
]

_USER_COLS = ("id, email_hash, email_enc, name_enc, password_hash, role, created_at, "
              "last_login_at, disabled")
_EMAIL_CTX, _NAME_CTX = "atlas_users.email", "atlas_users.name"


@dataclass(frozen=True)
class User:
    id: str
    email: str | None
    name: str | None
    role: str
    password_hash: str | None = None
    disabled: bool = False

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role}


@dataclass(frozen=True)
class RefreshRow:
    user_id: str
    family_id: str
    expires_at: float
    revoked_at: float | None
    rotated_at: float | None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _user(row: dict | None) -> User | None:
    if row is None:
        return None
    ring = keyring()
    return User(id=row["id"], email=ring.decrypt(row["email_enc"], _EMAIL_CTX),
                name=ring.decrypt(row["name_enc"], _NAME_CTX), role=row["role"],
                password_hash=row["password_hash"], disabled=bool(row["disabled"]))


class EmailTakenError(Exception):
    pass


class AuthStore:
    def __init__(self, db: SqlDb) -> None:
        self.db = db
        db.ddl(_DDL)

    # ---------------------------------------------------------------- users
    def create_user(self, *, email: str | None, name: str | None,
                    password_hash: str | None, role: str) -> User:
        uid = uuid.uuid4().hex
        ring = keyring()
        n = self.db.execute(
            "INSERT INTO atlas_users (id, email_hash, email_enc, name_enc, password_hash, role, "
            "created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (email_hash) DO NOTHING",
            (uid, ring.blind_index(email, _EMAIL_CTX) if email else None,
             ring.encrypt(email, _EMAIL_CTX), ring.encrypt(name, _NAME_CTX),
             password_hash, role, _now_iso()),
        )
        if n == 0:  # the unique index decided, not a racy SELECT-then-INSERT
            raise EmailTakenError(email)
        return User(id=uid, email=email, name=name, role=role, password_hash=password_hash)

    def user_by_email(self, email: str) -> User | None:
        # Every known key's index: an account keeps working in the middle of a rotation.
        hashes = keyring().blind_indexes(email, _EMAIL_CTX)
        marks = ", ".join(["%s"] * len(hashes))
        return _user(self.db.one(
            f"SELECT {_USER_COLS} FROM atlas_users WHERE email_hash IN ({marks})", hashes))

    def delete_user(self, uid: str) -> bool:
        """Erase an account and its sessions (right to erasure)."""
        self.db.execute("DELETE FROM atlas_refresh_tokens WHERE user_id = %s", (uid,))
        return self.db.execute("DELETE FROM atlas_users WHERE id = %s", (uid,)) == 1

    def set_password(self, uid: str, password_hash: str) -> None:
        self.db.execute("UPDATE atlas_users SET password_hash = %s WHERE id = %s",
                        (password_hash, uid))

    def all_users(self) -> list[dict]:
        """Raw rows (for key rotation)."""
        return self.db.all(f"SELECT {_USER_COLS} FROM atlas_users")

    def rewrite_user_crypto(self, uid: str, email: str | None, name: str | None) -> None:
        ring = keyring()
        self.db.execute(
            "UPDATE atlas_users SET email_hash = %s, email_enc = %s, name_enc = %s WHERE id = %s",
            (ring.blind_index(email, _EMAIL_CTX) if email else None,
             ring.encrypt(email, _EMAIL_CTX), ring.encrypt(name, _NAME_CTX), uid))

    def user_by_id(self, uid: str) -> User | None:
        return _user(self.db.one(f"SELECT {_USER_COLS} FROM atlas_users WHERE id = %s", (uid,)))

    def touch_login(self, uid: str, new_hash: str | None = None) -> None:
        if new_hash:
            self.db.execute("UPDATE atlas_users SET last_login_at = %s, password_hash = %s "
                            "WHERE id = %s", (_now_iso(), new_hash, uid))
        else:
            self.db.execute("UPDATE atlas_users SET last_login_at = %s WHERE id = %s",
                            (_now_iso(), uid))

    def set_role(self, uid: str, role: str) -> None:
        self.db.execute("UPDATE atlas_users SET role = %s WHERE id = %s", (role, uid))

    def purge_guests(self, older_than: timedelta) -> int:
        """Guests are throwaway accounts; drop old ones (and their tokens)."""
        cutoff = (datetime.now(UTC) - older_than).isoformat(timespec="seconds")
        self.db.execute(
            "DELETE FROM atlas_refresh_tokens WHERE user_id IN "
            "(SELECT id FROM atlas_users WHERE role = 'guest' AND created_at < %s)", (cutoff,))
        return self.db.execute(
            "DELETE FROM atlas_users WHERE role = 'guest' AND created_at < %s", (cutoff,))

    # ---------------------------------------------------------------- refresh tokens
    def add_refresh(self, token: str, *, user_id: str, family_id: str, ttl_s: float) -> None:
        now = time.time()
        self.db.execute(
            "INSERT INTO atlas_refresh_tokens (token_hash, user_id, family_id, created_at, "
            "expires_at) VALUES (%s, %s, %s, %s, %s)",
            (hash_token(token), user_id, family_id, now, now + ttl_s),
        )

    def get_refresh(self, token: str) -> RefreshRow | None:
        row = self.db.one(
            "SELECT user_id, family_id, expires_at, revoked_at, rotated_at "
            "FROM atlas_refresh_tokens WHERE token_hash = %s", (hash_token(token),))
        return RefreshRow(**row) if row else None

    def claim_refresh(self, token: str) -> bool:
        """Atomically retire ``token`` for rotation. False if someone else got there first."""
        now = time.time()
        return self.db.execute(
            "UPDATE atlas_refresh_tokens SET revoked_at = %s, rotated_at = %s "
            "WHERE token_hash = %s AND revoked_at IS NULL",
            (now, now, hash_token(token)),
        ) == 1

    def revoke_family(self, family_id: str) -> int:
        return self.db.execute(
            "UPDATE atlas_refresh_tokens SET revoked_at = %s "
            "WHERE family_id = %s AND revoked_at IS NULL", (time.time(), family_id))

    def revoke_user(self, user_id: str) -> int:
        return self.db.execute(
            "UPDATE atlas_refresh_tokens SET revoked_at = %s "
            "WHERE user_id = %s AND revoked_at IS NULL", (time.time(), user_id))

    def purge_expired_tokens(self) -> int:
        return self.db.execute("DELETE FROM atlas_refresh_tokens WHERE expires_at < %s",
                               (time.time() - 86_400,))

    # ---------------------------------------------------------------- secrets
    def shared_secret(self, name: str) -> str:
        """A random secret created once and shared by every instance.

        ``INSERT … ON CONFLICT DO NOTHING`` then ``SELECT``: if two instances boot at
        the same moment, both read back whichever value won the insert.
        """
        self.db.execute(
            "INSERT INTO atlas_secrets (name, value, created_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO NOTHING",
            (name, secrets.token_urlsafe(48), _now_iso()))
        row = self.db.one("SELECT value FROM atlas_secrets WHERE name = %s", (name,))
        return row["value"]


    # ---------------------------------------------------------------- key check
    def verify_key_canary(self) -> None:
        """Prove the configured key can read this database, at boot.

        A wrong ``DATA_ENCRYPTION_KEY`` (a typo, the staging key in production, a
        rotation that dropped the old key too early) would otherwise surface as
        decryption errors deep inside the first research run. A known value encrypted
        on first boot is decrypted here instead; mismatch → refuse to start. Once read,
        it is re-sealed under the active key, so it follows rotations.
        """
        ring = keyring()
        ctx = "atlas_secrets.key_canary"
        row = self.db.one("SELECT value FROM atlas_secrets WHERE name = %s", ("key_canary",))
        if row is None:
            self.db.execute(
                "INSERT INTO atlas_secrets (name, value, created_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (name) DO NOTHING",
                ("key_canary", ring.encrypt(_CANARY, ctx), _now_iso()))
            return
        try:
            ok = ring.decrypt(row["value"], ctx) == _CANARY
        except DecryptionError:
            ok = False
        if not ok:
            raise EncryptionConfigError(
                "DATA_ENCRYPTION_KEY cannot decrypt this database (key-check failed). "
                "Use the key the data was written with, or list it in "
                "DATA_ENCRYPTION_KEYS_PREVIOUS during a rotation.")
        if ring.needs_rotation(row["value"]):
            self.db.execute("UPDATE atlas_secrets SET value = %s WHERE name = %s",
                            (ring.encrypt(_CANARY, ctx), "key_canary"))


_CANARY = "atlas-key-check-v1"
_lock = threading.Lock()
_store: AuthStore | None = None


def get_auth_store() -> AuthStore:
    global _store
    with _lock:
        if _store is None:
            _store = AuthStore(SqlDb.default(cache_dir() / "atlas_auth.sqlite"))
        return _store


def set_auth_store(store: AuthStore | None) -> None:
    """Swap the process-wide store (tests)."""
    global _store
    with _lock:
        _store = store
