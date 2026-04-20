# Universal Decision Engine — Granular A-Z Task Breakdown

> **Status:** Implementation Ready  
> **Linked to:** `plans/UNIVERSAL_DECISION_ENGINE_ARCHITECTURE.md`  
> **Convention:** Every task has subtasks, acceptance criteria, test requirements, and debug checkpoints.  
> **Tracking:** Mark tasks `[x]` when complete. Never skip a debug checkpoint.

---

## How to Use This Document

1. Work tasks in phase order — never start a phase before the previous phase's Definition of Done is verified
2. Every **subtask** is a discrete unit of work that can be PR'd independently
3. Every **debug checkpoint** must be manually verified before moving forward
4. Every **test requirement** must pass (not just exist) before the phase is closed
5. Use `[~]` for in-progress, `[x]` for complete, `[ ]` for pending, `[!]` for blocked

---

## Phase 1 — Open Core Foundation

**Exit criterion:** Developer clones repo, runs `make dev`, calls `POST /v1/simulate` with a real API key, gets back a valid decision envelope, and Mojo is actually invoked (not mocked).

---

### 1.1 Repository and Workspace Initialization

#### Subtasks
- [ ] 1.1.1 Create root `decision-engine/` directory and `git init`
- [ ] 1.1.2 Create `.gitignore` (Python, Node, Mojo, Docker, secrets, env files)
- [ ] 1.1.3 Create root `pyproject.toml` with workspace config (Ruff, Black, MyPy, Pytest settings)
- [ ] 1.1.4 Create `Makefile` with targets: `dev`, `test`, `lint`, `migrate`, `build`, `clean`
- [ ] 1.1.5 Create full directory scaffold per architecture plan section 9.2
- [ ] 1.1.6 Create `.env.example` with all required env var keys (no values)
- [ ] 1.1.7 Create `pre-commit` config (Ruff, Black, MyPy, trailing whitespace)
- [ ] 1.1.8 Create root `README.md` with project summary, quickstart, and link to docs

#### Acceptance Criteria
- `git status` shows clean tree after scaffold
- `make lint` runs without error on empty scaffold
- `.env.example` contains every key referenced in any config file

#### Debug Checkpoints
- [ ] Verify directory tree matches `plans/UNIVERSAL_DECISION_ENGINE_ARCHITECTURE.md` section 9.2 exactly
- [ ] Verify `.gitignore` excludes `.env`, `__pycache__`, `*.pyc`, `node_modules`, `mojo_build/`

---

### 1.2 Docker Compose Local Stack

#### Subtasks
- [ ] 1.2.1 Write `infra/docker/docker-compose.yml` with services: `postgres`, `redis`, `minio`, `api`, `worker`
- [ ] 1.2.2 Configure Postgres service: image `postgres:16`, named volume, health check
- [ ] 1.2.3 Configure Redis service: image `redis:7-alpine`, health check
- [ ] 1.2.4 Configure MinIO service: image `minio/minio`, S3-compatible, health check, default bucket creation
- [ ] 1.2.5 Configure `api` service: build from `Dockerfile.api`, env from `.env`, depends_on with health checks
- [ ] 1.2.6 Configure `worker` service: build from `Dockerfile.worker`, same env, depends_on api + redis
- [ ] 1.2.7 Write `infra/docker/Dockerfile.api`: multi-stage, non-root user, Python 3.12 slim base
- [ ] 1.2.8 Write `infra/docker/Dockerfile.worker`: same pattern as API
- [ ] 1.2.9 Add `make dev` target: `docker compose up --build`
- [ ] 1.2.10 Add MinIO bucket initialization script (run as init container or entrypoint)

#### Acceptance Criteria
- `make dev` starts all 5 services with no errors
- Postgres reachable at `localhost:5432`
- Redis reachable at `localhost:6379`
- MinIO console reachable at `localhost:9001`
- API container starts and passes health check
- Worker container starts and connects to Redis queue

#### Debug Checkpoints
- [ ] `docker compose ps` shows all services as "healthy"
- [ ] `docker compose logs api` shows no Python import errors
- [ ] `docker compose logs worker` shows no connection errors to Redis
- [ ] `docker exec -it postgres psql -U postgres -c "\l"` lists databases

---

### 1.3 FastAPI Application Skeleton

#### Subtasks
- [ ] 1.3.1 Create `apps/api-server/main.py`: FastAPI app init, lifespan handler, include routers
- [ ] 1.3.2 Create `apps/api-server/config.py`: Pydantic `BaseSettings` reading all env vars with types
- [ ] 1.3.3 Create `apps/api-server/middleware/request_id.py`: inject `X-Request-Id` on every request/response
- [ ] 1.3.4 Create `apps/api-server/middleware/logging.py`: structured JSON log per request (method, path, status, duration, request_id)
- [ ] 1.3.5 Create `apps/api-server/middleware/cors.py`: CORS from config `CORS_ORIGINS`
- [ ] 1.3.6 Create `apps/api-server/routers/meta.py`: `GET /v1/health` and `GET /v1/version`
- [ ] 1.3.7 Wire all middleware and routers into `main.py`
- [ ] 1.3.8 Add `apps/api-server/requirements.txt` with pinned deps: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `structlog`, `httpx`

#### Health endpoint response schema
```json
GET /v1/health
{
  "status": "ok",
  "timestamp": "2026-03-20T18:00:00Z"
}
```
```json
GET /v1/version
{
  "api_version": "1.0.0",
  "engine_version": "0.1.0",
  "environment": "development"
}
```

#### Acceptance Criteria
- `GET /v1/health` returns `200 {"status": "ok"}`
- `GET /v1/version` returns version object
- Every response has `X-Request-Id` header
- Request logs appear as single-line JSON in `docker compose logs api`

#### Test Requirements
- [ ] `tests/unit/test_meta_routes.py`: test health returns 200, version returns correct fields
- [ ] `tests/unit/test_middleware.py`: test request_id injected, test logging fields present

#### Debug Checkpoints
- [ ] `curl http://localhost:8000/v1/health` returns `{"status": "ok"}`
- [ ] `curl http://localhost:8000/v1/version` returns version fields
- [ ] `curl http://localhost:8000/v1/health` shows log line in `docker compose logs api`
- [ ] Response header `X-Request-Id` present in curl output

---

### 1.4 Database Models and Migrations

