---
icon: microchip
description: Get the Mojo engine running as a warm worker pool (sidecar) — Docker or from source — confirm it's on the fast path, and fix the build/startup issues you're most likely to hit.
---

# Run the Mojo engine

The **Mojo engine** is the compiled binary (`mojo_build/simulate`) that runs Algenta's simulations. In production the API talks to a **pool of long-lived Mojo workers** over local sockets — the "sidecar" — instead of forking a process per request. Getting that pool up and confirmed-healthy is the single most important step in a self-hosted deployment, and the one most likely to trip you up. This page gets you there.

{% hint style="info" %}
Most users never build the binary: the Docker image **ships it pre-compiled**, so `./install.sh` just works. Build from source only for local engine development or a custom module set (selecting which runtime modules to compile via `MOJO_RUNTIME_MODULE_FILTER`).
{% endhint %}

## Prerequisites

* A self-hosted deployment (see [Self-hosting](../self-hosting.md)), or a local checkout for building from source.
* For source builds: the Mojo toolchain via `pixi` (installed by `make setup-mojo`), `clang`/LLVM, and **plenty of RAM/disk** — a full build is large (see the OOM note below).

## Get the pool running

{% tabs %}
{% tab title="Docker (recommended)" %}
The compiled binary is baked into the image at `/app/mojo_build/simulate`; `MOJO_BINARY_PATH` already points at it. The pool starts with the API — you don't build anything.

```bash title="start.sh"
# the standard self-hosted install brings the API up with the engine pool
curl -sSL https://algenta.ai/install.sh | bash
```

Then jump to **Confirm it's on the fast path** below.
{% endtab %}

{% tab title="Build from source" %}
For a local engine or a custom module set:

```bash title="build-engine.sh"
make setup-mojo     # one-time: install the Mojo toolchain (pixi) into mojo_env/
make build-mojo     # compile mojo/engine → mojo_build/simulate
make test-mojo      # smoke test: runs a simulation, prints engine=<ver> mean=<value>
```

Point the API at the binary and start it:

```bash title="run.sh"
export MOJO_BINARY_PATH="$PWD/mojo_build/simulate"
# start the API (Docker Compose, or your dev server) — the pool spins up on boot
```
{% endtab %}
{% endtabs %}

The pool size defaults to `cpu_count - 1`; set `MOJO_POOL_SIZE` to pin it. On startup the API runs a **server-mode probe** (it computes a known payload and checks the result is correct, not just that a socket opened), then logs `mojo_runtime_mode="pool"` when the real engine is live.

## Confirm it's on the fast path

{% stepper %}
{% step %}
### Check the engine status

```bash title="engine-status.sh"
curl http://localhost:8000/v1/infrastructure
```

Look at `engine_mode`. **`pool`** means the warm Mojo pool is serving requests (what you want). `subprocess_fallback` means it degraded to per-request processes; `unavailable` means no engine.
{% endstep %}

{% step %}
### Run a real simulation and read the mode

```bash title="verify-simulate.sh"
curl -X POST http://localhost:8000/v1/simulate \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"auto","scenario":{"variables":{"x":{"low":50,"high":150}},"objective":"maximize_net_value"},"runs":100,"seed":42}'
```

The response reports `engine_mode`; the result must carry real statistics (a non-zero `summary.mean`).
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `/v1/infrastructure` shows `engine_mode: pool`, the simulate call returns a decision envelope with real stats, and the API logs include `mojo_pool_started` + `mojo_runtime_mode="pool"`. The sidecar engine is live. Full verification options are on [Engine health & verification](health.md).
{% endhint %}

## Fallback policy — fail fast in production

Whether the API may leave the pool is governed by **`RUNTIME_FALLBACK_MODE`**:

| Value | Behavior | Use for |
| --- | --- | --- |
| `deny` | Hard-fail at startup if the pool can't start — never silently degrade | **Production** |
| `allow` | Permit the slower subprocess path when the pool is unavailable | Self-hosted dev |
| `auto` | Fallback allowed only in development | Local development |

`MOJO_ALLOW_SUBPROCESS_FALLBACK=false` additionally forbids the per-request subprocess path. For production, set both so a broken engine surfaces immediately instead of running slow:

```bash title="production.env"
RUNTIME_FALLBACK_MODE=deny
MOJO_ALLOW_SUBPROCESS_FALLBACK=false
MOJO_BINARY_PATH=/app/mojo_build/simulate
MOJO_POOL_SIZE=4
```

## Fix what's most likely to break

{% expandable title="Build runs out of memory / hangs" %}
A full runtime-library build is very large (~17 GB of work). If `make build-mojo` OOMs or hangs, build a **subset** with `MOJO_RUNTIME_MODULE_FILTER` (a comma-separated list of only the modules you need). On Docker, prefer the prebuilt image instead of building in-container.
{% endexpandable %}

{% expandable title="Crash on start / SIGILL on a different machine" %}
A binary compiled with host-native instructions (e.g. AVX-512) **SIGILLs** on a CPU that lacks them (a common cloud cross-build trap). Build a portable binary:

```bash title="portable-build.sh"
MOJO_BUILD_MCPU=x86-64-v3 make build-mojo
```
{% endexpandable %}

{% expandable title="engine_mode is subprocess_fallback (not pool)" %}
The pool failed its probe and the policy allowed degrading. Check the logs for `mojo_server_mode_probe_failed` / `mojo_server_mode_compute_broken` (a stale or broken binary → rebuild with `make build-mojo`) or `mojo_pool_unavailable`. On slow/cold hardware, raise the probe budget: `MOJO_PROBE_SOCKET_TIMEOUT_S` and `MOJO_WORKER_READY_TIMEOUT_S`.
{% endexpandable %}

{% expandable title="Startup fails with the pool required but unavailable" %}
With `RUNTIME_FALLBACK_MODE=deny`, a pool that can't start aborts boot (`mojo_pool_required_unavailable`). That's intended — it means the binary is missing/broken. Confirm `MOJO_BINARY_PATH` exists and `make test-mojo` passes, then restart.
{% endexpandable %}

{% expandable title='"module not registered" / disabled module' %}
The requested simulation engine wasn't compiled into the binary. Either it was filtered out at build time (add it to `MOJO_RUNTIME_MODULE_FILTER`) or you need a full build. List what's compiled in via `GET /v1/runtime/manifest`.
{% endexpandable %}

## Next

{% content-ref url="health.md" %}
[health.md](health.md)
{% endcontent-ref %}

{% content-ref url="../concepts/engine.md" %}
[engine.md](../concepts/engine.md)
{% endcontent-ref %}
