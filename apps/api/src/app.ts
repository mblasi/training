import Fastify from 'fastify';
import { healthStatusSchema } from '@trainia/shared';
import pkg from '../package.json' with { type: 'json' };
import type { Pool } from 'pg';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

interface DbClient {
  pool: Pool;
  db: NodePgDatabase;
}

interface BuildAppOptions {
  db: DbClient;
}

export function buildApp({ db }: BuildAppOptions) {
  const app = Fastify();

  app.get('/health', async (request, reply) => {
    const timeoutMs = parseInt(process.env.DB_HEALTH_TIMEOUT_MS || '2000', 10);
    
    let dbStatus: 'ok' | 'error' = 'error';
    
    try {
      await Promise.race([
        db.pool.query('SELECT 1'),
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('DB health check timeout')), timeoutMs)
        ),
      ]);
      dbStatus = 'ok';
    } catch {
      dbStatus = 'error';
    }
    
    const status = dbStatus === 'ok' ? 'ok' : 'degraded';
    const statusCode = dbStatus === 'ok' ? 200 : 503;
    
    const response = {
      status,
      db: dbStatus,
      version: pkg.version,
      timestamp: new Date().toISOString(),
    };
    
    reply.code(statusCode);
    return healthStatusSchema.parse(response);
  });

  return app;
}
