import type { Database } from '../db/index.js';
import { users } from '../db/schema/users.js';
import type { AuthUser } from './types.js';

interface DecodedToken {
  uid: string;
  email: string;
  email_verified: boolean;
}

export async function upsertUser(
  db: Database,
  decodedToken: DecodedToken,
  adminEmails: string[]
): Promise<AuthUser> {
  const { uid, email, email_verified } = decodedToken;

  // Normalize admin emails for comparison
  const normalizedAdminEmails = adminEmails.map(e => e.trim().toLowerCase());
  const normalizedEmail = email.trim().toLowerCase();

  // Determine role
  const role: 'user' | 'admin' = 
    normalizedAdminEmails.includes(normalizedEmail) && email_verified
      ? 'admin'
      : 'user';

  const row = {
    firebase_uid: uid,
    email,
    role,
    locale: 'es',
  };

  const [dbUser] = await db
    .insert(users)
    .values(row)
    .onConflictDoUpdate({
      target: users.firebase_uid,
      set: {
        email,
        role,
        locale: 'es',
      },
    })
    .returning();

  return {
    id: dbUser.id,
    uid: dbUser.firebase_uid,
    email: dbUser.email,
    role: dbUser.role,
  };
}
