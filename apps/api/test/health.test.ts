import { describe, test, expect, vi } from 'vitest';
import { buildApp } from '../src/app.js';
import { healthStatusSchema } from '@trainia/shared';

describe('GET /health', () => {
  test('test_get_health_returns_200_with_db_ok', async () => {
    const mockPool = {
      query: vi.fn().mockResolvedValue({ rows: [{ '?column?': 1 }] }),
    };
    const mockDb = { pool: mockPool };
    const mockAuth = { verifyIdToken: vi.fn() };
    
    const app = buildApp({ db: mockDb as never, auth: mockAuth, adminEmails: [] });
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });
    
    expect(response.statusCode).toBe(200);
    
    const body = JSON.parse(response.body);
    expect(body.status).toBe('ok');
    expect(body.db).toBe('ok');
    expect(mockPool.query).toHaveBeenCalledWith('SELECT 1');
  });

  test('test_get_health_returns_503_when_db_fails', async () => {
    const mockPool = {
      query: vi.fn().mockRejectedValue(new Error('Connection refused')),
    };
    const mockDb = { pool: mockPool };
    const mockAuth = { verifyIdToken: vi.fn() };
    
    const app = buildApp({ db: mockDb as never, auth: mockAuth, adminEmails: [] });
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });
    
    expect(response.statusCode).toBe(503);
    
    const body = JSON.parse(response.body);
    expect(body.status).toBe('degraded');
    expect(body.db).toBe('error');
  });

  test('test_get_health_returns_503_on_timeout', async () => {
    const mockPool = {
      query: vi.fn().mockImplementation(() => new Promise(() => {})), // never resolves
    };
    const mockDb = { pool: mockPool };
    const mockAuth = { verifyIdToken: vi.fn() };
    
    process.env.DB_HEALTH_TIMEOUT_MS = '1';
    const app = buildApp({ db: mockDb as never, auth: mockAuth, adminEmails: [] });
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });
    delete process.env.DB_HEALTH_TIMEOUT_MS;
    
    expect(response.statusCode).toBe(503);
    
    const body = JSON.parse(response.body);
    expect(body.status).toBe('degraded');
    expect(body.db).toBe('error');
  });

  test('test_get_health_body_matches_healthstatus_schema', async () => {
    const mockPool = {
      query: vi.fn().mockResolvedValue({ rows: [{ '?column?': 1 }] }),
    };
    const mockDb = { pool: mockPool };
    const mockAuth = { verifyIdToken: vi.fn() };
    
    const app = buildApp({ db: mockDb as never, auth: mockAuth, adminEmails: [] });
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });

    const body = JSON.parse(response.body);
    const parsed = healthStatusSchema.parse(body);
    
    expect(parsed.status).toBe('ok');
    expect(parsed.db).toBe('ok');
  });
});
