/**
 * Bearer token validation middleware.
 *
 * Extracts the Bearer token from Authorization header.
 * Checks against Redis cache (API key lookup, 5-min TTL).
 * Falls through to Python API for cache misses (sets cache on success).
 *
 * Sets ctx.var.orgId and ctx.var.plan so downstream middleware can use them.
 */
import type { Context, Next } from 'hono'
import { getRedis } from './redis.js'
import { config } from './config.js'
import pino from 'pino'

const log = pino({ name: 'gateway:auth' })

const KEY_CACHE_TTL = 300  // 5 minutes

export interface AuthInfo {
  orgId: string
  plan:  string
  email: string
}

/** Extract Bearer token from Authorization header. Returns null if absent/malformed. */
export function extractBearer(authHeader: string | undefined): string | null {
  if (!authHeader) return null
  const [scheme, token] = authHeader.split(' ')
  return scheme?.toLowerCase() === 'bearer' && token ? token : null
}

/**
 * Validate the Bearer token.
 * Returns AuthInfo on success, null on failure.
 * Uses Redis cache to avoid a DB hit on every request.
 */
export async function validateToken(token: string): Promise<AuthInfo | null> {
  const redis = getRedis()
  const cacheKey = `gw:auth:${Buffer.from(token).toString('base64').slice(0, 32)}`

  // Check Redis cache first
  try {
    const cached = await redis.get(cacheKey)
    if (cached) {
      return JSON.parse(cached) as AuthInfo
    }
  } catch {
    // Redis unavailable — fall through to API validation
  }

  // Cache miss — validate via Python API
  try {
    const res = await fetch(`${config.apiOrigin}/v1/me`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type':  'application/json',
      },
    })
    if (!res.ok) return null

    const body = await res.json() as {
      org:  { id: string; plan: string }
      user: { email: string }
    }

    const info: AuthInfo = {
      orgId: body.org.id,
      plan:  body.org.plan,
      email: body.user.email,
    }

    // Cache for 5 minutes
    try {
      await redis.set(cacheKey, JSON.stringify(info), 'EX', KEY_CACHE_TTL)
    } catch { /* ignore cache write failure */ }

    return info
  } catch (err) {
    log.error({ err }, 'auth validation failed')
    return null
  }
}

/** Hono middleware: authenticate request, set c.var.auth */
export async function authMiddleware(c: Context, next: Next) {
  const token = extractBearer(c.req.header('Authorization'))
  if (!token) {
    return c.json({
      error: {
        code:    'authentication_required',
        message: 'Authorization: Bearer <key> header required',
      }
    }, 401)
  }

  const auth = await validateToken(token)
  if (!auth) {
    return c.json({
      error: {
        code:    'invalid_api_key',
        message: 'The API key provided is invalid or has been revoked.',
      }
    }, 401)
  }

  c.set('auth', auth)
  return next()
}
