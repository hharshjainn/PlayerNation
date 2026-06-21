# PlayerNation Match Report Generator

Incremental build-out of an end-to-end football match report generator on
top of the Wyscout Soccer Match Event Dataset (FIFA World Cup 2018 slice).
Each phase is implemented, tested, and reviewed before the next begins.
This README accumulates one section per phase.

## Phase 1 — Dataset Exploration

### Source

Dataset: https://github.com/koenvo/wyscout-soccer-match-event-dataset,
which mirrors the original Pappalardo et al. (2019) "Soccer match event
dataset" publication. We use the **FIFA World Cup 2018** slice.

The repo's `README` links to the original figshare sources:

| File | Format | Notes |
|---|---|---|
| `teams.json` | JSON | **Global** — covers all 7 competitions, not just the World Cup |
| `players.json` | JSON | **Global** — same as above |
| `matches_World_Cup.json` | JSON (also shipped zipped) | One document per match |
| `events_World_Cup.json` | JSON (also shipped zipped) | One document per event |

> Note on environment: this sandbox has no outbound network access to
> GitHub/figshare/PyPI, so the schema below was verified by directly
> fetching real sample records and the dataset's own academic paper
> (Pappalardo et al., *Scientific Data* 6, 236, 2019) via the web tool, and
> cross-checked against the open-source `socceraction` library's
> independent re-implementation of the same Wyscout→action mapping. The
> code in this repo was then smoke-tested against a small hand-written
> fixture that mirrors the verified schema exactly (see
> `backend/data/fixtures/`). **You will need to download the real files
> yourself** (see "Getting the real data" below) and run
> `scripts/explore_dataset.py` against them as the final acceptance check
> before moving to Phase 2.

### Verified schema

**Events** (`events_World_Cup.json`) — one row per touch/incident:

```
eventId        int     top-level type, e.g. 8 = Pass, 10 = Shot, 1 = Duel
eventName      str     human label for eventId
subEventId     int|""  finer-grained type, e.g. 85 = Simple pass. EMPTY
                        STRING for Offside events -- not always an int!
subEventName   str     human label for subEventId
tags           list    [{"id": <int>}, ...] -- accuracy/outcome metadata
playerId       int     0 means "no specific player" (e.g. ball out of play)
teamId         int
matchId        int
matchPeriod    str     "1H" | "2H" | "E1" | "E2" | "P"
eventSec       float   seconds since the START OF THE CURRENT PERIOD,
                        NOT a running match clock
positions      list    [{"x":.., "y":..}, {"x":.., "y":..}] start/end,
                        0-100 scale, attacking-direction-normalized
id             int     unique event id
```

**Matches** (`matches_World_Cup.json`):

```
wyId, competitionId, label, date, dateutc, venue, status, duration,
winner (0 = draw), roundId, gameweek
teamsData: { "<teamId>": { side, score, scoreHT, scoreET, scoreP,
                            coachId, lineup: [...], bench: [...],
                            substitutions: [...] }, ... }
```

`teamsData` is a **dict keyed by team id**, not a list — easy to get wrong.

**Teams** (`teams.json`): `wyId, name, officialName, city, area, type`
(`type` is `"national"` for World Cup squads, `"club"` for league teams).

**Players** (`players.json`): `wyId, shortName, firstName, lastName,
birthDate, birthArea, passportArea, foot, height, weight, role
({name, code2}), currentTeamId, currentNationalTeamId`.

### Ambiguities found, and the decisions made

1. **Player short-name field name.** The original paper's prose calls it
   `shortName2`, but real-world dumps and most downstream tooling use
   `shortName`. **Decision:** `dataset_loader.get_player()` checks for
   `shortName` first and falls back to `shortName2`.
2. **`subEventId` is not always numeric.** Offside events ship
   `"subEventId": ""`. **Decision:** the events DataFrame coerces this
   column to nullable `Int64` (`pd.to_numeric(..., errors="coerce")`) so
   downstream numeric comparisons never raise, and missing values are
   real, queryable nulls rather than silently-wrong zeros.
