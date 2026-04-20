/**
 * Reverse proxy — forwards requests to Python FastAPI.
 * Adds X-Org-Id and X-Org-Plan trusted headers so Python doesn't re-auth.
 */
import type { Context } from 'hono'
import { config } from './config.js'
import type { AuthInfo } from './auth.js'

export async function proxyToApi(c: Context): Promise<Response> {
  const auth   = c.get('auth') as AuthInfo | undefined
  const url     = new URL(c.req.url)
  const target  = `${config.apiOrigin}${url.pathname}${url.search}`

  // Copy original headers, add trusted org headers
  const headers = new Headers(c.req.raw.headers)
  if (auth) {
    headers.set('X-Org-Id',    auth.orgId)
    headers.set('X-Org-Plan',  auth.plan)
    headers.set('X-Org-Email', auth.email)
  }
  // Remove hop-by-hop headers
  headers.delete('host')
  headers.delete('connection')
  headers.delete('transfer-encoding')

  const body = c.req.method !== 'GET' && c.req.method !== 'HEAD'
    ? await c.req.arrayBuffer()
    : undefined

  const upstream = await fetch(target, {
    method:  c.req.method,
    headers,
    body,
    // @ts-expect-error Node 22 fetch
    duplex: 'half',
  })

  // Forward upstream response with all headers
  const respHeaders = new Headers(upstream.headers)
  respHeaders.delete('connection')
  respHeaders.delete('transfer-encoding')

  return new Response(upstream.body, {
    status:  upstream.status,
    headers: respHeaders,
  })
}
