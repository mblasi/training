import { pgTable, uuid, text, integer, timestamp, check, unique } from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';

export const agentPrompts = pgTable(
  'agent_prompts',
  {
    id: uuid('id').primaryKey().default(sql`uuidv7()`),
    agent: text('agent').notNull(),
    version: integer('version').notNull(),
    content: text('content').notNull(),
    status: text('status', { enum: ['draft', 'published', 'archived'] }).notNull(),
    author: uuid('author').notNull(),
    notes: text('notes'),
    created_at: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    check('status_check', sql`${table.status} IN ('draft', 'published', 'archived')`),
    unique().on(table.agent, table.version),
  ]
);
