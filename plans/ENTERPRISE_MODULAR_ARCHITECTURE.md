# Codna Decision Engine — Enterprise Modular Architecture Plan

> Goal: Handle 100k customers with heavy daily usage. Fully modular. Each runtime used only where it excels: **Mojo** for compute, **Node.js** for I/O-bound gateway/streaming, **Python (FastAPI)** for orchestration + ML logic, **Next.js** for portal.

---

## 1. File Audit — Everything >800 Lines (Immediate Refactor)

| File | Lines | Problem | Action |
|------|-------|---------|--------|
| [`mojo/engine/main.mojo`](../mojo/engine/main.mojo) | 1,384 | All 7 engine types + 20 distributions + AST + Cholesky in one file | Split into modules |
| [`apps/portal/src/app/dashboard/infrastructure/page.tsx`](../apps/portal/src/app/dashboard/infrastructure/page.tsx) | ~2,041 | Wizard + Connect panel + Engine Status + Nodes all in one | Extract components |
| [`apps/portal/src/app/dashboard/simulations/page.tsx`](../apps/portal/src/app/dashboard/simulations/page.tsx) | 1,740 | New run modal + expanded row + table + charts all in one | Extract components |
| [`apps/portal/src/app/dashboard/simulations/new/page.tsx`](../apps/portal/src/app/dashboard/simulations/new/page.tsx) | 1,435 | Variables, correlations, model selection, submit all in one | Extract components |
| [`apps/portal/src/app/dashboard/data/page.tsx`](../apps/portal/src/app/dashboard/data/page.tsx) | 1,409 | ConnectModal + CRUD + browse + all connector types in one | Extract components |
| [`apps/portal/src/app/dashboard/page.tsx`](../apps/portal/src/app/dashboard/page.tsx) | 1,223 | All dashboard KPI cards + charts + recent runs in one | Extract components |
| [`apps/mcp_server/server.py`](../apps/mcp_server/server.py) | 856 | All tool handlers + 2 transports + FastAPI router in one | Split into modules |
| [`apps/api_server/services/provisioner_service.py`](../apps/api_server/services/provisioner_service.py) | 612 | AWS+Azure+GCP provisioners + 108 region metadata entries + base class | Split per provider |
| [`apps/api_server/routers/connectors.py`](../apps/api_server/routers/connectors.py) | 529 | Schemas + CRUD + connection testing all in one router | Split schemas + service |
| [`apps/portal/src/lib/api.ts`](../apps/portal/src/lib/api.ts) | 565 | All API calls in one flat file | Split by domain |

---

## 2. Target Architecture — Modular Monorepo

