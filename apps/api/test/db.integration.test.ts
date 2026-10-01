import { describe, test, expect, beforeAll, afterAll } from 'vitest';
import { createDb } from '../src/db/client.js';
import { runSeed } from '../src/db/seed.js';
import { buildApp } from '../src/app.js';

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

  test('vector extension is installed', async () => {
    if (!db) throw new Error('DB not initialized');
    
    const result = await db.pool.query<{ extname: string }>(
      "SELECT extname FROM pg_extension WHERE extname='vector'"
    );
    
    expect(result.rows.length).toBe(1);
    expect(result.rows[0].extname).toBe('vector');
  });

  test('exactly 6 tables exist in public schema', async () => {
    if (!db) throw new Error('DB not initialized');
    
    const result = await db.pool.query<{ table_name: string }>(
      `SELECT table_name FROM information_schema.tables 
       WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
       ORDER BY table_name`
    );
    
    const tableNames = result.rows.map(r => r.table_name);
    expect(tableNames).toEqual([
      'agent_prompts',
      'llm_calls',
      'llm_providers',
      'llm_routes',
      'profiles',
      'users',
    ]);
  });

  test('seed runs twice with exact counts (idempotency)', async () => {
    if (!db) throw new Error('DB not initialized');
    
    const { llmProviders, llmRoutes } = await import('../src/db/schema/index.js');
    
    // First seed
    await runSeed(db.db);
    
    let providers = await db.db.select().from(llmProviders);
    expect(providers.length).toBe(2);
    
    let routes = await db.db.select().from(llmRoutes);
    expect(routes.length).toBe(7);
    
    // Second seed - should not throw and counts should stay the same
    await runSeed(db.db);
    
    providers = await db.db.select().from(llmProviders);
    expect(providers.length).toBe(2);
    
    routes = await db.db.select().from(llmRoutes);
    expect(routes.length).toBe(7);
  });

  test('each route points to nous and fallback to gemini', async () => {
    if (!db) throw new Error('DB not initialized');
    
    const { llmProviders, llmRoutes } = await import('../src/db/schema/index.js');
    
    await runSeed(db.db);
    
    const providers = await db.db.select().from(llmProviders);
    const nousProvider = providers.find(p => p.name === 'nous');
    const geminiProvider = providers.find(p => p.name === 'gemini');
    
    expect(nousProvider).toBeDefined();
    expect(geminiProvider).toBeDefined();
    
    const routes = await db.db.select().from(llmRoutes);
    
    for (const route of routes) {
      expect(route.provider_id).toBe(nousProvider!.id);
      expect(route.fallback_provider_id).toBe(geminiProvider!.id);
    }
  });

  test('inserting duplicate provider name fails', async () => {
    if (!db) throw new Error('DB not initialized');
    
    const { llmProviders } = await import('../src/db/schema/index.js');
    
    await runSeed(db.db);
    
    // Try to insert a duplicate 'nous' provider
    await expect(
      db.db.insert(llmProviders).values({
        name: 'nous',
        base_url: 'https://example.com',
        secret_ref: 'test-secret',
        enabled: true,
      })
    ).rejects.toThrow();
  });

  test('/health returns 200 with db ok', async () => {
    if (!db) throw new Error('DB not initialized');
    
    const app = buildApp({ db });
    
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });
    
    expect(response.statusCode).toBe(200);
    
    const body = JSON.parse(response.body);
    expect(body.status).toBe('ok');
    expect(body.db).toBe('ok');
  });
});
