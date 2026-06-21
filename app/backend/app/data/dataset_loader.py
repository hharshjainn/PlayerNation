"""
Data access layer for the raw Wyscout Soccer Match Event Dataset.

DESIGN NOTES (read before extending this in Phase 2+)
-------------------------------------------------------------------------
The public dataset (Pappalardo et al., 2019; mirrored by koenvo's GitHub
repo, originally hosted on figshare) ships four files relevant to this
project:

    teams.json                  -- GLOBAL, covers all 7 competitions
    players.json                -- GLOBAL, covers all 7 competitions
    matches_World_Cup.json      -- per-competition (also shipped zipped)
    events_World_Cup.json       -- per-competition (also shipped zipped)

`teams.json` / `players.json` have no explicit "competition" field, so the
only reliable way to know which teams/players are relevant to the World Cup
is to look at who actually appears in World Cup matches/events. This loader
therefore never tries to "filter" the global files; it just resolves ids
on demand and lets the exploration script compute "referenced" counts from
actual usage.

Known schema quirks this loader handles defensively:
  * `subEventId` is an empty string `""` for Offside events (not an int).
  * `eventSec` resets to 0 at the start of every `matchPeriod` -- it is NOT
    a running match clock. Periods can be "1H", "2H", "E1", "E2", "P".
  * `playerId == 0` means "no specific player" (e.g. ball-out-of-play).
  * `teamsData` on a match document is a dict keyed by team id (as a
    string), not a list.
  * Per-player goal/card counters inside `teamsData.*.lineup` /
    `...bench` are sometimes encoded as strings (e.g. `"goals": "1"`).
  * Some competition zip exports nest the JSON one level deeper as
    `{"events": [...]}` rather than a bare top-level list (observed in the
    koenvo mirror's per-match files). This loader supports both shapes.
"""
from __future__ import annotations

import json
import logging
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from app.data.models import Match, MatchSummary, MatchTeamInfo, Player, Team
from app.data.wyscout_constants import describe_unknown_tags

logger = logging.getLogger(__name__)

# Ordering of match periods for chronological sorting (eventSec resets each
# period, so this must be combined with eventSec, not used alone).
_PERIOD_ORDER = {"1H": 0, "2H": 1, "E1": 2, "E2": 3, "P": 4}


class DatasetFileNotFoundError(FileNotFoundError):
    """Raised when a required dataset file cannot be located on disk."""


