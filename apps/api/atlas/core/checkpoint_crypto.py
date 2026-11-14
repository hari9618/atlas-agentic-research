"""Encrypted LangGraph checkpoints.

A checkpoint is the full research scratchpad: the question, every specialist's
findings, the debate, the draft report and the reviewer's feedback. Three places in
the stock savers would write that to the database in the clear, and each is closed:

1. **Serialized blobs** (lists, dicts, messages) → ``EncryptedSerializer`` with an
   AES-256-GCM cipher from ``security.crypto`` (key id embedded, so rotation works).
2. **Inline primitives** — the Postgres saver stores ``str`` channel values (the
   query, the report markdown, the feedback) directly in the ``checkpoint`` JSONB
   column, bypassing the serializer. They are encrypted to ``enc:v1:`` strings before
   the write and decrypted after the read.
3. **Metadata** (plain JSONB) — LangGraph copies each step's node outputs into it
   (``writes``) *and* merges every string from the run config into it, which in Atlas
   includes the question (``atlas_query``, a tracing label). Metadata is reduced to an
   allowlist of structural keys (``source``, ``step``, ``parents``) and the config
   passed alongside is stripped to the checkpoint address, so nothing else leaks.

Unencrypted checkpoints written before this change still load (the serializer and the
string decryptor both pass legacy values through).
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.serde.base import CipherProtocol
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ..security.crypto import keyring

_BLOB_CTX = "langgraph.checkpoint.blob"
_VALUE_CTX = "langgraph.checkpoint.value"
CIPHER_NAME = "atlas-aesgcm"


class AtlasCipher(CipherProtocol):
    def encrypt(self, plaintext: bytes) -> tuple[str, bytes]:
        return CIPHER_NAME, keyring().encrypt_bytes(plaintext, _BLOB_CTX)

    def decrypt(self, ciphername: str, ciphertext: bytes) -> bytes:
        if ciphername != CIPHER_NAME:
            raise ValueError(f"unsupported checkpoint cipher {ciphername!r}")
        return keyring().decrypt_bytes(ciphertext, _BLOB_CTX)


def encrypted_serde() -> EncryptedSerializer:
    return EncryptedSerializer(AtlasCipher(), JsonPlusSerializer())


_SAFE_METADATA = frozenset({"source", "step", "parents"})
_ADDRESS_KEYS = frozenset({"thread_id", "checkpoint_ns", "checkpoint_id"})


def redact_metadata(metadata: Any) -> Any:
    if isinstance(metadata, dict):
        return {k: v for k, v in metadata.items() if k in _SAFE_METADATA}
    return metadata


def address_only(config: dict) -> dict:
    """The config the saver needs (where to write), without the labels and run
    metadata it would otherwise merge into the stored checkpoint metadata."""
    configurable = {k: v for k, v in (config.get("configurable") or {}).items()
                    if k in _ADDRESS_KEYS}
    return {"configurable": configurable}


def _seal_values(checkpoint: dict) -> dict:
    values = checkpoint.get("channel_values") or {}
    if not any(isinstance(v, str) for v in values.values()):
        return checkpoint
    ring = keyring()
    sealed = {k: ring.encrypt(v, _VALUE_CTX) if isinstance(v, str) else v
              for k, v in values.items()}
    return {**checkpoint, "channel_values": sealed}


def _open_values(checkpoint: dict) -> dict:
    values = checkpoint.get("channel_values") or {}
    ring = keyring()
    return {**checkpoint, "channel_values": {
        k: ring.decrypt(v, _VALUE_CTX) if isinstance(v, str) else v
        for k, v in values.items()}}


def encrypted_postgres_saver_cls():
    from langgraph.checkpoint.base import CheckpointTuple
    from langgraph.checkpoint.postgres import PostgresSaver

    class EncryptedPostgresSaver(PostgresSaver):
        def put(self, config, checkpoint, metadata, new_versions):  # type: ignore[override]
            return super().put(address_only(config), _seal_values(checkpoint),
                               redact_metadata(metadata), new_versions)

        def _load_checkpoint_tuple(self, value) -> CheckpointTuple:  # type: ignore[override]
            t = super()._load_checkpoint_tuple(value)
            return CheckpointTuple(t.config, _open_values(t.checkpoint), t.metadata,
                                   t.parent_config, t.pending_writes)

    return EncryptedPostgresSaver


def encrypted_sqlite_saver_cls():
    from langgraph.checkpoint.sqlite import SqliteSaver

    class EncryptedSqliteSaver(SqliteSaver):
        # The SQLite saver serializes the whole checkpoint through ``serde`` already;
        # only the metadata column needs redacting.
        def put(self, config, checkpoint, metadata, new_versions):  # type: ignore[override]
            return super().put(address_only(config), checkpoint, redact_metadata(metadata),
                               new_versions)

    return EncryptedSqliteSaver
