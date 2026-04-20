# Remaining Tasks — Complete Mojo-First Decision Engine

> **Generated:** 2026-04-06  
> **Source:** Cross-referenced from all 10 plan documents in `/plans/`  
> **Binary Version:** 0.7.0-mojo-universal  
> **Test Status:** SHA-256 8/8 ✅ · conv 51/51 ✅ · Binary runs ✅ (all-zero output — see Category 2)

---

## Status: What's Done Today

### Mojo Engine Libraries (6 custom libraries created this session)
| Library | File | Tests | Status |
|---------|------|-------|--------|
| SHA-256 (FIPS 180-4) | [`mojo/engine/sha256.mojo`](../mojo/engine/sha256.mojo) | 8/8 ✅ | Replaces Python `hashlib` |
| Number Conversion | [`mojo/engine/conv.mojo`](../mojo/engine/conv.mojo) | 51/51 ✅ | `parse_float64`, `parse_int`, `int_to_hex` |
| JSON Parser | [`mojo/engine/json/parser.mojo`](../mojo/engine/json/parser.mojo) | test_json_parser.mojo | Schema-specific tokenizer |
| Unix Socket | [`mojo/engine/net/unix_socket.mojo`](../mojo/engine/net/unix_socket.mojo) | test_unix_socket.mojo | libc-based IPC |
| Decision Tree Parser | [`mojo/engine/decision_tree_parser.mojo`](../mojo/engine/decision_tree_parser.mojo) | test_decision_tree_parser.mojo | TreeNode + enumerate_paths |
| Field Mapper | [`mojo/engine/field_mapper.mojo`](../mojo/engine/field_mapper.mojo) | test_field_mapper.mojo | Auto field mapping |

### Engine Modularization (Phase 7 / Phase A complete)
- 11 engine types in [`mojo/engine/engines/`](../mojo/engine/engines/): monte_carlo, qmc_sobol, lhs, bootstrap, scenario, sensitivity, mcmc
- Plus: compare, decision_tree, time_series, importance_sampling as top-level modules
- [`main.mojo`](../mojo/engine/main.mojo) reduced to dispatch-only entry point
- [`distributions.mojo`](../mojo/engine/distributions.mojo) — 27 distributions
- [`expr.mojo`](../mojo/engine/expr.mojo) — 40+ function expression evaluator
- [`types.mojo`](../mojo/engine/types.mojo) — typed SimRequest structs
- [`output.mojo`](../mojo/engine/output.mojo) — typed DecisionEnvelopeMojo with histogram/CDF
- [`stats.mojo`](../mojo/engine/stats.mojo) — introsort + stats
- [`correlation.mojo`](../mojo/engine/correlation.mojo) — Cholesky decomposition
- [`sobol.mojo`](../mojo/engine/sobol.mojo) — Joe-Kuo Sobol sequences

### Infrastructure Already Built
- Binary compiles: [`mojo_build/simulate`](../mojo_build/simulate) (v0.7.0-mojo-universal)
- Python worker pool: [`mojo_pool.py`](../apps/api_server/compute/mojo_pool.py) (419 lines, persistent Unix socket)
- Node.js gateway: [`apps/gateway/`](../apps/gateway/) with JWT, rate limiting, WebSocket
- Portal: Next.js with playground, dashboard, compare, billing pages
- MCP server: modular tools in [`apps/mcp_server/`](../apps/mcp_server/)
- Benchmark suite: 5 benchmark scripts in [`tests/benchmark/`](../tests/benchmark/)
- Mojo test suite: 10 test files in [`tests/mojo/`](../tests/mojo/)
- Integration examples: LangGraph, ChatGPT Actions, n8n, Power Automate
- Claim language: [`plans/CLAIM_LANGUAGE.md`](CLAIM_LANGUAGE.md) — approved claim ladder

---

## Category 1: Critical Bugs — Binary Output All Zeros 🔴

The binary runs and returns valid JSON structure, but all computed values are 0.0.
This means the native JSON parser → distribution sampling → engine pipeline has a
data flow break somewhere.

