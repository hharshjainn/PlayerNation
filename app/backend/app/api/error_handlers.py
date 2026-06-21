"""
Centralized exception -> HTTP response mapping (Phase 6).

Registered once on the FastAPI app in `main.py`. Routes never need their
own try/except for these -- raising the right internal exception type is
enough; the mapping to a clean, consistent JSON error shape and the
right status code happens here, in one place.

Deliberately does *not* echo internal error detail (e.g. a Groq failure
message, which could reference internal config) back to the client on a
5xx -- the full detail is logged server-side instead, and the client gets
a clean, generic message. 4xx responses (bad input, not-found) are safe
to echo back since they describe the caller's own request, not internal
state.
"""
from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas import ErrorResponse
from app.data.dataset_loader import DatasetFileNotFoundError
from app.llm.llm_service import ReportGenerationError
from app.services.report_service import MatchNotFoundError

logger = logging.getLogger(__name__)


async def match_not_found_handler(request: Request, exc: MatchNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(error="match_not_found", detail=str(exc)).model_dump(),
    )


async def dataset_unavailable_handler(request: Request, exc: DatasetFileNotFoundError) -> JSONResponse:
    logger.error("dataset_unavailable", extra={"path": request.url.path, "detail": str(exc)})
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="dataset_unavailable", detail="The match dataset is not available on the server."
        ).model_dump(),
    )


async def report_generation_error_handler(request: Request, exc: ReportGenerationError) -> JSONResponse:
    logger.error(
        "report_generation_failed",
        extra={"path": request.url.path, "detail": str(exc), "attempts": exc.attempts},
    )
    return JSONResponse(
        status_code=502,
        content=ErrorResponse(
            error="report_generation_failed",
            detail="The report could not be generated right now. Please try again shortly.",
        ).model_dump(),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(error="validation_error", detail=str(exc.errors())).model_dump(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error="internal_error", detail="An unexpected error occurred.").model_dump(),
    )


# Registered in `main.py` via a loop over this dict -- one place that
# lists every exception type the API knows how to handle gracefully.
EXCEPTION_HANDLERS = {
    MatchNotFoundError: match_not_found_handler,
    DatasetFileNotFoundError: dataset_unavailable_handler,
    ReportGenerationError: report_generation_error_handler,
    RequestValidationError: validation_error_handler,
    Exception: unhandled_exception_handler,
}
