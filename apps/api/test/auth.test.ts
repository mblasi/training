import { describe, test, expect, vi } from 'vitest';
import { verifyToken } from '../src/auth/verifyToken.js';

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
