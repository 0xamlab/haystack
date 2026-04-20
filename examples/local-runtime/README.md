# Algenta — Local Runtime

Use the hosted control plane with local execution and offline task history.

## First proof

```bash
ALGENTA_API_KEY=de_live_... python3 scripts/verify_local_api_key_runtime.py
```

## Register and start

```bash
de login de_live_...
de runtime start
de runtime status
```

## Inspect local history

```bash
de runtime history --limit 20
```

The append-only ledger lives at:

```text
~/.algenta/runtime/history.jsonl
```

## Stop or revoke

```bash
de runtime stop
de logout
```
