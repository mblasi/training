import { describe, test, expect } from 'vitest';
import { buildApp } from '../src/app.js';
import { healthStatusSchema } from '@trainia/shared';

describe('GET /health', () => {
  test('test_get_health_returns_503_degraded_without_db_client', async () => {
    const app = buildApp();
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });
    
    expect(response.statusCode).toBe(503);
    
    const body = JSON.parse(response.body);
    expect(body.status).toBe('degraded');
    expect(body.db).toBe('error');
  });

  test('test_get_health_body_matches_healthstatus_schema', async () => {
    const app = buildApp();
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });

    const body = JSON.parse(response.body);
    const parsed = healthStatusSchema.parse(body);
    
    expect(parsed.status).toBe('degraded');
    expect(parsed.db).toBe('error');
  });
});
