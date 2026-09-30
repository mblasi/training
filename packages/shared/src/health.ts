import { z } from 'zod';

export const healthStatusSchema = z.object({
  status: z.enum(['ok', 'degraded']),
  db: z.enum(['ok', 'error']),
  version: z.string(),
  timestamp: z.string(),
});

export type HealthStatus = z.infer<typeof healthStatusSchema>;
