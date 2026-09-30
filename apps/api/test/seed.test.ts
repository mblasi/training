import { describe, test, expect } from 'vitest';
import { llmProviders, llmRoutes } from '../src/db/schema/index.js';
import { SEED_PROVIDERS, SEED_ROUTES, runSeed } from '../src/db/seed.js';

type ProviderRecord = { name: string; base_url: string };
type RouteRecord = { agent: string; model: string; fallback_model: string };

describe('SEED_PROVIDERS', () => {
  test('test_seed_providers_has_nous_and_gemini', () => {
    expect(SEED_PROVIDERS).toBeDefined();
    expect(Array.isArray(SEED_PROVIDERS)).toBe(true);
    expect(SEED_PROVIDERS.length).toBe(2);

    const names = SEED_PROVIDERS.map((p: ProviderRecord) => p.name);
    expect(names).toContain('nous');
    expect(names).toContain('gemini');
  });

  test('test_seed_providers_nous_base_url', () => {
    const nous = SEED_PROVIDERS.find((p: ProviderRecord) => p.name === 'nous');
    expect(nous).toBeDefined();
    expect(nous!.base_url).toBe('https://inference-api.nousresearch.com/v1');
  });
});

describe('SEED_ROUTES', () => {
  test('test_seed_routes_has_7_agents', () => {
    expect(SEED_ROUTES).toBeDefined();
    expect(Array.isArray(SEED_ROUTES)).toBe(true);
    expect(SEED_ROUTES.length).toBe(7);

    const agents = SEED_ROUTES.map((r: RouteRecord) => r.agent);
    expect(agents).toContain('router');
    expect(agents).toContain('coach');
    expect(agents).toContain('nutri');
    expect(agents).toContain('psico');
    expect(agents).toContain('sintetizador');
    expect(agents).toContain('extractor');
    expect(agents).toContain('resumidor');
  });

  test('test_seed_routes_small_agents_model', () => {
    const smallAgents = ['router', 'extractor', 'resumidor'];
    const routes = SEED_ROUTES.filter((r: RouteRecord) => smallAgents.includes(r.agent));

    expect(routes.length).toBe(3);
    routes.forEach((route: RouteRecord) => {
      expect(route.model).toBe('openai/gpt-6-luna');
    });
  });

  test('test_seed_routes_large_agents_model', () => {
    const largeAgents = ['coach', 'nutri', 'psico', 'sintetizador'];
    const routes = SEED_ROUTES.filter((r: RouteRecord) => largeAgents.includes(r.agent));

    expect(routes.length).toBe(4);
    routes.forEach((route: RouteRecord) => {
      expect(route.model).toBe('anthropic/claude-sonnet-5.5');
    });
  });

  test('test_seed_routes_small_agents_fallback', () => {
    const smallAgents = ['router', 'extractor', 'resumidor'];
    const routes = SEED_ROUTES.filter((r: RouteRecord) => smallAgents.includes(r.agent));

    expect(routes.length).toBe(3);
    routes.forEach((route: RouteRecord) => {
      expect(route.fallback_model).toBe('gemini-3.5-flash-lite');
    });
  });

  test('test_seed_routes_large_agents_fallback', () => {
    const largeAgents = ['coach', 'nutri', 'psico', 'sintetizador'];
    const routes = SEED_ROUTES.filter((r: RouteRecord) => largeAgents.includes(r.agent));

    expect(routes.length).toBe(4);
    routes.forEach((route: RouteRecord) => {
      expect(route.fallback_model).toBe('gemini-3.8-flash');
    });
  });
});

describe('runSeed', () => {
  test('test_runSeed_calls_onConflictDoNothing', async () => {
    let providersInserted: unknown = undefined;
    let providersConflictCalled = false;
    let routesInserted: unknown = undefined;
    let routesConflictCalled = false;

    const mockProvidersInsert = {
      values(data: unknown) {
        providersInserted = data;
        return {
          onConflictDoNothing() {
            providersConflictCalled = true;
            return Promise.resolve();
          },
        };
      },
    };

    const mockRoutesInsert = {
      values(data: unknown) {
        routesInserted = data;
        return {
          onConflictDoNothing() {
            routesConflictCalled = true;
            return Promise.resolve();
          },
        };
      },
    };

    const fakeDb = {
      insert(table: typeof llmProviders | typeof llmRoutes) {
        if (table === llmProviders) {
          return mockProvidersInsert;
        }
        if (table === llmRoutes) {
          return mockRoutesInsert;
        }
        throw new Error('Unexpected table');
      },
    };

    await runSeed(fakeDb as never);

    expect(providersInserted).toBeDefined();
    expect(providersConflictCalled).toBe(true);
    expect(routesInserted).toBeDefined();
    expect(routesConflictCalled).toBe(true);
  });
});