#### Subtasks
- [ ] 1.4.1 Add `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `greenlet` to requirements
- [ ] 1.4.2 Create `apps/api-server/db/session.py`: async SQLAlchemy engine + session factory
- [ ] 1.4.3 Create `apps/api-server/db/base.py`: `DeclarativeBase` with UUID primary key mixin and timestamp mixin
- [ ] 1.4.4 Create `apps/api-server/models/organization.py`: `Organization` model (id, name, slug, plan, status, stripe_customer_id, timestamps)
- [ ] 1.4.5 Create `apps/api-server/models/user.py`: `User` model (id, org_id FK, email, password_hash, name, role, status, email_verified, timestamps)
- [ ] 1.4.6 Create `apps/api-server/models/api_key.py`: `APIKey` model (id, org_id FK, user_id FK, label, key_prefix, hashed_key, status, expires_at, last_used_at, timestamps)
- [ ] 1.4.7 Create `apps/api-server/models/simulation_run.py`: `SimulationRun` model (all fields per architecture data model)
- [ ] 1.4.8 Create `apps/api-server/models/__init__.py`: export all models
- [ ] 1.4.9 Initialize Alembic: `alembic init alembic` inside `apps/api-server/`
- [ ] 1.4.10 Configure `alembic/env.py` to use async engine and import all models
- [ ] 1.4.11 Generate first migration: `alembic revision --autogenerate -m "initial_schema"`
- [ ] 1.4.12 Verify migration SQL is correct (review generated file)
- [ ] 1.4.13 Apply migration: `alembic upgrade head`
- [ ] 1.4.14 Add `make migrate` target to Makefile

#### Acceptance Criteria
- `make migrate` applies migrations with no errors
- All 4 tables exist in Postgres with correct columns and constraints
- Foreign keys enforced (org_id references organizations.id etc.)
- UUID primary keys on all tables
- `created_at` and `updated_at` auto-populated

#### Test Requirements
- [ ] `tests/integration/test_db_models.py`: insert Organization, User, APIKey, SimulationRun; verify FK constraints; verify unique constraints on email and org slug

#### Debug Checkpoints
- [ ] `docker exec -it postgres psql -U postgres -d decision_engine -c "\dt"` shows all 4 tables
- [ ] `docker exec -it postgres psql -U postgres -d decision_engine -c "\d organizations"` shows all columns
- [ ] Attempt to insert duplicate email → verify unique constraint fires
- [ ] Attempt to insert user with non-existent org_id → verify FK constraint fires

---

### 1.5 API Key Authentication Middleware

#### Subtasks
- [ ] 1.5.1 Create `apps/api-server/services/auth_service.py`: `hash_key(raw_key)`, `generate_api_key()`, `verify_api_key(raw_key)` functions
- [ ] 1.5.2 `generate_api_key()`: create `de_live_` + 32 random base62 chars; return `(raw_key, prefix, hash)`
- [ ] 1.5.3 `verify_api_key(raw_key)`: SHA-256 hash → query DB → return `{org_id, key_id, plan, status}` or None
- [ ] 1.5.4 Add Redis caching to `verify_api_key`: cache `hash → {org_id, key_id, plan}` for 5 min TTL
- [ ] 1.5.5 Create `apps/api-server/middleware/auth.py`: FastAPI dependency `get_current_org()` — extract key from `X-API-Key` or `Authorization: Bearer`, call verify, raise 401 if invalid
- [ ] 1.5.6 Seed script: `scripts/seed_dev.py` — create dev org + user + api_key, print raw key to terminal
- [ ] 1.5.7 Add `make seed` target to Makefile

#### Acceptance Criteria
- `GET /v1/health` accessible without auth
- `POST /v1/simulate` returns `401` without valid key
- `POST /v1/simulate` proceeds with valid key
- Invalid/revoked key returns `401` with error schema
- Cache hit verified (second identical request does not hit DB)

#### Test Requirements
- [ ] `tests/unit/test_auth_service.py`: test key generation format, hash consistency, invalid key returns None
- [ ] `tests/integration/test_auth_middleware.py`: test 401 on missing key, 401 on bad key, 200 on valid key, 401 on revoked key

#### Debug Checkpoints
- [ ] `make seed` prints a real API key starting with `de_live_`
- [ ] `curl -H "X-API-Key: de_live_invalid" http://localhost:8000/v1/simulate` returns 401
- [ ] `curl -H "X-API-Key: <real_key>" http://localhost:8000/v1/health` returns 200
- [ ] Redis key `apikey:{hash}` visible in Redis after first authenticated request

---

### 1.6 Pydantic Request/Response Models

#### Subtasks
- [ ] 1.6.1 Create `apps/api-server/schemas/common.py`: `ErrorDetail`, `ErrorResponse`, `PaginationMeta`
- [ ] 1.6.2 Create `apps/api-server/schemas/simulate.py`: `SimulateRequestAuto`, `SimulateRequestExpert`, `SimulateRequest` (union), `DistributionParam`, `VariableSpec`, `CorrelationSpec`, `ScoringSpec`
- [ ] 1.6.3 Create `apps/api-server/schemas/response.py`: `PercentileSummary`, `MetricsSummary`, `DecisionEnvelope` (full response schema)
- [ ] 1.6.4 Add strict Pydantic validation: `model_config = ConfigDict(strict=True)`
- [ ] 1.6.5 Add field validators: `runs` must be 1–1,000,000; `seed` must be non-negative int or None; distribution params must be internally consistent
- [ ] 1.6.6 Create `apps/api-server/schemas/__init__.py`: export all schemas

#### Acceptance Criteria
- Invalid request body (missing required field) returns `422` with field-level error details
- `mode: "auto"` with `{low, high, objective}` passes validation
- `mode: "expert"` with full distribution spec passes validation
- Mixing auto fields with expert fields raises validation error
- All field errors include `field` path and `issue` description

#### Test Requirements
- [ ] `tests/unit/test_schemas.py`: test valid auto payload, valid expert payload, missing fields, invalid distribution params, invalid runs count, mismatched mode fields

#### Debug Checkpoints
- [ ] POST with `{}` body returns 422 with readable field errors
- [ ] POST with `mode: "auto"` and missing `objective` returns 422 citing `objective`
- [ ] POST with `runs: 0` returns 422 with validation error on `runs`

---

### 1.7 Mojo Simulation Engine (Public Edition)

#### Subtasks
- [ ] 1.7.1 Initialize `mojo/` directory with `mojo.toml` project config
- [ ] 1.7.2 Create `mojo/engine/main.mojo`: CLI entry point — reads JSON from stdin, dispatches to engine, writes JSON to stdout
- [ ] 1.7.3 Create `mojo/distributions/normal.mojo`: `NormalDistribution` struct with `sample(seed, n) -> Tensor[DType.float64]`
- [ ] 1.7.4 Create `mojo/distributions/uniform.mojo`: `UniformDistribution` struct
- [ ] 1.7.5 Create `mojo/distributions/triangular.mojo`: `TriangularDistribution` struct
- [ ] 1.7.6 Create `mojo/distributions/lognormal.mojo`: `LognormalDistribution` struct
- [ ] 1.7.7 Create `mojo/engine/monte_carlo.mojo`: `run_simulation(config: SimConfig) -> SimResult` — seeds PRNG, samples all variables, computes correlations (identity matrix for v1), runs N iterations
- [ ] 1.7.8 Create `mojo/stats/percentiles.mojo`: `compute_percentiles(samples: Tensor, ps: List[Float64]) -> Dict`
- [ ] 1.7.9 Create `mojo/stats/summary.mojo`: `compute_summary(samples: Tensor) -> SummaryStats` (mean, median, std, variance)
- [ ] 1.7.10 Create `mojo/stats/risk.mojo`: `probability_of_loss(samples: Tensor) -> Float64`, `var_95(samples) -> Float64`
- [ ] 1.7.11 Create `mojo/engine/scoring.mojo`: `score_scenario(summary: SummaryStats, weights: ScoringWeights) -> Float64`
- [ ] 1.7.12 Build engine: `mojo build mojo/engine/main.mojo -o mojo_build/simulate`
- [ ] 1.7.13 Write `mojo/bindings/python_adapter.py`: `invoke_engine(payload: dict) -> dict` — serialize to JSON, call subprocess `mojo_build/simulate`, parse stdout JSON, raise on non-zero exit

#### Input/Output Contract (stdin → stdout)
```json
// stdin
{
  "seed": 42,
  "runs": 10000,
  "variables": [
    {"name": "revenue", "distribution": "normal", "params": {"mean": 100000, "std": 20000}}
  ],
  "objective": "revenue"
}

// stdout
{
  "samples": [/* omitted for large payloads */],
  "summary": {"mean": 100012.3, "median": 99987.1, "std": 19998.2, "variance": 399928000.0},
  "percentiles": {"p5": 67192.0, "p25": 86503.0, "p50": 99987.0, "p75": 113421.0, "p95": 132891.0},
  "risk": {"probability_of_loss": 0.0, "var_95": 67192.0},
  "score": 0.82,
  "engine_version": "0.1.0"
}
```

