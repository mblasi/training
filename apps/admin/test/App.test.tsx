import { describe, test, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';
import { parseHealthResponse } from '../src/health';

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
});
