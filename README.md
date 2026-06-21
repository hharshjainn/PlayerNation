# PlayerNation Match Report Generator

Generates LLM-written football match reports from the Wyscout Soccer
Match Event Dataset (FIFA World Cup 2018). A FastAPI backend runs an
analytics pipeline over raw match events and calls an LLM (Groq +
Llama 3.3 70B) to produce a structured report; a React Native (Expo) app
displays it.

> Detailed phase-by-phase design rationale, ambiguities resolved, and bugs
> This README covers setup, running, architecture, and LLM config.

## Architecture

```
Raw Wyscout JSON
      │
      ▼
DatasetLoader            backend/app/data/            typed access to teams/players/matches/events
      │
      ▼
MatchAnalyzer             backend/app/analytics/        deterministic stats, ratings, key moments,
      │                                                  tactical patterns, coaching observations
      ▼
ContextBuilder            backend/app/context/          compresses analysis into a token-minimized,
      │                                                  LLM-ready JSON payload
      ▼
GroqReportService          backend/app/llm/              calls Groq (Llama 3.3 70B), validates the
      │                                                   response against a schema, retries on failure
      ▼
ReportService + cache      backend/app/services/,        orchestrates the above behind the API,
                            backend/app/cache/             caches generated reports per match
      │
      ▼
FastAPI (GET /matches,      backend/app/api/, app/main.py
 POST /generate-report)
      │
      ▼
React Native app           frontend/                      Match List + Match Report screens
```

`backend/evaluation/` runs the whole pipeline across many matches and
scores each report (winner correctness, event/player coverage,
hallucination checks, latency, schema success rate) — useful for
benchmarking a prompt or analytics change.

### Key architecture decisions

- **Deterministic analytics, not a black box.** Every stat, player
  rating, and tactical pattern is a documented formula or threshold rule
  (`backend/app/analytics/`), not a model — every number is traceable to
  a count or a named constant.
- **Official score from match metadata, not re-derived from event tags.**
  Wyscout's own-goal tagging is genuinely ambiguous (see
  `docs/PHASE_NOTES.md` ambiguities #7–8); the scoreline always comes from
  the dataset's own `teamsData.score`.
- **Token-minimized LLM context.** `ContextBuilder` strips anything the
  LLM doesn't need (audit-only breakdowns, numeric ids, raw inputs to
  already-computed conclusions) — roughly a 50%+ size reduction vs. the
  full analytics output.
- **Reliability pipeline around the LLM call**, not just a single API
  call: JSON mode → parse → schema validation → content-quality checks →
  retry with the exact error fed back to the model → one normalized
  exception on exhaustion. The API layer never sees a raw parsing or
  network exception.
- **Business logic lives in `app/services/`, not in API routes.** Routes
  in `app/api/routes/` only call a service method and return the result;
  caching, error mapping, and orchestration are centralized, not
  scattered across endpoints.
- **Caching is indefinite per match**, since the underlying historical
  match data never changes — no TTL to get wrong. `force_refresh` on the
  report endpoint bypasses it explicitly (e.g. after a prompt change).
- **Frontend state split**: server state (matches, reports) goes through
  React Query; Zustand holds only the one piece of genuinely client-only
  state (search text) — not duplicated as a second source of truth.

## Project structure

```
playernation/
├── backend/
│   ├── app/
│   │   ├── data/          Phase 1 — dataset loading, Pydantic models
│   │   ├── analytics/     Phase 2 — MatchAnalyzer
│   │   ├── context/       Phase 3 — ContextBuilder
│   │   ├── llm/           Phase 4 — GroqReportService, report schema
│   │   ├── services/      Phase 6 — business logic (MatchService, ReportService)
│   │   ├── cache/         Phase 6 — report cache
│   │   ├── api/           Phase 6 — routes, schemas, error handlers, middleware
│   │   ├── core/          config + structured logging
│   │   └── main.py        FastAPI app
│   ├── evaluation/        Phase 5 — evaluation framework + CLI
│   ├── data/
│   │   ├── raw/           put the real dataset files here
│   │   └── fixtures/      small hand-written fixture for offline testing
│   ├── scripts/explore_dataset.py
│   └── requirements.txt
├── frontend/               Phase 7 — Expo + React Native app
│   ├── src/{api,hooks,store,navigation,components,screens,theme}
│   ├── App.tsx, app.json, eas.json
│   └── package.json
└── docs/PHASE_NOTES.md     detailed design log
```

## Setup


## Backend Setup

### Prerequisites

