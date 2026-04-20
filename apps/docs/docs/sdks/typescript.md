---
sidebar_position: 2
---

# TypeScript SDK

## Installation

```bash
npm install @decision-engine/sdk
# or
yarn add @decision-engine/sdk
```

## Basic usage

```typescript
import { DecisionEngineClient } from '@decision-engine/sdk'

const client = new DecisionEngineClient({
  apiKey: process.env.DECISION_ENGINE_API_KEY!,
  // baseUrl: 'https://api.algenta.ai',  // default
})

// Simulate
const result = await client.simulate({
  mode: 'auto',
  scenario: {
    variables: {
      revenue: { low: 80000, high: 200000 },
      cost:    { low: 30000, high: 90000 },
    },
    objective: 'maximize_net_value',
  },
  seed: 42,
})

console.log(result.recommended_action)         // "proceed"
console.log(result.confidence)                  // 0.82
console.log(result.metrics.expected_value)      // 105000
console.log(result.result_hash)                 // "40a76a11..."

// Recommend
const best = await client.recommend({
  actions: [
    { name: 'option_a', request: { mode: 'auto', scenario: {...} } },
    { name: 'option_b', request: { mode: 'auto', scenario: {...} } },
  ],
})
console.log(best.recommended_action)  // "option_a"
```

## Expert mode

```typescript
const result = await client.simulate({
  mode: 'expert',
  simulation: {
    variables: [
      { name: 'revenue', distribution: 'normal', params: { mean: 140000, std: 30000 } },
      { name: 'cost',    distribution: 'triangular', params: { low: 30000, mode: 60000, high: 90000 } },
    ],
    correlations: [{ variables: ['revenue', 'cost'], coefficient: 0.3 }],
    objective_function: 'revenue - cost',
    scoring: { expected_value: 0.6, downside_risk: 0.4 },
  },
  runs: 50000,
})
```

## Error handling

```typescript
import { ApiError } from '@decision-engine/sdk'

try {
  const result = await client.simulate({...})
} catch (e) {
  if (e instanceof ApiError) {
    switch (e.status) {
      case 401: console.error('Invalid API key'); break
      case 429: console.error('Rate limited — retry in 60s'); break
      default:  console.error(`API error: ${e.message}`)
    }
  }
}
```

## Environment variables

The SDK reads `NEXT_PUBLIC_DECISION_ENGINE_API_KEY` (Next.js) or `DECISION_ENGINE_API_KEY` (Node.js) automatically:

```typescript
// No apiKey param needed if env var is set
const client = new DecisionEngineClient()
```

## TypeScript types

All types are exported:

```typescript
import type {
  SimulateRequest,
  DecisionEnvelope,
  MetricsSummary,
  PercentileSummary,
} from '@decision-engine/sdk'
```
