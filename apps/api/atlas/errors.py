"""One error shape for the whole API: ``{"detail": str, "code": str, ...}``.

FastAPI's ``HTTPException`` nests a dict ``detail`` one level down, so clients would
have to special-case it. ``ApiError`` renders flat, always carries a machine-readable
``code`` the frontend can switch on (``rate_limited``, ``token_expired``, ``busy``…),
and lets a 429/503 set ``Retry-After``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str, *,
                 headers: dict[str, str] | None = None, **extra: object) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.headers = headers or {}
        self.extra = extra

    def body(self) -> dict:
        return {"detail": self.detail, "code": self.code, **self.extra}


def retry_after_error(status: int, code: str, detail: str, retry_after: float) -> ApiError:
    """A 429/503 with both the header and the body field (fetch clients read either)."""
    seconds = max(1, int(retry_after + 0.999))
    return ApiError(status, code, detail, headers={"Retry-After": str(seconds)},
                    retry_after=seconds)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status, headers=exc.headers)
