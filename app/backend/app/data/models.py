"""
Pydantic models for the entities exposed by the data access layer.

These models intentionally only capture the fields that the rest of the
system (analytics engine, context builder, API) actually needs. The raw
Wyscout documents have many more fields (e.g. full lineup/bench formation
data); those stay in the underlying pandas DataFrame / dict and can be
promoted to a typed model in a later phase if needed.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class Team(BaseModel):
    team_id: int
    name: str
    official_name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    team_type: Optional[str] = None  # "club" or "national"


class Player(BaseModel):
    player_id: int
    short_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    birth_country: Optional[str] = None
    role_name: Optional[str] = None  # e.g. "Goalkeeper", "Defender", "Midfielder", "Forward"
    role_code: Optional[str] = None  # Wyscout's short code, e.g. "GK", "DEF", "MID", "FWD"
    preferred_foot: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    current_team_id: Optional[int] = None


class MatchTeamInfo(BaseModel):
    """A single team's participation in a single match."""

    team_id: int
    side: str  # "home" or "away"
    score: int = 0
    score_half_time: int = 0
    score_extra_time: int = 0
    score_penalties: int = 0
    coach_id: Optional[int] = None
    lineup_player_ids: list[int] = Field(default_factory=list)
    bench_player_ids: list[int] = Field(default_factory=list)


class Match(BaseModel):
    match_id: int
    competition_id: Optional[int] = None
    label: str
    date_utc: Optional[str] = None  # kept as string (ISO) to avoid timezone ambiguity
    venue: Optional[str] = None
    status: Optional[str] = None  # "Played", "Cancelled", "Postponed", "Suspended"
    duration: Optional[str] = None  # "Regular", "ExtraTime", "Penalties"
    winner_team_id: Optional[int] = None  # 0 (draw) is preserved as-is, None means unknown
    round_id: Optional[int] = None
    teams: list[MatchTeamInfo] = Field(default_factory=list)

    def get_team(self, team_id: int) -> Optional[MatchTeamInfo]:
        for team in self.teams:
            if team.team_id == team_id:
                return team
        return None


class MatchSummary(BaseModel):
    """Lightweight projection used for list views (e.g. GET /matches in Phase 6)."""

    match_id: int
    label: str
    date_utc: Optional[str] = None
    venue: Optional[str] = None
    status: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class DatasetSummary(BaseModel):
    """Output of the exploration script -- a snapshot of the loaded dataset."""

    competition: str
    num_matches: int
    num_events: int
    num_players_referenced: int
    num_teams_referenced: int
    event_type_counts: dict[str, int]
    matches_missing_events: list[int] = Field(default_factory=list)
    unknown_tag_ids: list[int] = Field(default_factory=list)
