import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('firebase/auth');
vi.mock('@react-native-google-signin/google-signin');

describe('signInWithEmail', () => {
  let mockAuth: { currentUser: null };
  
  beforeEach(() => {
    mockAuth = { currentUser: null };
    vi.resetModules();
  });

  it('test_signInWithEmail_calls_firebase_signInWithEmailAndPassword', async () => {
    const { signInWithEmailAndPassword } = await import('firebase/auth');
    const mockSignIn = vi.mocked(signInWithEmailAndPassword);
    
    const { signInWithEmail } = await import('../src/auth/index.js');
    
    await signInWithEmail(mockAuth as never, 'a@b.com', 'pass');
    
    expect(mockSignIn).toHaveBeenCalledWith(mockAuth, 'a@b.com', 'pass');
  });

  it('test_signInWithEmail_propagates_error_on_failure', async () => {
    const { signInWithEmailAndPassword } = await import('firebase/auth');
    const mockSignIn = vi.mocked(signInWithEmailAndPassword);
    const testError = new Error('auth/invalid-credential');
    mockSignIn.mockRejectedValue(testError);
    
    const { signInWithEmail } = await import('../src/auth/index.js');
    
    await expect(signInWithEmail(mockAuth as never, 'a@b.com', 'wrong')).rejects.toThrow('auth/invalid-credential');
  });
});

describe('signInWithGoogle', () => {
  let mockAuth: { currentUser: null };
  
  beforeEach(() => {
    mockAuth = { currentUser: null };
    vi.resetModules();
  });

  it('test_signInWithGoogle_calls_GoogleSignin_and_signInWithCredential', async () => {
    const GoogleSignin = await import('@react-native-google-signin/google-signin');
    const { signInWithCredential, GoogleAuthProvider } = await import('firebase/auth');
    
    const mockSignInWithCredential = vi.mocked(signInWithCredential);
    const mockGoogleSignIn = vi.mocked(GoogleSignin.GoogleSignin.signIn);
    const mockCredential = vi.mocked(GoogleAuthProvider.credential);
    
    const idToken = 'mock-id-token';
    const signInResult: Awaited<ReturnType<typeof GoogleSignin.GoogleSignin.signIn>> = {
      type: 'success',
      data: {
        idToken,
        user: {
          id: 'user123',
          name: 'Test User',
          email: 'test@example.com',
          photo: null,
          familyName: null,
          givenName: null,
        },
        scopes: [],
        serverAuthCode: null,
      },
    };
    
    mockGoogleSignIn.mockResolvedValue(signInResult);
    
    const credentialObject = { providerId: 'google.com', signInMethod: 'google.com' };
    mockCredential.mockReturnValue(credentialObject as never);
    
    const { signInWithGoogle } = await import('../src/auth/index.js');
    
    await signInWithGoogle(mockAuth as never);
    
    expect(mockGoogleSignIn).toHaveBeenCalled();
    expect(mockCredential).toHaveBeenCalledWith(idToken);
    expect(mockSignInWithCredential).toHaveBeenCalledWith(mockAuth, credentialObject);
  });
});

describe('signOut', () => {
  let mockAuth: { currentUser: null };
  
  beforeEach(() => {
    mockAuth = { currentUser: null };
    vi.resetModules();
  });

  it('test_signOut_calls_firebase_signOut', async () => {
    const { signOut: firebaseSignOut } = await import('firebase/auth');
    const mockFirebaseSignOut = vi.mocked(firebaseSignOut);
    
    const { signOut } = await import('../src/auth/index.js');
    
    await signOut(mockAuth as never);
    
    expect(mockFirebaseSignOut).toHaveBeenCalledWith(mockAuth);
  });
});

describe('firebaseAuth', () => {
  let mockAuth: { currentUser: null };
  
  beforeEach(() => {
    mockAuth = { currentUser: null };
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('test_firebaseAuth_calls_connectAuthEmulator_when_env_set', async () => {
    vi.stubEnv('EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099');
    
    const { connectAuthEmulator, initializeAuth } = await import('firebase/auth');
    vi.mocked(initializeAuth).mockReturnValue(mockAuth as never);
    
    await import('../src/auth/firebaseAuth.js');
    
    expect(initializeAuth).toHaveBeenCalledTimes(1);
    expect(connectAuthEmulator).toHaveBeenCalledWith(expect.anything(), 'http://localhost:9099');
  });

  it('test_firebaseAuth_does_not_call_connectAuthEmulator_when_env_not_set', async () => {
    vi.stubEnv('EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST', '');
    
    const { connectAuthEmulator, initializeAuth } = await import('firebase/auth');
    vi.mocked(initializeAuth).mockReturnValue(mockAuth as never);
    
    await import('../src/auth/firebaseAuth.js');
    
    expect(initializeAuth).toHaveBeenCalledTimes(1);
    expect(connectAuthEmulator).not.toHaveBeenCalled();
  });
});
