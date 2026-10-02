import { describe, test, expect, beforeAll, afterAll } from 'vitest';
import { initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { createDb } from '../src/db/client.js';
import { buildApp } from '../src/app.js';

async function exchangeCustomTokenForIdToken(customToken: string): Promise<string> {
  const response = await fetch(
    `http://${process.env.FIREBASE_AUTH_EMULATOR_HOST}/identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=fake-api-key`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ token: customToken, returnSecureToken: true }),
    }
  );
  if (!response.ok) {
    throw new Error(
      `signInWithCustomToken failed: ${response.status} ${await response.text()}`
    );
  }
  const body = (await response.json()) as { idToken?: unknown };
  if (typeof body.idToken !== 'string') {
    throw new Error('signInWithCustomToken response has no string idToken');
  }
  return body.idToken;
}

describe('Auth integration with emulator', () => {
  let db: ReturnType<typeof createDb> | undefined;
  let app: ReturnType<typeof buildApp> | undefined;
  let testUserIdToken: string;
  let adminUserIdToken: string;
  const testEmail = `user-${Date.now()}@example.com`;

  beforeAll(async () => {
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl) {
      throw new Error(
        'DATABASE_URL not set. Integration tests require a Postgres database.\n' +
        'In CI, this is provided by a service container.\n' +
        'Locally, run with DATABASE_URL or wait for issue #13 (staging DB).'
      );
    }

    if (!process.env.FIREBASE_AUTH_EMULATOR_HOST) {
      throw new Error(
        'FIREBASE_AUTH_EMULATOR_HOST not set. Integration tests require Firebase Auth emulator.'
      );
    }

    db = createDb(databaseUrl);

    // Initialize firebase-admin
    initializeApp({ projectId: process.env.FIREBASE_PROJECT_ID || 'demo-trainia' });
    const auth = getAuth();

    // Build app once for all tests
    app = buildApp({
      db,
      auth: { verifyIdToken: auth.verifyIdToken.bind(auth) },
      adminEmails: ['admin@test.local'],
    });

    // Create test users and get real ID tokens
    const testUser = await auth.createUser({
      email: testEmail,
      emailVerified: true,
    });
    testUserIdToken = await exchangeCustomTokenForIdToken(
      await auth.createCustomToken(testUser.uid)
    );

    let adminUser;
    try {
      adminUser = await auth.createUser({
        email: 'admin@test.local',
        emailVerified: true,
      });
    } catch (error) {
      const code = (error as { code?: unknown }).code;
      if (code !== 'auth/email-already-exists') throw error;
      adminUser = await auth.getUserByEmail('admin@test.local');
    }
    adminUserIdToken = await exchangeCustomTokenForIdToken(
      await auth.createCustomToken(adminUser.uid)
    );
  });

  afterAll(async () => {
    if (db) {
      await db.pool.end();
    }
  });

  test('/me without Authorization header returns 401', async () => {
    if (!app) throw new Error('App not initialized');

    const response = await app.inject({
      method: 'GET',
      url: '/me',
    });

    expect(response.statusCode).toBe(401);
  });

  test('/me with valid token returns 200 with user data', async () => {
    if (!app) throw new Error('App not initialized');

    const response = await app.inject({
      method: 'GET',
      url: '/me',
      headers: {
        authorization: `Bearer ${testUserIdToken}`,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = JSON.parse(response.body);
    expect(body.email).toBe(testEmail);
    expect(body.role).toBe('user');
  });

  test('/admin/ping with non-admin user returns 403', async () => {
    if (!app) throw new Error('App not initialized');

    const response = await app.inject({
      method: 'GET',
      url: '/admin/ping',
      headers: {
        authorization: `Bearer ${testUserIdToken}`,
      },
    });

    expect(response.statusCode).toBe(403);
  });

  test('/admin/ping with admin user returns 200', async () => {
    if (!app) throw new Error('App not initialized');

    const response = await app.inject({
      method: 'GET',
      url: '/admin/ping',
      headers: {
        authorization: `Bearer ${adminUserIdToken}`,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = JSON.parse(response.body);
    expect(body.ok).toBe(true);
  });
});
