import { describe, it, expect } from 'vitest';
import { parseHealthResponse } from '../src/health.js';

describe('mobile health logic', () => {
  it('test_mobile_imports_healthstatus_from_shared', () => {
    const validResponse = {
      status: 'ok',
      version: '0.1.0',
      timestamp: new Date().toISOString(),
      db: 'ok',
    };

    const parsed = parseHealthResponse(validResponse);

    expect(parsed.status).toBe('ok');
    expect(parsed.version).toBe('0.1.0');
    expect(parsed.timestamp).toBeTruthy();
    expect(parsed.db).toBe('ok');
  });

  it('parseHealthResponse throws on invalid data', () => {
    const invalidResponse = {
      status: 'error',
      version: '0.1.0',
    };

    expect(() => parseHealthResponse(invalidResponse)).toThrow();
  });
});
