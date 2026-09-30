import type { InferInsertModel } from 'drizzle-orm';
import { llmProviders, llmRoutes } from './schema/index.js';

type ProviderInsert = InferInsertModel<typeof llmProviders>;
type RouteInsert = InferInsertModel<typeof llmRoutes>;

export const SEED_PROVIDERS: ProviderInsert[] = [
  {
    name: 'nous',
    base_url: 'https://inference-api.nousresearch.com/v1',
    secret_ref: 'trainia-nous-api-key',
    enabled: true,
  },
  {
    name: 'gemini',
    base_url: 'https://generativelanguage.googleapis.com/v1beta',
    secret_ref: 'trainia-gemini-api-key',
    enabled: true,
  },
];

type RouteTemplate = {
  agent: string;
  provider: 'nous' | 'gemini';
  model: string;
  fallback_provider: 'nous' | 'gemini';
  fallback_model: string;
};

const SEED_ROUTES_TEMPLATE: RouteTemplate[] = [
  {
    agent: 'router',
    provider: 'nous',
    model: 'openai/gpt-6-luna',
    fallback_provider: 'gemini',
    fallback_model: 'gemini-3.5-flash-lite',
  },
  {
    agent: 'extractor',
    provider: 'nous',
    model: 'openai/gpt-6-luna',
    fallback_provider: 'gemini',
    fallback_model: 'gemini-3.5-flash-lite',
  },
  {
    agent: 'resumidor',
    provider: 'nous',
    model: 'openai/gpt-6-luna',
    fallback_provider: 'gemini',
    fallback_model: 'gemini-3.5-flash-lite',
  },
  {
    agent: 'coach',
    provider: 'nous',
    model: 'anthropic/claude-sonnet-5.5',
    fallback_provider: 'gemini',
    fallback_model: 'gemini-3.8-flash',
  },
  {
    agent: 'nutri',
    provider: 'nous',
    model: 'anthropic/claude-sonnet-5.5',
    fallback_provider: 'gemini',
    fallback_model: 'gemini-3.8-flash',
  },
  {
    agent: 'psico',
    provider: 'nous',
    model: 'anthropic/claude-sonnet-5.5',
    fallback_provider: 'gemini',
    fallback_model: 'gemini-3.8-flash',
  },
  {
    agent: 'sintetizador',
    provider: 'nous',
    model: 'anthropic/claude-sonnet-5.5',
    fallback_provider: 'gemini',
    fallback_model: 'gemini-3.8-flash',
  },
];

// Exportar SEED_ROUTES como RouteInsert[] (sin provider_id/fallback_provider_id aún)
export const SEED_ROUTES: RouteInsert[] = SEED_ROUTES_TEMPLATE.map((template) => ({
  agent: template.agent,
  provider_id: '', // Will be populated in runSeed
  model: template.model,
  params: null,
  fallback_provider_id: null,
  fallback_model: template.fallback_model,
  updated_by: null,
  updated_at: new Date(),
}));

interface DbClient {
  insert: (table: typeof llmProviders | typeof llmRoutes) => {
    values: (rows: ProviderInsert[] | RouteInsert[]) => {
      onConflictDoNothing: () => Promise<unknown>;
    };
  };
  select: () => {
    from: (table: typeof llmProviders) => Promise<{ id: string; name: string }[]>;
  };
}

export async function runSeed(db: DbClient): Promise<void> {
  // Insert providers
  await db.insert(llmProviders).values(SEED_PROVIDERS).onConflictDoNothing();

  // Fetch provider IDs
  const providers = await db.select().from(llmProviders);
  const providerMap = new Map<string, string>();
  for (const provider of providers) {
    providerMap.set(provider.name, provider.id);
  }

  const nousId = providerMap.get('nous');
  const geminiId = providerMap.get('gemini');

  if (!nousId || !geminiId) {
    throw new Error('Failed to fetch provider IDs');
  }

  // Build routes with actual IDs
  const routesToInsert: RouteInsert[] = SEED_ROUTES_TEMPLATE.map((template) => ({
    agent: template.agent,
    provider_id: template.provider === 'nous' ? nousId : geminiId,
    model: template.model,
    params: null,
    fallback_provider_id: template.fallback_provider === 'nous' ? nousId : geminiId,
    fallback_model: template.fallback_model,
    updated_by: null,
    updated_at: new Date(),
  }));

  // Insert routes
  await db.insert(llmRoutes).values(routesToInsert).onConflictDoNothing();
}
