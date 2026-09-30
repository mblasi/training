import { pgTable, uuid, text, timestamp, date, integer, jsonb, check } from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';

export const users = pgTable(
  'users',
  {
    id: uuid('id').primaryKey().default(sql`uuidv7()`),
    firebase_uid: text('firebase_uid').notNull(),
    email: text('email').notNull(),
    role: text('role', { enum: ['user', 'admin'] }).notNull(),
    locale: text('locale').notNull(),
    created_at: timestamp('created_at').notNull(),
  },
  (table) => [
    check('role_check', sql`${table.role} IN ('user', 'admin')`),
  ]
);

export const profiles = pgTable('profiles', {
  user_id: uuid('user_id')
    .notNull()
    .references(() => users.id),
  birthdate: date('birthdate', { mode: 'string' }),
  sex: text('sex'),
  height_cm: integer('height_cm'),
  activity_level: text('activity_level'),
  experience_level: text('experience_level'),
  injuries: jsonb('injuries'),
  updated_at: timestamp('updated_at').notNull(),
});