```
decision-engine/
├── mojo/
│   └── engine/
│       ├── main.mojo              ← entry point + CLI dispatch only (~80 lines)
│       ├── distributions.mojo     ← all 20 distribution samplers
│       ├── engines/
│       │   ├── monte_carlo.mojo
│       │   ├── qmc_sobol.mojo
│       │   ├── lhs.mojo
│       │   ├── bootstrap.mojo
│       │   ├── scenario.mojo
│       │   ├── sensitivity.mojo
│       │   └── mcmc.mojo
│       ├── math/
│       │   ├── expr_ast.mojo      ← ExprNode parser + evaluator
│       │   └── cholesky.mojo      ← correlation decomposition
│       └── types.mojo             ← shared structs
│
├── apps/
│   ├── api_server/                ← Python FastAPI (orchestration only)
│   │   ├── routers/               ← thin HTTP layer, delegates to services
│   │   ├── services/
│   │   │   ├── provisioner/
│   │   │   │   ├── __init__.py    ← abstract base + factory
│   │   │   │   ├── aws.py
│   │   │   │   ├── azure.py
│   │   │   │   └── gcp.py
│   │   │   └── connectors/
│   │   │       ├── __init__.py
│   │   │       ├── tester.py      ← connection testing logic
│   │   │       └── schemas.py     ← ConnectorCreate/Update/Response
│   │   └── compute/
│   │       └── mojo_adapter.py    ← single subprocess bridge (unchanged)
│   │
│   ├── gateway/                   ← NEW: Node.js (Hono/Fastify) API Gateway
│   │   ├── src/
│   │   │   ├── index.ts           ← entry point, rate limiting, auth header validation
│   │   │   ├── proxy.ts           ← routes to Python API or data plane
│   │   │   ├── ws-stream.ts       ← WebSocket streaming for job status
│   │   │   ├── cache.ts           ← Redis hot-path caching (API key lookup)
│   │   │   └── metrics.ts         ← Prometheus counters, p99 histograms
│   │   └── package.json
│   │
│   ├── worker/                    ← Python Celery/ARQ workers
│   │   └── tasks/
│   │       ├── simulation_task.py
│   │       ├── provision_task.py  ← NEW: async cloud provisioning
│   │       └── cost_sync_task.py  ← NEW: nightly cloud cost polling
│   │
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py              ← entry point + transport routing (~80 lines)
│   │   ├── transports/
│   │   │   ├── stdio.py
│   │   │   └── http_sse.py
│   │   ├── tools/
│   │   │   ├── simulate.py
│   │   │   ├── runs.py
│   │   │   ├── analytics.py
│   │   │   ├── jobs.py
│   │   │   ├── connectors.py
│   │   │   └── recommend.py
│   │   └── registry.py            ← TOOLS dict built from tool modules
│   │
│   └── portal/                    ← Next.js 14 (App Router)
│       └── src/
│           ├── components/        ← NEW: shared UI components
│           │   ├── ui/
│           │   │   ├── KPICard.tsx
│           │   │   ├── StatGrid.tsx
│           │   │   ├── DataTable.tsx
│           │   │   ├── CopyButton.tsx
│           │   │   ├── StatusBadge.tsx
│           │   │   └── CodeBlock.tsx   ← replaces inline <pre> everywhere
│           │   ├── simulation/
│           │   │   ├── NewRunModal.tsx
│           │   │   ├── ExpandedRow.tsx
│           │   │   ├── VariableRow.tsx
│           │   │   └── CorrelationEditor.tsx
│           │   ├── infrastructure/
│           │   │   ├── DeploymentCard.tsx
│           │   │   ├── DeploymentWizard.tsx
│           │   │   ├── ConnectPanel.tsx
│           │   │   ├── EngineStatusCard.tsx
│           │   │   └── NodeTable.tsx
│           │   ├── data/
│           │   │   ├── ConnectModal.tsx
│           │   │   └── ConnectorTable.tsx
│           │   └── dashboard/
│           │       ├── OverviewKPIs.tsx
│           │       ├── RunsChart.tsx
│           │       └── RecentRuns.tsx
│           └── lib/
│               ├── api/           ← split by domain
│               │   ├── index.ts   ← re-exports all
│               │   ├── client.ts  ← apiFetch + ApiError
│               │   ├── simulate.ts
│               │   ├── runs.ts
│               │   ├── jobs.ts
│               │   ├── connectors.ts
│               │   ├── infrastructure.ts
│               │   ├── deployments.ts
│               │   ├── billing.ts
│               │   ├── account.ts
│               │   └── team.ts
│               ├── auth.ts
│               └── console.ts
```

---

## 3. Mojo — Correct Usage + Expansion

### What Mojo is doing correctly today
- All compute-hot loops: Monte Carlo sampling, LHS, QMC Sobol, MCMC, bootstrap, scenario, sensitivity
- ExprNode AST: objective function parsed once, zero Python calls in simulation loop
- Cholesky decomposition for correlated variables
- `fast_f64()`: direct float conversion without `struct.pack`
- Zero Python in the hot path — binary called via stdin/stdout subprocess

### What Mojo should NOT do (keep out)
| Task | Why |
|------|-----|
| HTTP handling | Use Node.js gateway or FastAPI |
| Database queries | SQLAlchemy on Python |
| Cloud provider SDKs | AWS/Azure/GCP SDKs are Python/Go |
| Auth / RBAC | Python middleware |
| Job queue management | Celery/ARQ in Python |
| File I/O (config loading) | Python |

