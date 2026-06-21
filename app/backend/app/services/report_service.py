"""
Business logic for generating a match report end to end (Phase 6):
analyze -> build context -> check cache -> call the LLM if needed ->
cache -> return.

This is the ONLY place that wires the Phase 1-4 pipeline together for the
API. Routes never call `MatchAnalyzer` / `ContextBuilder` /
`GroqReportService` directly -- they call `ReportService.generate_report`
and translate the two exception types it can raise. This is what makes
"business logic outside API routes" true in practice, not just in name.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from app.analytics.match_analyzer import MatchAnalysisError, MatchAnalyzer
from app.cache.report_cache import InMemoryReportCache, ReportCache, ReportResult
from app.context.context_builder import ContextBuilder
from app.data.dataset_loader import DatasetLoader
from app.llm.llm_service import GroqReportService

logger = logging.getLogger(__name__)


class MatchNotFoundError(Exception):
    """Raised when `match_id` doesn't resolve to a usable match -- either
    it doesn't exist, or it has no events to analyze. Both are genuinely
    "there's nothing here for this id" from the API's point of view, so
    they're collapsed into one exception type here; the message still
    says which one it was.
    """

    def __init__(self, match_id: int, reason: str) -> None:
        super().__init__(reason)
        self.match_id = match_id


class ReportService:
    def __init__(
        self,
        loader: DatasetLoader,
        llm_service: Optional[GroqReportService] = None,
        cache: Optional[ReportCache] = None,
    ) -> None:
        self.loader = loader
        self.analyzer = MatchAnalyzer(loader)
        self.context_builder = ContextBuilder()
        self.llm_service = llm_service or GroqReportService()
        self.cache = cache or InMemoryReportCache()

    async def generate_report(self, match_id: int, force_refresh: bool = False) -> ReportResult:
        if not force_refresh:
            cached = await self.cache.get(match_id)
            if cached is not None:
                logger.info("report_cache_hit", extra={"match_id": match_id})
                # `cached` here is a stored object whose own `.cached` field
                # reflects its state at *creation* time (it was False when
                # first generated). Build a fresh result with `cached=True`
                # rather than returning that stale value -- the flag means
                # "was *this* call served from cache", not a static property
                # of the stored object.
                return ReportResult(
                    context=cached.context,
                    report=cached.report,
                    cached=True,
                    model=cached.model,
                    attempts=cached.attempts,
                    latency_ms=cached.latency_ms,
                )

        logger.info("report_cache_miss", extra={"match_id": match_id, "force_refresh": force_refresh})

        try:
            analysis = self.analyzer.analyze(match_id)
        except MatchAnalysisError as exc:
            raise MatchNotFoundError(match_id, str(exc)) from exc

        context = self.context_builder.build(analysis)

        start = time.monotonic()
        # `generate_report` raises `ReportGenerationError` on failure --
        # deliberately left to propagate uncaught. The API layer's
        # exception handler (registered once, in `error_handlers.py`) is
        # where that gets translated to a clean HTTP response; this
        # service has no business deciding HTTP status codes.
        generation = await self.llm_service.generate_report(context)
        logger.info(
            "report_generated",
            extra={
                "match_id": match_id,
                "attempts": generation.attempts,
                "latency_ms": generation.latency_ms,
                "total_latency_ms": round((time.monotonic() - start) * 1000, 1),
            },
        )

        result = ReportResult(
            context=context,
            report=generation.report,
            cached=False,
            model=generation.model,
            attempts=generation.attempts,
            latency_ms=generation.latency_ms,
        )
        await self.cache.set(match_id, result)
        return result
