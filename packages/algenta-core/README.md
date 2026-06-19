# algenta-core

High-level Algenta runtime SDK for governed data/query flows, local runtime control, and local Mojo libraries.

## Install

For pure local runtime work only:

```bash
pip install algenta-core
```

For hosted API-backed runtime mode from a published package index:

```bash
pip install "algenta-core[cloud]"
```

`Runtime(mode="api")` and `Runtime(mode="self_hosted")` intentionally fail
closed if `algenta-sdk` is not installed.

If you are validating unpublished local artifacts, install the local
`algenta-sdk` and `algenta-core` artifacts together instead of assuming the
`[cloud]` extra can resolve an unpublished `algenta-sdk` from a package index.

## Root Contract Exports

```python
from algenta import DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT

print(DEFAULT_BASE_URL)
print(PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"])
print(PRIMARY_DATA_QUERY_CONTRACT["runtime_sdk"]["python"]["query_batch_method"])
print(PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["operators"]["scalar"])
```

## Unified Capability Plane

```python
route = rt.route_capabilities(
    {
        "objective": "Investigate the latest checkout incident and route me to the right specialist path.",
        "kinds": ["dataset", "skill", "mcp_tool", "runtime_library"],
        "artifact_affinities": ["incident"],
        "tags": ["incident", "triage"],
    }
)

capability = rt.get_capability(route.selected_capability_id, include_instruction=True)
execution = rt.execute_capability(
    {
        "capability_id": route.selected_capability_id,
        "binding_id": route.selected_binding_id,
        "input": {
            "objective": "Investigate the latest checkout incident and route me to the right specialist path.",
            "requested_output": "instruction_bundle",
        },
    }
)

providers = rt.list_capability_providers()
skills = rt.list_skills()
mcp_providers = rt.list_mcp_providers()
```

For `Runtime(mode="local")`, register customer-owned execution handlers with
`rt.register_capability_adapter(adapter)` when a selected capability is
`client_managed`. Local runtime execution fails closed for `algenta_managed`
capabilities: they remain discoverable and routable, but execution must go
through `Runtime(mode="api")` or `Runtime(mode="self_hosted")`. Checked-in
request artifacts and runnable examples live in `examples/capability-plane/`
and `examples/langgraph/capability_router.py`.

## Governed Runtime Flow

```python
import os

from algenta import QueryFilterCondition, QueryFilterSpec, Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(
    mode="self_hosted",
    api_key=api_key,
    base_url="http://localhost:8000",
)

datasets = rt.list_datasets(search="orders", compact=True)
contract = rt.get_contract()
summary = rt.get_dataset_summary(datasets.datasets[0].dataset_id)
completed_orders = QueryFilterSpec(
    time_filter="last_year",
    conditions=(
        QueryFilterCondition(dimension_hint="status", op="eq", value="completed"),
    ),
)

query = rt.query_with_metadata(
    {
        "dataset_id": summary.dataset_id,
        "filter": completed_orders.to_dict(),
        "metric": {"hint": "gross_revenue"},
        "aggregation": "sum",
    }
)

batch = rt.query_batch(
    {
        "defaults": {
            "dataset_id": summary.dataset_id,
            "filter": completed_orders.to_dict(),
        },
        "queries": [
            {
                "key": "completed_orders",
                "request": {
                    "metric": {"hint": "order_count"},
                    "aggregation": "sum",
                },
            },
            {
                "key": "monthly_completed_orders",
                "request": {
                    "metric": {"hint": "order_count"},
                    "aggregation": "sum",
                    "group_by": ["order_month"],
                    "limit": 12,
                    "order": "desc",
                },
            },
        ],
    }
)

report = rt.query_sql_report(
    {
        "sources": [{"dataset_id": summary.dataset_id, "alias": "orders"}],
        "sql": "SELECT order_month, gross_revenue FROM orders ORDER BY order_month DESC LIMIT 12",
        "max_rows": 100,
    }
)
```

## Hosted Connector + Refreshable Dataset Flow

