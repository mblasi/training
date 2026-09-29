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
});
