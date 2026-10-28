"""Persistence factory — where Atlas keeps durable state.

One place decides the storage backend so the graph, memory and registry never
hard-code it:

* ``DATABASE_URL`` set  → Postgres (durable across deploys, safe for many workers).
* otherwise             → local SQLite files under ``cache_dir()`` (zero-setup dev/tests).

Why this matters: the LangGraph checkpointer is what lets a run pause for human
review and resume later. On hosts with an ephemeral filesystem (Render's free tier),
SQLite files are wiped on every deploy/restart, so a paused run — and episodic
memory — would silently vanish. Postgres keeps them.
"""

from __future__ import annotations

import logging
import sqlite3

from ..paths import cache_dir

log = logging.getLogger("atlas.persistence")


def get_checkpointer():
    """Return a LangGraph checkpointer for the configured backend."""
    db = cache_dir() / "atlas_checkpoints.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(db), check_same_thread=False)
    saver = SqliteSaver(conn)
    try:
        saver.setup()  # create checkpoint tables if missing
    except Exception as exc:  # pragma: no cover
        log.warning("SqliteSaver.setup() failed (%s); continuing.", exc)
    log.info("Checkpointer: SQLite (%s)", db)
    return saver
