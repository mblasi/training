import { describe, test, expect } from 'vitest';
import { requireDatabaseUrl } from '../src/db/env.js';

describe('requireDatabaseUrl', () => {
  test('test_requireDatabaseUrl_returns_url_when_present', () => {
    const env = { DATABASE_URL: 'postgres://user:pass@localhost:5432/db' };
    const result = requireDatabaseUrl(env);
    expect(result).toBe('postgres://user:pass@localhost:5432/db');
  });

  test('test_requireDatabaseUrl_throws_when_missing', () => {
    const env = {};
    expect(() => requireDatabaseUrl(env)).toThrow('DATABASE_URL no definida');
  });

  test('test_requireDatabaseUrl_throws_when_empty_string', () => {
    const env = { DATABASE_URL: '' };
    expect(() => requireDatabaseUrl(env)).toThrow('DATABASE_URL no definida');
  });
});
