export function requireFirebaseProjectId(env: NodeJS.ProcessEnv): string {
  const projectId = env.FIREBASE_PROJECT_ID;
  
  if (!projectId || projectId.trim() === '') {
    throw new Error('FIREBASE_PROJECT_ID no definido');
  }
  
  return projectId;
}