### Mojo expansion opportunities
| Opportunity | Benefit |
|-------------|---------|
| Split `main.mojo` into per-engine modules | Compile time, test isolation |
| Add `distributions.mojo` as standalone module | Reusable across all engine types |
| `expr_ast.mojo` as separate file | Unit-testable AST without full engine |
| `cholesky.mojo` as separate file | Reusable for multi-output correlation |
| Stream results chunked via stdout | Enable partial result streaming for large simulations |
| SIMD vectorization for `normal()` sampler | 4x throughput on AVX2 hardware |
| Parallel engine shards via Mojo threads | `n_jobs=4` spawns 4 threads, each owns subset of runs |

### Mojo size target: each file ≤ 300 lines
```
main.mojo          ~80 lines  (dispatch only)
distributions.mojo ~250 lines (20 distributions)
expr_ast.mojo      ~200 lines (AST parser + evaluator)
cholesky.mojo      ~80 lines  (Cholesky + correlation apply)
types.mojo         ~60 lines  (shared structs)
engines/monte_carlo.mojo  ~100 lines
engines/qmc_sobol.mojo    ~120 lines
engines/lhs.mojo          ~80 lines
engines/bootstrap.mojo    ~100 lines
engines/scenario.mojo     ~80 lines
engines/sensitivity.mojo  ~120 lines
engines/mcmc.mojo         ~160 lines
```

---

## 4. Node.js — Where It Fits

Python (asyncio/FastAPI) is excellent for ML-adjacent orchestration and database access. Node.js/Deno are better for:

| Layer | Node.js Role | Why |
|-------|-------------|-----|
| **API Gateway** | Hono on Node 22 LTS | ~3ms cold start, 100k req/s on single process, native WebSocket, built-in rate limiting via `@upstash/ratelimit` |
| **Auth token validation** | JWT verify at gateway | Offloads Python from `Authorization: Bearer` check — done in <1ms in Node |
| **Redis hot-path caching** | API key lookup cache | `ioredis` on Node is ~2x faster than `redis.asyncio` for simple GET/SET |
| **WebSocket streaming** | Job status SSE/WS | Node's `EventEmitter` + native WS is far simpler than Python `asyncio` SSE |
| **Webhook dispatch** | Outbound HTTP fan-out | Node handles 10k concurrent outbound connections naturally |
| **Static asset CDN proxy** | Portal edge functions | Next.js middleware already runs on Node at the edge |

### Gateway architecture (Hono on Node 22)

```
Client
  │
  ▼
apps/gateway/  (Node.js — Hono)       Port 443/8080
  │  - JWT/Bearer validation (< 1ms)
  │  - Rate limiting (Upstash Redis sliding window)
  │  - Org-level request routing (shared vs dedicated)
  │  - WebSocket upgrade for /v1/jobs/stream
  │  - Prometheus metrics
  │
  ├─→ /v1/simulate          → Python FastAPI (compute orchestration)
  ├─→ /v1/jobs/*            → Python FastAPI + Celery worker
  ├─→ /v1/simulate (stream) → Node WebSocket bridge → Mojo stdout pipe
  └─→ /mcp/*                → Python MCP server
```

### Node.js does NOT replace
- SQLAlchemy / Alembic (Python owns DB schema)
- FastAPI route handlers (Python orchestration)
- Mojo compute engine
- Celery/ARQ workers (Python)
- Stripe / cloud provider SDK calls (Python)

---

## 5. Python FastAPI — Right-sizing

Python stays for all business logic that needs:
- SQLAlchemy ORM + Alembic migrations
- Stripe, AWS/Azure/GCP SDK calls
- Pydantic schema validation
- Structlog + audit trail
- Celery/ARQ task queue
- ML-adjacent code (numpy, scipy, statsmodels — for analytics endpoints only)

### Python exposure to minimize
- **Remove Python fallback engines** — [`apps/api_server/compute/python_engine/`](../apps/api_server/compute/python_engine/) should only exist for dev/CI when Mojo binary is not compiled. Production: Mojo only.
- **Remove Python in hot loops** — `simulation_service.py` builds the payload and calls Mojo. Nothing else.
- **Offload auth header parsing** to Node gateway — Python only sees already-validated org_id in a trusted internal header (`X-Org-Id`).

