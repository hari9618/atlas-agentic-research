"""Application-level encryption for data at rest in Postgres.

The managed database already encrypts its disks. That protects against a stolen
drive, not against what actually leaks in practice: a database dump, a backup copied
somewhere it shouldn't be, an over-privileged read replica or SQL console. So the
sensitive *values* — emails, names, research state (queries, drafts, reviewer
feedback), learning-loop records, episodic memories — are encrypted by the app before
they are written. The database only ever holds ciphertext; the key lives in the API's
environment (``DATA_ENCRYPTION_KEY``), never in the database.

Design:

* **AES-256-GCM** (authenticated: tampering is detected, not silently decrypted),
  random 96-bit nonce per value.
* **Per-purpose subkeys** via HKDF from one master key, so the encryption key and the
  blind-index key are never the same bytes.
* **Context binding** — the column name is the GCM associated data, so a ciphertext
  copied from ``users.email`` into another column fails to decrypt.
* **Key rotation without downtime** — every value carries its key id
  (``enc:v1:<kid>:<payload>``). Old keys stay listed in
  ``DATA_ENCRYPTION_KEYS_PREVIOUS`` for decryption; ``python -m
  atlas.security.rotate_keys`` re-encrypts everything under the active key.
* **Blind index** for lookups — an email can't be found by ciphertext (the nonce makes
  every encryption different), so the users table also stores an HMAC of the
  normalized email. Lookups compute it under every known key, so they keep working
  mid-rotation.
* **Legacy passthrough** — a value without the ``enc:`` prefix is returned as-is, so
  data written before encryption was switched on stays readable until rotated.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import threading
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..config import get_settings
from ..paths import cache_dir

log = logging.getLogger("atlas.security.crypto")

PREFIX = "enc:v1:"
_NONCE = 12


class EncryptionConfigError(RuntimeError):
    pass


class DecryptionError(ValueError):
    pass


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def generate_key() -> str:
    """A new master key, in the format ``DATA_ENCRYPTION_KEY`` expects."""
    return _b64e(secrets.token_bytes(32))


def _parse_master(raw: str, label: str) -> bytes:
    try:
        key = _b64d(raw.strip())
    except Exception as exc:
        raise EncryptionConfigError(f"{label} is not valid base64") from exc
    if len(key) != 32:
        raise EncryptionConfigError(f"{label} must decode to 32 bytes (got {len(key)})")
    return key


def _subkey(master: bytes, purpose: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=f"atlas/{purpose}/v1".encode()).derive(master)


@dataclass(frozen=True)
class _Key:
    kid: str
    aead: AESGCM
    index_key: bytes


class Keyring:
    def __init__(self, active: tuple[str, bytes], previous: list[tuple[str, bytes]],
                 source: str) -> None:
        def build(kid: str, master: bytes) -> _Key:
            return _Key(kid, AESGCM(_subkey(master, "field-encryption")),
                        _subkey(master, "blind-index"))

        self.active = build(*active)
        self.by_id = {self.active.kid: self.active}
        for kid, master in previous:
            self.by_id.setdefault(kid, build(kid, master))
        self.source = source  # "env" | "dev-file" — surfaced in /health/ready

    # ---------------------------------------------------------- strings
    def encrypt(self, plaintext: str | None, context: str) -> str | None:
        if plaintext is None:
            return None
        nonce = os.urandom(_NONCE)
        ct = self.active.aead.encrypt(nonce, plaintext.encode(), context.encode())
        return f"{PREFIX}{self.active.kid}:{_b64e(nonce + ct)}"

    def decrypt(self, value: str | None, context: str) -> str | None:
        if value is None or not value.startswith(PREFIX):
            return value  # legacy plaintext (written before encryption was enabled)
        try:
            kid, payload = value[len(PREFIX):].split(":", 1)
            key = self.by_id[kid]
            raw = _b64d(payload)
            return key.aead.decrypt(raw[:_NONCE], raw[_NONCE:], context.encode()).decode()
        except KeyError as exc:
            raise DecryptionError(f"unknown encryption key id in {context}") from exc
        except Exception as exc:
            raise DecryptionError(f"cannot decrypt {context} (wrong key or tampered)") from exc

    def needs_rotation(self, value: str | None) -> bool:
        return bool(value) and not value.startswith(f"{PREFIX}{self.active.kid}:")

    # ---------------------------------------------------------- bytes (checkpoints)
    def encrypt_bytes(self, data: bytes, context: str) -> bytes:
        nonce = os.urandom(_NONCE)
        kid = self.active.kid.encode()
        return bytes([len(kid)]) + kid + nonce + self.active.aead.encrypt(
            nonce, data, context.encode())

    def decrypt_bytes(self, blob: bytes, context: str) -> bytes:
        try:
            n = blob[0]
            kid = blob[1:1 + n].decode()
            body = blob[1 + n:]
            return self.by_id[kid].aead.decrypt(body[:_NONCE], body[_NONCE:], context.encode())
        except Exception as exc:
            raise DecryptionError(f"cannot decrypt {context}") from exc

    # ---------------------------------------------------------- blind index
    def blind_index(self, value: str, context: str) -> str:
        return self._index(self.active, value, context)

    def blind_indexes(self, value: str, context: str) -> list[str]:
        """The value's index under every known key (lookups during a rotation)."""
        return [self._index(k, value, context) for k in self.by_id.values()]

    @staticmethod
    def _index(key: _Key, value: str, context: str) -> str:
        return hmac.new(key.index_key, f"{context}\x00{value}".encode(),
                        hashlib.sha256).hexdigest()


def _dev_key() -> str:
    """Local development only: a key generated once and kept outside the database."""
    path = cache_dir() / "dev_data_encryption.key"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = generate_key()
    path.write_text(key, encoding="utf-8")
    return key


def _build() -> Keyring:
    s = get_settings()
    previous: list[tuple[str, bytes]] = []
    for item in filter(None, (p.strip() for p in s.data_encryption_keys_previous.split(","))):
        kid, _, raw = item.partition(":")
        if not raw:
            raise EncryptionConfigError("DATA_ENCRYPTION_KEYS_PREVIOUS entries are kid:key")
        previous.append((kid.strip(), _parse_master(raw, f"previous key {kid}")))
    if s.data_encryption_key:
        active = (s.data_encryption_key_id, _parse_master(s.data_encryption_key,
                                                          "DATA_ENCRYPTION_KEY"))
        return Keyring(active, previous, "env")
    if s.is_production:
        raise EncryptionConfigError(
            "DATA_ENCRYPTION_KEY is required in production. Generate one with "
            "`python -m atlas.security.crypto` and set it in the host's secret store.")
    log.warning("DATA_ENCRYPTION_KEY not set — using a local development key file.")
    return Keyring(("dev", _parse_master(_dev_key(), "dev key")), previous, "dev-file")


_lock = threading.Lock()
_keyring: Keyring | None = None


def keyring() -> Keyring:
    global _keyring
    with _lock:
        if _keyring is None:
            _keyring = _build()
        return _keyring


def reset_keyring() -> None:
    global _keyring
    with _lock:
        _keyring = None


if __name__ == "__main__":  # python -m atlas.security.crypto → print a fresh key
    print(generate_key())
