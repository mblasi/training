import { healthStatusSchema, type HealthStatus } from '@trainia/shared';

export function parseHealthResponse(json: unknown): HealthStatus {
  return healthStatusSchema.parse(json);
}
