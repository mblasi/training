import { describe, test, expect, beforeAll, afterAll } from 'vitest';
import { initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { createDb } from '../src/db/client.js';
import { buildApp } from '../src/app.js';

describe('Auth integration with emulator', () => {
  let db: ReturnType<typeof createDb> | undefined;
  let testUserToken: string;
  let adminUserToken: string;

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

    // Create test users and get tokens
    const testUser = await auth.createUser({
      email: 'test@example.com',
      emailVerified: true,
    });
    testUserToken = await auth.createCustomToken(testUser.uid);

    const adminUser = await auth.createUser({
      email: 'admin@test.local',
      emailVerified: true,
    });
    adminUserToken = await auth.createCustomToken(adminUser.uid);
  });

  afterAll(async () => {
    if (db) {
      await db.pool.end();
    }
  });

  test('/me without Authorization header returns 401', async () => {
    if (!db) throw new Error('DB not initialized');

    const app = buildApp({
      db,
      auth: { verifyIdToken: getAuth().verifyIdToken.bind(getAuth()) },
      adminEmails: ['admin@test.local'],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/me',
    });

    expect(response.statusCode).toBe(401);
  });

  test('/me with valid token returns 200 with user data', async () => {
    if (!db) throw new Error('DB not initialized');

    const app = buildApp({
      db,
      auth: { verifyIdToken: getAuth().verifyIdToken.bind(getAuth()) },
      adminEmails: ['admin@test.local'],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/me',
      headers: {
        authorization: `Bearer ${testUserToken}`,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = JSON.parse(response.body);
    expect(body.email).toBe('test@example.com');
    expect(body.role).toBe('user');
  });

  test('/admin/ping with non-admin user returns 403', async () => {
    if (!db) throw new Error('DB not initialized');

    const app = buildApp({
      db,
      auth: { verifyIdToken: getAuth().verifyIdToken.bind(getAuth()) },
      adminEmails: ['admin@test.local'],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/admin/ping',
      headers: {
        authorization: `Bearer ${testUserToken}`,
      },
    });

    expect(response.statusCode).toBe(403);
  });

  test('/admin/ping with admin user returns 200', async () => {
    if (!db) throw new Error('DB not initialized');

    const app = buildApp({
      db,
      auth: { verifyIdToken: getAuth().verifyIdToken.bind(getAuth()) },
      adminEmails: ['admin@test.local'],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/admin/ping',
      headers: {
        authorization: `Bearer ${adminUserToken}`,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = JSON.parse(response.body);
    expect(body.ok).toBe(true);
  });
});