3. **`eventSec` resets every period.** It is *not* a cumulative match
   clock, so naive sorting by `eventSec` alone interleaves halves
   incorrectly. **Decision:** `get_events_for_match()` sorts by
   `(matchPeriod ordinal, eventSec)` using an explicit period-ordering
   table (`1H < 2H < E1 < E2 < P`), since World Cup knockout matches can
   go to extra time / penalties.
4. **No explicit "competition" field on players/teams.** Since
   `players.json` / `teams.json` are shared across all 7 competitions,
   there is no reliable structural way to ask "which players are at the
   World Cup" except by *usage*: who actually appears in World Cup
   matches/events. **Decision:** the loader never filters these global
   files; `DatasetSummary.num_players_referenced` /
   `num_teams_referenced` are computed from ids that actually occur in the
   loaded competition's events, not from the global files directly.
5. **Per-player counters (`goals`, `yellowCards`, etc.) inside
   `teamsData.*.lineup/bench`** are sometimes encoded as strings (e.g.
   `"goals": "1"`). **Decision:** anything we read from there is cast
   explicitly (`int(... or 0)`) rather than assumed numeric.
6. **Tag vocabulary isn't shipped with the dataset itself** (it lives in
   Wyscout's gated API docs). **Decision:** `wyscout_constants.py` ships a
   verified `TAGS` dictionary (cross-checked against `socceraction`) plus
   a `find_unknown_tag_ids()` data-quality check the explorer script runs
   automatically, so any tag we don't recognize is surfaced rather than
   silently ignored.
7. **Own goals.** A goal tagged `102` (`own_goal`) credits the *scoring
   team* in raw Wyscout terms but should count toward the *opponent's*
   score in football terms. This doesn't affect Phase 1, but is flagged
   here because Phase 2's score reconstruction must handle it explicitly.
