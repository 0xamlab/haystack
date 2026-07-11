/** Gateway configuration — all from environment variables. */
import { resolveGatewayApiOrigin } from './privacy.js'

export const config = {
  port:          parseInt(process.env.GATEWAY_PORT       ?? '8080'),
  apiOrigin:     resolveGatewayApiOrigin(process.env),
  redisUrl:      process.env.REDIS_URL                   ?? 'redis://localhost:6379',
  jwtSecret:     process.env.JWT_SECRET                  ?? '',
  metricsSecret: process.env.METRICS_SECRET              ?? '',
  rateLimitWindowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS ?? '60000'),
  /** Generic hosted-plan limits. Algenta and Enterprise use 0 = no request meter. */
  planLimits: {
    free:       parseInt(process.env.RATE_LIMIT_FREE       ?? '60'),
    developer:  parseInt(process.env.RATE_LIMIT_DEVELOPER  ?? '300'),
    pro:        parseInt(process.env.RATE_LIMIT_PRO        ?? '1000'),
    algenta_free: 0,
    algenta_pro:  0,
    algenta_team: 0,
    enterprise: parseInt(process.env.RATE_LIMIT_ENTERPRISE ?? '0'),
  } as Record<string, number>,
} as const