```python
preview_tested = rt.test_connector(
    connector={"type": "rest", "url": "https://example.test/orders.json", "data_path": "items"}
)
preview_browsed = rt.browse_connector(
    connector={"type": "rest", "url": "https://example.test/orders.json", "data_path": "items"}
)

connector = rt.create_connector(
    name="orders-rest",
    connector_type="rest",
    description="Managed REST connector for orders",
    config={"url": "https://example.test/orders.json", "data_path": "items"},
)

detail = rt.get_connector(connector.id)
updated = rt.update_connector(
    connector.id,
    description="Managed REST connector for refreshable orders",
)
tested = rt.test_connector(connector.id)
browsed = rt.browse_connector(connector.id)

created = rt.connect_data(
    connection_type="api",
    provider="rest",
    dataset_name="orders-refreshable",
    description="Refreshable orders dataset",
    connection_config={"url": "https://example.test/orders.json", "data_path": "items"},
)

refreshed = rt.refresh_dataset(created.dataset_id)
dataset = rt.get_dataset(created.dataset_id)

rt.delete_dataset(created.dataset_id)
rt.delete_connector(connector.id)
```

`Runtime.query()` remains available and unchanged when you only need the governed query body.

Use Cloud Managed URLs only with `Runtime(mode="api")`. `Runtime(mode="self_hosted")`
and private profiles must point `base_url` at your own self-hosted service and
fail closed instead of silently falling back to Codna cloud.

`rt.get_contract()` also handles older self-hosted nodes that still return
`404` for `/v1/meta/contract` by falling back to `/openapi.json` and reading
`x-primary-data-query-contract`.

For formal runtime-proof surfaces, the runtime also exposes:

- `rt.get_runtime_manifest()`
- `rt.get_runtime_modules()`
- `rt.get_runtime_benchmarks()`
- `rt.get_runtime_release_validation()`

For the current plan-aligned utility and agent surfaces, the runtime also exposes:

- `rt.list_models()`
- `rt.resolve_artifact_bridge(repo_id=..., filename=..., revision=..., local_files_only=True)`
- `rt.tokenize(text, model="text.tokenizer")`
- `rt.count_tokens(text, model="text.tokenizer")`
- `rt.chat_completions(messages, model="text.tokenizer")`
- `rt.stream_chat_completions(messages, model="text.tokenizer")`
- `rt.responses(input_value, model="text.tokenizer", dimensions=64)`
- `rt.stream_responses(input_value, model="text.tokenizer", dimensions=64)`
- `rt.embeddings(input_value, model="text.hash_embedding_v1", dimensions=64)`
- `rt.embedding_similarity(left, right, model="embeddings.cosine_similarity")`
- `rt.rerank(query_embedding, documents, model="embeddings.cosine_similarity", top_n=...)`
- `rt.plan_decision(request)`
- `rt.log_decision(request)`
- `rt.list_decisions(page=..., limit=..., with_outcome_only=...)`
- `rt.get_decision(decision_id)`
- `rt.record_outcome(decision_id, actual_outcome=..., outcome_notes=...)`
- `rt.execute_decision(decision_id, webhook_url=..., timeout_seconds=...)`
- `rt.delete_decision(decision_id)`
- `rt.get_billing_info()`
- `rt.create_billing_checkout(plan="developer" | "pro")`
- `rt.create_billing_portal()`
- `rt.refresh_credits(device_id=..., billing_period="YYYY-MM", credits_used=...)`
- `rt.ingest_metering_events(device_id=..., events=[...])`
- `rt.submit_job(request, callback_url=...)`
- `rt.get_job(job_id)`
- `rt.get_job_result(job_id)`
- `rt.list_jobs(page=..., limit=..., status=...)`
- `rt.cancel_job(job_id)`
- `rt.poll_job(job_id, timeout=..., poll_interval=...)`
- `rt.test_webhook_delivery(callback_url)`
- `rt.register_trigger(name=..., condition=..., simulation_template=..., webhook_url=..., execution_webhook_url=..., auto_execute=..., description=...)`
- `rt.list_triggers(status="all", page=..., limit=...)`
- `rt.fire_trigger(trigger_id, force=False)`
- `rt.pause_trigger(trigger_id, paused=True | False)`
- `rt.delete_trigger(trigger_id)`
- `rt.update_me(name="Mission Ops", org_name="Mission Control")`
- `rt.distributions()`
- `rt.templates()`
- `rt.invite_team_member(email=..., role="member")`
- `rt.update_team_member_role(user_id, role="viewer")`
- `rt.remove_team_member(user_id)`
- `rt.create_agent_run(task=..., approval_mode=..., ...)`
- `rt.get_agent_run(run_id)`
- `rt.get_agent_run_events(run_id, limit=...)`
- `rt.stream_agent_run_events(run_id, limit=...)`
- `rt.list_agent_runs(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=...)`
- `rt.list_agent_run_checkpoints(run_id)`
- `rt.query_agent_run_checkpoints(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., checkpoint_id=...)`
- `rt.list_agent_run_mission_events(run_id, limit=...)`
- `rt.query_agent_run_mission_events(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., event_type=...)`
- `rt.list_agent_run_telemetry(run_id, limit=...)`
- `rt.query_agent_run_telemetry(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., telemetry_kind=..., module_name=...)`
- `rt.replay_agent_run(run_id, checkpoint_id=...)`
- `rt.fork_agent_run(run_id, checkpoint_id=...)`
- `rt.resume_agent_run(run_id)`
- `rt.cancel_agent_run(run_id)`
- `rt.approve_agent_run(run_id)`
- `rt.create_repository_snapshot(repository_id, request)`
- `rt.get_repository_snapshot(repository_id, snapshot_id)`
- `rt.triage_repository(repository_id, request)`
- `rt.create_repository_decision_plan(repository_id, request)`
- `rt.query_repository_graph(repository_id, request)`
- `rt.simulate_repository(repository_id, request)`
- `rt.apply_repository(repository_id, request)`
- `rt.list_devices(page=..., limit=...)`
- `rt.revoke_device(registration_id)`