#### Acceptance Criteria
- `echo '{"seed":42,"runs":10000,...}' | ./mojo_build/simulate` returns valid JSON to stdout
- Same seed always produces same output (determinism test)
- Different seed produces different output
- Invalid input JSON exits with code 1 and error message on stderr

#### Test Requirements
- [ ] `tests/unit/test_mojo_engine.py`: test normal distribution samples within 3 sigma of mean; test determinism with same seed; test different seeds produce different output; test all 4 distributions produce non-empty output
- [ ] `tests/unit/test_mojo_stats.py`: test percentile calculation correctness against known datasets; test probability_of_loss = 0 for all-positive samples; test var_95 at known quantile

#### Debug Checkpoints
- [ ] `./mojo_build/simulate` runs without segfault
- [ ] Determinism: run twice with seed=42, diff the outputs → identical
- [ ] Run with seed=1 vs seed=2 → different outputs
- [ ] Run with 100 iterations: all 5 percentiles present and in correct order (p5 < p25 < p50 < p75 < p95)
- [ ] Malformed JSON input → exit code 1, readable error on stderr

---

### 1.8 Simulation Service and `/v1/simulate` Endpoint

#### Subtasks
- [ ] 1.8.1 Create `apps/api-server/services/simulation_service.py`: `run_simulation(request: SimulateRequest, org_id: UUID) -> DecisionEnvelope`
- [ ] 1.8.2 `run_simulation()`: validate org quota (stub for now), build Mojo input payload, call `invoke_engine()`, map output to `DecisionEnvelope`, write `SimulationRun` record to DB
- [ ] 1.8.3 Create `apps/api-server/compute/mojo_adapter.py`: import and wrap `python_adapter.py` with error handling (`subprocess.TimeoutExpired`, `json.JSONDecodeError`, non-zero exit)
- [ ] 1.8.4 Create `apps/api-server/routers/simulate.py`: `POST /v1/simulate` — auth dependency, call service, return `DecisionEnvelope`
- [ ] 1.8.5 Wire `simulate` router into `main.py`
- [ ] 1.8.6 Add `run_id` to response — use `SimulationRun.id` from DB write
- [ ] 1.8.7 Add execution timing: measure wall time of Mojo call, include in `execution_ms` field
- [ ] 1.8.8 Map auto mode inputs to Mojo payload: derive triangular from `{low, high}` with midpoint = `(low+high)/2`

#### Acceptance Criteria
- `POST /v1/simulate` with valid auto payload returns `200` with full `DecisionEnvelope`
- `run_id` in response is a valid UUID stored in `simulation_runs` table
- `execution_ms` reflects real timing
- Mojo is actually invoked (not mocked): verify by checking `engine_version` from Mojo output in response
- `POST /v1/simulate` without auth returns `401`
- Malformed body returns `422`
- Mojo crash returns `500` with error schema (not raw Python traceback)

#### Test Requirements
- [ ] `tests/integration/test_simulate_endpoint.py`: test valid auto payload returns 200 + full envelope; test run stored in DB; test auth required; test malformed body 422; test engine_version present in response
- [ ] `tests/unit/test_simulation_service.py`: test auto→expert payload mapping; test Mojo adapter error wrapped into 500; test run record written with correct fields

#### Debug Checkpoints
- [ ] `curl -H "X-API-Key: <key>" -d '{"mode":"auto","scenario":{...}}' http://localhost:8000/v1/simulate` returns 200
- [ ] Response contains `run_id`, `recommended_action`, `metrics`, `percentiles`
- [ ] `SELECT * FROM simulation_runs ORDER BY created_at DESC LIMIT 1;` shows the run in DB
- [ ] `engine_version` in response matches value from `mojo_build/simulate --version` (or embedded constant)
- [ ] Kill mojo binary → simulate endpoint returns 500 with error schema (not 500 with traceback)

---

### 1.9 OpenAPI Spec Skeleton

#### Subtasks
- [ ] 1.9.1 Configure FastAPI `app` with `title`, `version`, `description`, `openapi_url="/openapi.json"`, `docs_url="/docs"`, `redoc_url="/redoc"`
- [ ] 1.9.2 Add Pydantic `model_config` with `json_schema_extra` examples on all request/response models
- [ ] 1.9.3 Export generated OpenAPI to `schemas/openapi/openapi.yaml`: `python -c "import yaml, json; print(yaml.dump(json.load(...)))"` — add to `make` target
- [ ] 1.9.4 Validate OpenAPI schema with `openapi-spec-validator` in CI check
- [ ] 1.9.5 Add `make openapi` target: generate and validate spec

#### Acceptance Criteria
- `GET /openapi.json` returns valid OpenAPI 3.1 JSON
- `GET /docs` renders Swagger UI with all routes documented
- Generated `openapi.yaml` passes `openapi-spec-validator` with zero errors or warnings
- All request/response models have examples in the spec

#### Test Requirements
- [ ] `tests/contract/test_openapi_schema.py`: load `openapi.json` from running server, validate with `openapi-spec-validator`, assert all required paths present

#### Debug Checkpoints
- [ ] `curl http://localhost:8000/openapi.json | python -m json.tool` outputs valid JSON
- [ ] Open `http://localhost:8000/docs` in browser — all routes visible and documented
- [ ] `make openapi` generates `schemas/openapi/openapi.yaml` with no errors
- [ ] `openapi-spec-validator schemas/openapi/openapi.yaml` exits 0

---

### Phase 1 — Integration Test Suite

- [ ] `tests/integration/test_phase1_e2e.py`: Full flow test — start stack, call health, call version, call simulate with real Mojo, verify DB record, verify response schema
- [ ] Run `make test` — all tests green
- [ ] Run `make lint` — zero lint errors
- [ ] Run `make dev` on a clean machine (no cached Docker layers) — stack starts successfully

### Phase 1 — Definition of Done Verification

- [ ] `make dev` starts all services with no manual steps
- [ ] `make seed` prints a valid API key
- [ ] `curl` to `/v1/simulate` with that key returns a full decision envelope
- [ ] Mojo binary is invoked (not mocked) — confirm via log line in simulate service
- [ ] `SELECT COUNT(*) FROM simulation_runs;` returns 1 after one simulate call
- [ ] All unit and integration tests pass
- [ ] OpenAPI spec valid and exports cleanly

---

## Phase 2 — Decision APIs + Auth

**Exit criterion:** All sync endpoints live, self-serve sign-up works end-to-end, full OpenAPI spec validated.

---

### 2.1 Auth Endpoints (Self-Serve Sign-Up)

#### Subtasks
- [ ] 2.1.1 Add `bcrypt` and `python-jose` to requirements
- [ ] 2.1.2 Create `apps/api-server/routers/auth.py`: `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`
- [ ] 2.1.3 `POST /auth/signup`: validate email, hash password, create Organization (slug from email domain), create User (owner role), create one APIKey automatically, return `{user, org, api_key_raw}` — show key only once
- [ ] 2.1.4 `POST /auth/login`: verify email + password, issue JWT session token (7 day expiry)
- [ ] 2.1.5 Create `apps/api-server/services/user_service.py`: `create_user()`, `get_user_by_email()`, `verify_password()`
- [ ] 2.1.6 Create `apps/api-server/services/org_service.py`: `create_org()`, `get_org_by_id()`
- [ ] 2.1.7 Add duplicate email check: return `409 {"error": {"code": "email_already_exists", ...}}`
- [ ] 2.1.8 Add welcome email stub (log to console in dev, real email service hooked later)

