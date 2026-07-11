# Decision Engine Scorecard

Updated: 2026-07-11

## Current measured state

| Area | Current | Evidence | Status |
| --- | --- | --- | --- |
| Mojo correctness (A-Z) | 454/454 libraries passed, 4266/4266 functions passed, 115.4s total | `build/mojo_libraries_az_summary.json`, `tests/integration/test_mojo_libraries_az.py` | Green |
| Benchmark discovery inventory | 1 libraries benchmarkable today: 1 top-level, 0 nested; shipping contract remains 22 modules / 209 functions | `benchmarks/summary.json`, `tests/benchmark_mojo_vs_python.py` | Green |
| Mojo vs Python speed | 9.26x median, 9.26x mean, 9.26x max, 9.26x min across 9 compared functions | `benchmarks/summary.json`, `tests/benchmark_mojo_vs_python.py` | Green |
| Provider routing overhead | p50 in-process routed latency (chat/embed) direct 4.62/4.58 us, single 7.71/7.58 us, nested 12.54/15.33 us, failover 13.88/14.79 us; failover mean provider attempts 2.0/2.0 | `build/provider_routing_overhead_benchmark.json`, `benchmarks/provider_routing_overhead_benchmark.py`, `tests/test_provider_routing_overhead_benchmark.py` | Green |
| Repository intelligence workflow | mean stages cold snapshot 869.24 ms, existing hit 62.09 ms, triage 23.33 ms, decision 174.33 ms, simulate 2.15 ms, apply patch 0.9 ms, local branch 621.21 ms; token reduction 10.93x mean, patch risk 0.27 | `build/repository_intelligence_benchmark.json`, `benchmarks/repository_intelligence_benchmark.py`, `tests/test_repository_intelligence_benchmark.py` | Green |
| MCP runtime integration | 65/65 live MCP boundary tests passed; 0 runtime proof tools present, 112 tools expected overall | `build/mcp_server_integration_summary.json`, `tests/integration/test_mcp_server.py` | Green |
| OpenAPI compliance | 90/90 compliance checks passed; 0 paths, 0 schemas, security  | `build/openapi_integration_summary.json`, `tests/integration/test_openapi.py` | Green |
| Resolver accuracy (universal) | Not measured yet | No cross-industry benchmark corpus exists yet | Red |
| Narrow resolver regression | 12/12 correct = 100% on one hospitality schema; 30/30 regression tests passed | `build/scorecard_suite_summaries.json`, `tests/test_vector_resolver_hospitality.py` | Yellow |
| Join-path correctness | 14/14 passed | `build/scorecard_suite_summaries.json`, `tests/test_query_join_path.py` | Green |
| Import pipeline correctness | 67/67 active CSV pipeline integration checks passed | `build/csv_pipeline_summary.json`, `tests/integration/test_csv_pipeline.py` | Green |
| Import/planner regression suite | 168/168 passed | `build/scorecard_suite_summaries.json`, `tests/unit/test_connectors.py`, `tests/test_auto_planner.py`, `tests/test_vector_resolver.py`, `tests/test_query_join_path.py` | Green |
| MCP end-to-end benchmark | 18/20 passed, 428.6 ms average latency | `benchmarks/claude_mcp_20q_results.json`, `benchmarks/bench_claude_mcp_20q.py` | Yellow |
| CSV ingest throughput | Backlog: 21,118 rows/s; bookings_new: 16,035 rows/s; quotes_new: 12,338 rows/s; Available_Inventory (244 cols): 3,375 rows/s | `tests/integration/csv_pipeline_results.csv`, `tests/integration/test_csv_pipeline.py` | Green |
| Vector hot path | Prefilter + rank at N=2048: 650 ns/query batch, 43.0x faster than full scan | `benchmarks/results/engines_prefilter_vs_fullscan.json`, `mojo/engine/vector_kernels/bench_prefilter.mojo` | Green |
| Arrow/Parquet ingest throughput | Not measured | Parquet connector path is still a stub | Red |
## Go-live verifier (2026-07-10)

This is the top-level repo-owned operator proof from `tests/go_live_verify.py`. It tracks the serial go-live path separately from the dedicated LLM rollout artifacts.

