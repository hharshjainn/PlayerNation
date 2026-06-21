import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { BulletList } from '@/components/BulletList';
import { ErrorState } from '@/components/ErrorState';
import { ScoreHeader } from '@/components/ScoreHeader';
import { SectionCard } from '@/components/SectionCard';
import { StandoutPlayerCards } from '@/components/StandoutPlayerCards';
import { TurningPointsTimeline } from '@/components/TurningPointsTimeline';
import { useMatchReport, useRegenerateReport } from '@/hooks/useMatchReport';
import type { RootStackParamList } from '@/navigation/types';
import { colors, radius, spacing, typography } from '@/theme';

type Props = NativeStackScreenProps<RootStackParamList, 'MatchReport'>;

export function MatchReportScreen({ route }: Props) {
  const { matchId, homeTeam, awayTeam } = route.params;
  const { data, isLoading, isError, error, refetch } = useMatchReport(matchId);
  const regenerate = useRegenerateReport(matchId);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.ink} />
          <Text style={styles.loadingTitle}>
            {homeTeam} vs {awayTeam}
          </Text>
          <Text style={styles.loadingSubtitle}>
            Generating the match report -- this calls an LLM and can take a few seconds.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (isError || !data) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <ErrorState
          message={error instanceof Error ? error.message : 'Could not generate the report.'}
          onRetry={refetch}
        />
      </SafeAreaView>
    );
  }

  const { match, report, cached } = data;

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
        <ScoreHeader match={match} />

        <View style={styles.metaRow}>
          <Text style={styles.metaText}>{cached ? 'Cached report' : 'Freshly generated'}</Text>
          <Pressable
            onPress={() => regenerate.mutate()}
            disabled={regenerate.isPending}
            style={({ pressed }) => [styles.regenerateButton, pressed && styles.regenerateButtonPressed]}
          >
            <Text style={styles.regenerateText}>{regenerate.isPending ? 'Regenerating...' : 'Regenerate'}</Text>
          </Pressable>
        </View>

        {regenerate.isError ? (
          <Text style={styles.regenerateError}>
            {regenerate.error instanceof Error ? regenerate.error.message : 'Could not regenerate the report.'}
          </Text>
        ) : null}

        <SectionCard title="Summary">
          <Text style={typography.body}>{report.summary}</Text>
        </SectionCard>

        <SectionCard title="Turning Points">
          <TurningPointsTimeline points={report.turning_points} />
        </SectionCard>

        <SectionCard title="Standout Players">
          <StandoutPlayerCards players={report.standout_players} />
        </SectionCard>

        <SectionCard title="Tactical Analysis">
          <Text style={typography.body}>{report.tactical_analysis}</Text>
        </SectionCard>

        <SectionCard title="Coaching Insights">
          <BulletList items={report.coaching_insights} />
        </SectionCard>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  container: {
    padding: spacing.lg,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  loadingTitle: {
    ...typography.heading,
    marginTop: spacing.md,
  },
  loadingSubtitle: {
    ...typography.bodyMuted,
    textAlign: 'center',
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  metaText: {
    ...typography.bodyMuted,
  },
  regenerateButton: {
    borderWidth: 1,
    borderColor: colors.brand,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
  },
  regenerateButtonPressed: {
    backgroundColor: colors.surfaceAlt,
  },
  regenerateText: {
    ...typography.bodyMuted,
    fontWeight: '700',
    color: colors.ink,
  },
  regenerateError: {
    ...typography.bodyMuted,
    color: colors.danger,
    marginBottom: spacing.md,
  },
});
