"""
GET /matches (Phase 6).

Thin by design: parse nothing (no params yet), call `MatchService`, map
the result to the API response shape, return. No business logic lives
here -- see `app/services/match_service.py`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_match_service
from app.api.schemas import MatchListItem, MatchListResponse
from app.services.match_service import MatchService

router = APIRouter(tags=["matches"])


@router.get("/matches", response_model=MatchListResponse)
def list_matches(match_service: MatchService = Depends(get_match_service)) -> MatchListResponse:
    summaries = match_service.list_matches()
    items = [
        MatchListItem(
            match_id=summary.match_id,
            home_team=summary.home_team or "Unknown",
            away_team=summary.away_team or "Unknown",
            date=summary.date_utc.split(" ")[0] if summary.date_utc else None,
        )
        for summary in summaries
    ]
    return MatchListResponse(matches=items)