#### Acceptance Criteria
- `POST /auth/signup` with valid email + password returns 201 with user, org, and raw API key
- `POST /auth/signup` with duplicate email returns 409
- `POST /auth/login` with correct creds returns JWT token
- `POST /auth/login` with wrong password returns 401
- Raw API key shown only once (signup response only)
- Password never stored in plaintext (verify via DB check)

#### Test Requirements
- [ ] `tests/integration/test_auth_endpoints.py`: test signup success, duplicate email 409, login success, login wrong password 401, verify password not in DB

#### Debug Checkpoints
- [ ] `curl -d '{"email":"test@example.com","password":"Password123!","name":"Test"}' http://localhost:8000/auth/signup` returns 201 with `api_key` field
- [ ] Second identical signup returns 409
- [ ] `SELECT password_hash FROM users WHERE email='test@example.com';` shows bcrypt hash (not plaintext)
- [ ] `SELECT hashed_key FROM api_keys ORDER BY created_at DESC LIMIT 1;` shows SHA-256 hash (not raw key)

---

### 2.2 API Key CRUD Endpoints

#### Subtasks
- [ ] 2.2.1 Create `apps/api-server/routers/api_keys.py`
- [ ] 2.2.2 `GET /v1/api-keys`: list all active keys for org (show prefix, label, created, last_used — never hash)
- [ ] 2.2.3 `POST /v1/api-keys`: create new key (label required), return raw key once
- [ ] 2.2.4 `DELETE /v1/api-keys/{id}`: set status to revoked, invalidate Redis cache entry
- [ ] 2.2.5 Add guard: cannot delete the last active key for an org

#### Test Requirements
- [ ] `tests/integration/test_api_key_routes.py`: list keys, create key, raw key returned once, delete key, verify Redis cache cleared, cannot delete last key

#### Debug Checkpoints
- [ ] Create 2 keys, list — both appear with prefix but no hash
- [ ] Delete key 1 → `GET /v1/api-keys` shows only key 2
- [ ] Attempt to delete key 2 (last key) → 400 with readable error
- [ ] After delete, old key returns 401 on next simulate call (cache cleared)

---

### 2.3 `/v1/recommend` Endpoint

#### Subtasks
- [ ] 2.3.1 Create `apps/api-server/routers/recommend.py`: `POST /v1/recommend`
- [ ] 2.3.2 Request schema: same as simulate but `actions` field — array of named scenario specs to compare
- [ ] 2.3.3 Simulation service: run simulate for each action, rank by expected value (v1 default)
- [ ] 2.3.4 Response: `recommended_action` (name of top-ranked action), `rationale`, `scenario_ranking` array
- [ ] 2.3.5 Validate: minimum 2 actions required, maximum 10 actions per request

#### Test Requirements
- [ ] `tests/integration/test_recommend_endpoint.py`: test 2-action comparison returns recommended_action; test action ranking order; test 1 action returns 422; test 11 actions returns 422

#### Debug Checkpoints
- [ ] POST with 2 actions → response has `recommended_action` matching the higher-EV scenario
- [ ] POST with 1 action → 422

---

### 2.4 `/v1/score` Endpoint

#### Subtasks
- [ ] 2.4.1 Create `apps/api-server/routers/score.py`: `POST /v1/score`
- [ ] 2.4.2 Request: single simulation spec + optional scoring weights
- [ ] 2.4.3 Response: all `DecisionEnvelope` fields plus `score` (0.0–1.0) and `score_breakdown`
- [ ] 2.4.4 Default scoring: weighted combination of `expected_value` (60%) and `1 - probability_of_loss` (40%)
- [ ] 2.4.5 Custom scoring weights: user-supplied `{"expected_value": 0.7, "downside_risk": 0.3}`

#### Test Requirements
- [ ] `tests/unit/test_scoring_logic.py`: test default weights, custom weights, score bounded 0–1, score breakdown fields present

---

### 2.5 `/v1/batch` Endpoint

#### Subtasks
- [ ] 2.5.1 Create `apps/api-server/routers/batch.py`: `POST /v1/batch`
- [ ] 2.5.2 Request: `{"items": [SimulateRequest, ...]}` — max 10 (free), 100 (pro+)
- [ ] 2.5.3 Execute items in parallel using `asyncio.gather`
- [ ] 2.5.4 Response: `{"results": [DecisionEnvelope, ...], "total": N, "failed": M}`
- [ ] 2.5.5 Partial failure: if one item fails, include error in that position, continue others
- [ ] 2.5.6 Billing: charge `N` simulation units for batch of N items

#### Test Requirements
- [ ] `tests/integration/test_batch_endpoint.py`: test 3-item batch returns 3 results; test partial failure (1 bad item) returns 2 good + 1 error; test over-limit batch returns 429

---

### 2.6 `/v1/compare` Endpoint

#### Subtasks
- [ ] 2.6.1 Create `apps/api-server/routers/compare.py`: `POST /v1/compare`
- [ ] 2.6.2 Request: `{"scenarios": [{name, spec}, ...]}` — 2–10 scenarios
- [ ] 2.6.3 Response: full envelope for each + side-by-side comparison table (EV delta, risk delta, score delta)
- [ ] 2.6.4 Highlight winner in response: `{"winner": "scenario_name", "margin": {...}}`

---

### 2.7 Account Endpoints

#### Subtasks
- [ ] 2.7.1 `GET /v1/me`: return current user + org info
- [ ] 2.7.2 `GET /v1/usage`: return simulation count, API calls, compute units for current billing period
- [ ] 2.7.3 `GET /v1/limits`: return plan-based limits (max runs, max batch, rate limit)
- [ ] 2.7.4 `GET /v1/templates`: return list of built-in simulation templates (v1: 3 examples — financial, risk, comparison)
- [ ] 2.7.5 `GET /v1/distributions`: return list of supported distribution types with required params

#### Test Requirements
- [ ] `tests/integration/test_account_endpoints.py`: test `/v1/me` returns org and user; test `/v1/usage` counts increment after simulate; test `/v1/limits` matches plan config

---

### 2.8 Structured Logging and Metrics

#### Subtasks
- [ ] 2.8.1 Configure `structlog` with JSON renderer for production, pretty renderer for dev
- [ ] 2.8.2 Add `org_id`, `run_id`, `api_key_id`, `endpoint`, `duration_ms`, `billing_units` to every request log
- [ ] 2.8.3 Add `prometheus-fastapi-instrumentator` (or manual Prometheus metrics)
- [ ] 2.8.4 Expose `GET /metrics` endpoint (Prometheus text format)
- [ ] 2.8.5 Implement metrics: `http_requests_total`, `http_request_duration_seconds`, `simulations_total`, `simulation_duration_seconds`
- [ ] 2.8.6 Verify no sensitive data (API keys, raw payloads) appears in logs

#### Debug Checkpoints
- [ ] `curl http://localhost:8000/metrics` returns Prometheus text with all 4 metric names
- [ ] After 3 simulate calls, `simulations_total` counter = 3
- [ ] Grep logs for raw API key — must not appear
- [ ] Every log line has `request_id` and `org_id`

---

### 2.9 Full OpenAPI Spec Completion

#### Subtasks
- [ ] 2.9.1 Add all new routes to OpenAPI with full request/response schemas
- [ ] 2.9.2 Add `security` schemes (`ApiKeyAuth`, `BearerAuth`) to spec
- [ ] 2.9.3 Add `tags` to all operations for clean grouping
- [ ] 2.9.4 Add `x-code-samples` for curl, Python, TypeScript on key endpoints
- [ ] 2.9.5 Validate spec: `openapi-spec-validator schemas/openapi/openapi.yaml`
- [ ] 2.9.6 Manual import test: import spec into ChatGPT Actions — verify it imports without errors
- [ ] 2.9.7 Manual import test: import spec into Power Automate custom connector — verify it imports

