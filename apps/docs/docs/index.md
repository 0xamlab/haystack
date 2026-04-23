---
slug: /
sidebar_position: 1
---

# Start Here

Algenta is a **deterministic execution layer for structured data**.

This repository currently supports multiple real usage modes, but the primary path we now recommend is:

```python
from algenta import Runtime

rt = Runtime()
plan = rt.resolve({...})
result = rt.query(plan)
```

## Current truth

Algenta today is a hybrid backend/runtime system with:

- deterministic data-runtime queries
- simulation workflows
- local helper APIs
- MCP/agent integration
- local runtime/device flows

## Primary path

The primary published path is:

- `Runtime.connect(...)`
- `Runtime.resolve(...)`
- `Runtime.verify(...)` (optional trust/introspection step)
- `Runtime.query(...)`

This path is strongly tested and benchmarked today.

## Target model

Algenta is converging toward a **local-first deterministic runtime**:

- local execution by default
- optional cloud/API assist
- deterministic `resolve -> query` as the core user model

## Read this next

- [Runtime Quickstart](/quickstart)
- [Connect / Register Sources](/connect-register-sources)
- [Resolve](/resolve)
- [Query](/query)
- [Verify](/verify)
- [How Algenta Works Today](/how-algenta-works-today)
- [Competitor Compatibility](/competitor-compatibility)
- [Trust Model](/trust-model)
- [Supported Secondary Modes](/supported-secondary-modes)
- [Direct API Client](/direct-api-client)
