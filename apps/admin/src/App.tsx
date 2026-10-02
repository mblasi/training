import type { HealthStatus } from '@trainia/shared';
import { useAuth } from './auth/AuthContext';
import Login from './pages/Login';

interface AppProps {
  health?: HealthStatus;
}

export default function App({ health }: AppProps) {
  const { role } = useAuth();

  if (role !== 'admin') {
    return <Login />;
  }

  return (
    <div>
      <h1>Trainia</h1>
      {health && <p>Status: {health.status}</p>}
    </div>
  );
}