## Provider-Backed LLM Registry

`Runtime(mode="api")` and `AlgentaClient` use the same provider-backed model
registry configured through `ALGENTA_LLM_PROVIDER_MODELS_JSON`. Each entry must
declare `id`, `backend`, `model_name`, `base_url`, and `api_key_env` unless the
backend explicitly allows local no-auth access.
Use `model_name` as the canonical upstream model field. Legacy `upstream_model`
is still accepted for backward compatibility.
`capabilities` is optional; when omitted, the runtime defaults to the full
capability set supported by that backend.

Supported backends:

- `openai_compatible` for OpenAI-style chat-completions and embeddings endpoints
- `openai` for the native OpenAI chat/responses and embeddings surface
- `anthropic` for chat-completions only
- `ollama` for local chat-completions and embeddings, with optional `api_key_env`
- `google_genai` for Gemini chat-completions and embeddings
- `mistral` for Mistral chat-completions and embeddings
- `cohere` for Cohere V2 chat-completions and embeddings
- `groq` for Groq chat-completions
- `xai` for xAI chat-completions and embeddings
- `router` for deterministic ordered multi-provider routing over `targets`

```bash
export ALGENTA_LLM_PROVIDER_MODELS_JSON='[
  {
    "id": "provider.openai-gpt-4o-mini",
    "backend": "openai",
    "model_name": "gpt-4o-mini",
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"},
    "chat_timeout_seconds": 12.5,
    "embedding_timeout_seconds": 9.0
  },
  {
    "id": "provider.ollama-gemma3",
    "backend": "ollama",
    "model_name": "gemma3",
    "base_url": "http://127.0.0.1:11434"
  },
  {
    "id": "provider.google-gemini-flash",
    "backend": "google_genai",
    "model_name": "gemini-2.0-flash",
    "base_url": "https://generativelanguage.googleapis.com/v1beta",
    "api_key_env": "GOOGLE_API_KEY"
  },
  {
    "id": "provider.mistral-small",
    "backend": "mistral",
    "model_name": "mistral-small-latest",
    "base_url": "https://api.mistral.ai/v1",
    "api_key_env": "MISTRAL_API_KEY"
  },
  {
    "id": "provider.command-a",
    "backend": "cohere",
    "model_name": "command-a-03-2025",
    "base_url": "https://api.cohere.com",
    "api_key_env": "COHERE_API_KEY"
  },
  {
    "id": "provider.groq-llama",
    "backend": "groq",
    "model_name": "llama-3.3-70b-versatile",
    "base_url": "https://api.groq.com/openai/v1",
    "api_key_env": "GROQ_API_KEY"
  },
  {
    "id": "provider.xai-grok",
    "backend": "xai",
    "model_name": "grok-4.3",
    "base_url": "https://api.x.ai/v1",
    "api_key_env": "XAI_API_KEY"
  },
  {
    "id": "provider.router-fast-chat",
    "backend": "router",
    "capabilities": ["chat_completions"],
    "targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"],
    "fallback_policy": "retryable_only",
    "fallback_on": ["provider_rate_limited", "provider_timeout"],
    "timeout_seconds": 18.0,
    "max_attempts": 2
  },
  {
    "id": "provider.router-split",
    "backend": "router",
    "capabilities": ["chat_completions", "embeddings"],
    "chat_targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"],
    "embedding_targets": ["provider.openai-gpt-4o-mini"],
    "chat_fallback_policy": "retryable_only",
    "chat_fallback_on": ["provider_rate_limited"],
    "embedding_fallback_policy": "disabled",
    "embedding_fallback_on": ["provider_backend_error"],
    "chat_max_attempts": 2,
    "embedding_max_attempts": 1
  }
]'
```

