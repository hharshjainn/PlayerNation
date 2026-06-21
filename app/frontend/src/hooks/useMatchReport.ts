import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { generateReport } from '@/api/endpoints';
import type { GenerateReportResponse } from '@/api/types';

export function reportQueryKey(matchId: number) {
  return ['report', matchId] as const;
}

/**
 * Fetches (and, via the backend's own cache, generates) the report for a
 * match. Modeled as a query, not a mutation -- from the UI's point of
 * view "get the report for this match" is read-like and cacheable, even
 * though it's a POST under the hood; React Query doesn't care about HTTP
 * verbs, only about the queryKey.
 */
export function useMatchReport(matchId: number) {
  return useQuery({
    queryKey: reportQueryKey(matchId),
    queryFn: () => generateReport(matchId, false),
    staleTime: Infinity, // a report for historical match data never goes stale on its own
    retry: false, // the backend already retries transient LLM failures internally; retrying here would just re-trigger an expensive generation
  });
}

/**
 * Explicit user-triggered regeneration (force_refresh=true) -- modeled as
 * a mutation since it's a deliberate action with a side effect, not a
 * passive read. On success, it overwrites the cached query data for this
 * match so the screen updates without a second round-trip.
 */
export function useRegenerateReport(matchId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => generateReport(matchId, true),
    onSuccess: (data: GenerateReportResponse) => {
      queryClient.setQueryData(reportQueryKey(matchId), data);
    },
  });
}
