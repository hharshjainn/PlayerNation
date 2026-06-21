import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { MatchListItem } from '@/api/types';
import { colors, radius, spacing, typography } from '@/theme';

interface MatchCardProps {
  match: MatchListItem;
  onPress: () => void;
}

export function MatchCard({ match, onPress }: MatchCardProps) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}>
      {/* A thin brand-colored stripe on every card -- a deliberate, restrained
          use of the accent color so it reads as a consistent brand mark
          rather than a one-off decoration. */}
      <View style={styles.stripe} />
      <View style={styles.content}>
        <Text style={styles.matchup} numberOfLines={1}>
          {match.home_team} <Text style={styles.vs}>vs</Text> {match.away_team}
        </Text>
        {match.date ? <Text style={styles.date}>{match.date}</Text> : null}
      </View>
      <Text style={styles.chevron}>›</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
    overflow: 'hidden',
  },
  cardPressed: {
    backgroundColor: colors.surfaceAlt,
  },
  stripe: {
    width: 4,
    alignSelf: 'stretch',
    backgroundColor: colors.brand,
  },
  content: {
    flex: 1,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
  },
  matchup: {
    ...typography.body,
    fontWeight: '700',
  },
  vs: {
    ...typography.bodyMuted,
    fontWeight: '400',
  },
  date: {
    ...typography.bodyMuted,
    marginTop: 2,
  },
  chevron: {
    ...typography.bodyMuted,
    fontSize: 22,
    paddingHorizontal: spacing.md,
  },
});