#### Debug Checkpoints
- [ ] `openapi-spec-validator schemas/openapi/openapi.yaml` → 0 errors, 0 warnings
- [ ] Import into ChatGPT Actions → all endpoints visible, auth shows as API key
- [ ] Import into Power Automate → connector shows all operations

### Phase 2 — Definition of Done Verification

- [ ] All 8 route groups return correct responses
- [ ] Sign-up flow creates org + user + API key in one request
- [ ] Recommend endpoint returns ranked actions
- [ ] All test files pass
- [ ] OpenAPI imports cleanly into ChatGPT Actions and Power Automate

---

## Phase 3 — Async Platform + Webhooks

**Exit criterion:** Large simulation submitted as async job, worker processes it, webhook fires on completion.

---

### 3.1 Worker Service Setup

#### Subtasks
- [ ] 3.1.1 Create `apps/worker/` directory structure
- [ ] 3.1.2 Add `dramatiq[redis]`, `apscheduler` to requirements
- [ ] 3.1.3 Create `apps/worker/worker.py`: configure Dramatiq with Redis broker, define worker process entry point
- [ ] 3.1.4 Create `apps/worker/config.py`: same Pydantic settings pattern as API
- [ ] 3.1.5 Create `apps/worker/tasks/__init__.py`
- [ ] 3.1.6 Create `apps/worker/tasks/simulation_task.py`: `@dramatiq.actor run_simulation_job(job_id: str)` — load job from DB, invoke Mojo engine, update job status, fire webhook
- [ ] 3.1.7 Add worker to Docker Compose with `dramatiq apps.worker.worker` command
- [ ] 3.1.8 Add dead-letter queue config: failed jobs after 3 retries → DLQ

#### Debug Checkpoints
- [ ] `docker compose logs worker` shows `Connected to Redis broker`
- [ ] Submit dummy Dramatiq message manually → worker logs show it was received and processed

---

### 3.2 Job Database Model and Service

#### Subtasks
- [ ] 3.2.1 Create `apps/api-server/models/job.py`: `Job` model (all fields per data model in architecture doc)
- [ ] 3.2.2 Create `apps/api-server/models/usage_record.py`: `UsageRecord` model
- [ ] 3.2.3 Create `apps/api-server/models/audit_event.py`: `AuditEvent` model
- [ ] 3.2.4 Generate and apply Alembic migration for new tables
- [ ] 3.2.5 Create `apps/api-server/services/job_service.py`: `create_job()`, `get_job()`, `update_job_status()`, `cancel_job()`
- [ ] 3.2.6 Job lifecycle state machine: `queued → validating → running → completed/failed/cancelled`; invalid transitions return error

#### Test Requirements
- [ ] `tests/unit/test_job_state_machine.py`: test all valid transitions; test invalid transition (e.g., completed → running) raises error

---

### 3.3 Async Job Endpoints

#### Subtasks
- [ ] 3.3.1 Create `apps/api-server/routers/jobs.py`
- [ ] 3.3.2 `POST /v1/jobs`: validate request (reuse SimulateRequest schema), create `SimulationRun` + `Job` records, enqueue Dramatiq task, return `{job_id, status: "queued", poll_url}`
- [ ] 3.3.3 `GET /v1/jobs/{job_id}`: return job status + metadata; 404 if not found; 403 if wrong org
- [ ] 3.3.4 `GET /v1/jobs/{job_id}/result`: if completed, return full `DecisionEnvelope`; if not completed, return 202 with status; fetch from S3 if result is large blob
- [ ] 3.3.5 `POST /v1/jobs/{job_id}/cancel`: set status to cancelled if still queued/running; 409 if already terminal
- [ ] 3.3.6 Add TTL: jobs expire after 24h (configurable); expired results cleaned up by scheduler task

#### Test Requirements
- [ ] `tests/integration/test_jobs_endpoints.py`: submit job → poll → verify completed; cancel queued job; verify 403 on cross-org job access; verify 404 on non-existent job_id; verify result returns DecisionEnvelope after completion

#### Debug Checkpoints
- [ ] `POST /v1/jobs` returns `job_id` and `status: "queued"` immediately (< 100ms)
- [ ] `GET /v1/jobs/{job_id}` returns `status: "running"` within 1 second of submission
- [ ] `GET /v1/jobs/{job_id}` returns `status: "completed"` within expected execution time
- [ ] Worker logs show job picked up and processed
- [ ] Cancel a queued job → subsequent poll returns `status: "cancelled"`

---

### 3.4 Webhook Delivery Service

#### Subtasks
- [ ] 3.4.1 Create `apps/worker/tasks/webhook_task.py`: `deliver_webhook(job_id, callback_url, payload)` — HTTP POST with timeout, retry logic
- [ ] 3.4.2 Implement exponential backoff retry: 3 attempts with 5s, 30s, 120s delays
- [ ] 3.4.3 Sign webhook payloads: `X-Webhook-Signature: sha256={hmac_hex}` using org-level secret
- [ ] 3.4.4 `POST /v1/webhooks/test`: send test payload to provided URL, return delivery result
- [ ] 3.4.5 Update `Job` record with `callback_status` (pending, delivered, failed) after each attempt
- [ ] 3.4.6 Log all webhook delivery attempts with status code and duration

#### Webhook payload schema
```json
{
  "event": "job.completed",
  "job_id": "job_abc123",
  "run_id": "run_xyz789",
  "org_id": "org_def456",
  "timestamp": "2026-03-20T18:00:00Z",
  "result": { /* DecisionEnvelope */ }
}
```

#### Test Requirements
- [ ] `tests/integration/test_webhook_delivery.py`: use `httpx` mock server to receive webhook; verify payload schema; verify signature header; test retry on 500 response; test delivery status updated in DB after 3 failures

#### Debug Checkpoints
- [ ] Run `POST /v1/webhooks/test` with `https://webhook.site` URL → verify payload received
- [ ] Inspect `X-Webhook-Signature` header — verify HMAC matches
- [ ] Simulate callback_url returning 500 → verify 3 retry attempts in worker logs
- [ ] After 3 failures, `callback_status` in DB = `failed`

---

### 3.5 Large Result Blob Storage

#### Subtasks
- [ ] 3.5.1 Add `boto3` (or `aioboto3`) to requirements
- [ ] 3.5.2 Create `apps/api-server/services/storage_service.py`: `upload_result(run_id, data)`, `download_result(run_id)`
- [ ] 3.5.3 Storage key convention: `orgs/{org_id}/runs/{run_id}/result.json`
- [ ] 3.5.4 Threshold: if result JSON > 512KB, store in S3 and set `output_blob_ref`; else inline in DB (JSONB column on SimulationRun)
- [ ] 3.5.5 `GET /v1/jobs/{job_id}/result`: fetch from S3 if `output_blob_ref` set
- [ ] 3.5.6 MinIO used locally; S3 in production (same boto3 client with endpoint override)

#### Debug Checkpoints
- [ ] Run large simulation (1M runs) → verify `output_blob_ref` populated in DB
- [ ] `GET /v1/jobs/{job_id}/result` returns full result despite blob being in MinIO
- [ ] MinIO console shows result object at correct key path

### Phase 3 — Definition of Done Verification

