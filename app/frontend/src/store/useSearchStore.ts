import { create } from 'zustand';

interface SearchState {
  query: string;
  setQuery: (query: string) => void;
  clear: () => void;
}

/**
 * The only piece of state in this app that's genuinely client/UI-only:
 * the match-list search text. Everything else (the match list, generated
 * reports) is server state and belongs to React Query, not here -- see
 * the README's "state management split" note for why this app doesn't
 * reach for Zustand more than this one store. Forcing more state in here
 * "to use Zustand more" would just create a second source of truth for
 * data React Query already owns.
 */
export const useSearchStore = create<SearchState>((set) => ({
  query: '',
  setQuery: (query) => set({ query }),
  clear: () => set({ query: '' }),
}));
