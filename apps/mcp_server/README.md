# Codna MCP Server

**Model Context Protocol (MCP)** bridge for the Codna runtime and public API surface. Connects AI agents to governed dataset discovery, exact queries, deterministic utility-model routes, simplified product helpers, persisted agent runs, simulations, jobs, and connector-backed datasets.

## Tools Available

| Tool | Description |
|------|-------------|
| `get_contract` | Machine-readable Codna contract for tool/API/SDK discovery. |
| `connect_data` | High-level dataset onboarding. Connect once and get a reusable `dataset_id`. |
| `list_data` | Canonical dataset discovery. Supports `search`, `status`, `source_name`, and `compact`. |
| `get_data_summary` | Low-token summary for a selected dataset before loading full schema. |
| `get_data_schema` | Full schema, roles, formulas, and query hints for a dataset. |
| `query_data` | Governed exact query over a chosen dataset. |
| `query_batch` | Governed multi-metric exact query in one API call. |
| `query_sql_report` | Constrained read-only SQL rowset over authorized datasets. |
| `list_models` | Enumerate the truthful model catalog, including routed provider targets, failover policy, timeout budgets, aggregate provider-auth metadata, and capability-specific chat/embedding auth-header readiness, before LLM utility calls. |
| `resolve_artifact_bridge` | Resolve one Hugging Face artifact path through the cache-safe compatibility bridge. |
| `tokenize` | Deterministic tokenizer utility route. |
| `count_tokens` | Deterministic token-count utility route. |
| `chat_completions` | Tokenizer-backed utility chat contract. |
| `responses` | Unified deterministic utility response surface. |
| `embeddings` | Deterministic lexical embedding route. |
| `embedding_similarity` | Score caller-supplied vectors with a supported similarity model. |
| `rerank` | Rank caller-supplied document embeddings deterministically. |
| `product_decision` | Run the simple product decision helper and return the chosen action plus risk summary. |
| `product_agent_run` | Run the simple product task-execution helper and return a compact task result. |
| `product_optimize` | Run the simple product optimization helper and return the best variable values. |
| `product_retrieve` | Run the simple product retrieval helper over caller-supplied documents or a collection id. |
| `product_forecast` | Run the simple product forecast helper over a historical metric series. |
| `plan_decision` | Return the structured DecisionPlan without the full decision envelope. |
| `log_decision` | Persist one decision-memory record for later outcome review. |
| `list_decisions` | List persisted decision-memory records with optional outcome-only filtering. |
| `get_decision` | Fetch one persisted decision-memory record by id. |
| `record_outcome` | Record the actual outcome for one persisted decision-memory record. |
| `execute_decision` | Dispatch one persisted decision-memory record to a webhook and persist the receipt. |
| `delete_decision` | Delete one persisted decision-memory record by id. |
| `create_agent_run` | Create a persisted agent run lifecycle resource. |
| `list_agent_runs` | List persisted agent runs with lineage-aware filters and pagination. |
| `get_agent_run` | Fetch one persisted agent run. |
| `get_agent_run_events` | Fetch the append-only event stream for one run. |
| `get_agent_run_checkpoints` | Fetch persisted checkpoints for one agent run. |
| `query_agent_run_checkpoints` | Query persisted checkpoints across runs with lineage-aware filters. |
| `get_agent_run_mission_events` | Fetch canonical mission-event records for one agent run. |
| `query_agent_run_mission_events` | Query mission-event records across runs with lineage-aware filters. |
| `get_agent_run_telemetry` | Fetch persisted runtime telemetry batches for one agent run. |
| `query_agent_run_telemetry` | Query telemetry batches across runs with lineage-aware filters. |
| `resume_agent_run` | Resume a paused run. |
| `cancel_agent_run` | Cancel a run. |
| `approve_agent_run` | Approve a run waiting on manual approval. |
| `update_me` | Update the current user name and or organization name for the active API key. |
| `list_distributions` | List the simulation distribution catalog available to the current organization. |
| `list_templates` | List scenario templates available to the current organization. |
| `list_team_members` | List team members for the current organization. |
| `invite_team_member` | Invite a team member to the current organization. |
| `update_team_member_role` | Update one current organization team member role by user id. |
| `remove_team_member` | Remove one team member from the current organization by user id. |
| `get_billing_info` | Get current billing plan and subscription info for the active organization. |
| `create_billing_checkout` | Create a Stripe Checkout session for the active organization. |
| `create_billing_portal` | Create a Stripe Billing Portal session for the active organization. |
| `refresh_credits` | Issue one execution credit batch for a local runtime device. |
| `ingest_metering_events` | Ingest one local metering event batch for the active organization. |
| `list_devices` | List registered devices for the current organization. |
| `revoke_device` | Revoke one registered device by registration id for the current organization. |
| `get_audit_logs` | Get paginated audit logs for the current organization. |
| `get_audit_log_artifacts` | Get immutable audit-log artifacts for the current organization, including content hashes. |
| `get_execution_policy` | Get the current autonomous execution policy for the active organization. |
| `list_execution_policy_snapshots` | List stored execution-policy snapshots for the active organization. |
| `update_execution_policy` | Update one or more execution-policy thresholds for the active organization. |
| `list_deployment_regions` | List available deployment providers and regions for the current organization. |
| `get_deployment` | Fetch the current deployment for the active organization, if one exists. |
| `create_deployment` | Request a new isolated deployment for the active organization. |
| `get_deployment_cost` | Get current-month cost details for one deployment by id. |
| `delete_deployment` | Request deprovisioning for one deployment by id. |
| `list_runtime_libraries` | List executable local-runtime Mojo libraries and their functions. |
| `execute_runtime_library` | Execute one local-runtime Mojo library function by module and function name. |
| `simulate` | Monte Carlo simulation (auto or expert mode). |
| `recommend` | Compare actions and return a ranked recommendation. |
| `score` | Score one simulation request with weighted decision criteria. |
| `batch` | Run multiple simulation requests in one decision-runtime call. |
| `compare` | Compare named scenarios and return the winner plus deltas. |
| `submit_job` | Submit a large async simulation with optional webhook. |
| `list_jobs` | List async simulation jobs with pagination and optional status filtering. |
| `get_job_status` | Fetch the latest async simulation job status by id. |
| `poll_job` | Wait for a terminal async job state and return the final result or timeout summary. |
| `get_job_result` | Fetch the completed result payload for an async simulation job by id. |
| `cancel_job` | Cancel a queued or running async simulation job by id. |
| `test_webhook_delivery` | Send a test webhook payload to one callback URL and return the delivery result. |
| `register_trigger` | Register a threshold trigger with a simulation template and optional webhook automation. |
| `list_triggers` | List registered triggers with current status and latest evaluation summary. |
| `fire_trigger` | Manually evaluate and fire one trigger, optionally forcing execution. |
| `pause_trigger` | Pause or resume one trigger without deleting it. |
| `delete_trigger` | Delete one trigger so it no longer fires automatically. |
| `list_runs` | List recent simulation runs with status and mode filters. |
| `get_run` | Fetch the full decision envelope for a specific run by ID. |
| `get_analytics` | Daily volume, P95 latency, action distribution, mode breakdown. |
| `get_usage` | Current billing period usage vs quota, rate limits. |
| `list_connectors` | List saved data connectors and their current health status. |
| `create_connector` | Create and save one reusable connector definition. |
| `get_connector` | Fetch one saved connector by id. |
| `update_connector` | Update one saved connector config or metadata. |
| `test_connector` | Run a real health check for one saved connector. |
| `preview_test_connector` | Run a real health check for one inline connector definition without saving it. |
| `browse_connector` | Browse one saved live connector for tables, files, or items. |
| `preview_browse_connector` | Browse one inline connector definition without saving it. |
| `delete_connector` | Delete one saved connector by id. |
| `create_repository_snapshot` | Create or reuse one immutable repository snapshot for a saved repository connector. |
| `get_repository_snapshot` | Fetch one immutable repository snapshot by repository_id and snapshot_id. |
| `triage_repository` | Triage one repository snapshot into a bounded workspace evidence bundle. |
| `create_repository_decision_plan` | Create one immutable repository DecisionPlan revision from a snapshot and workspace evidence bundle. |
| `simulate_repository` | Simulate repository patch risk and return the gated DecisionEnvelope. |
| `run_repository_pipeline` | Run snapshot, triage, plan, and simulate, then return the canonical repository envelope. |
| `simulate_repository_patch` | Simulate one in-flight patch and return the canonical repository envelope. |
| `run_repository_fix` | Run repository pipeline plus apply, then return the canonical repository envelope. |
| `apply_repository` | Apply a simulated repository decision as patch_only, local_branch, or remote_pr. |

