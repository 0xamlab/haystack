# Algenta — Claude Desktop and Codex MCP

Use Algenta from Claude Desktop, Codex, and other MCP clients.

## Recommended split

- Cloud Managed remote-MCP clients: `https://api.algenta.ai/mcp`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL
- Claude Desktop local-process hosts: use the bundled stdio bridge below

Private profiles do not silently fall back to Algenta cloud.

## Claude Desktop local bridge

Edit your Claude Desktop config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add the Algenta MCP server:

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

Then restart Claude Desktop fully.

## Codex and remote MCP clients

Use:

```text
URL: https://api.algenta.ai/mcp
Header: Authorization: Bearer <YOUR_ALGENTA_API_KEY>
```

Use the hosted URL only in Cloud Managed. `self_hosted` and `air_gapped` must
point `ALGENTA_BASE_URL`, `DE_BASE_URL`, or `ALGENTA_API_URL` or the remote
MCP URL at the self-hosted deployment. Canonical env vars are `ALGENTA_API_KEY` and `ALGENTA_BASE_URL`; legacy `DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for compatibility.
Cloud Managed API keys come from `https://app.algenta.ai/dashboard/api-keys`.
In `self_hosted` and `air_gapped`, use the API key provisioned by your
self-hosted operator deployment instead.

Start read-only if your client supports tool scoping.

## Available Tools in Claude

| Tool | Description |
|------|-------------|
| `get_contract` | Machine-readable Algenta contract for live API/SDK/CLI/MCP discovery |
| `list_data` | Canonical dataset discovery with `search`, `status`, `source_name`, and `compact` |
| `get_data_summary` | Low-token summary for a selected dataset before full schema |
| `get_data_schema` | Full schema, roles, formulas, and query hints |
| `query_data` | Governed exact query over a chosen dataset |
| `query_batch` | Governed multi-metric exact query in one call |
| `query_sql_report` | Constrained read-only SQL rowset over authorized datasets |
| `simulate` | Run a Monte Carlo simulation with any variables and distributions |
| `list_runs` | List recent simulation runs with filters |
| `get_run` | Fetch full details of a specific run |
| `get_analytics` | Analytics: volume, latency, action distribution |
| `get_usage` | Current quota usage vs plan limits |
| `submit_job` | Submit large async simulation (100K+ scenarios) |
| `get_job_status` | Poll async job status |
| `list_connectors` | List configured data connectors |
| `recommend` | Quick recommendation from natural language context |
| `list_agent_runs` | List persisted agent runs with lineage-aware filters |
| `query_agent_run_checkpoints` | Query replay checkpoints across runs |
| `query_agent_run_mission_events` | Query persisted mission-event records across runs |
| `query_agent_run_telemetry` | Query persisted runtime telemetry across runs |
| `get_audit_log_artifacts` | Fetch immutable audit-log artifacts and content hashes |
| `list_execution_policy_snapshots` | Review stored execution-policy snapshots |

## Example Conversations

### Dataset Discovery and Query
```
You: Inspect get_contract(), then find the orders dataset with
     list_data(search="orders", compact=true), inspect its summary, then query
     completed orders by month for the last 12 months.

Claude: [Uses get_contract → list_data → get_data_summary → query_data]
```

### Simple Business Decision
```
You: Should we invest in expanding our warehouse capacity?
     Current revenue: $800K-$1.5M, expansion cost: $200K-$400K,
     expected demand increase: 15-40%.

Claude: [Uses simulate tool → returns PROCEED/CAUTION/REJECT with confidence %]
```

### Portfolio Risk Analysis
```
You: Run a VaR analysis on a portfolio with 60% equities, 
     30% bonds, 10% alternatives. Use 100,000 scenarios.

Claude: [Uses simulate with expert mode + lhs model → returns VaR, CVaR, percentile distribution]
```

### Drug Development ROI
```
You: What's the expected NPV for our Phase 2 drug trial?
     Success probability: 40-60%, development cost: $50M-$80M,
     peak sales if successful: $300M-$800M.

Claude: [Uses simulate → returns expected NPV, probability of positive ROI, risk metrics]
```

### Check Your Usage
```
You: How many simulations have I run this month?

Claude: [Uses get_usage tool → returns quota consumption and plan details]
```

## Local development

If running the API server locally:

```json
{
  "mcpServers": {
    "algenta-local": {
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

## Recommended data flow

For governed data questions, use:

1. `get_contract()`
2. `list_data(search=..., compact=true)`
3. `get_data_summary(dataset_id)`
4. `get_data_schema(dataset_id)` only if you need the full schema payload
5. `query_data(...)` for a single exact query
6. `query_batch(...)` for multi-metric governed exact queries
7. `query_sql_report(...)` only for wide read-only rowsets

For persisted runtime follow-up or governed approval flows, use:

1. `list_agent_runs(...)`
2. `query_agent_run_checkpoints(...)`
3. `query_agent_run_mission_events(...)`
4. `query_agent_run_telemetry(...)`
5. `get_audit_log_artifacts(...)`
6. `list_execution_policy_snapshots()`

`get_contract()` includes `primary_data_query_contract.governed_filter_contract`
for machine-readable selector fields, operator families, and validation rules.

## Troubleshooting

**"ALGENTA_API_KEY not set"** — Check the env block in your claude_desktop_config.json has the correct key.

**"API error 401"** — Your API key is invalid or expired. In Cloud Managed,
rotate it at `https://app.algenta.ai/dashboard/api-keys`. In `self_hosted` and
`air_gapped`, rotate the API key in your self-hosted operator deployment.

**Tools not appearing** — Restart Claude Desktop fully after editing the config file.

**Connection timeout** — Check your internet connection or try
`ALGENTA_BASE_URL=http://localhost:8000`,
`DE_BASE_URL=http://localhost:8000`, or
`ALGENTA_API_URL=http://localhost:8000` for local testing.
