import { describe, test, expect } from 'vitest';
import { requireFirebaseProjectId } from '../src/auth/env.js';

describe('requireFirebaseProjectId', () => {
  test('test_requireFirebaseProjectId_returns_id_when_present', () => {
    const env = { FIREBASE_PROJECT_ID: 'demo-trainia' };
    const result = requireFirebaseProjectId(env);
    expect(result).toBe('demo-trainia');
  });

  test('test_requireFirebaseProjectId_throws_when_missing', () => {
    const env = {};
    expect(() => requireFirebaseProjectId(env)).toThrow('FIREBASE_PROJECT_ID no definido');
  });

  test('test_requireFirebaseProjectId_throws_when_empty_string', () => {
    const env = { FIREBASE_PROJECT_ID: '' };
    expect(() => requireFirebaseProjectId(env)).toThrow('FIREBASE_PROJECT_ID no definido');
  });
});
