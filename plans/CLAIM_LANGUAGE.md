# Codna Decision Engine — Approved Claim Language

> Phase 0 — Claim Hygiene  
> Version: 1.0  
> Last updated: 2026-04-02  
> Owner: Engineering / Product  

This document defines **the only approved language** for describing the Codna
Decision Engine in documentation, marketing copy, SDKs, API references, and sales
materials. No claim stronger than the current claim ladder position may be used
without passing the stated benchmark gate.

---

## Current Approved Position

> **"Codna is a typed, persistent, low-latency decision runtime — Mojo as the
> compute core, Python and Node as orchestration and product surfaces."**

This is the Phase 3 position on the claim ladder. It is accurate, defensible,
and technically verifiable with the current codebase.

---

## Claim Ladder

The claim ladder defines what can be said at each milestone. Use only the
language for the current milestone and below.

### Milestone 0 — Always claimable (no gate required)

These claims are true regardless of runtime mode:

- "Native Mojo execution for Monte Carlo, QMC Sobol, LHS, scenario, sensitivity,
  bootstrap, MCMC, decision tree, time series, compare, and importance sampling"
- "All 11 decision engine types run natively in Mojo"
- "26 probability distributions supported natively"
- "Mojo-native simulation core"
- "Mojo-first decision math engine"
- "Expression language with 50+ functions including financial, statistical,
  and scientific operations"

**Do not say:** "zero Python overhead" or "no Python in the compute path" — the
`json.loads()` boundary in `request_parser.mojo` is intentional and documented.

---

### Milestone 1 — After Phase 1 gate (pool active, MOJO_ALLOW_SUBPROCESS_FALLBACK=false)

Gate: `make bench-gate` passes with pool runtime confirmed (`_proto:1` in all responses).

**Approved:**
- "Persistent Mojo decision runtime"
- "Long-lived Mojo worker pool with sub-millisecond IPC"
- "No subprocess spawn per request — persistent Unix socket workers"
- "Mojo worker pool with automatic health monitoring and restart"

**Do not say:** "no Python bottlenecks" — Python still owns the request boundary
parse and post-compute Vega-Lite spec assembly.

---

### Milestone 2 — After Phase 3 gate (typed SimRequest, single parse boundary)

Gate: No PythonObject in any engine hot loop. Confirmed via code review.

**Approved (in addition to above):**
- "Single Python parse boundary — typed Mojo structs handed directly to engines"
- "Mojo-first decision runtime with Python orchestration"
- "No PythonObject access in any engine computation loop"
- "Typed simulation contract from request to result"

---

### Milestone 3 — After Phase 5+6 gate (typed result envelope, Mojo-precomputed aggregates)

Gate: `_proto:1` in all responses. `histogram_data.source == "mojo_precomputed"` confirmed.

**Approved (in addition to above):**
- "Mojo-computed histogram, CDF, and decision hash — zero Python post-processing"
- "Typed result envelope from compute core to API response"
- "SHA-256 result integrity hash computed in Mojo"

---

### Milestone 4 — After Phase 8 gate (benchmark vs NumPy/SciPy published)

Gate: `make bench-vs-python` shows ≥ 5x speedup over NumPy baseline on Monte Carlo
and LHS. `make bench-concurrency` passes at 100 and 500 concurrent requests.

**Approved (in addition to above):**
- "Full Mojo-first decision runtime without Python compute bottlenecks"
- "Nx faster than NumPy/SciPy for equivalent workloads" (use actual measured N)
- "Verified under 100+ concurrent request load with sub-Xms p95 latency"
  (use actual measured values)
- "Mojo-first performance moat — benchmarked and published"

**Do not say:** "10x faster than Python" or any specific multiplier without the
published `bench_vs_python` results attached to the claim.

---

## What Must NEVER Be Said (regardless of milestone)

