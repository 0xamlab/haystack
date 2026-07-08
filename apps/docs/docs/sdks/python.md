---
sidebar_position: 1
slug: /sdks/python
---

# Python SDK

Use the Python SDK after the service is already running.

Start with [Quickstart](/quickstart), then authenticate with [API Authentication](/api-reference/authentication).

## Install

```bash
pip install algenta-sdk
```

## API keys

```python
import os

from decision_engine import AlgentaClient

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(
    api_key=api_key,
    base_url="http://localhost:8000",
)

created = client.create_api_key(
    label="mission-runtime",
    expires_at="2028-05-19T00:00:00Z",
    device_limit=3,
)

print(created["raw_key"])
print(created["key_prefix"])
print(created["device_limit"])
print(created["expires_at"])
```

The `raw_key` value is returned only once on creation. Store it, along with
`id`, `key_prefix`, `device_limit`, and `expires_at`, before revoking or
rotating the previous key.

## Provider-backed LLM models

Configure provider-backed models through `ALGENTA_LLM_PROVIDER_MODELS_JSON`.
Each entry must declare `id`, `backend`, `model_name`, `base_url`, and
`api_key_env` unless the backend explicitly allows local no-auth access.
Use `model_name` as the canonical upstream model field. Legacy `upstream_model`
is still accepted for backward compatibility.
`capabilities` is optional; when omitted, the runtime defaults to the full
capability set supported by that backend.

**Dynamic discovery (no static model list):** set `model_name` to `"*"` and the
engine queries that backend's own list-models API for the models it *currently*
offers, instead of a hardcoded name. `GET /v1/models` then lists one live entry
per discovered model as `<id>:<model>` (e.g. `provider.openai:gpt-5`), and a
chat/embeddings request to that id routes to the backend with that model as the
upstream. Discovery is egress-guarded and cached (TTL `ALGENTA_LLM_DISCOVERY_TTL_SECONDS`,
default 600s); a provider hiccup degrades to "no discovered models" for that entry,
never an error. Example: `{"id": "provider.openai", "backend": "openai",
"model_name": "*", "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"}`.

Supported backends:

- `openai_compatible`
- `openai`
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

After registration, use `client.list_models()` to verify the catalog and route
requests through `client.chat_completions(...)`, `client.responses(...)`, or
`client.embeddings(...)` when the selected backend supports that capability.
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

If you set an explicit `device_limit`, that cap also applies to ordinary hosted
API traffic for the key. The Python SDK sends the stable device headers
automatically, including device ID, platform, and hostname hash, and persists
the hosted device binding token for repeated same-device requests. Set
`ALGENTA_DEVICE_ID` or `DE_DEVICE_ID` only when you need a deterministic
service identity across restarts.

## Simulate

```python
import os

from decision_engine import AlgentaClient

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(
    api_key=api_key,
    base_url="http://localhost:8000",
)

result = client.simulate(
    mode="auto",
    scenario={
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost": {"low": 30000, "high": 90000},
        },
        "objective": "maximize_net_value",
    },
    runs=10000,
    seed=42,
)

print(result.recommended_action)
```

## Async jobs

```python
import os

from decision_engine import AlgentaClient

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(
    api_key=api_key,
    base_url="http://localhost:8000",
)

job = client.submit_job(
    mode="auto",
    scenario={
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost": {"low": 30000, "high": 90000},
        },
        "objective": "maximize_net_value",
    },
    runs=10000,
    seed=42,
)

status = client.get_job(job.job_id)
if status.status == "completed":
    result = client.get_job_result(job.job_id)
    print(result)
elif status.status in {"queued", "running"}:
    result = client.poll_job(job.job_id, timeout=60.0, poll_interval=2.0)
    print(result)
else:
    client.cancel_job(job.job_id)

webhook = client.test_webhook_delivery("https://example.test/webhook")
print(webhook["status_code"], webhook["message"])

trigger = client.register_trigger(
    name="Revenue alert",
    condition={
        "source_id": "src_orders",
        "metric_hint": "revenue",
        "threshold": 200000,
        "direction": "above",
        "aggregation": "sum",
    },
    simulation_template={
        "mode": "auto",
        "scenario": {
            "variables": {"revenue": {"low": 100000, "high": 250000}},
            "objective": "maximize_net_value",
        },
    },
)
paused = client.pause_trigger(trigger.trigger_id, paused=True)
print(paused.status)
```

