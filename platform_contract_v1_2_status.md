# Platform Contract v1.2 Status

This file tracks implementation status for the formal `v1.2` platform contract.

## Done

- [x] Canonical `v1` public contract is exposed in OpenAPI, docs, SDK defaults, CLI examples, and MCP docs.
- [x] Canonical auth is `Authorization: Bearer <api_key>` with `X-API-Key` retained for legacy compatibility.
- [x] Canonical hosted origins are `https://api.algenta.ai` and `https://api.algenta.ai/mcp/sse`.
- [x] Local runtime no longer silently falls back to a dev stub after hosted registration failure.
- [x] Offline runtime ledger exists at `~/.algenta/runtime/history.jsonl`.
- [x] `de runtime history` exposes the local append-only task ledger.
- [x] Shared idempotency middleware exists for public write routes under `/v1/*`.
- [x] Redis-backed idempotency replay works across app instances when `app.state.redis` is present.
- [x] Concurrent write conflicts return explicit `409 resource_write_conflict`.
- [x] Public write-scope permission denials now return `403 access_scope_denied`.
- [x] MCP transports now emit explicit `unsupported_mcp_auth_configuration` and `mcp_upstream_unavailable` error payloads instead of generic tool-error strings.
- [x] Shared response middleware now enforces `X-Execution-Ms` and `X-Mojo-Ms` on non-streaming `/v1/*` responses.
- [x] Rate-limit enforcement now propagates `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After` on explicit 429 rate-limit responses.
- [x] Canonical pagination was added additively to `/v1/decisions` with `page`, `limit`, and `pages` while retaining `page_size` for legacy compatibility.
- [x] Jobs list returns `total`, `page`, `limit`, and `pages`, with `limit <= 200`.
- [x] Canonical pagination was added additively to `/v1/data`, `/v1/datasets`, `/v1/sources`, and `/v1/triggers`.
- [x] Legacy raw-list endpoints now support additive `page`/`limit` envelopes without breaking array responses for existing callers (`/v1/connectors`, `/v1/team`, `/v1/api-keys`, `/v1/distributions`, `/v1/templates`).
- [x] Object-based catalog/list endpoints now expose canonical pagination metadata (`/v1/audit-logs`, `/v1/device/list`, `/v1/engines`, `/v1/simulate/templates`).
- [x] Integration manifest exists as the canonical discoverability source file.
- [x] Manifest-driven contract artifacts now generate Python and TypeScript SDK defaults plus shared Python contract constants.
- [x] OpenAPI, MCP config, runtime defaults, and SDK clients now read canonical hosted defaults from generated contract artifacts instead of hardcoded strings.
- [x] Focused contract/unit test coverage is green for runtime, idempotency, API, CLI, and MCP touched surfaces.
- [x] Onboarding/docs parity is in place for ChatGPT, Claude/Codex, n8n, Azure, and local runtime.
- [x] Repo-wide Python test sweep has been run (`python3 -m pytest tests -q`) to expose non-contract regressions and legacy failures.
- [x] Full real go-live validation is green (`python3 -u tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30`).
- [x] Live connectivity fanout regression is fixed: read-like POST routes no longer trigger `resource_write_conflict`.
- [x] Live Python SDK integration is aligned with the canonical `ALGENTA_API_KEY` contract.
- [x] Repo-wide pytest now auto-starts a localhost API only for legacy live integration suites, with isolated test env and writable local sources dir.
- [x] Pytest collection now skips standalone real go-live runner scripts so repo-wide collection no longer imports heavyweight script-only harnesses.
- [x] Dataset service no longer eagerly imports the semantic training pipeline during normal router/test collection.
- [x] Query API now returns structured `400 empty_source` errors for header-only or no-row sources instead of bubbling raw `ValueError` as `500`.
- [x] Query execution now converts parsed Arrow tables back to row dicts before row-oriented execution, fixing record-backed negative-value queries.
- [x] Repo-wide test env leakage into `tests/test_sdk.py` is fixed by explicitly clearing canonical and legacy API key env vars in the no-key repr assertion.
- [x] Connector schema unit coverage is aligned with the live response contract: `ConnectorResponse` tests now require `visibility`.
- [x] Phase-4 Python SDK unit coverage is aligned with canonical env-var behavior and precedence (`ALGENTA_API_KEY` first, `DE_API_KEY` legacy fallback).
- [x] Repo-wide Python pytest is green end to end (`876 passed, 1 skipped, 8 deselected`).
- [x] Core lint cleanup is complete for `apps/api_server/services/auto_planner.py`.
  The file now passes Ruff cleanly and retained planner behavior under focused test coverage.
- [x] Core lint cleanup is complete for `apps/api_server/routers/query.py`.
  The file now passes Ruff cleanly, and the related query API/planner suites are green.
