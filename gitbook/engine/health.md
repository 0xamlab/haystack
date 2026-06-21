---
icon: heart-pulse
description: Confirm the Algenta engine is healthy and actually running on the warm Mojo pool — the health endpoints, the engine_mode signal, the smoke test, the log events, and every pool tuning knob.
---

# Engine health & verification

How to prove the engine is up, fast, and computing correctly — and the knobs to tune it. Use this after [Run the Mojo engine](mojo-sidecar.md) and whenever a deployment behaves unexpectedly.

## Health endpoints

| Endpoint | Tells you |
| --- | --- |
| `GET /v1/health` | Liveness — `{"status":"ok","timestamp":"…"}`. The API process is up. |
| `GET /v1/infrastructure` | Engine status: `engine_mode`, `engine_version`, last health check. The authoritative engine signal. |
| `GET /v1/runtime/manifest` | Which runtime-library modules are compiled into the binary (verify a filtered build). |
| `GET /v1/libraries/health` | Module health snapshot — **only when `ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED=1`** (404 otherwise). |

## The `engine_mode` signal

`GET /v1/infrastructure` and every simulate response report `engine_mode`:

| `engine_mode` | Meaning |
| --- | --- |
| `pool` | The warm Mojo worker pool is serving requests — the fast path. **This is the goal.** |
| `subprocess_fallback` | Degraded: a Python/subprocess path is serving because the pool was unavailable and the policy allowed it. |
| `unavailable` | No engine — requests that need it fail (expected under `RUNTIME_FALLBACK_MODE=deny`). |

## Smoke test

```bash title="smoke.sh"
make test-mojo
# parses a payload, runs simulate, prints: engine=<version> mean=<value>
```

A non-zero `mean` confirms the binary actually computes (not just that it launches). Pair it with a live call:

```bash title="live-check.sh"
curl http://localhost:8000/v1/infrastructure        # expect engine_mode: pool
curl http://localhost:8000/v1/runtime/manifest      # expect your modules listed
```

## Log events to watch

The API logs (structlog) make the startup decision explicit:

| Event | Meaning |
| --- | --- |
| `mojo_pool_started` / `mojo_pool_ready` | Pool initialized; workers ready. |
| `mojo_runtime_mode` (`pool` \| `subprocess_fallback`) | The mode actually selected at startup. |
| `mojo_server_mode_probe_retry` | Probe failed once, retrying — usually system load on a cold start. |
| `mojo_server_mode_probe_failed` / `mojo_server_mode_compute_broken` | The binary launches but can't compute correctly → rebuild (`make build-mojo`). |
| `mojo_pool_unavailable` | Pool failed; degraded to subprocess (policy permitting). |
| `mojo_pool_required_unavailable` | Pool failed and fallback is denied → startup aborts (intended in production). |

## Tuning knobs

All optional; defaults are sized for a typical host. Times are seconds (float).

| Variable | Default | What it controls |
| --- | --- | --- |
| `MOJO_BINARY_PATH` | `./mojo_build/simulate` | Where the compiled engine lives. |
| `RUNTIME_FALLBACK_MODE` | `auto` | `deny` (prod, no fallback) · `allow` · `auto` (dev only). |
| `MOJO_ALLOW_SUBPROCESS_FALLBACK` | `true` | Permit the per-request subprocess path; set `false` in prod. |
| `MOJO_POOL_SIZE` | `cpu_count - 1` | Number of warm worker processes. |
| `MOJO_ACQUIRE_TIMEOUT_S` | `10` | Max wait to acquire a free worker. |
| `MOJO_COMPUTE_TIMEOUT_S` | `60` | Max time for one computation. |
| `MOJO_WORKER_READY_TIMEOUT_S` | `5` | Max time for a worker to create its socket. |
| `MOJO_PROBE_SOCKET_TIMEOUT_S` | `30` | Health-probe socket budget (raise on slow/cold hosts). |
| `MOJO_PROBE_FRAME_TIMEOUT_S` | `10` | Health-probe I/O budget. |
| `MOJO_PROBE_ATTEMPTS` | `3` | Server-mode validation retries. |

{% hint style="warning" %}
In production, set `RUNTIME_FALLBACK_MODE=deny` **and** `MOJO_ALLOW_SUBPROCESS_FALLBACK=false`. Otherwise a broken engine silently serves the slow path and you won't notice until latency complaints arrive.
{% endhint %}

## Related

{% content-ref url="mojo-sidecar.md" %}
[mojo-sidecar.md](mojo-sidecar.md)
{% endcontent-ref %}

{% content-ref url="../troubleshooting.md" %}
[troubleshooting.md](../troubleshooting.md)
{% endcontent-ref %}
