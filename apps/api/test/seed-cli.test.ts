import { describe, test, expect, vi } from 'vitest';
import { main } from '../src/db/seed-cli.js';

describe('seed-cli', () => {
  test('calls runSeed once and ends pool', async () => {
    const mockPool = {
      end: vi.fn().mockResolvedValue(undefined),
    };
    
    const mockDb = {} as never;
    
    const mockCreateDb = vi.fn().mockReturnValue({
      db: mockDb,
      pool: mockPool,
    });
    
    const mockRunSeed = vi.fn().mockResolvedValue(undefined);
    
    const env = { DATABASE_URL: 'postgres://test/db' };
    
    await main(env, { createDb: mockCreateDb, runSeed: mockRunSeed });
    
    expect(mockCreateDb).toHaveBeenCalledWith('postgres://test/db');
    expect(mockRunSeed).toHaveBeenCalledWith(mockDb);
    expect(mockRunSeed).toHaveBeenCalledTimes(1);
    expect(mockPool.end).toHaveBeenCalledTimes(1);
  });
  
  test('throws "DATABASE_URL no definida" when missing', async () => {
    const mockCreateDb = vi.fn();
    const mockRunSeed = vi.fn();
    
    await expect(
      main({}, { createDb: mockCreateDb, runSeed: mockRunSeed })
    ).rejects.toThrow('DATABASE_URL no definida');
    
    expect(mockCreateDb).not.toHaveBeenCalled();
    expect(mockRunSeed).not.toHaveBeenCalled();
  });
  
  test('ends pool even if runSeed fails', async () => {
    const mockPool = {
      end: vi.fn().mockResolvedValue(undefined),
    };
    
    const mockDb = {} as never;
    
    const mockCreateDb = vi.fn().mockReturnValue({
      db: mockDb,
      pool: mockPool,
    });
    
    const mockRunSeed = vi.fn().mockRejectedValue(new Error('Seed failed'));
    
    const env = { DATABASE_URL: 'postgres://test/db' };
    
    await expect(
      main(env, { createDb: mockCreateDb, runSeed: mockRunSeed })
    ).rejects.toThrow('Seed failed');
    
    expect(mockPool.end).toHaveBeenCalledTimes(1);
  });
});
