"""
Run the Phase 5 evaluation framework from the command line.

Usage:
    python -m evaluation.cli --matches 9000001,9000002,9000003

Run it once before a prompt/analytics change and once after, diff the two
JSON reports, and you've got a concrete before/after on schema success
rate, latency, winner correctness, and event/player coverage -- which is
the whole point of this phase ("make it easy to benchmark prompt changes
and analytics improvements").
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.core.config import settings
from app.data.dataset_loader import DatasetLoader
from evaluation.report_writer import format_text_report, write_json_report
from evaluation.runner import EvaluationRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate report generation across multiple matches.")
    parser.add_argument("--matches", required=True, help="Comma-separated match ids to evaluate.")
    parser.add_argument(
        "--output", default="evaluation_report.json", help="Path to write the JSON report to."
    )
    args = parser.parse_args()

    match_ids = [int(m.strip()) for m in args.matches.split(",") if m.strip()]

    loader = DatasetLoader(settings.raw_data_dir, settings.default_competition)
    runner = EvaluationRunner(loader)
    summary = asyncio.run(runner.run(match_ids))

    output_path = Path(args.output)
    write_json_report(summary, output_path)

    print(format_text_report(summary))
    print(f"\nFull JSON report written to {output_path}")


if __name__ == "__main__":
    main()
