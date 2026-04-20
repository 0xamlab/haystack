# Algenta Backend — Full Go-Live Gap Analysis
> Generated against: TASK_BREAKDOWN_ALL_PHASES.md, UNIVERSAL_DECISION_ENGINE_ARCHITECTURE.md, Universal Decision Engine — Enterprise.md

---

## STATUS SUMMARY

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Open Core Foundation | ✅ Done |
| Phase 2 | Decision APIs + Auth | ✅ Done |
| Phase 3 | Async Platform + Webhooks | ✅ Done |
| Phase 4 | Integrations + SDKs | ✅ Done |
| Phase 5A | Docs Shell + Auth-Gated Portal | ✅ Done |
| Phase 5B | Full Portal + Billing | ~85% Done |
| Phase 6 | Launch Readiness | ❌ Not started |
| Phase 7 | Enterprise Hardening | ~60% Done |
| Phase 8 | Optimized Mojo Runtime | ~70% Done |

---

## GAP 1 — Stripe Usage Metering NOT Wired

### What plan requires (5B.2.8):
After each simulation, push metered usage to Stripe async. On `invoice.paid`, reset org's usage counter.

### Current state:
- `quota_service.py` increments a DB counter
- `stripe_service.py` has `create_checkout_session` and `portal` — but NO usage metering call
- `billing.py` webhook handler catches `invoice.paid` but does NOT reset the DB usage counter

### What to implement:
1. In `simulation_service.py` after successful run → call `stripe.UsageRecord.create()` async
2. In `billing.py` webhook `invoice.paid` handler → `await reset_monthly_usage(org_id)`
3. In `billing.py` webhook `customer.subscription.updated` → update org plan in DB

---

## GAP 2 — Redis API Key Caching NOT Implemented

### What plan requires (1.5.4):
Cache `hash → {org_id, key_id, plan}` in Redis for 5 min TTL after first auth.

### Current state:
- `auth_service.py` `verify_api_key()` hits Postgres on EVERY request
- Redis client is imported but caching is not used

### Impact:
Every authenticated API call = 1 DB query. Under load (100 req/s) = 100 DB queries/sec just for auth. This will become the bottleneck.

### What to implement:
1. After DB lookup → `await redis.set(f"apikey:{hashed}", json.dumps({...}), ex=300)`
2. Before DB lookup → check `await redis.get(f"apikey:{hashed}")`

---

## GAP 3 — Email Verification NOT Implemented

### What plan requires (signup flow):
After signup → send verification email → user must verify before accessing API.

### Current state:
- `email_service.py` exists with `send_verification_email()` stub
- `auth.py` `/auth/signup` creates user but never calls email service
- No `GET /auth/verify?token=...` endpoint exists
- Users can use unverified accounts immediately

### What to implement:
1. Generate verification token on signup → store in DB (users.email_verification_token)
2. `POST /auth/signup` → call `send_verification_email(email, token)`
3. `GET /auth/verify?token=X` → mark user verified
4. Auth middleware: if user not verified → return 403 with "Please verify your email"

---

## GAP 4 — Password Reset NOT Implemented

### What plan requires:
Standard password reset flow (email-based).

### Current state:
- No `POST /auth/forgot-password` endpoint
- No `POST /auth/reset-password` endpoint
- `email_service.py` has no reset email function

### What to implement:
1. `POST /auth/forgot-password` → generate reset token → email link
2. `POST /auth/reset-password` → validate token → update password_hash
3. Token stored in DB with expiry (15 min)

---

## GAP 5 — Quota Alert Emails NOT Wired

### What plan requires (5B.2.10):
Send email at 80% and 100% of monthly quota.

### Current state:
- `quota_service.py` checks quota but never triggers email
- `email_service.py` has no quota alert email function