- [x] Post-split visibility import drift is fixed across query/data/connectors routers.
  `query.py`, `data.py`, and `connectors.py` now import visibility helpers from `data_visibility` and provider browse logic from `data_connection_specs`.
- [x] Core lint cleanup is complete for `apps/api_server/services/unit_service/formatter.py`.
  The formatter now passes Ruff cleanly, and the shared services integration suite stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/services/data_connection_specs.py`.
  The provider/source-spec module now passes Ruff cleanly, and focused data/API/CLI/MCP coverage stayed green.
- [x] Backward-compatible helper exports are restored in `apps/api_server/services/data_connection_service.py`.
  Older callers and tests can still import visibility and object-storage helpers from the orchestration module while the implementation stays split across `data_visibility.py` and `data_connection_specs.py`.
- [x] Core lint cleanup is complete for `apps/api_server/services/unit_service.py`.
  The main unit service module now passes Ruff cleanly, and the shared services plus runtime-contract tests stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/routers/data_map.py`.
  The mapping router now passes Ruff cleanly, data-map/columnar/source-registration tests stayed green, and a latent `QueryResponse` typo in the legacy fallback path was fixed to `_LegacyQueryResponse`.
- [x] Core lint cleanup is complete for `apps/api_server/routers/account.py`.
  The account router now passes Ruff cleanly, and the paginated account/template route coverage stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/schemas/simulate.py`.
  The main simulate request/schema contract file now passes Ruff cleanly, and unit schema validation coverage stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/services/unit_service/pipeline.py`.
  The pipeline entry-point module now passes Ruff cleanly, with service and schema regressions still green.
- [x] Core lint cleanup is complete for `apps/runtime/daemon.py`.
  The local runtime daemon now passes Ruff cleanly, with safer temp-socket defaults, explicit stdout writes instead of raw `print`, and runtime-contract tests still green.
- [x] Core lint cleanup is complete for `apps/cli/main.py`.
  The main CLI entrypoint now passes Ruff cleanly, and the focused CLI plus runtime-contract tests stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/routers/products.py`.
  The simplified product router now passes Ruff cleanly, with the product API import/schema surface validated through the standalone integration script.
- [x] Core lint cleanup is complete for `apps/api_server/routers/deployments.py`.
  The deployment management router now passes Ruff cleanly, and the deployment-routing middleware coverage stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/services/email_service.py`.
  The email notification service now passes Ruff cleanly, and stale Decision Engine / old hosted URL drift in user-facing emails was aligned to the canonical Algenta contract.
- [x] Core lint cleanup is complete for `apps/api_server/services/unit_service/spec.py`.
  The unit-spec registry now passes Ruff cleanly, and the schema plus shared services suites stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/services/connectors/tester.py`.
  The real connector tester dispatch module now passes Ruff cleanly, and focused connector/data-connection coverage stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/main.py`.
  The main FastAPI entrypoint now passes Ruff cleanly, with deployment-router fallback logging made explicit and OpenAPI/response-template checks still green.
- [x] Core lint cleanup is complete for `apps/mcp_server/tools/decisions.py`.
  The Decision Memory MCP tool specs and handlers now pass Ruff cleanly, with no behavior changes.
- [x] Core lint cleanup is complete for `apps/mcp_server/registry.py`.
  The MCP tool registry now passes Ruff cleanly while preserving the same tool inventory and handlers.
- [x] Core lint cleanup is complete for `apps/runtime/server.py`.
  The runtime gRPC server now passes Ruff cleanly, with the daemon socket default derived from the system temp directory and explicit grpc method-name exceptions.
- [x] Core lint cleanup is complete for `apps/api_server/services/source_registry.py`.
  The source registry now passes Ruff cleanly, with the preload/cache helpers and candidate-join scoring preserved under focused coverage.
- [x] Core lint cleanup is complete for `apps/mcp_server/tools/data.py`.
  The high-level dataset MCP tool specs now pass Ruff cleanly, with focused MCP data-tool tests still green.
- [x] Core lint cleanup is complete for `apps/runtime/license.py`.
  The local license path now passes Ruff cleanly, with explicit control-plane URL validation and debug logging replacing silent filesystem failures.
- [x] Core lint cleanup is complete for `apps/runtime/metering.py`.
  The metering queue now passes Ruff cleanly, with explicit control-plane URL validation and debug logging replacing silent local persistence failures.
- [x] Core lint cleanup is complete for `apps/api_server/schemas/response.py`.
  The shared decision-response schemas now pass Ruff cleanly, with schema validation coverage still green.
- [x] Core lint cleanup is complete for `apps/api_server/routers/auth.py`.
  The auth router now passes Ruff cleanly, with only formatting/noise fixes and no auth-flow behavior change.
- [x] Core lint cleanup is complete for `apps/api_server/routers/billing.py`.
  The billing router now passes Ruff cleanly, including explicit logging instead of silent subscription-plan parse fallback.
