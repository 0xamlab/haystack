---
sidebar_position: 5
---

# Azure AI Foundry and Studio

Use Codna from Azure-hosted copilots, assistants, and prompt flows with the canonical `v1` contract.

## Recommended path

- Use OpenAPI import or a function-tool wrapper today
- Keep auth canonical: `Authorization: Bearer <api_key>`
- Start read-only, then enable write actions only when the flow really needs them

Base URL:

- Cloud Managed: `https://api.codna.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Codna cloud.

## Option A: OpenAPI import

1. Import `https://your-algenta-base-url.example/openapi.json` and replace the
   placeholder with Cloud Managed `https://api.codna.ai` or
   `https://your-algenta-host.example/openapi.json` for `self_hosted` / `air_gapped`.
2. Configure Bearer auth with your Codna API key. Canonical env vars are
   `ALGENTA_API_KEY` and `ALGENTA_BASE_URL`; legacy `DE_API_KEY`,
   `DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for compatibility.
3. Limit the imported actions to what the agent actually needs.

If an older self-hosted node still returns `404` for `/v1/meta/contract`, use
`/openapi.json` and read `x-primary-data-query-contract` instead. The OpenAPI
import path already carries that machine-readable contract on current nodes.
That contract also includes `governed_filter_contract`, so Azure-hosted agents
can inspect selector fields and allowed operators before building exact
filters.

Good first actions:

- `/v1/meta/contract`
- `/v1/data`
- `/v1/data/{dataset_id}/summary`
- `/v1/query`
- `/v1/query/batch`
- `/v1/query/sql-report`
- `/v1/simulate`

## Option B: Function tool or Prompt Flow node

Use the reference files in [`examples/azure-ai-studio/`](https://github.com/decisionengine/decision-engine/tree/main/examples/azure-ai-studio/):

- `algenta_contract_tool_definition.json`
- `algenta_tool_definition.json`
- `algenta_query_tool_definition.json`
- `algenta_sql_report_tool_definition.json`
- `README.md`

## First successful task

Try one simple governed data task first:

```text
Inspect the live Codna contract, then find the dataset that matches orders, summarize it, and return the total completed orders plus a monthly breakdown for the last 12 months.
```

That proves:

- Azure can call Codna
- Bearer auth is correct
- the agent can stay on the read-only data path

For wide read-only rowsets that do not fit one exact query or exact-query
batch, add `algenta_sql_report_tool_definition.json` instead of stretching the
exact-query tool into a generic SQL console.

## Write actions

Only enable dataset mutations if the flow needs them:

- `connect_data`
- `refresh_data`
- `disconnect_data`

For Azure-hosted agents, put those behind an explicit approval step in the orchestration layer.

## Revoke or disconnect

- Remove the imported tool or flow node from Azure
- Rotate or revoke the Codna API key
- Remove stored environment variables in the Azure project or deployment

## Troubleshooting

- `401 invalid_api_key`: wrong key or wrong auth mode
- `429 rate_limit_exceeded`: honor `Retry-After`
- `429 quota_exceeded`: monthly plan limit reached
- `503 mcp_upstream_unavailable`: if you proxy through MCP, treat it as an upstream outage
