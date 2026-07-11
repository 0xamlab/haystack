---
sidebar_position: 99
---

# Changelog

## v1.0.0 — 2026-03 (Current)

### Phase 5B — Hosted Account Interface + Billing
- **Hosted account interface** — login, dashboard, API keys, playground, usage, billing, settings
- **Stripe billing integration** — checkout sessions, customer portal, webhook handler, plan upgrades
- **Generic hosted-plan quota alerts** — Algenta per-device editions remain unmetered
- **Welcome email** on signup with quickstart snippet
- Billing endpoints: `POST /v1/billing/checkout`, `POST /v1/billing/portal`, `GET /v1/billing/info`, `POST /v1/billing/webhook`
- 223 unit tests total

### Phase 5A — Documentation Set + Rate Limiting + Usage Recording
- **Documentation set** under `apps/docs/docs/` — quickstart, API reference, integration guides
- **Named endpoint abuse controls** — Redis counters for authentication and other narrow surfaces
- **Generic hosted-plan quota enforcement** — not applied to Algenta per-device editions
- **Local activity records** — `usage_records` table, `UsageRecord` model, migration 0004
- `GET /v1/usage` reads customer-owned activity records for audit and capacity planning

### Phase 4 — Integrations + SDKs
- **Python SDK** (`packages/python-sdk/`) — sync + async client, Pydantic models, typed exceptions
- **TypeScript SDK** (`packages/ts-sdk/`) — fetch-based, globalThis-safe env access
- **CLI** (`apps/cli/`) — `simulate`, `recommend`, `score`, `batch`, `compare`, `jobs` commands
- ChatGPT Actions YAML, LangGraph tool, n8n workflow, Power Automate connector, Zapier + Make guides

### Phase 3 — Async Jobs + Webhooks
- Async jobs with Dramatiq (`POST /v1/jobs`, polling, result, cancel)
- HMAC-SHA256 webhook delivery with exponential backoff
- Job state machine: queued → validating → running → completed/failed/cancelled/expired
- `POST /v1/webhooks/test` endpoint

### Phase 2 — Decision APIs + Auth
- `POST /v1/recommend` — pick best action from multiple options
- `POST /v1/score` — score a single scenario (0.0–1.0)
- `POST /v1/batch` — run multiple simulations in one request
- `POST /v1/compare` — compare named scenarios head-to-head
- `POST /auth/signup`, `POST /auth/login`
- Account endpoints: `/v1/me`, `/v1/usage`, `/v1/limits`, `/v1/api-keys`, `/v1/templates`, `/v1/distributions`
- Prometheus metrics at `/metrics`

### Phase 1 — Core Foundation
- FastAPI application with lifespan, CORS, RequestID, structured logging
- Monte Carlo engine (Python adapter with Mojo interface contract)
- `POST /v1/simulate` — Auto Mode + Expert Mode
- Alembic migrations (0001: initial schema with 4 tables + enums)
- Multi-tenant: organizations, users, API keys, simulation runs
- SHA-256 API key hashing with Redis cache (5-min TTL)
- Structured JSON logs via structlog
- Docker Compose (`apps/api`, `apps/worker`, PostgreSQL, Redis)

---

## Upcoming

### v1.1 — Enterprise Hardening (Phase 7)
- SSO / SAML / OIDC
- Fine-grained RBAC
- Audit log export (CSV / JSON)
- Compliance tooling

### v2.0 — Optimized Mojo Runtime (Phase 8)
- Vectorized Monte Carlo (SIMD)
- Latin hypercube sampling
- GPU acceleration hooks
- 10–100x throughput improvement