- [x] Core lint cleanup is complete for `apps/api_server/routers/ingest.py`.
  The ingest router now passes Ruff cleanly, with small comprehension/type cleanup and no ingest behavior change.
- [x] Core lint cleanup is complete for `apps/api_server/routers/decisions.py`.
  The Decision Memory API router now passes Ruff cleanly, and decision-list pagination coverage stayed green.
- [x] Core lint cleanup is complete for `apps/mcp_server/transports/http_sse.py`.
  The HTTP/SSE MCP transport now passes Ruff cleanly, with explicit debug logging for malformed scope headers instead of silent continue.
- [x] Core lint cleanup is complete for `apps/mcp_server/tools/query.py`.
  The query MCP tool spec now passes Ruff cleanly, and focused MCP query/data tool coverage stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/services/data_visibility.py`.
  The shared dataset/connector visibility helpers now pass Ruff cleanly, with focused data-connection visibility coverage still green.
- [x] Core lint cleanup is complete for `apps/api_server/services/simulation_service.py`.
  The simulation service now passes Ruff cleanly, with only mechanical cleanup plus explicit debug logging replacing the stale silent simulation_model assignment failure.
- [x] Core lint cleanup is complete for `apps/cli/support.py`.
  The shared CLI support layer now passes Ruff cleanly, with explicit base-URL validation and debug logging for secure-storage fallback failures.
- [x] Core lint cleanup is complete for `apps/cli/data_commands.py`.
  The CLI data command module now passes Ruff cleanly, and focused CLI/runtime tests stayed green.
- [x] Core lint cleanup is complete for `apps/mcp_server/tools/sources.py`.
  The advanced source-registration MCP tool specs now pass Ruff cleanly, with focused source-registration coverage still green.
- [x] Core lint cleanup is complete for `apps/api_server/services/unit_service/validate.py`.
  The unit validation helpers now pass Ruff cleanly, and the unit-service plus source-registration suites stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/routers/triggers.py`.
  The trigger router now passes Ruff cleanly, with explicit warning logs replacing the stale silent policy-gate failure path.
- [x] Core lint cleanup is complete for `apps/api_server/routers/team.py`.
  The team and audit-log router now passes Ruff cleanly, and focused enterprise/data API coverage stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/routers/playground.py`.
  The playground router now passes Ruff cleanly, with explicit exception chaining on the error path and focused API coverage still green.
- [x] Core lint cleanup is complete for `apps/runtime/device.py`.
  The device fingerprint helper now passes Ruff cleanly, with explicit debug logging for machine-ID fallbacks and a resolved `ioreg` path instead of a bare subprocess executable name.
- [x] Core lint cleanup is complete for `apps/runtime/credits.py`.
  The local credit bucket now passes Ruff cleanly, with validated control-plane URL usage for refresh calls and focused runtime/license/credit coverage still green.
- [x] Core lint cleanup is complete for `apps/api_server/routers/stream.py`.
  The streaming simulation SSE router now passes Ruff cleanly, including the fixed quota-error closure path, and direct OpenAPI import plus response-header checks stayed green.
- [x] Core lint cleanup is complete for `apps/mcp_server/tools/triggers.py`.
  The MCP trigger tool specs now pass Ruff cleanly, and focused MCP plus pagination coverage stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/services/job_service.py`.
  The async job lifecycle service now passes Ruff cleanly, with explicit debug logging replacing the stale silent simulation-model persistence failure and new focused unit tests covering structured errors and terminal fallback payloads.
- [x] Core lint cleanup is complete for `apps/api_server/services/chart_service.py`.
  The chart-building service now passes Ruff cleanly, and the focused chart-service integration check stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/routers/recommend.py`.
  The recommendation router now passes Ruff cleanly, with explicit debug logging replacing the stale silent calibration failure and focused adversarial recommendation coverage still green.
- [x] Core lint cleanup is complete for `apps/api_server/routers/infrastructure.py`.
  The infrastructure and self-hosted node router now passes Ruff cleanly, and focused direct router coverage now exists for node registration and heartbeat org-isolation behavior.
- [x] Core lint cleanup is complete for `apps/api_server/connectors/cloud_connector.py`.
  The object-storage connector module now passes Ruff cleanly, and the focused cloud-connector plus data-connection suites stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/services/unit_service/__init__.py`.
  The unit-service package entrypoint now passes Ruff cleanly, with backward-compatible helper re-exports explicitly listed in `__all__` and shared services/schema tests still green.
- [x] Core lint cleanup is complete for `apps/api_server/services/stripe_service.py`.
  The Stripe billing helper now passes Ruff cleanly, and the Phase 5B billing unit suite stayed green.
- [x] Core lint cleanup is complete for `apps/api_server/services/engine_selector.py`.
  The engine auto-selector now passes Ruff cleanly, and new focused unit tests cover forecast, tail-risk, and high-run-count selection heuristics.
