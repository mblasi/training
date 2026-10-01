import type { FastifyRequest, FastifyReply } from 'fastify';
import { verifyToken } from '../auth/verifyToken.js';
import { upsertUser } from '../auth/upsertUser.js';
import type { Database } from '../db/index.js';
import type { DecodedIdToken } from '../auth/types.js';

interface Auth {
  verifyIdToken(token: string): Promise<DecodedIdToken>;
}

interface CreateAuthHookOptions {
  auth: Auth;
  db: Database;
  adminEmails: string[];
}

export function createAuthHook({ auth, db, adminEmails }: CreateAuthHookOptions) {
  return async (request: FastifyRequest, reply: FastifyReply) => {
    const authHeader = request.headers.authorization;
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return reply.code(401).send({ error: 'Unauthorized' });
    }
    
    const token = authHeader.substring(7);
    
    try {
      const decoded = await verifyToken(auth, token);
      
      if (!decoded.email || decoded.email_verified === undefined) {
        return reply.code(401).send({ error: 'Unauthorized' });
      }
      
      const user = await upsertUser(db, {
        uid: decoded.uid,
        email: decoded.email,
        email_verified: decoded.email_verified,
      }, adminEmails);
      request.user = user;
    } catch {
      return reply.code(401).send({ error: 'Unauthorized' });
    }
  };
}