Once registered, provider-backed models appear in `rt.list_models()` and can be
used through `rt.chat_completions(...)`, `rt.responses(...)`, and
`rt.embeddings(...)` when that backend supports the requested capability.
Router entries omit transport fields and fail over across ordered `targets`
only when a target returns retryable provider transport/backend errors.
Use `chat_targets` and `embedding_targets` when chat and embeddings should route
through different ordered provider lists. Use shared `fallback_policy` to govern
all routed capabilities, or `chat_fallback_policy` / `embedding_fallback_policy`
to override failover behavior per capability. Use shared `fallback_on`, or
`chat_fallback_on` / `embedding_fallback_on`, to restrict which retryable
provider error codes may trigger failover. Use shared `max_attempts` to cap the
routed attempt budget across all capabilities, or `chat_max_attempts` /
`embedding_max_attempts` to bound retries per capability. Use shared
`timeout_seconds`, or `chat_timeout_seconds` / `embedding_timeout_seconds`, to
set provider HTTP timeouts; router aliases can use the same fields to override
the timeout budget applied to their routed targets. Use `header_envs` to require
additional upstream headers from environment variables; `list_models()` exposes
only the required header names under `required_provider_headers`. The same
catalog entry also exposes `chat_required_provider_headers`,
`embedding_required_provider_headers`, `chat_provider_auth_env_vars`,
`embedding_provider_auth_env_vars`, `chat_provider_auth_configured`,
`embedding_provider_auth_configured`, plus the aggregate
`provider_auth_env_vars` and `provider_auth_configured`, so self-hosted
deployments can verify the full provider auth contract without leaking secret
values. Router-backed entries also expose `resolved_routing_targets`,
`resolved_chat_routing_targets`, and `resolved_embedding_routing_targets` so the
catalog shows the flattened leaf providers that execution can actually select.

The governed filter model is a **record-filter contract** over normalized rows,
not SQL. The same `QueryFilterCondition` / `QueryFilterSpec` payload works for
SQL-backed datasets, Redis snapshots, files, and other non-SQL sources after
normalization. The machine-readable operator families and validation rules are
published under `PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]`.

## Runtime Methods