- [x] Core lint cleanup is complete for `apps/api_server/services/cost_tracker_service.py`.
  The deployment cost tracker now passes Ruff cleanly, and new focused unit tests cover monthly cost estimation defaults and markup application.
- [x] Core lint cleanup is complete for `apps/api_server/routers/jobs.py`.
  The async jobs router now passes Ruff cleanly, with the webhook test route fixed to import and call the shared webhook helpers, and focused router plus platform-contract coverage still green.

## In Progress

- [~] Repo-wide lint backlog triage is the remaining broad validation task.
  Python pytest is now fully green. `make lint` has been reduced from `55,443` Ruff violations to `2,020` remaining by:
  - moving Ruff config to the non-deprecated `lint` section
  - excluding non-source / duplicated trees (`.codex`, `hello-world`, `mojo_env`, `apps/api-server`, generated benchmark libs, Colab notebooks)
  - tightening per-file ignores for tests, benchmarks, training scripts, and Alembic migrations
  - running a safe Ruff autofix pass (`1,057` issues fixed automatically)
  A follow-up pass has now reduced Ruff further to `1,550` remaining by:
  - treating intentional CLI output and the static simulation template catalog as file-level lint-policy exceptions
  - fixing compute/config lint in `apps/api_server/compute/mojo_adapter.py`, `apps/api_server/compute/mojo_pool.py`, and `apps/api_server/config.py`
  The latest passes reduced Ruff again to `689` remaining by:
  - cleaning `apps/api_server/services/auto_planner.py`
  - cleaning `apps/api_server/routers/query.py`
  - cleaning `apps/api_server/services/unit_service/formatter.py`
  - cleaning `apps/api_server/services/data_connection_specs.py`
  - cleaning `apps/api_server/services/unit_service.py`
  - cleaning `apps/api_server/routers/data_map.py`
  - cleaning `apps/api_server/routers/account.py`
  - cleaning `apps/api_server/schemas/simulate.py`
  - cleaning `apps/api_server/services/unit_service/pipeline.py`
  - cleaning `apps/runtime/daemon.py`
  - cleaning `apps/cli/main.py`
  - cleaning `apps/api_server/routers/products.py`
  - cleaning `apps/api_server/routers/deployments.py`
  - cleaning `apps/api_server/services/email_service.py`
  - cleaning `apps/api_server/services/unit_service/spec.py`
  - cleaning `apps/api_server/services/connectors/tester.py`
  - cleaning `apps/api_server/main.py`
  - cleaning `apps/mcp_server/tools/decisions.py`
  - cleaning `apps/mcp_server/registry.py`
  - cleaning `apps/runtime/server.py`
  - cleaning `apps/api_server/services/source_registry.py`
  - cleaning `apps/mcp_server/tools/data.py`
  - cleaning `apps/runtime/license.py`
  - cleaning `apps/runtime/metering.py`
  - cleaning `apps/api_server/schemas/response.py`
  - cleaning `apps/api_server/routers/auth.py`
  - cleaning `apps/api_server/routers/billing.py`
  - cleaning `apps/api_server/routers/ingest.py`
  - cleaning `apps/api_server/routers/decisions.py`
  - cleaning `apps/mcp_server/transports/http_sse.py`
  - cleaning `apps/mcp_server/tools/query.py`
  - cleaning `apps/api_server/services/data_visibility.py`
  - cleaning `apps/api_server/services/simulation_service.py`
  - cleaning `apps/cli/support.py`
  - cleaning `apps/cli/data_commands.py`
  - cleaning `apps/mcp_server/tools/sources.py`
  - cleaning `apps/api_server/services/unit_service/validate.py`
  - cleaning `apps/api_server/routers/triggers.py`
  - cleaning `apps/api_server/routers/team.py`
  - cleaning `apps/api_server/routers/playground.py`
  - cleaning `apps/runtime/device.py`
  - cleaning `apps/runtime/credits.py`
  - cleaning `apps/api_server/routers/stream.py`
  - cleaning `apps/mcp_server/tools/triggers.py`
  - cleaning `apps/api_server/services/job_service.py`
  - cleaning `apps/api_server/services/chart_service.py`
  - cleaning `apps/api_server/routers/recommend.py`
  - cleaning `apps/api_server/routers/infrastructure.py`
  - cleaning `apps/api_server/connectors/cloud_connector.py`
  - cleaning `apps/api_server/services/unit_service/__init__.py`
  - cleaning `apps/api_server/services/stripe_service.py`
  - cleaning `apps/api_server/services/engine_selector.py`
  - cleaning `apps/api_server/services/cost_tracker_service.py`
  - cleaning `apps/api_server/routers/jobs.py`
  - restoring backward-compatible helper re-exports in `apps/api_server/services/data_connection_service.py`
  - fixing router import drift in `apps/api_server/routers/query.py`, `apps/api_server/routers/data.py`, and `apps/api_server/routers/connectors.py`
  - validating planner/query behavior with `tests/test_auto_planner.py`, `tests/test_query_planner.py`, and `tests/test_query_api_contract.py`
  - validating service behavior with `tests/integration/test_services.py`
  - validating data/API/CLI/MCP behavior with `tests/test_data_connections.py`, `tests/test_data_api.py`, `tests/test_mcp_data_tools.py`, and `tests/test_cli_data.py`
  - validating data-map/columnar/source-registration behavior with `tests/test_columnar_loading.py`, `tests/test_source_registration.py`, and `tests/integration/test_csv_pipeline.py::test_data_mapping`
  - validating account/pagination behavior with `tests/test_legacy_list_pagination.py` and `tests/integration/test_services.py::test_templates`
  - validating schema and pipeline behavior with `tests/unit/test_schemas.py`
  - validating connector tester behavior with `tests/test_connector_tester.py` and `tests/test_data_connections.py`
  - validating `apps/api_server/main.py` behavior with direct OpenAPI import checks plus `tests/test_response_contract_headers.py` and `tests/integration/test_services.py::test_templates`
  - validating source-registry/runtime/MCP behavior with `tests/test_source_registration.py`, `tests/test_columnar_loading.py`, `tests/test_query_runtime_cache.py`, `tests/test_mcp_data_tools.py`, and `tests/test_runtime_contract.py`
  - validating runtime/MCP/schema behavior with `tests/test_mcp_data_tools.py`, `tests/test_runtime_contract.py`, `tests/test_runtime_license.py`, and `tests/unit/test_schemas.py`
  - validating billing/data/schema behavior with `tests/test_decisions_api.py`, `tests/test_data_api.py`, `tests/unit/test_schemas.py`, and `tests/integration/test_services.py::test_templates`
  - validating MCP transport/query/data-visibility behavior with `tests/test_mcp_data_tools.py`, `tests/test_mcp_client.py`, and `tests/test_data_connections.py`
  - validating simulation behavior with `tests/integration/test_services.py::test_simulation_service` and `tests/unit/test_schemas.py`
  - validating CLI behavior with `tests/test_cli_data.py` and `tests/test_runtime_contract.py`
  - validating source/unit validation behavior with `tests/test_source_registration.py` and `tests/integration/test_services.py::test_unit_service`
  - validating trigger/team/playground behavior with `tests/unit/test_phase7_enterprise.py`, `tests/test_decisions_api.py`, and `tests/test_data_api.py`
  - validating runtime device/credit behavior with `tests/test_runtime_contract.py`, `tests/test_runtime_license.py`, and `tests/test_credit_bucket.py`
  - validating streaming/OpenAPI behavior with direct `app.openapi()` checks and `tests/test_response_contract_headers.py`
  - validating MCP trigger specs and list pagination with `tests/test_mcp_data_tools.py` and `tests/test_list_pagination_contract.py`
  - validating async job service behavior with `tests/test_job_service.py`
  - validating chart service behavior with `tests/integration/test_services.py::test_chart_service`
  - validating recommendation behavior with `tests/integration/test_adversarial.py -k 'recommend_decision_plan_has_all_options or recommend_identical_options'`
  - validating infrastructure node behavior with `tests/test_infrastructure_router.py`
  - validating cloud connectors and data connections with `tests/test_cloud_connectors.py` and `tests/test_data_connections.py`
  - validating unit-service package exports with `tests/integration/test_services.py::test_unit_service` and `tests/unit/test_schemas.py`
  - validating Stripe billing helpers with `tests/unit/test_phase5b_billing.py`
  - validating engine selection with `tests/test_engine_selector.py`
  - validating cost estimation with `tests/test_cost_tracker_service.py`
  - validating jobs router behavior with `tests/test_jobs_router.py` and `tests/test_platform_contract.py`
  The latest backend/runtime-only passes reduced Ruff further to `424` remaining by:
  - excluding generated runtime gRPC stubs under `apps/runtime/proto`
  - treating generated `apps/platform_contract_constants.py` line length as a generated-artifact policy exception
  - cleaning `apps/runtime/client.py`
  - cleaning `apps/runtime/executor.py`
  - cleaning `apps/runtime/sdk.py`
  - cleaning `apps/worker/tasks/simulation_task.py`
  - cleaning `apps/mcp_server/tools/connectors.py`
  - cleaning `apps/mcp_server/tools/datasets.py`
  - cleaning `apps/mcp_server/tools/ingest.py`
  - cleaning `apps/mcp_server/tools/jobs.py`
  - cleaning `apps/mcp_server/tools/runs.py`
  - cleaning `apps/mcp_server/tools/simulate.py`
  - cleaning `apps/mcp_server/transports/stdio.py`
  - cleaning `mojo/engine/vector_kernels/ffi_layout.py`
  - cleaning `mojo/engine/vector_kernels/meta_executor.py`
  - cleaning `mojo/engine/vector_kernels/query_planner.py`
  - cleaning `mojo/engine/vector_kernels/resolver.py`
  - cleaning `mojo/engine/vector_kernels/tokenizer.py`
  - validating runtime/worker behavior with `tests/test_sdk.py`, `tests/integration/test_worker_tasks.py`, and `tests/test_runtime_contract.py`
  - validating MCP/runtime contract behavior with `tests/test_mcp_data_tools.py` and `tests/test_platform_contract_generation.py`
  - validating vector resolver/planner behavior with `tests/test_vector_resolver.py`, `tests/test_query_planner.py`, `tests/test_vector_resolver_hospitality.py`, and `tests/test_auto_planner.py`
  - re-running the strongest real path with `python3 -u tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30`
  The latest training/example pass reduced Ruff further to `381` remaining by:
  - cleaning `examples/langgraph/decision_tool.py`
  - cleaning `training/semantic/build_dataset.py`
  - cleaning `training/semantic/build_vocab.py`
  - cleaning `training/semantic/export_artifacts.py`
  - cleaning `training/semantic/pipeline.py`
  - cleaning `training/semantic/precompute_neighbors.py`
  - cleaning `training/semantic/schema_ingestor.py`
  - cleaning `training/semantic/schema_registry.py`
  - cleaning `training/semantic/train_thin_semantic.py`
  - validating training/example syntax with `python3 -m py_compile` on the touched files
  - validating training/example imports with `python3 -m pytest tests/test_dataset_service_imports.py tests/unit/test_phase4_sdk.py -q`
  Remaining lint debt is now concentrated primarily in old benchmark harnesses and a smaller residual tail outside the main runtime/API/training path.

