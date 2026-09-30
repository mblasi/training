export function requireDatabaseUrl(env: NodeJS.ProcessEnv): string {
  const url = env.DATABASE_URL;
  
  if (!url || url.trim() === '') {
    throw new Error('DATABASE_URL no definida');
  }
  
  return url;
}
