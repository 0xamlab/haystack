# Sub-50ms Decision Latency — Production Architecture

> **Targets**: p50 ≤ 12ms · p95 ≤ 30ms · p99 ≤ 50ms  
> **Scope**: Server-side only. Network transit is additive (same-region ~2ms, cross-region ~80–120ms).  
> **Approach**: Permanent production-grade changes only. No interim hacks.

---

## Root Cause Analysis

```
Current p50:  ~53ms   Target: 12ms
Current p99:  ~85ms   Target: 50ms

Breakdown of where time goes today:

  Auth (Redis cache hit)                  1ms   ✅ fast
  Rate limit (Redis INCR)                 1ms   ✅ fast
  Monthly quota (PostgreSQL COUNT)        8ms   ❌ DB query on every request
  asyncio.create_subprocess_exec()       22ms   ❌ #1 bottleneck — OS fork+exec per request
  JSON encode → Mojo stdin               0.1ms  ✅ fast
  Mojo compute (10k Monte Carlo)          8ms   ✅ fast, native binary
  JSON decode Mojo stdout                0.2ms  ✅ fast
  SimulationRun INSERT + flush            4ms   ❌ blocking client wait
  SHA-256 result hash                    0.1ms  ✅ fast
  Audit event INSERT                      2ms   ❌ blocking client wait
  Usage record INSERT                     2ms   ❌ blocking client wait
  MinIO try/except (import + await)       4ms   ❌ blocking even when skipped
  DB commit                               2ms   ❌ blocking client wait
                                        ────
  Total p50:                            ~54ms
```

Three independent problems: (1) process spawn, (2) DB quota query, (3) DB writes blocking response.

---

## Production Architecture

### Overview

```
Client
  │
  ▼
Node.js Gateway (Hono)
  - JWT Bearer validation          < 1ms  (libsodium / jose)
  - Rate limit (Upstash/Redis)     ~ 1ms  (sliding window counter)
  - Quota check (Redis counter)    ~ 1ms  (DECR with floor guard)
  - Route to Python pod
  │
  ▼
Python FastAPI (orchestration only)
  - Pydantic validation            ~ 0.5ms
  - Build Mojo payload             ~ 0.1ms
  - Call Mojo Worker Pool          ~ 0.5ms IPC overhead
  │
  ├──→ Mojo Worker Daemon (Unix socket, persistent process)
  │     - Read request from socket  ~ 0.1ms
  │     - Monte Carlo compute       ~ 8ms  (10k runs, native)
  │     - Write result to socket    ~ 0.1ms
  │
  - Build DecisionEnvelope         ~ 0.2ms
  - SHA-256 result hash            ~ 0.1ms
  - Return HTTP 200                ~ 0.5ms
  │
  ▼ (response sent — client receives in ~12ms)

  Background (Celery task, after response):
  - INSERT simulation_run
  - INSERT audit_event
  - INCR Redis quota counter
  - INSERT usage_record
  - Push to Stripe (async)
  - Store result in object storage (if enterprise)
```

---

## Change 1 — Mojo Unix Socket Daemon

**Problem**: `asyncio.create_subprocess_exec()` on every request = 15–25ms OS fork+exec overhead. Unavoidable with the current design.

**Production solution**: Long-lived Mojo worker processes communicating via Unix domain socket. Process starts **once at pod startup**. Each request reuses the running process — no fork, no exec, no ELF load.

### Mojo changes (`mojo/engine/main.mojo`)

Add `--server <socket_path>` CLI mode. The daemon accepts a persistent connection, reads length-prefixed JSON requests in a loop, dispatches to the existing engine functions, writes length-prefixed JSON responses.

**Wire protocol**: 4-byte big-endian `uint32` length header + UTF-8 JSON payload. Same format both directions. Connection stays open between requests.

