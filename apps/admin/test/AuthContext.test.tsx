import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import type { Auth, User, UserCredential } from 'firebase/auth';

// Mock de firebase/auth
const mockConnectAuthEmulator = vi.fn();
const mockSignInWithPopup = vi.fn();
const mockSignOut = vi.fn();
const mockGetAuth = vi.fn();
const mockGetIdToken = vi.fn();
const mockOnAuthStateChanged = vi.fn();

vi.mock('firebase/auth', () => ({
  getAuth: () => mockGetAuth(),
  connectAuthEmulator: (...args: unknown[]) => mockConnectAuthEmulator(...args),
  signInWithPopup: (...args: unknown[]) => mockSignInWithPopup(...args),
  signOut: (...args: unknown[]) => mockSignOut(...args),
  GoogleAuthProvider: vi.fn().mockImplementation(() => ({})),
  onAuthStateChanged: (...args: unknown[]) => mockOnAuthStateChanged(...args),
  getIdToken: (...args: unknown[]) => mockGetIdToken(...args),
}));

vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({})),
}));

// Mock de fetch global
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as typeof fetch;

// Helper para manipular env vars en tests
interface TestImportMeta extends ImportMeta {
  env: Record<string, string | undefined>;
}

describe('firebaseConfig', () => {
  test('test_firebaseConfig_calls_connectAuthEmulator_when_env_set', async () => {
    // Guardar el estado original
    const originalEnv = (import.meta as TestImportMeta).env.VITE_FIREBASE_AUTH_EMULATOR_HOST;
    
    // Definir la env var antes de importar
    (import.meta as TestImportMeta).env.VITE_FIREBASE_AUTH_EMULATOR_HOST = 'localhost:9099';
    
    // Resetear el mock antes de importar
    mockConnectAuthEmulator.mockClear();
    
    // Usar dynamic import con cache busting
    await import('../src/auth/firebaseConfig.js?t=' + Date.now());
    
    // Verificar que connectAuthEmulator fue llamado con la URL correcta
    expect(mockConnectAuthEmulator).toHaveBeenCalledWith(
      expect.anything(),
      'http://localhost:9099'
    );
    
    // Restaurar env original
    if (originalEnv !== undefined) {
      (import.meta as TestImportMeta).env.VITE_FIREBASE_AUTH_EMULATOR_HOST = originalEnv;
    } else {
      delete (import.meta as TestImportMeta).env.VITE_FIREBASE_AUTH_EMULATOR_HOST;
    }
  });

  test('test_firebaseConfig_does_not_call_connectAuthEmulator_when_env_not_set', async () => {
    // Guardar el estado original
    const originalEnv = (import.meta as TestImportMeta).env.VITE_FIREBASE_AUTH_EMULATOR_HOST;
    
    // Asegurarse de que la env var NO está definida
    delete (import.meta as TestImportMeta).env.VITE_FIREBASE_AUTH_EMULATOR_HOST;
    
    // Resetear el mock antes de importar
    mockConnectAuthEmulator.mockClear();
    
    // Usar dynamic import con cache busting
    await import('../src/auth/firebaseConfig.js?t=' + Date.now());
    
    // Verificar que connectAuthEmulator NO fue llamado
    expect(mockConnectAuthEmulator).not.toHaveBeenCalled();
    
    // Restaurar env original
    if (originalEnv !== undefined) {
      (import.meta as TestImportMeta).env.VITE_FIREBASE_AUTH_EMULATOR_HOST = originalEnv;
    }
  });
});

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
    mockOnAuthStateChanged.mockImplementation((auth: Auth, callback: (user: User | null) => void) => {
      // Simular que no hay usuario al inicio
      setTimeout(() => callback(null), 0);
      return vi.fn(); // unsubscribe function
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test('test_login_calls_signInWithPopup_with_google_provider', async () => {
    const { AuthProvider, useAuth } = await import('../src/auth/AuthContext.js');
    
    const mockUser: Partial<User> = {
      uid: 'test-uid',
      email: 'test@example.com',
    };
    const mockUserCredential: UserCredential = {
      user: mockUser as User,
      providerId: 'google.com',
      operationType: 'signIn',
    };
    
    mockSignInWithPopup.mockResolvedValue(mockUserCredential);
    mockGetIdToken.mockResolvedValue('fake-id-token');
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ id: '1', uid: 'test-uid', email: 'test@example.com', role: 'admin' }),
    });

    let loginFn: (() => Promise<void>) | undefined;
    
    function TestComponent() {
      const { login } = useAuth();
      loginFn = login;
      return null;
    }

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(loginFn).toBeDefined();
    });

    await loginFn!();

    expect(mockSignInWithPopup).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({})
    );
  });

  test('test_auth_context_sets_role_admin_when_me_returns_admin', async () => {
    const { AuthProvider, useAuth } = await import('../src/auth/AuthContext.js');
    
    const mockUser: Partial<User> = {
      uid: 'admin-uid',
      email: 'admin@example.com',
    };
    
    mockGetIdToken.mockResolvedValue('fake-admin-token');
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ id: '1', uid: 'admin-uid', email: 'admin@example.com', role: 'admin' }),
    });

    // Simular que hay un usuario autenticado
    mockOnAuthStateChanged.mockImplementation((auth: Auth, callback: (user: User | null) => void) => {
      setTimeout(() => callback(mockUser as User), 0);
      return vi.fn();
    });

    let role: string | null | undefined;
    
    function TestComponent() {
      const auth = useAuth();
      role = auth.role;
      return null;
    }

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(role).toBe('admin');
    });

    expect(mockSignOut).not.toHaveBeenCalled();
  });

  test('test_auth_context_calls_signout_when_me_returns_user_role', async () => {
    const { AuthProvider } = await import('../src/auth/AuthContext.js');
    
    const mockUser: Partial<User> = {
      uid: 'user-uid',
      email: 'user@example.com',
    };
    
    mockGetIdToken.mockResolvedValue('fake-user-token');
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ id: '2', uid: 'user-uid', email: 'user@example.com', role: 'user' }),
    });

    // Simular que hay un usuario autenticado
    mockOnAuthStateChanged.mockImplementation((auth: Auth, callback: (user: User | null) => void) => {
      setTimeout(() => callback(mockUser as User), 0);
      return vi.fn();
    });

    render(
      <AuthProvider>
        <div>Test</div>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalled();
    });
  });
});