8. **Own-goal tags can be split across two different events.** Confirmed
   against a real-world example (ML-KULeuven/socceraction issue #25): the
   deflecting touch carries tag `102` *alone* (no `101`), while a
   following event -- often the opposing goalkeeper's save attempt -- can
   be left with a stray `101` ("goal") tag even though that player didn't
   score. Wyscout's own glossary confirms a genuine goal is always a Shot
   event, except when it's an own goal, which is exactly the asymmetry
   exploited here. **Decision:** Phase 2 never assumes tags 101 and 102
   co-occur on the same event. Own-goal detection (`is_own_goal`) is
   checked independently of the goal tag; genuine goal/penalty detection
   (`is_scoring_event`) additionally requires the event to be a shot-type
   event, which reliably excludes the stray-tagged keeper event. Team-level
   goal counts use the authoritative `teamsData.score` from match metadata
   rather than re-deriving from tags at all.

### Data access layer

- `app/data/wyscout_constants.py` — verified `EVENT_TYPES` / `SUB_EVENT_TYPES`
  / `TAGS` dictionaries plus tag-set helpers (`has_tag`, `tag_ids`,
  `describe_unknown_tags`). Reused by Phase 2's analytics engine.
- `app/data/models.py` — Pydantic models (`Team`, `Player`, `Match`,
  `MatchTeamInfo`, `MatchSummary`, `DatasetSummary`) for typed access at
  the boundaries of the system.
- `app/data/dataset_loader.py` — `DatasetLoader`: loads teams/players/
  matches/events (plain or zipped JSON) into cached pandas DataFrames, and
  exposes typed accessors (`get_team`, `get_player`, `get_match`,
  `list_matches`, `get_events_for_match`) plus the data-quality helper
  `find_unknown_tag_ids`.
- `app/core/config.py` — environment-driven settings (`raw_data_dir`,
  `default_competition`) so nothing is hardcoded.

### Getting the real data

1. Download (from the figshare links in the dataset's own README, or via
   `git clone` of the koenvo mirror's `raw_data/` folder once you have
   network access):
   `teams.json`, `players.json`, `matches_World_Cup.json` (or its zip),
   `events_World_Cup.json` (or its zip).
2. Place them in `backend/data/raw/` (or set
   `PLAYERNATION_RAW_DATA_DIR=/path/to/files`).
3. From `backend/`, run:
   ```
   python -m scripts.explore_dataset
   ```

### Validation performed in this sandbox

Since this sandbox cannot reach GitHub/figshare/PyPI, `dataset_loader.py`
and `explore_dataset.py` were exercised end-to-end against a small,
hand-written fixture in `backend/data/fixtures/` that mirrors the verified
real schema field-for-field (including the `subEventId: ""` Offside
quirk, string-encoded card counters, and a zipped variant of
matches/events). All of the following were confirmed to work correctly:
event-type counts, chronological sorting across "1H"/"2H", typed
`Team`/`Player`/`Match`/`MatchSummary` construction, the `playerId == 0`
sentinel, zipped-JSON loading, the missing-file error message, and the
unknown-tag data-quality check (returns empty, as expected, since every
tag id used in the fixture is in `TAGS`).

## Phase 2 — Match Analytics Engine

`MatchAnalyzer.analyze(match_id)` is the entry point. It turns one match's
raw events into a fully typed `MatchAnalysis`: `match_info`, `score`,
`team_stats`, `top_players`, `key_moments`, `tactical_patterns`, and
`coaching_observations`.

### Design principles

- **Deterministic and explainable.** Every number in the output is either
  a direct count/aggregate from the raw events, or a simple, named,
  documented threshold rule (`app/analytics/thresholds.py`) — never a
  black-box score.
- **The official score comes from match metadata**, not from re-deriving
  it from event tags — see ambiguities 7 and 8 above. Event tags are still
  used to figure out *who* scored, for the key-moments timeline and player
  goal tallies, with own goals explicitly excluded from the scorer's own
  tally and re-attributed to the conceding team's opponent.
- **Player ratings are a transparent formula**, not a model:
  `rating = goals*6.0 + assists*4.0 + key_passes*1.0 + successful_actions*0.05`.
  Every `TopPlayer` ships its own `rating_breakdown` so the number is
  auditable. "Successful action" is itself a documented, explainable rule
  (`is_successful_event` in `event_utils.py`) — fouls/offsides never count,
  own goals never count, the dataset's own accurate/not_accurate tag is
  respected where present, interceptions/clearances always count (matching
  the convention used by the `socceraction` library), duels follow their
  won/lost/neutral tag, and anything with no clear signal is *not* counted
  — the design favors under-counting over guessing.
- **Top players are selected per team, then merged.** The top 3 (by
  rating) from each side are combined and re-sorted, so a one-sided
  scoreline can't crowd the losing team's best performer out of the list
  entirely.
- **Possession is a documented proxy, not a measurement.** The dataset has
  no tracking data, so `possession_proxy_pct` is each team's share of the
  match's total pass attempts — labeled as a proxy throughout, not implied
  to be real ball-time.

### Modules

- `app/analytics/thresholds.py` — named, tunable constants: rating weights
  and the tactical-pattern / coaching-observation thresholds.
- `app/analytics/event_utils.py` — single-event classification helpers
  (`is_goal`, `is_scoring_event`, `is_own_goal`, `is_on_target`,
  `is_successful_event`, minute reconstruction, etc.), each documented with
  *why*, not just *what*.
- `app/analytics/models.py` — the Pydantic output contract that Phase 3
  and the API will depend on.
- `app/analytics/match_analyzer.py` — `MatchAnalyzer`, one private method
  per analytical building block (team stats, player ratings, key moments,
  tactical patterns, coaching observations).

### A real data-quality finding (own-goal tag splitting)

While building the key-moments timeline, testing surfaced a subtle bug:
own-goal events don't reliably carry both tag `101` ("goal") and `102`
("own_goal") on the *same* event. A real example from the public dataset
(via an open `socceraction` GitHub issue) shows the deflecting touch
tagged `102` alone, while the opposing goalkeeper's save-attempt event is
left with a stray `101` — which, read naively, would have credited that
goalkeeper with a goal he didn't score. See ambiguity #8 above for the
full explanation and the fix (`is_scoring_event` gates the goal tag on
the event also being a shot, since Wyscout's own glossary confirms a
genuine goal is always a Shot event except when it's an own goal).

### Validation performed in this sandbox

Ran `analyze()` against the Phase 1 fixture match and independently
recomputed every output field (team stats, player ratings, key moments,
tactical patterns, coaching observations) directly from the raw fixture
JSON to confirm an exact match — including `avg_event_x` and
`final_third_share_pct`, which were cross-checked programmatically after
a manual hand-count turned out to have missed an event. Separately
exercised the five branches the main fixture doesn't reach (own goal,
penalty scored, penalty missed, hit the post, counter-attack shot) with
synthetic events, including the real-world own-goal tag-splitting pattern
described above, which is exactly what caught the bug and confirmed the
fix.

## Phase 3 — Report Context Generation

`ContextBuilder.build(analysis)` compresses a Phase 2 `MatchAnalysis` into
a compact `MatchContext`: small enough to keep LLM inference cheap and
fast, while still carrying everything Phase 4's report-writing prompt
needs (match/score, per-team box score, top players, a key-moments
timeline, tactical patterns, coaching observations).

### Design

- **No raw event dumps, structurally.** `ContextBuilder` only ever
  receives a `MatchAnalysis` — it has no access to the events DataFrame at
  all, so this requirement can't be accidentally violated later.
- **Every dropped field is dropped on purpose.** `rating_breakdown` per
  player and `supporting_metric` per tactical pattern exist in Phase 2's
  output for *auditability* — so a human/QA process can check a number
  against the formula that produced it. The LLM doesn't need the formula,
  just the conclusion, which is already spelled out in the accompanying
  `text` — shipping the breakdown too would pay tokens twice for the same
  information. Similarly dropped: all numeric ids, `status`/`duration`,
  per-player total/successful action counts, and the three territory
  metrics on team stats (`avg_event_x`, `final_third_share_pct`,
  `high_pass_ratio_pct`) — these are *inputs* to the tactical-pattern
  rules, not outputs a report needs directly, since the pattern's `text`
  already states the conclusion in football terms. Full list of
  omissions is in the module docstring.
- **`possession_proxy_pct` is renamed `pass_share_pct` in the compact
  context.** It's genuinely a share-of-passes proxy, not measured
  ball-time — keeping the honest name here (rather than the more
  Gemini-friendly-sounding "possession_pct") reduces the chance the report
  later overstates it as a measured statistic.
- **The actual prompt payload is minified, not pretty-printed.**
  `build_json()` calls `model_dump_json(exclude_none=True)` with no
  indentation — every formatting character is a token. `exclude_none`
  also drops `went_to_extra_time` / `went_to_penalties` / `penalty_score`
  entirely for the (overwhelming majority of) matches that don't need
  them, rather than shipping `false`/`null` for every match.

### Validation performed in this sandbox

Built the context from the Phase 1 fixture match and confirmed every
field traces back correctly to its `MatchAnalysis` source (including the
`side → team name` lookup for `top_players`, which isn't directly on
`TopPlayer`). Separately constructed a synthetic extra-time/penalties
match to confirm those optional fields appear correctly when true and
disappear entirely when false. Measured the actual token-minimization
result against the fixture: the full `MatchAnalysis` JSON is 5,430
characters; the compact, minified `MatchContext` is 2,550 — a 53%
reduction on this small fixture (real matches, with their bulkier
`rating_breakdown` dicts and `supporting_metric` payloads per top player
and per pattern, should compress by at least as much).


## Phase 4 — LLM Integration (Groq + Llama 3.3 70B)

`GroqReportService.generate_report(context)` turns a Phase 3
`MatchContext` into a validated `MatchReport`:
`{summary, turning_points, standout_players, tactical_analysis,
coaching_insights}`.

### Provider swap: Gemini → Groq + Llama 3.3 70B

Originally specified as Gemini 2.5 Flash; swapped to **Groq**
(`https://api.groq.com`, OpenAI-compatible endpoint) running
**`llama-3.3-70b-versatile`** per explicit instruction. Verified via web
search before writing any code (same "don't assume" discipline as every
other phase):
- The model id is still active on Groq's free tier (1,000 requests/day)
  as of mid-2026 — it hasn't been deprecated or renamed.
- Groq gates its newer `json_schema` "Structured Outputs" enforcement to
  "supported models," and every worked example of it in Groq's own docs
  uses the `openai/gpt-oss-*` models, not `llama-3.3-70b-versatile` —
  there's no confirmed guarantee it's honored for this model, and Groq's
  community forum has reports of structured outputs being silently
  ignored even for a model that nominally supports it. The older,
  broadly-supported `json_object` mode (valid JSON syntax, not
  schema-validated) is used instead — the brief separately requires our
  own schema validation + retry logic on top regardless of provider
  guarantees, so this satisfies the requirement without leaning on an
  unconfirmed feature.
- Get a free key at `https://console.groq.com/keys`; set it as
  `GROQ_API_KEY`. Model id, timeout, retry budget, temperature, and seed
  are now all in `app/core/config.py` (`PLAYERNATION_GROQ_*` env vars) —
  nothing is hardcoded in `llm_service.py`.

### Reliability pipeline

1. JSON mode (`response_format={"type": "json_object"}`) + the exact
   schema spelled out in the system prompt.
2. Parse as JSON.
3. Validate against `MatchReport` (Pydantic) — catches wrong types or
   missing keys.
4. Lightweight content-quality checks Pydantic's type validation alone
   wouldn't catch (a syntactically valid empty list or blank string is
   not a usable report).