## Remaining

- [x] Clear the handwritten repo-wide Ruff backlog so `ruff check . --statistics` passes cleanly.
  Repo-wide Ruff is now clean. The final cleanup batches covered the remaining
  benchmark harnesses, integration scripts, generated contract artifacts, SDK
  helpers, and small utility scripts without reopening web-interface scope.

## Last Focused Validation

- `python3 -m pytest tests/test_idempotency_middleware.py -q`
- `python3 -m pytest tests/test_platform_contract.py tests/test_runtime_contract.py tests/test_cli_data.py tests/unit/test_rbac.py tests/test_data_connections.py -q`
- `python3 -m pytest tests/unit/test_phase5a_quota.py tests/test_response_contract_headers.py tests/test_data_api.py tests/test_platform_contract.py tests/test_decisions_api.py -q`
- `python3 -m pytest tests/test_mcp_client.py tests/test_mcp_data_tools.py tests/test_cli_data.py tests/test_idempotency_middleware.py -q`
- `python3 scripts/generate_platform_contract_artifacts.py`
- `python3 -m pytest tests/test_platform_contract_generation.py tests/test_mcp_client.py tests/test_runtime_contract.py tests/test_runtime_license.py tests/test_sdk.py -q`
- `python3 -m pytest tests/test_response_contract_headers.py tests/unit/test_phase5a_quota.py -q`
- `python3 -m pytest tests/test_data_api.py tests/test_mcp_data_tools.py tests/test_cli_data.py -q`
- `python3 -m pytest tests/test_data_connections.py tests/test_idempotency_middleware.py -q`
- `python3 -m pytest tests/test_legacy_list_pagination.py tests/test_platform_contract.py tests/unit/test_phase7_enterprise.py -q`
- `python3 -m pytest tests/test_data_api.py tests/test_data_connections.py tests/test_mcp_data_tools.py tests/test_cli_data.py tests/test_idempotency_middleware.py tests/test_platform_contract_generation.py -q`
- `python3 -m pytest tests/test_platform_contract.py tests/test_platform_contract_generation.py -q`
- `python3 -m pytest tests/test_legacy_list_pagination.py tests/test_mcp_client.py tests/test_runtime_contract.py tests/test_runtime_license.py tests/test_sdk.py -q`
- `python3 -m pytest tests/test_pytest_collection_policy.py tests/test_idempotency_middleware.py -q`
- `python3 -m pytest tests/test_dataset_service_imports.py tests/test_list_pagination_contract.py -q`
- `python3 -m pytest tests/test_query_api_contract.py tests/integration/test_adversarial.py::test_query_empty_csv -q`
- `python3 -m pytest tests/integration/test_adversarial.py::test_query_all_negative_revenue tests/integration/test_adversarial.py::test_query_empty_csv tests/test_query_api_contract.py -q`
- `python3 -m pytest tests/test_sdk.py::test_runtime_repr_no_key -q`
- `python3 -m pytest tests/unit/test_connectors.py::test_connector_model_all_types_present -q`
- `python3 -m pytest tests/test_sdk.py tests/integration/test_worker_tasks.py tests/test_runtime_contract.py tests/test_mcp_data_tools.py tests/test_platform_contract_generation.py -q`
- `python3 -m pytest tests/test_vector_resolver.py tests/test_query_planner.py tests/test_vector_resolver_hospitality.py tests/test_auto_planner.py -q`
- `python3 -u tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30`
- `python3 -m py_compile examples/langgraph/decision_tool.py training/semantic/build_dataset.py training/semantic/build_vocab.py training/semantic/export_artifacts.py training/semantic/pipeline.py training/semantic/precompute_neighbors.py training/semantic/schema_ingestor.py training/semantic/schema_registry.py training/semantic/train_thin_semantic.py`
- `python3 -m pytest tests/test_dataset_service_imports.py tests/unit/test_phase4_sdk.py -q`
- `python3 -m pytest tests/unit/test_connectors.py -q`
- `python3 -m pytest tests/unit/test_phase4_sdk.py -q`
- `python3 -m pytest tests -x -q`
- `make lint`
- `python3 -m ruff check . --fix`
- `python3 -m ruff check apps/api_server/compute/mojo_adapter.py apps/api_server/compute/mojo_pool.py apps/api_server/config.py`
- `python3 -m pytest tests/integration/test_mojo_pool.py tests/unit/test_phase5a_quota.py -q`
- `python3 -m ruff check apps/api_server/services/auto_planner.py`
- `python3 -m pytest tests/test_auto_planner.py -q`
- `python3 -m pytest tests/test_query_planner.py -q`
- `python3 -m ruff check . --statistics`
- `python3 -m ruff check apps/api_server/routers/query.py apps/api_server/routers/connectors.py apps/api_server/routers/data.py`
- `python3 -m pytest tests/test_query_api_contract.py tests/test_query_planner.py -q`
- `python3 -m ruff check apps/api_server/services/unit_service/formatter.py`
- `python3 -m pytest tests/integration/test_services.py -q`
- `python3 -m ruff check apps/api_server/services/data_connection_specs.py apps/api_server/services/data_connection_service.py`
- `python3 -m pytest tests/test_data_connections.py tests/test_data_api.py tests/test_mcp_data_tools.py tests/test_cli_data.py -q`
- `python3 -m ruff check apps/api_server/services/unit_service.py`
- `python3 -m pytest tests/integration/test_services.py tests/test_runtime_contract.py -q`
- `python3 -m ruff check apps/api_server/routers/data_map.py`
- `python3 -m pytest tests/test_columnar_loading.py tests/test_source_registration.py tests/integration/test_csv_pipeline.py::test_data_mapping -q`
- `python3 -m ruff check apps/api_server/routers/account.py`
- `python3 -m pytest tests/test_legacy_list_pagination.py tests/integration/test_services.py::test_templates -q`
- `python3 -m ruff check apps/api_server/schemas/simulate.py`
- `python3 -m pytest tests/unit/test_schemas.py -q`
- `python3 -m ruff check apps/api_server/services/unit_service/pipeline.py`
- `python3 -m pytest tests/integration/test_services.py tests/unit/test_schemas.py -q`
- `python3 -m ruff check apps/runtime/daemon.py`
- `python3 -m pytest tests/test_runtime_contract.py -q`
- `python3 -m ruff check apps/cli/main.py`
- `python3 -m pytest tests/test_cli_data.py -q`
- `python3 -m ruff check apps/api_server/routers/products.py`
- `DE_SKIP_API=1 python3 tests/integration/test_products.py`
- `python3 -m ruff check apps/api_server/routers/deployments.py`
- `python3 -m pytest tests/integration/test_middleware.py::test_deployment_router_middleware -q`
- `python3 -m ruff check apps/api_server/services/email_service.py`
- `python3 -m pytest tests/test_platform_contract.py -q`
- `make lint`
- `python3 -m pytest tests -q`
- `python3 -u tests/integration/test_go_live_connectivity_real.py --parallel-tasks 4`
- `python3 -u tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30`
- `python3 -m ruff check apps/api_server/routers/triggers.py apps/api_server/routers/team.py apps/api_server/routers/playground.py`
- `python3 -m pytest tests/unit/test_phase7_enterprise.py tests/test_decisions_api.py tests/test_data_api.py -q`
- `python3 -m ruff check apps/runtime/device.py apps/runtime/credits.py`
- `python3 -m pytest tests/test_runtime_contract.py tests/test_runtime_license.py tests/test_credit_bucket.py -q`
- `python3 -m ruff check apps/api_server/routers/stream.py`
- `python3 -m pytest tests/test_response_contract_headers.py -q`
- `python3 -m ruff check apps/mcp_server/tools/triggers.py`
- `python3 -m pytest tests/test_mcp_data_tools.py tests/test_list_pagination_contract.py -q`
- `python3 -m ruff check apps/api_server/services/job_service.py tests/test_job_service.py`
- `python3 -m pytest tests/test_job_service.py -q`
- `python3 -m ruff check apps/api_server/services/chart_service.py`
- `python3 -m pytest tests/integration/test_services.py::test_chart_service -q`
- `python3 -m ruff check apps/api_server/routers/recommend.py`
- `python3 -m pytest tests/integration/test_adversarial.py -k 'recommend_decision_plan_has_all_options or recommend_identical_options' -q`
- `python3 -m ruff check apps/api_server/routers/infrastructure.py tests/test_infrastructure_router.py`
- `python3 -m pytest tests/test_infrastructure_router.py -q`
- `python3 -m ruff check apps/api_server/connectors/cloud_connector.py`
- `python3 -m pytest tests/test_cloud_connectors.py tests/test_data_connections.py -q`
- `python3 -m ruff check apps/api_server/services/unit_service/__init__.py`
- `python3 -m pytest tests/integration/test_services.py::test_unit_service tests/unit/test_schemas.py -q`
- `python3 -m ruff check apps/api_server/services/stripe_service.py`
- `python3 -m pytest tests/unit/test_phase5b_billing.py -q`
- `python3 -m ruff check apps/api_server/services/engine_selector.py tests/test_engine_selector.py`
- `python3 -m pytest tests/test_engine_selector.py -q`
- `python3 -m ruff check apps/api_server/services/cost_tracker_service.py tests/test_cost_tracker_service.py`
- `python3 -m pytest tests/test_cost_tracker_service.py -q`
- `python3 -m ruff check apps/api_server/routers/jobs.py tests/test_jobs_router.py`
- `python3 -m pytest tests/test_jobs_router.py tests/test_platform_contract.py -q`

