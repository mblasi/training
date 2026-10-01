import { buildApp } from './app.js';
import { requireDatabaseUrl } from './db/env.js';
import { createDb } from './db/client.js';
import { requireFirebaseProjectId } from './auth/env.js';
import { initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';

const databaseUrl = requireDatabaseUrl(process.env);
const { pool, db } = createDb(databaseUrl);

const projectId = requireFirebaseProjectId(process.env);
initializeApp({ projectId });

const auth = {
  verifyIdToken: (token: string) => getAuth().verifyIdToken(token),
};

const adminEmails = (process.env.ADMIN_EMAILS ?? '')
  .split(',')
  .map(e => e.trim())
  .filter(Boolean);

const app = buildApp({ db: { pool, db }, auth, adminEmails });

const start = async () => {
  try {
    const port = parseInt(process.env.PORT || '3000', 10);
    await app.listen({ port, host: '0.0.0.0' });
    console.log(`Server listening on http://0.0.0.0:${port}`);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
};

start();