For the primary data flow, use:

1. `get_contract()`
2. `list_data(search=..., compact=true)`
3. `get_data_summary(dataset_id)`
4. `get_data_schema(dataset_id)` only if you need the full schema payload
5. `query_data(dataset_id=...)` for a single governed exact query
6. `query_batch(...)` for multi-metric governed exact queries
7. `query_sql_report(...)` only for wide read-only rowsets

For the saved connector lifecycle, use:

1. `list_connectors()` to inspect current connector inventory
2. `create_connector(...)` to save one connector definition
3. `get_connector(connector_id)` / `update_connector(connector_id, ...)` for one saved connector
4. `test_connector(connector_id)` before browsing or governed data onboarding
5. `browse_connector(connector_id)` to inspect tables, files, endpoints, or items
6. `delete_connector(connector_id)` when the saved connector is no longer needed

For one-off inline preview checks without saving a connector, use:

1. `preview_test_connector(connector_type=..., config=...)`
2. `preview_browse_connector(connector_type=..., config=...)`

For the repository intelligence lane, use:

1. `create_repository_snapshot(...)` to pin one immutable repository snapshot
2. `triage_repository(...)` to build one bounded workspace evidence bundle
3. `query_repository_graph(...)` to inspect dependency, dependent, and change-risk edges for one file, symbol, or evidence bundle
4. `create_repository_decision_plan(...)` to create one immutable `decision_plan_id`
5. `simulate_repository(...)` to run the repository apply gate with the stored plan
6. `apply_repository(...)` only after the gate passes or when `patch_only` is the explicit requested mode