class DatasetLoader:
    """Loads and provides typed access to the raw Wyscout dataset files.

    Parameters
    ----------
    raw_data_dir:
        Directory containing the raw JSON (or zipped JSON) dataset files.
    competition:
        The competition slug as used in the dataset's filenames, e.g.
        "World_Cup" or "European_Championship".
    """

    def __init__(self, raw_data_dir: Path | str, competition: str = "World_Cup") -> None:
        self.raw_data_dir = Path(raw_data_dir)
        self.competition = competition

        self._teams_df: Optional[pd.DataFrame] = None
        self._players_df: Optional[pd.DataFrame] = None
        self._matches_df: Optional[pd.DataFrame] = None
        self._events_df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # File discovery / raw JSON loading
    # ------------------------------------------------------------------
    def _find_file(self, candidates: list[str]) -> Path:
        for name in candidates:
            path = self.raw_data_dir / name
            if path.exists():
                return path
        raise DatasetFileNotFoundError(
            f"Could not find any of {candidates} under {self.raw_data_dir}. "
            "Download the dataset files described in the project README "
            "and place them in this directory (or point "
            "PLAYERNATION_RAW_DATA_DIR at the folder that has them)."
        )

    @staticmethod
    def _read_json_records(path: Path) -> list[dict]:
        """Read a dataset file that may be plain JSON or a zip of one JSON file.

        Also unwraps the `{"events": [...]}` nesting seen in some exports.
        """
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as zf:
                json_members = [n for n in zf.namelist() if n.endswith(".json")]
                if not json_members:
                    raise ValueError(f"No .json file found inside {path}")
                with zf.open(json_members[0]) as fh:
                    data = json.load(fh)
        else:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)

        if isinstance(data, dict) and "events" in data:
            return data["events"]
        if isinstance(data, list):
            return data
        raise ValueError(f"Unexpected JSON shape in {path}: top-level type {type(data)}")

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------
    def load_teams(self) -> pd.DataFrame:
        if self._teams_df is None:
            path = self._find_file(["teams.json"])
            records = self._read_json_records(path)
            self._teams_df = pd.json_normalize(records)
            logger.info("Loaded %d teams from %s", len(self._teams_df), path)
        return self._teams_df

    def get_team(self, team_id: int) -> Optional[Team]:
        df = self.load_teams()
        row = df.loc[df["wyId"] == team_id]
        if row.empty:
            return None
        r = row.iloc[0]
        return Team(
            team_id=int(r["wyId"]),
            name=r.get("name", "Unknown"),
            official_name=r.get("officialName"),
            city=r.get("city"),
            country=r.get("area.name") if "area.name" in r.index else None,
            team_type=r.get("type"),
        )

    # ------------------------------------------------------------------
    # Players
    # ------------------------------------------------------------------
    def load_players(self) -> pd.DataFrame:
        if self._players_df is None:
            path = self._find_file(["players.json"])
            records = self._read_json_records(path)
            self._players_df = pd.json_normalize(records)
            logger.info("Loaded %d players from %s", len(self._players_df), path)
        return self._players_df

    def get_player(self, player_id: int) -> Optional[Player]:
        if player_id == 0:
            # 0 is the dataset's sentinel for "no specific player".
            return None
        df = self.load_players()
        row = df.loc[df["wyId"] == player_id]
        if row.empty:
            return None
        r = row.iloc[0]
        # The published paper calls this field "shortName2" but real dumps
        # commonly use "shortName" -- support both defensively.
        short_name = r.get("shortName") if "shortName" in r.index else r.get("shortName2")
        # `pd.json_normalize` flattens nested objects like {"role": {"name": ...}}
        # into "role.name" columns, so the unflattened "role" key is usually
        # absent. Handle both shapes defensively.
        role_block = r.get("role") if "role" in r.index else None
        if isinstance(role_block, dict):
            role_name = role_block.get("name")
            role_code = role_block.get("code2")
        else:
            role_name = r.get("role.name") if "role.name" in r.index else None
            role_code = r.get("role.code2") if "role.code2" in r.index else None
        return Player(
            player_id=int(r["wyId"]),
            short_name=short_name or f"Player {player_id}",
            first_name=r.get("firstName"),
            last_name=r.get("lastName"),
            birth_date=r.get("birthDate") or None,
            birth_country=r.get("birthArea.name") if "birthArea.name" in r.index else None,
            role_name=role_name,
            role_code=role_code,
            preferred_foot=r.get("foot"),
            height_cm=r.get("height") or None,
            weight_kg=r.get("weight") or None,
            current_team_id=r.get("currentTeamId") or None,
        )

    # ------------------------------------------------------------------
    # Matches
    # ------------------------------------------------------------------
    def load_matches(self) -> pd.DataFrame:
        if self._matches_df is None:
            path = self._find_file(
                [
                    f"matches_{self.competition}.json",
                    f"matches_{self.competition}.json.zip",
                    f"matches_{self.competition}.zip",
                ]
            )
            records = self._read_json_records(path)
            self._matches_df = pd.json_normalize(records)
            logger.info("Loaded %d matches from %s", len(self._matches_df), path)
        return self._matches_df

    def _raw_match_record(self, match_id: int) -> Optional[dict]:
        # We keep this on the raw dict (not the flattened DataFrame) because
        # `teamsData` is a nested object that pandas would otherwise mangle.
        path = self._find_file(
            [
                f"matches_{self.competition}.json",
                f"matches_{self.competition}.json.zip",
                f"matches_{self.competition}.zip",
            ]
        )
        for record in self._read_json_records(path):
            if record.get("wyId") == match_id:
                return record
        return None

    def get_match(self, match_id: int) -> Optional[Match]:
        record = self._raw_match_record(match_id)
        if record is None:
            return None

        teams: list[MatchTeamInfo] = []
        for team_id_str, team_block in (record.get("teamsData") or {}).items():
            lineup_ids = [p.get("playerId") for p in team_block.get("lineup", []) if p.get("playerId")]
            bench_ids = [p.get("playerId") for p in team_block.get("bench", []) if p.get("playerId")]
            teams.append(
                MatchTeamInfo(
                    team_id=int(team_id_str),
                    side=team_block.get("side", "unknown"),
                    score=int(team_block.get("score", 0) or 0),
                    score_half_time=int(team_block.get("scoreHT", 0) or 0),
                    score_extra_time=int(team_block.get("scoreET", 0) or 0),
                    score_penalties=int(team_block.get("scoreP", 0) or 0),
                    coach_id=team_block.get("coachId"),
                    lineup_player_ids=lineup_ids,
                    bench_player_ids=bench_ids,
                )
            )

        return Match(
            match_id=record["wyId"],
            competition_id=record.get("competitionId"),
            label=record.get("label", f"Match {match_id}"),
            date_utc=record.get("dateutc"),
            venue=record.get("venue"),
            status=record.get("status"),
            duration=record.get("duration"),
            winner_team_id=record.get("winner"),
            round_id=record.get("roundId"),
            teams=teams,
        )

    def list_matches(self) -> list[MatchSummary]:
        summaries: list[MatchSummary] = []
        path = self._find_file(
            [
                f"matches_{self.competition}.json",
                f"matches_{self.competition}.json.zip",
                f"matches_{self.competition}.zip",
            ]
        )
        for record in self._read_json_records(path):
            teams_data = record.get("teamsData") or {}
            home = next((t for t in teams_data.values() if t.get("side") == "home"), None)
            away = next((t for t in teams_data.values() if t.get("side") == "away"), None)
            home_team = self.get_team(home["teamId"]) if home else None
            away_team = self.get_team(away["teamId"]) if away else None
            summaries.append(
                MatchSummary(
                    match_id=record["wyId"],
                    label=record.get("label", f"Match {record.get('wyId')}"),
                    date_utc=record.get("dateutc"),
                    venue=record.get("venue"),
                    status=record.get("status"),
                    home_team=home_team.name if home_team else None,
                    away_team=away_team.name if away_team else None,
                    home_score=int(home["score"]) if home and home.get("score") is not None else None,
                    away_score=int(away["score"]) if away and away.get("score") is not None else None,
                )
            )
        return summaries

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def load_events(self) -> pd.DataFrame:
        if self._events_df is None:
            path = self._find_file(
                [
                    f"events_{self.competition}.json",
                    f"events_{self.competition}.json.zip",
                    f"events_{self.competition}.zip",
                ]
            )
            records = self._read_json_records(path)
            df = pd.DataFrame(records)
            # subEventId is "" for Offside events; keep the column as
            # nullable Int64 so downstream numeric comparisons don't break.
            if "subEventId" in df.columns:
                df["subEventId"] = pd.to_numeric(df["subEventId"], errors="coerce").astype("Int64")
            self._events_df = df
            logger.info("Loaded %d events from %s", len(self._events_df), path)
        return self._events_df

    def get_events_for_match(self, match_id: int) -> pd.DataFrame:
        df = self.load_events()
        match_events = df.loc[df["matchId"] == match_id].copy()
        if match_events.empty:
            return match_events
        match_events["periodOrder"] = match_events["matchPeriod"].map(_PERIOD_ORDER).fillna(99)
        match_events = match_events.sort_values(["periodOrder", "eventSec"]).reset_index(drop=True)
        return match_events

    # ------------------------------------------------------------------
    # Data quality helpers
    # ------------------------------------------------------------------
    def find_unknown_tag_ids(self, match_id: Optional[int] = None) -> list[int]:
        """Cross-check tags actually present in the data against TAGS.

        Pass a match_id to check just one match (fast); omit it to scan the
        whole competition (slower, intended for the exploration script).
        """
        df = self.get_events_for_match(match_id) if match_id is not None else self.load_events()
        unknown: set[int] = set()
        for tags in df["tags"]:
            unknown.update(describe_unknown_tags(tags))
        return sorted(unknown)


@lru_cache(maxsize=4)
def get_loader(raw_data_dir: str, competition: str = "World_Cup") -> DatasetLoader:
    """Cached factory so repeated calls (e.g. across API requests) reuse one loader."""
    return DatasetLoader(raw_data_dir=raw_data_dir, competition=competition)
