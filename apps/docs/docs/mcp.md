---
sidebar_position: 7
---

# MCP

Algenta exposes a broad MCP surface, including the governed data/query flow from this rollout.

## Current truth

The MCP server in this repo covers more than just queries. It includes tools across:

- source/data operations
- deterministic query operations
- local/runtime-backed Mojo library operations
- simulation workflows
- memory
- triggers and automation-related operations

## Primary data/query flow

For the governed data/query lane, the preferred MCP sequence is:

1. `get_contract()`
2. `list_data(search="orders", compact=true)`
3. `get_data_summary(dataset_id)`
4. `get_data_schema(dataset_id)` only if the agent really needs the full schema
5. `query_data(...)` for one governed exact metric
6. `query_batch(...)` for several governed exact metrics in one call
7. `query_sql_report(...)` only for wide read-only rowsets

That mirrors the same API/SDK contract published through `/v1/meta/contract` and `x-primary-data-query-contract`.
That same machine-readable contract also publishes
`primary_data_query_contract.governed_filter_contract` so MCP agents can
inspect selector fields, operator families, and validation rules before
building exact filters.

## Local runtime libraries

When the local daemon is available, MCP also exposes the runtime-backed Mojo
library lane directly:

1. `list_runtime_libraries(search="token")`
2. `execute_runtime_library(module="text.tokenizer", function="char_ngrams", args=["alpha beta", 3])`

These tools stay on the local/runtime-backed compute surface. They do not route
through the hosted governed data/query API and they preserve canonical dotted
module names such as `text.tokenizer` and `vector_kernels.table`.

The checked-in MCP example sequences live in the multihop example bundle:

