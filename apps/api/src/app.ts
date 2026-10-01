import Fastify from 'fastify';
import { healthStatusSchema } from '@trainia/shared';
import pkg from '../package.json' with { type: 'json' };
import type { Pool } from 'pg';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';
import { createAuthHook } from './plugins/auth.js';
import { requireAdmin } from './plugins/requireAdmin.js';
import type { DecodedIdToken } from './auth/types.js';

interface DbClient {
  pool: Pool;
  db: NodePgDatabase;
}

interface Auth {
  verifyIdToken(token: string): Promise<DecodedIdToken>;
}

interface BuildAppOptions {
  db: DbClient;
  auth: Auth;
  adminEmails: string[];
}

export function buildApp({ db, auth, adminEmails }: BuildAppOptions) {
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

  // Auth routes with hook
  const authHook = createAuthHook({ auth, db: db.db, adminEmails });
  
  app.register((scope, opts, done) => {
    scope.addHook('onRequest', authHook);
    
    scope.get('/me', async (request) => {
      return {
        id: request.user.id,
        uid: request.user.uid,
        email: request.user.email,
        role: request.user.role,
      };
    });
    
    done();
  });

  // Admin routes with auth + requireAdmin hooks
  app.register((scope, opts, done) => {
    scope.addHook('onRequest', authHook);
    scope.addHook('preHandler', requireAdmin);
    
    scope.get('/admin/ping', async () => {
      return { ok: true };
    });
    
    done();
  });

  return app;
}
