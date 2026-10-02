import { describe, test, expect, beforeAll } from 'vitest';
import { initializeApp } from 'firebase/app';
import {
  getAuth,
  connectAuthEmulator,
  createUserWithEmailAndPassword,
  signOut,
} from 'firebase/auth';
import { signInWithEmail } from '../src/auth/email.js';

describe('Auth integration with emulator', () => {
  let auth: ReturnType<typeof getAuth>;
  const email = `user-${Date.now()}@example.com`;
  const password = 'password123';

  beforeAll(async () => {
    if (!process.env.EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST) {
      throw new Error(
        'EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST not set. Integration tests require Firebase Auth emulator.'
      );
    }

    const app = initializeApp({
      apiKey: 'fake-api-key',
      projectId: 'demo-trainia',
    });
    auth = getAuth(app);
    connectAuthEmulator(auth, `http://${process.env.EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST}`);

    // The emulator does not auto-create users on sign in: create it explicitly
    await createUserWithEmailAndPassword(auth, email, password);
    await signOut(auth);
  });

  test('signInWithEmail succeeds with correct credentials', async () => {
    const result = await signInWithEmail(auth, email, password);
    expect(result.user).toBeDefined();
    expect(result.user.email).toBe(email);
  });

  test('signInWithEmail fails with wrong password', async () => {
    const wrongPassword = 'wrongpassword';

    await expect(
      signInWithEmail(auth, email, wrongPassword)
    ).rejects.toThrow();
  });

  test('signInWithEmail fails with invalid email format', async () => {
    await expect(
      signInWithEmail(auth, 'notanemail', 'password123')
    ).rejects.toThrow();
  });
});
