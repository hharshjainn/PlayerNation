"""
Event-level classification helpers shared across the analytics engine.

Every function here answers one specific, named football question about a
single raw event ("was this shot on target?", "was this a successful
action?") so that `match_analyzer.py` reads as football logic, not tag-id
arithmetic. Each rule is documented with *why*, since these are exactly the
kind of decisions a reviewer needs to be able to audit.
"""
from __future__ import annotations

import pandas as pd

from app.data.wyscout_constants import (
    EVENT_ID_FOUL,
    EVENT_ID_OFFSIDE,
    EVENT_ID_SAVE_ATTEMPT,
    OFF_TARGET_POSITION_TAGS,
    ON_TARGET_POSITION_TAGS,
    POST_POSITION_TAGS,
    SHOT_SUB_EVENT_IDS,
    SUB_EVENT_ID_CLEARANCE,
    SUB_EVENT_ID_CORNER,
    SUB_EVENT_ID_PENALTY,
    TAG_ACCURATE,
    TAG_ASSIST,
    TAG_BLOCKED,
    TAG_COUNTER_ATTACK,
    TAG_GOAL,
    TAG_KEY_PASS,
    TAG_NOT_ACCURATE,
    TAG_OWN_GOAL,
    TAG_RED_CARD,
    TAG_SECOND_YELLOW_CARD,
    TAG_YELLOW_CARD,
)

# Tag id used by Wyscout for "interception" -- imported by value here since
# wyscout_constants only exposes it inside the TAGS dict, not as a constant.
TAG_INTERCEPTION = 1401

# ---------------------------------------------------------------------------
# Match clock reconstruction
# ---------------------------------------------------------------------------
# `eventSec` resets every period (see Phase 1 README, ambiguity #3), so we
# reconstruct an approximate, human-readable match minute. This is
# explicitly an approximation: real stoppage time varies, and `eventSec`
# does not tell us when a period actually ended -- only how far into it a
# given event occurred.
_PERIOD_START_MINUTE = {"1H": 0, "2H": 45, "E1": 90, "E2": 105, "P": 120}
_PERIOD_NOMINAL_END_MINUTE = {"1H": 45, "2H": 90, "E1": 105, "E2": 120, "P": 120}
PERIOD_ORDER = {"1H": 0, "2H": 1, "E1": 2, "E2": 3, "P": 4}