## Discovery and governed query helpers

```python
import os

from decision_engine import AlgentaClient, QueryFilterCondition, QueryFilterSpec

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(
    api_key=api_key,
    base_url="http://localhost:8000",
)

datasets = client.list_datasets(
    search="orders",
    status="ready",
    source_name="warehouse_postgres",
    compact=True,
)
summary = client.get_dataset_summary(datasets.datasets[0].dataset_id)
completed_orders = QueryFilterSpec(
    time_filter="last_year",
    conditions=[
        QueryFilterCondition(dimension_hint="status", op="eq", value="completed"),
    ],
)

query = client.query_with_metadata(
    {
        "dataset_id": datasets.datasets[0].dataset_id,
        "filter": completed_orders.model_dump(exclude_none=True),
        "metric": {"role": "metric", "hint": "gross_revenue"},
        "aggregation": "sum",
    }
)

batch = client.query_batch(
    {
        "defaults": {
            "dataset_id": datasets.datasets[0].dataset_id,
            "filter": completed_orders.model_dump(exclude_none=True),
        },
        "queries": [
            {"key": "completed_orders", "request": {"metric": {"role": "metric", "hint": "order_count"}, "aggregation": "sum"}},
            {"key": "monthly_completed_orders", "request": {"metric": {"role": "metric", "hint": "order_count"}, "aggregation": "sum", "group_by": ["order_month"], "limit": 12, "order": "desc"}},
        ],
    }
)

report = client.query_sql_report(
    {
        "sources": [{"dataset_id": datasets.datasets[0].dataset_id, "alias": "orders"}],
        "sql": "select order_month, gross_revenue from orders",
        "max_rows": 100,
    }
)

preview_test = client.preview_test_connector(
    connector={"type": "rest", "url": "https://example.test/orders.json", "data_path": "items"}
)
preview_browse = client.preview_browse_connector(
    connector={"type": "rest", "url": "https://example.test/orders.json", "data_path": "items"}
)

print(preview_test["status"])
print(preview_browse["items"][:1])

connector = client.create_connector(
    name="orders-rest",
    connector_type="rest",
    description="Managed REST connector for orders",
    config={"url": "https://example.test/orders.json", "data_path": "items"},
)
tested = client.test_connector(connector.id)
browsed = client.browse_connector(connector.id)
updated = client.update_connector(
    connector.id,
    description="Managed REST connector for refreshable orders",
)

created = client.connect_data(
    connection_type="api",
    provider="rest",
    dataset_name="orders-refreshable",
    description="Refreshable orders dataset",
    connection_config={"url": "https://example.test/orders.json", "data_path": "items"},
)

refreshed = client.refresh_dataset(created.dataset_id)
detail = client.get_dataset(created.dataset_id)
print(tested["status"], browsed["total"], updated["description"], refreshed["status"], detail["dataset"]["dataset_id"])
```

## Unified capability plane

Use the capability-plane methods when you want one customer-agnostic discovery
and routing surface across connectors, MCP providers, prompt-skills, native
tools, and runtime libraries.

```python
import os

from decision_engine import AlgentaClient

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(
    api_key=api_key,
    base_url="http://localhost:8000",
)

providers = client.list_capability_providers()
skills = client.list_skills()
mcp_providers = client.list_mcp_providers()

route = client.route_capabilities(
    {
        "objective": "Escalate the production incident and use the right tool",
        "kinds": ["skill", "mcp_tool", "native_tool"],
        "artifact_affinities": ["incident"],
        "tags": ["incident", "escalation"],
    }
)

selected = client.get_capability(route.selected_capability_id)
print(route.kind, route.execution_owner, route.selected_capability_id)
print(selected["name"], selected["required_policy"])
print(providers[0]["provider_id"], len(skills), len(mcp_providers))

if route.kind != "skill":
    execution = client.execute_capability(
        {
            "capability_id": route.selected_capability_id,
            "input": {"ticket_id": "INC-123"},
        }
    )
    print(execution["status"], execution["execution_owner"])
```

These route and execution methods are the same public control-plane contract
used by hosted, self-hosted, and hybrid customer apps. Use
`list_capability_bindings(...)`, `create_capability_binding(...)`,
`preview_test_capability_binding(...)`, `preview_discover_capability_binding(...)`,
`start_capability_authorization(...)`, and `complete_capability_authorization(...)`
when you need to manage the binding lifecycle explicitly before routing.

