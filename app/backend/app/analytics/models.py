"""
Pydantic models describing the output of the Phase 2 analytics engine.

This is the contract the Phase 3 context builder and Phase 6 API will
depend on, so it's kept separate from `match_analyzer.py`'s logic.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Side = Literal["home", "away"]


class TeamRef(BaseModel):
    team_id: int
    name: str
    side: Side


class MatchInfo(BaseModel):
    match_id: int
    label: str
    date_utc: Optional[str] = None
    venue: Optional[str] = None
    competition_id: Optional[int] = None
    status: Optional[str] = None
    duration: Optional[str] = None  # "Regular" | "ExtraTime" | "Penalties"
    home_team: TeamRef
    away_team: TeamRef


class ScoreInfo(BaseModel):
    home_score: int
    away_score: int
    home_score_half_time: int
    away_score_half_time: int
    result: Literal["home_win", "away_win", "draw"]
    went_to_extra_time: bool = False
    went_to_penalties: bool = False
    penalty_score: Optional[str] = None  # e.g. "4-3", only set if went_to_penalties


class TeamStats(BaseModel):
    team_id: int
    name: str
    side: Side

    shots: int = 0
    shots_on_target: int = 0
    goals: int = 0

    passes_attempted: int = 0
    passes_completed: int = 0
    pass_accuracy_pct: float = 0.0

    fouls_committed: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    corners: int = 0

    possession_proxy_pct: float = 0.0
    """Share of total match passes attempted by this team. This is a
    deterministic proxy for possession (the dataset has no tracking data /
    ball-time data), not a measured statistic. See Phase 2 design notes."""

    avg_event_x: float = 0.0
    """Mean start-x (0-100, attacking-direction-normalized) across all of
    this team's events -- a simple proxy for how high up the pitch the team
    operates, used by the tactical-pattern rules."""

    final_third_share_pct: float = 0.0
    """Share of this team's events that started in the attacking third
    (x >= attacking_third_x threshold)."""

    high_pass_ratio_pct: float = 0.0
    """Share of this team's passes that were "High pass"/"Launch" rather
    than short/ground passes -- used as a directness proxy."""


class TopPlayer(BaseModel):
    player_id: int
    name: str
    team_id: int
    side: Side

    rating: float
    rating_breakdown: dict[str, float]
    """e.g. {"goals": 12.0, "assists": 4.0, "key_passes": 2.0, "successful_actions": 1.85}"""

    goals: int = 0
    assists: int = 0
    key_passes: int = 0
    successful_actions: int = 0
    total_actions: int = 0
    yellow_cards: int = 0
    red_cards: int = 0


class KeyMoment(BaseModel):
    minute: int
    minute_label: str
    period: str
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    player_id: Optional[int] = None
    player_name: Optional[str] = None
    moment_type: Literal[
        "goal",
        "own_goal",
        "penalty_scored",
        "penalty_missed",
        "red_card",
        "post",
        "counter_attack_shot",
    ]
    description: str


class TacticalPattern(BaseModel):
    team_id: int
    team_name: str
    side: Side
    pattern: Literal[
        "possession_dominant",
        "direct_play",
        "defensive_low_block",
        "high_attacking_territory",
        "high_attacking_activity",
    ]
    explanation: str
    supporting_metric: dict[str, float]


class CoachingObservation(BaseModel):
    team_id: int
    team_name: str
    side: Side
    observation: str
    supporting_evidence: str


class MatchAnalysis(BaseModel):
    match_info: MatchInfo
    score: ScoreInfo
    team_stats: dict[Side, TeamStats]
    top_players: list[TopPlayer] = Field(default_factory=list)
    key_moments: list[KeyMoment] = Field(default_factory=list)
    tactical_patterns: list[TacticalPattern] = Field(default_factory=list)
    coaching_observations: list[CoachingObservation] = Field(default_factory=list)
