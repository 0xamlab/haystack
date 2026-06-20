/**
 * Algenta license-signer Worker (P4) — the ONLY holder of the RS256 private key.
 *
 * The Fly control plane (services/license_signer.py CloudflareWorkerSigner) POSTs already-
 * computed claims here over an Access service token; this Worker enforces a last-gate ABSOLUTE
 * policy (the per-org entitlement was already validated server-side by entitlement_service) and
 * returns a compact RS256 JWS. The private key never leaves the Worker (a Worker Secret).
 *
 * Routes (bound in wrangler.toml to license.algenta.ai):
 *   POST /sign                     Bearer SERVICE_TOKEN, body {"claims": {...}} -> {"token": "<jwt>"}
 *   GET  /.well-known/jwks.json    public JWKS ({keys:[RSA]}) — the runtime verifies licenses by kid
 *
 * Secrets/vars (wrangler secret put / [vars]):
 *   RS256_PRIVATE_KEY  PKCS8 PEM (secret)        SERVICE_TOKEN  Bearer the Fly app holds (secret)
 *   RS256_PUBLIC_KEY   SPKI PEM (var, for JWKS)  KID            key id (var)
 *   LICENSE_ISS=https://license.algenta.ai  LICENSE_AUD=algenta-runtime  (vars)
 *   LICENSES           KV namespace (jti idempotency + monotonic entitlement_version)
 */

const KNOWN_PRODUCTS = new Set(["codna", "cohenta", "decimas", "escrypto", "mission"]);
const WILDCARD = new Set(["*", "all", "any", "ALL", "*.*"]);
const MAX_TTL_SECONDS = 90 * 86400; // no signed license may outlive 90 days
// Absolute sanity ceilings (NOT per-org entitlement — that is enforced server-side). The Worker
// refuses anything wildly out of range as a last line of defense before the private key signs.
const ABS = { named_seat_limit: 100000, active_node_limit: 10000, concurrent_worker_limit: 100000 };

const b64url = (bytes) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

const b64urlJson = (obj) => b64url(new TextEncoder().encode(JSON.stringify(obj)));

function pemToDer(pem) {
  const body = pem.replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  const raw = atob(body);
  const der = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) der[i] = raw.charCodeAt(i);
  return der.buffer;
}

// Constant-time string compare (avoid auth-token timing leaks).
function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function importPrivateKey(pem) {
  return crypto.subtle.importKey(
    "pkcs8",
    pemToDer(pem),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
}

async function signRs256(claims, env) {
  const key = await importPrivateKey(env.RS256_PRIVATE_KEY);
  const header = { alg: "RS256", typ: "JWT", kid: env.KID };
  const signingInput = `${b64urlJson(header)}.${b64urlJson(claims)}`;
  const sig = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(signingInput),
  );
  return `${signingInput}.${b64url(sig)}`;
}

function reject(status, code, message) {
  return new Response(JSON.stringify({ error: { code, message } }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// Last-gate policy. Returns an error string, or null if the claims are acceptable to sign.
function policyError(claims, env) {
  if (!claims || typeof claims !== "object") return "claims must be an object";
  if (claims.ver !== 2) return "only ver:2 licenses are signed by the control plane";
  const iss = env.LICENSE_ISS || "https://license.algenta.ai";
  const aud = env.LICENSE_AUD || "algenta-runtime";
  if (claims.iss && claims.iss !== iss) return `iss must be ${iss}`;
  if (claims.aud && claims.aud !== aud) return `aud must be ${aud}`;
  if (!claims.jti) return "jti required";
  if (!claims.activation_id) return "activation_id required";
  const now = Math.floor(Date.now() / 1000);
  const exp = Number(claims.exp || 0);
  if (!exp || exp <= now) return "exp must be in the future";
  if (exp - now > MAX_TTL_SECONDS) return "exp exceeds the maximum license TTL";
  for (const [field, ceiling] of Object.entries(ABS)) {
    const v = Number(claims[field] || 0);
    if (v < 0 || v > ceiling) return `${field} out of range`;
  }
  const products = claims.products || {};
  for (const [name, grant] of Object.entries(products)) {
    if (!KNOWN_PRODUCTS.has(name)) return `unknown product: ${name}`;
    for (const feat of (grant && grant.features) || []) {
      if (WILDCARD.has(feat)) return "wildcard features are not allowed";
    }
  }
  return null;
}

async function handleSign(request, env) {
  const auth = request.headers.get("authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  if (!env.SERVICE_TOKEN || !timingSafeEqual(token, env.SERVICE_TOKEN)) {
    return reject(401, "unauthorized", "invalid service token");
  }
  let body;
  try {
    body = await request.json();
  } catch {
    return reject(400, "bad_request", "invalid JSON");
  }
  const claims = body && body.claims;
  const err = policyError(claims, env);
  if (err) return reject(422, "policy_violation", err);

  // Idempotency + monotonic entitlement_version via KV (best-effort if KV is bound).
  if (env.LICENSES) {
    const existing = await env.LICENSES.get(`jti:${claims.jti}`);
    if (existing) return Response.json({ token: existing }); // idempotent re-issue
    if (claims.activation_id && claims.entitlement_version != null) {
      const lastRaw = await env.LICENSES.get(`entver:${claims.activation_id}`);
      const last = lastRaw ? Number(lastRaw) : -1;
      if (Number(claims.entitlement_version) < last) {
        return reject(409, "stale_entitlement_version", "entitlement_version regressed");
      }
    }
  }

  const signed = await signRs256({ ...claims, iat: Math.floor(Date.now() / 1000) }, env);

  if (env.LICENSES) {
    const ttl = Math.max(60, Number(claims.exp) - Math.floor(Date.now() / 1000));
    await env.LICENSES.put(`jti:${claims.jti}`, signed, { expirationTtl: ttl });
    if (claims.activation_id && claims.entitlement_version != null) {
      await env.LICENSES.put(`entver:${claims.activation_id}`, String(claims.entitlement_version));
    }
  }
  return Response.json({ token: signed });
}

async function handleJwks(env) {
  if (!env.RS256_PUBLIC_KEY) return Response.json({ keys: [] });
  const pub = await crypto.subtle.importKey(
    "spki",
    pemToDer(env.RS256_PUBLIC_KEY),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    true,
    ["verify"],
  );
  const jwk = await crypto.subtle.exportKey("jwk", pub);
  return Response.json(
    {
      keys: [
        { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: "RS256", use: "sig", kid: env.KID },
      ],
    },
    { headers: { "cache-control": "public, max-age=3600" } },
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/sign") return handleSign(request, env);
    if (request.method === "GET" && url.pathname === "/.well-known/jwks.json") {
      return handleJwks(env);
    }
    return reject(404, "not_found", "no such route");
  },
};
