"""
Persist an `EvaluationSummary` as JSON, and render a short human-readable
text summary -- the two output forms a developer benchmarking a prompt or
analytics change actually wants: a diffable artifact, and something
skimmable in a terminal.
"""
from __future__ import annotations

from pathlib import Path

from evaluation.models import EvaluationSummary


def write_json_report(summary: EvaluationSummary, path: Path) -> None:
    path.write_text(summary.model_dump_json(indent=2))


def format_text_report(summary: EvaluationSummary) -> str:
    def pct(value: float | None) -> str:
        return f"{value}%" if value is not None else "n/a"

    lines = [
        f"Matches evaluated:         {summary.total_matches}",
        f"Schema success rate:       {pct(summary.schema_success_rate)}",
        f"First-attempt success:     {pct(summary.first_attempt_success_rate)}",
        f"Avg latency:                {summary.avg_latency_ms} ms" if summary.avg_latency_ms is not None else "Avg latency:                n/a",
        f"Winner correctness rate:   {pct(summary.winner_correct_rate)}",
        f"Avg major-event coverage:  {pct(summary.avg_major_event_coverage_pct)}",
        f"Avg top-player coverage:   {pct(summary.avg_top_player_coverage_pct)}",
        f"Matches w/ missing sections:     {summary.matches_with_missing_sections}",
        f"Matches w/ unrecognized names:   {summary.matches_with_unrecognized_names}",
        "",
        "Per-match detail:",
    ]
    for e in summary.evaluations:
        if not e.succeeded:
            lines.append(f"  [{e.match_id}] {e.match_label}: FAILED -- {e.error}")
            continue
        winner_label = "?" if not e.winner_check else ("OK" if e.winner_check.correct else "WRONG")
        events_pct = e.major_event_coverage.coverage_pct if e.major_event_coverage else "?"
        players_pct = e.top_player_coverage.coverage_pct if e.top_player_coverage else "?"
        lines.append(
            f"  [{e.match_id}] {e.match_label}: winner={winner_label}, "
            f"events={events_pct}%, players={players_pct}%, "
            f"attempts={e.attempts}, latency={e.latency_ms}ms"
        )
        if e.missing_sections:
            lines.append(f"      missing sections: {', '.join(e.missing_sections)}")
        if e.hallucination_check and e.hallucination_check.unrecognized_names:
            lines.append(f"      unrecognized standout_players: {e.hallucination_check.unrecognized_names}")

    return "\n".join(lines)
