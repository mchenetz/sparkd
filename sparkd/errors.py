from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status: int = 500
    title: str = "Internal Error"

    def __init__(self, detail: str, *, details: dict | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.details = details or {}


class NotFoundError(DomainError):
    status = 404
    title = "Not Found"

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"{kind} '{key}' not found")
        self.kind = kind
        self.key = key


class ValidationError(DomainError):
    status = 422
    title = "Validation Error"


class ConflictError(DomainError):
    status = 409
    title = "Conflict"


class UpstreamError(DomainError):
    status = 502
    title = "Upstream Error"


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle(request: Request, exc: DomainError) -> JSONResponse:
        body = {
            "type": "about:blank",
            "title": exc.title,
            "status": exc.status,
            "detail": exc.detail,
        }
        if exc.details:
            body["details"] = exc.details
        return JSONResponse(
            status_code=exc.status,
            content=body,
            media_type="application/problem+json",
        )