def minute_label(period: str, event_sec: float) -> str:
    """Render an approximate, football-style minute label, e.g. '52'' or '45+2'."""
    start = _PERIOD_START_MINUTE.get(period, 0)
    nominal_end = _PERIOD_NOMINAL_END_MINUTE.get(period, start)
    minute_in_period = int(event_sec // 60)
    total = start + minute_in_period
    if total > nominal_end:
        return f"{nominal_end}+{total - nominal_end}'"
    return f"{total}'"


def approximate_minute(period: str, event_sec: float) -> int:
    """Numeric version of `minute_label`, for sorting/threshold comparisons."""
    start = _PERIOD_START_MINUTE.get(period, 0)
    return start + int(event_sec // 60)


# ---------------------------------------------------------------------------
# Shots
# ---------------------------------------------------------------------------
def _clean_sub_event_id(sub_event_id: object) -> int | None:
    """Normalize a `subEventId` cell to a plain int or None.

    The events DataFrame stores `subEventId` as nullable Int64 because
    Offside events ship `subEventId: ""` in the raw data (see Phase 1
    README). A naive `sub_event_id == 30` on a `pandas.NA` returns
    `pandas.NA` itself, not `False` -- which would silently corrupt any
    boolean Series built from these helpers. We make "missing" explicit
    here instead.
    """
    if sub_event_id is None or pd.isna(sub_event_id):
        return None
    return int(sub_event_id)


def is_shot_event(sub_event_id: int | None) -> bool:
    """True for open-play shots, free-kick shots, and penalties.

    Free-kick shots and penalties carry eventId 3 ("Free Kick"), not 10
    ("Shot") -- they're only distinguishable via subEventId. See Phase 1
    README and `wyscout_constants.SHOT_SUB_EVENT_IDS`.
    """
    cleaned = _clean_sub_event_id(sub_event_id)
    return cleaned is not None and cleaned in SHOT_SUB_EVENT_IDS


def is_penalty_event(sub_event_id: int | None) -> bool:
    cleaned = _clean_sub_event_id(sub_event_id)
    return cleaned is not None and cleaned == SUB_EVENT_ID_PENALTY


def is_corner_event(sub_event_id: int | None) -> bool:
    cleaned = _clean_sub_event_id(sub_event_id)
    return cleaned is not None and cleaned == SUB_EVENT_ID_CORNER


def is_on_target(tag_ids: set[int]) -> bool:
    """A shot counts as on target if it scored, hit the post, or was tagged
    with one of the "inside the goal frame" placement tags -- and was not
    blocked before reaching the frame.
    """
    if TAG_BLOCKED in tag_ids:
        return False
    if TAG_GOAL in tag_ids:
        return True
    if tag_ids & ON_TARGET_POSITION_TAGS:
        return True
    if tag_ids & POST_POSITION_TAGS:
        return True
    return False


def is_off_target(tag_ids: set[int]) -> bool:
    return bool(tag_ids & OFF_TARGET_POSITION_TAGS) and TAG_BLOCKED not in tag_ids


def is_post(tag_ids: set[int]) -> bool:
    return bool(tag_ids & POST_POSITION_TAGS)


# subEventId values for "High pass" (83) and "Launch" (84) -- used as a
# simple, explainable proxy for "direct" passing style.
HIGH_PASS_SUB_EVENT_IDS = frozenset({83, 84})


def start_x(positions: object) -> float | None:
    """Extract the start x-coordinate (0-100) from an event's `positions`
    field, defensively. Returns None if positions are missing/malformed.
    """
    if isinstance(positions, list) and len(positions) >= 1 and isinstance(positions[0], dict):
        return positions[0].get("x")
    return None


def is_goal(tag_ids: set[int]) -> bool:
    return TAG_GOAL in tag_ids


def is_scoring_event(event_id: int, sub_event_id: int | None, tag_ids: set[int]) -> bool:
    """True only for an event that represents an actual goal being scored
    by the player on that event (used for player goal tallies and the
    "goal"/"penalty_scored" key-moment branches).

    This deliberately requires the event to be a shot-type event
    (Shot / free-kick shot / penalty), not merely "carries tag 101".

    Why: real Wyscout own-goal sequences can split tags 101 ("goal") and
    102 ("own_goal") across two *different* consecutive events -- the
    deflecting touch (tagged 102 only, eventName "Touch"/"Others on the
    ball") and a goalkeeper's following save-attempt event, which can be
    stray-tagged with 101 even though the keeper didn't score (documented
    in the wild, e.g. ML-KULeuven/socceraction issue #25). Wyscout's own
    glossary confirms a genuine goal is always a Shot event except when
    it's an own goal -- so gating on "is this a shot?" reliably excludes
    that stray keeper tag without needing to reconstruct event sequences.
    Own goals are handled separately via `is_own_goal`, independent of
    this function.
    """
    return TAG_GOAL in tag_ids and is_shot_event(sub_event_id)


def is_own_goal(tag_ids: set[int]) -> bool:
    """True if this event carries the own_goal tag (102), checked
    independently of `is_goal`/`is_scoring_event` -- see the note on
    `is_scoring_event` for why the two tags can't be assumed to co-occur
    on the same event.
    """
    return TAG_OWN_GOAL in tag_ids


def is_counter_attack(tag_ids: set[int]) -> bool:
    return TAG_COUNTER_ATTACK in tag_ids


# ---------------------------------------------------------------------------
# Cards / fouls
# ---------------------------------------------------------------------------
def is_yellow_card(tag_ids: set[int]) -> bool:
    """A second yellow still shows a yellow card, so it counts here too."""
    return TAG_YELLOW_CARD in tag_ids or TAG_SECOND_YELLOW_CARD in tag_ids


def is_red_card(tag_ids: set[int]) -> bool:
    """A second yellow results in a red, so it counts here too."""
    return TAG_RED_CARD in tag_ids or TAG_SECOND_YELLOW_CARD in tag_ids


# ---------------------------------------------------------------------------
# Passing
# ---------------------------------------------------------------------------
def is_key_pass(tag_ids: set[int]) -> bool:
    return TAG_KEY_PASS in tag_ids


def is_assist(tag_ids: set[int]) -> bool:
    return TAG_ASSIST in tag_ids


def is_accurate(tag_ids: set[int]) -> bool:
    return TAG_ACCURATE in tag_ids


# ---------------------------------------------------------------------------
# Player-rating support: "was this a successful action?"
# ---------------------------------------------------------------------------
def is_successful_event(event_id: int, sub_event_id: int | None, tag_ids: set[int]) -> bool:
    """Decide whether a single event counts as a "successful action" for the
    player who performed it, for rating purposes.

    Priority order (each rule documented so the decision is auditable):
      1. Fouls and offsides are never a "success" for the player who
         committed/triggered them, regardless of any other tags present.
      2. Own goals are never a success for the scorer.
      3. A goal is always a success.
      4. Respect the dataset's own accurate/not_accurate tag when present
         (covers passes, crosses, shots, free kicks, ...).
      5. Interceptions and clearances are always counted as a defensive
         success, matching the convention used by the `socceraction`
         library when converting this exact dataset (an interception that
         puts the ball out of play is still a successful defensive act).
      6. For duels: "won" is a success, "lost" or "neutral" are not. We
         deliberately treat "neutral" as not-a-success (no clear winner) --
         a small, documented deviation from upstream prior art, which
         defaults ambiguous cases to "success"; we prefer the more
         conservative, more explainable reading.
      7. Goalkeeper save attempts are a success (the keeper acted on the
         shot).
      8. Anything else with no clear signal: not counted as a success. We
         would rather under-count than inflate a rating on a guess.
    """
    if event_id in (EVENT_ID_FOUL, EVENT_ID_OFFSIDE):
        return False
    if TAG_OWN_GOAL in tag_ids:
        return False
    if TAG_GOAL in tag_ids:
        return True
    if TAG_ACCURATE in tag_ids:
        return True
    if TAG_NOT_ACCURATE in tag_ids:
        return False
    if TAG_INTERCEPTION in tag_ids or _clean_sub_event_id(sub_event_id) == SUB_EVENT_ID_CLEARANCE:
        return True
    if 703 in tag_ids:  # duel won
        return True
    if 701 in tag_ids:  # duel lost
        return False
    if 702 in tag_ids:  # duel neutral -- no clear winner
        return False
    if event_id == EVENT_ID_SAVE_ATTEMPT:
        return True
    return False