- [ ] **Debug binary all-zero output**: `echo '{"runs":500,"variables":[{"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}}],"objective_function":"rev"}' | ./mojo_build/simulate` returns `mean:0.0, std:0.0` — all values zero
- [ ] Trace data flow: `request_parser.mojo` → JSON parser → `VarSpec` population → `distributions.mojo` → `monte_carlo.mojo` sampling loop
- [ ] Verify `parse_variables_array()` in [`json/parser.mojo`](../mojo/engine/json/parser.mojo) correctly extracts `params.mean` and `params.std`
- [ ] Verify `sample_distribution()` in [`distributions.mojo`](../mojo/engine/distributions.mojo) receives non-zero params from parsed VarSpec
- [ ] Verify `eval_expr()` in [`expr.mojo`](../mojo/engine/expr.mojo) resolves variable references correctly against sampled values
- [ ] Add debug logging to the native JSON parser path to trace parsed values
- [ ] Rebuild binary after fix: `cd mojo_env && pixi run mojo build -I ../mojo/engine ../mojo/engine/main.mojo -o ../mojo_build/simulate`
- [ ] Re-run smoke test and verify non-zero mean/percentiles

---

## Category 2: Integration Testing & Benchmarks

### Benchmark Gates (from MOJO_FIRST_FULL_GAP_ANALYSIS §10)
- [ ] Run `make bench-gate` with new binary — all 11 engines within latency thresholds
- [ ] Run `make bench-concurrency` — 500 parallel requests, no degradation
- [ ] Run `make bench-vs-python` — speedup ratios (target: >5x MC, >5x LHS)
- [ ] Run `make bench-boundary` — parse overhead <1% of compute
- [ ] Create `make bench-memory` — memory under load <100MB per worker
- [ ] Create `make bench-ipc` — socket IPC overhead <0.5ms per frame
- [ ] Create `make bench-json-native` — JSON parse <0.05ms for 10 variables

### Mojo Test Coverage Expansion (from GAP_ANALYSIS §8.2)
- [ ] `tests/mojo/test_distributions.mojo` — Kolmogorov-Smirnov test per distribution, chi-squared goodness of fit, mean/variance convergence at N=100k
- [ ] `tests/mojo/test_simd_sampling.mojo` — SIMD vs scalar equivalence for all distributions
- [ ] `tests/mojo/test_parallel_determinism.mojo` — seeded parallel runs are reproducible
- [ ] `tests/mojo/test_memory_safety.mojo` — no leaks under repeated allocation
- [ ] `tests/mojo/test_correlation_matrix.mojo` — Cholesky decomposition edge cases (singular, near-singular)

### Compiler Warnings (from build output)
- [ ] Fix `math` → `std.math` deprecation warnings in Mojo source
- [ ] Fix unused variable warnings
- [ ] Fix any remaining Python interop warnings
- [ ] Achieve zero-warning build

---

## Category 3: Mojo Engine Performance (Phase M5 / Phase 8)

### SIMD Vectorization (from GAP_ANALYSIS §9 Phase M5 + SIMULATION_ENGINE §A2)
- [ ] SIMD sampling for triangular distribution
- [ ] SIMD sampling for lognormal distribution
- [ ] SIMD sampling for beta distribution
- [ ] SIMD sampling for gamma distribution
- [ ] SIMD sampling for exponential distribution
- [ ] SIMD sampling for weibull distribution
- [ ] SIMD sampling for pert distribution
- [ ] SIMD sampling for poisson distribution
- [ ] Benchmark: SIMD vs scalar for all 10 priority distributions

### Parallelism & Memory (from PHASED_PLAN Phase 8 + GAP_ANALYSIS §9 Phase M5)
- [ ] Cross-core partitioning as default for >10k runs (`parallelize()` in MC loop)
- [ ] Shared-memory worker strategy evaluation (if stable in current Mojo release)
- [ ] Arena/pool allocator for zero-allocation hot loops ([`mojo/engine/memory/pool_allocator.mojo`](../mojo/engine/memory/))
- [ ] Struct-of-arrays memory layout in hot paths (from PHASED_PLAN Phase 7)

### GPU (from GAP_ANALYSIS §9 Phase M5)
- [ ] GPU kernel proof-of-concept for normal distribution Monte Carlo ([`mojo/engine/engines/gpu_monte_carlo.mojo`](../mojo/engine/engines/))
- [ ] GPU feasibility report with measured throughput vs CPU

### Performance Publication (from PHASED_PLAN Phase 8)
- [ ] Published p50/p95/p99 benchmark matrix by workload class
- [ ] Fill in benchmark results table in [`CLAIM_LANGUAGE.md`](CLAIM_LANGUAGE.md)

---

## Category 4: Remaining Python Contamination Removal (Phase M1–M3)

