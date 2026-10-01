import { describe, test, expect, vi } from 'vitest';
import { verifyToken } from '../src/auth/verifyToken.js';
import { upsertUser } from '../src/auth/upsertUser.js';
import { users } from '../src/db/schema/users.js';

describe('verifyToken', () => {
  test('test_verifyToken_returns_decoded_token', async () => {
    const mockAuth = {
      verifyIdToken: vi.fn().mockResolvedValue({
        uid: 'u1',
        email: 'a@b.com',
        email_verified: true,
      }),
    };

    const result = await verifyToken(mockAuth, 'tok');

    expect(mockAuth.verifyIdToken).toHaveBeenCalledWith('tok');
    expect(result).toEqual({
      uid: 'u1',
      email: 'a@b.com',
      email_verified: true,
    });
  });

  test('test_verifyToken_throws_on_invalid_token', async () => {
    const mockAuth = {
      verifyIdToken: vi.fn().mockRejectedValue(new Error('invalid')),
    };

    await expect(verifyToken(mockAuth, 'bad')).rejects.toThrow('invalid');
    expect(mockAuth.verifyIdToken).toHaveBeenCalledWith('bad');
  });
});

interface InsertCall {
  row: {
    firebase_uid: string;
    email: string;
    role: 'user' | 'admin';
    locale: string;
  };
  target: unknown;
  set: {
    email: string;
    role: 'user' | 'admin';
    locale: string;
  };
}

function createFakeDb() {
  const calls: InsertCall[] = [];

  const fakeDb = {
    insert: () => {
      let currentRow: InsertCall['row'];
      let currentTarget: unknown;
      let currentSet: InsertCall['set'];

      return {
        values: (row: InsertCall['row']) => {
          currentRow = row;
          return {
            onConflictDoUpdate: (opts: { target: unknown; set: InsertCall['set'] }) => {
              currentTarget = opts.target;
              currentSet = opts.set;
              return {
                returning: () => {
                  calls.push({
                    row: currentRow,
                    target: currentTarget,
                    set: currentSet,
                  });

                  return Promise.resolve([
                    {
                      id: 'generated-uuid',
                      firebase_uid: currentRow.firebase_uid,
                      email: currentRow.email,
                      role: currentRow.role,
                      locale: currentRow.locale,
                      created_at: new Date(),
                    },
                  ]);
                },
              };
            },
          };
        },
      };
    },
    getCalls: () => calls,
  };

  return fakeDb;
}

describe('upsertUser', () => {
  test('test_upsertUser_returns_user_role_when_not_in_admin_emails', async () => {
    const fakeDb = createFakeDb();
    
    const result = await upsertUser(
      fakeDb as never,
      { uid: 'u1', email: 'other@x.com', email_verified: true },
      ['admin@x.com']
    );

    expect(result).toEqual({
      id: 'generated-uuid',
      uid: 'u1',
      email: 'other@x.com',
      role: 'user',
    });

    const calls = fakeDb.getCalls();
    expect(calls).toHaveLength(1);
    expect(calls[0].row.firebase_uid).toBe('u1');
    expect(calls[0].row.role).toBe('user');
    expect(calls[0].set.role).toBe('user');
    expect(calls[0].target).toBe(users.firebase_uid);
  });

  test('test_upsertUser_returns_admin_role_when_in_admin_emails_and_verified', async () => {
    const fakeDb = createFakeDb();
    
    const result = await upsertUser(
      fakeDb as never,
      { uid: 'u2', email: 'admin@x.com', email_verified: true },
      ['admin@x.com']
    );

    expect(result).toEqual({
      id: 'generated-uuid',
      uid: 'u2',
      email: 'admin@x.com',
      role: 'admin',
    });

    const calls = fakeDb.getCalls();
    expect(calls).toHaveLength(1);
    expect(calls[0].row.firebase_uid).toBe('u2');
    expect(calls[0].row.role).toBe('admin');
    expect(calls[0].set.role).toBe('admin');
    expect(calls[0].target).toBe(users.firebase_uid);
  });

  test('test_upsertUser_returns_user_role_when_in_admin_emails_but_not_verified', async () => {
    const fakeDb = createFakeDb();
    
    const result = await upsertUser(
      fakeDb as never,
      { uid: 'u3', email: 'admin@x.com', email_verified: false },
      ['admin@x.com']
    );

    expect(result).toEqual({
      id: 'generated-uuid',
      uid: 'u3',
      email: 'admin@x.com',
      role: 'user',
    });

    const calls = fakeDb.getCalls();
    expect(calls).toHaveLength(1);
    expect(calls[0].row.firebase_uid).toBe('u3');
    expect(calls[0].row.role).toBe('user');
    expect(calls[0].set.role).toBe('user');
    expect(calls[0].target).toBe(users.firebase_uid);
  });

  test('test_upsertUser_admin_email_comparison_is_case_insensitive_and_trimmed', async () => {
    const fakeDb = createFakeDb();
    
    const result = await upsertUser(
      fakeDb as never,
      { uid: 'u4', email: '  Admin@X.COM  ', email_verified: true },
      ['admin@x.com']
    );

    expect(result).toEqual({
      id: 'generated-uuid',
      uid: 'u4',
      email: '  Admin@X.COM  ',
      role: 'admin',
    });

    const calls = fakeDb.getCalls();
    expect(calls).toHaveLength(1);
    expect(calls[0].row.firebase_uid).toBe('u4');
    expect(calls[0].row.role).toBe('admin');
    expect(calls[0].set.role).toBe('admin');
    expect(calls[0].target).toBe(users.firebase_uid);
  });

  test('test_upsertUser_role_recalculated_every_upsert', async () => {
    const fakeDb = createFakeDb();
    
    // First call: email in admin list → admin
    const result1 = await upsertUser(
      fakeDb as never,
      { uid: 'u5', email: 'admin@x.com', email_verified: true },
      ['admin@x.com']
    );

    expect(result1.role).toBe('admin');

    const calls1 = fakeDb.getCalls();
    expect(calls1).toHaveLength(1);
    expect(calls1[0].row.role).toBe('admin');
    expect(calls1[0].set.role).toBe('admin');

    // Second call: same db, empty admin list → user
    const result2 = await upsertUser(
      fakeDb as never,
      { uid: 'u5', email: 'admin@x.com', email_verified: true },
      []
    );

    expect(result2.role).toBe('user');

    const calls2 = fakeDb.getCalls();
    expect(calls2).toHaveLength(2);
    expect(calls2[1].row.role).toBe('user');
    expect(calls2[1].set.role).toBe('user');
  });
});

