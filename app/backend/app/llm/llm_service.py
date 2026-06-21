"""
Phase 4: LLM integration -- turning a Phase 3 `MatchContext` into a
validated `MatchReport`.

Provider: Groq (https://api.groq.com), OpenAI-compatible chat completions
endpoint, model "llama-3.3-70b-versatile" by default (configurable via
`Settings.groq_model` / `PLAYERNATION_GROQ_MODEL`).

  Originally specified as Gemini 2.5 Flash; swapped to Groq + Llama 3.3
  70B per explicit instruction. Verified via web search (mid-2026) that
  `llama-3.3-70b-versatile` is still an active model id on Groq's free
  tier (1,000 requests/day) before writing this, rather than assuming.

JSON enforcement -- `response_format={"type": "json_object"}` ("JSON
mode"), deliberately *not* the newer `json_schema` "Structured Outputs"
mode:
  Groq's own docs gate `json_schema` enforcement to "supported models",
  and every worked example of it in their docs uses the `openai/gpt-oss-*`
  models, not `llama-3.3-70b-versatile` -- there's no confirmed guarantee
  it's honored for this model, and Groq's own community forum has reports
  of structured outputs being silently ignored even for a model that
  nominally supports it. `json_object` mode (valid JSON syntax, not
  schema-validated) is broadly and reliably documented as supported
  across Groq's models. The brief separately requires our own schema
  validation + retry logic on top regardless of provider guarantees, so
  this combination satisfies the requirement without depending on an
  unconfirmed feature.

Reliability pipeline, end to end:
  1. Ask for JSON mode and give the schema explicitly in the system
     prompt (required for JSON mode to behave well, and makes failures
     rarer to begin with).
  2. Parse the response as JSON.
  3. Validate it against `MatchReport` (Pydantic) -- catches wrong types
     or missing keys.
  4. Run a few lightweight content-quality checks Pydantic's type
     validation alone wouldn't catch (e.g. a syntactically-valid-but-empty
     list, or a blank string).
  5. If any of 2-4 fail, re-prompt with the previous output and the exact
     error, and try again, up to `Settings.groq_max_retries` extra times.
  6. If every attempt fails, raise one normalized `ReportGenerationError`
     -- callers (the Phase 6 API layer) never need to handle more than
     one exception type, and never see a raw
     `JSONDecodeError`/`ValidationError`/network exception.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

import requests
from pydantic import ValidationError

from app.context.models import MatchContext
from app.core.config import Settings
from app.core.config import settings as default_settings
from app.llm.report_schema import MatchReport, ReportGenerationResult

logger = logging.getLogger(__name__)

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are a football (soccer) match report writer for PlayerNation.

You will be given structured match data as a JSON object. Using ONLY that data, write a match report as a single JSON object with EXACTLY these five keys:

{
  "summary": "3-5 sentences: the final score, who won (or drew), and the headline storyline of the match",
  "turning_points": ["2-5 short items, each 1-2 sentences, on the specific moments that decided the match (goals, red cards, big missed chances)"],
  "standout_players": ["2-4 short items naming one specific player each and why they stood out, using the ratings/goals/assists/key passes given"],
  "tactical_analysis": "2-4 sentences on how each team played, based on the tactical patterns given",
  "coaching_insights": ["2-4 short, actionable items a coach could use, based on the coaching observations given"]
}

Rules:
- Respond with ONLY that JSON object. No markdown, no code fences, no commentary before or after it.
- Use ONLY the players, teams, scores, and events present in the match data you were given. Never invent a player, team, statistic, or event that isn't in it.
- Every claim should be traceable to a specific number or moment in the data you were given.
- Write in clear, engaging football-journalism prose -- full sentences, not data dumps.
- Do not just restate the raw data verbatim; synthesize it into a narrative."""


