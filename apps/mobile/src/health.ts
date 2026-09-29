import { healthStatusSchema, type HealthStatus } from '@trainia/shared';

export function parseHealthResponse(data: unknown): HealthStatus {
  return healthStatusSchema.parse(data);
}
