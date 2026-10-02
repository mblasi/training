import { View, Text, Button } from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../src/auth/AuthContext';
import { parseHealthResponse } from '../src/health';

export default function Index() {
  const { user, signOut } = useAuth();
  const router = useRouter();

  if (!user) {
    router.replace('/login');
    return null;
  }

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
      <Text>User: {user.email}</Text>
      <Button title="Logout" onPress={() => signOut()} />
    </View>
  );
}
