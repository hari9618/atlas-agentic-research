"""Re-encrypt stored data under the active key (and encrypt legacy plaintext).

Rotation procedure (no downtime):

1. Generate a key: ``python -m atlas.security.crypto``.
2. Deploy with ``DATA_ENCRYPTION_KEY=<new>``, ``DATA_ENCRYPTION_KEY_ID=k2`` and the old
   key kept as ``DATA_ENCRYPTION_KEYS_PREVIOUS=k1:<old>``. Reads of old rows and logins
   (blind index under both keys) keep working.
3. Run ``python -m atlas.security.rotate_keys`` once. It rewrites users, learning-loop
   documents and episodic memories under the new key. It is idempotent: rows already
   on the active key are skipped, so it can be re-run after an interruption.
4. Remove the old key from ``DATA_ENCRYPTION_KEYS_PREVIOUS`` once paused-review
   checkpoints older than the rotation have expired (they are short-lived).

``--dry-run`` reports what would change without writing.
"""

from __future__ import annotations

import argparse
import json
import logging

from ..core.persistence import get_pg_pool
from .crypto import keyring
from .store import _EMAIL_CTX, _NAME_CTX, get_auth_store

log = logging.getLogger("atlas.security.rotate")


def rotate_users(dry_run: bool) -> int:
    store = get_auth_store()
    ring = keyring()
    changed = 0
    for row in store.all_users():
        if not (ring.needs_rotation(row["email_enc"]) or ring.needs_rotation(row["name_enc"])):
            continue
        changed += 1
        if not dry_run:
            store.rewrite_user_crypto(row["id"], ring.decrypt(row["email_enc"], _EMAIL_CTX),
                                      ring.decrypt(row["name_enc"], _NAME_CTX))
    return changed


def rotate_documents(dry_run: bool) -> int:
    pool = get_pg_pool()
    if pool is None:
        return 0
    from psycopg.types.json import Jsonb

    from ..core.llmops.store import DocumentStore

    ring = keyring()
    changed = 0
    with pool.connection() as conn:
        rows = conn.execute("SELECT kind, id, data FROM atlas_llmops_documents").fetchall()
    for r in rows:
        data = r["data"]
        if "_enc" in data and not ring.needs_rotation(data["_enc"]):
            continue
        changed += 1
        if dry_run:
            continue
        store = DocumentStore(r["kind"], pool=pool)
        plain = store._open(data)
        with pool.connection() as conn:
            conn.execute("UPDATE atlas_llmops_documents SET data = %s WHERE kind = %s AND id = %s",
                         (Jsonb(store._seal(plain)), r["kind"], r["id"]))
    return changed


def rotate_episodes(dry_run: bool) -> int:
    pool = get_pg_pool()
    if pool is None:
        return 0
    from psycopg.types.json import Jsonb

    from ..core.memory.episodic import _PostgresBackend

    ring = keyring()
    ctx = _PostgresBackend._CTX
    changed = 0
    with pool.connection() as conn:
        rows = conn.execute("SELECT id, query, target, report, findings FROM atlas_episodes"
                            ).fetchall()
    for r in rows:
        findings = r["findings"]
        sealed = isinstance(findings, dict) and "_enc" in findings
        stale = any(ring.needs_rotation(r[c]) for c in ("query", "target", "report")
                    if r[c]) or not sealed or ring.needs_rotation(findings.get("_enc"))
        if not stale:
            continue
        changed += 1
        if dry_run:
            continue
        plain_findings = (json.loads(ring.decrypt(findings["_enc"], "atlas_episodes.findings"))
                          if sealed else findings)
        values = {c: ring.decrypt(r[c], ctx[i]) for i, c in ((1, "query"), (2, "target"),
                                                             (3, "report"))}
        with pool.connection() as conn:
            conn.execute(
                "UPDATE atlas_episodes SET query=%s, target=%s, report=%s, findings=%s "
                "WHERE id=%s",
                (ring.encrypt(values["query"], ctx[1]), ring.encrypt(values["target"], ctx[2]),
                 ring.encrypt(values["report"], ctx[3]),
                 Jsonb({"_enc": ring.encrypt(json.dumps(plain_findings, default=str),
                                             "atlas_episodes.findings")}), r["id"]))
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ring = keyring()
    log.info("Active key: %s (source: %s)", ring.active.kid, ring.source)
    for name, fn in (("users", rotate_users), ("documents", rotate_documents),
                     ("episodes", rotate_episodes)):
        n = fn(args.dry_run)
        log.info("%s: %d row(s) %s", name, n, "would change" if args.dry_run else "rewritten")


if __name__ == "__main__":
    main()