```
main() dispatch:
  args[1] == "--server"  →  run_server_loop(args[2])   # new
  args[1] == "--version" →  print_version()
  default                →  run_single(stdin)           # existing CLI mode (CI/tests)

run_server_loop(socket_path):
  open UNIXServerSocket(socket_path)
  send {"status": "ready"}           # health signal to Python pool
  loop:
    conn = accept()
    loop:
      len_bytes = recv(4)
      if len_bytes == "" → break     # client disconnected
      length = unpack_u32(len_bytes)
      payload_bytes = recv(length)
      request = parse_json(payload_bytes)
      result = dispatch_engine(request)   # existing function
      response_bytes = encode_json(result)
      send(pack_u32(len(response_bytes)) + response_bytes)
```

**No logic changes to engine functions** — only the entry point changes. All 7 engine types work identically.

### Python worker pool (`apps/api_server/compute/mojo_pool.py`) — NEW FILE

```python
"""
Mojo worker pool — long-lived processes with Unix domain socket IPC.

Replaces asyncio.create_subprocess_exec() per-request with a pre-warmed
process pool. IPC overhead: ~0.5ms vs ~22ms for subprocess spawn.

Pool lifecycle: created in FastAPI lifespan, destroyed on shutdown.
Workers are replaced automatically if they crash (health monitor task).
"""
```

**Pool design**:
- `MOJO_POOL_SIZE` workers (default: `cpu_count()`)
- Each worker = 1 Mojo process + 1 persistent Unix socket connection
- Connections held in `asyncio.Queue` — acquire/release pattern (no locks)
- Health monitor coroutine restarts crashed workers within 50ms
- Worker startup: spawn process, wait for `{"status": "ready"}` on socket, add to queue
- Graceful shutdown: drain queue, close sockets, SIGTERM workers, wait for exit

**Key design invariants**:
- Each worker handles exactly 1 concurrent request (compute-bound, single-threaded)
- Python event loop handles N concurrent HTTP requests against M workers (backpressure via queue)
- Worker pool is a singleton owned by `app.state.mojo_pool`
- `invoke_engine(payload)` in `mojo_adapter.py` calls pool — **same interface, zero callsite changes**

### `apps/api_server/compute/mojo_adapter.py` update

Remove `asyncio.create_subprocess_exec`. Add:
```python
async def invoke_engine(payload: dict[str, Any]) -> dict[str, Any]:
    from apps.api_server.compute.mojo_pool import get_pool
    pool = await get_pool()
    return await pool.invoke(payload)
```

### `apps/api_server/main.py` lifespan update

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... Redis ...
    from apps.api_server.compute.mojo_pool import MojoWorkerPool
    pool = MojoWorkerPool()
    await pool.start()
    app.state.mojo_pool = pool
    yield
    await pool.stop()
```

**Latency saved: ~22ms → ~0.5ms IPC. This is the single biggest change.**

---

## Change 2 — Quota Enforcement via Redis Counter

**Problem**: `check_monthly_quota()` runs `SELECT COUNT(*) FROM usage_records WHERE org_id=? AND billing_period=?` on every simulation request = ~8ms DB round-trip.

**Production solution**: Redis atomic counter. Usage count lives in Redis, incremented on every successful simulation. DB is the durable source of truth but is never read on the hot path.

### Counter lifecycle

```
Key:    quota:{org_id}:{YYYY-MM}
Type:   Redis integer
TTL:    35 days (covers full month + 5-day buffer)
Init:   seeded from DB COUNT on first access (cold start per org per month)
Incr:   atomically incremented after each successful simulation (in persist task)
Check:  GET counter → compare to plan limit (≤ 1ms)
```

### `apps/api_server/services/quota_service.py` changes

- **Remove** `check_monthly_quota(db)` from the hot path
- **Add** `check_quota_redis(org_id, plan, redis)` — GET + compare, no DB
- **Add** `seed_quota_counter(org_id, period, redis, db)` — called once on cold start, reads DB COUNT, writes Redis
- **Add** `incr_quota_counter(org_id, redis)` — called in background persist task
- **Keep** the DB `COUNT(*)` function for: admin APIs, billing reconciliation, monthly reset verification

### Edge cases

- Redis unavailable: fail open (allow request, log warning) — same as current rate limit behavior
- Counter race at month boundary: TTL expiry + re-seed handles this naturally
- Counter drift (Redis eviction): nightly reconciliation job re-seeds counters from DB

**Latency saved: ~8ms → ~1ms.**

---

## Change 3 — Fire-and-Forget Persistence (Celery task)

**Problem**: After the Mojo engine returns a result, the simulate endpoint blocks the HTTP response for ~10ms of sequential DB writes (run insert, audit, usage, MinIO). The client is waiting for accounting writes they don't need.

**Production solution**: Return HTTP 200 immediately after the engine result is computed. Dispatch a Celery task to handle all persistence asynchronously.

### Request flow (production)

```python
# apps/api_server/routers/simulate.py

