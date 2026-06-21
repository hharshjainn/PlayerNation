"""
Pydantic models for the Phase 5 evaluation framework's output.

`MatchEvaluation` is one match's worth of checks; `EvaluationSummary`
aggregates many of them into the headline numbers a developer benchmarking
a prompt or analytics change would actually look at.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WinnerCheckResult(BaseModel):
    correct: bool
    expected_result: str  # "home_win" | "away_win" | "draw"
    detected_signal: str  # human-readable note on what was matched, for auditability


class CoverageResult(BaseModel):
    covered: list[str]
    missing: list[str]
    coverage_pct: float


class HallucinationCheckResult(BaseModel):
    home_team_mentioned: bool
    away_team_mentioned: bool
    score_mentioned: bool
    unrecognized_names: list[str]
    """Best-effort: `standout_players` items that don't reference any name
    we actually know about. See `checks.py` for the precision-first
    rationale -- absence here is not proof of no hallucination, only the
    cases this specific heuristic is confident about."""


class MatchEvaluation(BaseModel):
    match_id: int
    match_label: str
    succeeded: bool
    error: Optional[str] = None
    attempts: Optional[int] = None
    latency_ms: Optional[float] = None
    missing_sections: list[str] = Field(default_factory=list)
    winner_check: Optional[WinnerCheckResult] = None
    major_event_coverage: Optional[CoverageResult] = None
    top_player_coverage: Optional[CoverageResult] = None
    hallucination_check: Optional[HallucinationCheckResult] = None


class EvaluationSummary(BaseModel):
    total_matches: int
    schema_success_rate: float  # % of matches where generate_report didn't raise
    first_attempt_success_rate: Optional[float] = None  # % of successes that needed no retry
    avg_latency_ms: Optional[float] = None
    avg_major_event_coverage_pct: Optional[float] = None
    avg_top_player_coverage_pct: Optional[float] = None
    winner_correct_rate: Optional[float] = None
    matches_with_missing_sections: int = 0
    matches_with_unrecognized_names: int = 0
    evaluations: list[MatchEvaluation] = Field(default_factory=list)
