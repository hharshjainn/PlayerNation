"""
POST /generate-report (Phase 6).

Thin by design: parse the request, call `ReportService`, map the result
to the API response shape, return. Exceptions the service can raise
(`MatchNotFoundError`, `ReportGenerationError`) are deliberately *not*
caught here -- they're translated to HTTP responses by the centralized
exception handlers in `error_handlers.py`. A route that catches and
re-raises its own HTTP errors is exactly the "business logic in the API
layer" this phase is meant to avoid.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_report_service
from app.api.schemas import GenerateReportRequest, GenerateReportResponse
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


@router.post("/generate-report", response_model=GenerateReportResponse)
async def generate_report(
    payload: GenerateReportRequest,
    report_service: ReportService = Depends(get_report_service),
) -> GenerateReportResponse:
    result = await report_service.generate_report(payload.match_id, force_refresh=payload.force_refresh)
    return GenerateReportResponse(
        match=result.context.match,
        report=result.report,
        cached=result.cached,
        model=result.model,
        attempts=result.attempts,
        latency_ms=result.latency_ms,
    )
