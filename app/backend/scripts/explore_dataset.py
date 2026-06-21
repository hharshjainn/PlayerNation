"""
Phase 1 exploration script.

Run this after placing the raw dataset files in `backend/data/raw/`
(or pointing PLAYERNATION_RAW_DATA_DIR elsewhere):

    cd backend
    python -m scripts.explore_dataset

It prints:
  * number of matches / events in the World Cup competition
  * breakdown of events by type
  * a sample match (teams, score, venue) with its first few events
  * any tag ids found in the data that aren't in our reference dictionary
    (a data-quality smoke test, not expected to find anything for this
    dataset, but cheap insurance against schema drift)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow `python scripts/explore_dataset.py`

from app.core.config import settings  # noqa: E402
from app.data.dataset_loader import DatasetLoader  # noqa: E402
from app.data.models import DatasetSummary  # noqa: E402


def build_summary(loader: DatasetLoader) -> DatasetSummary:
    matches_df = loader.load_matches()
    events_df = loader.load_events()

    event_type_counts = events_df["eventName"].value_counts().to_dict()

    match_ids_with_events = set(events_df["matchId"].unique())
    all_match_ids = set(matches_df["wyId"].unique())
    matches_missing_events = sorted(all_match_ids - match_ids_with_events)

    referenced_players = {pid for pid in events_df["playerId"].unique() if pid and pid != 0}
    referenced_teams = set(events_df["teamId"].unique())

    return DatasetSummary(
        competition=loader.competition,
        num_matches=len(matches_df),
        num_events=len(events_df),
        num_players_referenced=len(referenced_players),
        num_teams_referenced=len(referenced_teams),
        event_type_counts={str(k): int(v) for k, v in event_type_counts.items()},
        matches_missing_events=matches_missing_events,
        unknown_tag_ids=loader.find_unknown_tag_ids(),
    )


def print_sample_match(loader: DatasetLoader) -> None:
    matches = loader.list_matches()
    if not matches:
        print("No matches found.")
        return

    # Prefer a match that actually has events, and ideally a final/decisive
    # one (label often shows the score), for a more interesting sample.
    sample = matches[0]
    for candidate in matches:
        events = loader.get_events_for_match(candidate.match_id)
        if not events.empty:
            sample = candidate
            break

    print("\n--- Sample match ---")
    print(json.dumps(sample.model_dump(), indent=2, default=str))

    match = loader.get_match(sample.match_id)
    if match:
        print("\nFull typed Match object:")
        print(json.dumps(match.model_dump(), indent=2, default=str))

    events = loader.get_events_for_match(sample.match_id)
    print(f"\nFirst 5 events of {len(events)} total for this match:")
    cols = [c for c in ["eventSec", "matchPeriod", "teamId", "playerId", "eventName", "subEventName", "tags"] if c in events.columns]
    print(events[cols].head(5).to_string(index=False))


def main() -> None:
    loader = DatasetLoader(raw_data_dir=settings.raw_data_dir, competition=settings.default_competition)

    print(f"Loading competition='{loader.competition}' from {loader.raw_data_dir} ...")
    summary = build_summary(loader)

    print("\n--- Dataset summary ---")
    print(json.dumps(summary.model_dump(), indent=2))

    print_sample_match(loader)


if __name__ == "__main__":
    main()
