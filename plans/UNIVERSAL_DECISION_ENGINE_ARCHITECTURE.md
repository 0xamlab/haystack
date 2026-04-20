# Universal Decision Engine — Mass Market + Enterprise Architecture Plan

> **Version:** 1.0  
> **Status:** Draft — Pending Approval  
> **Strategy:** Developer-first mass market → Prosumer UI → Enterprise platform  
> **Positioning:** "The Stripe of decision-making — API infrastructure to simulate outcomes before you act"

---

## Table of Contents

1. [Strategic Context](#1-strategic-context)
2. [Product Strategy and Layers](#2-product-strategy-and-layers)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Mass Market Additions to Enterprise Base](#4-mass-market-additions-to-enterprise-base)
5. [Self-Serve Onboarding and Time-to-Value Flow](#5-self-serve-onboarding-and-time-to-value-flow)
6. [API Design: Simple Mode vs Expert Mode](#6-api-design-simple-mode-vs-expert-mode)
7. [Developer Portal and Docs-First Strategy](#7-developer-portal-and-docs-first-strategy)
8. [Pricing Model and Billing Architecture](#8-pricing-model-and-billing-architecture)
9. [Repository and Open-Core Strategy](#9-repository-and-open-core-strategy)
10. [Data Model](#10-data-model)
11. [Security Architecture](#11-security-architecture)
12. [Observability Architecture](#12-observability-architecture)
13. [Infrastructure and Deployment](#13-infrastructure-and-deployment)
14. [Integration Architecture](#14-integration-architecture)
15. [Phased Build Plan](#15-phased-build-plan)
16. [Definition of Done Per Phase](#16-definition-of-done-per-phase)

---

## 1. Strategic Context

### 1.1 The Core Problem We Are Solving

Every developer, analyst, operator, or system making a consequential decision needs the same thing:

> "Given this situation, what should I do — and how confident should I be?"

Today that requires either:
- Expensive proprietary BI tools with steep onboarding
- Hand-rolled Monte Carlo code in notebooks
- Intuition and guesswork

**The Decision Engine is the API layer that replaces all of that in a single POST request.**

### 1.2 The Mental Model Shift

| Old Framing | New Framing |
|---|---|
| Enterprise simulation software | Decision API infrastructure |
| Sold to companies | Used by developers |
| Configured by consultants | Integrated in minutes |
| Output: reports | Output: structured JSON decisions |
| Months to deploy | Under 2 minutes to first result |

### 1.3 The Winning Strategy

```
Developer-first (launch)
    → Open-core for adoption
        → Prosumer UI for non-technical users
            → Enterprise controls for companies
```

**Reference companies:**
- Stripe — API-first payments, layered dashboard on top
- Twilio — API-first communications, added Studio UI later
- Supabase — dev-first DB, added UI/dashboard layer
- Vercel — dev-first deployment, added team/org features

---

## 2. Product Strategy and Layers

### 2.1 The Four-Layer Product Model

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4 — ENTERPRISE PLATFORM                              │
│  SSO, SAML, RBAC, compliance, SLA, dedicated infra          │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3 — PROSUMER / NO-CODE UI                            │
│  Templates, visual builder, saved scenarios, dashboards      │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2 — DEVELOPER PLATFORM                               │
│  SDK, CLI, webhooks, integrations, API key management        │
├─────────────────────────────────────────────────────────────┤
│  LAYER 1 — CORE API  (open-core)                            │
│  POST /simulate, POST /recommend, OpenAPI, JSON in/out       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Tier Definitions

#### Open Core (public repo)
- Basic simulation engine (Mojo-backed, public bindings)
- REST API (FastAPI)
- OpenAPI 3.1 specification
- Python SDK + TypeScript SDK
- CLI tool
- Docker Compose local setup
- Integration examples (n8n, LangGraph, ChatGPT Actions, Zapier, Power Automate)
- Apache 2.0 or BSL license

#### Developer Tier (hosted, self-serve)
- Instant sign-up, no sales
- Immediate API key generation
- Free tier (limited simulations/month)
- Pay-as-you-go pricing
- Usage dashboard
- Webhook support
- Job history

#### Pro Tier (hosted, self-serve)
- Higher limits
- Faster execution SLA
- Batch endpoints
- More distribution types
- Priority queue

#### Enterprise Tier (sales-assisted)
- SSO/SAML/OIDC
- RBAC with fine-grained roles
- Dedicated compute option
- SLA guarantees
- Compliance exports (SOC2 alignment)
- Custom rate limits
- Private deployment options

#### Commercial Engine (private repo)
- Optimized Mojo runtime (vectorized, SIMD)
- Advanced correlated variable support
- Distributed simulation partitioning
- Advanced scoring and policy logic
- Premium templates

### 2.3 Positioning and Messaging

**Primary headline (mass market):**
> "Run thousands of decision scenarios instantly — with one API call"

**Secondary (developer):**
> "Monte Carlo simulation and decision intelligence as API infrastructure"

**For AI engineers:**
> "Give your LLM agents the ability to reason about uncertainty before acting"

**For automation builders:**
> "Add probabilistic decision-making to any n8n, Zapier, or Power Automate flow"

---

## 3. System Architecture Overview

### 3.1 Full System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                    │
│  Browser  │  Python SDK  │  TS SDK  │  CLI  │  n8n  │  LangGraph        │
│  Power Automate  │  ChatGPT Actions  │  Zapier  │  Make  │  curl         │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTPS / JSON
┌──────────────────────────────▼──────────────────────────────────────────┐
│                        API GATEWAY LAYER                                 │
│  Auth (API key / JWT)  │  Rate Limiting  │  Quota Enforcement            │
│  Request Validation    │  Idempotency    │  Request Logging              │
│  OpenTelemetry ingress │  Versioning     │  CORS / IP filtering          │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                       APPLICATION LAYER                                  │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  FastAPI REST   │  │  Async Job Svc  │  │  Webhook Svc    │         │
│  │  /v1/simulate   │  │  /v1/jobs       │  │  delivery +     │         │
│  │  /v1/recommend  │  │  polling        │  │  retry logic    │         │
│  │  /v1/score      │  │  cancellation   │  └─────────────────┘         │
│  │  /v1/batch      │  └────────┬────────┘                              │
│  └────────┬────────┘           │                                        │
│           │              Redis Queue                                     │
│           │                    │                                        │
│  ┌────────▼────────────────────▼────────┐                              │
│  │         Orchestration Service         │                              │
│  │  job dispatch, retry, TTL, state      │                              │
│  └────────┬──────────────────────────────┘                              │
└───────────│─────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────────────┐
│                         COMPUTE LAYER                                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Mojo Simulation Kernel                         │   │
│  │  Monte Carlo engine  │  Distribution sampler  │  Scoring engine   │   │
│  │  Risk metrics        │  Optimization hooks    │  Stats engine     │   │
│  │  Seed management     │  Vectorized loops       │  Batch runner    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Python compute adapter (subprocess or shared-lib binding)               │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                        PERSISTENCE LAYER                                 │
│  Postgres (orgs, users, runs, jobs, usage, audit)                        │
│  Redis (cache, queue, idempotency keys, locks)                           │
│  S3-compatible object store (large payloads, result blobs)               │
│  Analytics store (usage telemetry, optional: ClickHouse / BigQuery)      │
└─────────────────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────────────┐
│                     ENTERPRISE CONTROL LAYER                             │
│  Audit log service  │  Secrets manager  │  SSO adapter  │  RBAC engine  │
│  Key management     │  Quota engine     │  Compliance   │  Billing hook  │
└─────────────────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────────────┐
│                      DEVELOPER PORTAL + DASHBOARD                        │
│  Sign-up / sign-in  │  API key management  │  Usage charts               │
│  Run history        │  Docs (integrated)   │  Playground                 │
│  Billing            │  Templates           │  Org management             │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Separation of Concerns

| Layer | Responsibility | Technology |
|---|---|---|
| Compute | High-performance simulation math | Mojo |
| API | Interoperability surface | Python + FastAPI |
| Orchestration | Jobs, retries, workflow | Dramatiq + Redis |
| Auth | Identity, keys, tokens | Custom + JWT |
| Persistence | State, history, blobs | Postgres + Redis + S3 |
| Enterprise | Audit, quotas, SSO | Custom + cloud providers |
| Portal | Developer UX, docs | Next.js |

---

## 4. Mass Market Additions to Enterprise Base

The enterprise doc defines a solid technical base. The mass market layer requires specific additions and simplifications.

### 4.1 What Changes from Enterprise-Only

| Dimension | Enterprise Only | Mass Market Layer Added |
|---|---|---|
| Onboarding | Sales-assisted, weeks | Self-serve, under 2 minutes |
| Auth setup | Admin configures | User signs up, key auto-generated |
| API surface | Full expert mode | Simple mode + expert mode |
| Pricing | Contract-based | Free tier + PAYG + Pro plans |
| Docs | Internal wiki style | Docs-first, examples-first |
| Time to value | Days/weeks | Under 2 minutes to first result |
| Portal | Optional | Required (developer dashboard) |
| API keys | Admin-managed | Self-service instant generation |
| Billing | Invoiced | Credit card, Stripe integration |
| Rate limits | Negotiated | Tier-based, visible in dashboard |

### 4.2 New Services Required for Mass Market

#### Self-Serve Auth Service
- Email + password sign-up
- Magic link (optional)
- OAuth via GitHub / Google (optional, high conversion)
- Instant API key creation post sign-up
- Email verification flow

#### Billing Service
- Stripe integration
- Plan management (free, pro, enterprise)
- Usage metering → Stripe usage records
- Invoice generation
- Quota checks before each request

#### Developer Portal (Next.js)
- Sign-up / login
- API key management (create, rotate, revoke)
- Usage dashboard (per day, per endpoint, per key)
- Run history
- Playground (call the API from the browser)
- Billing management
- Documentation (integrated, not separate)

#### Public Documentation Site
- Quickstart (< 5 min to first result)
- API reference (auto-generated from OpenAPI)
- Copy-paste examples in Python, TypeScript, curl
- Integration guides (LangGraph, n8n, ChatGPT Actions, Zapier, Make, Power Automate)
- Concepts (Monte Carlo, distributions, decision envelopes)
- Changelog

### 4.3 Key Mass Market Product Rules

1. **Under 2 minutes to first result** — from sign-up to successful API call
2. **Zero friction API key** — key generated at sign-up, shown immediately
3. **Copy-paste first** — every doc page has a working curl example
4. **Playground required** — user must be able to try the API from the browser without writing code
5. **Error messages are user-readable** — errors must explain what went wrong and how to fix it
6. **Dashboard is the product** — users must see their usage, history, and keys at a glance

---

## 5. Self-Serve Onboarding and Time-to-Value Flow

### 5.1 Ideal Onboarding Journey

```
User lands on site (marketing or docs)
    │
    ▼
"Get API Key" CTA
    │
    ▼
Sign up with email + password (or GitHub OAuth)
    │
    ▼
Email verified (or immediate access on dev tier)
    │
    ▼
Dashboard: API key shown immediately with copy button
    │
    ▼
Quickstart shown inline: curl example pre-filled with their key
    │
    ▼
User makes first API call
    │
    ▼
Result shown — run stored — usage updated
    │
    ▼
Prompt to explore: Playground / Docs / SDKs
```

**Target: user reaches first successful API call response in under 2 minutes from landing.**

### 5.2 Onboarding Technical Requirements

#### Sign-up endpoint
```
POST /auth/signup
{
  "email": "user@example.com",
  "password": "...",
  "name": "..."
}
→ returns: user object, org created, api_key generated, session token
```

#### Post-signup state
- Organization created automatically (slug derived from email domain or user name)
- One API key created automatically
- Free tier quota applied
- Welcome email sent

#### Welcome email contents
- Their API key (or link to dashboard)
- One-line curl command to test immediately
- Link to quickstart docs

### 5.3 Developer Playground Requirements

The playground must:
- Accept a simulation payload in a JSON editor
- Show the API key pre-filled (authenticated user)
- Run the request against the live API
- Show formatted JSON response
- Show latency and usage units consumed
- Allow switching between `/simulate`, `/recommend`, `/score`
- Provide pre-loaded example payloads to click and run

---

## 6. API Design: Simple Mode vs Expert Mode

This is the most important UX design decision for mass market adoption.

### 6.1 The Problem

The full enterprise API requires significant domain knowledge to use:
- Distribution types
- Correlation matrices
- Scoring weights
- Constraint definitions

This creates friction for mass market users. The solution is **two API modes on the same endpoints**.

### 6.2 Simple Mode (Auto)

User sends minimal, high-level input. The engine infers distributions, runs default simulation parameters, and returns a structured decision.

```json
POST /v1/simulate
{
  "mode": "auto",
  "scenario": {
    "name": "Launch product A vs B",
    "variables": {
      "revenue_upside": { "low": 80000, "high": 200000 },
      "cost": { "low": 40000, "high": 90000 },
      "churn_risk": { "low": 0.05, "high": 0.25 }
    },
    "objective": "maximize_net_value"
  }
}
```

**What the engine does automatically in auto mode:**
- Infers triangular distribution from low/high (with midpoint calculated)
- Defaults to 10,000 simulation runs
- Auto-selects scoring method based on `objective`
- Returns full decision envelope

### 6.3 Expert Mode (Full Control)

```json
POST /v1/simulate
{
  "mode": "expert",
  "simulation": {
    "runs": 50000,
    "seed": 42,
    "variables": [
      {
        "name": "revenue",
        "distribution": "lognormal",
        "params": { "mean": 11.5, "std": 0.4 }
      },
      {
        "name": "cost",
        "distribution": "triangular",
        "params": { "low": 40000, "mode": 60000, "high": 90000 }
      }
    ],
    "correlations": [
      { "variables": ["revenue", "cost"], "coefficient": 0.3 }
    ],
    "objective_function": "revenue - cost",
    "scoring": {
      "weights": { "expected_value": 0.6, "downside_risk": 0.4 },
      "risk_free_rate": 0.05
    }
  }
}
```

### 6.4 Unified Response Envelope

Both modes return the same response schema — the **decision envelope**:

```json
{
  "run_id": "run_abc123",
  "status": "completed",
  "engine_version": "1.2.0",
  "recommended_action": "proceed",
  "confidence": 0.78,
  "rationale": "Expected net value positive in 78% of scenarios. Downside bounded by cost floor.",
  "metrics": {
    "expected_value": 62400,
    "median": 58200,
    "std_deviation": 18300,
    "probability_of_loss": 0.22,
    "var_95": -12000,
    "cvar_95": -18500
  },
  "percentiles": {
    "p5": 18000,
    "p25": 44000,
    "p50": 58200,
    "p75": 78000,
    "p95": 105000
  },
  "scenarios_run": 10000,
  "execution_ms": 87,
  "metadata": {
    "mode": "auto",
    "seed": null,
    "billing_units": 1
  }
}
```

### 6.5 API Endpoint Reference (Full Surface)

#### Synchronous

| Method | Path | Description |
|---|---|---|
| POST | `/v1/simulate` | Run simulation, return results |
| POST | `/v1/recommend` | Run simulation + return recommended action |
| POST | `/v1/score` | Score a pre-defined scenario set |
| POST | `/v1/batch` | Run multiple simulations in one request |
| POST | `/v1/compare` | Compare two or more scenarios side by side |

#### Asynchronous

| Method | Path | Description |
|---|---|---|
| POST | `/v1/jobs` | Submit async simulation job |
| GET | `/v1/jobs/{job_id}` | Poll job status |
| GET | `/v1/jobs/{job_id}/result` | Retrieve job result |
| POST | `/v1/jobs/{job_id}/cancel` | Cancel a running job |

#### Metadata

| Method | Path | Description |
|---|---|---|
| GET | `/v1/health` | Service health check |
| GET | `/v1/version` | Engine and API version info |
| GET | `/v1/limits` | Current rate limits and quotas for caller |
| GET | `/v1/templates` | List of available simulation templates |
| GET | `/v1/distributions` | List of supported distribution types |

#### Auth and Account

| Method | Path | Description |
|---|---|---|
| GET | `/v1/me` | Current user / org info |
| GET | `/v1/usage` | Usage summary for current billing period |
| GET | `/v1/api-keys` | List API keys |
| POST | `/v1/api-keys` | Create new API key |
| DELETE | `/v1/api-keys/{id}` | Revoke API key |

### 6.6 API Design Rules

- JSON only (v1)
- All requests require `Authorization: Bearer <api_key>` or `X-API-Key: <key>`
- All responses include `X-Request-Id` header
- `Idempotency-Key` header supported on all mutation endpoints
- Consistent error schema (see below)
- Versioned routes (`/v1/...`)
- No breaking changes within a version

### 6.7 Error Schema

```json
{
  "error": {
    "code": "validation_error",
    "message": "The 'variables' field is required in expert mode",
    "details": [
      {
        "field": "simulation.variables",
        "issue": "required field missing"
      }
    ],
    "request_id": "req_abc123",
    "docs_url": "https://docs.decisionengine.io/errors/validation_error"
  }
}
```

**Error codes must be:**
- Snake_case strings (not HTTP status codes alone)
- Human-readable messages
- Paired with a docs URL explaining the fix

---

## 7. Developer Portal and Docs-First Strategy

### 7.1 The Docs Are the Product

For mass market developer tools, documentation is the primary acquisition, activation, and retention surface.

**Rule: If you can't get a successful API response in under 5 minutes from the docs homepage, the docs have failed.**

### 7.2 Documentation Architecture

```
docs.decisionengine.io
├── /quickstart              ← First page every user sees
├── /concepts
│   ├── /monte-carlo
│   ├── /distributions
│   ├── /decision-envelopes
│   └── /simulation-modes
├── /api-reference           ← Auto-generated from OpenAPI
│   ├── /simulate
│   ├── /recommend
│   ├── /score
│   ├── /batch
│   └── /jobs
├── /sdks
│   ├── /python
│   └── /typescript
├── /cli
├── /integrations
│   ├── /langgraph
│   ├── /n8n
│   ├── /power-automate
│   ├── /chatgpt-actions
│   ├── /zapier
│   └── /make
├── /guides
│   ├── /async-jobs
│   ├── /webhooks
│   ├── /batch-processing
│   └── /self-hosting
└── /changelog
```

### 7.3 Quickstart Page Requirements

The quickstart page must:

1. Show a one-click "Get API Key" button (or display key if already authenticated)
2. Show working curl example with real API key pre-filled
3. Show working Python example
4. Show working TypeScript example
5. Each example must be copy-pasteable and run immediately
6. Show what the response looks like (real example output)
7. Link to playground for interactive exploration

**Target: user makes first successful call from the quickstart page in under 2 minutes.**

### 7.4 Developer Portal Pages

#### Dashboard (/)
- Usage graph (simulations this week/month)
- Current plan and limits
- Recent runs with status and duration
- Quick links to docs and playground

#### API Keys (/keys)
- Table of active keys with label, created date, last used
- Create new key (name it, set expiry optional)
- Revoke key (with confirmation)
- Copy key to clipboard

#### Playground (/playground)
- JSON editor with syntax highlighting
- Endpoint selector (simulate / recommend / score)
- Mode selector (auto / expert)
- Pre-loaded example payloads (dropdown)
- "Run" button
- Response panel with formatted JSON
- Show latency, billing units used

#### Usage (/usage)
- Simulations run (current period vs limit)
- API calls by endpoint
- Average latency
- Billing period summary

#### Billing (/billing)
- Current plan
- Usage vs quota
- Payment method
- Upgrade / downgrade plan
- Invoice history

### 7.5 Tech Stack for Developer Portal

```
Frontend: Next.js 14+ (App Router)
Styling: Tailwind CSS + shadcn/ui
Auth: Custom session handling (JWT stored in httpOnly cookie)
API calls: Use the TypeScript SDK internally
Docs: Custom MDX pipeline OR Mintlify / Docusaurus
Code highlighting: Shiki
API playground: Monaco editor + fetch
```

---

## 8. Pricing Model and Billing Architecture

### 8.1 Pricing Tiers

#### Free Tier (always free)
| Limit | Value |
|---|---|
| Simulations/month | 500 |
| Max runs per simulation | 10,000 |
| Sync only | Yes |
| API keys | 1 |
| Support | Community |

#### Developer Tier ($29/month)
| Limit | Value |
|---|---|
| Simulations/month | 10,000 |
| Max runs per simulation | 100,000 |
| Async jobs | Yes |
| API keys | 5 |
| Webhooks | Yes |
| Batch endpoint | Yes |
| Support | Email |

#### Pro Tier ($99/month)
| Limit | Value |
|---|---|
| Simulations/month | 100,000 |
| Max runs per simulation | 1,000,000 |
| Priority queue | Yes |
| API keys | 20 |
| Advanced distributions | Yes |
| Support | Priority email |

#### Enterprise (Custom)
| Limit | Value |
|---|---|
| Simulations/month | Unlimited / SLA-backed |
| Dedicated compute option | Yes |
| SSO / SAML | Yes |
| RBAC | Yes |
| Audit logs export | Yes |
| Custom SLA | Yes |
| Support | Dedicated |

#### Pay-As-You-Go Overage
- Available on Developer and Pro tiers
- $0.001 per additional simulation unit over quota
- Soft limit alerts at 80% and 100% usage

### 8.2 Billing Unit Definition

One **simulation unit** = one call to `/simulate`, `/recommend`, or `/score` with up to 10,000 simulation runs.

Batch multiplier: each item in a `/batch` request = 1 simulation unit.

Async jobs: same unit count as sync, billed on completion.

### 8.3 Billing Architecture

```
Request arrives at API layer
    │
    ▼
Quota check (Redis cache of current usage)
    │
    ├─ Over limit + no overage enabled → 429 response
    │
    └─ Within limit → proceed
            │
            ▼
         Execute simulation
            │
            ▼
Record UsageEvent to database
            │
            ▼
Push UsageEvent to Stripe usage record (via background task)
            │
            ▼
Update Redis quota cache
```

#### Stripe Integration Components
- `stripe.Customer` per organization
- `stripe.Subscription` per plan
- `stripe.SubscriptionItem` for metered usage
- Webhook listener for subscription events (created, updated, cancelled, payment_failed)
- Metered usage reporting (daily batch or near-real-time)

#### Quota Enforcement
- Primary check: Redis counter `quota:{org_id}:{billing_period}` 
- Fallback check: Postgres usage table (if Redis miss)
- Counter reset: Stripe webhook `invoice.paid` triggers reset
- Alert triggers: 80% and 100% usage → email + dashboard notification

---

## 9. Repository and Open-Core Strategy

### 9.1 Three-Repository Structure

#### Repo 1: `decision-engine` (public, open-core)

License: **BSL 1.1** (converts to Apache 2.0 after 4 years)
> BSL protects against direct SaaS competition while allowing self-hosting, evaluation, and community use.

Contents:
- Full FastAPI REST service
- OpenAPI 3.1 specification
- Python SDK
- TypeScript SDK
- CLI tool
- Basic Mojo simulation engine (public edition)
- Docker Compose local stack
- Integration examples (all platforms)
- Full documentation source
- Unit + integration tests

**What is NOT in this repo:**
- Optimized Mojo runtime internals
- Advanced scoring / policy logic
- Billing service
- Enterprise auth adapters (SSO/SAML)
- Production infra configs

#### Repo 2: `decision-engine-enterprise` (private)

Contents:
- Optimized Mojo runtime (vectorized, SIMD, distributed)
- Advanced distribution types (correlated, Latin hypercube)
- Premium scoring and policy engines
- Billing service internals
- SSO / SAML / OIDC adapters
- Fine-grained RBAC engine
- Advanced audit and compliance features
- Enterprise dashboard backend
- Advanced quota and rate-limiting engine

#### Repo 3: `decision-engine-infra` (private)

Contents:
- Terraform modules (AWS, GCP, Azure)
- Helm charts (Kubernetes)
- Cloud Run / ECS deployment configs
- CI/CD pipeline definitions
- Environment configs
- Secret management templates
- Production runbooks

### 9.2 Monorepo Structure (Repo 1 — Public)

```
decision-engine/
├── apps/
│   ├── api-server/              # FastAPI application
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── simulate.py
│   │   │   ├── recommend.py
│   │   │   ├── score.py
│   │   │   ├── batch.py
│   │   │   ├── jobs.py
│   │   │   └── auth.py
│   │   ├── services/
│   │   │   ├── simulation_service.py
│   │   │   ├── job_service.py
│   │   │   ├── auth_service.py
│   │   │   └── webhook_service.py
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── compute/            # Mojo adapter
│   │   ├── middleware/
│   │   └── config.py
│   ├── worker/                 # Dramatiq worker
│   │   ├── worker.py
│   │   ├── tasks/
│   │   └── config.py
│   └── cli/                    # CLI tool (Typer)
│       ├── main.py
│       └── commands/
├── packages/
│   ├── python-sdk/             # pip installable SDK
│   │   ├── decision_engine/
│   │   │   ├── client.py
│   │   │   ├── async_client.py
│   │   │   ├── models.py
│   │   │   └── exceptions.py
│   │   └── pyproject.toml
│   └── ts-sdk/                 # npm installable SDK
│       ├── src/
│       │   ├── client.ts
│       │   ├── types.ts
│       │   └── errors.ts
│       └── package.json
├── mojo/
│   ├── engine/                 # Public simulation engine
│   │   ├── monte_carlo.mojo
│   │   └── main.mojo
│   ├── distributions/
│   │   ├── normal.mojo
│   │   ├── uniform.mojo
│   │   ├── triangular.mojo
│   │   └── lognormal.mojo
│   ├── stats/
│   │   ├── percentiles.mojo
│   │   ├── summary.mojo
│   │   └── risk.mojo
│   └── bindings/
│       └── python_adapter.py   # Subprocess invocation
├── schemas/
│   ├── openapi/
│   │   └── openapi.yaml        # OpenAPI 3.1 spec
│   └── jsonschema/
│       ├── simulate_request.json
│       └── simulate_response.json
├── examples/
│   ├── langgraph/
│   │   └── decision_tool.py
│   ├── n8n/
│   │   └── workflow_example.json
│   ├── power-automate/
│   │   └── connector_definition.json
│   ├── chatgpt-actions/
│   │   └── openapi_actions.yaml
│   ├── zapier/
│   │   └── zapier_action.js
│   └── make/
│       └── webhook_scenario.json
├── infra/
│   └── docker/
│       ├── Dockerfile.api
│       ├── Dockerfile.worker
│       └── docker-compose.yml
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── load/
├── docs/                       # Source for docs site
├── Makefile
├── pyproject.toml
└── README.md
```

---

## 10. Data Model

### 10.1 Entity Relationship Overview

```
Organization
    ├── Users (many)
    ├── APIKeys (many)
    ├── SimulationRuns (many)
    │       └── Jobs (one per async run)
    ├── UsageRecords (many)
    ├── AuditEvents (many)
    └── Subscription (one)
```

### 10.2 Core Tables

#### organizations
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR | Display name |
| slug | VARCHAR | Unique, URL-safe |
| plan | ENUM | free, developer, pro, enterprise |
| status | ENUM | active, suspended, deleted |
| stripe_customer_id | VARCHAR | Stripe customer reference |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### users
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| org_id | UUID | FK organizations |
| email | VARCHAR | Unique |
| password_hash | VARCHAR | bcrypt |
| name | VARCHAR | |
| role | ENUM | owner, admin, member, viewer |
| status | ENUM | active, invited, suspended |
| email_verified | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

#### api_keys
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| org_id | UUID | FK organizations |
| user_id | UUID | FK users (creator) |
| label | VARCHAR | User-defined name |
| key_prefix | VARCHAR | First 8 chars (display only) |
| hashed_key | VARCHAR | SHA-256 hash for lookup |
| status | ENUM | active, revoked |
| expires_at | TIMESTAMPTZ | Nullable |
| last_used_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

#### simulation_runs
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| org_id | UUID | FK organizations |
| api_key_id | UUID | FK api_keys |
| mode | ENUM | auto, expert |
| engine_version | VARCHAR | |
| request_hash | VARCHAR | SHA-256 of input for dedup |
| status | ENUM | queued, running, completed, failed |
| execution_type | ENUM | sync, async |
| input_blob_ref | VARCHAR | S3 key (large payloads) |
| output_blob_ref | VARCHAR | S3 key |
| error_message | TEXT | Nullable |
| scenarios_run | INTEGER | |
| billing_units | INTEGER | |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |
| duration_ms | INTEGER | |

#### jobs
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| run_id | UUID | FK simulation_runs |
| org_id | UUID | FK organizations |
| queue_name | VARCHAR | |
| status | ENUM | queued, validating, running, completed, failed, cancelled, expired |
| retry_count | INTEGER | |
| max_retries | INTEGER | |
| callback_url | VARCHAR | Nullable |
| callback_status | ENUM | pending, delivered, failed |
| ttl_expires_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### usage_records
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| org_id | UUID | FK organizations |
| run_id | UUID | FK simulation_runs |
| metric_name | VARCHAR | simulations, api_calls, compute_units |
| quantity | INTEGER | |
| billing_period | VARCHAR | YYYY-MM |
| stripe_usage_record_id | VARCHAR | Nullable |
| created_at | TIMESTAMPTZ | |

#### audit_events
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| org_id | UUID | FK organizations |
| actor_type | ENUM | user, api_key, system |
| actor_id | UUID | |
| action | VARCHAR | api_key.created, run.submitted, etc. |
| entity_type | VARCHAR | |
| entity_id | UUID | Nullable |
| payload_summary | JSONB | Non-sensitive summary |
| ip_address | INET | |
| created_at | TIMESTAMPTZ | |

#### subscriptions
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| org_id | UUID | FK organizations |
| stripe_subscription_id | VARCHAR | |
| plan | ENUM | free, developer, pro, enterprise |
| status | ENUM | active, past_due, cancelled |
| current_period_start | TIMESTAMPTZ | |
| current_period_end | TIMESTAMPTZ | |
| cancel_at | TIMESTAMPTZ | Nullable |
| updated_at | TIMESTAMPTZ | |

---

## 11. Security Architecture

### 11.1 Authentication Flow

```
Client sends request with X-API-Key: de_live_abc123...
    │
    ▼
API Gateway middleware extracts key
    │
    ▼
SHA-256 hash of key
    │
    ▼
Redis cache lookup: hash → {org_id, key_id, status, plan}
    │
    ├─ Cache hit + active → proceed
    │
    └─ Cache miss → Postgres lookup → cache result (TTL 5 min)
            │
            ├─ Not found → 401
            └─ Revoked → 401
```

### 11.2 API Key Format

```
de_live_[32 random base62 chars]
de_test_[32 random base62 chars]
```

- `de_` prefix identifies the product
- `live_` / `test_` environment disambiguation
- First 8 chars stored as `key_prefix` for display
- Full key shown only once at creation
- Stored as `SHA-256(full_key)` in database

### 11.3 Tenant Isolation

- Every database query filtered by `org_id`
- No cross-org result visibility — enforced at service layer
- Row-level security on Postgres as defense-in-depth
- S3 object paths include org_id prefix: `orgs/{org_id}/runs/{run_id}/result.json`
- Redis keys namespaced: `quota:{org_id}:`, `cache:{org_id}:`

### 11.4 Input Validation

- All request bodies validated with Pydantic strict mode
- Max payload size: 1 MB (configurable per plan)
- Max `runs` per simulation: 100,000 (free), 1,000,000 (pro+)
- Max variables per simulation: 50 (free), 500 (pro+)
- Max batch items: 10 (free), 100 (pro+)

### 11.5 Secrets Management

| Environment | Secret Storage |
|---|---|
| Local dev | `.env` file only |
| Staging/Prod on AWS | AWS Secrets Manager |
| Staging/Prod on GCP | GCP Secret Manager |
| Kubernetes | External Secrets Operator |

### 11.6 Rate Limiting

```
Rate limits enforced per org_id at API gateway layer.

Free: 60 requests/minute, 500 simulations/month
Developer: 300 requests/minute, 10,000 simulations/month
Pro: 1,000 requests/minute, 100,000 simulations/month
Enterprise: Custom (configurable in DB)
```

Rate limit headers returned on every response:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1711000800
```

---

## 12. Observability Architecture

### 12.1 Logging

Every request logs:
```json
{
  "level": "info",
  "timestamp": "2026-03-20T18:00:00Z",
  "request_id": "req_abc123",
  "run_id": "run_xyz789",
  "org_id": "org_def456",
  "api_key_id": "key_ghi012",
  "endpoint": "POST /v1/simulate",
  "status_code": 200,
  "duration_ms": 87,
  "billing_units": 1,
  "mode": "auto",
  "scenarios_run": 10000
}
```

**Never log:**
- Raw input payloads (may contain sensitive business data)
- API keys
- Passwords

### 12.2 Metrics (Prometheus)

```
# Request metrics
http_requests_total{endpoint, method, status_code, org_plan}
http_request_duration_seconds{endpoint, quantile}

# Simulation metrics
simulations_total{mode, status}
simulation_duration_seconds{mode, quantile}
simulation_scenarios_run_total{mode}

# Job metrics
jobs_queued_total
jobs_completed_total{status}
jobs_queue_depth
jobs_processing_duration_seconds

# Billing metrics
billing_units_consumed_total{org_id, plan}

# Webhook metrics
webhook_deliveries_total{status}
webhook_delivery_duration_seconds
```

### 12.3 Tracing (OpenTelemetry)

Trace spans:
1. HTTP request received (API server)
2. Auth middleware validation
3. Request validation (Pydantic)
4. Simulation service dispatch
5. Mojo compute kernel execution
6. Result serialization
7. Persistence (Postgres write)
8. Usage record write

Trace context propagated through:
- HTTP headers (`traceparent`, `tracestate`)
- Redis message headers (async jobs)
- Log correlation (`trace_id` in every log line)

### 12.4 Alerting (Production)

| Alert | Threshold | Channel |
|---|---|---|
| API error rate | > 1% over 5 min | PagerDuty / Slack |
| P95 latency | > 2s over 5 min | Slack |
| Job failure rate | > 5% over 10 min | PagerDuty |
| Queue depth | > 1000 jobs | Slack |
| Webhook failure rate | > 10% over 10 min | Slack |
| Auth abuse | > 100 401s from single IP in 1 min | PagerDuty |

---

## 13. Infrastructure and Deployment

### 13.1 Local Development Stack

```yaml
# docker-compose.yml services:
- api-server (FastAPI, port 8000)
- worker (Dramatiq)
- postgres (port 5432)
- redis (port 6379)
- minio (S3-compatible, port 9000)
```

One-command start:
```bash
make dev
# → docker compose up + migrations + seed data
```

### 13.2 Production Deployment Topology

#### Primary Cloud Target: AWS

```
Route 53 (DNS)
    │
    ▼
CloudFront (CDN for docs/portal)
    │
    ▼
Application Load Balancer
    │
    ├── ECS Fargate: api-server (auto-scaling, 2-10 tasks)
    ├── ECS Fargate: worker (auto-scaling, 2-20 tasks)
    └── ECS Fargate: portal (Next.js, 2-4 tasks)

Managed Services:
    RDS Postgres (Multi-AZ)
    ElastiCache Redis (cluster mode)
    S3 (result blobs)
    SQS (job queue, backing Dramatiq)
    CloudWatch + X-Ray (observability)
    Secrets Manager (secrets)
    SES (transactional email)
```

#### Secondary: GCP (Cloud Run)

```
Cloud Load Balancing
    │
    ├── Cloud Run: api-server
    ├── Cloud Run: worker
    └── Cloud Run: portal

Managed:
    Cloud SQL Postgres
    Memorystore Redis
    Cloud Storage
    Cloud Pub/Sub (queue)
    Cloud Monitoring
    Secret Manager
```

### 13.3 Container Requirements

Every service must have:
- Multi-stage `Dockerfile` (build → runtime)
- Non-root user in container
- `HEALTHCHECK` instruction
- Environment-based configuration (no hardcoded values)
- Graceful shutdown handling (SIGTERM → drain → exit)
- Minimal base image (distroless or slim)

### 13.4 Environment Configuration

All configuration via environment variables:

```
# Database
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
S3_BUCKET_NAME=...
S3_ENDPOINT_URL=... (for local MinIO)

# App
API_ENV=development|staging|production
LOG_LEVEL=info
CORS_ORIGINS=...
MAX_PAYLOAD_SIZE_BYTES=1048576

# Auth
JWT_SECRET=...
API_KEY_HASH_SALT=...

# Mojo
MOJO_BINARY_PATH=/app/mojo/engine/simulate
MOJO_MAX_CONCURRENT=4

# Billing
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=...
SENTRY_DSN=...
```

---

## 14. Integration Architecture

### 14.1 ChatGPT Actions / OpenAI Tools

Requirements:
- OpenAPI spec must have clear `operationId` per endpoint
- Descriptions must be ≤ 300 chars (tool description limit)
- Auth: `apikey` security scheme in OpenAPI
- No nested objects deeper than 3 levels
- Response fields must be named for LLM readability

Provide:
- `chatgpt_actions.yaml` — trimmed OpenAPI for action import
- Example GPT system prompt using the tool

### 14.2 LangGraph

Provide Python tool wrapper:
```python
from decision_engine import DecisionEngineClient
from langchain_core.tools import tool

@tool
def simulate_decision(scenario: dict) -> dict:
    """Simulate outcomes for a decision scenario using Monte Carlo analysis."""
    client = DecisionEngineClient(api_key=os.environ["DE_API_KEY"])
    return client.simulate(mode="auto", scenario=scenario)
```

Support both sync and async tool patterns.

### 14.3 n8n

Provide:
- `n8n_workflow.json` — importable workflow using HTTP Request node
- Pre-configured auth via credential variable
- Example: simulate → extract recommended_action → branch workflow

### 14.4 Power Automate / Logic Apps

Provide:
- `power_automate_connector.json` — importable custom connector definition
- Flat schema (Power Automate struggles with deep nesting)
- API key auth via connector credential

### 14.5 Zapier

Provide:
- Zapier action definition using webhook trigger
- Documentation for Zapier HTTP action usage
- CLI example for testing

### 14.6 Make (formerly Integromat)

Provide:
- Inbound webhook module example (trigger on result)
- Outbound HTTP module example (call `/simulate`)
- Fast webhook acknowledgement pattern for async jobs

---

## 15. Phased Build Plan

> **Revised phase ordering (approved 2026-03-20):** Integrations + SDKs moved ahead of the full portal. Portal split into Phase 5A (minimal auth shell + docs) and Phase 5B (full portal + billing). Rationale: API adoption is the real wedge — SDKs and all 6 integration surfaces must ship before the full dashboard.

---

### Phase 1 — Open Core Foundation
**Goal: Working local stack, first API call, Mojo wired**

- [ ] Initialize monorepo with structure defined in section 9.2
- [ ] Docker Compose (Postgres, Redis, MinIO, API, Worker)
- [ ] FastAPI app skeleton with middleware (request_id, logging, CORS)
- [ ] Config management (Pydantic Settings)
- [ ] `GET /v1/health` and `GET /v1/version`
- [ ] Pydantic request/response models for simulate
- [ ] `POST /v1/simulate` — wired to mock compute adapter
- [ ] Mojo public engine: normal, uniform, triangular, lognormal distributions
- [ ] Mojo subprocess adapter (Pattern A)
- [ ] Postgres models: Organization, User, APIKey, SimulationRun
- [ ] Alembic migration setup
- [ ] Basic API key auth middleware
- [ ] Unit tests for simulation math
- [ ] OpenAPI spec skeleton
- [ ] Root `README.md` and quickstart doc

**Definition of Done:** Developer clones repo, runs `make dev`, calls `/v1/simulate` with their API key, gets back a valid decision envelope. Mojo is actually invoked.

---

### Phase 2 — Decision APIs + Auth
**Goal: Full sync API surface, self-serve API keys**

- [ ] `POST /v1/recommend` endpoint
- [ ] `POST /v1/score` endpoint
- [ ] `POST /v1/batch` endpoint
- [ ] `POST /v1/compare` endpoint
- [ ] Simple mode (`auto`) implementation
- [ ] Decision envelope schema finalized
- [ ] Self-serve sign-up endpoint (`POST /auth/signup`)
- [ ] Self-serve login endpoint (`POST /auth/login`)
- [ ] API key CRUD endpoints
- [ ] `GET /v1/me`, `GET /v1/usage`, `GET /v1/limits`
- [ ] `GET /v1/templates`, `GET /v1/distributions`
- [ ] Structured logging with request_id, run_id, org_id
- [ ] Prometheus metrics endpoint
- [ ] Integration tests: API → compute → persistence
- [ ] OpenAPI spec complete and validated

**Definition of Done:** User can sign up, get API key, call all sync endpoints, view usage.

---

### Phase 3 — Async Platform + Webhooks
**Goal: Large simulation support, webhook delivery**

- [ ] Dramatiq worker service setup
- [ ] Redis job queue wiring
- [ ] Job lifecycle state machine (queued → running → completed/failed)
- [ ] `POST /v1/jobs` (submit async job)
- [ ] `GET /v1/jobs/{job_id}` (poll status)
- [ ] `GET /v1/jobs/{job_id}/result` (fetch result)
- [ ] `POST /v1/jobs/{job_id}/cancel`
- [ ] Webhook delivery service (HTTP POST to callback_url)
- [ ] Webhook retry logic (exponential backoff, 3 attempts)
- [ ] `POST /v1/webhooks/test`
- [ ] Job TTL and cleanup
- [ ] Large result blob storage (S3)
- [ ] Integration tests: queue → worker → webhook

**Definition of Done:** Large simulation submitted as job, worker picks it up, completes, fires webhook to test endpoint.

---

### Phase 4 — Integrations + SDKs
**Goal: All 6 integration surfaces live, SDKs published — the real adoption wedge**

- [ ] Python SDK (sync + async, Pydantic models, retries, timeouts)
- [ ] TypeScript SDK (typed, Node + browser-safe)
- [ ] CLI tool (Typer, local + remote mode, job polling)
- [ ] ChatGPT Actions OpenAPI package (`chatgpt_actions.yaml`)
- [ ] LangGraph tool wrapper example (`examples/langgraph/decision_tool.py`)
- [ ] n8n workflow example (`examples/n8n/workflow_example.json`)
- [ ] Power Automate connector definition (`examples/power-automate/connector_definition.json`)
- [ ] Zapier action documentation (`examples/zapier/`)
- [ ] Make module documentation (`examples/make/`)
- [ ] Python SDK published to PyPI
- [ ] TypeScript SDK published to npm
- [ ] CLI published (PyPI + Homebrew formula)
- [ ] Contract tests (OpenAPI validity, SDK compatibility)

**Definition of Done:** A LangGraph agent, an n8n workflow, and a ChatGPT Action all call the engine successfully end-to-end. SDKs published and tested. All 6 platforms have working examples.

---

### Phase 5A — Minimal Docs Shell + Auth-Gated API Key Page
**Goal: Minimum viable developer activation surface — first call in under 2 minutes, no full portal needed**

- [ ] Static docs site deployed (Mintlify or Docusaurus)
- [ ] Quickstart page with pre-filled curl / Python / TypeScript examples
- [ ] API reference pages auto-generated from OpenAPI spec
- [ ] Minimal sign-up page (email + password → API key shown immediately)
- [ ] Minimal API key display/revoke page
- [ ] Integration guide pages (all 6 platforms, linking to example files)
- [ ] Rate limit and quota enforcement middleware active in API
- [ ] Usage record writes active on each simulation run

**Definition of Done:** External developer lands on docs, signs up, copies API key, makes a successful `/v1/simulate` call — in under 2 minutes. No full dashboard required.

---

### Phase 5B — Full Developer Portal + Billing
**Goal: Full self-serve portal, usage visibility, Stripe billing**

- [ ] Next.js portal app scaffold
- [ ] Dashboard page (usage graph, recent runs)
- [ ] API key management page (create, rotate, revoke, label)
- [ ] Playground page (Monaco editor + live API call + example payloads)
- [ ] Usage page (simulations by period, by endpoint, avg latency)
- [ ] Stripe integration (plans, subscriptions, metered billing)
- [ ] Billing page (plan, payment method, invoice history)
- [ ] Quota alert emails (80% and 100% usage)
- [ ] Plan upgrade / downgrade flow
- [ ] Org settings page

**Definition of Done:** User signs up on the portal, gets API key, uses playground, sees usage update in real-time, can upgrade plan with a credit card.

---

### Phase 6 — Launch Docs Polish + Public Launch Readiness
**Goal: Docs-first product fully polished, ready for public launch**

- [ ] Quickstart page refined to under 2 minute target (tested with real users)
- [ ] All concept pages (Monte Carlo, distributions, decision envelopes, simple vs expert mode)
- [ ] Self-hosting guide
- [ ] Security model page
- [ ] Changelog page
- [ ] Public landing / marketing page
- [ ] SEO + Open Graph
- [ ] Status page (uptime monitoring)
- [ ] CLI reference page polished
- [ ] Load tests pass at launch throughput targets

**Definition of Done:** External developer finds docs, completes quickstart in under 2 minutes, all integrations documented, site live, status page live.

---

### Phase 7 — Enterprise Hardening (Private Repo)
**Goal: Enterprise controls, compliance-ready**

- [ ] SSO / SAML / OIDC adapter
- [ ] Fine-grained RBAC engine
- [ ] Audit log export (CSV / JSON)
- [ ] Advanced rate limit controls per org
- [ ] Dedicated compute option
- [ ] SLA monitoring and alerting
- [ ] Compliance export tooling
- [ ] Enterprise dashboard (org management, member management)
- [ ] Custom plan configuration

---

### Phase 8 — Optimized Mojo Runtime (Private Repo)
**Goal: Performance moat, commercial engine**

- [ ] Vectorized Monte Carlo loops (SIMD)
- [ ] Advanced correlated variable sampling
- [ ] Latin hypercube sampling
- [ ] VaR / CVaR metrics
- [ ] Distributed simulation partitioning
- [ ] Shared library mode (Pattern B)
- [ ] GPU acceleration hooks (optional)
- [ ] Benchmark suite vs open engine
- [ ] Premium template library

---

## 16. Definition of Done Per Phase

### MVP (Phases 1–3)
A developer can:
- Run the full stack locally with `make dev`
- Call `/v1/simulate` with JSON and get back a valid decision envelope from real Mojo compute
- Submit a large job async, poll it, receive a webhook callback
- All runs stored in Postgres with audit trail
- OpenAPI spec imports cleanly into ChatGPT Actions and Power Automate

### Adoption-Ready (Phases 1–4 + 5A)
- All 6 integration platforms have working end-to-end examples
- Python SDK on PyPI, TypeScript SDK on npm, CLI published
- LangGraph agent, n8n workflow, ChatGPT Action all call the engine successfully
- Self-serve sign-up works in production
- First API call achievable in under 2 minutes from docs/quickstart page
- Usage quota enforcement active

### Launch-Ready (Phases 1–5B + 6)
- Full developer portal live (dashboard, playground, billing)
- Stripe billing and plan enforcement active
- Docs site live with full API reference and all integration guides
- Status page live
- Load tests pass at launch throughput targets
- SEO and public marketing page live

### Enterprise-Ready (Phases 1–7)
- SSO / SAML working
- Audit logs exportable
- RBAC enforced
- Dedicated compute option available
- Compliance documentation ready

---

## Appendix A — Technology Decision Log

| Decision | Choice | Reason |
|---|---|---|
| API framework | FastAPI | Best Python/Pydantic integration, async-native, OpenAPI auto-generation |
| Queue/worker | Dramatiq + Redis | Simpler than Celery, reliable, Redis-native |
| Database | Postgres | Battle-tested, JSONB support, row-level security |
| Cache/queue | Redis | Ubiquitous, fast, supports both queue and cache patterns |
| Object store | S3-compatible | Abstraction allows MinIO locally, S3/GCS/Azure Blob in cloud |
| Compute | Mojo (subprocess first) | Stability over latency for v1; shared-lib evaluated for v1.1 |
| Frontend | Next.js + Tailwind + shadcn/ui | Developer portal + docs; modern, fast, accessible |
| Billing | Stripe | Industry standard, metered billing support, webhook-native |
| Observability | OpenTelemetry + Prometheus + Grafana | Vendor-neutral, industry standard |
| Auth (API key) | Custom SHA-256 hash | Full control, no external dep for core auth |
| Auth (user) | Custom JWT + Postgres | Keep it simple for v1, add Auth0/Clerk later if needed |
| License | BSL 1.1 | Protects against SaaS competition, converts to Apache 2.0 after 4 years |

---

## Appendix B — Key Architecture Decisions (ADRs)

### ADR-001: Simple Mode as First-Class Citizen
**Decision:** Implement `mode: "auto"` as a first-class API mode, not just a wrapper.
**Reason:** Mass market adoption requires zero domain knowledge to get first value. Expert mode is secondary.

### ADR-002: Subprocess Invocation for Mojo (v1)
**Decision:** Invoke Mojo engine as compiled subprocess, not shared library.
**Reason:** Stability and debuggability > latency for v1. Shared-lib adds complexity in Python/Mojo ABI boundary.

### ADR-003: API Key Auth First, OAuth Later
**Decision:** v1 supports only API key auth. OAuth/SSO deferred to v2.
**Reason:** Fastest time to integration. OAuth adds significant complexity and friction for developer-first mass market.

### ADR-004: Portal is a Separate Next.js App
**Decision:** Developer portal is its own service, not embedded in FastAPI.
**Reason:** Clean separation, independent deploys, allows docs and portal to scale independently.

### ADR-005: BSL License for Open Core
**Decision:** Use BSL 1.1 for public repo instead of MIT/Apache.
**Reason:** Prevents competitors from wrapping and reselling as SaaS while allowing self-hosting, developer use, and evaluation. Converts to Apache 2.0 after 4 years.

### ADR-006: Docs Are Deployed Separately from Portal
**Decision:** `docs.decisionengine.io` and `app.decisionengine.io` are separate deployments.
**Reason:** Docs can be public/CDN-served (fast, no auth), portal requires auth context.
