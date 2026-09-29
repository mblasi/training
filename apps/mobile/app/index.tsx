import { View, Text } from 'react-native';
import { parseHealthResponse } from '../src/health';

export default function Index() {
  // Parse a sample/placeholder payload
  const health = parseHealthResponse({
    status: 'ok',
    version: '0.1.0',
    timestamp: new Date().toISOString(),
  });

  return (
    <View>
      <Text>Trainia</Text>
      <Text>Status: {health.status}</Text>
    </View>
  );
}