- [ ] Async job submitted, worker picks it up, result stored, webhook fires
- [ ] All job state transitions tested
- [ ] Cross-org access blocked on job endpoints
- [ ] Webhook signature verification works
- [ ] Large result stored in object store and retrieved correctly
- [ ] All tests pass

---

## Phase 4 — Integrations + SDKs

**Exit criterion:** All 6 integration examples work end-to-end. SDKs published to PyPI and npm. CLI published.

---

### 4.1 Python SDK

#### Subtasks
- [ ] 4.1.1 Create `packages/python-sdk/pyproject.toml`: name `decision-engine-sdk`, version `0.1.0`, requires Python 3.10+
- [ ] 4.1.2 Create `packages/python-sdk/decision_engine/__init__.py`: export `DecisionEngineClient`, `AsyncDecisionEngineClient`
- [ ] 4.1.3 Create `packages/python-sdk/decision_engine/client.py`: sync client wrapping `httpx.Client`
  - `simulate(request: dict | SimulateRequest) -> DecisionEnvelope`
  - `recommend(request: dict) -> RecommendResponse`
  - `score(request: dict) -> ScoreResponse`
  - `batch(items: list) -> BatchResponse`
  - `submit_job(request: dict) -> JobStatus`
  - `poll_job(job_id: str, timeout: int = 300) -> DecisionEnvelope` (polls until complete or timeout)
  - `list_api_keys() -> list[APIKeyInfo]`
  - `create_api_key(label: str) -> APIKeyCreated`
- [ ] 4.1.4 Create `packages/python-sdk/decision_engine/async_client.py`: same methods but async with `httpx.AsyncClient`
- [ ] 4.1.5 Create `packages/python-sdk/decision_engine/models.py`: Pydantic models mirroring API schemas
- [ ] 4.1.6 Create `packages/python-sdk/decision_engine/exceptions.py`: `DecisionEngineError`, `AuthenticationError`, `RateLimitError`, `ValidationError`, `ServerError`
- [ ] 4.1.7 Implement retry logic: 3 retries on 429 and 5xx, exponential backoff
- [ ] 4.1.8 Implement timeout: default 30s connect, 120s read (configurable)
- [ ] 4.1.9 Implement `base_url` config: default to `https://api.decisionengine.io`, overridable for self-hosted
- [ ] 4.1.10 Write SDK README with quickstart examples
- [ ] 4.1.11 Publish to PyPI via `twine` (or GitHub Actions workflow)

#### Test Requirements
- [ ] `tests/unit/sdk/test_python_sdk.py`: mock httpx responses, test all methods, test retry behavior, test timeout raises correct exception, test error response raises typed exception
- [ ] `tests/integration/sdk/test_python_sdk_live.py`: call running local stack, verify real round-trip

#### Debug Checkpoints
- [ ] `pip install decision-engine-sdk` installs without errors (from local wheel first)
- [ ] `from decision_engine import DecisionEngineClient; client = DecisionEngineClient(api_key="..."); result = client.simulate(...)` returns `DecisionEnvelope`
- [ ] Pass an invalid API key → raises `AuthenticationError` (not raw HTTP error)
- [ ] Rate limit exceeded → raises `RateLimitError` with `retry_after` field

---

### 4.2 TypeScript SDK

#### Subtasks
- [ ] 4.2.1 Create `packages/ts-sdk/package.json`: name `decision-engine-sdk`, exports for Node and browser
- [ ] 4.2.2 Create `packages/ts-sdk/src/client.ts`: `DecisionEngineClient` class with all same methods as Python SDK
- [ ] 4.2.3 Create `packages/ts-sdk/src/types.ts`: full TypeScript interfaces for all request/response schemas
- [ ] 4.2.4 Create `packages/ts-sdk/src/errors.ts`: typed error classes
- [ ] 4.2.5 Use native `fetch` (Node 18+) — no Axios dependency
- [ ] 4.2.6 Implement retry and timeout via `AbortController`
- [ ] 4.2.7 Build: `tsc` + generate `index.d.ts` declarations
- [ ] 4.2.8 Publish to npm via `npm publish`

#### Test Requirements
- [ ] `packages/ts-sdk/tests/client.test.ts` (Vitest or Jest): mock fetch, test all methods, typed responses, error handling

#### Debug Checkpoints
- [ ] `npm install decision-engine-sdk` installs (local pack first)
- [ ] `import { DecisionEngineClient } from 'decision-engine-sdk'; const c = new DecisionEngineClient({apiKey: '...'}); const r = await c.simulate({...})` — TypeScript compiles and returns typed result
- [ ] TypeScript strict mode compiles with no errors

---

### 4.3 CLI Tool

#### Subtasks
- [ ] 4.3.1 Create `apps/cli/pyproject.toml`: name `de-cli`, entry point `de`
- [ ] 4.3.2 Add `typer[all]`, `rich` to requirements
- [ ] 4.3.3 Create `apps/cli/main.py`: Typer app with commands:
  - `de simulate <file.json>` — run simulation from JSON file, print result
  - `de recommend <file.json>` — run recommend from JSON file
  - `de job submit <file.json>` — submit async job, print job_id
  - `de job status <job_id>` — poll and print status
  - `de job wait <job_id>` — poll until complete, print result
  - `de keys list` — list API keys
  - `de keys create <label>` — create new key
  - `de keys revoke <id>` — revoke key
  - `de config set-key <api_key>` — store key in `~/.de/config.json`
  - `de config set-url <base_url>` — set base URL for self-hosted
- [ ] 4.3.4 Output formats: `--format json` (raw JSON) and `--format table` (Rich table, default)
- [ ] 4.3.5 Auth: read key from `~/.de/config.json`, then `DE_API_KEY` env var, then `--api-key` flag
- [ ] 4.3.6 Publish to PyPI + write Homebrew formula stub

#### Test Requirements
- [ ] `tests/unit/test_cli.py`: use Typer `CliRunner` to test all commands with mock responses

#### Debug Checkpoints
- [ ] `de config set-key de_live_xxx` writes to `~/.de/config.json`
- [ ] `de simulate examples/sample_request.json` prints formatted table
- [ ] `de simulate examples/sample_request.json --format json` prints raw JSON
- [ ] `de job submit examples/sample_request.json` prints job_id
- [ ] `de job wait <job_id>` blocks until complete and prints result

---

### 4.4 ChatGPT Actions Integration

#### Subtasks
- [ ] 4.4.1 Create `examples/chatgpt-actions/openapi_actions.yaml`: trimmed OpenAPI with only `simulate`, `recommend`, `score` — descriptions ≤ 300 chars each
- [ ] 4.4.2 Ensure `operationId` values are clean identifiers: `runSimulation`, `getRecommendation`, `scoreScenario`
- [ ] 4.4.3 Flatten response schema to max 3 levels deep
- [ ] 4.4.4 Add `apikey` security scheme
- [ ] 4.4.5 Write `examples/chatgpt-actions/README.md`: step-by-step GPT action import guide with screenshots
- [ ] 4.4.6 Write sample GPT system prompt that uses the decision tool

#### Debug Checkpoints
- [ ] Import `openapi_actions.yaml` into a GPT → all 3 endpoints appear, no import errors
- [ ] Ask GPT to "simulate a product launch decision" → GPT calls `runSimulation` and returns formatted result

---

### 4.5 LangGraph Integration

#### Subtasks
- [ ] 4.5.1 Create `examples/langgraph/decision_tool.py`: `@tool` decorated function wrapping Python SDK
- [ ] 4.5.2 Create `examples/langgraph/decision_tool_async.py`: async version for async LangGraph agents
- [ ] 4.5.3 Create `examples/langgraph/example_agent.py`: full working agent that uses the decision tool to evaluate 2 business choices
- [ ] 4.5.4 Create `examples/langgraph/README.md`: setup instructions, how to run, example output

