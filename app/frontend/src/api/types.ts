/**
 * TypeScript types mirroring the Phase 6 API contract
 * (`backend/app/api/schemas.py`) exactly -- kept in sync by hand since the
 * two codebases don't share a schema generator yet. If the backend
 * contract changes, this is the one file to update on the frontend.
 */

export type Side = 'home' | 'away';
export type MatchResult = 'home_win' | 'away_win' | 'draw';

export interface MatchListItem {
  match_id: number;
  home_team: string;
  away_team: string;
  date: string | null;
}

export interface MatchListResponse {
  matches: MatchListItem[];
}

export interface ContextMatch {
  label: string;
  date: string | null;
  venue: string | null;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  result: MatchResult;
  went_to_extra_time?: boolean | null;
  went_to_penalties?: boolean | null;
  penalty_score?: string | null;
}

/**
 * The LLM-generated report. `turning_points` and `standout_players` are
 * flat prose strings, not structured objects with their own minute/rating
 * metadata -- that's the real shape the backend returns (see Phase 4's
 * `MatchReport`), so the UI renders them as a sequential timeline /
 * card list rather than pretending to have per-item structured data it
 * doesn't actually have.
 */
export interface MatchReport {
  summary: string;
  turning_points: string[];
  standout_players: string[];
  tactical_analysis: string;
  coaching_insights: string[];
}

export interface GenerateReportResponse {
  match: ContextMatch;
  report: MatchReport;
  cached: boolean;
  model: string;
  attempts: number;
  latency_ms: number;
}

export interface ApiErrorBody {
  error: string;
  detail: string;
}
