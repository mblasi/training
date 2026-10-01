import { describe, test, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { User } from 'firebase/auth';
import App from '../src/App';
import { parseHealthResponse } from '../src/health';

// Mock del AuthContext
vi.mock('../src/auth/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    user: { uid: 'test-uid', email: 'admin@example.com' } as Partial<User>,
    role: 'admin',
    login: vi.fn(),
    logout: vi.fn(),
  })),
}));

describe('Admin App', () => {
  test('test_app_renders_trainia_heading', () => {
    render(<App />);
    const heading = screen.getByText('Trainia');
    expect(heading).toBeInTheDocument();
  });

  test('parseHealthResponse parses valid response', () => {
    const validResponse = {
      status: 'ok',
      version: '0.1.0',
      timestamp: new Date().toISOString(),
      db: 'ok',
    };
    const parsed = parseHealthResponse(validResponse);
    expect(parsed.status).toBe('ok');
    expect(parsed.version).toBe('0.1.0');
    expect(parsed.db).toBe('ok');
  });

  test('parseHealthResponse throws on invalid response', () => {
    const invalidResponse = {
      status: 'ok',
      version: '0.1.0',
    };
    expect(() => parseHealthResponse(invalidResponse)).toThrow();
  });

  test('test_app_renders_login_when_not_authenticated', async () => {
    const { useAuth } = await import('../src/auth/AuthContext.js');
    
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      role: null,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(<App />);
    
    // Debe renderizar el componente Login
    const loginElement = screen.getByTestId('login-component');
    expect(loginElement).toBeInTheDocument();
  });

  test('test_app_renders_content_when_authenticated_as_admin', async () => {
    const { useAuth } = await import('../src/auth/AuthContext.js');
    
    vi.mocked(useAuth).mockReturnValue({
      user: { uid: 'admin-uid', email: 'admin@example.com' } as Partial<User> as User,
      role: 'admin',
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(<App />);
    
    // No debe renderizar Login cuando está autenticado
    const loginElement = screen.queryByTestId('login-component');
    expect(loginElement).not.toBeInTheDocument();
    
    // Debe renderizar el heading
    const heading = screen.getByText('Trainia');
    expect(heading).toBeInTheDocument();
  });
});
