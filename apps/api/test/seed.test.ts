import { describe, test, expect } from 'vitest';
import { SEED_PROVIDERS, SEED_ROUTES, runSeed } from '../src/db/seed.js';

describe('SEED_PROVIDERS', () => {
  test('test_seed_providers_has_nous_and_gemini', () => {
    expect(SEED_PROVIDERS).toBeDefined();
    expect(SEED_PROVIDERS.length).toBe(2);

    const names = SEED_PROVIDERS.map((p: any) => p.name);
    expect(names).toContain('nous');
    expect(names).toContain('gemini');
  });

  test('test_seed_providers_nous_base_url', () => {
    const nous = SEED_PROVIDERS.find((p: any) => p.name === 'nous');
    expect(nous).toBeDefined();
    expect(nous!.base_url).toBe('https://inference-api.nousresearch.com/v1');
  });
});

describe('SEED_ROUTES', () => {
  test('test_seed_routes_has_7_agents', () => {
    expect(SEED_ROUTES).toBeDefined();
    expect(SEED_ROUTES.length).toBe(7);

    const agents = SEED_ROUTES.map((r: any) => r.agent);
    expect(agents).toContain('router');
    expect(agents).toContain('coach');
    expect(agents).toContain('nutri');
    expect(agents).toContain('psico');
    expect(agents).toContain('sintetizador');
    expect(agents).toContain('extractor');
    expect(agents).toContain('resumidor');
  });

  test('test_seed_routes_small_agents_model', () => {
    const router = SEED_ROUTES.find((r: any) => r.agent === 'router');
    const extractor = SEED_ROUTES.find((r: any) => r.agent === 'extractor');
    const resumidor = SEED_ROUTES.find((r: any) => r.agent === 'resumidor');

    expect(router).toBeDefined();
    expect(router!.model).toBe('openai/gpt-6-luna');

    expect(extractor).toBeDefined();
    expect(extractor!.model).toBe('openai/gpt-6-luna');

    expect(resumidor).toBeDefined();
    expect(resumidor!.model).toBe('openai/gpt-6-luna');
  });

  test('test_seed_routes_large_agents_model', () => {
    const coach = SEED_ROUTES.find((r: any) => r.agent === 'coach');
    const nutri = SEED_ROUTES.find((r: any) => r.agent === 'nutri');
    const psico = SEED_ROUTES.find((r: any) => r.agent === 'psico');
    const sintetizador = SEED_ROUTES.find((r: any) => r.agent === 'sintetizador');

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
    const router = SEED_ROUTES.find((r: any) => r.agent === 'router');
    const extractor = SEED_ROUTES.find((r: any) => r.agent === 'extractor');
    const resumidor = SEED_ROUTES.find((r: any) => r.agent === 'resumidor');

    expect(router).toBeDefined();
    expect(router!.fallback_model).toBe('gemini-3.5-flash-lite');

    expect(extractor).toBeDefined();
    expect(extractor!.fallback_model).toBe('gemini-3.5-flash-lite');

    expect(resumidor).toBeDefined();
    expect(resumidor!.fallback_model).toBe('gemini-3.5-flash-lite');
  });

  test('test_seed_routes_large_agents_fallback', () => {
    const coach = SEED_ROUTES.find((r: any) => r.agent === 'coach');
    const nutri = SEED_ROUTES.find((r: any) => r.agent === 'nutri');
    const psico = SEED_ROUTES.find((r: any) => r.agent === 'psico');
    const sintetizador = SEED_ROUTES.find((r: any) => r.agent === 'sintetizador');

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
    // Mock chainable builder
    let insertCalled = false;
    let valuesCalled = false;
    let onConflictDoNothingCalled = false;

    const builder = {
      values: (data: unknown) => {
        valuesCalled = true;
        return {
          onConflictDoNothing: () => {
            onConflictDoNothingCalled = true;
            return Promise.resolve();
          },
        };
      },
    };

    const fakeDb = {
      insert: (table: unknown) => {
        insertCalled = true;
        return builder;
      },
    };

    await runSeed(fakeDb as any);

    expect(insertCalled).toBe(true);
    expect(valuesCalled).toBe(true);
    expect(onConflictDoNothingCalled).toBe(true);
  });
});
