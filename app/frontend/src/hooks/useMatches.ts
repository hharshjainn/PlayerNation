import { useQuery } from '@tanstack/react-query';

import { fetchMatches } from '@/api/endpoints';

export function useMatches() {
  return useQuery({
    queryKey: ['matches'],
    queryFn: fetchMatches,
    staleTime: 5 * 60 * 1000, // the match list is historical data; 5 minutes avoids refetching on every screen focus without pretending it's static forever
  });
}
