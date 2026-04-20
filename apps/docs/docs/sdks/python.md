---
sidebar_position: 1
---

# Python SDK

## Installation

```bash
pip install decision-engine-sdk
```

## Sync client

```python
from decision_engine import DecisionEngineClient

client = DecisionEngineClient(api_key="de_live_...")

# Simulate
result = client.simulate(
    mode="auto",
    scenario={
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost":    {"low": 30000, "high": 90000},
        },
        "objective": "maximize_net_value",
    },
    seed=42,
)
print(result.recommended_action)   # "proceed"
print(result.confidence)           # 0.82
print(result.metrics.expected_value)  # 105000.0
print(result.result_hash)          # "40a76a11..."

# Recommend
best = client.recommend(actions=[
    {"name": "option_a", "request": {"mode": "auto", "scenario": {...}}},
    {"name": "option_b", "request": {"mode": "auto", "scenario": {...}}},
])
print(best.recommended_action)  # "option_a"

# Score
score = client.score(request={"mode": "auto", "scenario": {...}})
print(score.score)  # 0.74

# Batch
batch = client.batch(items=[...])
print(batch.succeeded)  # 2

# Compare
compare = client.compare(scenarios=[...])
print(compare.winner)  # "low_risk"
```

## Async client

```python
from decision_engine import AsyncDecisionEngineClient
import asyncio

async def main():
    client = AsyncDecisionEngineClient(api_key="de_live_...")
    result = await client.simulate(mode="auto", scenario={...})
    print(result.recommended_action)

asyncio.run(main())
```

## Error handling

```python
from decision_engine.exceptions import (
    QuotaExceededError, RateLimitError,
    AuthenticationError, APIError,
)

try:
    result = client.simulate(...)
except QuotaExceededError as e:
    print(f"Quota exceeded: {e.used}/{e.limit}")
except RateLimitError as e:
    time.sleep(e.retry_after)
except AuthenticationError:
    print("Invalid API key")
except APIError as e:
    print(f"API error {e.status}: {e.code}")
```

## Configuration

```python
client = DecisionEngineClient(
    api_key="de_live_...",
    base_url="https://api.algenta.ai",  # default
    timeout=30,        # seconds
    max_retries=3,     # automatic retry on 5xx/429
)
```

## Verify result integrity

```python
from decision_engine.integrity import verify_result_hash

result = client.simulate(...)
is_valid = verify_result_hash(result)
assert is_valid, "Result has been tampered with!"
```
