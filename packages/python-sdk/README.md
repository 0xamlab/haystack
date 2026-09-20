# algenta-sdk

**Python SDK for [Algenta](https://algenta.ai) — self-hosted building blocks for AI applications.**

Algenta is the deterministic layer developers build on — a compiled library of mathematical and
operational functions on custom Mojo kernels, with simulation, planning, memory and governance
built into the runtime. This package is the Python client for its public API: governed data
queries, simulations, decision memory, agent runs with approvals, connectors, and the capability
plane. The Algenta engine itself is proprietary; everything in this package is Apache-2.0.

## Install

```bash
pip install algenta-sdk
```

## Quickstart

The PyPI package is `algenta-sdk`; the importable module is `decision_engine`.

```python
from decision_engine import AlgentaClient

client = AlgentaClient()  # reads ALGENTA_API_KEY; defaults to https://api.algenta.ai

datasets = client.list_datasets(search="orders", compact=True)
summary = client.get_dataset_summary(datasets.datasets[0].dataset_id)
result = client.query_with_metadata(
    {
        "dataset_id": summary.dataset_id,
        "metric": {"hint": "gross_revenue"},
        "aggregation": "sum",
    }
)
print(result.data.result)
```

Self-hosted engine? Pass `base_url="http://localhost:8000"` and the API key
provisioned by your operator deployment. The `self_hosted` and `air_gapped`
deployment profiles fail closed and never silently fall back to Algenta's
cloud.

## Root Contract Exports

```python
from decision_engine import DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT

print(DEFAULT_BASE_URL)
print(PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"])
print(PRIMARY_DATA_QUERY_CONTRACT["api"]["query_batch_endpoint"])
print(PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["operators"]["scalar"])
```

## Unified Capability Plane

```python
route = client.route_capabilities(
    {
        "objective": "Investigate the latest checkout incident and route me to the right specialist path.",
        "kinds": ["dataset", "skill", "mcp_tool", "runtime_library"],
        "artifact_affinities": ["incident"],
        "tags": ["incident", "triage"],
    }
)

capability = client.get_capability(route.selected_capability_id, include_instruction=True)
execution = client.execute_capability(
    {
        "capability_id": route.selected_capability_id,
        "binding_id": route.selected_binding_id,
        "input": {
            "objective": "Investigate the latest checkout incident and route me to the right specialist path.",
            "requested_output": "instruction_bundle",
        },
    }
)

providers = client.list_capability_providers()
skills = client.list_skills()
mcp_providers = client.list_mcp_providers()
```

The direct client now exposes a single customer-agnostic capability plane over
data connectors, MCP providers, skills, native tools, and runtime libraries.
Execution ownership remains authoritative: `algenta_managed` capabilities must
execute through the Algenta service, while local runtime adapters only execute
`client_managed` capabilities and fail closed otherwise.
Checked-in request artifacts and runnable examples live in
`examples/capability-plane/` and `examples/langgraph/capability_router.py`.

## Governed Data + Query Flow

```python
import os

from decision_engine import AlgentaClient, QueryFilterCondition, QueryFilterSpec

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(
    api_key=api_key,
    base_url="https://api.algenta.ai",
)

datasets = client.list_datasets(search="orders", compact=True)
contract = client.get_contract()
summary = client.get_dataset_summary(datasets.datasets[0].dataset_id)
completed_orders = QueryFilterSpec(
    time_filter="last_year",
    conditions=[
        QueryFilterCondition(dimension_hint="status", op="eq", value="completed"),
    ],
)

query = client.query_with_metadata(
    {
        "dataset_id": summary.dataset_id,
        "filter": completed_orders.model_dump(exclude_none=True),
        "metric": {"hint": "gross_revenue"},
        "aggregation": "sum",
    }
)

batch = client.query_batch(
    {
        "defaults": {
            "dataset_id": summary.dataset_id,
            "filter": completed_orders.model_dump(exclude_none=True),
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

report = client.query_sql_report(
    {
        "sources": [{"dataset_id": summary.dataset_id, "alias": "orders"}],
        "sql": "SELECT order_month, gross_revenue FROM orders ORDER BY order_month DESC LIMIT 12",
        "max_rows": 100,
    }
)
```

## Connectors + Refreshable Dataset Flow

```python
preview_tested = client.preview_test_connector(
    connector_type="rest",
    config={"url": "https://example.test/orders.json", "data_path": "items"},
)
preview_browsed = client.preview_browse_connector(
    connector_type="rest",
    config={"url": "https://example.test/orders.json", "data_path": "items"},
)

connector = client.create_connector(
    name="orders-rest",
    connector_type="rest",
    description="Managed REST connector for orders",
    config={"url": "https://example.test/orders.json", "data_path": "items"},
)

detail = client.get_connector(connector.id)
updated = client.update_connector(
    connector.id,
    description="Managed REST connector for refreshable orders",
)
tested = client.test_connector(connector.id)
browsed = client.browse_connector(connector.id)

created = client.connect_data(
    connection_type="api",
    provider="rest",
    dataset_name="orders-refreshable",
    description="Refreshable orders dataset",
    connection_config={"url": "https://example.test/orders.json", "data_path": "items"},
)

refreshed = client.refresh_dataset(created.dataset_id)
dataset = client.get_dataset(created.dataset_id)

client.delete_dataset(created.dataset_id)
client.delete_connector(connector.id)
```

`query()` remains available and unchanged when you only need the response body.

Use `https://api.algenta.ai` only in Cloud Managed. `ALGENTA_DEPLOYMENT_MODE=self_hosted`
and `ALGENTA_DEPLOYMENT_MODE=air_gapped` must point `base_url` at your own
self-hosted service and fail closed instead of silently falling back to
Algenta cloud.

`client.get_contract()` also handles older self-hosted nodes that still return
`404` for `/v1/meta/contract` by falling back to `/openapi.json` and reading
`x-primary-data-query-contract`.

For formal runtime-proof surfaces, the client also exposes:

- `client.get_runtime_manifest()`
- `client.get_runtime_modules()`
- `client.get_runtime_benchmarks()`
- `client.get_runtime_release_validation()`

`client.get_runtime_benchmarks()` includes benchmark-class `evidence_paths`, so
the typed runtime-proof surface carries concrete benchmark artifact linkage
instead of only benchmark codes and descriptions.
It currently publishes quality-gate benchmark classes `B6` checkpoint and
replay overhead, `B7` MCP tool latency, `B9` RAG retrieval quality and
latency, and `B10` decision workflow completion latency, plus quality-gate SLO
budgets `mcp_call_first_party`, `decision_plan_creation`, and `replay`.
`B10` is currently backed by the engine's Repository Intelligence workflow
benchmark.

For the current plan-aligned utility and agent surfaces, the direct client also exposes:

- `client.list_models()`
- `client.resolve_artifact_bridge(repo_id=..., filename=..., revision=..., local_files_only=True)`
- `client.tokenize(text, model="text.tokenizer")`
- `client.count_tokens(text, model="text.tokenizer")`
- `client.chat_completions(messages, model="text.tokenizer")`
- `client.stream_chat_completions(messages, model="text.tokenizer")`
- `client.responses(input_value, model="text.tokenizer", dimensions=64)`
- `client.stream_responses(input_value, model="text.tokenizer", dimensions=64)`
- `client.embeddings(input_value, model="text.hash_embedding_v1", dimensions=64)`
- `client.embedding_similarity(left, right, model="embeddings.cosine_similarity")`
- `client.rerank(query_embedding, documents, model="embeddings.cosine_similarity", top_n=...)`
- `client.plan_decision(request)`
- `client.log_decision(request)`
- `client.list_decisions(page=..., limit=..., with_outcome_only=...)`
- `client.get_decision(decision_id)`
- `client.record_outcome(decision_id, actual_outcome=..., outcome_notes=...)`
- `client.execute_decision(decision_id, webhook_url=..., timeout_seconds=...)`
- `client.delete_decision(decision_id)`
- `client.create_agent_run(task=..., approval_mode=..., ...)`
- `client.get_agent_run(run_id)`
- `client.list_agent_runs(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=...)`
- `client.get_agent_run_events(run_id, limit=...)`
- `client.stream_agent_run_events(run_id, limit=...)`
- `client.list_agent_run_checkpoints(run_id)`
- `client.query_agent_run_checkpoints(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., checkpoint_id=...)`
- `client.list_agent_run_mission_events(run_id, limit=...)`
- `client.query_agent_run_mission_events(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., event_type=...)`
- `client.list_agent_run_telemetry(run_id, limit=...)`
- `client.query_agent_run_telemetry(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., telemetry_kind=..., module_name=...)`
- `client.replay_agent_run(run_id, checkpoint_id=...)`
- `client.fork_agent_run(run_id, checkpoint_id=...)`
- `client.resume_agent_run(run_id)`
- `client.cancel_agent_run(run_id)`
- `client.approve_agent_run(run_id)`
- `client.submit_job(request, callback_url=...)`
- `client.get_job(job_id)`
- `client.get_job_result(job_id)`
- `client.list_jobs(page=..., limit=..., status=...)`
- `client.cancel_job(job_id)`
- `client.poll_job(job_id, timeout=..., poll_interval=...)`
- `client.test_webhook_delivery(callback_url)`
- `client.create_repository_snapshot(repository_id, request)`
- `client.get_repository_snapshot(repository_id, snapshot_id)`
- `client.triage_repository(repository_id, request)`
- `client.create_repository_decision_plan(repository_id, request)`
- `client.query_repository_graph(repository_id, request)`
- `client.simulate_repository(repository_id, request)`
- `client.apply_repository(repository_id, request)`

For a fully local self-hosted repository planner, set
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`.
That planner is explicit and bounded; it currently supports deterministic
Python return-literal mismatch repairs and fails closed with
`repository_local_planner_unsupported` outside that contract.

Every stored repository `DecisionPlan` records planner provenance in
`decision_plan.repository_analysis` through `planner_model_id`,
`planner_execution_mode`, and `planner_provider_backend`.
- `client.register_trigger(name=..., condition=..., simulation_template=..., webhook_url=..., execution_webhook_url=..., auto_execute=..., description=...)`
- `client.list_triggers(status="all", page=..., limit=...)`
- `client.fire_trigger(trigger_id, force=False)`
- `client.pause_trigger(trigger_id, paused=True | False)`
- `client.delete_trigger(trigger_id)`

## Provider-Backed LLM Registry

Provider-backed LLM models are configured through `ALGENTA_LLM_PROVIDER_MODELS_JSON`.
Each entry must declare `id`, `backend`, `model_name`, `base_url`, and `api_key_env`
unless the backend explicitly allows local no-auth access.
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
    "id": "provider.anthropic-sonnet",
    "backend": "anthropic",
    "model_name": "claude-3-5-sonnet-latest",
    "base_url": "https://api.anthropic.com/v1",
    "api_key_env": "ANTHROPIC_API_KEY"
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

Once registered, provider-backed models appear in `client.list_models()` and can
be used through `client.chat_completions(...)`, `client.responses(...)`, and
`client.embeddings(...)` when that backend supports the requested capability.
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
not SQL. Use `QueryFilterCondition` / `QueryFilterSpec` for deterministic exact
slices that also stay valid for Redis and other non-SQL sources. The
machine-readable operator families and validation rules are published under
`PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]`.

## Direct Client Methods

- `list_datasets(search=..., status=..., source_name=..., page=..., limit=..., compact=True)`
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
- `get_billing_info()`
- `create_billing_checkout(plan="developer" | "pro")`
- `create_billing_portal()`
- `refresh_credits(device_id=..., billing_period="YYYY-MM", credits_used=...)`
- `ingest_metering_events(device_id=..., events=[...])`
- `update_me(name="Mission Ops", org_name="Mission Control")`
- `distributions()`
- `templates()`
- `invite_team_member(email=..., role="member")`
- `update_team_member_role(user_id, role="viewer")`
- `remove_team_member(user_id)`
- `get_audit_logs(page=..., limit=..., actor_email=..., action=..., resource_type=..., result=..., policy_snapshot_id=..., schema_snapshot_id=..., manifest_version=..., request_hash=...)`
- `get_audit_log_artifacts(page=..., limit=..., actor_email=..., action=..., resource_type=..., result=..., policy_snapshot_id=..., schema_snapshot_id=..., manifest_version=..., request_hash=..., content_hash=...)`
- `list_execution_policy_snapshots()`
- `create_agent_run(task=..., approval_mode=..., ...)`
- `get_agent_run(run_id)`
- `get_agent_run_events(run_id, limit=...)`
- `stream_agent_run_events(run_id, limit=...)`
- `list_agent_runs(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=...)`
- `list_agent_run_checkpoints(run_id)`
- `query_agent_run_checkpoints(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., checkpoint_id=...)`
- `list_agent_run_mission_events(run_id, limit=...)`
- `query_agent_run_mission_events(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., event_type=...)`
- `list_agent_run_telemetry(run_id, limit=...)`
- `query_agent_run_telemetry(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., telemetry_kind=..., module_name=...)`
- `replay_agent_run(run_id, checkpoint_id=...)`
- `fork_agent_run(run_id, checkpoint_id=...)`
- `resume_agent_run(run_id)`
- `cancel_agent_run(run_id)`
- `approve_agent_run(run_id)`
- `list_devices(page=..., limit=...)`
- `revoke_device(registration_id)`
- `list_connectors(page=..., limit=...)`
- `create_connector(name=..., connector_type=..., description=..., config={...})`
- `get_connector(connector_id)`
- `update_connector(connector_id, description=..., config={...})`
- `test_connector(connector_id)`
- `browse_connector(connector_id)`
- `delete_connector(connector_id)`
- `preview_test_connector(connector={...})`
- `preview_browse_connector(connector={...})`
- `connect_data(connection_type=..., provider=..., dataset_name=..., description=..., connection_config={...})`
- `get_dataset(dataset_id)`
- `get_dataset_summary(dataset_id)`
- `refresh_dataset(dataset_id)`
- `delete_dataset(dataset_id)`
- `query_with_metadata(request)`
- `query_batch(request)`
- `query_sql_report(request)`
- `simulate(...)`

The public Python package also exports `QueryFilterCondition` and
`QueryFilterSpec` so callers can build deterministic filter payloads without
hand-rolling ad hoc dictionaries.

## Docs

- [Algenta docs](https://docs.algenta.ai)
- [Direct API client guide](https://docs.algenta.ai/direct-api-client)
