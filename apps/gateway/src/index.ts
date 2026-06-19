/**
 * Algenta API Gateway — Hono on Node.js 22 LTS
 *
 * Responsibilities:
 *   1. Bearer token validation (Redis cache, < 1ms on cache hit)
 *   2. Rate limiting (Redis sliding window, per plan)
 *   3. Trusted header injection (X-Org-Id, X-Org-Plan → Python API)
 *   4. Reverse proxy to Python FastAPI
 *   5. Prometheus metrics endpoint
 *
 * Environment variables: see src/config.ts
 */
import { Hono }       from 'hono'
import { serve }      from '@hono/node-server'
import { logger }     from 'hono/logger'
import { cors }       from 'hono/cors'
import pino           from 'pino'

import { config }           from './config.js'
import { authMiddleware }    from './auth.js'
import { rateLimitMiddleware, sseRateLimitMiddleware } from './ratelimit.js'
import { proxyToApi }        from './proxy.js'
import { metricsHandler }    from './metrics.js'

const log = pino({ name: 'gateway', level: 'info' })

// ── App ────────────────────────────────────────────────────────────────────────

const app = new Hono()

// ── Middleware ─────────────────────────────────────────────────────────────────

app.use('*', logger())
app.use('*', cors({
  origin:         '*',
  allowMethods:   ['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
  allowHeaders:   ['Content-Type', 'Authorization', 'X-Request-Id'],
  exposeHeaders:  ['X-Request-Id', 'X-Decision-Hash', 'X-Execution-Ms', 'X-Mojo-Ms',
                   'X-RateLimit-Limit', 'X-RateLimit-Remaining'],
  credentials:    true,
}))

// ── Public endpoints (no auth required) ───────────────────────────────────────

/** Health check */
app.get('/health', (c) => c.json({ status: 'ok', service: 'algenta-gateway' }))

/** Prometheus metrics — protected by secret header or loopback */
app.get('/metrics', async (c) => {
  const clientIp = c.req.header('x-forwarded-for') ?? 'unknown'
  const isLocal  = ['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(clientIp)
  const secret   = c.req.header('x-metrics-secret')

  if (!isLocal && (!config.metricsSecret || secret !== config.metricsSecret)) {
    return c.text('Forbidden', 403)
  }
  const metrics = await metricsHandler()
  return c.text(metrics, 200, { 'Content-Type': 'text/plain; version=0.0.4' })
})

// ── Auth + rate limit middleware for all /v1/* routes ─────────────────────────

app.use('/v1/*', authMiddleware)
app.use('/v1/*', rateLimitMiddleware)

// ── SSE streaming — separate connection limiter + per-minute stream rate limit ─
// Must be registered BEFORE the generic /v1/* proxy to intercept /v1/simulate/stream
app.use('/v1/simulate/stream', sseRateLimitMiddleware)

// ── Proxy all /v1/* and /auth/* to Python FastAPI ─────────────────────────────

app.all('/v1/*',   (c) => proxyToApi(c))
app.all('/auth/*', (c) => proxyToApi(c))
app.all('/mcp/*',  (c) => proxyToApi(c))
app.all('/docs*',  (c) => proxyToApi(c))

// ── 404 fallback ───────────────────────────────────────────────────────────────

app.notFound((c) => c.json({ error: { code: 'not_found', message: 'Route not found' } }, 404))

// ── Start ──────────────────────────────────────────────────────────────────────

serve({ fetch: app.fetch, port: config.port }, (info) => {
  log.info({ port: info.port, upstream: config.apiOrigin }, 'gateway started')
})

export default app
