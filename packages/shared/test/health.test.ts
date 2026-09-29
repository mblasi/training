import { describe, test, expect } from 'vitest';
import { healthStatusSchema } from '../src/index.js';

describe('HealthStatus schema', () => {
  test('test_healthstatus_parse_valid_object', () => {
    const validData = {
      status: 'ok' as const,
      version: '0.1.0',
      timestamp: new Date().toISOString(),
    };

    expect(() => healthStatusSchema.parse(validData)).not.toThrow();
  });

  test('test_healthstatus_rejects_missing_status', () => {
    const invalidData = {};

    expect(() => healthStatusSchema.parse(invalidData)).toThrow();
  });

  test('test_healthstatus_rejects_wrong_status_value', () => {
    const invalidData = {
      status: 'fail',
      version: '0.1.0',
      timestamp: new Date().toISOString(),
    };

    expect(() => healthStatusSchema.parse(invalidData)).toThrow();
  });

  test('test_healthstatus_parse_valid_ok_with_db', () => {
    const validData = {
      status: 'ok' as const,
      version: '0.1.0',
      timestamp: new Date().toISOString(),
      db: 'ok' as const,
    };

    expect(() => healthStatusSchema.parse(validData)).not.toThrow();
  });

  test('test_healthstatus_parse_degraded_with_db_error', () => {
    const validData = {
      status: 'degraded' as const,
      version: '0.1.0',
      timestamp: new Date().toISOString(),
      db: 'error' as const,
    };

    expect(() => healthStatusSchema.parse(validData)).not.toThrow();
  });

  test('test_healthstatus_rejects_missing_db', () => {
    const invalidData = {
      status: 'ok' as const,
      version: '0.1.0',
      timestamp: new Date().toISOString(),
    };

    expect(() => healthStatusSchema.parse(invalidData)).toThrow();
  });

  test('test_healthstatus_rejects_wrong_db_value', () => {
    const invalidData = {
      status: 'ok' as const,
      version: '0.1.0',
      timestamp: new Date().toISOString(),
      db: 'unknown',
    };

    expect(() => healthStatusSchema.parse(invalidData)).toThrow();
  });
});