#### Debug Checkpoints
- [ ] `python examples/langgraph/example_agent.py` runs without errors and produces a decision recommendation via the tool

---

### 4.6 n8n Integration

#### Subtasks
- [ ] 4.6.1 Create `examples/n8n/workflow_simulate.json`: importable n8n workflow — HTTP Request node calling `/v1/simulate`, branch on `recommended_action`
- [ ] 4.6.2 Create `examples/n8n/workflow_async_job.json`: submit job → poll → handle completion
- [ ] 4.6.3 Create `examples/n8n/README.md`: import instructions, credential setup, test steps

#### Debug Checkpoints
- [ ] Import workflow into local n8n instance
- [ ] Run workflow → HTTP Request node calls `/v1/simulate` and returns result
- [ ] Branch node correctly routes based on `recommended_action`

---

### 4.7 Power Automate Connector

#### Subtasks
- [ ] 4.7.1 Create `examples/power-automate/connector_definition.json`: custom connector definition with flat schemas
- [ ] 4.7.2 Ensure all schemas are ≤ 3 levels deep (Power Automate limitation)
- [ ] 4.7.3 Configure API key auth header in connector definition
- [ ] 4.7.4 Create `examples/power-automate/README.md`: import guide with screenshots

#### Debug Checkpoints
- [ ] Import connector into Power Automate → all actions visible
- [ ] Create a test flow using the `Simulate` action → runs and returns result

---

### 4.8 Zapier Integration

#### Subtasks
- [ ] 4.8.1 Create `examples/zapier/README.md`: step-by-step Zapier "Webhooks by Zapier" setup to call `/v1/simulate`
- [ ] 4.8.2 Document exact payload format and auth header config
- [ ] 4.8.3 Create sample Zap description: "When a new row is added to Google Sheets → simulate decision → post result to Slack"

---

### 4.9 Make (Integromat) Integration

#### Subtasks
- [ ] 4.9.1 Create `examples/make/README.md`: HTTP module setup to call `/v1/simulate` or `/v1/jobs`
- [ ] 4.9.2 Document webhook response handling for async jobs
- [ ] 4.9.3 Create sample scenario description: "Trigger → call simulate → parse result → route by recommended_action"

---

### 4.10 Contract Tests

#### Subtasks
- [ ] 4.10.1 `tests/contract/test_openapi_validity.py`: validate `openapi.yaml` with `openapi-spec-validator`
- [ ] 4.10.2 `tests/contract/test_sdk_compatibility.py`: verify Python SDK models match OpenAPI schema (use `jsonschema` to validate SDK-generated payloads against spec)
- [ ] 4.10.3 `tests/contract/test_chatgpt_actions_spec.py`: validate `openapi_actions.yaml` with `openapi-spec-validator`; verify operationId uniqueness; verify description lengths ≤ 300 chars

### Phase 4 — Definition of Done Verification

- [ ] Python SDK published to PyPI (or installable from local wheel)
- [ ] TypeScript SDK published to npm (or installable from local pack)
- [ ] CLI installed via `pip install de-cli` and all commands work
- [ ] ChatGPT Actions import works without errors
- [ ] LangGraph example agent runs end-to-end
- [ ] n8n workflow runs end-to-end
- [ ] Power Automate connector imports and runs
- [ ] All contract tests pass

---

## Phase 5A — Minimal Docs Shell + Auth-Gated API Key Page

**Exit criterion:** External developer signs up, gets API key, makes first successful call — in under 2 minutes from the quickstart page.

---

### 5A.1 Docs Site Setup

#### Subtasks
- [ ] 5A.1.1 Choose and initialize docs platform (Mintlify recommended — MDX-based, auto-syncs from OpenAPI)
- [ ] 5A.1.2 Configure `mint.json` / `docusaurus.config.ts` with nav structure matching architecture doc section 7.2
- [ ] 5A.1.3 Deploy docs site to `docs.decisionengine.io` (Vercel or Mintlify hosting)
- [ ] 5A.1.4 Configure CI: auto-deploy docs on merge to `main`

---

### 5A.2 Quickstart Page

#### Subtasks
- [ ] 5A.2.1 Write `docs/quickstart.mdx`: 5-step guide — sign up → get key → install SDK → make call → see result
- [ ] 5A.2.2 Add `curl` example (pre-filled template, user replaces `YOUR_API_KEY`)
- [ ] 5A.2.3 Add Python example (3 lines using SDK)
- [ ] 5A.2.4 Add TypeScript example
- [ ] 5A.2.5 Add real example response JSON (copy from live API)
- [ ] 5A.2.6 Add "Next steps" section linking to API reference and integrations

#### Debug Checkpoints
- [ ] Read quickstart page fresh (no prior knowledge) — complete all steps in under 2 minutes
- [ ] Copy-paste curl command exactly as shown → get 200 response (after replacing API key)
- [ ] Copy-paste Python example → runs without modification (after setting env var)

---

### 5A.3 API Reference Pages

#### Subtasks
- [ ] 5A.3.1 Auto-generate API reference from `openapi.yaml` using Mintlify or Docusaurus OpenAPI plugin
- [ ] 5A.3.2 Verify all endpoints visible with request/response schemas and examples
- [ ] 5A.3.3 Add "Try it" widget (Mintlify built-in or custom iframe)

---

### 5A.4 Minimal Auth Shell (Sign-Up + Key Display)

#### Subtasks
- [ ] 5A.4.1 Create minimal Next.js app (or use separate lightweight HTML page)
- [ ] 5A.4.2 Sign-up page: email + password → POST /auth/signup → show API key immediately with copy button
- [ ] 5A.4.3 API key page: show active keys (prefix only) with revoke button
- [ ] 5A.4.4 Deploy to `app.decisionengine.io`

#### Debug Checkpoints
- [ ] Sign up → immediately see API key on screen with copy button
- [ ] Copy API key → paste into quickstart curl command → get 200 response
- [ ] Total time from landing on docs to first successful API call: ≤ 2 minutes

---

## Phase 5B — Full Developer Portal + Billing

**Exit criterion:** User can sign up, manage keys, see usage, upgrade plan with credit card, use playground.

---

### 5B.1 Next.js Portal (Full)

#### Subtasks
- [ ] 5B.1.1 Full Next.js 14 app with App Router, Tailwind, shadcn/ui
- [ ] 5B.1.2 Dashboard: usage chart (Recharts), recent runs table, plan badge, quick links
- [ ] 5B.1.3 API Keys page: full table, create dialog, revoke with confirm dialog, show prefix and last_used
- [ ] 5B.1.4 Playground: Monaco editor (JSON), endpoint selector, mode selector, example payload dropdown, Run button, response panel, latency badge
- [ ] 5B.1.5 Usage page: simulations by day chart, by endpoint breakdown, avg latency, period selector
- [ ] 5B.1.6 Settings page: org name, billing email, danger zone (delete org)

---

### 5B.2 Stripe Billing Integration

#### Subtasks
- [ ] 5B.2.1 Stripe account setup + API keys in secrets manager
- [ ] 5B.2.2 Create Stripe products: Free, Developer ($29), Pro ($99)
- [ ] 5B.2.3 Create Stripe metered usage price for overage ($0.001 per unit)
- [ ] 5B.2.4 `POST /billing/create-checkout`: create Stripe Checkout session for plan upgrade
- [ ] 5B.2.5 `POST /billing/portal`: create Stripe Customer Portal session (manage plan/payment)
- [ ] 5B.2.6 Stripe webhook handler: `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`
- [ ] 5B.2.7 On `invoice.paid`: reset org's usage counter for new billing period
- [ ] 5B.2.8 Usage metering: after each `SimulationRun`, push metered usage to Stripe async
- [ ] 5B.2.9 Quota enforcement: check Redis counter before each request; return 429 with `upgrade_url` if over limit
- [ ] 5B.2.10 Quota alert emails: send at 80% and 100% of monthly quota

