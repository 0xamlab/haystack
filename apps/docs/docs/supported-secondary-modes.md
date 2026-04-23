---
sidebar_position: 9
---

# Supported Secondary Modes

The runtime-first story is the primary path, but these supported modes remain part of the product today.

## Simulation workflows

Simulation remains fully implemented and tested:

- `/v1/simulate`
- `/v1/recommend`
- `/v1/jobs`
- simulation-focused SDK and integration flows

## Local helper APIs

`algenta-core` still ships:

- `map_data`
- `query_data`
- `simulate`
- `decision`
- `optimize`
- `forecast`

These remain supported. They are simply not the first examples shown anymore.

## Direct API client

The lower-level direct client remains supported:

```python
from decision_engine import DecisionEngineClient
```

## MCP

MCP remains a broad, production-capable integration layer.