- [`mcp_governed_exact_sequence.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mcp_governed_exact_sequence.json)
- [`mcp_governed_sql_report_sequence.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mcp_governed_sql_report_sequence.json)
- [`mcp_runtime_library_sequence.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mcp_runtime_library_sequence.json)

## LLM utility and agent-run flow

MCP also exposes the current truthful utility-model and persisted agent-run lane:

1. `list_models()` for the truthful model catalog, including routed target, failover, timeout, aggregate provider-auth metadata, and capability-specific chat/embedding auth-header readiness
2. `resolve_artifact_bridge(repo_id=..., filename=..., revision=..., local_files_only=...)` for cache-safe Hugging Face artifact resolution
3. `tokenize(...)`, `count_tokens(...)`, `chat_completions(...)`, `responses(...)`, `embeddings(...)`, `embedding_similarity(...)`, or `rerank(...)`
4. `product_decision(...)`, `product_agent_run(...)`, `product_optimize(...)`, `product_retrieve(...)`, and `product_forecast(...)` for the business-facing simplified product helpers
5. `recommend(...)`, `score(...)`, `batch(...)`, or `compare(...)` for the decision-runtime helpers
6. `submit_job(...)`, `list_jobs(...)`, `get_job_status(...)`, `poll_job(...)`, `get_job_result(...)`, `cancel_job(...)`, and `test_webhook_delivery(...)` for async simulation orchestration
7. `register_trigger(...)`, `list_triggers(...)`, `fire_trigger(...)`, `pause_trigger(...)`, and `delete_trigger(...)` for trigger automation
8. `plan_decision(...)` when you need the structured `DecisionPlan` only
9. `log_decision(...)`, `list_decisions(...)`, `get_decision(...)`, `record_outcome(...)`, `execute_decision(...)`, and `delete_decision(...)` for the persisted decision-memory lifecycle
10. `create_agent_run(...)`
11. `list_agent_runs(...)` for paginated persisted run discovery
12. `get_agent_run(run_id)` and `get_agent_run_events(run_id)` to inspect lifecycle state
13. `get_agent_run_checkpoints(run_id)`, `query_agent_run_checkpoints(...)`, `get_agent_run_mission_events(run_id)`, `query_agent_run_mission_events(...)`, `get_agent_run_telemetry(run_id)`, and `query_agent_run_telemetry(...)` for canonical checkpoint, mission-event, and telemetry inspection
14. `resume_agent_run(run_id)`, `approve_agent_run(run_id)`, or `cancel_agent_run(run_id)` for explicit transitions

These tools mirror the same deterministic utility-model and agent-run surfaces exposed by the API and SDKs. `list_models()` also surfaces routed target, failover, timeout, aggregate provider-auth metadata, and capability-specific chat/embedding auth-header readiness for provider-backed catalog entries. They do not pretend to be provider-backed generative chat tools.

## Deployment control-plane flow

MCP now also exposes the deployment operator lane:

1. `list_deployment_regions()`
2. `get_deployment()`
3. `get_deployment_cost(deployment_id)` when a deployment exists
4. `create_deployment(...)` / `delete_deployment(...)` for explicit control-plane mutations

That keeps deployment discovery and current-cost inspection aligned with the same API contract the CLI and SDKs use.

## Team and execution-policy flow

MCP also exposes the current operator read/write control-plane lane for billing, team governance, and execution safety:

1. `update_me(name=..., org_name=...)`
2. `list_distributions()`
3. `list_templates()`
4. `list_team_members()`
5. `invite_team_member(email=..., role=...)`
6. `update_team_member_role(user_id=..., role=...)`
7. `remove_team_member(user_id=...)`
8. `get_billing_info()`
9. `create_billing_checkout(plan=...)`
10. `create_billing_portal()`
11. `refresh_credits(device_id=..., billing_period=..., credits_used=...)`
12. `ingest_metering_events(device_id=..., events=[...])`
13. `list_devices()`
14. `revoke_device(registration_id=...)`
15. `get_audit_logs()`
16. `get_audit_log_artifacts()`
17. `get_execution_policy()`
18. `list_execution_policy_snapshots()`
19. `update_execution_policy(...)`

That keeps the distribution catalog, template catalog, billing state, local metering ingestion, team roster, registered-device inventory, audit trail, and autonomous execution thresholds and snapshot history aligned with the same API contract the CLI uses.

## Repository intelligence flow

For the governed repository lane, use:

1. `create_repository_snapshot(...)` to pin one immutable repository snapshot
2. `triage_repository(...)` to build one bounded workspace evidence bundle
3. `create_repository_decision_plan(...)` to create one immutable `decision_plan_id`
4. `simulate_repository(...)` to run the repository apply gate with the stored plan
5. `apply_repository(...)` only after the gate passes or when you intentionally request `patch_only`

`create_repository_decision_plan(...)` returns repository analysis with
`generated_patch_ref`, `patch_impact_report_ref`, and planner provenance through
`repository_analysis.planner_model_id`,
`repository_analysis.planner_execution_mode`, and
`repository_analysis.planner_provider_backend`.

When the local stack sets
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`, MCP
surfaces the bounded deterministic local planner instead of a provider-backed
planner. The explicit local planner model id is
`repository.deterministic_local_v1`. Unsupported evidence bundles fail closed with
`repository_local_planner_unsupported`.

## Mission functionality mapping

If you are porting a Mission workflow onto MCP, use the tool mapping below
instead of assuming there is a one-to-one tool for every Mission helper.

| Mission functionality | MCP tool here | Notes |
| --- | --- | --- |
| `list_data` | `list_data(search=..., compact=true)` | Low-token governed dataset discovery. |
| `get_data_schema` | `get_data_summary(dataset_id=...)` or `get_data_schema(dataset_id=...)` | Use summary first. |
| `ensure_governed_dataset` | `connect_data(...)` | Resend with `connection_id` plus `selection` when status is `needs_selection`. |
| `query_data` | `query_data(...)` | Governed exact metric/query tool. |
| `query_data_batch` | `query_batch(...)` | Multi-metric governed exact query tool. |
| `query_sql_report` | `query_sql_report(...)` | Read-only SQL rowset tool. |
| `query_sql_source` | No one-to-one MCP tool today. Use `query_data(...)` or `query_sql_report(...)`. | Do not look for a separate SQL-source tool. |
| `get_sources_graph` | No one-to-one MCP tool today. | Discover datasets and send the exact governed query or SQL report request directly. |
| `map_data_sources` | No one-to-one MCP tool today. | Resolve dataset ids and source names through `list_data` and `get_data_summary`. |
| `register_sql_source` | No one-to-one MCP tool today. | Use `query_sql_report(...)` for one-off SQL or `connect_data(...)` for a persistent governed dataset. |
| `get_algenta_library_health` | No one-to-one MCP tool today. | Health remains visible through the CLI/SDK local runtime surfaces. |
| `list_algenta_libraries` | `list_runtime_libraries(search=...)` | Local/runtime-backed only. |
| `inspect_algenta_library` | `list_runtime_libraries(search="text.tokenizer")` | Search by canonical dotted module name. |
| `get_algenta_library_module` | `list_runtime_libraries(search="text.tokenizer")` | MCP exposes inventory, not a persistent module-proxy object. |
| `execute_algenta_library` | `execute_runtime_library(module="rerank_eval", function="precision_at_k", args={...})` | Local/runtime-backed deterministic compute only. |

The machine-readable version of the same map lives at:

- [`mission_functionality_surface_map.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mission_functionality_surface_map.json)

## Product guidance

MCP is a first-class supported integration surface, but it is not the only product narrative. The API and SDK surfaces still expose `resolve -> verify -> query`, while MCP centers the discovery-first tool flow above.

## When to use MCP

Use MCP when:

- you are integrating Algenta into an agent workflow
- you want structured tool calling
- you want the runtime surfaces available to agent systems without inventing ad hoc wrappers

## Important boundary

- `query_data` is for one governed exact query
- `get_contract` is the machine-readable contract discovery tool
- `query_batch` is for several governed exact queries with ordered keyed results
- `query_sql_report` is a separate read-only SQL rowset surface, not metric inference
- `list_models`, `tokenize`, `count_tokens`, `chat_completions`, `responses`, `embeddings`, `embedding_similarity`, and `rerank` are deterministic utility-model tools
- `product_decision`, `product_agent_run`, `product_optimize`, `product_retrieve`, and `product_forecast` are the business-facing simplified product tools
- `recommend`, `score`, `batch`, and `compare` are the decision-runtime helper tools
- `submit_job`, `list_jobs`, `get_job_status`, `poll_job`, `get_job_result`, `cancel_job`, and `test_webhook_delivery` are the async simulation job tools
- `register_trigger`, `list_triggers`, `fire_trigger`, `pause_trigger`, and `delete_trigger` are the trigger automation tools
- `plan_decision` is the DecisionPlan-only planning surface
- `log_decision`, `list_decisions`, `get_decision`, `record_outcome`, `execute_decision`, and `delete_decision` are the persisted decision-memory tools
- `create_agent_run`, `list_agent_runs`, `get_agent_run`, `get_agent_run_events`, `get_agent_run_checkpoints`, `query_agent_run_checkpoints`, `get_agent_run_mission_events`, `query_agent_run_mission_events`, `get_agent_run_telemetry`, `query_agent_run_telemetry`, `resume_agent_run`, `approve_agent_run`, and `cancel_agent_run` are the persisted agent lifecycle tools
- `update_me`, `list_distributions`, `list_templates`, `list_team_members`, `invite_team_member`, `update_team_member_role`, `remove_team_member`, `get_billing_info`, `create_billing_checkout`, `create_billing_portal`, `refresh_credits`, `ingest_metering_events`, `list_devices`, `revoke_device`, `get_audit_logs`, `get_audit_log_artifacts`, `get_execution_policy`, `list_execution_policy_snapshots`, and `update_execution_policy` are the account, billing, team, device, metering, and execution-policy control-plane tools
- `list_deployment_regions`, `get_deployment`, `get_deployment_cost`, `create_deployment`, and `delete_deployment` are the deployment control-plane tools
- `list_connectors`, `create_connector`, `get_connector`, `update_connector`, `test_connector`, `preview_test_connector`, `browse_connector`, `preview_browse_connector`, and `delete_connector` are the saved and inline-preview connector lifecycle tools
- `create_repository_snapshot`, `get_repository_snapshot`, `triage_repository`, `create_repository_decision_plan`, `simulate_repository`, and `apply_repository` are the governed repository-intelligence tools
- `list_runtime_libraries` / `execute_runtime_library` are the local/runtime-backed compute tools
- the API still exposes `/v1/resolve` and `/v1/verify`, but those are not separate MCP tools in this repo