---

## 6. Portal — Component Extraction Rules

**Rule: No page file may exceed 400 lines.** If it does, extract to `components/`.

### Page → Component split

#### [`simulations/page.tsx`](../apps/portal/src/app/dashboard/simulations/page.tsx) (1,740 → ~150 lines)
```
components/simulation/NewRunModal.tsx          ~300 lines
components/simulation/ExpandedRow.tsx          ~400 lines
components/simulation/SimulationsTable.tsx     ~200 lines
components/simulation/SimulationsFilters.tsx   ~100 lines
components/simulation/RunVolumeChart.tsx        ~80 lines
```

#### [`simulations/new/page.tsx`](../apps/portal/src/app/dashboard/simulations/new/page.tsx) (1,435 → ~100 lines)
```
components/simulation/VariableRow.tsx          ~250 lines
components/simulation/CorrelationEditor.tsx    ~200 lines
components/simulation/ModelSelector.tsx        ~120 lines
components/simulation/SimulationForm.tsx       ~300 lines
```

#### [`infrastructure/page.tsx`](../apps/portal/src/app/dashboard/infrastructure/page.tsx) (2,041 → ~150 lines)
```
components/infrastructure/DeploymentWizard.tsx  ~350 lines
components/infrastructure/ConnectPanel.tsx      ~400 lines
components/infrastructure/EngineStatusCard.tsx  ~120 lines
components/infrastructure/NodeTable.tsx         ~150 lines
```

#### [`data/page.tsx`](../apps/portal/src/app/dashboard/data/page.tsx) (1,409 → ~150 lines)
```
components/data/ConnectModal.tsx               ~400 lines
components/data/ConnectorTable.tsx             ~250 lines
components/data/ConnectorCard.tsx              ~100 lines
```

#### [`dashboard/page.tsx`](../apps/portal/src/app/dashboard/page.tsx) (1,223 → ~120 lines)
```
components/dashboard/OverviewKPIs.tsx          ~150 lines
components/dashboard/ActivityChart.tsx          ~120 lines
components/dashboard/RecentRuns.tsx             ~150 lines
components/dashboard/UsageBreakdown.tsx         ~120 lines
```

#### [`lib/api.ts`](../apps/portal/src/lib/api.ts) (565 → split by domain)
```
lib/api/client.ts          (apiFetch, ApiError, getApiKey)
lib/api/simulate.ts        (runSimulation, listSimulations, getAnalytics)
lib/api/jobs.ts            (submitJob, getJob, cancelJob, listJobs)
lib/api/runs.ts            (listRuns, getRun)
lib/api/connectors.ts      (listConnectors, createConnector, testConnector, deleteConnector)
lib/api/infrastructure.ts  (getInfrastructure, getDeployment)
lib/api/deployments.ts     (listDeploymentRegions, createDeployment, deleteDeployment)
lib/api/billing.ts         (getBilling, getUsage, getInvoices)
lib/api/account.ts         (getMe, updateProfile, listApiKeys, createApiKey)
lib/api/team.ts            (listTeamMembers, inviteMember)
lib/api/index.ts           (re-export all)
```

---

## 7. MCP Server — Module Split

[`apps/mcp_server/server.py`](../apps/mcp_server/server.py) (856 → ~80 lines entry point)

```
apps/mcp_server/
├── server.py              ← entry point + argparse + transport dispatch (~80 lines)
├── config.py              ← env vars, API key, base URL
├── client.py              ← shared httpx client, _api() helper
├── registry.py            ← TOOLS dict assembled from tool modules
├── transports/
│   ├── stdio.py           ← run_stdio_server()
│   └── http_sse.py        ← run_http_server() + Starlette SSE + messages handler
└── tools/
    ├── simulate.py        ← tool_simulate() + TOOL_SPEC
    ├── runs.py            ← tool_list_runs() + tool_get_run()
    ├── analytics.py       ← tool_get_analytics()
    ├── usage.py           ← tool_get_usage()
    ├── jobs.py            ← tool_submit_job() + tool_get_job_status()
    ├── connectors.py      ← tool_list_connectors()
    └── recommend.py       ← tool_recommend()
```

