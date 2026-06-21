import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '@/theme';

/**
 * `points` is a flat list of prose strings (see `MatchReport` in
 * `api/types.ts`) -- there's no per-item minute to anchor on, so this
 * renders as a sequential timeline (lime dot + connecting line) rather
 * than pretending to have timestamps it doesn't have.
 */
export function TurningPointsTimeline({ points }: { points: string[] }) {
  if (points.length === 0) {
    return <Text style={typography.bodyMuted}>No standout turning points were identified for this match.</Text>;
  }

  return (
    <View>
      {points.map((point, index) => (
        <View key={index} style={styles.row}>
          <View style={styles.markerColumn}>
            <View style={styles.dot} />
            {index < points.length - 1 ? <View style={styles.line} /> : null}
          </View>
          <Text style={styles.text}>{point}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
  },
  markerColumn: {
    alignItems: 'center',
    width: 20,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.brand,
    marginTop: 4,
  },
  line: {
    width: 2,
    flex: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
  },
  text: {
    ...typography.body,
    flex: 1,
    paddingBottom: spacing.lg,
    paddingLeft: spacing.sm,
  },
});
