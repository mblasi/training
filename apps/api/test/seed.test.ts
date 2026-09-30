import { describe, test, expect } from 'vitest';
import { SEED_PROVIDERS, SEED_ROUTES, runSeed } from '../src/db/seed.js';
import type { InferInsertModel } from 'drizzle-orm';
import { llmProviders, llmRoutes } from '../src/db/schema/index.js';

type ProviderInsert = InferInsertModel<typeof llmProviders>;
type RouteInsert = InferInsertModel<typeof llmRoutes>;

describe('SEED_PROVIDERS', () => {
  test('test_seed_providers_has_nous_and_gemini', () => {
    expect(SEED_PROVIDERS).toHaveLength(2);
    const names = SEED_PROVIDERS.map((p: ProviderInsert) => p.name);
    expect(names).toContain('nous');
    expect(names).toContain('gemini');
  });

  test('test_seed_providers_nous_base_url', () => {
    const nous = SEED_PROVIDERS.find((p: ProviderInsert) => p.name === 'nous');
    expect(nous).toBeDefined();
    expect(nous!.base_url).toBe('https://inference-api.nousresearch.com/v1');
  });
});

describe('SEED_ROUTES', () => {
  test('test_seed_routes_has_7_agents', () => {
    expect(SEED_ROUTES).toHaveLength(7);
    const agents = SEED_ROUTES.map((r: RouteInsert) => r.agent);
    expect(agents).toContain('router');
    expect(agents).toContain('coach');
    expect(agents).toContain('nutri');
    expect(agents).toContain('psico');
    expect(agents).toContain('sintetizador');
    expect(agents).toContain('extractor');
    expect(agents).toContain('resumidor');
  });

  test('test_seed_routes_small_agents_model', () => {
    const router = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'router');
    const extractor = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'extractor');
    const resumidor = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'resumidor');

    expect(router).toBeDefined();
    expect(router!.model).toBe('openai/gpt-6-luna');

    expect(extractor).toBeDefined();
    expect(extractor!.model).toBe('openai/gpt-6-luna');

    expect(resumidor).toBeDefined();
    expect(resumidor!.model).toBe('openai/gpt-6-luna');
  });

  test('test_seed_routes_large_agents_model', () => {
    const coach = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'coach');
    const nutri = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'nutri');
    const psico = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'psico');
    const sintetizador = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'sintetizador');

    expect(coach).toBeDefined();
    expect(coach!.model).toBe('anthropic/claude-sonnet-5.5');

    expect(nutri).toBeDefined();
    expect(nutri!.model).toBe('anthropic/claude-sonnet-5.5');

    expect(psico).toBeDefined();
    expect(psico!.model).toBe('anthropic/claude-sonnet-5.5');

    expect(sintetizador).toBeDefined();
    expect(sintetizador!.model).toBe('anthropic/claude-sonnet-5.5');
  });

  test('test_seed_routes_small_agents_fallback', () => {
    const router = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'router');
    const extractor = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'extractor');
    const resumidor = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'resumidor');

    expect(router).toBeDefined();
    expect(router!.fallback_model).toBe('gemini-3.5-flash-lite');

    expect(extractor).toBeDefined();
    expect(extractor!.fallback_model).toBe('gemini-3.5-flash-lite');

    expect(resumidor).toBeDefined();
    expect(resumidor!.fallback_model).toBe('gemini-3.5-flash-lite');
  });

  test('test_seed_routes_large_agents_fallback', () => {
    const coach = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'coach');
    const nutri = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'nutri');
    const psico = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'psico');
    const sintetizador = SEED_ROUTES.find((r: RouteInsert) => r.agent === 'sintetizador');

    expect(coach).toBeDefined();
    expect(coach!.fallback_model).toBe('gemini-3.8-flash');

    expect(nutri).toBeDefined();
    expect(nutri!.fallback_model).toBe('gemini-3.8-flash');

    expect(psico).toBeDefined();
    expect(psico!.fallback_model).toBe('gemini-3.8-flash');

    expect(sintetizador).toBeDefined();
    expect(sintetizador!.fallback_model).toBe('gemini-3.8-flash');
  });
});

