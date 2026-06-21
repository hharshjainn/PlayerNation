import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { MatchListScreen } from '@/screens/MatchListScreen';
import { MatchReportScreen } from '@/screens/MatchReportScreen';
import { colors } from '@/theme';

import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  return (
    <Stack.Navigator
      initialRouteName="MatchList"
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerShadowVisible: false,
        headerTitleStyle: { color: colors.ink, fontWeight: '700' },
        headerTintColor: colors.ink,
        contentStyle: { backgroundColor: colors.surface },
      }}
    >
      <Stack.Screen name="MatchList" component={MatchListScreen} options={{ title: 'PlayerNation' }} />
      <Stack.Screen name="MatchReport" component={MatchReportScreen} options={{ title: 'Match Report' }} />
    </Stack.Navigator>
  );
}
