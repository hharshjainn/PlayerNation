"""
Reference vocabulary for the raw Wyscout event schema (Pappalardo et al., 2019).

This module is intentionally separated from the loading/parsing logic because
the same dictionaries will be reused by the Phase 2 analytics engine. Nothing
here is guessed: every mapping below was cross-checked against (a) real event
records pulled from this dataset and (b) the open-source `socceraction`
library, which independently re-implements the same Wyscout -> SPADL mapping
used in published research built on this dataset.

If you load the real dataset locally and find a tag/event id NOT covered
here, treat it as a genuine gap (the public Wyscout tag list has ~60 tags,
some extremely rare e.g. related to exact shot placement) -- log it via
`describe_unknown_tags()` rather than silently ignoring it.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Top level event types ("eventId" / "eventName" in the raw JSON)
# ---------------------------------------------------------------------------
EVENT_TYPES: dict[int, str] = {
    1: "Duel",
    2: "Foul",
    3: "Free Kick",
    4: "Goalkeeper leaving line",
    5: "Interruption",
    6: "Offside",
    7: "Others on the ball",
    8: "Pass",
    9: "Save attempt",
    10: "Shot",
}

# ---------------------------------------------------------------------------
# Sub event types ("subEventId" / "subEventName"). Not exhaustive -- the raw
# `subEventName` string is always trusted as the display label. This dict
# exists so analytics code can branch on stable integer ids instead of
# free-text strings.
# ---------------------------------------------------------------------------
SUB_EVENT_TYPES: dict[int, str] = {
    10: "Air duel",
    11: "Ground attacking duel",
    12: "Ground defending duel",
    13: "Ground loose ball duel",
    20: "Foul",
    21: "Hand foul",
    22: "Late card foul",
    23: "Out of game foul",
    24: "Protest",
    25: "Simulation",
    26: "Time lost foul",
    27: "Violent Conduct",
    30: "Corner",
    31: "Free Kick",
    32: "Free kick cross",
    33: "Free kick shot",
    34: "Goal kick",
    35: "Penalty",
    36: "Throw in",
    50: "Ball out of the field",
    51: "Whistle",
    52: "Ball in play",
    70: "Acceleration",
    71: "Clearance",
    72: "Touch",
    80: "Cross",
    81: "Hand pass",
    82: "Head pass",
    83: "High pass",
    84: "Launch",
    85: "Simple pass",
    86: "Smart pass",
    90: "Reflexes",
    91: "Save attempt",
    100: "Shot",
}

# ---------------------------------------------------------------------------
# Tags. Every event carries zero or more of these as {"id": <int>}.
# Source: Pappalardo et al. (2019) Table 2 + socceraction's `wyscout_tags`
# mapping (ML-KULeuven/socceraction), verified against real sample events.
# ---------------------------------------------------------------------------
TAGS: dict[int, str] = {
    101: "goal",
    102: "own_goal",
    201: "opportunity",
    301: "assist",
    302: "key_pass",
    401: "left_foot",
    402: "right_foot",
    403: "head/body",
    501: "free_space_right",
    502: "free_space_left",
    503: "take_on_left",
    504: "take_on_right",
    601: "anticipated",
    602: "anticipation",
    701: "lost",
    702: "neutral",
    703: "won",
    801: "high",
    802: "low",
    901: "through",
    1001: "fairplay",
    1101: "direct",
    1102: "indirect",
    1201: "position_goal_low_center",
    1202: "position_goal_low_right",
    1203: "position_goal_mid_center",
    1204: "position_goal_mid_left",
    1205: "position_goal_low_left",
    1206: "position_goal_mid_right",
    1207: "position_goal_high_center",
    1208: "position_goal_high_left",
    1209: "position_goal_high_right",
    1210: "position_out_low_right",
    1211: "position_out_mid_left",
    1212: "position_out_low_left",
    1213: "position_out_mid_right",
    1214: "position_out_high_center",
    1215: "position_out_high_left",
    1216: "position_out_high_right",
    1217: "position_post_low_right",
    1218: "position_post_mid_left",
    1219: "position_post_low_left",
    1220: "position_post_mid_right",
    1221: "position_post_high_center",
    1222: "position_post_high_left",
    1223: "position_post_high_right",
    1301: "feint",
    1302: "missed_ball",
    1401: "interception",
    1501: "clearance",
    1601: "sliding_tackle",
    1701: "red_card",
    1702: "yellow_card",
    1703: "second_yellow_card",
    1801: "accurate",
    1802: "not_accurate",
    1901: "counter_attack",
    2001: "dangerous_ball_lost",
    2101: "blocked",
}

# Tags that indicate the shot ended up "on target" (in the goal frame),
# as opposed to going out or hitting the post.
ON_TARGET_POSITION_TAGS: frozenset[int] = frozenset(
    {1201, 1202, 1203, 1204, 1205, 1206, 1207, 1208, 1209}
)
# Tags that indicate the shot missed the frame entirely (wide/over).
OFF_TARGET_POSITION_TAGS: frozenset[int] = frozenset(
    {1210, 1211, 1212, 1213, 1214, 1215, 1216}
)
# Tags that indicate the shot struck the post (counted as on target).
POST_POSITION_TAGS: frozenset[int] = frozenset(
    {1217, 1218, 1219, 1220, 1221, 1222, 1223}
)

# Convenience single-tag constants used heavily by the analytics engine.
TAG_GOAL = 101
TAG_OWN_GOAL = 102
TAG_ASSIST = 301
TAG_KEY_PASS = 302
TAG_YELLOW_CARD = 1702
TAG_RED_CARD = 1701
TAG_SECOND_YELLOW_CARD = 1703
TAG_ACCURATE = 1801
TAG_NOT_ACCURATE = 1802
TAG_COUNTER_ATTACK = 1901
TAG_BLOCKED = 2101

EVENT_ID_DUEL = 1
EVENT_ID_FOUL = 2
EVENT_ID_FREE_KICK = 3
EVENT_ID_INTERRUPTION = 5
EVENT_ID_OFFSIDE = 6
EVENT_ID_OTHERS_ON_BALL = 7
EVENT_ID_PASS = 8
EVENT_ID_SAVE_ATTEMPT = 9
EVENT_ID_SHOT = 10

SUB_EVENT_ID_CORNER = 30
SUB_EVENT_ID_FREE_KICK = 31
SUB_EVENT_ID_FREE_KICK_CROSS = 32
SUB_EVENT_ID_FREE_KICK_SHOT = 33
SUB_EVENT_ID_GOAL_KICK = 34
SUB_EVENT_ID_PENALTY = 35
SUB_EVENT_ID_THROW_IN = 36
SUB_EVENT_ID_BALL_OUT = 50
SUB_EVENT_ID_CLEARANCE = 71
SUB_EVENT_ID_TOUCH = 72
SUB_EVENT_ID_CROSS = 80
SUB_EVENT_ID_SHOT = 100
SUB_EVENT_ID_FOUL = 20

# subEventId values that represent shots on goal (used together with eventId
# == 10, but free kick shots and penalties carry eventId == 3 instead).
SHOT_SUB_EVENT_IDS: frozenset[int] = frozenset(
    {SUB_EVENT_ID_SHOT, SUB_EVENT_ID_FREE_KICK_SHOT, SUB_EVENT_ID_PENALTY}
)


def tag_ids(tags: list[dict]) -> set[int]:
    """Extract the set of tag ids from a raw event's ``tags`` field."""
    return {t["id"] for t in tags if "id" in t}


def has_tag(tags: list[dict], tag_id: int) -> bool:
    return tag_id in tag_ids(tags)


def describe_unknown_tags(tags: list[dict]) -> list[int]:
    """Return any tag ids present in the data but missing from TAGS.

    Useful as a data-quality check when pointing the loader at the real
    dataset for the first time.
    """
    return [t["id"] for t in tags if "id" in t and t["id"] not in TAGS]
