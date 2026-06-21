"""
API request/response schemas (Phase 6).

Deliberately separate from the internal Phase 1-5 models even where the
shapes overlap (`MatchListItem` vs `MatchSummary`): the API contract
should be free to evolve independently of internal model changes, rather
than exposing internal models directly through the wire format. Where a
Phase 3/4 model already *is* exactly what the API needs to return
(`ContextMatch`, `MatchReport`), those are reused directly rather than
duplicated -- see `GenerateReportResponse`.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.context.models import ContextMatch
from app.llm.report_schema import MatchReport


class MatchListItem(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    date: str | None = None


class MatchListResponse(BaseModel):
    matches: list[MatchListItem]


class GenerateReportRequest(BaseModel):
    match_id: int
    force_refresh: bool = False
    """Bypass the cache and regenerate even if a report already exists
    for this match -- useful after a prompt change, without needing a
    separate cache-clearing endpoint."""


class GenerateReportResponse(BaseModel):
    match: ContextMatch
    report: MatchReport
    cached: bool
    model: str
    attempts: int
    latency_ms: float


class ErrorResponse(BaseModel):
    error: str
    detail: str
