import type { DecodedIdToken } from './types.js';

interface Auth {
  verifyIdToken(token: string): Promise<DecodedIdToken>;
}

export async function verifyToken(
  auth: Auth,
  token: string
): Promise<DecodedIdToken> {
  return await auth.verifyIdToken(token);
}
