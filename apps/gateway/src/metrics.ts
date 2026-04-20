/**
 * Prometheus metrics for the gateway layer.
 */
import { Counter, Histogram, register } from 'prom-client'

export const httpRequestTotal = new Counter({
  name:       'gateway_http_requests_total',
  help:       'Total HTTP requests through the gateway',
  labelNames: ['method', 'path', 'status', 'plan'],
})

export const httpRequestDuration = new Histogram({
  name:       'gateway_http_request_duration_seconds',
  help:       'HTTP request duration (gateway → upstream → client)',
  labelNames: ['method', 'path', 'plan'],
  buckets:    [0.005, 0.010, 0.020, 0.050, 0.100, 0.250, 0.500, 1.0],
})

export const authCacheHits = new Counter({
  name: 'gateway_auth_cache_hits_total',
  help: 'API key Redis cache hits',
})

export const rateLimitHits = new Counter({
  name:       'gateway_rate_limit_exceeded_total',
  help:       'Rate limit exceeded events',
  labelNames: ['plan'],
})

export const metricsHandler = async (): Promise<string> =>
  register.metrics()