- `list_connectors(page=..., limit=...)`
- `create_connector(name=..., connector_type=..., description=..., config={...})`
- `get_connector(connector_id)`
- `update_connector(connector_id, description=..., config={...})`
- `test_connector(connector_id | connector={...})`
- `browse_connector(connector_id | connector={...})`
- `delete_connector(connector_id)`
- `connect_data(request | **kwargs)`
- `list_datasets(search=..., status=..., source_name=..., page=..., limit=..., compact=True)`
- `get_dataset(dataset_id)`
- `get_contract()`
- `get_runtime_manifest()`
- `get_runtime_modules()`
- `get_runtime_benchmarks()`
- `get_runtime_release_validation()`
- `list_models()`
- `resolve_artifact_bridge(repo_id=..., filename=..., revision=..., local_files_only=True)`
- `tokenize(text, model="text.tokenizer")`
- `count_tokens(text, model="text.tokenizer")`
- `chat_completions(messages, model="text.tokenizer")`
- `stream_chat_completions(messages, model="text.tokenizer")`
- `responses(input_value, model="text.tokenizer", dimensions=64)`
- `stream_responses(input_value, model="text.tokenizer", dimensions=64)`
- `embeddings(input_value, model="text.hash_embedding_v1", dimensions=64)`
- `embedding_similarity(left, right, model="embeddings.cosine_similarity")`
- `rerank(query_embedding, documents, model="embeddings.cosine_similarity", top_n=...)`
- `plan_decision(request)`
- `log_decision(request)`
- `list_decisions(page=..., limit=..., with_outcome_only=...)`
- `get_decision(decision_id)`
- `record_outcome(decision_id, actual_outcome=..., outcome_notes=...)`
- `execute_decision(decision_id, webhook_url=..., timeout_seconds=...)`
- `delete_decision(decision_id)`
- `create_agent_run(task=..., approval_mode=..., ...)`
- `get_agent_run(run_id)`
- `get_agent_run_events(run_id, limit=...)`
- `stream_agent_run_events(run_id, limit=...)`
- `resume_agent_run(run_id)`
- `cancel_agent_run(run_id)`
- `approve_agent_run(run_id)`
- `submit_job(request, callback_url=...)`
- `get_job(job_id)`
- `get_job_result(job_id)`
- `list_jobs(page=..., limit=..., status=...)`
- `cancel_job(job_id)`
- `poll_job(job_id, timeout=..., poll_interval=...)`
- `test_webhook_delivery(callback_url)`
- `register_trigger(name=..., condition=..., simulation_template=..., webhook_url=..., execution_webhook_url=..., auto_execute=..., description=...)`
- `list_triggers(status="all", page=..., limit=...)`
- `fire_trigger(trigger_id, force=False)`
- `pause_trigger(trigger_id, paused=True | False)`
- `delete_trigger(trigger_id)`
- `distributions()`
- `templates()`
- `get_audit_logs(page=..., limit=..., actor_email=..., action=..., resource_type=..., result=..., policy_snapshot_id=..., schema_snapshot_id=..., manifest_version=..., request_hash=...)`
- `get_audit_log_artifacts(page=..., limit=..., actor_email=..., action=..., resource_type=..., result=..., policy_snapshot_id=..., schema_snapshot_id=..., manifest_version=..., request_hash=..., content_hash=...)`
- `list_execution_policy_snapshots()`
- `list_devices(page=..., limit=...)`
- `revoke_device(registration_id)`
- `refresh_credits(device_id=..., billing_period="YYYY-MM", credits_used=...)`
- `ingest_metering_events(device_id=..., events=[...])`
- `get_dataset(dataset_id)`
- `get_dataset_summary(dataset_id)`
- `refresh_dataset(dataset_id)`
- `delete_dataset(dataset_id)`
- `resolve(request)`
- `verify(request)`
- `query(request)`
- `query_with_metadata(request)`
- `query_batch(request)`
- `query_sql_report(request)`
- `rt.recommend(actions, **kwargs)`
- `rt.score(request, scoring_weights=...)`
- `rt.batch(items)`
- `rt.compare(scenarios, **kwargs)`

The runtime package also exports `QueryFilterCondition` and `QueryFilterSpec`
for deterministic exact-query filters across hosted and local execution.

## Local Mojo Libraries

```python
from algenta import libraries

catalog = libraries(mode="local", auto_start_daemon=True)
print(catalog.names()[:10])
```

`libraries()` remains the local/runtime-backed Mojo surface. It is separate from
the hosted or self-hosted governed data/query API, but it can accept local
`api_key` and `base_url` when you want the local daemon to enforce a hosted
device license.

