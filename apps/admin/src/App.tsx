import type { HealthStatus } from '@trainia/shared';

interface AppProps {
  health?: HealthStatus;
}

export default function App({ health }: AppProps) {
  return (
    <div>
      <h1>Trainia</h1>
      {health && <p>Status: {health.status}</p>}
    </div>
  );
}
