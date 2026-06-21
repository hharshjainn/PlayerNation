"""
Phase 5: content-correctness checks.

Every function here takes the already-generated `(MatchReport, MatchContext)`
pair and returns a small typed result -- nothing here calls the LLM or
touches the analytics pipeline, so these can be (and are, see the
sandbox test suite) exercised directly against hand-built fixtures
without any network access.

These are deliberately simple, auditable, string/keyword-based checks,
not semantic understanding -- consistent with this project's "favor
clarity and robustness over advanced models" principle (Phase 2's brief),
extended here to evaluation. Each function's docstring states exactly
what it can and can't catch, so a human reading a flagged result knows
how much to trust it.
"""
from __future__ import annotations

import re
from typing import Optional

from app.context.models import MatchContext
from app.llm.report_schema import MatchReport
from evaluation.models import CoverageResult, HallucinationCheckResult, WinnerCheckResult

# Moment types treated as "major" for coverage purposes -- the
# game-deciding ones. `post` and `counter_attack_shot` are left out: they're
# flavor/texture moments, not usually what coverage of a match report is
# judged on.
MAJOR_MOMENT_TYPES = frozenset({"goal", "own_goal", "penalty_scored", "penalty_missed", "red_card"})

_WIN_KEYWORDS = ("won", "win", "beat", "beats", "defeat", "defeated", "victory", "triumph", "edged", "downed")
_LOSE_KEYWORDS = ("lost", "lose", "fell to", "falls to", "defeated by", "beaten by")
_DRAW_KEYWORDS = ("draw", "drew", "tied", " tie ", "level", "stalemate", "share the points", "shared the points")

# Phrases `match_analyzer.py` uses to lead into a player's name in a
# KeyMoment's `description` -- used only to strip them back off when
# extracting the name. See `_extract_names_from_moment_text`.
_MOMENT_LEAD_INS = (
    "Goal by ",
    "Penalty scored by ",
    "Penalty missed or saved -- taken by ",
    "Red card for ",
    "Own goal by ",
)


def _full_text(report: MatchReport) -> str:
    return " ".join(
        [report.summary, report.tactical_analysis, *report.turning_points, *report.standout_players, *report.coaching_insights]
    )


def check_missing_sections(report: MatchReport) -> list[str]:
    """Independent structural-completeness check, decoupled from
    `llm_service.py`'s internal quality gate on purpose: this needs to work
    as a standalone judge of *any* report, including ones produced by a
    future prompt/model swap that might not share that internal gate.
    """
    missing: list[str] = []
    if not report.summary.strip():
        missing.append("summary")
    if not report.tactical_analysis.strip():
        missing.append("tactical_analysis")
    for name, value in (
        ("turning_points", report.turning_points),
        ("standout_players", report.standout_players),
        ("coaching_insights", report.coaching_insights),
    ):
        if not value or all(not item.strip() for item in value):
            missing.append(name)
    return missing


def check_winner_correctness(report: MatchReport, context: MatchContext) -> WinnerCheckResult:
    """Keyword/proximity heuristic for whether `summary` states the correct
    result. Not semantic understanding: it looks for a win-keyword near
    the winning team's name, or a lose-keyword near the losing team's name
    (covers both "Alpha beat Beta" and "Beta lost to Alpha" phrasings). It
    will misjudge phrasings outside that keyword list -- a deliberate,
    documented limitation rather than building a full NLI model for a
    take-home evaluation tool.
    """
    summary_lower = report.summary.lower()
    expected = context.match.result

    if expected == "draw":
        correct = any(kw in summary_lower for kw in _DRAW_KEYWORDS)
        signal = "draw keyword found in summary" if correct else "no draw keyword found in summary"
        return WinnerCheckResult(correct=correct, expected_result=expected, detected_signal=signal)

    winner = context.match.home_team if expected == "home_win" else context.match.away_team
    loser = context.match.away_team if expected == "home_win" else context.match.home_team

    winner_ok = _keyword_near_name(summary_lower, winner.lower(), _WIN_KEYWORDS)
    loser_ok = _keyword_near_name(summary_lower, loser.lower(), _LOSE_KEYWORDS)
    correct = winner_ok or loser_ok

    if correct:
        signal = f"win/lose keyword found near '{winner}'/'{loser}'"
    elif winner.lower() not in summary_lower:
        signal = f"winning team '{winner}' not even mentioned in summary"
    else:
        signal = f"no win/lose keyword found near '{winner}'/'{loser}' in summary"

    return WinnerCheckResult(correct=correct, expected_result=expected, detected_signal=signal)


def _keyword_near_name(text_lower: str, name_lower: str, keywords: tuple[str, ...], window: int = 60) -> bool:
    idx = text_lower.find(name_lower)
    if idx == -1:
        return False
    surrounding = text_lower[max(0, idx - window) : idx + len(name_lower) + window]
    return any(kw in surrounding for kw in keywords)