5. On any failure in 2-4, re-prompt with the previous output and the
   exact error, and retry (`Settings.groq_max_retries`, default 2 extra
   attempts). On a transport/network failure, back off (respecting
   `Retry-After` on a 429) and retry instead.
6. If every attempt fails, raise one normalized `ReportGenerationError`
   — the only exception type a caller (Phase 6's API layer) ever needs to
   handle. Network errors, malformed JSON, and schema-validation failures
   are all funneled into it; nothing propagates as a raw
   `JSONDecodeError`/`ValidationError`/`requests` exception.
7. `seed` is set (default 42, configurable) for Groq's best-effort
   deterministic sampling, and temperature is kept low (default 0.2) —
   "deterministic prompting where possible," per the brief.

### Anti-hallucination by construction

The system prompt explicitly instructs the model to use *only* the
players, teams, and numbers present in the supplied context and to never
invent one that isn't there. This is enforceable in spirit, not
guaranteed — Phase 5's evaluation framework is where this actually gets
*measured* (player/event coverage checks) rather than just asked for.

### Validation performed in this sandbox

This sandbox has no network access, so `GroqReportService` was tested
with `requests.post` mocked (the real `requests` library — not a shim —
*is* installed here, so this exercises the actual HTTP call shape, just
against a fake server). Confirmed: missing API key raises immediately
without any network call; a clean first response succeeds with
`attempts=1`; malformed JSON from the model triggers a retry that
re-prompts with the *exact* parse error and succeeds on the second
attempt; a syntactically-valid-but-empty `turning_points` list is caught
by the quality check and also triggers a successful retry; a transport
ConnectionError is retried and recovers; and when every attempt
genuinely fails, a single `ReportGenerationError` is raised (never a raw
exception) with the right attempt count attached. Separately confirmed,
via a call-time snapshot (a naive mock-inspection first suggested a false
positive here, caused by the mock recording a live reference to the
mutated message list rather than its state at call time — re-tested with
an explicit deep-copy snapshot to get the real answer), that the message
history sent to Groq grows correctly across retries: 2 messages on the
first attempt, 4 on the retry (the original exchange plus the bad output
and the correction request).

## Phase 5 — Evaluation Framework

`backend/evaluation/` runs the full Phase 1→4 pipeline across many
matches and scores every report against a set of deterministic checks,
producing an `EvaluationSummary` — the tool for answering "did my prompt
change actually help?"

### What it measures

- **Reliability** (`runner.py`): schema success rate (% of matches where
  `generate_report` didn't raise), first-attempt success rate (% of
  successes that needed *no* retry — a sharper signal than raw success
  rate for judging prompt quality), and average latency.
- **Content correctness** (`checks.py`):
  - **Winner correctness** — keyword/proximity heuristic on `summary`
    (a win-keyword near the winning team's name, or a lose-keyword near
    the losing team's, or a draw-keyword for a draw). Explicitly *not*
    semantic understanding — it's auditable and will misjudge phrasing
    outside its keyword list, by design (see the docstring).
  - **Major event coverage** — for each goal/own-goal/penalty/red-card,
    checks whether *that specific player's name* (not just a team name)
    appears in the report. This mattered: an earlier version matched on
    any name extracted from the moment, including team names — and since
    a team name appears in nearly every report regardless of content,
    every moment looked "covered" even when the actual player was never
    mentioned. Fixed by requiring the player name specifically, falling
    back to a team-name match only for the rare anonymous case.
  - **Top player coverage** — % of `context.top_players` named anywhere
    in the report.
  - **Missing sections** — re-implemented independently of
    `llm_service.py`'s internal quality gate on purpose, so it works as a
    standalone judge of any report, including ones from a future
    prompt/model swap that might not share that gate.
  - **Hallucination checks** — are both team names and the correct score
    present in `summary`; does every `standout_players` item reference a
    name we actually know about. Precision-first: it catches an invented
    *subject* but not a fabricated stat attached to a real player.
- **Output**: `report_writer.py` writes a JSON file (the diffable
  artifact) and a skimmable text summary with per-match detail, including
  *which* moments/players were missed and *which* standout-player items
  got flagged — not just an aggregate percentage.

### Usage

```
python -m evaluation.cli --matches 9000001,9000002,9000003
```
Run once before a prompt/analytics change, once after, diff the two JSON
files. One bad match (missing data, a Groq failure, anything unexpected)
is recorded as a failed `MatchEvaluation` and the batch keeps going —
deliberately, so one problem match can't block a benchmarking run.

### Validation performed in this sandbox

Since the check functions (`checks.py`) only ever operate on an
already-built `(MatchContext, MatchReport)` pair, they're fully testable
without any network access. Verified all 7 of `match_analyzer.py`'s
description templates extract the right player/team name; verified
winner correctness on a home win ("Alpha beat Beta"), the same result
phrased from the loser's side ("Beta lost to Alpha"), a draw, and a
vague summary with no win/lose keyword (correctly flagged wrong);
verified missing-sections detection on blank/empty fields; verified the
hallucination check flags an invented standout player. Caught the
major-event-coverage bug described above via my own test before it ever
shipped. Then tested `EvaluationRunner` with a mocked Groq response
across three match ids — two valid, one nonexistent — confirming the
batch finishes, the bad match is recorded as a clean failure without
aborting the run, Groq is only called for the two valid matches, and
every aggregate stat (schema success rate, coverage percentages, latency
average) is arithmetically correct against hand-traced expected values.
Also ran `evaluation.cli` end-to-end with a mocked Groq call, confirming
both the console summary and the JSON file are written correctly.

## Phase 6 — FastAPI Backend

`GET /matches` and `POST /generate-report`, run with:
```
uvicorn app.main:app --reload
```

### Architecture

- `app/api/` — the HTTP layer only: `schemas.py` (request/response
  contracts), `routes/matches.py` + `routes/reports.py` (thin route
  handlers), `dependencies.py` (DI providers), `error_handlers.py`
  (exception → HTTP response mapping), `middleware.py` (request logging).
- `app/services/` — the actual business logic: `MatchService`,
  `ReportService`. Routes only ever call a service method and either
  return the result or let an exception propagate — no analytics,
  context-building, LLM-calling, or caching logic lives in `app/api/`.
  This is what makes "business logic outside API routes" true in
  practice rather than just stated as a goal.
- `app/cache/report_cache.py` — `ReportCache` is a `Protocol`;
  `InMemoryReportCache` is the only implementation needed for a
  single-process deployment, but a Redis-backed one could drop in without
  touching `ReportService` at all.
- `app/core/logging_config.py` — structured (single-line JSON) logging,
  configured once at startup.

### Design decisions

- **Caching**: a generated report is cached indefinitely per `match_id`
  — the underlying historical match data never changes, so there's no
  TTL to get wrong. `POST /generate-report` accepts an optional
  `force_refresh: bool` to bypass the cache (e.g. after a prompt change),
  rather than needing a separate cache-invalidation endpoint.
- **Singletons via `lru_cache`**: the dataset loader, LLM service, and
  cache are all created once (`app/api/dependencies.py`) and reused
  across requests — recreating `DatasetLoader` per request would reload
  every JSON file from disk on every call, and a cache recreated per
  request wouldn't cache anything.
- **Error handling**: every exception type the pipeline can raise
  (`MatchNotFoundError` → 404, `DatasetFileNotFoundError` → 500,
  `ReportGenerationError` → 502, `RequestValidationError` → 422, anything
  else → 500) is mapped once in `error_handlers.py`. 5xx responses
  deliberately don't echo the internal error message to the client (a
  Groq failure detail could reference internal config) — the full detail
  is logged server-side, the client gets a clean, generic message.
- **The API reuses Phase 3/4 models directly** (`ContextMatch`,
  `MatchReport`) in `GenerateReportResponse` rather than redefining
  near-identical shapes, since they already are exactly what the response
  needs.

### Validation performed in this sandbox

Neither `fastapi` nor `starlette` are installed here, so — same approach
as every other phase's missing dependency — I wrote a minimal shim
(`FastAPI`, `APIRouter`, `Depends`, `Request`, `JSONResponse`,
`RequestValidationError`, `BaseHTTPMiddleware`) sufficient to import every
module and exercise it directly, without real ASGI/HTTP machinery. This
isn't a substitute for hitting the running server, but it did catch real
wiring bugs:

Confirmed via this shim: `app.main` imports cleanly with all 3 routes,
all 5 exception handlers, and the middleware correctly registered.
Called `GET /matches` and `POST /generate-report` as plain function
calls (resolving `Depends(...)` manually) and confirmed: correct response
shapes; a cache miss generates and caches; a *second call through the
actual route* (not just the service directly, to prove the singleton
dependency wiring works end to end) is served from cache without calling
Groq again; a nonexistent match raises `MatchNotFoundError`, and feeding
that into its registered handler produces a clean 404; feeding a
`ReportGenerationError` carrying a deliberately sensitive-looking message
into its handler produces a 502 whose body does *not* contain that
message (verified by assertion, not just inspection) — confirming the
"don't leak internal detail" design decision actually holds; a generic
unhandled exception produces a clean 500 the same way; `/health` returns
correctly. Also exercised `RequestLoggingMiddleware.dispatch` with a fake
`call_next`, confirming it logs and attaches an `X-Request-ID` header.

Before running this for real, install the dependencies (now including
`fastapi` and `uvicorn[standard]`) and run `uvicorn app.main:app --reload`
— that exercises the real ASGI/ HTTP layer (request parsing, response
serialization, actual middleware ordering) that the shim above cannot.

## Phase 7 — React Native App

A new `frontend/` Expo + TypeScript app, sibling to `backend/`. Two
screens — Match List and Match Report — wired to the Phase 6 API via
React Query, with one Zustand store for the one piece of state that's
genuinely client-only.

### Design: the brand color

The brand color (`#CDFC00`, a high-luminance lime) is used as an
**accent, never as text on a light background** — lime-on-white has
almost no contrast and is genuinely hard to read. The rules this app
follows (stated explicitly in `src/theme/index.ts`):
- Lime as a **fill** (buttons, badges, the score-header winner highlight,
  a thin card accent stripe), always paired with near-black text on top
  of it, never white.
- Reserved for **functional** moments, not sprayed everywhere: the score
  header colors the winning team's name/score in lime specifically so it
  tells you who won at a glance; every section card gets a small lime dot
  next to its heading as a consistent, restrained brand mark; turning
  points get lime timeline dots. Coaching-insight bullets and the
  standout-player star badge deliberately use plain ink/lime sparingly so
  the accent still feels intentional rather than decorative everywhere.
- Otherwise: white surfaces, near-black text, one muted gray for
  secondary text and borders. Minimal by design — one accent color, one
  ink color, one gray scale, no sprawling palette.

### Architecture

- `src/api/` — `types.ts` (mirrors the Phase 6 contract by hand),
  `client.ts` (fetch wrapper, consistent `ApiError`), `endpoints.ts`
  (typed request functions). No React/React Native imports here at all.
- `src/hooks/` — `useMatches`, `useMatchReport`, `useRegenerateReport`:
  all server state goes through React Query here. Screens never call
  `fetch` or the API functions directly.
- `src/store/useSearchStore.ts` — the *only* Zustand store. The
  match-list search text is the one piece of state in this app that's
  genuinely client/UI-only; everything else is server state and belongs
  to React Query. Adding more Zustand stores just to use it more would
  create a second source of truth for data React Query already owns, so
  this app deliberately doesn't.
- `src/components/` + `src/screens/` — presentation only. Screens read
  from hooks/store and render; they don't fetch, cache, or transform data
  themselves.
- `src/navigation/` — a typed `RootStackParamList` and the stack
  navigator; the report screen receives `homeTeam`/`awayTeam` as nav
  params so it can show a real header immediately while the report is
  still generating, instead of a blank screen.

### Screens

- **Match List**: search-as-you-type (filters client-side against the
  already-fetched list — no extra request per keystroke), an animated
  skeleton while loading, pull-to-refresh, and distinct error/empty
  states (not the same blank screen for both).
- **Match Report**: dark score-header hero card with the winner
  highlighted in lime; a "Regenerate" button (calls the backend's
  `force_refresh`) with its own loading/error state, kept independent
  of the main report query/error state; Summary, Turning Points
  (timeline), Standout Players (card row), Tactical Analysis, Coaching
  Insights, each in a consistent `SectionCard`. `turning_points` and
  `standout_players` are flat prose strings from the LLM (see Phase 4),
  not structured objects with their own minute/rating — the UI renders
  them as a sequential timeline/card row rather than pretending to have
  per-item metadata it doesn't actually have.

### Validation performed in this sandbox

Neither the npm registry nor the real `react-native`/`expo`/
`@react-navigation/*`/`@tanstack/react-query`/`zustand` packages are
reachable here (`npm ping` against the registry returns 403). Same
approach as every other phase's missing dependency: I hand-wrote minimal
ambient `.d.ts` shims for just the APIs this app actually uses, and ran
the real `tsc` (TypeScript 6.0.3, genuinely installed in this sandbox)
against all 23 source files with `strict: true`.

This caught real things, not just import errors:
- A genuine TypeScript 6.x compatibility issue worth fixing in the actual
  delivered `tsconfig.json`, not just my test harness: bare `baseUrl`
  usage is now deprecated and errors under TS 6 unless
  `"ignoreDeprecations": "6.0"` is set. Added to the real config.
- Confirmed the type-checker was actually checking things, not silently
  passing: deliberately introduced a bogus prop on `MatchCard`, watched
  `tsc` correctly reject it, then reverted and confirmed a clean pass.
- Two early shim gaps (missing `JSX.ElementChildrenAttribute`, missing
  the `fetch`/`process` globals RN and Expo provide natively) turned out
  to be gaps in my *shim*, not my app code — worth being honest about
  that distinction rather than just declaring victory at "zero errors."

What this validates: every prop passed to every component matches its
declared interface, the navigation param types are used consistently
across both screens, the API client/types/hooks compose without a type
mismatch anywhere in the chain. What it does *not* validate: actual
runtime rendering, styling/layout correctness, or real device behavior —
that needs `npx expo start` with the real dependencies installed, which
this sandbox can't do (no registry access). Before relying on this, run
it for real: `cd frontend && npm install && npm run typecheck` (should
still pass clean), then `npx expo start` with `backend/` running and
`EXPO_PUBLIC_API_BASE_URL` pointed at it.
