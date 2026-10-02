import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Auth } from 'firebase/auth';

// Mock firebase/auth
vi.mock('firebase/auth', () => ({
  signInWithEmailAndPassword: vi.fn(),
  signInWithCredential: vi.fn(),
  signOut: vi.fn(),
  GoogleAuthProvider: {
    credential: vi.fn(),
  },
  connectAuthEmulator: vi.fn(),
  initializeAuth: vi.fn(),
  getReactNativePersistence: vi.fn(),
}));

// Mock @react-native-google-signin/google-signin
vi.mock('@react-native-google-signin/google-signin', () => ({
  GoogleSignin: {
    configure: vi.fn(),
    signIn: vi.fn(),
  },
}));

// Mock @react-native-async-storage/async-storage
vi.mock('@react-native-async-storage/async-storage', () => ({
  default: {},
}));

// Mock firebase/app
vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(),
}));

describe('mobile auth', () => {
  let mockAuth: Auth;

  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth = {} as Auth;
  });

  describe('signInWithEmail', () => {
    it('test_signInWithEmail_calls_firebase_signInWithEmailAndPassword', async () => {
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      const { signInWithEmail } = await import('../src/auth/index.js');

      await signInWithEmail(mockAuth, 'a@b.com', 'pass');

      expect(signInWithEmailAndPassword).toHaveBeenCalledWith(mockAuth, 'a@b.com', 'pass');
    });

    it('test_signInWithEmail_propagates_error_on_failure', async () => {
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      const { signInWithEmail } = await import('../src/auth/index.js');

      const error = new Error('Invalid credentials');
      vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce(error);

      await expect(signInWithEmail(mockAuth, 'a@b.com', 'wrongpass')).rejects.toThrow('Invalid credentials');
    });
  });

  describe('signInWithGoogle', () => {
    it('test_signInWithGoogle_calls_GoogleSignin_and_signInWithCredential', async () => {
      const { signInWithCredential, GoogleAuthProvider } = await import('firebase/auth');
      const { GoogleSignin } = await import('@react-native-google-signin/google-signin');
      const { signInWithGoogle } = await import('../src/auth/index.js');

      const mockIdToken = 'mock-google-id-token';
      vi.mocked(GoogleSignin.signIn).mockResolvedValueOnce({
        type: 'success',
        data: {
          user: {
            id: 'mock-user-id',
            name: 'Test User',
            email: 'test@example.com',
            photo: null,
            familyName: null,
            givenName: null,
          },
          scopes: [],
          idToken: mockIdToken,
          serverAuthCode: null,
        },
      });

      const mockCredential = { providerId: 'google.com', signInMethod: 'google.com' };
      vi.mocked(GoogleAuthProvider.credential).mockReturnValueOnce(mockCredential as never);

      await signInWithGoogle(mockAuth);

      expect(GoogleSignin.signIn).toHaveBeenCalledWith();
      expect(GoogleAuthProvider.credential).toHaveBeenCalledWith(mockIdToken);
      expect(signInWithCredential).toHaveBeenCalledWith(mockAuth, mockCredential);
    });
  });

  describe('signOut', () => {
    it('test_signOut_calls_firebase_signOut', async () => {
      const firebaseAuth = await import('firebase/auth');
      const { signOut } = await import('../src/auth/index.js');

      await signOut(mockAuth);

      expect(firebaseAuth.signOut).toHaveBeenCalledWith(mockAuth);
    });
  });

  describe('firebaseAuth', () => {
    beforeEach(() => {
      vi.resetModules();
      vi.unstubAllEnvs();
    });

    it('test_firebaseAuth_calls_connectAuthEmulator_when_env_set', async () => {
      vi.stubEnv('EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099');

      const { connectAuthEmulator } = await import('firebase/auth');

      await import('../src/auth/firebaseAuth.js');

      expect(connectAuthEmulator).toHaveBeenCalledWith(
        expect.anything(),
        'http://localhost:9099'
      );
    });

    it('test_firebaseAuth_does_not_call_connectAuthEmulator_when_env_not_set', async () => {
      vi.stubEnv('EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST', '');

      const { connectAuthEmulator } = await import('firebase/auth');

      await import('../src/auth/firebaseAuth.js');

      expect(connectAuthEmulator).not.toHaveBeenCalled();
    });
  });
});