## Repository intelligence

```python
snapshot = client.create_repository_snapshot(
    "repo_123",
    {
        "ref": "main",
        "include_patterns": ["apps/**", "packages/**", "tests/**"],
        "exclude_patterns": ["**/node_modules/**", "**/dist/**"],
        "max_files": 20000,
    },
)

triage = client.triage_repository(
    "repo_123",
    {
        "snapshot_id": snapshot["snapshot_id"],
        "signals": {
            "issue_text": "Production regression after the latest deploy",
            "diagnostics": [
                {
                    "path": "apps/api_server/services/repository_intelligence.py",
                    "line": 2047,
                    "severity": "error",
                    "message": "Repository analysis is missing patch impact metadata.",
                }
            ],
            "failing_tests": [
                "tests/test_repository_intelligence_service.py::test_simulate_requires_patch_impact"
            ],
            "changed_files": ["apps/api_server/services/repository_intelligence.py"],
            "workspace_context": ["incident-1842", "jira-912"],
        },
        "max_evidence_items": 12,
        "token_budget": 4000,
    },
)

plan_revision = client.create_repository_decision_plan(
    "repo_123",
    {
        "snapshot_id": snapshot["snapshot_id"],
        "workspace_evidence_bundle_ref": triage["workspace_evidence_bundle_ref"],
        "model": "gpt-5.1",
    },
)

simulation = client.simulate_repository(
    "repo_123",
    {
        "snapshot_id": snapshot["snapshot_id"],
        "decision_plan_id": plan_revision["decision_plan_id"],
        "runs": 5000,
        "seed": 42,
    },
)

patch_only = client.apply_repository(
    "repo_123",
    {
        "snapshot_id": snapshot["snapshot_id"],
        "decision_plan_id": plan_revision["decision_plan_id"],
        "simulation_id": simulation["validated_inputs"]["simulation_id"],
        "mode": "patch_only",
    },
)

print(plan_revision["decision_plan"]["repository_analysis"]["patch_impact_report_ref"])
print(simulation["recommended_action"], simulation["score_breakdown"])
print(patch_only["patch"])
```

`create_repository_decision_plan(...)` creates the immutable stored revision
behind `POST /v1/repositories/{repository_id}/decision-plans`. The client keeps
the method singular as a verb while the API stays plural as a resource.