describe('auth plugin', () => {
  test('test_auth_plugin_returns_401_without_token', async () => {
    const fakeDb = createFakeDb();
    const fakePool = { query: vi.fn() } as never;
    const mockAuth = {
      verifyIdToken: vi.fn(),
    };

    const { buildApp } = await import('../src/app.js');
    const app = buildApp({
      db: { pool: fakePool, db: fakeDb as never },
      auth: mockAuth,
      adminEmails: [],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/me',
    });

    expect(response.statusCode).toBe(401);
    expect(mockAuth.verifyIdToken).not.toHaveBeenCalled();
  });

  test('test_auth_plugin_returns_401_with_invalid_token', async () => {
    const fakeDb = createFakeDb();
    const fakePool = { query: vi.fn() } as never;
    const mockAuth = {
      verifyIdToken: vi.fn().mockRejectedValue(new Error('invalid token')),
    };

    const { buildApp } = await import('../src/app.js');
    const app = buildApp({
      db: { pool: fakePool, db: fakeDb as never },
      auth: mockAuth,
      adminEmails: [],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/me',
      headers: {
        authorization: 'Bearer invalid-token',
      },
    });

    expect(response.statusCode).toBe(401);
    expect(mockAuth.verifyIdToken).toHaveBeenCalledWith('invalid-token');
    expect(fakeDb.getCalls()).toHaveLength(0);
  });

  test('test_auth_plugin_returns_200_and_user_with_valid_token', async () => {
    const fakeDb = createFakeDb();
    const fakePool = { query: vi.fn() } as never;
    const mockAuth = {
      verifyIdToken: vi.fn().mockResolvedValue({
        uid: 'u123',
        email: 'user@test.com',
        email_verified: true,
      }),
    };

    const { buildApp } = await import('../src/app.js');
    const app = buildApp({
      db: { pool: fakePool, db: fakeDb as never },
      auth: mockAuth,
      adminEmails: [],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/me',
      headers: {
        authorization: 'Bearer valid-token',
      },
    });

    expect(response.statusCode).toBe(200);
    expect(mockAuth.verifyIdToken).toHaveBeenCalledWith('valid-token');
    
    const calls = fakeDb.getCalls();
    expect(calls).toHaveLength(1);
    expect(calls[0].row.firebase_uid).toBe('u123');
    expect(calls[0].row.email).toBe('user@test.com');
    expect(calls[0].row.role).toBe('user');

    const body = JSON.parse(response.body);
    expect(body).toEqual({
      id: 'generated-uuid',
      uid: 'u123',
      email: 'user@test.com',
      role: 'user',
    });
  });

  test('test_requireAdmin_returns_403_for_user_role', async () => {
    const fakeDb = createFakeDb();
    const fakePool = { query: vi.fn() } as never;
    const mockAuth = {
      verifyIdToken: vi.fn().mockResolvedValue({
        uid: 'u456',
        email: 'user@test.com',
        email_verified: true,
      }),
    };

    const { buildApp } = await import('../src/app.js');
    const app = buildApp({
      db: { pool: fakePool, db: fakeDb as never },
      auth: mockAuth,
      adminEmails: [],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/admin/ping',
      headers: {
        authorization: 'Bearer valid-token',
      },
    });

    expect(response.statusCode).toBe(403);
  });

  test('test_requireAdmin_returns_200_for_admin_role', async () => {
    const fakeDb = createFakeDb();
    const fakePool = { query: vi.fn() } as never;
    const mockAuth = {
      verifyIdToken: vi.fn().mockResolvedValue({
        uid: 'u789',
        email: 'admin@test.com',
        email_verified: true,
      }),
    };

    const { buildApp } = await import('../src/app.js');
    const app = buildApp({
      db: { pool: fakePool, db: fakeDb as never },
      auth: mockAuth,
      adminEmails: ['admin@test.com'],
    });

    const response = await app.inject({
      method: 'GET',
      url: '/admin/ping',
      headers: {
        authorization: 'Bearer admin-token',
      },
    });

    expect(response.statusCode).toBe(200);
    
    const calls = fakeDb.getCalls();
    expect(calls).toHaveLength(1);
    expect(calls[0].row.role).toBe('admin');

    const body = JSON.parse(response.body);
    expect(body).toEqual({ ok: true });
  });
});
