"""
Phase 2: the match analytics engine.

`MatchAnalyzer.analyze(match_id)` is the single entry point. It pulls a
match + its events from the Phase 1 data access layer and returns a fully
typed `MatchAnalysis` (see `app/analytics/models.py`) containing:

    match_info, score, team_stats, top_players, key_moments,
    tactical_patterns, coaching_observations

Design principles (per the brief):
  * Deterministic and explainable. Every number in the output is either a
    direct count/aggregate from the raw events, or a simple, named,
    documented threshold rule -- never a black-box score.
  * The official match score comes from match metadata (`teamsData.score`),
    not re-derived from event tags. Reconstructing the scoreline purely
    from events is genuinely ambiguous (own goals, disallowed goals, data
    entry quirks) -- see Phase 1 README ambiguity #7. Event tags are still
    used for *who* scored, for the key-moments timeline and player goal
    tallies, where own goals are explicitly excluded from the scorer's own
    tally and re-attributed to the conceding team's opponent.
  * Each analytical building block (team stats, player ratings, key
    moments, tactical patterns, coaching observations) is its own private
    method, so the class reads as a sequence of football questions rather
    than one large procedure.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

import pandas as pd

from app.analytics.event_utils import (
    HIGH_PASS_SUB_EVENT_IDS,
    PERIOD_ORDER,
    approximate_minute,
    is_accurate,
    is_assist,
    is_corner_event,
    is_counter_attack,
    is_key_pass,
    is_on_target,
    is_own_goal,
    is_penalty_event,
    is_post,
    is_red_card,
    is_scoring_event,
    is_shot_event,
    is_successful_event,
    is_yellow_card,
    minute_label,
    start_x,
)
from app.analytics.models import (
    CoachingObservation,
    KeyMoment,
    MatchAnalysis,
    MatchInfo,
    ScoreInfo,
    Side,
    TacticalPattern,
    TeamRef,
    TeamStats,
    TopPlayer,
)
from app.analytics.thresholds import AnalyticsConfig
from app.data.dataset_loader import DatasetLoader
from app.data.models import Match, MatchTeamInfo
from app.data.wyscout_constants import tag_ids as extract_tag_ids

logger = logging.getLogger(__name__)


class MatchAnalysisError(ValueError):
    """Raised when a match cannot be analyzed (not found, or has no events)."""


class MatchAnalyzer:
    """Turns raw Wyscout events for one match into structured football intelligence."""

    def __init__(self, loader: DatasetLoader, config: Optional[AnalyticsConfig] = None) -> None:
        self.loader = loader
        self.config = config or AnalyticsConfig()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def analyze(self, match_id: int) -> MatchAnalysis:
        match = self.loader.get_match(match_id)
        if match is None:
            raise MatchAnalysisError(f"Match {match_id} not found.")

        events = self.loader.get_events_for_match(match_id)
        if events.empty:
            raise MatchAnalysisError(f"No events found for match {match_id}.")

        events = events.copy()
        events["tagIdSet"] = events["tags"].apply(extract_tag_ids)

        home_info, away_info = self._resolve_sides(match)
        team_refs: dict[Side, TeamRef] = {
            "home": TeamRef(team_id=home_info.team_id, name=self._team_name(home_info.team_id), side="home"),
            "away": TeamRef(team_id=away_info.team_id, name=self._team_name(away_info.team_id), side="away"),
        }

        match_info = MatchInfo(
            match_id=match.match_id,
            label=match.label,
            date_utc=match.date_utc,
            venue=match.venue,
            competition_id=match.competition_id,
            status=match.status,
            duration=match.duration,
            home_team=team_refs["home"],
            away_team=team_refs["away"],
        )

        score = self._build_score(match, home_info, away_info)

        team_stats: dict[Side, TeamStats] = {
            "home": self._build_team_stats(events, home_info, team_refs["home"]),
            "away": self._build_team_stats(events, away_info, team_refs["away"]),
        }

        top_players = self._build_top_players(events, team_refs)
        key_moments = self._build_key_moments(events, team_refs)
        tactical_patterns = self._build_tactical_patterns(team_stats)
        coaching_observations = self._build_coaching_observations(team_stats)

        return MatchAnalysis(
            match_info=match_info,
            score=score,
            team_stats=team_stats,
            top_players=top_players,
            key_moments=key_moments,
            tactical_patterns=tactical_patterns,
            coaching_observations=coaching_observations,
        )

    # ------------------------------------------------------------------
    # Small shared lookups
    # ------------------------------------------------------------------
    def _resolve_sides(self, match: Match) -> tuple[MatchTeamInfo, MatchTeamInfo]:
        home = next((t for t in match.teams if t.side == "home"), None)
        away = next((t for t in match.teams if t.side == "away"), None)
        if home is None or away is None:
            raise MatchAnalysisError(f"Match {match.match_id} is missing home/away side information.")
        return home, away

    def _team_name(self, team_id: int) -> str:
        team = self.loader.get_team(team_id)
        return team.name if team else f"Team {team_id}"

    def _player_name(self, player_id: Optional[int]) -> Optional[str]:
        if not player_id:
            return None
        player = self.loader.get_player(player_id)
        return player.short_name if player else f"Player {player_id}"

    # ------------------------------------------------------------------
    # Score (from match metadata -- see module docstring)
    # ------------------------------------------------------------------
    def _build_score(self, match: Match, home: MatchTeamInfo, away: MatchTeamInfo) -> ScoreInfo:
        if home.score > away.score:
            result = "home_win"
        elif away.score > home.score:
            result = "away_win"
        else:
            result = "draw"

        went_to_penalties = match.duration == "Penalties"
        went_to_extra_time = match.duration in ("ExtraTime", "Penalties")
        penalty_score = None
        if went_to_penalties:
            penalty_score = f"{home.score_penalties}-{away.score_penalties}"

        return ScoreInfo(
            home_score=home.score,
            away_score=away.score,
            home_score_half_time=home.score_half_time,
            away_score_half_time=away.score_half_time,
            result=result,
            went_to_extra_time=went_to_extra_time,
            went_to_penalties=went_to_penalties,
            penalty_score=penalty_score,
        )

    # ------------------------------------------------------------------
    # Team stats
    # ------------------------------------------------------------------
    def _build_team_stats(
        self, events: pd.DataFrame, team_info: MatchTeamInfo, team_ref: TeamRef
    ) -> TeamStats:
        team_events = events.loc[events["teamId"] == team_info.team_id]
        opponent_events = events.loc[events["teamId"] != team_info.team_id]

        shot_mask = team_events["subEventId"].apply(is_shot_event)
        shots = int(shot_mask.sum())
        shots_on_target = int(team_events.loc[shot_mask, "tagIdSet"].apply(is_on_target).sum())
        # Goals come from match metadata, not from counting tag-101 events:
        # own-goal sequences can leave a stray "goal" tag on an unrelated
        # event (e.g. the conceding goalkeeper's save attempt) attributed
        # to the wrong team if read naively. See `is_scoring_event` in
        # event_utils.py for the full explanation.
        goals = team_info.score

        pass_mask = team_events["eventName"] == "Pass"
        passes_attempted = int(pass_mask.sum())
        passes_completed = int(team_events.loc[pass_mask, "tagIdSet"].apply(is_accurate).sum())
        pass_accuracy_pct = round(100 * passes_completed / passes_attempted, 1) if passes_attempted else 0.0

        foul_mask = team_events["eventName"] == "Foul"
        fouls_committed = int(foul_mask.sum())
        yellow_cards = int(team_events.loc[foul_mask, "tagIdSet"].apply(is_yellow_card).sum())
        red_cards = int(team_events.loc[foul_mask, "tagIdSet"].apply(is_red_card).sum())

        corners = int(team_events["subEventId"].apply(is_corner_event).sum())

        opponent_passes = int((opponent_events["eventName"] == "Pass").sum())
        total_passes = passes_attempted + opponent_passes
        possession_proxy_pct = round(100 * passes_attempted / total_passes, 1) if total_passes else 50.0

        team_x = team_events["positions"].apply(start_x).dropna()
        avg_event_x = round(float(team_x.mean()), 1) if not team_x.empty else 0.0
        final_third_share_pct = (
            round(100 * float((team_x >= self.config.tactical.attacking_third_x).mean()), 1)
            if not team_x.empty
            else 0.0
        )

        high_pass_count = int(team_events.loc[pass_mask, "subEventId"].isin(HIGH_PASS_SUB_EVENT_IDS).sum())
        high_pass_ratio_pct = round(100 * high_pass_count / passes_attempted, 1) if passes_attempted else 0.0

        return TeamStats(
            team_id=team_ref.team_id,
            name=team_ref.name,
            side=team_ref.side,
            shots=shots,
            shots_on_target=shots_on_target,
            goals=goals,
            passes_attempted=passes_attempted,
            passes_completed=passes_completed,
            pass_accuracy_pct=pass_accuracy_pct,
            fouls_committed=fouls_committed,
            yellow_cards=yellow_cards,
            red_cards=red_cards,
            corners=corners,
            possession_proxy_pct=possession_proxy_pct,
            avg_event_x=avg_event_x,
            final_third_share_pct=final_third_share_pct,
            high_pass_ratio_pct=high_pass_ratio_pct,
        )

    # ------------------------------------------------------------------
    # Player ratings
    # ------------------------------------------------------------------
    def _build_top_players(self, events: pd.DataFrame, team_refs: dict[Side, TeamRef]) -> list[TopPlayer]:
        side_by_team_id = {ref.team_id: side for side, ref in team_refs.items()}
        player_team_id: dict[int, int] = {}
        stats: dict[int, dict[str, int]] = defaultdict(
            lambda: {
                "goals": 0,
                "assists": 0,
                "key_passes": 0,
                "successful_actions": 0,
                "total_actions": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            }
        )

        for row in events.itertuples(index=False):
            player_id = row.playerId
            if not player_id:
                continue  # 0 == "no specific player" (see Phase 1 README)

            player_team_id.setdefault(player_id, row.teamId)
            tag_id_set = row.tagIdSet
            s = stats[player_id]
            s["total_actions"] += 1

            if is_scoring_event(row.eventId, row.subEventId, tag_id_set) and not is_own_goal(tag_id_set):
                s["goals"] += 1
            if is_assist(tag_id_set):
                s["assists"] += 1
            if is_key_pass(tag_id_set):
                s["key_passes"] += 1
            if is_successful_event(row.eventId, row.subEventId, tag_id_set):
                s["successful_actions"] += 1
            if row.eventName == "Foul":
                if is_yellow_card(tag_id_set):
                    s["yellow_cards"] += 1
                if is_red_card(tag_id_set):
                    s["red_cards"] += 1

        weights = self.config.rating_weights
        per_team_candidates: dict[int, list[TopPlayer]] = defaultdict(list)

        for player_id, s in stats.items():
            team_id = player_team_id[player_id]
            side = side_by_team_id.get(team_id)
            if side is None:
                continue  # defensive: event attributed to a team not in this match

            breakdown = {
                "goals": round(s["goals"] * weights.goal, 2),
                "assists": round(s["assists"] * weights.assist, 2),
                "key_passes": round(s["key_passes"] * weights.key_pass, 2),
                "successful_actions": round(s["successful_actions"] * weights.successful_action, 2),
            }
            rating = round(sum(breakdown.values()), 2)

            per_team_candidates[team_id].append(
                TopPlayer(
                    player_id=player_id,
                    name=self._player_name(player_id) or f"Player {player_id}",
                    team_id=team_id,
                    side=side,
                    rating=rating,
                    rating_breakdown=breakdown,
                    goals=s["goals"],
                    assists=s["assists"],
                    key_passes=s["key_passes"],
                    successful_actions=s["successful_actions"],
                    total_actions=s["total_actions"],
                    yellow_cards=s["yellow_cards"],
                    red_cards=s["red_cards"],
                )
            )

        # Take the top N *per team* before merging, so a one-sided match
        # doesn't crowd out the losing side's best performer entirely.
        selected: list[TopPlayer] = []
        for candidates in per_team_candidates.values():
            candidates.sort(key=lambda p: p.rating, reverse=True)
            selected.extend(candidates[: self.config.top_players_per_team])

        selected.sort(key=lambda p: p.rating, reverse=True)
        return selected

    # ------------------------------------------------------------------
    # Key moments
    # ------------------------------------------------------------------
    def _build_key_moments(self, events: pd.DataFrame, team_refs: dict[Side, TeamRef]) -> list[KeyMoment]:
        side_by_team_id = {ref.team_id: side for side, ref in team_refs.items()}
        timeline: list[tuple[tuple[int, float], KeyMoment]] = []

        for row in events.itertuples(index=False):
            tag_id_set = row.tagIdSet
            team_id = row.teamId
            player_id = row.playerId or None
            period = row.matchPeriod
            event_sec = row.eventSec
            sort_key = (PERIOD_ORDER.get(period, 99), event_sec)

            team_name = self._team_name(team_id) if team_id else None
            player_name = self._player_name(player_id)
            minute = approximate_minute(period, event_sec)
            label = minute_label(period, event_sec)

            def make(moment_type, mt_id, mt_name, description) -> KeyMoment:
                return KeyMoment(
                    minute=minute,
                    minute_label=label,
                    period=period,
                    team_id=mt_id,
                    team_name=mt_name,
                    player_id=player_id,
                    player_name=player_name,
                    moment_type=moment_type,
                    description=description,
                )

            # Own goals are checked independently and first: real Wyscout
            # own-goal sequences can carry tag 102 alone on a non-shot
            # "touch" event, with tag 101 left stray on an unrelated
            # following event (e.g. the keeper's save attempt) -- see
            # `is_scoring_event` in event_utils.py. We must not require
            # `is_goal`/`is_scoring_event` to be true here, or this branch
            # would simply never fire for that (common) case.
            if is_own_goal(tag_id_set):
                conceding_side = side_by_team_id.get(team_id)
                scoring_side: Optional[Side] = (
                    "away" if conceding_side == "home" else "home" if conceding_side == "away" else None
                )
                scoring_ref = team_refs.get(scoring_side) if scoring_side else None
                timeline.append(
                    (
                        sort_key,
                        make(
                            "own_goal",
                            scoring_ref.team_id if scoring_ref else None,
                            scoring_ref.name if scoring_ref else None,
                            f"Own goal by {player_name or 'a player'} ({team_name}) -- "
                            f"credited to {scoring_ref.name if scoring_ref else 'the opponent'}.",
                        ),
                    )
                )
            elif is_scoring_event(row.eventId, row.subEventId, tag_id_set):
                if is_penalty_event(row.subEventId):
                    timeline.append(
                        (
                            sort_key,
                            make(
                                "penalty_scored",
                                team_id,
                                team_name,
                                f"Penalty scored by {player_name} ({team_name}).",
                            ),
                        )
                    )
                else:
                    timeline.append(
                        (sort_key, make("goal", team_id, team_name, f"Goal by {player_name} ({team_name}).")),
                    )
            elif is_penalty_event(row.subEventId):
                timeline.append(
                    (
                        sort_key,
                        make(
                            "penalty_missed",
                            team_id,
                            team_name,
                            f"Penalty missed or saved -- taken by {player_name} ({team_name}).",
                        ),
                    )
                )

            if row.eventName == "Foul" and is_red_card(tag_id_set):
                timeline.append(
                    (sort_key, make("red_card", team_id, team_name, f"Red card for {player_name} ({team_name})."))
                )

            if is_shot_event(row.subEventId) and not is_scoring_event(row.eventId, row.subEventId, tag_id_set):
                if is_post(tag_id_set):
                    timeline.append(
                        (
                            sort_key,
                            make("post", team_id, team_name, f"{player_name} ({team_name}) hits the post."),
                        )
                    )
                elif is_counter_attack(tag_id_set):
                    timeline.append(
                        (
                            sort_key,
                            make(
                                "counter_attack_shot",
                                team_id,
                                team_name,
                                f"{player_name} ({team_name}) shoots from a fast break.",
                            ),
                        )
                    )

        timeline.sort(key=lambda item: item[0])
        return [moment for _, moment in timeline]

    # ------------------------------------------------------------------
    # Tactical patterns
    # ------------------------------------------------------------------
    def _build_tactical_patterns(self, team_stats: dict[Side, TeamStats]) -> list[TacticalPattern]:
        th = self.config.tactical
        patterns: list[TacticalPattern] = []

        for side, stats in team_stats.items():
            if stats.possession_proxy_pct >= th.possession_dominant_pct:
                patterns.append(
                    TacticalPattern(
                        team_id=stats.team_id,
                        team_name=stats.name,
                        side=side,
                        pattern="possession_dominant",
                        explanation=(
                            f"{stats.name} attempted {stats.possession_proxy_pct}% of the match's total "
                            "passes, indicating they controlled the ball for most of the game."
                        ),
                        supporting_metric={"possession_proxy_pct": stats.possession_proxy_pct},
                    )
                )

            if stats.high_pass_ratio_pct >= th.direct_play_high_pass_ratio * 100:
                patterns.append(
                    TacticalPattern(
                        team_id=stats.team_id,
                        team_name=stats.name,
                        side=side,
                        pattern="direct_play",
                        explanation=(
                            f"{stats.high_pass_ratio_pct}% of {stats.name}'s passes were long/high balls "
                            "rather than short combinations, consistent with a direct playing style."
                        ),
                        supporting_metric={"high_pass_ratio_pct": stats.high_pass_ratio_pct},
                    )
                )

            if stats.avg_event_x <= th.defensive_avg_x_max:
                patterns.append(
                    TacticalPattern(
                        team_id=stats.team_id,
                        team_name=stats.name,
                        side=side,
                        pattern="defensive_low_block",
                        explanation=(
                            f"{stats.name}'s actions averaged a pitch position of {stats.avg_event_x}/100 "
                            "(closer to their own goal), consistent with a deeper, more defensive shape."
                        ),
                        supporting_metric={"avg_event_x": stats.avg_event_x},
                    )
                )
            elif stats.avg_event_x >= th.high_attacking_avg_x_min:
                patterns.append(
                    TacticalPattern(
                        team_id=stats.team_id,
                        team_name=stats.name,
                        side=side,
                        pattern="high_attacking_territory",
                        explanation=(
                            f"{stats.name}'s actions averaged a pitch position of {stats.avg_event_x}/100 "
                            "(closer to the opponent's goal), indicating a high-territory attacking approach."
                        ),
                        supporting_metric={"avg_event_x": stats.avg_event_x},
                    )
                )

            if stats.final_third_share_pct >= th.high_attacking_activity_share * 100:
                patterns.append(
                    TacticalPattern(
                        team_id=stats.team_id,
                        team_name=stats.name,
                        side=side,
                        pattern="high_attacking_activity",
                        explanation=(
                            f"{stats.final_third_share_pct}% of {stats.name}'s actions took place in the "
                            "attacking third, well above a typical share of the pitch."
                        ),
                        supporting_metric={"final_third_share_pct": stats.final_third_share_pct},
                    )
                )

        return patterns

    # ------------------------------------------------------------------
    # Coaching observations
    # ------------------------------------------------------------------
    def _build_coaching_observations(self, team_stats: dict[Side, TeamStats]) -> list[CoachingObservation]:
        th = self.config.coaching
        observations: list[CoachingObservation] = []

        for side, stats in team_stats.items():
            opponent_side: Side = "away" if side == "home" else "home"
            opponent = team_stats[opponent_side]

            if stats.shots >= th.low_shot_conversion_min_shots:
                on_target_pct = round(100 * stats.shots_on_target / stats.shots, 1) if stats.shots else 0.0
                if on_target_pct < th.low_shot_on_target_pct:
                    observations.append(
                        CoachingObservation(
                            team_id=stats.team_id,
                            team_name=stats.name,
                            side=side,
                            observation=(
                                f"{stats.name} need to improve shot selection -- only {on_target_pct}% of "
                                f"their {stats.shots} shots were on target."
                            ),
                            supporting_evidence=f"{stats.shots_on_target}/{stats.shots} shots on target.",
                        )
                    )

            if stats.passes_attempted > 0 and stats.pass_accuracy_pct < th.low_pass_accuracy_pct:
                observations.append(
                    CoachingObservation(
                        team_id=stats.team_id,
                        team_name=stats.name,
                        side=side,
                        observation=(
                            f"{stats.name} struggled to retain the ball under pressure, completing only "
                            f"{stats.pass_accuracy_pct}% of their passes."
                        ),
                        supporting_evidence=f"{stats.passes_completed}/{stats.passes_attempted} passes completed.",
                    )
                )

            if stats.fouls_committed >= th.high_fouls:
                observations.append(
                    CoachingObservation(
                        team_id=stats.team_id,
                        team_name=stats.name,
                        side=side,
                        observation=(
                            f"{stats.name}'s discipline is worth addressing -- {stats.fouls_committed} fouls "
                            f"committed, with {stats.yellow_cards} yellow card(s) and {stats.red_cards} red "
                            "card(s)."
                        ),
                        supporting_evidence=(
                            f"{stats.fouls_committed} fouls, {stats.yellow_cards} yellow, {stats.red_cards} red."
                        ),
                    )
                )

            if opponent.possession_proxy_pct >= th.possession_imbalance_pct:
                observations.append(
                    CoachingObservation(
                        team_id=stats.team_id,
                        team_name=stats.name,
                        side=side,
                        observation=(
                            f"{stats.name} saw very little of the ball ({stats.possession_proxy_pct}% pass "
                            "share) and will need a clear plan for playing without possession."
                        ),
                        supporting_evidence=(
                            f"Pass share {stats.possession_proxy_pct}% vs {opponent.name}'s "
                            f"{opponent.possession_proxy_pct}%."
                        ),
                    )
                )

        return observations