| Prohibited Claim | Why |
|-----------------|-----|
| "Zero Python" | Python owns request parse, HTTP, auth, storage, Vega-Lite assembly |
| "100% Mojo compute" | SHA-256 hash uses Python `hashlib`; json.loads() at boundary |
| "Faster than C" | No benchmark supports this |
| "GPU-accelerated" | GPU feasibility study not complete (Phase 8) |
| "Real-time" | Latency targets are sub-50ms p50, not sub-1ms |
| "No overhead" | IPC framing and JSON serialization exist |
| "Infinitely scalable" | Pool size is bounded by MOJO_POOL_SIZE |

---

## Approved Language by Surface

### Product Website / Marketing

**Headline (current):**
> Codna Decision Engine — a typed, persistent decision runtime built on Mojo

**Sub-headline:**
> All 11 decision engine types — Monte Carlo, QMC Sobol, LHS, MCMC, Decision Tree,
> Time Series, Compare, Sensitivity, Bootstrap, Scenario, and Importance Sampling —
> run natively in Mojo with a persistent worker pool and typed compute boundary.

**Feature bullets:**
- "Persistent Mojo worker pool — no subprocess spawn per request"
- "26 probability distributions with native Mojo sampling"
- "Single-boundary request model — typed SimRequest handed directly to engines"
- "Mojo-computed histogram, CDF, and result hash"
- "MOJO_ALLOW_SUBPROCESS_FALLBACK=false enforced in production"

### API Documentation

**Engine description:**
> The simulation engine runs natively in Mojo via a persistent worker pool.
> All 11 engine types are dispatched from a single typed request boundary
> with no Python in the computation hot path.

**Response description:**
> All responses include `_proto: 1` (current JSON framing), Mojo-precomputed
> histogram and CDF data, and a SHA-256 `result_hash` computed in Mojo.

### Python SDK (`packages/python-sdk/`)

**Docstring:**
> Codna Decision Engine Python client. The computation engine runs natively
> in Mojo — this client handles HTTP orchestration only.

**README:**
> The Codna engine uses Mojo as its compute core. All simulation math runs
> in persistent Mojo workers. This SDK is the Python orchestration layer.

### TypeScript SDK (`packages/ts-sdk/`)

**README:**
> Codna Decision Engine TypeScript client for the persistent Mojo runtime.
> All computation is handled by Mojo workers — this SDK provides type-safe
> access to the full 11-engine decision API.

### Sales / Enterprise Copy

**One-liner:**
> "Codna is a typed decision runtime — Mojo compute, Python orchestration,
> Node gateway — covering all decision modalities under one contract."

**Technical differentiator:**
> Unlike Python-first simulation tools, Codna's compute core is implemented
> in Mojo with a persistent worker pool, single typed request boundary, and
> Mojo-native post-compute aggregates. The Python API layer handles auth,
> storage, and HTTP — the simulation math does not.

---

## Claim Review Process

1. Any new claim about performance, architecture, or capabilities must be reviewed
   against this document before publication.
2. Claims citing specific numbers (speedup ratios, latency values) must include
   the benchmark run that produced the number, committed to `tests/benchmark/`.
3. Claims at Milestone 4 require approval from Engineering and the benchmark
   results published in `plans/BENCHMARK_RESULTS.md` (to be created after
   `make bench-vs-python` and `make bench-concurrency` are run in production).

---

## Benchmark Results (to be filled after Phase 8)

Once `make bench-vs-python` and `make bench-concurrency` are run against the
production binary, record the results here to support Milestone 4 claims.

| Engine | Python p50 (ms) | Mojo p50 (ms) | Speedup |
|--------|----------------|--------------|---------|
| monte_carlo | TBD | TBD | TBD |
| lhs | TBD | TBD | TBD |
| bootstrap | TBD | TBD | TBD |

| Concurrency | Mojo p50 (ms) | Mojo p99 (ms) | Errors |
|-------------|--------------|--------------|--------|
| 1 | TBD | TBD | TBD |
| 10 | TBD | TBD | TBD |
| 100 | TBD | TBD | TBD |
| 500 | TBD | TBD | TBD |