## 2026-04-21 benchmark burn-down continuation

- Cleaned the remaining benchmark harness hotspots:
  - `benchmarks/universal_benchmark.py`
  - `benchmarks/bench_llm_e2e.py`
  - `benchmarks/bench_engines.py`
  - `benchmarks/bench_claude_mcp_20q.py`
  - `benchmarks/test_query_advanced.py`
  - `benchmarks/bench_10q.py`
  - `benchmarks/test_live.py`
  - `benchmarks/test_query.py`
- `ruff check benchmarks --statistics` is now clean.
- Repo-wide Ruff moved from `381` at the start of this pass to `273` remaining.
- Full strongest real-path suite stayed green after the benchmark cleanup:
  - `python3 -u tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30`
  - result: `Passed suites: 12`, `Failed suites: 0`
- Narrow benchmark validation executed on current code:
  - `python3 -m py_compile benchmarks/universal_benchmark.py benchmarks/bench_llm_e2e.py benchmarks/bench_engines.py benchmarks/bench_claude_mcp_20q.py benchmarks/test_query_advanced.py benchmarks/bench_10q.py benchmarks/test_live.py benchmarks/test_query.py`
  - `python3 -u benchmarks/universal_benchmark.py`
  - `python3 -u benchmarks/bench_engines.py`
  - `python3 -u benchmarks/bench_llm_e2e.py`
  - `python3 -u benchmarks/test_query_advanced.py`
  - `python3 -u benchmarks/bench_10q.py`
  - `python3 -u benchmarks/test_query.py`