For the canonical repository envelope lane, use:

1. `run_repository_pipeline(...)` when you want one normalized repository envelope for snapshot, triage, plan, and simulate
2. `simulate_repository_patch(...)` when you want the same envelope shape for in-flight patch gating
3. `run_repository_fix(...)` when you want pipeline plus apply in one MCP call

`create_repository_decision_plan(...)` returns repository analysis with
`generated_patch_ref`, `patch_impact_report_ref`, and planner provenance through
`repository_analysis.planner_model_id`,
`repository_analysis.planner_execution_mode`, and
`repository_analysis.planner_provider_backend`.

When the local stack sets
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`, the
MCP server exposes the bounded deterministic local planner instead of a
provider-backed planner. The explicit local planner model id is
`repository.deterministic_local_v1`. Unsupported evidence bundles fail closed with
`repository_local_planner_unsupported`.

The governed filter shape behind `query_data` / `query_batch` is a
**record-filter contract** over normalized rows, not SQL. That keeps the same
tool contract valid for SQL backends, Redis snapshots, files, and API-fed data.
The machine-readable operator families and validation rules are exposed through
`get_contract()` under `primary_data_query_contract.governed_filter_contract`.

For the local/runtime-backed compute lane, use:

1. `list_runtime_libraries(search=...)`
2. `execute_runtime_library(module=..., function=..., args=...)`

For the utility-model and agent-run lane, use:

1. `list_models()` for the truthful model catalog, including routed target, failover, timeout, aggregate provider-auth metadata, and capability-specific chat/embedding auth-header readiness
2. `resolve_artifact_bridge(repo_id=..., filename=..., revision=..., local_files_only=...)`
3. `tokenize(...)`, `count_tokens(...)`, `chat_completions(...)`, `responses(...)`, `embeddings(...)`, `embedding_similarity(...)`, or `rerank(...)`
3. `product_decision(...)`, `product_agent_run(...)`, `product_optimize(...)`, `product_retrieve(...)`, and `product_forecast(...)` for the business-facing simplified product lane
4. `plan_decision(...)` when you need the DecisionPlan summary only
5. `log_decision(...)`, `list_decisions(...)`, `get_decision(...)`, `record_outcome(...)`, `execute_decision(...)`, and `delete_decision(...)` for persisted decision-memory work
6. `create_agent_run(...)`
7. `list_agent_runs(...)` for paginated persisted run discovery
8. `get_agent_run(run_id)` and `get_agent_run_events(run_id)` to inspect lifecycle state
9. `get_agent_run_checkpoints(run_id)`, `query_agent_run_checkpoints(...)`, `get_agent_run_mission_events(run_id)`, `query_agent_run_mission_events(...)`, `get_agent_run_telemetry(run_id)`, and `query_agent_run_telemetry(...)` for canonical checkpoint, mission-event, and telemetry inspection
10. `resume_agent_run(run_id)`, `approve_agent_run(run_id)`, or `cancel_agent_run(run_id)` for explicit transitions

For the deployment control-plane lane, use:

1. `list_deployment_regions()`
2. `get_deployment()`
3. `get_deployment_cost(deployment_id)` when a deployment exists
4. `create_deployment(...)` / `delete_deployment(...)` for explicit control-plane mutations

For the billing, team, device, and execution-policy lane, use:

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
17. `list_execution_policy_snapshots()`
18. `update_execution_policy(...)`

---

## Prerequisites

```bash
pip install mcp httpx structlog
```

Set your API key:
```bash
export ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"
if [ -z "$ALGENTA_API_KEY" ]; then
  echo "Set ALGENTA_API_KEY or DE_API_KEY before running this example." >&2
  exit 1
