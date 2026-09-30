import { describe, test, expect } from 'vitest';
import { createDb } from '../src/db/client.js';

describe('createDb', () => {
  test('test_createDb_returns_pool_and_db', () => {
    const result = createDb('postgres://localhost/test');
    expect(result).toHaveProperty('pool');
    expect(result).toHaveProperty('db');
    expect(result.pool).toBeDefined();
    expect(result.db).toBeDefined();
  });

  test('test_createDb_does_not_connect_on_instantiation', () => {
    // Should not throw even with invalid URL - connection is lazy
    expect(() => createDb('postgres://invalid-host-that-does-not-exist-12345/test')).not.toThrow();
  });
});
