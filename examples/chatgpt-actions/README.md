# Algenta — ChatGPT Actions

Use the hosted Algenta OpenAPI contract inside ChatGPT Actions.

## Files

- `openapi_actions.yaml` — importable OpenAPI action definition

## Setup

1. Create or edit an Action-enabled GPT.
2. Import `https://api.algenta.ai/openapi.json` or use `openapi_actions.yaml`.
3. Configure auth as `Authorization: Bearer de_live_...`.
4. Start with read-only actions unless you explicitly need dataset mutations.

## First prompt

```text
Should I launch this product if revenue could be $80k-$200k and cost could be $30k-$90k?
```

## Revoke or disconnect

- Remove the imported action from the GPT
- Revoke the Algenta API key if the GPT should no longer have access