fi

export ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.codna.ai}}}"   # Cloud Managed default only; replace for self-hosted private profiles
```

Canonical MCP env vars are `ALGENTA_API_KEY` and `ALGENTA_BASE_URL`. Legacy
`DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for compatibility.

Choose the base URL for your deployment mode:

- Cloud Managed: `https://api.codna.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL via `ALGENTA_BASE_URL`, `DE_BASE_URL`, or `ALGENTA_API_URL`

Private profiles fail closed and will not silently fall back to Codna cloud.

Use `https://app.codna.ai/dashboard/api-keys` only in Cloud Managed. In
`self_hosted` and `air_gapped`, use the API key provisioned by your
self-hosted operator deployment.

---

## Connection Guide by Platform

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "algenta": {
      "command": "python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
          "ALGENTA_API_KEY": "<SET ALGENTA_API_KEY OR DE_API_KEY BEFORE LAUNCH>",
          "ALGENTA_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

Use `https://api.codna.ai` only in Cloud Managed. `self_hosted` and
`air_gapped` must point `ALGENTA_BASE_URL`, `DE_BASE_URL`, or `ALGENTA_API_URL`
at the self-hosted base URL.

Restart Claude Desktop. You'll see `algenta` in the tools panel. Try:
> *"Inspect get_contract(), find the orders dataset with list_data(search='orders', compact=true), inspect its summary, then query completed orders by month for the last 12 months."*

---

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "algenta": {
      "command": "python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
        "ALGENTA_API_KEY": "<SET ALGENTA_API_KEY OR DE_API_KEY BEFORE LAUNCH>"
      }
    }
  }
}
```

Then in Cursor chat: *"@algenta simulate this business case..."*
For repository fixing, prefer:
> *"@algenta run_repository_fix repository_id='repo_123' pipeline={\"signals\":{\"issue_text\":\"Null dereference in src/service.py\"}} apply={\"mode\":\"patch_only\"}"*

---

### Zed Editor

Add to `~/.config/zed/settings.json`:

```json
{
  "context_servers": {
    "algenta": {
      "command": {
        "path": "python",
        "args": ["-m", "apps.mcp_server.server"],
        "env": {
          "ALGENTA_API_KEY": "<SET ALGENTA_API_KEY OR DE_API_KEY BEFORE LAUNCH>"
        }
      }
    }
  }
}
```

---

### HTTP/SSE Transport (Remote Agents)

Start the HTTP server:

```bash
python -m apps.mcp_server.server --transport http --port 8001

