/** Gateway configuration — all from environment variables. */
import { resolveGatewayApiOrigin } from './privacy.js'

export const config = {
  port:          parseInt(process.env.GATEWAY_PORT       ?? '8080'),
  apiOrigin:     resolveGatewayApiOrigin(process.env),
  redisUrl:      process.env.REDIS_URL                   ?? 'redis://localhost:6379',
  jwtSecret:     process.env.JWT_SECRET                  ?? '',
  metricsSecret: process.env.METRICS_SECRET              ?? '',
  rateLimitWindowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS ?? '60000'),
  /** Per-plan rate limits (requests per window). Override via env. */
  planLimits: {
    free:       parseInt(process.env.RATE_LIMIT_FREE       ?? '60'),
    developer:  parseInt(process.env.RATE_LIMIT_DEVELOPER  ?? '300'),
    pro:        parseInt(process.env.RATE_LIMIT_PRO        ?? '1000'),
    enterprise: parseInt(process.env.RATE_LIMIT_ENTERPRISE ?? '10000'),
  } as Record<string, number>,
} as const