- Python 3.11+
- A Groq API key — free at [console.groq.com/keys](https://console.groq.com/keys)

### 1. Create and activate a virtual environment

```bash
cd app/backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and fill in your values:

```bash
cp app/.env.example app/.env
```

Edit `app/.env`:

```env
GROQ_API_KEY=gsk_your_key_here
PLAYERNATION_RAW_DATA_DIR=data/fixtures
PLAYERNATION_COMPETITION=World_Cup
```

See [LLM Configuration](#llm-configuration-groq) for the full list of LLM-related variables.

### 4. Run the server

```bash
# from app/backend/
uvicorn app.main:app --reload
```

The API is now live at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the interactive Swagger UI.

---

## Frontend Setup

### Prerequisites

- Node.js 18+
- Expo CLI: `npm install -g expo-cli`

### 1. Install dependencies

```bash
cd app/frontend
npm install
```

### 2. Point at the backend

The frontend reads the backend URL from the `EXPO_PUBLIC_API_BASE_URL` environment variable. For local development:

```env
# app/.env  (or app/frontend/.env)
EXPO_PUBLIC_API_BASE_URL=http://192.168.0.x:8000
```

Replace `192.168.0.x` with your machine's local IP address (not `localhost` — the phone can't reach your laptop's localhost). On Windows, find it with `ipconfig`; on macOS/Linux with `ifconfig`.

### 3. Start the dev server

```bash
expo start
```

Scan the QR code with the Expo Go app on your phone, or press `a` to launch an Android emulator.

---

Get the dataset:
- **Quick test, no download needed**: a small fixture ships at
  `backend/data/fixtures/` and works out of the box (set
  `PLAYERNATION_RAW_DATA_DIR=data/fixtures`).
- **Real data**: download `teams.json`, `players.json`,
  `matches_World_Cup.json`, `events_World_Cup.json` from
  [koenvo/wyscout-soccer-match-event-dataset](https://github.com/koenvo/wyscout-soccer-match-event-dataset)
  and place them in `backend/data/raw/` (the default location).

### Building an installable APK
```bash
cd frontend
npm install -g eas-cli
eas login            # free account at expo.dev
eas build:configure
eas build --platform android --profile preview
```
Produces a real `.apk` (the `preview` profile in `eas.json` is configured
for direct install, not the Play-Store-only `.aab` format) with a
download link/QR code once the cloud build finishes. The API URL is baked
in at build time from `.env` — make sure it's set correctly before
building, and note the built app will only reach a backend that's
actually reachable from wherever the phone is (same Wi-Fi as your
machine, unless you deploy the backend somewhere public).

## LLM Configuration (Groq)

All LLM settings are environment-driven. Set them in `app/.env` for local development, or as environment variables on your hosting platform.

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Your Groq API key. Get one free at [console.groq.com/keys](https://console.groq.com/keys). |
| `PLAYERNATION_GROQ_MODEL` | `llama-3.3-70b-versatile` | Any Groq-supported model ID. `llama-3.3-70b-versatile` is on the free tier (1,000 requests/day). |
| `PLAYERNATION_GROQ_TIMEOUT_SECONDS` | `30.0` | Per-request HTTP timeout in seconds. |
| `PLAYERNATION_GROQ_MAX_RETRIES` | `2` | Number of additional attempts after the first failure (schema or network). |
| `PLAYERNATION_GROQ_TEMPERATURE` | `0.2` | Low temperature for consistent, deterministic-ish reports. Raise toward `1.0` for more varied output. |
| `PLAYERNATION_GROQ_SEED` | `42` | Groq best-effort seed for reproducibility. Set to empty to disable. |

## API Reference

### `GET /health`

Returns `{"status": "ok"}`. Use this to verify the server is up.

### `GET /matches`

Returns a list of all available matches from the dataset.

**Response:**
```json
{
  "matches": [
    {
      "match_id": 2057954,
      "home_team": "France",
      "away_team": "Croatia",
      "date": "2018-07-15"
    }
  ]
}
```

### `POST /generate-report`

Generates (or returns a cached) LLM report for a match.

**Request body:**
```json
{
  "match_id": 2057954,
  "force_refresh": false
}
```

Set `force_refresh: true` to bypass the cache and re-call the LLM.

**Response:**
```json
{
  "match": { "label": "France - Croatia", "home_score": 4, "away_score": 2, ... },
  "report": {
    "summary": "...",
    "turning_points": ["...", "..."],
    "standout_players": ["...", "..."],
    "tactical_analysis": "...",
    "coaching_insights": ["...", "..."]
  },
  "cached": false,
  "model": "llama-3.3-70b-versatile",
  "attempts": 1,
  "latency_ms": 1823.4
}
```

---

## Evaluation Framework

The `evaluation/` module lets you benchmark report quality across multiple matches in one run. It tracks schema success rate, first-attempt success rate, LLM latency, key-event coverage, player coverage, and winner correctness.

```bash
# from app/backend/
python -m evaluation.cli --matches 5
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--matches N` | `5` | Number of matches to evaluate |
| `--match-ids 123 456` | — | Evaluate specific match IDs |
| `--output report.json` | — | Save full results to a JSON file |

The runner is fault-tolerant — a failed match records an error and the batch continues. This makes it safe to run over the full 64-match World Cup dataset when iterating on the prompt.

---

## Deployment

### Backend — Railway (recommended for demos)

Railway's free tier ($5/month credit) keeps the server always on with no spin-down.

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Set **Root Directory** to `app/backend`
4. Under the **Variables** tab, add:
   ```
   GROQ_API_KEY=gsk_your_key_here
   PLAYERNATION_COMPETITION=World_Cup
   ```
5. Under **Settings → Deploy**, set the start command:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
6. Under **Settings → Networking**, click **Generate Domain**

### Mobile App — EAS Build (APK)

```bash
npm install -g eas-cli
eas login

# store the backend URL as a build secret
eas secret:create --scope project --name EXPO_PUBLIC_API_BASE_URL \
  --value "https://your-app.up.railway.app"

# build the APK
cd app/frontend
eas build --platform android --profile preview
```

The build runs in Expo's cloud (no Android Studio needed). When complete, EAS provides a direct download link for the `.apk` that can be shared with anyone.
