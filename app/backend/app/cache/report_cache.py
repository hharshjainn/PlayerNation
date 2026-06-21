"""
Report cache abstraction (Phase 6).

Reports are expensive to produce (an LLM call, plus the analytics
pipeline) and built from static, historical match data that never
changes -- so a successfully generated report can be cached indefinitely
per match_id, with no TTL needed.

`ReportCache` is a `Protocol` rather than a concrete dependency anywhere
in `report_service.py`, specifically so `InMemoryReportCache` (fine for a
single-process deployment, which is all this take-home needs) can be
swapped for something shared/persistent (Redis, a database table) later
without touching the service layer at all.
"""
from __future__ import annotations

import asyncio
from typing import Optional, Protocol

from pydantic import BaseModel

from app.context.models import MatchContext
from app.llm.report_schema import MatchReport


class ReportResult(BaseModel):
    """Everything about a generated report worth caching and returning to
    the API layer: the report itself, the match context it was built
    from (the API needs this for the response's score-header section),
    and generation metadata.
    """

    context: MatchContext
    report: MatchReport
    cached: bool
    model: str
    attempts: int
    latency_ms: float


class ReportCache(Protocol):
    async def get(self, match_id: int) -> Optional[ReportResult]: ...

    async def set(self, match_id: int, result: ReportResult) -> None: ...

    async def clear(self, match_id: Optional[int] = None) -> None: ...


class InMemoryReportCache:
    """Process-local cache, keyed by match_id.

    Not shared across multiple backend processes/instances -- acceptable
    for a single-process deployment. If this needs to scale horizontally,
    swap this for a Redis-backed implementation of the same `ReportCache`
    protocol; nothing else in the codebase needs to change.
    """

    def __init__(self) -> None:
        self._store: dict[int, ReportResult] = {}
        self._lock = asyncio.Lock()

    async def get(self, match_id: int) -> Optional[ReportResult]:
        async with self._lock:
            return self._store.get(match_id)

    async def set(self, match_id: int, result: ReportResult) -> None:
        async with self._lock:
            self._store[match_id] = result

    async def clear(self, match_id: Optional[int] = None) -> None:
        async with self._lock:
            if match_id is None:
                self._store.clear()
            else:
                self._store.pop(match_id, None)
