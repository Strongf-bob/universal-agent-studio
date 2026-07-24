"""Safe API errors and exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger("universal_agent_studio_api")


def error_document(
    code: str,
    *,
    message_key: str | None = None,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message_key": message_key or f"errors.{code}",
        "retryable": retryable,
        "details": details or {},
    }


class ApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        code: str,
        *,
        message_key: str | None = None,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.document = error_document(
            code,
            message_key=message_key,
            retryable=retryable,
            details=details,
        )
        super().__init__(code)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(error.document, status_code=error.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        fields = [
            ".".join(str(part) for part in item["loc"]) for item in error.errors()
        ]
        return JSONResponse(
            error_document(
                "request_validation_failed",
                details={"fields": fields},
            ),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, error: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        LOGGER.error(
            "unhandled request error request_id=%s type=%s",
            request_id,
            type(error).__name__,
        )
        return JSONResponse(
            error_document("internal_error"),
            status_code=500,
        )
