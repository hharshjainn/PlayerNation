"""
FastAPI application entry point (Phase 6).

Run with:
    uvicorn app.main:app --reload

This file wires things together -- structured logging, request-logging
middleware, the two route modules, and the centralized exception
handlers -- and contains no business logic of its own. See
`app/services/` for that.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.error_handlers import EXCEPTION_HANDLERS
from app.api.middleware import RequestLoggingMiddleware
from app.api.routes import matches, reports
from app.core.logging_config import configure_logging

configure_logging()

app = FastAPI(
    title="PlayerNation Match Report API",
    description="Generates LLM-powered football match reports from the Wyscout World Cup dataset.",
    version="0.1.0",
)

app.add_middleware(RequestLoggingMiddleware)

for _exc_class, _handler in EXCEPTION_HANDLERS.items():
    app.add_exception_handler(_exc_class, _handler)

app.include_router(matches.router)
app.include_router(reports.router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
