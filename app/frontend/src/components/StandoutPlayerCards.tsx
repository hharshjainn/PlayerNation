import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

export function StandoutPlayerCards({ players }: { players: string[] }) {
  if (players.length === 0) {
    return <Text style={typography.bodyMuted}>No standout performers were highlighted for this match.</Text>;
  }

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {players.map((player, index) => (
        <View key={index} style={styles.card}>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>★</Text>
          </View>
          <Text style={styles.text}>{player}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    gap: spacing.md,
    paddingRight: spacing.md,
  },
  card: {
    width: 220,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.lg,
  },
  badge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  badgeText: {
    color: colors.ink,
    fontWeight: '700',
  },
  text: {
    ...typography.body,
  },
});