- `python3 -u benchmarks/test_live.py`
- Remaining Ruff debt is no longer in `benchmarks/`; the next highest-value hotspots are outside the benchmark tree.

## 2026-04-21 final Ruff completion

- Completed the final non-web Ruff burn-down from `273` remaining to `0`.
- The closing batches cleaned:
  - benchmark harnesses under `tests/benchmark/`
  - remaining integration scripts under `tests/integration/`
  - generated Python contract artifacts under `packages/*/_contract.py`
  - SDK/runtime support files and utility scripts such as `scripts/run_diagnostics.py`
- The generated artifact source was also updated in
  `scripts/generate_platform_contract_artifacts.py` so future regenerations stay
  Ruff-clean.
- Latest focused validation after the zero-debt pass:
  - `ruff check . --statistics`
  - `python3 scripts/run_diagnostics.py`
  - `DE_SKIP_API=1 python3 tests/integration/test_billing_team.py`
  - historical at that time: `DE_SKIP_API=1 python3 tests/integration/test_cli_full.py`
  - current canonical live CLI proof: `python3 tests/integration/test_cli.py`
  - `DE_SKIP_API=1 python3 tests/integration/test_engines.py`
  - `python3 -m pytest tests/integration/test_adversarial.py tests/test_sdk.py -q`
  - `python3 -m pytest tests -q`
  - `python3 -u tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30`
- Latest strongest real-path result:
  - `Passed suites: 12`
  - `Failed suites: 0`
- Latest broad backend suite result:
  - `1091 passed`
  - `1 skipped`
  - `8 deselected`