| Area | Current | Evidence | Status |
| --- | --- | --- | --- |
| Serial verifier summary | 7/19 configured, 7/19 behavior-ready, completed steps connectivity, 1 failed steps | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py`, `tests/test_go_live_verify.py` | Red |
| Full real suite | 24/24 suites passed; live API-facing 13, local benchmark/regression 8, top-level verifier/bundle/A-Z 3 | `build/go_live_full_real_summary.json`, `tests/integration/test_go_live_full_real.py` | Green |
| Planned serial steps | connectivity + full_real + pytest | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/integration/GO_LIVE_VALIDATION.md` | Green |
| Latest serial durations | connectivity 19.70s, full_real 496.80s | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md` | Green |
| Canonical verifier mode | unfiltered, non-strict, includes full_real, includes pytest | `build/go_live_verify_summary.json`, `Makefile`, `tests/integration/GO_LIVE_VALIDATION.md` | Green |
| Static matrix operational gaps | 12 cases from the current static matrix status before live connectivity overrides | `build/go_live_verify_summary.json`, `tests/go_live_matrix_status.py` | Amber |
| Live connectivity skips | 12 skips captured from the latest connectivity run and merged into operational gaps | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/integration/test_go_live_connectivity_real.py` | Amber |
| Gap source breakdown | static tiers credentialed_example 2, customer_credentials_required 9, public_no_auth 1; live tiers credentialed_example 2, customer_credentials_required 9, public_no_auth 1; merged sources static_matrix+live_connectivity 12 | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py` | Amber |
| Gap connector breakdown | merged connectors azure_blob 1, bigquery 1, clickhouse 1, elasticsearch 1, gcs 1, neo4j 1, redis 1, rest_api 3, s3 1, snowflake 1 | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py` | Amber |
| Outstanding operational gaps | 12 cases outside repo-owned proof: credentialed_example 2, customer_credentials_required 9, public_no_auth 1 | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_matrix_status.py` | Amber |
| Operator next actions | 4 action groups ready from current operational gaps | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py` | Amber |
| Gap action routing | 12/12 cases mapped; actions enable_opt_in_public_cases 1, set_credentialed_example_envs 2, set_customer_connector_envs 9; envs enable_opt_in_public_cases 1, set_credentialed_example_envs 2, set_customer_connector_envs 24; connectors enable_opt_in_public_cases 1, set_credentialed_example_envs 1, set_customer_connector_envs 9; terminal rerun_strict_go_live_gate; unmapped none | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py` | Amber |
| Gap connector routing | cases azure_blob 1, bigquery 1, clickhouse 1, elasticsearch 1, gcs 1, neo4j 1, redis 1, rest_api 3, s3 1, snowflake 1; envs azure_blob 5, bigquery 2, clickhouse 3, elasticsearch 2, gcs 2, neo4j 3, redis 1, rest_api 3, s3 2, snowflake 4 | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py` | Amber |
| Gap env routing | 27 envs mapped; tiers credentialed_example 2, customer_credentials_required 24, public_no_auth 1; shared none | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py` | Amber |
| Gap env resolution | resolver-supported 26; manual-only 1; groups azure_blob 5, bigquery 2, clickhouse 3, elasticsearch 2, gcs 2, neo4j 3, redis 1, s3 2, snowflake 4; manual DE_ENABLE_SLOW_PUBLIC_REST_CASES | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py`, `tests/go_live_secret_resolver.py` | Amber |
| Gap env templates | root_env_example 27/27, go_live_validation_env_example 27/27; missing none | `build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `.env.example`, `tests/integration/go_live_validation.env.example`, `tests/go_live_verify.py` | Green |
## LLM rollout proof (2026-07-11)

This is the dedicated evidence for the 22-library Mojo LLM rollout. Use these artifacts instead of the shared `benchmarks/summary.*` files when validating the rollout itself.

| Area | Current | Evidence | Status |
| --- | --- | --- | --- |
| 22-library parity proof | 22 libraries, 209 public runtime functions, 116.6x median, 108.73x mean, 326.45x max | `build/llm_rollout_parity_benchmark.json`, `build/llm_rollout_parity_benchmark.txt`, `tests/test_llm_rollout_parity_benchmark.py` | Green |
| Compiled runtime latency proof | 22 modules, 209 functions, 0 failures, all `engine_used="mojo"`, worst cold 199.32 ms, warm 0.955 ms, hot 0.926 ms | `build/llm_compiled_runtime_benchmark.json`, `tests/test_llm_compiled_runtime_benchmark.py` | Green |
| Serving extension subset proof | 6 modules, 60 functions, 60/60 parity comparisons across 6/6 modules, speedup range 103.36x to 137.38x, compiled mojo-only, worst cold 0.69 ms, warm 0.395 ms, hot 0.380 ms | `build/llm_rollout_proof_bundle.json`, `tests/test_llm_rollout_proof_bundle.py` | Green |
| Serving extension channel coverage | python_sdk, typescript_sdk, daemon_client, runtime_local, cli, mcp, http_api_feature_flag all passed for the 6-module / 60-function serving subset; source rollout basis 209 functions | `build/llm_rollout_proof_bundle.json`, `tests/test_llm_rollout_matrix.py`, `tests/test_llm_rollout_proof_bundle.py` | Green |
| Supported channel coverage | Python SDK 7/7 passed, CLI + DaemonClient + `Runtime(mode="local")` + MCP 11/11 passed, TypeScript SDK 15 passed and 0 API-backed skips when `DE_API_KEY` is unset | `build/python_sdk_local_runtime_live_summary.json`, `build/local_runtime_cli_mcp_matrix_live_summary.json`, `build/typescript_sdk_local_runtime_live_summary.json`, `tests/integration/test_algenta_mojo_library_live.py`, `tests/integration/test_cli_mcp_runtime_libraries_live.py`, `tests/integration/test_typescript_runtime_live.py` | Green |
| SDK package contract coverage | Python SDK package contract 1 passed; TypeScript SDK package contract 1 passed and 8 skipped; both 0 failed | `tests/test_algenta_mojo_sdk.py`, `packages/ts-sdk/src/libraries.test.ts` | Green |
| HTTP API flag contract coverage | HTTP API flag contract 2 passed; 0 failed | `tests/test_runtime_libraries_api.py`, `apps/api_server/main.py`, `apps/api_server/config.py` | Green |
| HTTP API flag live coverage | HTTP API feature-flag live suite 4/4 passed; 0 failed | `build/public_http_library_routes_feature_flag_live_live_summary.json`, `tests/integration/test_runtime_libraries_http_live.py`, `tests/_asgi_client.py`, `build/llm_rollout_proof_bundle.json` | Green |
| Public HTTP API flag readiness | `/v1/libraries*` routes are feature-flag ready via `ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED` and remain disabled by default | `tests/test_runtime_libraries_api.py`, `apps/api_server/main.py`, `apps/api_server/config.py` | Green |
| Machine-readable rollout bundle | Single JSON bundle validating parity, compiled runtime, SDK package contracts, supported public channels, and underlying local lanes | `build/llm_rollout_proof_bundle.json`, `benchmarks/llm_rollout_proof_bundle.py`, `tests/test_llm_rollout_proof_bundle.py` | Green |
## Non-negotiable product requirement

This project must be scored against:

- any tabular data
- any column naming style
- any supported database or file source
- local, API, and MCP execution paths

Industry-specific results are useful only as narrow regressions. They are not product-level accuracy claims.

## Gaps that still matter

| Area | Current gap | Why it matters |
| --- | --- | --- |
| Import accuracy | No labeled corpus yet for "any DB/CSV import" percentage accuracy | We can say the path is safer and tested, but not yet claim a universal import accuracy %
| Resolver accuracy | Current measured percentage is industry-specific, not universal | Needed before claiming "any data, any column, any database"
| Join accuracy | Correctness tests are green, but there is no benchmark corpus with a reported accuracy % | Needed before claiming broad multi-hop join reliability
| Database coverage | No benchmark matrix yet across multiple DB engines and schemas | Needed before claiming "any database"
| Arrow/Parquet | `parquet` path is not production-ready yet | You want Arrow/Parquet, local installs, API, and MCP at scale
| API latency | No current end-to-end API benchmark summary in `benchmarks/` | Needed for deployment planning
| Local embedded latency | No dedicated local-only benchmark summary yet | Needed for desktop/offline installs

## Proposed production targets

| Area | Target |
| --- | --- |
| Import accuracy | >= 99% typed-field correctness on a labeled mixed-format import corpus |
| Resolver accuracy | >= 95% top-1 on a cross-domain corpus spanning generic ERP, finance, logistics, healthcare, retail, manufacturing, and synthetic unknown schemas |
| Join accuracy | >= 95% correct join-path selection on labeled 1-hop and 2-hop corpora across mixed-schema databases |
| Database coverage | Green benchmark runs on PostgreSQL, SQLite, DuckDB, MySQL-compatible, and CSV/Arrow/Parquet sources |
| Local hot query latency | p50 < 50 ms, p95 < 150 ms |
| API query latency | p50 < 150 ms, p95 < 400 ms |
| MCP query latency | p50 < 300 ms, p95 < 700 ms |
| CSV ingest throughput | >= 2k rows/s on tall files, >= 500 rows/s on wide 200+ column files |
| Arrow/Parquet ingest throughput | >= 50k rows/s local scan for common analytics shapes once implemented |

## Read this scorecard correctly

- The Mojo compute layer is already fast enough to justify the architecture.
- The hospitality resolver number is a narrow regression, not a product-wide accuracy claim.
- CSV import is materially improved and currently fast enough for local usage, but the project still lacks a formal universal import-accuracy benchmark.
- The missing pieces for the user requirement are universal benchmark corpora, database-matrix testing, and real Arrow/Parquet ingest.