### Already Done ✅
- [x] Mojo-native SHA-256 ([`sha256.mojo`](../mojo/engine/sha256.mojo)) — replaces Python `hashlib`
- [x] Mojo-native Unix socket ([`net/unix_socket.mojo`](../mojo/engine/net/unix_socket.mojo)) — replaces Python `socket`
- [x] Mojo-native JSON parser ([`json/parser.mojo`](../mojo/engine/json/parser.mojo)) — replaces Python `json.loads()`
- [x] Mojo-native number conversion ([`conv.mojo`](../mojo/engine/conv.mojo)) — replaces `python_bridge.mojo` helpers
- [x] Decision tree flattening in Mojo ([`decision_tree_parser.mojo`](../mojo/engine/decision_tree_parser.mojo))
- [x] Field mapper in Mojo ([`field_mapper.mojo`](../mojo/engine/field_mapper.mojo))

### Remaining Wiring (from GAP_ANALYSIS §3, §4)
- [ ] Wire [`sha256.mojo`](../mojo/engine/sha256.mojo) into [`output.mojo`](../mojo/engine/output.mojo) `compute_result_hash()` — remove `Python.import_module("hashlib")`
- [ ] Wire [`net/unix_socket.mojo`](../mojo/engine/net/unix_socket.mojo) into [`main.mojo`](../mojo/engine/main.mojo) `run_server_loop()` — remove `Python.import_module("socket")`, `Python.import_module("struct")`, `Python.import_module("os")`
- [ ] Wire [`json/parser.mojo`](../mojo/engine/json/parser.mojo) into [`request_parser.mojo`](../mojo/engine/request_parser.mojo) — remove `Python.import_module("json")`
- [ ] Wire [`conv.mojo`](../mojo/engine/conv.mojo) into request parser — remove `fast_f64()`, `fast_int()`, `py_str()` from [`python_bridge.mojo`](../mojo/engine/python_bridge.mojo)
- [ ] Wire [`decision_tree_parser.mojo`](../mojo/engine/decision_tree_parser.mojo) into [`decision_tree.mojo`](../mojo/engine/decision_tree.mojo) — remove JSON re-parse
- [ ] Remove `python_engine` imports from [`simulation_service.py`](../apps/api_server/services/simulation_service.py) (lines 146, 179)
- [ ] Add `granularity_to_dt()` to [`time_series.mojo`](../mojo/engine/time_series.mojo) — replace Python `GRANULARITY_TO_YEARS`
- [ ] Deprecate [`python_bridge.mojo`](../mojo/engine/python_bridge.mojo) — keep only for backward compat
- [ ] Verify zero `Python.import_module()` calls in compute path (static analysis)

---

## Category 5: Universal Connector System (Phase M6 / from GAP_ANALYSIS §7)

### Connector Plugin Architecture
- [ ] Create `apps/api_server/connectors/` directory with plugin system
- [ ] `base.py` — `BaseConnector` ABC with `fetch_data()`, `map_fields()`, `validate_connection()`
- [ ] REST connector plugin (`rest_connector.py`)
- [ ] SQL connector plugin — PostgreSQL (`sql_connector.py`)
- [ ] SQL connector plugin — Snowflake
- [ ] File connector — CSV upload
- [ ] File connector — Excel upload
- [ ] File connector — Parquet upload
- [ ] Stream connector — Kafka
- [ ] Stream connector — Redis Streams
- [ ] Cloud connector — S3
- [ ] Cloud connector — GCS
- [ ] Cloud connector — Azure Blob
- [ ] Real-time data feed integration (`POST /v1/simulate/stream`)

### Field Mapper Integration
- [ ] Auto distribution fitting from raw data ([`distribution_fit.mojo`](../mojo/engine/))
- [ ] Industry vocabulary tables ([`industry_vocab.mojo`](../mojo/engine/)) — finance, health, retail, energy, manufacturing, insurance
- [ ] Enhanced auto mode in [`simulation_service.py`](../apps/api_server/services/simulation_service.py) — raw data arrays → auto-fit distributions
- [ ] New `mode: "adaptive"` in [`schemas/simulate.py`](../apps/api_server/schemas/simulate.py)

---

## Category 6: Portal & Interface Design (Phase 7 Enterprise Portal)

### From [`PHASE_7_ENTERPRISE_PORTAL.md`](PHASE_7_ENTERPRISE_PORTAL.md)
- [ ] 7-H: Navigation restructure — grouped sections in sidebar
- [ ] 7-A: Dashboard upgrade — Plotly charts (volume, outcome distribution, EV histogram, latency trend, confidence trend)
- [ ] 7-B: Simulations/Runs page — run browser with drill-down, filters, export CSV
- [ ] 7-C: Data connectors page — connector type cards, active connections list, add connector dialog
- [ ] 7-D: Infrastructure page — deployment mode selector (cloud/self-hosted/hybrid), compute nodes panel, engine health
- [ ] 7-E: Jobs/Async queue page — status tabs, job detail panel with webhook delivery log
- [ ] 7-F: Team page — members table, RBAC, SSO section, audit log
- [ ] 7-G: Public landing page — hero, how it works, integrations, live demo, pricing table

