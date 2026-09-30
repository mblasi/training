import { pgTable, uuid, text, timestamp, integer, jsonb, check, boolean, numeric } from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';

export const llmProviders = pgTable(
  'llm_providers',
  {
    id: uuid('id').primaryKey().default(sql`uuidv7()`),
    name: text('name', { enum: ['nous', 'gemini'] }).notNull().unique(),
    base_url: text('base_url').notNull(),
    secret_ref: text('secret_ref').notNull(),
    enabled: boolean('enabled').notNull(),
  },
  (table) => [
    check('name_check', sql`${table.name} IN ('nous', 'gemini')`),
  ]
);

export const llmRoutes = pgTable('llm_routes', {
  agent: text('agent').primaryKey(),
  provider_id: uuid('provider_id')
    .notNull()
    .references(() => llmProviders.id),
  model: text('model').notNull(),
  params: jsonb('params'),
  fallback_provider_id: uuid('fallback_provider_id').references(() => llmProviders.id),
  fallback_model: text('fallback_model'),
  updated_by: uuid('updated_by'),
  updated_at: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
});

export const llmCalls = pgTable('llm_calls', {
  id: uuid('id').primaryKey().default(sql`uuidv7()`),
  user_id: uuid('user_id'),
  conversation_id: uuid('conversation_id'),
  agent: text('agent').notNull(),
  model: text('model').notNull(),
  prompt_version: text('prompt_version'),
  tokens_in: integer('tokens_in').notNull(),
  tokens_out: integer('tokens_out').notNull(),
  cost_usd: numeric('cost_usd').notNull(),
  latency_ms: integer('latency_ms').notNull(),
  context_breakdown: jsonb('context_breakdown').notNull(),
  error: text('error'),
  provider: text('provider').notNull(),
});
