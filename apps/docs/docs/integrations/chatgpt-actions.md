---
sidebar_position: 2
---

# ChatGPT Actions

Let ChatGPT call Algenta automatically during conversations.

## Prerequisites

- An Algenta API key
- A GPT with Actions enabled
- Read access for discovery and query routes

## Setup

1. In ChatGPT, go to **Explore** → **Create** → **Configure** → **Actions**
2. Click **Import from URL**: `https://api.algenta.ai/openapi.json`
3. Configure authentication as `Authorization: Bearer <api_key>`
4. Start read-only unless the GPT must connect or refresh datasets

## OpenAPI Actions file

The complete spec is at [`examples/chatgpt-actions/openapi_actions.yaml`](https://github.com/decisionengine/decision-engine/tree/main/examples/chatgpt-actions/openapi_actions.yaml).

## First prompt

> "Should I launch this product? Revenue might be $80k–$200k and costs $30k–$90k."

GPT will call `/v1/simulate` automatically and explain the result in natural language.

## First write-capable action

After enabling write actions:

> "Connect this CSV as a dataset named `sales_pipeline`, then show me the schema."

## Tips

- Ask GPT to use `mode: "auto"` for simple scenarios
- Ask GPT to compare options using `/v1/recommend`
- GPT can explain `result_hash` as "a cryptographic proof of the recommendation"

## Revoke or disconnect

- Remove the imported action from the GPT
- Revoke the Algenta API key if the GPT should no longer have access
- Use `disconnect_data` only when you want to remove a dataset, not just disconnect ChatGPT

## Troubleshooting

- `401 invalid_api_key`: wrong or revoked Bearer token
- `429 rate_limit_exceeded`: honor `Retry-After`
- GPT not calling the action: confirm the imported spec still uses Bearer auth and the GPT has Actions enabled
