---
sidebar_position: 6
---

# Local Runtime

Use the hosted control plane with local execution, offline continuity, and an append-only local task ledger.

## What you get

- hosted API-key verification
- a local device license
- a local daemon for execution
- offline history at `~/.algenta/runtime/history.jsonl`

## Step 1: Verify the machine

Run the real local verifier:

```bash
ALGENTA_API_KEY=de_live_... python3 scripts/verify_local_api_key_runtime.py
```

That check performs:

- `/v1/health`
- device-license exchange
- local credit seeding
- daemon start
- one real local execution

## Step 2: Register the machine

```bash
de login de_live_...
```

Or:

```bash
ALGENTA_API_KEY=de_live_... de login
```

## Step 3: Start the runtime

```bash
de runtime start
de runtime status
```

## Step 4: Inspect local history

```bash
de runtime history --limit 20
de runtime history --limit 20 --format json
```

## Python runtime usage

```python
from apps.runtime.sdk import Runtime

rt = Runtime(mode="local", api_key="de_live_...")
result = rt.execute("monte_carlo", "run", {})
print(result["success"], result["engine_used"])
```

## Offline behavior

- First-time hosted registration must succeed
- Offline execution is allowed only from a previously issued valid or grace-period license
- Reconnect updates sync state, not prior local history

## Stop or revoke

```bash
de runtime stop
de logout
```

## Troubleshooting

- `hosted license required`: first-time registration failed
- no local history file: nothing has executed yet
- credits not seeded: rerun the verifier or `de login`
- daemon not running: restart with `de runtime start`