If you want a fully local self-hosted repository planner, set
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`.
That planner is explicit and bounded; it currently supports deterministic
Python return-literal mismatch repairs and fails closed with
`repository_local_planner_unsupported` when the evidence bundle does not match
that contract.

Every stored repository `DecisionPlan` also records planner provenance in
`decision_plan.repository_analysis` through `planner_model_id`,
`planner_execution_mode`, and `planner_provider_backend`.

Use these surfaces as follows:

- `get_contract()` when you need the live machine-readable Algenta contract from the running service
- `get_runtime_manifest()`, `get_runtime_modules()`, `get_runtime_benchmarks()`, and `get_runtime_release_validation()` when you need the signed runtime proof surfaces from the running service
- `get_runtime_benchmarks()` also includes benchmark-class `evidence_paths`, so benchmark claims retain concrete artifact linkage rather than only code and description labels
- `get_runtime_benchmarks()` currently exposes the quality-gate benchmark classes `B6` checkpoint and replay overhead, `B7` MCP tool latency, `B9` RAG retrieval quality and latency, and `B10` decision workflow completion latency
- `B10` is currently backed by the Repository Intelligence workflow artifact at `build/repository_intelligence_benchmark.json`
- `get_runtime_benchmarks()` currently exposes the quality-gate SLO budgets `mcp_call_first_party`, `decision_plan_creation`, and `replay`
- `list_agent_runs(...)` for paginated persisted agent-run inventory with lineage-aware filters
- `list_agent_run_checkpoints(run_id)` and `query_agent_run_checkpoints(...)` for checkpoint inspection and cross-run checkpoint discovery
- `list_agent_run_mission_events(run_id, limit=...)` and `query_agent_run_mission_events(...)` for canonical mission-event inspection
- `list_agent_run_telemetry(run_id, limit=...)` and `query_agent_run_telemetry(...)` for persisted runtime telemetry inspection
- `replay_agent_run(run_id, checkpoint_id=...)` and `fork_agent_run(run_id, checkpoint_id=...)` for deterministic replay and branch-from-checkpoint flows
- `get_audit_logs(...)` and `get_audit_log_artifacts(...)` for control-plane audit review, including immutable content-hash-backed artifacts
- `list_execution_policy_snapshots()` for execution-policy lineage and policy rollback review
- `create_connector(...)`, `get_connector(...)`, `update_connector(...)`, `test_connector(...)`, `browse_connector(...)`, and `delete_connector(...)` for the saved connector lifecycle
- `create_repository_snapshot(...)` and `get_repository_snapshot(...)` for immutable repository snapshot lineage
- `triage_repository(...)` for deterministic repository narrowing into a bounded workspace evidence bundle
- `query_repository_graph(...)` for dependency, dependent, and change-risk graph inspection from a snapshot or workspace evidence bundle
- `create_repository_decision_plan(...)` for stored immutable repository `DecisionPlan` revisions with `repository_analysis`
- `simulate_repository(...)` for policy-gated repository risk simulation with populated `decision_plan` and `score_breakdown`
- `apply_repository(...)` for `patch_only`, `local_branch`, or `remote_pr` application after simulation passes the apply gate

The same repository-intelligence operations are also available on
`algenta.Runtime(mode="api")` and `Runtime(mode="self_hosted")` when you want
the runtime-first surface instead of the direct `DecisionEngineClient` facade:
`create_repository_snapshot(...)`, `get_repository_snapshot(...)`,
`triage_repository(...)`, `create_repository_decision_plan(...)`,
`simulate_repository(...)`, and `apply_repository(...)`.

For `algenta.Runtime(mode="local")`, keep the repository-backend wiring on the
runtime side rather than mixing it into the service-first SDK page. The local
runtime guide documents the unified backend contract, including
`ALGENTA_RUNTIME_REPOSITORY_INTELLIGENCE_BACKEND`,
`repository_intelligence_backend="my_repo_backend.module:build_backend"`, and
the fail-closed `local_repository_intelligence_backend_required` behavior.
- `list_datasets(..., compact=True)` and `get_dataset_summary()` for low-token dataset discovery
- `preview_test_connector(connector={...})` and `preview_browse_connector(connector={...})` for one-shot connector validation before saving a reusable connector or starting an import
- `connect_data(...)`, `get_dataset(...)`, `refresh_dataset(...)`, and `delete_dataset(...)` for the refreshable dataset lifecycle
- `query_with_metadata()` when you need stable request/cost/latency metadata
- `query_batch()` for multiple governed exact queries in one API call
- `query_sql_report()` for read-only wide reports over already authorized datasets
- `QueryFilterCondition` / `QueryFilterSpec` when you want deterministic
  `status`, `category`, boolean, numeric, or null filters without inventing
  private request shapes

These filters follow a **record-filter contract**, not SQL clauses. The same
payload is meant to work for SQL-backed datasets, Redis and other non-SQL sources,
and normalized file-backed datasets.

The package root also exports the shared public contract constants:

```python
from decision_engine import DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT

print(DEFAULT_BASE_URL)
print(PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"])
print(PRIMARY_DATA_QUERY_CONTRACT["api"]["query_batch_endpoint"])
print(PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["type_behavior"]["numeric"])
```

## Optional local runtime

`algenta-core` remains available for local development, testing, embedded execution, and the optional development CLI:

```bash
pip install algenta-core
```

That is the pure local runtime surface. If you want `algenta.Runtime(mode="api")`
or `Runtime(mode="self_hosted")` from a published package index, install the
hosted extra too:

```bash
pip install "algenta-core[cloud]"
```

Those API-backed runtime modes intentionally fail closed if `algenta-sdk` is
not installed. For local artifact validation before publish, install the local
`algenta-sdk` and `algenta-core` artifacts together instead of assuming the
`[cloud]` extra can resolve an unpublished SDK from a package index.

For the unified capability plane, `Runtime(mode="local")` only executes
`client_managed` capabilities. `algenta_managed` capabilities remain
discoverable and routable in local mode, but execution fails closed until you
switch to `Runtime(mode="api")` or `Runtime(mode="self_hosted")`.

That is still a secondary local-runtime surface, not the self-hosted product.
