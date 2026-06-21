"""
Pydantic schema for the LLM-generated match report (Phase 4).

Kept deliberately simple: a flat shape of strings and string lists,
matching the schema specified in the brief exactly. This is what
`llm_service.py` validates every model response against -- a response
that doesn't fit this shape is treated as a validation failure and
retried, never allowed to propagate as a raw `KeyError`/`TypeError`
further up the stack.
"""
from __future__ import annotations

from pydantic import BaseModel


class MatchReport(BaseModel):
    summary: str
    turning_points: list[str]
    standout_players: list[str]
    tactical_analysis: str
    coaching_insights: list[str]


class ReportGenerationResult(BaseModel):
    """What `GroqReportService.generate_report()` returns on success.

    Carries the metadata (attempt count, latency, raw text, which model)
    that Phase 5's evaluation framework will want to measure across many
    matches -- latency and schema-success-rate are exactly what's asked
    for there, so it's captured here rather than discarded.
    """

    report: MatchReport
    raw_response: str
    attempts: int
    latency_ms: float
    model: str