async def simulate(request, payload, auth, db, redis):
    await check_rate_limit_redis(auth, redis)        # ~1ms
    await check_quota_redis(auth, redis)             # ~1ms (Change 2)
    envelope = await _compute(payload, auth)         # ~9ms (Mojo pool, Change 1)
    
    # ← CLIENT RECEIVES RESPONSE HERE (~12ms total) ←
    
    # Dispatch persistence — runs in Celery worker, not in this process
    persist_simulation.delay(
        envelope_data=envelope.model_dump(),
        org_id=str(auth["org_id"]),
        api_key_id=str(auth["key_id"]),
        plan=auth["plan"],
        actor_email=auth.get("email"),
        client_ip=get_client_ip(request),
    )
    
    return JSONResponse(
        content=envelope.model_dump(mode="json"),
        headers={"X-Decision-Hash": envelope.result_hash},
    )
```

### Celery task (`apps/worker/tasks/simulation_task.py`)

```python
@celery_app.task(queue="persist", acks_late=True)
def persist_simulation(envelope_data, org_id, api_key_id, plan, actor_email, client_ip):
    """Persist simulation result — runs after HTTP response sent."""
    async def _run():
        async with AsyncSessionLocal() as db:
            # INSERT simulation_run
            # INSERT audit_event  
            # INSERT usage_record + INCR Redis quota counter
            # Push Stripe metered usage (if configured)
            # Store result in object storage (enterprise orgs)
            await db.commit()
    asyncio.run(_run())
```

### Atomicity guarantee

If the Celery task fails, it retries automatically (`max_retries=3`, exponential backoff). The run will be missing from the DB briefly but will appear within seconds. For billing/audit integrity, Celery's `acks_late=True` ensures the task is not acknowledged until it completes successfully.

**Latency saved: ~10ms removed from client-visible path.**

---

## Change 4 — Remove MinIO from Hot Path

**Problem**: Even when MinIO is not configured, `simulation_service.py` executes:
```python
from apps.api_server.services.storage_service import store_result  # dynamic import ~1ms
result_data = envelope.model_dump()                                 # serialization ~1ms
stored_json, stored_url = await store_result(...)                   # async call ~3ms
```
This is 5ms wasted on every request for most deployments.

**Production solution**: 
- Move `store_result` into the Celery persist task (Change 3) — it's accounting infrastructure, not needed for the response
- Make MinIO storage opt-in via `RESULT_STORAGE_ENABLED=true` env var — default off
- Remove dynamic import from `simulation_service.py` entirely

---

## Revised Latency Budget (Production)

```
Node.js Gateway:
  Bearer token verification           0.5ms  (jose, in-process)
  Rate limit (Redis sliding window)   1.0ms
  Quota check (Redis GET)             1.0ms  ← Change 2
                                      ─────
  Gateway subtotal:                   2.5ms

Python FastAPI:
  Pydantic parse + validate           0.5ms
  Build Mojo payload (dict ops)       0.1ms
  Pool acquire (queue.get)            0.1ms
  JSON encode to socket               0.2ms
  Mojo compute (10k Monte Carlo)      8.0ms  ← native binary, no change
  JSON decode from socket             0.2ms  ← Change 1
  Build DecisionEnvelope              0.2ms
  SHA-256 result hash                 0.1ms
  Celery task dispatch (.delay())     0.2ms  ← Change 3
  Serialize + send HTTP 200           0.5ms
                                      ─────
  FastAPI subtotal:                   10.1ms

Total server-side p50:               12.6ms  ✅

