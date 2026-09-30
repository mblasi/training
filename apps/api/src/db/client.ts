import { drizzle } from 'drizzle-orm/node-postgres';
import pkg from 'pg';
const { Pool } = pkg;

export function createDb(url: string) {
  const pool = new Pool({ connectionString: url });
  const db = drizzle(pool);
  return { pool, db };
}