def _extract_names_from_moment_text(text: str) -> tuple[Optional[str], list[str]]:
    """Best-effort extraction of the player name and team name(s) embedded
    in a KeyMoment's `text`, exploiting the fact that we control the exact
    phrasing these were generated with in `match_analyzer.py` (every
    format is "<lead-in><player> (<team>)..."). This is not a general NLP
    name extractor -- it would break if the description templates change.

    Returns `(player_name_or_None, team_names)` -- kept separate rather
    than one flat list, because a team name (unlike a specific player) is
    almost certain to appear *somewhere* in any football report
    regardless of whether that particular moment was actually covered.
    Treating a team-name match as equivalent to a player-name match would
    make coverage checks trivially pass.
    """
    team_names: list[str] = []

    paren_match = re.search(r"\(([^)]+)\)", text)
    if paren_match:
        team_names.append(paren_match.group(1).strip())

    credited_match = re.search(r"credited to (\w+)", text)
    if credited_match:
        team_names.append(credited_match.group(1).strip())

    player_part = text
    for lead_in in _MOMENT_LEAD_INS:
        if player_part.startswith(lead_in):
            player_part = player_part[len(lead_in) :]
            break
    player_part = player_part.split("(")[0].strip()
    player_name = player_part if player_part and player_part.lower() != "a player" else None

    return player_name, [n for n in team_names if n]


def check_major_event_coverage(report: MatchReport, context: MatchContext) -> CoverageResult:
    """For each "major" key moment, checks whether it's covered in the
    report text. When the moment names a specific player (the normal
    case), coverage requires *that player's name* to appear in the report
    -- a team name alone doesn't count, since a team name is near-certain
    to appear somewhere in any report regardless of whether this specific
    moment was discussed. Only the rare anonymous case ("a player") falls
    back to checking for either team name. A match with zero major
    moments (e.g. a goalless, cardless draw) is treated as 100% covered --
    there's nothing to miss.
    """
    text_lower = _full_text(report).lower()
    major_moments = [m for m in context.key_moments if m.type in MAJOR_MOMENT_TYPES]

    covered: list[str] = []
    missing: list[str] = []
    for moment in major_moments:
        label = f"{moment.minute} {moment.type}: {moment.text}"
        player_name, team_names = _extract_names_from_moment_text(moment.text)

        if player_name:
            is_covered = player_name.lower() in text_lower
        else:
            is_covered = any(team.lower() in text_lower for team in team_names)

        (covered if is_covered else missing).append(label)

    total = len(major_moments)
    coverage_pct = round(100 * len(covered) / total, 1) if total else 100.0
    return CoverageResult(covered=covered, missing=missing, coverage_pct=coverage_pct)


def check_top_player_coverage(report: MatchReport, context: MatchContext) -> CoverageResult:
    """Share of `context.top_players` whose name appears anywhere in the
    report text. A match with no top players recorded is treated as 100%
    covered for the same vacuous-truth reason as `check_major_event_coverage`.
    """
    text_lower = _full_text(report).lower()
    covered: list[str] = []
    missing: list[str] = []
    for player in context.top_players:
        if player.name.lower() in text_lower:
            covered.append(player.name)
        else:
            missing.append(player.name)

    total = len(context.top_players)
    coverage_pct = round(100 * len(covered) / total, 1) if total else 100.0
    return CoverageResult(covered=covered, missing=missing, coverage_pct=coverage_pct)


_SCORELINE_PATTERN = re.compile(r"\d+\s*[-–:]\s*\d+")


def check_hallucinations(report: MatchReport, context: MatchContext) -> HallucinationCheckResult:
    """Checks the kind of hallucination that's both likely and cheaply
    checkable for this domain: did the model name the right teams, state
    the right score, and only describe standout players we actually know
    about. This is a precision-first, not recall-first, tool: it will not
    catch every kind of invented detail (e.g. a fabricated statistic
    attached to a real player), only the cases below.
    """
    summary = report.summary
    summary_lower = summary.lower()

    home_mentioned = context.match.home_team.lower() in summary_lower
    away_mentioned = context.match.away_team.lower() in summary_lower

    score_mentioned = False
    for scoreline in _SCORELINE_PATTERN.finditer(summary):
        digits = [int(d) for d in re.findall(r"\d+", scoreline.group())]
        if len(digits) == 2 and set(digits) == {context.match.home_score, context.match.away_score}:
            score_mentioned = True
            break
    if not score_mentioned:
        score_mentioned = str(context.match.home_score) in summary and str(context.match.away_score) in summary

    unrecognized_names = _find_unrecognized_standout_players(report, context)

    return HallucinationCheckResult(
        home_team_mentioned=home_mentioned,
        away_team_mentioned=away_mentioned,
        score_mentioned=score_mentioned,
        unrecognized_names=unrecognized_names,
    )


def _find_unrecognized_standout_players(report: MatchReport, context: MatchContext) -> list[str]:
    """Flags any `standout_players` item that doesn't contain any name we
    actually know about (a top player or either team name) -- a likely
    sign the model named a player not in our data. Precision-first: it
    will miss subtler hallucinations (a real player with an invented
    stat), but a flag here is a strong signal worth a human glance.
    """
    known_names = {p.name.lower() for p in context.top_players}
    known_names.add(context.match.home_team.lower())
    known_names.add(context.match.away_team.lower())

    flagged = []
    for item in report.standout_players:
        item_lower = item.lower()
        if not any(name in item_lower for name in known_names if name):
            flagged.append(item)
    return flagged
