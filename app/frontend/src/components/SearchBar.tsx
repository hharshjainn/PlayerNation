import { StyleSheet, TextInput, View } from 'react-native';

import { useSearchStore } from '@/store/useSearchStore';
import { colors, radius, spacing, typography } from '@/theme';

export function SearchBar() {
  const query = useSearchStore((s) => s.query);
  const setQuery = useSearchStore((s) => s.setQuery);

  return (
    <View style={styles.wrapper}>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search teams..."
        placeholderTextColor={colors.inkMuted}
        style={styles.input}
        autoCorrect={false}
        autoCapitalize="none"
        returnKeyType="search"
        clearButtonMode="while-editing"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.lg,
  },
  input: {
    ...typography.body,
    paddingVertical: spacing.md,
  },
});
