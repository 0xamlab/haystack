---
sidebar_position: 6
---

# Local Runtime

There are two related but different local-runtime stories in this repository.

## 1. Primary local runtime: `algenta.Runtime`

This is the default local-first path and the one we recommend first.

```python
from algenta import Runtime

rt = Runtime()
rt.connect("orders.csv", name="orders")
plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)
```

This path:

- runs locally
- requires no API key
- is the primary docs and SDK path
- supports local CSV, JSON, in-memory records, and deterministic SQLite descriptors on Python today
- remains outside the hosted device-license and credit-bucket enforcement path unless you explicitly opt into hosted local mode

## 2. Hosted control plane with local execution

This repo also supports a more advanced runtime/device flow where the hosted control plane verifies the machine and a local daemon performs execution.

Use this when you need:

- hosted API-key verification
- local device licensing
- daemon-managed local execution
- local task history

### Verify the machine

```bash
ALGENTA_API_KEY=de_live_... python3 scripts/verify_local_api_key_runtime.py
```

If you already have a stored device license from that advanced path, the public runtimes can also execute locally with hosted enforcement enabled.

Python:

```python
from algenta import Runtime

rt = Runtime(api_key="de_live_...")
rt.connect("orders.csv", name="orders")
plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)
```

TypeScript:

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime({ apiKey: process.env.ALGENTA_API_KEY });
await rt.connect("orders.csv", { name: "orders" });
const plan = await rt.resolve({ source_name: "orders", metric: "revenue" });
const result = await rt.query(plan);
```

For local database-backed development, the public runtimes now diverge slightly:

- Python local mode supports deterministic SQLite descriptors directly
- TypeScript local mode also supports SQLite descriptors when the active Node runtime exposes `node:sqlite`

That keeps execution local while enforcing the stored local device license and local credit bucket offline.

### Start the daemon runtime

```bash
de runtime start
de runtime status
```

### Inspect local runtime history

```bash
de runtime history --limit 20
```

## What this page proves

- The simple primary local runtime exists in `algenta-core`
- The more advanced hosted-control-plane local runtime also exists in this repo
- These are both real, but they are not the same surface

The docs now lead with the simpler `Runtime.resolve() -> Runtime.query()` story and keep the daemon/device path as an advanced operating mode.
