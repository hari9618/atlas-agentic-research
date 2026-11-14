"""Security audit log: who did what sensitive thing, when, from where.

Append-only rows for authentication events (sign-ups, sign-ins and failures, token
reuse, sign-outs, password changes, account deletion) and admin actions (experiments,
rollbacks, corpus changes). It answers the incident questions — "was this account
brute-forced?", "who rolled back the risk analyst on Tuesday?" — that request logs
(rotated, per instance) can't.

No secrets or personal data go in: user ids, not emails; the IP is kept because it is
the point of a security log, and rows older than ``RETENTION_DAYS`` are purged.
Writing an audit row must never fail the request it describes.
"""

from __future__ import annotations

import json
import logging
import random
import time
from datetime import UTC, datetime

from fastapi import Request

log = logging.getLogger("atlas.audit")

RETENTION_DAYS = 90

_DDL = [
    """CREATE TABLE IF NOT EXISTS atlas_audit_log (
        id TEXT PRIMARY KEY,
        at DOUBLE PRECISION NOT NULL,
        event TEXT NOT NULL,
        user_id TEXT,
        ip TEXT,
        request_id TEXT,
        detail TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS atlas_audit_log_at ON atlas_audit_log (at DESC)",
    "CREATE INDEX IF NOT EXISTS atlas_audit_log_user ON atlas_audit_log (user_id, at DESC)",
]

def _db():
    from .store import get_auth_store

    db = get_auth_store().db
    if not getattr(db, "_audit_ready", False):  # once per database handle
        db.ddl(_DDL)
        db._audit_ready = True
    return db


def record(event: str, *, user_id: str | None = None, request: Request | None = None,
           ip: str | None = None, **detail: object) -> None:
    import uuid

    try:
        if request is not None:
            from .limits import client_ip

            ip = ip or client_ip(request)
            rid = (request.scope.get("state") or {}).get("request_id")
        else:
            rid = None
        db = _db()
        db.execute(
            "INSERT INTO atlas_audit_log (id, at, event, user_id, ip, request_id, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (uuid.uuid4().hex, time.time(), event, user_id, ip, rid,
             json.dumps(detail, default=str) if detail else None))
        log.info("audit %s user=%s ip=%s %s", event, user_id, ip, detail or "")
        if random.random() < 0.01:
            db.execute("DELETE FROM atlas_audit_log WHERE at < %s",
                       (time.time() - RETENTION_DAYS * 86_400,))
    except Exception as exc:
        log.warning("audit write failed for %s: %s", event, exc)


def recent(limit: int = 100, *, user_id: str | None = None,
           event_prefix: str | None = None) -> list[dict]:
    where, params = [], []
    if user_id:
        where.append("user_id = %s")
        params.append(user_id)
    if event_prefix:
        where.append("event LIKE %s")
        params.append(f"{event_prefix}%")
    sql = ("SELECT at, event, user_id, ip, request_id, detail FROM atlas_audit_log"
           + (f" WHERE {' AND '.join(where)}" if where else "")
           + " ORDER BY at DESC LIMIT %s")
    rows = _db().all(sql, (*params, max(1, min(limit, 500))))
    for r in rows:
        r["at"] = datetime.fromtimestamp(r["at"], UTC).isoformat(timespec="seconds")
        r["detail"] = json.loads(r["detail"]) if r["detail"] else {}
    return rows
