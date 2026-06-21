import { StyleSheet, Text, View } from 'react-native';

import type { ContextMatch } from '@/api/types';
import { colors, radius, spacing, typography } from '@/theme';

/**
 * The score header is the one place the brand color is used functionally
 * rather than just decoratively: the winning team's name and score are
 * lime, the rest of the card is white-on-near-black. That's a deliberate
 * choice -- it tells you who won at a glance, which is exactly what a
 * score header is for, rather than coloring things arbitrarily.
 */
export function ScoreHeader({ match }: { match: ContextMatch }) {
  const homeWin = match.result === 'home_win';
  const awayWin = match.result === 'away_win';

  const statusLabel = match.went_to_penalties
    ? `FT (Pens ${match.penalty_score ?? ''})`
    : match.went_to_extra_time
      ? 'FT (AET)'
      : 'FT';

  const metaLine = [match.venue, match.date].filter(Boolean).join(' · ');

  return (
    <View style={styles.card}>
      <Text style={styles.status}>{statusLabel}</Text>
      <View style={styles.row}>
        <Text style={[styles.team, homeWin && styles.teamWinner]} numberOfLines={2}>
          {match.home_team}
        </Text>
        <View style={styles.scoreRow}>
          <Text style={[styles.score, homeWin && styles.scoreWinner]}>{match.home_score}</Text>
          <Text style={styles.dash}>-</Text>
          <Text style={[styles.score, awayWin && styles.scoreWinner]}>{match.away_score}</Text>
        </View>
        <Text style={[styles.team, awayWin && styles.teamWinner]} numberOfLines={2}>
          {match.away_team}
        </Text>
      </View>
      {metaLine ? <Text style={styles.meta}>{metaLine}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.ink,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  status: {
    ...typography.label,
    color: colors.brand,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    width: '100%',
  },
  team: {
    ...typography.body,
    color: colors.white,
    fontWeight: '700',
    flex: 1,
    textAlign: 'center',
  },
  teamWinner: {
    color: colors.brand,
  },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  score: {
    ...typography.score,
    color: colors.white,
  },
  scoreWinner: {
    color: colors.brand,
  },
  dash: {
    ...typography.score,
    color: colors.inkMuted,
  },
  meta: {
    ...typography.bodyMuted,
    color: colors.inkMuted,
  },
});
