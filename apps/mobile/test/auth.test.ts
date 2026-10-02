import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { Auth, OAuthCredential } from 'firebase/auth';

vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({}))
}));

vi.mock('firebase/auth', () => ({
  initializeAuth: vi.fn(),
  getReactNativePersistence: vi.fn(),
  connectAuthEmulator: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  signInWithCredential: vi.fn(),
  signOut: vi.fn(),
  GoogleAuthProvider: {
    credential: vi.fn()
  }
}));

vi.mock('@react-native-google-signin/google-signin', () => ({
  GoogleSignin: {
    signIn: vi.fn(),
    configure: vi.fn(),
    signOut: vi.fn()
  }
}));

vi.mock('@react-native-async-storage/async-storage', () => ({
  default: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn()
  }
}));

async function fakeOAuthCredential(idToken: string): Promise<OAuthCredential> {
  // OAuthCredential has private members, so an object literal cannot satisfy it;
  // build a real instance with the actual (unmocked) firebase/auth module.
  const actual = await vi.importActual<typeof import('firebase/auth')>('firebase/auth');
  const credential = actual.OAuthCredential.fromJSON({
    providerId: 'google.com',
    signInMethod: 'google.com',
    idToken
  });
  if (!credential) {
    throw new Error('failed to build OAuthCredential');
  }
  return credential;
}

describe('mobile auth', () => {
  const mockAuth = {} as Auth;

  describe('signInWithEmail', () => {
    it('test_signInWithEmail_calls_firebase_signInWithEmailAndPassword', async () => {
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      const { signInWithEmail } = await import('../src/auth/index.js');

      await signInWithEmail(mockAuth, 'a@b.com', 'pass');

      expect(signInWithEmailAndPassword).toHaveBeenCalledWith(mockAuth, 'a@b.com', 'pass');
    });

    it('test_signInWithEmail_propagates_error_on_failure', async () => {
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      vi.mocked(signInWithEmailAndPassword).mockRejectedValue(new Error('auth failed'));

      const { signInWithEmail } = await import('../src/auth/index.js');

      await expect(signInWithEmail(mockAuth, 'a@b.com', 'pass')).rejects.toThrow('auth failed');
    });
  });

  describe('signInWithGoogle', () => {
    it('test_signInWithGoogle_calls_GoogleSignin_and_signInWithCredential', async () => {
      const { GoogleSignin } = await import('@react-native-google-signin/google-signin');
      const { GoogleAuthProvider, signInWithCredential } = await import('firebase/auth');
      
      const idToken = 'mock-id-token';
      const mockCredential = await fakeOAuthCredential(idToken);
      
      const signInResult: Awaited<ReturnType<typeof GoogleSignin.signIn>> = {
        type: 'success',
        data: {
          idToken,
          user: {
            id: '123',
            name: 'Test User',
            email: 'test@example.com',
            photo: null,
            familyName: null,
            givenName: null
          },
          scopes: [],
          serverAuthCode: null
        }
      };
      
      vi.mocked(GoogleSignin.signIn).mockResolvedValue(signInResult);
      vi.mocked(GoogleAuthProvider.credential).mockReturnValue(mockCredential);

      const { signInWithGoogle } = await import('../src/auth/index.js');

      await signInWithGoogle(mockAuth);

      expect(GoogleSignin.signIn).toHaveBeenCalled();
      expect(GoogleAuthProvider.credential).toHaveBeenCalledWith(idToken);
      expect(signInWithCredential).toHaveBeenCalledWith(mockAuth, mockCredential);
    });
  });

  describe('signOut', () => {
    it('test_signOut_calls_firebase_signOut', async () => {
      const { signOut: firebaseSignOut } = await import('firebase/auth');
      const { signOut } = await import('../src/auth/index.js');

      await signOut(mockAuth);

      expect(firebaseSignOut).toHaveBeenCalledWith(mockAuth);
    });
  });

  describe('firebaseAuth', () => {
    beforeEach(() => {
      vi.resetModules();
    });

    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it('test_firebaseAuth_calls_connectAuthEmulator_when_env_set', async () => {
      vi.stubEnv('EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099');

      const { connectAuthEmulator, initializeAuth } = await import('firebase/auth');
      vi.mocked(initializeAuth).mockReturnValue(mockAuth);

      await import('../src/auth/firebaseAuth.js');

      expect(initializeAuth).toHaveBeenCalledTimes(1);
      expect(connectAuthEmulator).toHaveBeenCalledWith(mockAuth, 'http://localhost:9099');
    });

    it('test_firebaseAuth_does_not_call_connectAuthEmulator_when_env_not_set', async () => {
      vi.stubEnv('EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST', '');

      const { connectAuthEmulator, initializeAuth } = await import('firebase/auth');
      vi.mocked(initializeAuth).mockReturnValue(mockAuth);

      await import('../src/auth/firebaseAuth.js');

      expect(initializeAuth).toHaveBeenCalledTimes(1);
      expect(connectAuthEmulator).not.toHaveBeenCalled();
    });
  });
});
