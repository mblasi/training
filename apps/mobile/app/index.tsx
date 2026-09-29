import { View, Text } from 'react-native';
import type { HealthStatus } from '@trainia/shared';

export default function Index() {
  const health: HealthStatus = {
    status: 'ok',
    version: '0.1.0',
    timestamp: new Date().toISOString(),
  };

  return (
    <View>
      <Text>Trainia</Text>
      <Text>Status: {health.status}</Text>
    </View>
  );
}
