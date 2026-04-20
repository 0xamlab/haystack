---
sidebar_position: 4
---

# n8n

Use Algenta in n8n to add simulations and dataset queries to any workflow.

## Prerequisites

- An Algenta API key
- An n8n workflow with HTTP Request or AI-agent nodes
- Read-only access unless the workflow must mutate datasets

## Setup

1. In your n8n workflow, add an **HTTP Request** node
2. Set **Method**: `POST`
3. Set **URL**: `https://api.algenta.ai/v1/simulate`
4. Under **Headers**, add: `Authorization` = `Bearer de_live_...`
5. Set **Body** to JSON:

```json
{
  "mode": "auto",
  "scenario": {
    "variables": {
      "revenue": { "low": 80000, "high": 200000 },
      "cost":    { "low": 30000, "high": 90000 }
    },
    "objective": "maximize_net_value"
  }
}
```

6. Map `{{ $json.recommended_action }}` in downstream nodes

Full workflow example: [`examples/n8n/workflow_simulate.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/n8n/workflow_simulate.json)

## First workflow

Start with one simulation node, then pass:

- `recommended_action`
- `confidence`
- `rationale`

to Slack, Airtable, Notion, or approval steps.

## Typical use cases

- Decision gate: proceed only if `confidence > 0.7`
- Slack notification with recommendation rationale
- Write result to Airtable/Notion for audit trail
- Compare multiple options using `/v1/recommend`

## Write actions

Only add dataset mutations if the workflow needs them:

- `/v1/data/connect`
- `/v1/data/{dataset_id}/refresh`
- `/v1/data/{dataset_id}`

## Revoke or disconnect

- Remove the credential or environment variable from n8n
- Revoke the Algenta API key if the workflow should lose access entirely

## Troubleshooting

- `401 invalid_api_key`: wrong Bearer token or missing header
- `429 rate_limit_exceeded`: back off and honor `Retry-After`
- Empty downstream fields: inspect the HTTP node output and confirm you are mapping the Algenta response body, not the full transport envelope