#### Debug Checkpoints
- [ ] Test mode Stripe checkout: enter test card → subscription created in Stripe dashboard
- [ ] Plan updated in DB `subscriptions` table after webhook received
- [ ] After plan upgrade, quota limit reflects new plan immediately
- [ ] Simulate 501 requests on free plan → 501st returns 429 with upgrade URL

---

## Phase 6 — Launch Docs Polish + Public Launch Readiness

### 6.1 Content Completion

#### Subtasks
- [ ] 6.1.1 Write concepts page: Monte Carlo simulation (plain English, no jargon)
- [ ] 6.1.2 Write concepts page: Distribution types (with visual descriptions of each)
- [ ] 6.1.3 Write concepts page: Decision envelopes (what each field means)
- [ ] 6.1.4 Write concepts page: Simple vs Expert mode
- [ ] 6.1.5 Write self-hosting guide (Docker Compose local, cloud deployment options)
- [ ] 6.1.6 Write security model page
- [ ] 6.1.7 Write changelog page with v0.1.0 entry
- [ ] 6.1.8 Write CLI reference page (all commands with flags and examples)
- [ ] 6.1.9 All 6 integration guides linked from docs navbar

### 6.2 Marketing and Launch

#### Subtasks
- [ ] 6.2.1 Public landing page: headline, 3 value props, code example, pricing table, CTA
- [ ] 6.2.2 SEO: `<title>`, Open Graph, `robots.txt`, `sitemap.xml`
- [ ] 6.2.3 Status page: `status.decisionengine.io` (use Upptime or BetterUptime)
- [ ] 6.2.4 Load test: `locust` or `k6` — target 100 req/s on `/v1/simulate`, p95 < 500ms

#### Debug Checkpoints
- [ ] Lighthouse score on landing page ≥ 90 (performance, SEO, accessibility)
- [ ] Load test passes: 100 req/s with p95 < 500ms on warm API
- [ ] Status page shows all services green

---

## Phase 7 — Enterprise Hardening (Private Repo)

### 7.1 SSO / SAML / OIDC

#### Subtasks
- [ ] 7.1.1 Integrate `python-saml` or `authlib` for SAML 2.0 SP
- [ ] 7.1.2 `POST /auth/saml/callback`: handle SAML assertion, create/update user, issue session
- [ ] 7.1.3 OIDC adapter: `POST /auth/oidc/callback`
- [ ] 7.1.4 Org-level SSO config: store IdP metadata per org in DB
- [ ] 7.1.5 Enforce SSO for enterprise orgs (disable password login when SSO configured)

### 7.2 RBAC

#### Subtasks
- [ ] 7.2.1 Define roles: `owner`, `admin`, `member`, `viewer`
- [ ] 7.2.2 Define permissions: `simulate:run`, `jobs:manage`, `keys:manage`, `billing:manage`, `org:manage`
- [ ] 7.2.3 Permission check middleware: `require_permission("simulate:run")` decorator
- [ ] 7.2.4 UI: role assignment on member management page

### 7.3 Audit Logs

#### Subtasks
- [ ] 7.3.1 Write `AuditEvent` record on: login, logout, key create/revoke, simulate, job submit, plan change, member add/remove
- [ ] 7.3.2 `GET /v1/audit-logs`: paginated list, filterable by actor, action, entity, date range
- [ ] 7.3.3 Export: `GET /v1/audit-logs/export?format=csv` and `?format=json`

---

## Phase 8 — Optimized Mojo Runtime (Private Repo)

### 8.1 Vectorized Engine

#### Subtasks
- [ ] 8.1.1 Rewrite Monte Carlo loop with SIMD vectorization in Mojo
- [ ] 8.1.2 Optimize memory layout: struct-of-arrays instead of array-of-structs
- [ ] 8.1.3 Parallelize across CPU cores using Mojo parallelism primitives
- [ ] 8.1.4 Benchmark: compare against public engine — target 10x speedup on 1M runs

### 8.2 Advanced Statistics

#### Subtasks
- [ ] 8.2.1 Implement correlated variable sampling (Cholesky decomposition)
- [ ] 8.2.2 Implement Latin Hypercube Sampling
- [ ] 8.2.3 Implement CVaR (Conditional Value at Risk)
- [ ] 8.2.4 Implement Sobol sensitivity indices

### 8.3 Shared Library Mode (Pattern B)

#### Subtasks
- [ ] 8.3.1 Build Mojo as shared library (`.so` / `.dylib`)
- [ ] 8.3.2 Create Python ctypes or CFFI binding
- [ ] 8.3.3 Benchmark latency improvement vs subprocess mode (target < 10ms overhead)
- [ ] 8.3.4 Feature flag: `MOJO_MODE=subprocess|shared_lib` to switch at runtime

---

## Cross-Cutting Concerns (All Phases)

### Testing Standards

Every PR must:
- [ ] Add unit tests for any new service function
- [ ] Add integration test for any new endpoint
- [ ] Update contract tests if OpenAPI spec changes
- [ ] Pass `make test` with zero failures
- [ ] Pass `make lint` with zero errors

### Error Handling Standards

Every endpoint must:
- [ ] Return errors in the standard error schema (never raw Python tracebacks)
- [ ] Include `request_id` in error response
- [ ] Include `docs_url` pointing to error documentation
- [ ] Log error with structured fields at `error` level

### Security Standards

Every PR must:
- [ ] Never log sensitive data (API keys, passwords, raw payloads)
- [ ] Validate all inputs with Pydantic strict mode
- [ ] Enforce org_id on all data access
- [ ] Run `bandit` security linter as part of `make lint`

### Observability Standards

Every new endpoint must:
- [ ] Emit structured log with all required fields
- [ ] Increment Prometheus counters
- [ ] Include trace span via OpenTelemetry

---

## Running the Full Test Suite

```bash
# Unit tests only
make test-unit

# Integration tests (requires running stack)
make dev && make test-integration

# Contract tests
make test-contract

# All tests
make test

# Load test (Phase 6+)
make load-test
```

---

## Debugging Reference

### Common Issues

| Symptom | Check |
|---|---|
| API returns 500 with no body | Check `docker compose logs api` for Python traceback |
| Worker not picking up jobs | Check `docker compose logs worker` — Redis connection? |
| Mojo binary crashes | Run binary directly with stdin payload; check stderr |
| Auth always 401 | Check Redis — is cache poisoned? Try `redis-cli FLUSHDB` in dev |
| Webhook not firing | Check `callback_status` in `jobs` table; check worker logs |
| Migration fails | Check Alembic version table; run `alembic history` |
| OpenAPI import fails in Power Automate | Schemas nested > 3 levels; flatten them |
| ChatGPT Actions import fails | Check operationId uniqueness; check description length ≤ 300 |

### Useful One-Liners

```bash
# Check all tables
docker exec -it postgres psql -U postgres -d decision_engine -c "\dt"

# Tail API logs
docker compose logs -f api

# Inspect Redis keys
docker exec -it redis redis-cli KEYS "*"

# Run single test
pytest tests/unit/test_auth_service.py -v

# Regenerate OpenAPI spec
make openapi

# Lint only
make lint

# Apply pending migrations
make migrate
```