### From [`GO_LIVE_PLAN.md`](GO_LIVE_PLAN.md) — Fix What's Broken
- [ ] Fix sidebar layout CSS regression
- [ ] Overview: show empty state when no data (not fake chart)
- [ ] Playground: sync variable sliders ↔ JSON editor bidirectionally
- [ ] Infrastructure: remove fake elements (logs, restart buttons), show real data only
- [ ] Settings: gray out email field, remove fake 2FA/delete buttons
- [ ] Data connectors: add real credential forms per connector type

---

## Category 7: Production Hardening (Phase M7 / Phase 6–7)

### Load Testing (from GAP_ANALYSIS §9 Phase M7 + BACKEND_GAP §11)
- [ ] Load test at 500k simulated users/day (k6 + distributed)
- [ ] 24h sustained memory test — no memory growth beyond baseline
- [ ] Worker crash recovery verified < 50ms replacement
- [ ] Create `tests/load/locustfile.py` — 100 req/s target on `/v1/simulate`, p95 < 500ms

### Chaos Engineering (from GAP_ANALYSIS §9 Phase M7)
- [ ] Kill workers during load — verify auto-restart
- [ ] Network partition test
- [ ] OOM scenario handling

### Security (from GAP_ANALYSIS §9 Phase M7 + BACKEND_GAP §10)
- [ ] Security audit of native Mojo code (buffer overflow checks)
- [ ] Deterministic seeding verification for audit trail
- [ ] Production Docker hardening — multi-stage build, non-root user, `HEALTHCHECK`

### CI/CD (from BACKEND_GAP §9)
- [ ] Create `.github/workflows/ci.yml` — tests on every PR
- [ ] Auto-deploy on merge to main
- [ ] Mojo binary build step in CI

---

## Category 8: Backend Gaps (from [`BACKEND_GAP_ANALYSIS.md`](BACKEND_GAP_ANALYSIS.md))

### Must-Have Before First Paying Customer
- [ ] GAP 1: Stripe usage metering — push `stripe.UsageRecord.create()` after each simulation
- [ ] GAP 1: Stripe webhook `invoice.paid` → reset monthly usage counter
- [ ] GAP 2: Redis API key caching — cache `hash → {org_id, key_id, plan}` for 5min TTL
- [ ] GAP 3: Email verification — `POST /auth/signup` → send verification email → `GET /auth/verify?token=X`
- [ ] GAP 4: Password reset — `POST /auth/forgot-password` → email link → `POST /auth/reset-password`
- [ ] GAP 5: Quota alert emails at 80% and 100% usage
- [ ] GAP 6: Result object storage — MinIO/S3 for results >100KB
- [ ] GAP 7: Analytics endpoint real SQL aggregation (replace Python in-memory loop)
- [ ] GAP 8: Per-minute rate limiting middleware (`middleware/rate_limit.py`)
- [ ] GAP 14: Subscriptions table in DB + Stripe webhook for `customer.subscription.updated`

### Enterprise Features
- [ ] GAP 12: SSO / SAML 2.0 SP adapter
- [ ] GAP 12: OIDC adapter
- [ ] GAP 12: Per-org IdP config table
- [ ] GAP 13: Auto-generated API docs from OpenAPI spec (Docusaurus OpenAPI plugin)

---

## Category 9: Documentation & SDK Updates

### Claim Language (from [`CLAIM_LANGUAGE.md`](CLAIM_LANGUAGE.md))
- [ ] Update all marketing copy to match current approved claim position
- [ ] Update Python SDK docstrings to match approved language
- [ ] Update TypeScript SDK README to match approved language
- [ ] Update API docs description to match approved language

### Documentation Content (from UNIVERSAL_ARCHITECTURE §7 + TASK_BREAKDOWN Phase 6)
- [ ] Quickstart page refined to under 2 minute target (tested with real users)
- [ ] All concept pages: Monte Carlo, distributions, decision envelopes, simple vs expert mode
- [ ] Self-hosting guide (Docker Compose + cloud deployment)
- [ ] Security model page
- [ ] CLI reference page
- [ ] Changelog page with version history

