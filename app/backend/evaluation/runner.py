"""
Phase 5: the evaluation runner.

`EvaluationRunner.run(match_ids)` runs the full Phase 1->4 pipeline for
each match id, scores the resulting report against every check in
`checks.py`, and aggregates everything into an `EvaluationSummary`.

One bad match -- a missing fixture, a Groq failure, an unexpected
exception anywhere in the pipeline -- is recorded as a failed
`MatchEvaluation` and the run continues. A single match_id should never
be able to abort a whole benchmarking run, which is the entire point of
"make it easy to benchmark prompt changes" -- a developer iterating on the
prompt needs the batch to finish even if one match misbehaves.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.analytics.match_analyzer import MatchAnalyzer
from app.context.context_builder import ContextBuilder
from app.data.dataset_loader import DatasetLoader
from app.llm.llm_service import GroqReportService, ReportGenerationError
from evaluation.checks import (
    check_hallucinations,
    check_major_event_coverage,
    check_missing_sections,
    check_top_player_coverage,
    check_winner_correctness,
)
from evaluation.models import EvaluationSummary, MatchEvaluation

logger = logging.getLogger(__name__)


class EvaluationRunner:
    def __init__(self, loader: DatasetLoader, llm_service: Optional[GroqReportService] = None) -> None:
        self.loader = loader
        self.analyzer = MatchAnalyzer(loader)
        self.context_builder = ContextBuilder()
        self.llm_service = llm_service or GroqReportService()

    async def run(self, match_ids: list[int]) -> EvaluationSummary:
        evaluations = [await self._evaluate_one(match_id) for match_id in match_ids]
        return self._summarize(evaluations)

    # ------------------------------------------------------------------
    async def _evaluate_one(self, match_id: int) -> MatchEvaluation:
        try:
            analysis = self.analyzer.analyze(match_id)
            context = self.context_builder.build(analysis)
        except Exception as exc:  # noqa: BLE001 -- last-resort batch safety net, see module docstring
            logger.warning("Match %s failed during analysis/context-building: %s", match_id, exc)
            return MatchEvaluation(match_id=match_id, match_label=f"match {match_id}", succeeded=False, error=str(exc))

        match_label = context.match.label

        try:
            result = await self.llm_service.generate_report(context)
        except ReportGenerationError as exc:
            logger.warning("Match %s failed report generation: %s", match_id, exc)
            return MatchEvaluation(
                match_id=match_id,
                match_label=match_label,
                succeeded=False,
                error=str(exc),
                attempts=exc.attempts or None,
                latency_ms=exc.latency_ms,
            )
        except Exception as exc:  # noqa: BLE001 -- same safety net as above
            logger.warning("Match %s failed report generation unexpectedly: %s", match_id, exc)
            return MatchEvaluation(match_id=match_id, match_label=match_label, succeeded=False, error=str(exc))

        report = result.report
        return MatchEvaluation(
            match_id=match_id,
            match_label=match_label,
            succeeded=True,
            attempts=result.attempts,
            latency_ms=result.latency_ms,
            missing_sections=check_missing_sections(report),
            winner_check=check_winner_correctness(report, context),
            major_event_coverage=check_major_event_coverage(report, context),
            top_player_coverage=check_top_player_coverage(report, context),
            hallucination_check=check_hallucinations(report, context),
        )

    # ------------------------------------------------------------------
    def _summarize(self, evaluations: list[MatchEvaluation]) -> EvaluationSummary:
        total = len(evaluations)
        succeeded = [e for e in evaluations if e.succeeded]
        schema_success_rate = round(100 * len(succeeded) / total, 1) if total else 0.0

        first_attempt = [e for e in succeeded if e.attempts == 1]
        first_attempt_success_rate = round(100 * len(first_attempt) / len(succeeded), 1) if succeeded else None

        latencies = [e.latency_ms for e in succeeded if e.latency_ms is not None]
        avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else None

        event_coverages = [e.major_event_coverage.coverage_pct for e in succeeded if e.major_event_coverage]
        avg_event_coverage = round(sum(event_coverages) / len(event_coverages), 1) if event_coverages else None

        player_coverages = [e.top_player_coverage.coverage_pct for e in succeeded if e.top_player_coverage]
        avg_player_coverage = round(sum(player_coverages) / len(player_coverages), 1) if player_coverages else None

        winner_checks = [e.winner_check.correct for e in succeeded if e.winner_check]
        winner_correct_rate = round(100 * sum(winner_checks) / len(winner_checks), 1) if winner_checks else None

        matches_with_missing_sections = sum(1 for e in succeeded if e.missing_sections)
        matches_with_unrecognized_names = sum(
            1 for e in succeeded if e.hallucination_check and e.hallucination_check.unrecognized_names
        )

        return EvaluationSummary(
            total_matches=total,
            schema_success_rate=schema_success_rate,
            first_attempt_success_rate=first_attempt_success_rate,
            avg_latency_ms=avg_latency_ms,
            avg_major_event_coverage_pct=avg_event_coverage,
            avg_top_player_coverage_pct=avg_player_coverage,
            winner_correct_rate=winner_correct_rate,
            matches_with_missing_sections=matches_with_missing_sections,
            matches_with_unrecognized_names=matches_with_unrecognized_names,
            evaluations=evaluations,
        )