# Or via environment variable:
ALGENTA_MCP_PORT=8001 python -m apps.mcp_server.server --transport http
```

Or if you have the Codna API server running, the MCP is already mounted at:
- **`GET  /mcp/tools`** — List tools (JSON, no auth needed, always available)
- **`GET  /mcp/sse`** — SSE connection endpoint when the optional MCP transport dependencies are installed
- **`POST /mcp/messages`** — Message handler when the optional MCP transport dependencies are installed

If the optional MCP transport dependencies are not installed, the API still mounts all three routes, but:
- **`GET  /mcp/tools`** stays available
- **`GET  /mcp/sse`** returns `503` with `error.code = "mcp_transport_unavailable"`
- **`POST /mcp/messages`** returns `503` with `error.code = "mcp_transport_unavailable"`
- both transport routes include the hint: `Install requirements-mcp.txt to enable /mcp/sse and /mcp/messages.`

---

### n8n

1. Add an **MCP Client** node
2. Set **Transport**: `SSE`
3. Set **URL**: `<YOUR_ALGENTA_BASE_URL>/mcp/sse`
4. Set **Header**: `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`

Example workflow: *Trigger → Codna list_data/search → get_data_summary → query_data or query_batch → Send Slack notification*

---

### LangChain / LangGraph

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "algenta": {
        "url": "http://localhost:8001/mcp/sse",
        "transport": "sse",
    }
})

tools = await client.get_tools()

# Use with any LangChain agent
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(model="claude-3-5-sonnet", tools=tools)

result = await agent.ainvoke({
    "messages": [{
        "role": "user",
        "content": "Run a simulation with revenue=500000, cost=300000, growth_rate=0.15"
    }]
})
```

---

### LlamaIndex

```python
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

client = BasicMCPClient("http://localhost:8001/mcp/sse")
spec = McpToolSpec(client=client)
tools = spec.to_tool_list()

from llama_index.agent.openai import OpenAIAgent
agent = OpenAIAgent.from_tools(tools, verbose=True)
response = agent.chat("Should we proceed with the EMEA expansion? Revenue projection $800K.")
```

---

### OpenAI Assistants (Custom GPT / Function Calling)

The `/mcp/tools` endpoint returns tools in OpenAI-compatible format. You can also use any MCP→OpenAI bridge:

```python
import httpx
import os

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

base_url = (
    os.environ.get("ALGENTA_BASE_URL")
    or os.environ.get("DE_BASE_URL")
    or os.environ.get("ALGENTA_API_URL")
)
if not base_url:
    raise RuntimeError(
        "Set ALGENTA_BASE_URL, DE_BASE_URL, or ALGENTA_API_URL before running this example. "
        "Use https://api.codna.ai only in Cloud Managed."
    )

# Get tools list
tools = httpx.get(f"{base_url}/mcp/tools").json()["tools"]

# Call a tool directly via HTTP
result = httpx.post(
    f"{base_url}/v1/simulate",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"mode": "auto", "trials": 10000, "inputs": {"revenue": 500000, "cost": 300000}}
)
```

