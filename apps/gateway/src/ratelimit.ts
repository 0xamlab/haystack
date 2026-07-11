/**
 * Redis sliding-window rate limiter.
 *
 * Key: ratelimit:{orgId}:{YYYY-MM-DDTHH:MM}
 * TTL: 70 seconds (covers full minute window + buffer)
 *
 * SSE connections are long-lived — they hold a server process and a Mojo worker
 * for the duration of the simulation (up to 60 seconds for 1M runs).
 * A separate concurrent-connection counter prevents resource exhaustion.
 *
 * Algenta plans do not have request-volume quotas. Their SSE concurrency follows the licensed
 * worker count because each active stream occupies a worker. Generic hosted plans retain their
 * configurable abuse-protection limits.
 *
 * Also enforces a per-minute request limit on /v1/simulate/stream
 * (lower than regular, since each request is expensive).
 */
import { getRedis } from './redis.js'
import { config } from './config.js'
import type { Context, Next } from 'hono'
import type { AuthInfo } from './auth.js'

function minuteKey(orgId: string): string {
  const now = new Date()
  const ts  = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}T${String(now.getUTCHours()).padStart(2, '0')}:${String(now.getUTCMinutes()).padStart(2, '0')}`
  return `ratelimit:${orgId}:${ts}`
}

/** Concurrent SSE connection key. Value = current open connection count. */
function sseKey(orgId: string): string {
  return `sse_conns:${orgId}`
}

/** Max concurrent SSE connections per plan. */
const SSE_CONN_LIMITS: Record<string, number> = {
  free:         parseInt(process.env.SSE_LIMIT_FREE         ?? '1'),
  developer:    parseInt(process.env.SSE_LIMIT_DEVELOPER    ?? '3'),
  pro:          parseInt(process.env.SSE_LIMIT_PRO          ?? '10'),
  algenta_free: parseInt(process.env.SSE_LIMIT_ALGENTA_FREE ?? '1'),
  algenta_pro:  parseInt(process.env.SSE_LIMIT_ALGENTA_PRO  ?? '5'),
  algenta_team: parseInt(process.env.SSE_LIMIT_ALGENTA_TEAM ?? '20'),
  enterprise:   parseInt(process.env.SSE_LIMIT_ENTERPRISE   ?? '0'),
}

/** Per-minute request limit for /v1/simulate/stream (much lower than regular). */
const SSE_RATE_LIMITS: Record<string, number> = {
  free:         parseInt(process.env.SSE_RATE_FREE       ?? '2'),
  developer:    parseInt(process.env.SSE_RATE_DEVELOPER  ?? '10'),
  pro:          parseInt(process.env.SSE_RATE_PRO        ?? '30'),
  algenta_free: 0,
  algenta_pro:  0,
  algenta_team: 0,
  enterprise:   parseInt(process.env.SSE_RATE_ENTERPRISE ?? '0'),
}

export function sseConnectionLimit(plan: string): number {
  return SSE_CONN_LIMITS[plan] ?? SSE_CONN_LIMITS.free
}

export async function checkRateLimit(
  orgId: string,
  plan: string,
): Promise<{ allowed: boolean; remaining: number; limit: number }> {
  const limit = config.planLimits[plan] ?? config.planLimits.free
  if (limit === 0) return { allowed: true, remaining: -1, limit }

  try {
    const redis = getRedis()
    const key   = minuteKey(orgId)
    const count = await redis.incr(key)
    if (count === 1) await redis.expire(key, 70)

    const remaining = Math.max(0, limit - count)
    return { allowed: count <= limit, remaining, limit }
  } catch {
    // Redis unavailable — fail open
    return { allowed: true, remaining: -1, limit }
  }
}

/**
 * Check and acquire an SSE connection slot.
 * Returns { allowed, current, limit }.
 * Caller MUST call releaseSSESlot() when the SSE connection closes.
 */
export async function acquireSSESlot(
  orgId: string,
  plan: string,
): Promise<{ allowed: boolean; current: number; limit: number }> {
  const connLimit = sseConnectionLimit(plan)
  const rateLimit = SSE_RATE_LIMITS[plan] ?? SSE_RATE_LIMITS.free

  if (connLimit === 0 && rateLimit === 0) {
    return { allowed: true, current: 0, limit: 0 }
  }

  try {
    const redis   = getRedis()
    if (rateLimit > 0) {
      const rateKey = `sse_rate:${orgId}:${minuteKey(orgId).split(':')[2]}`
      const rateCount = await redis.incr(rateKey)
      if (rateCount === 1) await redis.expire(rateKey, 70)
      if (rateCount > rateLimit) {
        return { allowed: false, current: rateCount, limit: rateLimit }
      }
    }

    if (connLimit === 0) return { allowed: true, current: 0, limit: 0 }

    // Concurrent connections consume licensed worker capacity.
    const connKey = sseKey(orgId)
    const current = await redis.incr(connKey)
    // Connection TTL = 120s (generous — SSE sessions don't exceed 2 min for 1M run)
    await redis.expire(connKey, 120)

    if (current > connLimit) {
      // Revert the increment since we're rejecting
      await redis.decr(connKey)
      return { allowed: false, current: current - 1, limit: connLimit }
    }

    return { allowed: true, current, limit: connLimit }
  } catch {
    // Redis unavailable — fail open
    return { allowed: true, current: 0, limit: connLimit }
  }
}

/** Release an SSE connection slot when the stream closes. */
export async function releaseSSESlot(orgId: string): Promise<void> {
  try {
    const redis = getRedis()
    const key   = sseKey(orgId)
    const val   = await redis.decr(key)
    // Ensure we never go negative (e.g. after a Redis flush)
    if (val < 0) await redis.setex(key, 120, '0')
  } catch {
    // Ignore — worst case the slot leaks until TTL
  }
}

/** Hono middleware: enforce rate limit using auth info from previous middleware. */
export async function rateLimitMiddleware(c: Context, next: Next) {
  const auth = c.get('auth') as AuthInfo | undefined
  if (!auth) return next()  // Let auth middleware handle unauthenticated requests

  const { allowed, remaining, limit } = await checkRateLimit(auth.orgId, auth.plan)

  if (limit > 0) {
    c.header('X-RateLimit-Limit',     String(limit))
    c.header('X-RateLimit-Remaining', String(remaining))
  }

  if (!allowed) {
    return c.json({
      error: {
        code:    'rate_limit_exceeded',
        message: `Rate limit exceeded. Max ${limit} requests/minute for ${auth.plan} plan.`,
        limit,
        retry_after_seconds: 60,
      }
    }, 429, { 'Retry-After': '60' })
  }

  return next()
}

/**
 * Hono middleware for /v1/simulate/stream — enforces:
 *   1. Per-minute stream request rate limit (lower than regular)
 *   2. Concurrent connection limit per org
 *
 * Also proxies response as a streaming pass-through, releasing the SSE slot
 * after the stream body finishes.
 */
export async function sseRateLimitMiddleware(c: Context, next: Next) {
  const auth = c.get('auth') as AuthInfo | undefined
  if (!auth) return next()

  const { allowed, current, limit } = await acquireSSESlot(auth.orgId, auth.plan)

  if (limit > 0) {
    c.header('X-SSE-Connections-Current', String(current))
    c.header('X-SSE-Connections-Limit',   String(limit))
  }

  if (!allowed) {
    return c.json({
      error: {
        code:    'sse_limit_exceeded',
        message: `Concurrent stream limit reached (${limit} active connections for ${auth.plan} plan). ` +
                 `Wait for an existing stream to complete or upgrade your plan.`,
        current,
        limit,
      }
    }, 429, { 'Retry-After': '30' })
  }

  // Proceed to the upstream SSE proxy, then release slot when done
  await next()

  // Release slot after response completes (body fully consumed by client)
  // Use a detached microtask so we don't block the response
  const orgId = auth.orgId
  if (limit > 0) {
    Promise.resolve().then(() => releaseSSESlot(orgId)).catch(() => {})
  }

  return
}
