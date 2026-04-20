# Algenta — n8n

Use Algenta from n8n with HTTP Request nodes or MCP-aware AI flows.

## Files

- `workflow_simulate.json` — example HTTP workflow for `/v1/simulate`

## Setup

1. Add an **HTTP Request** node.
2. Set the URL to `https://api.algenta.ai/v1/simulate`.
3. Add `Authorization: Bearer de_live_...`.
4. Send JSON with `mode: "auto"` and a `scenario`.

## First workflow

Use `workflow_simulate.json`, then map:

- `recommended_action`
- `confidence`
- `rationale`

into downstream nodes.

## Revoke or disconnect

- Remove the node credentials or environment variable
- Revoke the Algenta API key if the workflow should lose access entirely
