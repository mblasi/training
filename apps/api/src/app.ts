import Fastify from 'fastify';
import type { HealthStatus } from '@trainia/shared';

export function buildApp() {
  const app = Fastify();

  app.get('/health', async () => {
    const response: HealthStatus = {
      status: 'ok',
      version: '0.1.0',
      timestamp: new Date().toISOString(),
    };
    return response;
  });

  return app;
}
