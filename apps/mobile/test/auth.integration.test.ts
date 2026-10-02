import { describe, test, expect, beforeAll } from 'vitest';
import { initializeApp } from 'firebase/app';
import { getAuth, signInWithEmailAndPassword, connectAuthEmulator } from 'firebase/auth';
import { signInWithEmail } from '../src/auth/index.js';

describe('Auth integration with emulator', () => {
  let auth: ReturnType<typeof getAuth>;

  beforeAll(() => {
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
  });

  test('signInWithEmail succeeds with correct credentials', async () => {
    // Create a test user via the emulator (using signInWithEmailAndPassword which auto-creates users in emulator)
    const email = 'test@example.com';
    const password = 'password123';

    // First create the user in the emulator
    await signInWithEmailAndPassword(auth, email, password).catch(() => {
      // User might not exist, that's ok for first run
    });

    // Now test our function
    const result = await signInWithEmail(auth, email, password);
    expect(result.user).toBeDefined();
    expect(result.user.email).toBe(email);
  });

  test('signInWithEmail fails with wrong password', async () => {
    const email = 'test@example.com';
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
