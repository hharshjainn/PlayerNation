"""
Pydantic models for the compact, LLM-ready match context (Phase 3).

This is intentionally a much smaller shape than `app/analytics/models.py`'s
`MatchAnalysis`. Every field here earns its place by directly supporting
the report sections Phase 4 needs to write (summary, turning points,
standout players, tactical analysis, coaching insights) -- see
`context_builder.py`'s module docstring for what was dropped and why.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.analytics.models import Side


class ContextMatch(BaseModel):
    label: str
    date: Optional[str] = None
    venue: Optional[str] = None
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    result: str  # "home_win" | "away_win" | "draw"
    went_to_extra_time: Optional[bool] = None  # omitted entirely when False
    went_to_penalties: Optional[bool] = None  # omitted entirely when False
    penalty_score: Optional[str] = None


class ContextTeamStats(BaseModel):
    team: str
    side: Side
    shots: int
    shots_on_target: int
    goals: int
    passes_attempted: int
    pass_accuracy_pct: float
    fouls: int
    yellow_cards: int
    red_cards: int
    corners: int
    pass_share_pct: float
    """Share of the match's total pass attempts. Named for what it actually
    is (a pass-volume share), not "possession", so a report-writing LLM
    doesn't overstate it as measured ball-time."""


class ContextPlayer(BaseModel):
    name: str
    team: str
    rating: float
    goals: int = 0
    assists: int = 0
    key_passes: int = 0


class ContextMoment(BaseModel):
    minute: str
    type: str
    text: str


class ContextPattern(BaseModel):
    team: str
    pattern: str
    text: str


class ContextObservation(BaseModel):
    team: str
    text: str
    evidence: str


class MatchContext(BaseModel):
    match: ContextMatch
    team_stats: list[ContextTeamStats]
    top_players: list[ContextPlayer]
    key_moments: list[ContextMoment]
    tactical_patterns: list[ContextPattern]
    coaching_observations: list[ContextObservation]
