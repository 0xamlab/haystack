---
sidebar_position: 10
---

# Direct API Client

Use the direct API client when you want lower-level access to the hosted API.

This is an advanced surface. The primary published path is the runtime-first flow:

- `Runtime.connect(...)`
- `Runtime.resolve(...)`
- optional `Runtime.verify(...)`
- `Runtime.query(...)`

## Python

```bash
pip install algenta-sdk
```

```python
from decision_engine import DecisionEngineClient

client = DecisionEngineClient(api_key="de_live_...")
plan = client.resolve(
    source_name="orders",
    metric="revenue",
    group_by="product_line",
)
verified = client.verify(plan.model_dump())
result = client.query(plan.model_dump())
```

## TypeScript

```bash
npm install decision-engine-sdk
```

```typescript
import { DecisionEngineClient } from 'decision-engine-sdk'

const client = new DecisionEngineClient({
  apiKey: process.env.DECISION_ENGINE_API_KEY!,
})

const plan = await client.resolve({
  source_name: 'orders',
  metric: 'revenue',
  group_by: 'product_line',
})
const result = await client.query(plan)
```

## When to use this surface

Use the direct API client when:

- you want the full API surface
- you need lower-level control than `Runtime`
- you are integrating directly against hosted API behavior
