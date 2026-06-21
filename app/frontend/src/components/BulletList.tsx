import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '@/theme';

export function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <Text style={typography.bodyMuted}>No coaching insights were generated for this match.</Text>;
  }

  return (
    <View>
      {items.map((item, index) => (
        <View key={index} style={styles.row}>
          <View style={styles.bullet} />
          <Text style={styles.text}>{item}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    marginBottom: spacing.sm,
  },
  bullet: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.ink,
    marginTop: 8,
    marginRight: spacing.sm,
  },
  text: {
    ...typography.body,
    flex: 1,
  },
});
