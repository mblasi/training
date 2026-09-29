import Fastify from 'fastify';
import { healthStatusSchema } from '@trainia/shared';
import pkg from '../package.json' with { type: 'json' };

export function buildApp() {
  const app = Fastify();

  app.get('/health', async () => {
    const response = {
      status: 'ok' as const,
      version: pkg.version,
      timestamp: new Date().toISOString(),
    };
    // Validate with Zod before returning
    return healthStatusSchema.parse(response);
  });

  return app;
}
