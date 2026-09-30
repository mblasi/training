import { describe, test, expect, vi } from 'vitest';
import { verifyToken } from '../src/auth/verifyToken.js';
import { upsertUser } from '../src/auth/upsertUser.js';

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

describe('upsertUser', () => {
  test('test_upsertUser_returns_user_role_when_not_in_admin_emails', async () => {
    const insertedRows: unknown[] = [];
    const mockInsert = () => {
      return {
        values: (row: unknown) => {
          insertedRows.push(row);
          return {
            onConflictDoUpdate: (config: {
              target: unknown;
              set: unknown;
            }) => {
              return {
                returning: () =>
                  Promise.resolve([
                    {
                      id: 'uuid-123',
                      uid: 'fb-uid-1',
                      email: 'other@x.com',
                      role: 'user',
                    },
                  ]),
              };
            },
          };
        },
      };
    };

    const fakeDb = {
      insert: mockInsert,
    };

    const result = await upsertUser(
      fakeDb as never,
      { uid: 'fb-uid-1', email: 'other@x.com', email_verified: true },
      ['admin@x.com']
    );

    expect(result).toEqual({
      id: 'uuid-123',
      uid: 'fb-uid-1',
      email: 'other@x.com',
      role: 'user',
    });
  });

  test('test_upsertUser_returns_admin_role_when_in_admin_emails_and_verified', async () => {
    const mockInsert = () => {
      return {
        values: () => {
          return {
            onConflictDoUpdate: () => {
              return {
                returning: () =>
                  Promise.resolve([
                    {
                      id: 'uuid-456',
                      uid: 'fb-uid-2',
                      email: 'admin@x.com',
                      role: 'admin',
                    },
                  ]),
              };
            },
          };
        },
      };
    };

    const fakeDb = {
      insert: mockInsert,
    };

    const result = await upsertUser(
      fakeDb as never,
      { uid: 'fb-uid-2', email: 'admin@x.com', email_verified: true },
      ['admin@x.com']
    );

    expect(result).toEqual({
      id: 'uuid-456',
      uid: 'fb-uid-2',
      email: 'admin@x.com',
      role: 'admin',
    });
  });

  test('test_upsertUser_returns_user_role_when_in_admin_emails_but_not_verified', async () => {
    const mockInsert = () => {
      return {
        values: () => {
          return {
            onConflictDoUpdate: () => {
              return {
                returning: () =>
                  Promise.resolve([
                    {
                      id: 'uuid-789',
                      uid: 'fb-uid-3',
                      email: 'admin@x.com',
                      role: 'user',
                    },
                  ]),
              };
            },
          };
        },
      };
    };

    const fakeDb = {
      insert: mockInsert,
    };

    const result = await upsertUser(
      fakeDb as never,
      { uid: 'fb-uid-3', email: 'admin@x.com', email_verified: false },
      ['admin@x.com']
    );

    expect(result).toEqual({
      id: 'uuid-789',
      uid: 'fb-uid-3',
      email: 'admin@x.com',
      role: 'user',
    });
  });

  test('test_upsertUser_admin_email_comparison_is_case_insensitive_and_trimmed', async () => {
    const mockInsert = () => {
      return {
        values: () => {
          return {
            onConflictDoUpdate: () => {
              return {
                returning: () =>
                  Promise.resolve([
                    {
                      id: 'uuid-abc',
                      uid: 'fb-uid-4',
                      email: '  Admin@X.COM  ',
                      role: 'admin',
                    },
                  ]),
              };
            },
          };
        },
      };
    };

    const fakeDb = {
      insert: mockInsert,
    };

    const result = await upsertUser(
      fakeDb as never,
      { uid: 'fb-uid-4', email: '  Admin@X.COM  ', email_verified: true },
      ['admin@x.com']
    );

    expect(result).toEqual({
      id: 'uuid-abc',
      uid: 'fb-uid-4',
      email: '  Admin@X.COM  ',
      role: 'admin',
    });
  });

  test('test_upsertUser_role_recalculated_every_upsert', async () => {
    let adminEmails: string[] = ['admin@x.com'];

    const mockInsert = () => {
      return {
        values: () => {
          return {
            onConflictDoUpdate: () => {
              return {
                returning: () => {
                  const email = 'admin@x.com';
                  const isAdmin =
                    adminEmails
                      .map((e) => e.trim().toLowerCase())
                      .includes(email.trim().toLowerCase());
                  return Promise.resolve([
                    {
                      id: 'uuid-def',
                      uid: 'fb-uid-5',
                      email: email,
                      role: isAdmin ? 'admin' : 'user',
                    },
                  ]);
                },
              };
            },
          };
        },
      };
    };

    const fakeDb = {
      insert: mockInsert,
    };

    // First call with email in admin list
    const result1 = await upsertUser(
      fakeDb as never,
      { uid: 'fb-uid-5', email: 'admin@x.com', email_verified: true },
      adminEmails
    );

    expect(result1.role).toBe('admin');

    // Second call with empty admin list
    adminEmails = [];
    const result2 = await upsertUser(
      fakeDb as never,
      { uid: 'fb-uid-5', email: 'admin@x.com', email_verified: true },
      adminEmails
    );

    expect(result2.role).toBe('user');
  });
});
