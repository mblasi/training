import { buildApp } from './app.js';
import { requireDatabaseUrl } from './db/env.js';
import { createDb } from './db/client.js';

const databaseUrl = requireDatabaseUrl(process.env);
const { pool, db } = createDb(databaseUrl);

const app = buildApp({ db: { pool, db } });

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