class ReportGenerationError(Exception):
    """Raised when a report could not be produced after exhausting
    retries, or the service is missing required configuration (e.g. no
    API key).

    Every failure mode inside `generate_report` -- network/HTTP errors,
    malformed JSON, schema-validation failures -- is normalized into this
    one exception type before it reaches the caller, carrying whatever
    diagnostic context is available. This is what makes "the backend
    never crashes because of malformed LLM output" true: there is exactly
    one exception type a caller needs to catch.
    """

    def __init__(
        self,
        message: str,
        *,
        raw_response: Optional[str] = None,
        attempts: int = 0,
        latency_ms: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.attempts = attempts
        self.latency_ms = latency_ms


class GroqReportService:
    """Generates a validated `MatchReport` from a `MatchContext` via Groq."""

    def __init__(self, settings: Settings = default_settings) -> None:
        self._settings = settings

    async def generate_report(self, context: MatchContext) -> ReportGenerationResult:
        if not self._settings.groq_api_key:
            raise ReportGenerationError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys "
                "and set it as the GROQ_API_KEY environment variable."
            )

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_user_message(context)},
        ]

        start = time.monotonic()
        last_error: Optional[str] = None
        raw_content: Optional[str] = None
        max_attempts = self._settings.groq_max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                raw_content = await asyncio.to_thread(self._call_groq, messages)
            except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as exc:
                last_error = f"Groq request failed: {exc}"
                logger.warning("Groq call failed on attempt %s/%s: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    await asyncio.sleep(self._backoff_seconds(attempt, exc))
                continue

            try:
                report = self._parse_and_validate(raw_content)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = str(exc)
                logger.warning("Invalid LLM output on attempt %s/%s: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "That response was not valid JSON matching the required schema. "
                                f"Error: {exc}\n"
                                "Return ONLY the corrected JSON object, with no other text."
                            ),
                        }
                    )
                continue

            return ReportGenerationResult(
                report=report,
                raw_response=raw_content,
                attempts=attempt,
                latency_ms=round((time.monotonic() - start) * 1000, 1),
                model=self._settings.groq_model,
            )

        raise ReportGenerationError(
            f"Failed to get a valid report after {max_attempts} attempt(s). Last error: {last_error}",
            raw_response=raw_content,
            attempts=max_attempts,
            latency_ms=round((time.monotonic() - start) * 1000, 1),
        )

    # ------------------------------------------------------------------
    def _build_user_message(self, context: MatchContext) -> str:
        context_json = context.model_dump_json(exclude_none=True)
        return (
            f"Match data (JSON):\n{context_json}\n\n"
            "Write the match report now as a single JSON object matching the schema exactly."
        )

    def _call_groq(self, messages: list[dict]) -> str:
        """Synchronous Groq call, run off the event loop via
        `asyncio.to_thread` in `generate_report`. `requests` has no native
        async API; running a sync client in a thread is the standard way
        to use it from async code (e.g. a future FastAPI route) without
        blocking the event loop.
        """
        payload: dict = {
            "model": self._settings.groq_model,
            "messages": messages,
            "temperature": self._settings.groq_temperature,
            "response_format": {"type": "json_object"},
        }
        if self._settings.groq_seed is not None:
            payload["seed"] = self._settings.groq_seed

        response = requests.post(
            GROQ_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {self._settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._settings.groq_request_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _parse_and_validate(self, raw_content: str) -> MatchReport:
        parsed = json.loads(raw_content)
        report = MatchReport.model_validate(parsed)
        issues = self._quality_issues(report)
        if issues:
            raise ValueError(f"report failed quality checks: {'; '.join(issues)}")
        return report

    def _quality_issues(self, report: MatchReport) -> list[str]:
        """Content-quality checks beyond bare type/shape validation (which
        Pydantic already guarantees) -- a syntactically valid empty string
        or empty list is not a usable report, and we'd rather retry than
        ship it.
        """
        issues: list[str] = []
        if not report.summary.strip():
            issues.append("summary is blank")
        if not report.tactical_analysis.strip():
            issues.append("tactical_analysis is blank")
        for field_name, value in (
            ("turning_points", report.turning_points),
            ("standout_players", report.standout_players),
            ("coaching_insights", report.coaching_insights),
        ):
            if not value:
                issues.append(f"{field_name} is empty")
            elif any(not item.strip() for item in value):
                issues.append(f"{field_name} contains a blank item")
        return issues

    def _backoff_seconds(self, attempt: int, exc: Exception) -> float:
        """A short, capped backoff before retrying a transport-level
        failure. Respects `Retry-After` on a 429 (rate limit) when Groq
        sends one, since the free tier does rate-limit; otherwise a small
        exponential backoff.
        """
        response = getattr(exc, "response", None)
        if response is not None and getattr(response, "status_code", None) == 429:
            retry_after = response.headers.get("Retry-After") if hasattr(response, "headers") else None
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
            return 5.0
        return min(2 ** (attempt - 1), 5)
