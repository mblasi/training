#!/usr/bin/env tsx
import { pathToFileURL } from 'node:url';
import { requireDatabaseUrl } from './env.js';
import { createDb } from './client.js';
import { runSeed } from './seed.js';

interface Dependencies {
  createDb: typeof createDb;
  runSeed: typeof runSeed;
}

export async function main(
  env: NodeJS.ProcessEnv,
  deps: Dependencies = { createDb, runSeed }
): Promise<void> {
  const url = requireDatabaseUrl(env);
  const { db, pool } = deps.createDb(url);
  
  try {
    await deps.runSeed(db);
  } finally {
    await pool.end();
  }
}

// Run only when executed directly
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.env).catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
