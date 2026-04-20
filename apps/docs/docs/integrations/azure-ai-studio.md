---
sidebar_position: 5
---

# Azure AI Foundry and Studio

Use Algenta from Azure-hosted copilots, assistants, and prompt flows with the canonical hosted `v1` contract.

## Recommended path

- Use OpenAPI import or a function-tool wrapper today
- Keep auth canonical: `Authorization: Bearer <api_key>`
- Start read-only, then enable write actions only when the flow really needs them

Base URL:

```text
https://api.algenta.ai
```

## Option A: OpenAPI import

1. Import `https://api.algenta.ai/openapi.json`.
2. Configure Bearer auth with your Algenta API key.
3. Limit the imported actions to what the agent actually needs.

Good first actions:

- `/v1/simulate`
- `/v1/recommend`
- `/v1/data`
- `/v1/query`

## Option B: Function tool or Prompt Flow node

Use the reference files in [`examples/azure-ai-studio/`](https://github.com/decisionengine/decision-engine/tree/main/examples/azure-ai-studio/):

- `algenta_tool_definition.json`
- `README.md`

## First successful task

Try one simple simulation first:

```text
Should we expand into Europe if revenue could be $500k-$2M and expansion cost could be $300k-$800k?
```

That proves:

- Azure can call Algenta
- Bearer auth is correct
- the agent can interpret the decision envelope

## Write actions

Only enable dataset mutations if the flow needs them:

- `connect_data`
- `refresh_data`
- `disconnect_data`

For Azure-hosted agents, put those behind an explicit approval step in the orchestration layer.

## Revoke or disconnect

- Remove the imported tool or flow node from Azure
- Rotate or revoke the Algenta API key
- Remove stored environment variables in the Azure project or deployment

## Troubleshooting

- `401 invalid_api_key`: wrong key or wrong auth mode
- `429 rate_limit_exceeded`: honor `Retry-After`
- `429 quota_exceeded`: monthly plan limit reached
- `503 mcp_upstream_unavailable`: if you proxy through MCP, treat it as an upstream outage