For hosted direct cloud access without the runtime facade, `AlgentaClient`
also exposes the governed contract and query helpers:
`get_contract()`, `get_runtime_manifest()`, `get_runtime_modules()`,
`get_runtime_benchmarks()`, `get_runtime_release_validation()`,
`list_connectors()`, `create_connector()`, `get_connector()`,
`update_connector()`, `test_connector()`, `preview_test_connector()`,
`browse_connector()`, `preview_browse_connector()`, `delete_connector()`,
`connect_data()`, `list_datasets()`, `get_dataset()`, `get_dataset_summary()`,
`refresh_dataset()`, `delete_dataset()`, `resolve()`, `query()`,
`query_with_metadata()`, `query_batch()`, `query_sql_report()`, and `verify()`.
It also exposes the plan-aligned utility and agent helpers:
`list_models()`, `resolve_artifact_bridge()`, `tokenize()`, `count_tokens()`, `chat_completions()`,
`stream_chat_completions()`, `responses()`, `stream_responses()`,
`embeddings()`, `embedding_similarity()`, `rerank()`, `recommend()`,
`score()`, `batch()`, `compare()`, `plan_decision()`, `log_decision()`,
`list_decisions()`, `get_decision()`, `record_outcome()`,
`execute_decision()`, `delete_decision()`, `get_audit_logs()`,
`get_audit_log_artifacts()`, `list_execution_policy_snapshots()`, and the full
`agent/runs` lifecycle, including `list_agent_runs()`,
`list_agent_run_checkpoints()`, `query_agent_run_checkpoints()`,
`list_agent_run_mission_events()`, `query_agent_run_mission_events()`,
`list_agent_run_telemetry()`, `query_agent_run_telemetry()`,
`replay_agent_run()`, `fork_agent_run()`, and `stream_agent_run_events()`, plus
`get_billing_info()`, `create_billing_checkout()`, `create_billing_portal()`,
`refresh_credits()`, `ingest_metering_events()`, `submit_job()`, `get_job()`, `get_job_result()`,
`list_jobs()`, `cancel_job()`, `poll_job()`, `test_webhook_delivery()`,
`register_trigger()`, `list_triggers()`, `fire_trigger()`, `pause_trigger()`,
`delete_trigger()`,
`update_me()`,
`invite_team_member()`, `update_team_member_role()`, `remove_team_member()`,
`list_devices()`, and `revoke_device()`, through the same direct cloud bridge.

The same runtime-backed library catalog is also available from the repo CLI and
MCP server:

```bash
de runtime manifest --format json
de runtime validate --format json
de runtime admin-modules --format json
de runtime admin-benchmarks --format json
de runtime modules --format json
de runtime functions vector_kernels.table --format json
de runtime execute rerank_eval hit_rate_at_k --args-json '[[1,0,1,1,0],5]' --format json
de llm chat chat_request.json --stream --format json
de llm responses responses_request.json --stream
de agent-runs events <run_id> --stream --format json
```

- MCP `get_runtime_manifest`
- MCP `get_runtime_modules`
- MCP `get_runtime_benchmarks`
- MCP `get_runtime_release_validation`
- MCP `list_runtime_libraries`
- MCP `execute_runtime_library`

`de runtime admin-benchmarks --format json` and MCP `get_runtime_benchmarks`
include benchmark-class `evidence_paths`, so the operator/runtime proof surface
includes concrete benchmark artifact linkage rather than only benchmark labels.
That same proof surface currently publishes quality-gate benchmark classes `B6`
checkpoint and replay overhead, `B7` MCP tool latency, `B9` RAG retrieval
quality and latency, and `B10` decision workflow completion latency, plus
quality-gate SLO budgets `mcp_call_first_party`, `decision_plan_creation`, and
`replay`.
`B10` is currently backed by the Repository Intelligence workflow artifact at
`build/repository_intelligence_benchmark.json`.

## Docs

- [Algenta core docs](https://docs.algenta.ai/core)
- [Local runtime guide](https://docs.algenta.ai/integrations/local-runtime)