---

## 8. Provisioner Service — Module Split

[`apps/api_server/services/provisioner_service.py`](../apps/api_server/services/provisioner_service.py) (612 → ~80 lines base)

```
apps/api_server/services/provisioner/
├── __init__.py             ← factory: get_provisioner(provider) + provision_deployment()
├── base.py                 ← BaseProvisioner ABC + ProvisionResult
├── region_meta.py          ← _AWS_REGION_META, _AZURE_REGION_META, _GCP_REGION_META dicts
├── regions.py              ← fetch_aws_regions(), fetch_azure_regions(), fetch_gcp_regions(), get_available_regions()
├── aws.py                  ← AWSProvisioner (ECS Fargate + RDS + ElastiCache)
├── azure.py                ← AzureProvisioner (Container Instances + Flexible PostgreSQL)
└── gcp.py                  ← GCPProvisioner (Cloud Run + Cloud SQL + Memorystore)
```

---

## 9. Scalability Architecture for 100k Customers

### Request flow at scale

```
                          ┌─────────────────────────────┐
                          │   CDN / Cloudflare (edge)    │
                          │   DDoS protection, TLS term  │
                          └─────────────┬───────────────┘
                                        │
                          ┌─────────────▼───────────────┐
                          │   Node.js API Gateway        │
                          │   Hono + Upstash rate limit  │
                          │   JWT validation < 1ms       │
                          │   Horizontal scaling: N pods │
                          └─────┬────────────┬──────────┘
                                │            │
               ┌────────────────▼─┐    ┌─────▼────────────────┐
               │  Python FastAPI   │    │  WebSocket Handler    │
               │  Orchestration    │    │  (Node.js streams)    │
               │  Pydantic / ORM   │    │  job status SSE       │
               └────────┬─────────┘    └──────────────────────┘
                        │
        ┌───────────────┼──────────────────┐
        │               │                  │
┌───────▼──────┐ ┌──────▼──────┐ ┌────────▼──────┐
│ Mojo Engine  │ │ PostgreSQL   │ │ Redis Cluster  │
│ (subprocess) │ │ (PgBouncer)  │ │ (cache + queue)│
│ Shared pool  │ │ per-org row  │ │ rate limits    │
└──────────────┘ └─────────────┘ └───────────────┘

Dedicated org data plane:
┌──────────────────────────────────┐
│ Per-org container (ECS/CR/ACI)   │
│  └── Mojo binary                 │
│  └── PostgreSQL (isolated)       │
│  └── Redis (isolated)            │
└──────────────────────────────────┘
```

### Scaling targets and how to hit them

| Metric | Target | Mechanism |
|--------|--------|-----------|
| 100k concurrent orgs | Shared pool: 1 Mojo binary per worker pod, 10-20 pods | HPA on CPU > 70% |
| 10k req/s at peak | Node gateway: horizontal, stateless | AWS ALB / GCP Cloud Load Balancing |
| < 50ms p99 auth | Redis API key cache, 5min TTL | Already implemented |
| < 200ms p99 simulate (10k runs) | Mojo native binary, no Python in hot loop | Already correct |
| < 500ms p99 simulate (100k runs) | Mojo async subprocess, Celery for >100k | Job queue for large |
| Zero downtime deployments | Kubernetes rolling, readiness probe on `/v1/health` | Already supported |
| Per-org isolation | Dedicated data plane on enterprise tier | Provisioner service |
| Multi-region | Deployment wizard → org picks region | Already implemented |

### Database scaling
- **PgBouncer** in front of PostgreSQL — connection pooling (already feasible, add via Docker)
- **Read replicas** for `/v1/runs`, `/v1/analytics` (read-heavy, non-transactional)
- **Partitioning**: `simulation_runs` table partitioned by `created_at` (monthly) — supports 100M+ rows
- **Indexes to add**: `(org_id, created_at DESC)` on `simulation_runs`, `(org_id, status)` on `jobs`

### Worker scaling
- **Celery + Redis** for async jobs — already in `apps/worker/`
- **Priority queues**: `simulate:high` (interactive), `simulate:batch` (API bulk), `provision:cloud` (async)
- **Concurrency**: 1 Mojo subprocess per Celery worker process (CPU-bound, no GIL contention)

