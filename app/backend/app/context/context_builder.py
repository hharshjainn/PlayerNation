"""
Phase 3: report context generation.

`ContextBuilder.build(analysis)` compresses a Phase 2 `MatchAnalysis` into
a compact `MatchContext` that's small enough to keep LLM inference cheap
and fast, while still carrying everything a report-writing prompt (Phase
4) needs.

This never touches raw events -- it only ever sees the already-aggregated
`MatchAnalysis`, so "no raw event dumps" is structural, not just a rule we
remember to follow.

What's intentionally left out, and why (each one is in `MatchAnalysis` but
not here):
  * `rating_breakdown` per player, `supporting_metric` per tactical
    pattern -- these exist in Phase 2's output for *auditability*
    (so a human/QA process can check a number against the formula that
    produced it). The LLM doesn't need the formula, just the conclusion
    -- and the conclusion is already spelled out in `text`/the headline
    stat, so shipping the dict too would just be paying tokens twice for
    the same information.
  * `total_actions` / `successful_actions` / per-player cards, and the
    territory metrics (`avg_event_x`, `final_third_share_pct`,
    `high_pass_ratio_pct`) on team stats -- these are *inputs* to the
    tactical-pattern rules, not outputs a report needs directly. The
    pattern's `text` already states the conclusion in football terms
    ("Alpha's actions averaged a pitch position of 72/100 ..."), so the
    raw inputs would be redundant tokens.
  * All numeric ids (`match_id`, `team_id`, `player_id`, `competition_id`)
    and `status`/`duration` -- not narratively useful, and the LLM never
    needs to look anything up by id.
  * `passes_completed` -- derivable from `passes_attempted` +
    `pass_accuracy_pct` closely enough that shipping all three would be
    redundant.
"""
from __future__ import annotations

from app.analytics.models import (
    KeyMoment,
    MatchAnalysis,
    TacticalPattern,
    TeamStats,
    TopPlayer,
)
from app.analytics.models import CoachingObservation as AnalyticsCoachingObservation
from app.context.models import (
    ContextMatch,
    ContextMoment,
    ContextObservation,
    ContextPattern,
    ContextPlayer,
    ContextTeamStats,
    MatchContext,
)


class ContextBuilder:
    """Compresses a `MatchAnalysis` into a compact, LLM-ready `MatchContext`."""

    def build(self, analysis: MatchAnalysis) -> MatchContext:
        team_name_by_side = {
            analysis.match_info.home_team.side: analysis.match_info.home_team.name,
            analysis.match_info.away_team.side: analysis.match_info.away_team.name,
        }

        return MatchContext(
            match=self._build_match(analysis),
            team_stats=[self._build_team_stats(s) for s in analysis.team_stats.values()],
            top_players=[self._build_player(p, team_name_by_side) for p in analysis.top_players],
            key_moments=[self._build_moment(m) for m in analysis.key_moments],
            tactical_patterns=[self._build_pattern(p) for p in analysis.tactical_patterns],
            coaching_observations=[self._build_observation(o) for o in analysis.coaching_observations],
        )

    def build_json(self, analysis: MatchAnalysis) -> str:
        """Render the context as minified JSON (no indentation/whitespace),
        ready to embed directly in an LLM prompt. Every formatting
        character is a token Gemini has to read, so we don't pretty-print
        here -- use `build(...).model_dump_json(indent=2)` for human
        inspection instead.
        """
        return self.build(analysis).model_dump_json(exclude_none=True)

    # ------------------------------------------------------------------
    def _build_match(self, analysis: MatchAnalysis) -> ContextMatch:
        info = analysis.match_info
        score = analysis.score
        # date_utc is a full timestamp ("2018-07-01 14:00:00"); only the
        # calendar date is narratively relevant.
        date = info.date_utc.split(" ")[0] if info.date_utc else None

        return ContextMatch(
            label=info.label,
            date=date,
            venue=info.venue,
            home_team=info.home_team.name,
            away_team=info.away_team.name,
            home_score=score.home_score,
            away_score=score.away_score,
            result=score.result,
            went_to_extra_time=score.went_to_extra_time or None,
            went_to_penalties=score.went_to_penalties or None,
            penalty_score=score.penalty_score,
        )

    def _build_team_stats(self, stats: TeamStats) -> ContextTeamStats:
        return ContextTeamStats(
            team=stats.name,
            side=stats.side,
            shots=stats.shots,
            shots_on_target=stats.shots_on_target,
            goals=stats.goals,
            passes_attempted=stats.passes_attempted,
            pass_accuracy_pct=stats.pass_accuracy_pct,
            fouls=stats.fouls_committed,
            yellow_cards=stats.yellow_cards,
            red_cards=stats.red_cards,
            corners=stats.corners,
            pass_share_pct=stats.possession_proxy_pct,
        )

    def _build_player(self, player: TopPlayer, team_name_by_side: dict[str, str]) -> ContextPlayer:
        return ContextPlayer(
            name=player.name,
            team=team_name_by_side.get(player.side, f"Team {player.team_id}"),
            rating=player.rating,
            goals=player.goals,
            assists=player.assists,
            key_passes=player.key_passes,
        )

    def _build_moment(self, moment: KeyMoment) -> ContextMoment:
        return ContextMoment(
            minute=moment.minute_label,
            type=moment.moment_type,
            text=moment.description,
        )

    def _build_pattern(self, pattern: TacticalPattern) -> ContextPattern:
        return ContextPattern(
            team=pattern.team_name,
            pattern=pattern.pattern,
            text=pattern.explanation,
        )

    def _build_observation(self, observation: AnalyticsCoachingObservation) -> ContextObservation:
        return ContextObservation(
            team=observation.team_name,
            text=observation.observation,
            evidence=observation.supporting_evidence,
        )
