# Algenta control plane — edge + signer (P4) owner runbook

Everything here is **config**; applying it provisions real resources and is **owner-only**. The
control-plane app itself (the `ALGENTA_SERVICE_ROLE=control_plane` role, `fly.control-plane.toml`)
shipped in P4a; this directory adds the Cloudflare edge (algenta.ai zone) + the RS256 license
signer Worker.

## 1. Fly control plane (its OWN Postgres — never codna's)
```
fly apps create algenta-control-plane
fly postgres create --name algenta-control-plane-pg --region iad
fly postgres attach algenta-control-plane-pg -a algenta-control-plane
fly secrets set -a algenta-control-plane \
  DATABASE_URL='postgresql+asyncpg://…@…/…' DATABASE_URL_SYNC='postgresql://…@…/…' \
  JWT_SECRET=… STRIPE_SECRET_KEY=… STRIPE_WEBHOOK_SECRET=… \
  STRIPE_PRICE_DEVELOPER=… STRIPE_PRICE_PRO=… METRICS_SECRET=… REDIS_URL=…
flyctl deploy -c fly.control-plane.toml -i ghcr.io/thyn-ai/algenta/api:<git-sha>
fly certs add api.algenta.ai -a algenta-control-plane   # do BEFORE Cloudflare proxies (orange)
```
The `release_command` runs `alembic upgrade head` against the control plane's OWN DB.

## 2. License signer Worker (holds the RS256 private key — NOT on Fly)
```
# generate the RS256 keypair (PKCS8 private + SPKI public)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out cp_priv.pem
openssl rsa -in cp_priv.pem -pubout -out cp_pub.pem

cd infra/cloudflare/license-signer
wrangler kv namespace create LICENSES        # paste the id into wrangler.toml
wrangler secret put RS256_PRIVATE_KEY < cp_priv.pem
wrangler secret put SERVICE_TOKEN            # a strong random token the Fly app will hold
wrangler secret put RS256_PUBLIC_KEY < cp_pub.pem   # (or set as a [var])
wrangler deploy                              # binds license.algenta.ai/sign + /.well-known/jwks.json
```
Then point the Fly control plane at the Worker (cf_worker backend — the private key stays in the
Worker):
```
fly secrets set -a algenta-control-plane \
  LICENSE_SIGNER_BACKEND=cf_worker \
  LICENSE_SIGNER_URL=https://license.algenta.ai/sign \
  LICENSE_SIGNER_AUTH_TOKEN=<the SERVICE_TOKEN above> \
  LICENSE_SIGNER_KID=algenta-license-2026 \
  LICENSE_SIGNER_WORKER_PUBLIC_KEY="$(cat cp_pub.pem)"   # so /.well-known/jwks.json publishes it
```
The Worker enforces last-gate policy (ver:2, known products, no wildcard features, caps ≤ sanity
ceilings, exp ≤ 90d, unique jti + monotonic entitlement_version via KV) and signs RS256+kid. The
runtime verifies licenses by kid via JWKS (Worker's or the control plane's `/.well-known/jwks.json`,
both publish the same key). Contract proven by `tests/test_license_signer_worker_contract.py`.

## 3. Cloudflare edge (algenta.ai zone)
```
cd infra/cloudflare/algenta-control-plane
export TF_VAR_cloudflare_api_token=… TF_VAR_cloudflare_account_id=… TF_VAR_algenta_zone_id=…
tofu init && tofu apply   # dns + Full-Strict TLS + cache (bypass dynamic, cache JWKS/CRL) + WAF
```
Cert ordering: deploy with `control_plane_proxied=false` (grey) until `fly certs show` is Ready,
then set `true` (orange) and re-apply (`tls.tf` flips Full-Strict).

## 4. Smoke
```
curl https://api.algenta.ai/v1/health            # 200 (liveness)
curl https://api.algenta.ai/v1/control-plane/meta # {"role":"control_plane",...}
curl https://api.algenta.ai/.well-known/jwks.json # the signer public key
curl -X POST https://api.algenta.ai/v1/simulate   # 404 — engine is NOT on the control plane
```

P5 (held) flips ver:2 issuance authoritative + pins iss/aud + RS256-only CRL verification.