---

## 10. Implementation Phases

### Phase A — Mojo modularization (zero breaking changes)
1. Create `mojo/engine/distributions.mojo` — extract all distribution samplers
2. Create `mojo/engine/math/expr_ast.mojo` — extract ExprNode AST
3. Create `mojo/engine/math/cholesky.mojo` — extract Cholesky
4. Create `mojo/engine/engines/` — one file per engine type
5. Slim `mojo/engine/main.mojo` to dispatch-only entry point
6. Rebuild binary, run smoke tests

### Phase B — Python provisioner split
1. Create `apps/api_server/services/provisioner/` package
2. Move region metadata to `region_meta.py`
3. Move fetch functions to `regions.py`
4. Move AWS to `aws.py`, Azure to `azure.py`, GCP to `gcp.py`
5. Create `__init__.py` factory
6. Update all imports

### Phase C — MCP server split
1. Extract `config.py`, `client.py`
2. Create `tools/` directory with one file per tool
3. Create `transports/stdio.py` and `transports/http_sse.py`
4. Create `registry.py` — TOOLS dict assembled from tool modules
5. Slim `server.py` to ~80 lines

### Phase D — Portal component extraction
1. Create `apps/portal/src/components/` directory structure
2. Extract simulation components (NewRunModal, ExpandedRow, VariableRow)
3. Extract infrastructure components (DeploymentWizard, ConnectPanel, NodeTable)
4. Extract data components (ConnectModal, ConnectorTable)
5. Extract dashboard components (OverviewKPIs, ActivityChart, RecentRuns)
6. Split `lib/api.ts` into per-domain files

### Phase E — Node.js API Gateway
1. Create `apps/gateway/` with Hono + TypeScript
2. Implement JWT/Bearer validation (< 1ms)
3. Implement rate limiting with Upstash/Redis sliding window
4. Implement proxy to Python FastAPI
5. Implement WebSocket upgrade for job streaming
6. Add Prometheus counters + p99 histograms
7. Add Docker configuration
8. Update `docker-compose.yml` to route external traffic through gateway

### Phase F — Connectors router split
1. Extract schemas to `apps/api_server/services/connectors/schemas.py`
2. Extract connection testing logic to `apps/api_server/services/connectors/tester.py`
3. Slim `routers/connectors.py` to route handlers only

### Phase G — Database scalability
1. Add PgBouncer to `docker-compose.yml`
2. Add read replica support to `db/session.py` (`AsyncReadSession`)
3. Add partition migration for `simulation_runs` by month
4. Add missing indexes migration
5. Add `async with AsyncReadSession() as db` in all read-only endpoints

---

## 11. What NOT to Change

| Item | Keep as-is | Reason |
|------|-----------|--------|
| `mojo_adapter.py` | Keep | Perfect subprocess bridge, already async |
| FastAPI router structure | Keep | Well organized, 1 file per resource |
| Alembic migrations | Keep | Sequential, well-named |
| SQLAlchemy models | Keep | Clean, separate files |
| `middleware/auth.py` | Keep | Bearer + X-API-Key fallback correct |
| `middleware/rbac.py` | Keep | Role hierarchy correct |
| Python SDK + TS SDK | Keep | Both already use Bearer, well structured |
| `apps/worker/` | Keep + extend | Add provision_task + cost_sync_task |

---

## Summary

| Runtime | Role | Lines budget per file |
|---------|------|-----------------------|
| **Mojo** | All simulation compute — distributions, engines, AST, Cholesky | ≤ 300 |
| **Python (FastAPI)** | HTTP orchestration, DB, auth, Stripe, cloud SDK, Celery | ≤ 400 |
| **Node.js (Hono)** | API gateway, rate limiting, JWT validation, WebSocket streaming | ≤ 200 |
| **Next.js** | Portal pages (thin) + shared React components | Pages ≤ 150, components ≤ 400 |
| **TypeScript (SDK)** | Client library | ≤ 300 per file |
| **Python (SDK)** | Client library | ≤ 300 per file |
