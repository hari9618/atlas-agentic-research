"""/admin — operator views. Admin-only."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from ..security import audit
from ..security.deps import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/audit")
async def audit_log(limit: int = 100, user_id: str | None = None,
                    event: str | None = None) -> dict:
    """Newest security events first. ``event`` filters by prefix (``auth.``, ``admin.``)."""
    rows = await run_in_threadpool(lambda: audit.recent(limit, user_id=user_id,
                                                        event_prefix=event))
    return {"events": rows}