### SDK Updates (from PHASED_PLAN Phase 9)
- [ ] Python SDK: add adaptive mode support
- [ ] TypeScript SDK: add adaptive mode support
- [ ] Both SDKs: add all 11 engine types in type definitions
- [ ] Both SDKs: ensure types match current response schema (v0.7.0)
- [ ] Align SDK types with engine-specific fields
- [ ] Add runtime capability matrix to docs

### Portal Alignment (from PHASED_PLAN Phase 9)
- [ ] Remove Monte Carlo-first assumptions from portal copy
- [ ] Expose all 11 engine types consistently in portal UI
- [ ] Align docs claim language with current runtime reality

---

## Category 10: Technical Debt

### Files to Delete
- [ ] Delete `apps/api_server/compute/python_engine/` directory (after Mojo parity verified for decision_tree + time_series)
- [ ] Remove deprecated `python_bridge.mojo` (after all callsites migrated to `conv.mojo` + native JSON parser)

### Files to Fix
- [ ] Fix all compiler warnings in Mojo build (math → std.math, unused vars)
- [ ] Remove fake/degraded fallback code paths from production mode (from PHASED_PLAN)
- [ ] Remove request/response field assumptions hardcoded around Monte Carlo (from PHASED_PLAN)

### Integration Example Updates
- [ ] [`examples/power-automate/connector_definition.json`](../examples/power-automate/connector_definition.json) — update hostname from `api.decisionengine.io` to `api.algenta.ai`
- [ ] Verify all integration examples use current API schema (v0.7.0 response fields)
- [ ] Add Zapier example (`examples/zapier/README.md`) — currently missing
- [ ] Add Make (Integromat) example (`examples/make/README.md`) — currently missing

### Binary Protocol v2 (from GAP_ANALYSIS §5.3 — deferred)
- [ ] Evaluate msgpack/flatbuf binary framing between FastAPI and Mojo (replace JSON IPC)
- [ ] Protocol versioning and compatibility checks

---

## Category 11: Surface Alignment & Launch Readiness (Phase 6)

### Marketing & SEO (from TASK_BREAKDOWN §6.2)
- [ ] Public landing page: headline, 3 value props, code example, pricing table, CTA
- [ ] SEO: `<title>`, Open Graph, `robots.txt`, `sitemap.xml`
- [ ] Status page: `status.decisionengine.io` (Upptime or BetterUptime)
- [ ] Lighthouse score ≥ 90 on landing page

### Launch Verification
- [ ] External developer test: lands on docs → signs up → first API call in under 2 minutes
- [ ] All 6 integration platforms have working end-to-end examples
- [ ] Python SDK published to PyPI
- [ ] TypeScript SDK published to npm
- [ ] CLI published (PyPI + Homebrew formula)

---

## Priority Execution Order

### Week 1 — Fix critical binary bug + wire libraries
1. Debug and fix binary all-zero output (Category 1)
2. Wire sha256.mojo into output.mojo (Category 4)
3. Wire unix_socket.mojo into main.mojo server loop (Category 4)
4. Wire json/parser.mojo into request_parser.mojo (Category 4)
5. Rebuild binary and verify smoke test

### Week 2 — Benchmarks + Python contamination removal
6. Run all benchmark gates (Category 2)
7. Remove python_engine imports from simulation_service.py (Category 4)
8. Fix compiler warnings (Category 10)
9. Run expanded Mojo test suite (Category 2)

### Week 3 — Backend gaps for paying customers
10. Redis API key caching (Category 8, GAP 2)
11. Email verification flow (Category 8, GAP 3)
12. Password reset flow (Category 8, GAP 4)
13. Stripe usage metering (Category 8, GAP 1)
14. Per-minute rate limiting (Category 8, GAP 8)

### Week 4+ — Performance, connectors, portal, launch
15. SIMD sampling for top distributions (Category 3)
16. Cross-core partitioning (Category 3)
17. Connector plugin system (Category 5)
18. Portal enterprise upgrade (Category 6)
19. Production hardening (Category 7)
20. Launch readiness (Category 11)

---

## Test Results Summary (2026-04-06)

| Test | Result | Notes |
|------|--------|-------|
| `test_sha256.mojo` | ✅ 8/8 passed | NIST FIPS 180-4 vectors + multi-update |
| `test_conv.mojo` | ✅ 51/51 passed | float64, int, hex, digit, whitespace, strip |
| Binary smoke test | ⚠️ Runs but all-zero | Valid JSON structure, `_proto:1`, `result_hash` present, but `mean:0.0`, all percentiles 0.0 |
| Integration examples | ✅ Up to date | LangGraph, ChatGPT Actions, n8n correct; Power Automate needs hostname fix |