describe('runSeed', () => {
  test('test_runSeed_calls_onConflictDoNothing', async () => {
    const insertedProviders: ProviderInsert[] = [];
    const insertedRoutes: RouteInsert[] = [];

    const mockInsert = (table: unknown) => {
      const builder = {
        values: (rows: ProviderInsert[] | RouteInsert[]) => {
          if (Array.isArray(rows)) {
            if (table === llmProviders) {
              insertedProviders.push(...(rows as ProviderInsert[]));
            } else if (table === llmRoutes) {
              insertedRoutes.push(...(rows as RouteInsert[]));
            }
          }
          return {
            onConflictDoNothing: () => Promise.resolve(),
          };
        },
      };
      return builder;
    };

    const mockSelect = () => {
      return {
        from: () => {
          return Promise.resolve([
            { id: '00000000-0000-7000-8000-000000000001', name: 'nous' },
            { id: '00000000-0000-7000-8000-000000000002', name: 'gemini' },
          ]);
        },
      };
    };

    const fakeDb = {
      insert: mockInsert,
      select: mockSelect,
    };

    await runSeed(fakeDb as never);

    // Verify providers
    expect(insertedProviders).toHaveLength(2);
    const nous = insertedProviders.find((p: ProviderInsert) => p.name === 'nous');
    const gemini = insertedProviders.find((p: ProviderInsert) => p.name === 'gemini');

    expect(nous).toBeDefined();
    expect(nous!.base_url).toBe('https://inference-api.nousresearch.com/v1');
    expect(nous!.secret_ref).toBeDefined();
    expect(nous!.enabled).toBe(true);

    expect(gemini).toBeDefined();
    expect(gemini!.secret_ref).toBeDefined();
    expect(gemini!.enabled).toBe(true);

    // Verify routes
    expect(insertedRoutes).toHaveLength(7);

    const nousId = '00000000-0000-7000-8000-000000000001';
    const geminiId = '00000000-0000-7000-8000-000000000002';

    // Small agents should use nous (provider_id) and gemini (fallback_provider_id)
    const router = insertedRoutes.find((r: RouteInsert) => r.agent === 'router');
    expect(router).toBeDefined();
    expect(router!.provider_id).toBe(nousId);
    expect(router!.fallback_provider_id).toBe(geminiId);
    expect(router!.model).toBe('openai/gpt-6-luna');
    expect(router!.fallback_model).toBe('gemini-3.5-flash-lite');

    const extractor = insertedRoutes.find((r: RouteInsert) => r.agent === 'extractor');
    expect(extractor).toBeDefined();
    expect(extractor!.provider_id).toBe(nousId);
    expect(extractor!.fallback_provider_id).toBe(geminiId);

    const resumidor = insertedRoutes.find((r: RouteInsert) => r.agent === 'resumidor');
    expect(resumidor).toBeDefined();
    expect(resumidor!.provider_id).toBe(nousId);
    expect(resumidor!.fallback_provider_id).toBe(geminiId);

    // Large agents should use nous (provider_id) and gemini (fallback_provider_id)
    const coach = insertedRoutes.find((r: RouteInsert) => r.agent === 'coach');
    expect(coach).toBeDefined();
    expect(coach!.provider_id).toBe(nousId);
    expect(coach!.fallback_provider_id).toBe(geminiId);
    expect(coach!.model).toBe('anthropic/claude-sonnet-5.5');
    expect(coach!.fallback_model).toBe('gemini-3.8-flash');

    const nutri = insertedRoutes.find((r: RouteInsert) => r.agent === 'nutri');
    expect(nutri).toBeDefined();
    expect(nutri!.provider_id).toBe(nousId);
    expect(nutri!.fallback_provider_id).toBe(geminiId);

    const psico = insertedRoutes.find((r: RouteInsert) => r.agent === 'psico');
    expect(psico).toBeDefined();
    expect(psico!.provider_id).toBe(nousId);
    expect(psico!.fallback_provider_id).toBe(geminiId);

    const sintetizador = insertedRoutes.find((r: RouteInsert) => r.agent === 'sintetizador');
    expect(sintetizador).toBeDefined();
    expect(sintetizador!.provider_id).toBe(nousId);
    expect(sintetizador!.fallback_provider_id).toBe(geminiId);
  });
});
