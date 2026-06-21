import { apiClient } from './client';
import type { GenerateReportResponse, MatchListResponse } from './types';

export function fetchMatches(): Promise<MatchListResponse> {
  return apiClient.get<MatchListResponse>('/matches');
}

export function generateReport(matchId: number, forceRefresh = false): Promise<GenerateReportResponse> {
  return apiClient.post<GenerateReportResponse>('/generate-report', {
    match_id: matchId,
    force_refresh: forceRefresh,
  });
}
