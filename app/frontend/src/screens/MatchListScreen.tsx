import { useMemo } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import type { MatchListItem } from '@/api/types';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { MatchCard } from '@/components/MatchCard';
import { MatchListSkeleton } from '@/components/MatchListSkeleton';
import { SearchBar } from '@/components/SearchBar';
import { useMatches } from '@/hooks/useMatches';
import type { RootStackParamList } from '@/navigation/types';
import { useSearchStore } from '@/store/useSearchStore';
import { colors, spacing, typography } from '@/theme';

type Navigation = NativeStackNavigationProp<RootStackParamList, 'MatchList'>;

export function MatchListScreen() {
  const navigation = useNavigation<Navigation>();
  const { data, isLoading, isError, error, refetch, isRefetching } = useMatches();
  const query = useSearchStore((s) => s.query);

  const filteredMatches = useMemo<MatchListItem[]>(() => {
    const matches = data?.matches ?? [];
    const needle = query.trim().toLowerCase();
    if (!needle) return matches;
    return matches.filter(
      (m) => m.home_team.toLowerCase().includes(needle) || m.away_team.toLowerCase().includes(needle)
    );
  }, [data, query]);

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.container}>
        <Text style={styles.title}>Matches</Text>
        <SearchBar />

        {isLoading ? (
          <MatchListSkeleton />
        ) : isError ? (
          <ErrorState
            message={error instanceof Error ? error.message : 'Could not load matches.'}
            onRetry={refetch}
          />
        ) : filteredMatches.length === 0 ? (
          <EmptyState message={query ? `No matches found for "${query}".` : 'No matches available yet.'} />
        ) : (
          <FlatList
            data={filteredMatches}
            keyExtractor={(item) => String(item.match_id)}
            renderItem={({ item }) => (
              <MatchCard
                match={item}
                onPress={() =>
                  navigation.navigate('MatchReport', {
                    matchId: item.match_id,
                    homeTeam: item.home_team,
                    awayTeam: item.away_team,
                  })
                }
              />
            )}
            refreshControl={
              <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.ink} />
            }
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.listContent}
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  container: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
  },
  title: {
    ...typography.title,
    marginBottom: spacing.lg,
  },
  listContent: {
    paddingBottom: spacing.xl,
  },
});
