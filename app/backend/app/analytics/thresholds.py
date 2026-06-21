"""
Configuration for the analytics engine: rating weights and the thresholds
used to detect tactical patterns.

Everything here is a deliberately simple, named constant rather than a
learned/statistical model -- per the brief, the goal is a deterministic,
explainable pipeline, not the most sophisticated football model possible.
Tune these here rather than scattering magic numbers through
match_analyzer.py.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RatingWeights:
    """Weights for the transparent player-rating formula:

        rating = goals * goal
               + assists * assist
               + key_passes * key_pass
               + successful_actions * successful_action

    `successful_action` is deliberately small since a player accumulates
    dozens of these in a match (completed passes, won duels, ...), while
    goals/assists/key passes are rare and should dominate the score.
    """

    goal: float = 6.0
    assist: float = 4.0
    key_pass: float = 1.0
    successful_action: float = 0.05


@dataclass(frozen=True)
class TacticalThresholds:
    """Thresholds for the deterministic tactical-pattern rules.

    `avg_event_x` is the mean of each team's event start-x coordinate
    (0-100, already attacking-direction-normalized by Wyscout). Higher
    means the team's actions happen closer to the opponent's goal.
    """

    possession_dominant_pct: float = 55.0  # pass-share proxy, see TeamStats
    direct_play_high_pass_ratio: float = 0.20  # share of passes that are "High pass"/"Launch"
    defensive_avg_x_max: float = 42.0  # below this -> "deep / defensive shape"
    high_attacking_avg_x_min: float = 58.0  # above this -> "high attacking territory"
    attacking_third_x: float = 66.0  # x threshold for "final third"
    high_attacking_activity_share: float = 0.25  # share of events in final third


@dataclass(frozen=True)
class CoachingThresholds:
    """Thresholds for the deterministic coaching-observation templates."""

    low_shot_conversion_min_shots: int = 4  # need at least this many shots to comment on conversion
    low_shot_on_target_pct: float = 35.0
    low_pass_accuracy_pct: float = 75.0
    high_fouls: int = 13
    possession_imbalance_pct: float = 60.0  # one side at/above this -> comment on the other chasing the game


@dataclass(frozen=True)
class AnalyticsConfig:
    rating_weights: RatingWeights = RatingWeights()
    tactical: TacticalThresholds = TacticalThresholds()
    coaching: CoachingThresholds = CoachingThresholds()
    top_players_per_team: int = 3