---

### AutoGen / Microsoft Autogen

```python
import autogen
from autogen.agentchat.contrib.mcp_agent import MCPAgent

config = {
    "mcp_server_url": "http://localhost:8001/mcp/sse",
}

algenta_agent = MCPAgent(
    name="CodnaDecisionAgent",
    system_message="You help make data-driven decisions using Monte Carlo simulations.",
    mcp_config=config,
)
```

---

### Direct Python (no MCP client)

```python
import httpx
import os

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

base_url = (
    os.environ.get("ALGENTA_BASE_URL")
    or os.environ.get("DE_BASE_URL")
    or os.environ.get("ALGENTA_API_URL")
)
if not base_url:
    raise RuntimeError(
        "Set ALGENTA_BASE_URL, DE_BASE_URL, or ALGENTA_API_URL before running this example. "
        "Use https://api.codna.ai only in Cloud Managed."
    )

# Run a simulation
resp = httpx.post(
    f"{base_url}/v1/simulate",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "mode": "auto",
        "trials": 10000,
        "inputs": {
            "revenue": 500000,
            "cost": 300000,
            "growth_rate": 0.15,
            "churn_rate": 0.05,
        }
    }
)
result = resp.json()
print(f"Recommendation: {result['recommended_action']} ({result['confidence']:.0%})")
print(f"Rationale: {result['rationale']}")
```

---

## Example Prompts for AI Assistants

Once connected, you can ask natural language questions:

> *"Run a simulation for a SaaS business: revenue $1.2M, costs $800K, monthly growth 12%, churn 3%"*

> *"What does our decision analytics look like for the past 30 days?"*

> *"Submit a large job with 500K trials for our Q3 financial planning model"*

> *"Check my API usage — how many simulations do I have left this month?"*

> *"List my recent simulation runs and show me the ones that recommended REJECT"*

> *"Get the full details of run abc-123 and explain the rationale"*

---

## Deployment (Docker)

Add to your `docker-compose.yml`:

```yaml
mcp-server:
  build:
    context: .
    dockerfile: infra/docker/Dockerfile.api.prod
  command: python -m apps.mcp_server.server --transport http --port 8001
  environment:
    ALGENTA_API_KEY: ${ALGENTA_API_KEY}
    ALGENTA_BASE_URL: http://api-server:8000
  ports:
    - "8001:8001"
  depends_on:
    - api-server
```

---

## Security Notes

- The stdio transport runs locally — API key is only in your environment
- The HTTP transport authenticates downstream to the Codna API with your key
- Add your own authentication layer (API gateway / Nginx) in front of the MCP HTTP port in production
- The `/mcp/tools` list endpoint on the FastAPI server is public (no sensitive data)
- All actual tool calls require `ALGENTA_API_KEY` or `DE_API_KEY` to be set

---

## Troubleshooting

**`ALGENTA_API_KEY / DE_API_KEY environment variables are not set`**
→ Set `export ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY>` or `export DE_API_KEY=<YOUR_LEGACY_DECISION_ENGINE_API_KEY>` before running

**`mcp package not installed`**
→ Run `pip install mcp`

**`API error 401: Unauthorized`**
→ In Cloud Managed, check or rotate the key at
  `https://app.codna.ai/dashboard/api-keys`. In `self_hosted` and
  `air_gapped`, validate or rotate the key in your self-hosted operator
  deployment.

**`API error 429: Rate limit exceeded`**
→ You're over your plan's requests/minute limit. Upgrade or space out calls.

**Tool not showing in Claude Desktop**
→ Check the JSON config syntax, restart Claude Desktop, look for errors in `~/Library/Logs/Claude/`