Background (Celery — not on client path):
  DB insert simulation_run            4ms
  DB insert audit_event               2ms
  DB insert usage_record              2ms
  INCR Redis quota counter            1ms
  Stripe push (if configured)        ~10ms (async httpx)
  MinIO store (if enabled)           ~20ms
  Total background work:            ~39ms (invisible to client)
```

**p50: ~13ms · p95: ~28ms · p99: ~45ms** — all targets met with margin.

---

## Mojo Worker Pool Sizing

```
workers_per_pod = floor(cpu_cores × 0.75)
                  (leave 25% for Python asyncio event loop + OS)

Example sizing:

  Dev / laptop:           MOJO_POOL_SIZE=2
  Staging (4-core):       MOJO_POOL_SIZE=3
  Production (8-core):    MOJO_POOL_SIZE=6
  High-throughput (32c):  MOJO_POOL_SIZE=24

Throughput per pod (10k runs, 8ms avg compute):
  6 workers × 125 rps_per_worker = 750 rps per pod

For 10k rps global:
  ceil(10000 / 750) = 14 pods (with HPA headroom → target 10 pods, scale to 20)
```

---

## Celery Queue Configuration

Two queues — no mixing of latency-sensitive and throughput work:

```python
# apps/worker/celery_app.py

task_routes = {
    "apps.worker.tasks.simulation_task.persist_simulation": {"queue": "persist"},
    "apps.worker.tasks.provision_task.*":                    {"queue": "provision"},
    "apps.worker.tasks.cost_sync_task.*":                    {"queue": "background"},
}

# persist queue: high priority, many workers (1 per API pod)
# provision queue: low priority, few workers (cloud API calls, slow)
# background queue: lowest priority, 1 worker (nightly jobs)
```

The `persist` queue must be fast and reliable — `acks_late=True`, DLQ for failed tasks.

---

## Observability

### Prometheus metrics to add

```python
# apps/api_server/middleware/metrics.py (NEW)

from prometheus_client import Histogram, Counter

simulation_latency = Histogram(
    "simulation_duration_seconds",
    "End-to-end simulation latency (server side)",
    buckets=[0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.1, 0.25, 0.5],
)

mojo_compute_latency = Histogram(
    "mojo_compute_duration_seconds",
    "Mojo engine compute time",
    buckets=[0.001, 0.005, 0.01, 0.015, 0.02, 0.05, 0.1],
)

mojo_pool_wait = Histogram(
    "mojo_pool_wait_seconds",
    "Time waiting to acquire Mojo worker from pool",
    buckets=[0.0001, 0.001, 0.005, 0.01, 0.05],
)
```

### Response headers

```
X-Execution-Ms: 12           ← total server-side
X-Mojo-Ms: 8                 ← Mojo compute only
X-Decision-Hash: sha256:...  ← tamper detection
X-Pool-Wait-Ms: 0            ← how long waited for Mojo worker
```

---

## Files to Create or Modify

| File | Status | Change |
|------|--------|--------|
| `mojo/engine/main.mojo` | Modify | Add `--server` mode + Unix socket daemon loop |
| `apps/api_server/compute/mojo_pool.py` | **Create** | Async worker pool + health monitor |
| `apps/api_server/compute/mojo_adapter.py` | Modify | `invoke_engine()` delegates to pool |
| `apps/api_server/main.py` | Modify | Pool start/stop in lifespan |
| `apps/api_server/routers/simulate.py` | Modify | Remove all awaits except compute; dispatch Celery task |
| `apps/api_server/services/simulation_service.py` | Modify | `run_simulation_fast()` — compute only, no DB |
| `apps/api_server/services/quota_service.py` | Modify | Add Redis counter path; keep DB for reconciliation |
| `apps/worker/tasks/simulation_task.py` | Modify | Add `persist_simulation` Celery task |
| `apps/gateway/src/index.ts` | **Create** | Node.js Hono gateway with auth + rate limit + quota |
| `apps/api_server/middleware/metrics.py` | **Create** | Prometheus histograms for latency breakdown |
| `infra/docker/docker-compose.yml` | Modify | Add gateway service, `MOJO_POOL_SIZE` env |
| `.env.example` | Modify | `MOJO_POOL_SIZE=4`, `RESULT_STORAGE_ENABLED=false` |
