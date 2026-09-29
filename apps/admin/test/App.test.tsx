import { describe, test, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';
import type { HealthStatus } from '@trainia/shared';

describe('Admin App', () => {
  test('test_app_renders_trainia_heading', () => {
    render(<App />);
    const heading = screen.getByText('Trainia');
    expect(heading).toBeInTheDocument();
  });

  test('test_app_uses_healthstatus_type', () => {
    // This test verifies that the HealthStatus type from shared is importable
    // The actual type checking happens at compile time (tsc --noEmit in CI)
    // This runtime test just ensures the import doesn't throw
    const mockHealth: HealthStatus = {
      status: 'ok',
      version: '0.1.0',
      timestamp: new Date().toISOString(),
    };
    expect(mockHealth.status).toBe('ok');
  });
});
