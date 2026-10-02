import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Auth, User } from 'firebase/auth';

// Mock firebase/auth
vi.mock('firebase/auth', () => ({
  connectAuthEmulator: vi.fn(),
  getAuth: vi.fn(),
  GoogleAuthProvider: vi.fn(function GoogleAuthProvider() {
    return {};
  }),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChanged: vi.fn(() => {
    // Callback vacío por default
    return () => {};
  }),
}));

const mockConnectAuthEmulator = vi.mocked(
  (await import('firebase/auth')).connectAuthEmulator
);
const mockGetAuth = vi.mocked((await import('firebase/auth')).getAuth);
const mockSignInWithPopup = vi.mocked(
  (await import('firebase/auth')).signInWithPopup
);
const mockSignOut = vi.mocked((await import('firebase/auth')).signOut);
const mockOnAuthStateChanged = vi.mocked(
  (await import('firebase/auth')).onAuthStateChanged
);

describe('firebaseConfig', () => {
  beforeEach(() => {
    vi.resetModules();
    mockConnectAuthEmulator.mockClear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  test('test_firebaseConfig_calls_connectAuthEmulator_when_env_set', async () => {
    vi.stubEnv('VITE_FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099');
    await import('../src/auth/firebaseConfig');
    expect(mockConnectAuthEmulator).toHaveBeenCalledWith(
      expect.anything(),
      'http://localhost:9099'
    );
  });

  test('test_firebaseConfig_does_not_call_connectAuthEmulator_when_env_not_set', async () => {
    vi.stubEnv('VITE_FIREBASE_AUTH_EMULATOR_HOST', '');
    await import('../src/auth/firebaseConfig');
    expect(mockConnectAuthEmulator).not.toHaveBeenCalled();
  });
});

describe('AuthContext', () => {
  beforeEach(() => {
    mockGetAuth.mockReturnValue({ currentUser: null } as Auth);
    mockConnectAuthEmulator.mockClear();
    mockSignInWithPopup.mockClear();
    mockSignOut.mockClear();
    mockOnAuthStateChanged.mockClear();
    vi.stubGlobal('fetch', vi.fn());
  });

  test('test_login_calls_signInWithPopup_with_google_provider', async () => {
    const { AuthProvider, useAuth } = await import('../src/auth/AuthContext');
    const { GoogleAuthProvider } = await import('firebase/auth');
    
    let loginFn: (() => Promise<void>) | null = null;
    function TestComponent() {
      const { login } = useAuth();
      loginFn = login;
      return <div>test</div>;
    }

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Llamar login() del context
    await loginFn!();

    expect(mockSignInWithPopup).toHaveBeenCalledWith(
      expect.anything(),
      expect.any(GoogleAuthProvider)
    );
  });

  test('test_auth_context_sets_role_admin_when_me_returns_admin', async () => {
    // Mock fetch para /me
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ role: 'admin' }),
    } as Response);
    vi.stubGlobal('fetch', mockFetch);

    // Mock onAuthStateChanged para simular usuario autenticado
    mockOnAuthStateChanged.mockImplementation((_auth, nextOrObserver) => {
      const mockUser = {
        uid: 'test-uid',
        getIdToken: vi.fn().mockResolvedValue('test-token'),
      } as unknown as User;
      if (typeof nextOrObserver === 'function') {
        nextOrObserver(mockUser);
      }
      return () => {};
    });

    const { AuthProvider, useAuth } = await import('../src/auth/AuthContext');
    
    let contextValue: { role: string | null } | null = null;
    function TestComponent() {
      contextValue = useAuth();
      return <div>test</div>;
    }

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for async operations
    await vi.waitFor(() => {
      expect(contextValue?.role).toBe('admin');
    });

    expect(mockSignOut).not.toHaveBeenCalled();
  });

  test('test_auth_context_calls_signout_when_me_returns_user_role', async () => {
    // Mock fetch para /me
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ role: 'user' }),
    } as Response);
    vi.stubGlobal('fetch', mockFetch);

    // Mock onAuthStateChanged para simular usuario autenticado
    mockOnAuthStateChanged.mockImplementation((_auth, nextOrObserver) => {
      const mockUser = {
        uid: 'test-uid',
        getIdToken: vi.fn().mockResolvedValue('test-token'),
      } as unknown as User;
      if (typeof nextOrObserver === 'function') {
        nextOrObserver(mockUser);
      }
      return () => {};
    });

    const { AuthProvider } = await import('../src/auth/AuthContext');

    render(
      <AuthProvider>
        <div>test</div>
      </AuthProvider>
    );

    // Wait for signOut to be called
    await vi.waitFor(() => {
      expect(mockSignOut).toHaveBeenCalled();
    });
  });

  test('test_app_renders_login_when_not_authenticated', async () => {
    // Mock onAuthStateChanged para simular sin usuario
    mockOnAuthStateChanged.mockImplementation((_auth, nextOrObserver) => {
      if (typeof nextOrObserver === 'function') {
        nextOrObserver(null);
      }
      return () => {};
    });

    const { AuthProvider } = await import('../src/auth/AuthContext');
    const App = (await import('../src/App')).default;

    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );

    // El App debe renderizar Login cuando no hay usuario
    // Este test fallará hasta que Login esté implementado
    expect(screen.getByText(/login/i)).toBeInTheDocument();
  });

  test('test_app_renders_content_when_authenticated_as_admin', async () => {
    // Mock fetch para /me
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ role: 'admin' }),
    } as Response);
    vi.stubGlobal('fetch', mockFetch);

    // Mock onAuthStateChanged para simular usuario autenticado
    mockOnAuthStateChanged.mockImplementation((_auth, nextOrObserver) => {
      const mockUser = {
        uid: 'test-uid',
        getIdToken: vi.fn().mockResolvedValue('test-token'),
      } as unknown as User;
      if (typeof nextOrObserver === 'function') {
        nextOrObserver(mockUser);
      }
      return () => {};
    });

    const { AuthProvider } = await import('../src/auth/AuthContext');
    const App = (await import('../src/App')).default;

    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );

    // Wait for role to be set
    await vi.waitFor(() => {
      expect(screen.getByText('Trainia')).toBeInTheDocument();
    });

    // El App debe renderizar contenido principal, no Login
    expect(screen.queryByText(/login/i)).not.toBeInTheDocument();
  });
});
