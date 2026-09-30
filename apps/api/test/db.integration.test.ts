import { describe, test, expect, beforeAll, afterAll } from 'vitest';
import { createDb } from '../src/db/client.js';
import { runSeed } from '../src/db/seed.js';

describe('Database integration', () => {
  let db: ReturnType<typeof createDb> | undefined;

  beforeAll(() => {
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl) {
      throw new Error(
        'DATABASE_URL not set. Integration tests require a Postgres database.\n' +
        'In CI, this is provided by a service container.\n' +
        'Locally, run with DATABASE_URL or wait for issue #13 (staging DB).'
      );
    }
    db = createDb(databaseUrl);
  });

  afterAll(async () => {
    if (db) {
      await db.pool.end();
    }
  });

  test('seed runs twice without errors (idempotency)', async () => {
    if (!db) throw new Error('DB not initialized');
    
    // First seed
    await runSeed(db.db);
    
    // Second seed - should not throw
    await runSeed(db.db);
    
    // Verify that providers and routes exist
    // This will be implemented in GREEN
    expect(true).toBe(false);
  });
});