### What to implement:
1. In `quota_service.py` after incrementing → check if crossed 80% or 100%
2. If crossed → `await email_service.send_quota_alert(org.email, pct, used, limit)`
3. Track alert sent (don't send 500 times) with Redis key `quota_alert:{org_id}:80`

---

## GAP 6 — Result Object Storage NOT Implemented

### What plan requires (architecture §3.2):
Large simulation results should be stored in object storage (MinIO/S3), not inline in Postgres.

### Current state:
- MinIO is in docker-compose but NOT connected to anything
- All simulation results stored inline in `simulation_runs.result_json` (Text column)
- For 1M-run simulations this column can be 10MB+ per row

### What to implement:
1. In `simulation_service.py` after engine run → if result_json > 100KB:
   - Upload to MinIO bucket `simulation-results/{org_id}/{run_id}.json`
   - Store only `result_url` in DB, not full JSON
2. In `GET /v1/runs/{id}` — fetch from MinIO if `result_url` set
3. Pre-signed URL for direct download

---

## GAP 7 — Analytics Endpoint Needs Real SQL

### What plan requires:
`GET /v1/analytics?days=30` returns real aggregated data from DB.

### Current state:
- `runs.py` has `/v1/analytics` but it does count queries in Python (loads all runs to memory!)
- For orgs with 10k+ runs this is O(n) in memory

### What to implement:
Replace Python aggregation with real SQL:
```sql
SELECT 
  DATE(created_at) as date,
  COUNT(*) as count,
  AVG(EXTRACT(EPOCH FROM (updated_at - created_at))*1000) as avg_latency_ms
FROM simulation_runs
WHERE org_id = :org_id AND created_at >= NOW() - INTERVAL ':days days'
GROUP BY DATE(created_at)
ORDER BY date
```

---

## GAP 8 — Rate Limiting NOT Implemented at API Level

### What plan requires (§11.6):
Per-API-key rate limiting: e.g., 100 req/min on free, 5000 req/min on developer.

### Current state:
- Quota (monthly) is enforced via DB counter
- Per-minute rate limiting: NOTHING in place
- Redis is available but no rate limiter middleware

### What to implement:
1. `middleware/rate_limit.py` using sliding window in Redis:
   - Key: `ratelimit:{key_id}:{minute_bucket}`
   - Increment + expire(60)
   - If > limit → return 429 with `Retry-After` header
2. Limits from `LimitsResponse.rate_limit_per_minute`

---

## GAP 9 — CI/CD Pipeline MISSING

### What plan requires (Phase 6):
Auto-deploy on merge. Tests run on every PR.

### Current state:
- No `.github/workflows/` directory
- No CI configuration of any kind

### What to implement:
```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test:
    - checkout
    - setup python 3.12
    - pip install -r requirements-dev.txt
    - pytest tests/
  
  # On merge to main:
  deploy:
    - docker build + push to registry
    - deploy to cloud run / ECS
```

---

## GAP 10 — Docker Production Hardening

### What plan requires (§13):
Non-root user, minimal image, secrets via env, health checks.

### Current state:
- `Dockerfile.api` and `Dockerfile.worker` exist
- NOT multi-stage (includes dev deps in prod image)
- NOT non-root user
- No production env configuration

### What to implement:
```dockerfile
# Multi-stage: builder → slim runtime
FROM python:3.12-slim AS builder
# install deps
FROM python:3.12-slim AS runtime
RUN addgroup --system app && adduser --system --ingroup app app
COPY --from=builder /app /app
USER app
HEALTHCHECK --interval=30s --timeout=10s CMD curl /v1/health
```

---

## GAP 11 — Load Testing NOT Done

### What plan requires (Phase 6.2.4):
100 req/s on `/v1/simulate`, p95 < 500ms.

### Current state:
- No `tests/load/` directory
- Never been load tested
- Unknown performance under concurrent load

### What to implement:
```python
# tests/load/locustfile.py
class SimulateUser(HttpUser):
    @task
    def simulate(self):
        self.client.post("/v1/simulate", 
            json={...},
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
```

---

## GAP 12 — SSO / SAML (Enterprise Phase 7)

### What plan requires (7.1):
SAML 2.0 SP, OIDC adapter, per-org IdP config, enforce SSO for enterprise.

### Current state:
- Nothing implemented
- Users only authenticate via email/password

### What to implement:
1. `python-saml` or `authlib` dependency
2. Org-level SSO config table: `sso_configs(org_id, idp_entity_id, metadata_xml, ...)`
3. `POST /auth/saml/callback` handler
4. `GET /auth/sso?org=slug` → redirect to IdP

---

## GAP 13 — OpenAPI Spec Export for Docs

### What plan requires (§7.1 Docs):
API reference auto-generated from OpenAPI. Mintlify or Docusaurus OpenAPI plugin.

### Current state:
- FastAPI auto-generates OpenAPI at `/openapi.json`
- Docs site (Docusaurus) has manually-written reference pages
- NOT auto-generated from actual OpenAPI spec

### What to implement:
1. Export `GET /openapi.json` to `apps/docs/api-spec.json` in CI
2. Configure `docusaurus-plugin-openapi-docs`
3. Auto-regenerate API reference on each deploy

---

## GAP 14 — Subscription Model in DB

### What plan requires (architecture data model):
`subscriptions` table with Stripe subscription ID, status, current_period_end.

### Current state:
- `organizations.plan` is just an enum string ("free", "developer")
- No `subscriptions` table
- No `stripe_subscription_id` stored
- Stripe webhook `customer.subscription.updated` has nowhere to store subscription details

### What to implement:
1. Migration: `subscriptions(id, org_id, stripe_subscription_id, plan, status, current_period_start, current_period_end)`
2. Webhook `customer.subscription.created/updated/deleted` → upsert subscription record
3. `GET /billing/info` → return subscription details

---

## PRIORITY ORDER FOR GO-LIVE

### Must-have before first paying customer:
1. **GAP 2** — Redis API key caching (performance critical)
2. **GAP 3** — Email verification (security/fraud prevention)
3. **GAP 4** — Password reset (users will be locked out)
4. **GAP 1** — Stripe usage metering (revenue depends on this)
5. **GAP 14** — Subscription model in DB (Stripe webhooks incomplete without it)
6. **GAP 8** — Per-minute rate limiting (prevent abuse)
7. **GAP 10** — Production Docker hardening (security)
8. **GAP 9** — CI/CD pipeline (deployment reliability)

### Important but not day-1 blockers:
9. **GAP 5** — Quota alert emails
10. **GAP 7** — Analytics real SQL (performance at scale)
11. **GAP 6** — Object storage for large results
12. **GAP 13** — Auto-generated API docs

### Enterprise / later phase:
13. **GAP 11** — Load testing
14. **GAP 12** — SSO/SAML

---

## IMPLEMENTATION ORDER (Next 2 Weeks)

### Day 1-2: Auth & Security
- Redis API key caching
- Email verification flow (signup → verify)
- Password reset flow

### Day 3-4: Billing & Subscriptions  
- `subscriptions` DB table + migration
- Stripe webhook: update subscription in DB
- Usage metering push to Stripe
- Quota alert emails

### Day 5-6: Performance & Production
- Per-minute rate limiting with Redis sliding window
- Analytics SQL aggregation (replace Python loop)
- Production Docker hardening (multi-stage, non-root)

### Day 7-8: DevOps
- GitHub Actions CI/CD pipeline
- Environment config for prod vs dev
- Object storage integration (MinIO → simulation results)

### Day 9-10: Enterprise & Docs
- Auto-generated API reference from OpenAPI
- Load test setup with Locust
- Self-hosting docs update with node registration API
