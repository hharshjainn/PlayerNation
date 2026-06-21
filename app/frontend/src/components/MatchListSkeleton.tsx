import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';

import { colors, radius, spacing } from '@/theme';

function useShimmer() {
  const opacity = useRef(new Animated.Value(0.5)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 650, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.5, duration: 650, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return opacity;
}

/** Responsive loading state for the match list -- a few pulsing skeleton
 * cards shaped like `MatchCard`, rather than a bare spinner. */
export function MatchListSkeleton({ count = 6 }: { count?: number }) {
  const opacity = useShimmer();

  return (
    <View>
      {Array.from({ length: count }).map((_, index) => (
        <Animated.View key={index} style={[styles.card, { opacity }]}>
          <View style={styles.stripe} />
          <View style={styles.content}>
            <View style={styles.lineWide} />
            <View style={styles.lineNarrow} />
          </View>
        </Animated.View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
    overflow: 'hidden',
  },
  stripe: {
    width: 4,
    backgroundColor: colors.border,
  },
  content: {
    flex: 1,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  lineWide: {
    height: 14,
    borderRadius: 4,
    backgroundColor: colors.surfaceAlt,
    width: '70%',
  },
  lineNarrow: {
    height: 12,
    borderRadius: 4,
    backgroundColor: colors.surfaceAlt,
    width: '40%',
  },
});
