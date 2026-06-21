---
icon: gears
description: How the Algenta engine works — the compiled Mojo binary, the warm worker pool (sidecar), the dispatch and fallback chain, and why it's built for low-latency, deterministic compute.
---

# How the engine works

The engine is the part of Algenta that actually computes — simulations, decisions, and the math/operational library. Understanding its shape explains the operational knobs in [Run the Mojo engine](../engine/mojo-sidecar.md) and why production deployments fail-closed instead of degrading silently.

## The binary

Algenta's compute is a **compiled Mojo binary** (`mojo_build/simulate`), not interpreted Python. That's what makes large Monte Carlo runs fast and **deterministic** — the same inputs and `seed` always produce the same result. The Python API server never does the heavy math itself; it hands work to this binary.

## The warm worker pool (sidecar)

Spawning a process per request is slow (fork/exec ~tens of ms). Instead the API keeps a **pool of long-lived Mojo workers** running in server mode and talks to them over **Unix domain sockets** using a small framed-JSON protocol (a 4-byte length prefix + a JSON payload). A request acquires a free worker, exchanges one round trip (~sub-millisecond IPC), and releases it. The pool self-heals — a crashed worker is detected and restarted.

This is the "sidecar engine": the same machine, a separate set of warm processes beside the API.

## Dispatch and the fallback chain

When a request needs compute, the API tries, in order:

1. **The Mojo worker pool** — the fast path (`engine_mode: pool`).
2. **A subprocess** of the same binary — slower, per-request, only if `MOJO_ALLOW_SUBPROCESS_FALLBACK` permits it (`engine_mode: subprocess_fallback`).
3. **Nothing** — if fallback is denied, the request fails (`engine_mode: unavailable`).

Whether steps 2–3 are even allowed is set by `RUNTIME_FALLBACK_MODE` (`deny` in production). The point of `deny` is honesty: a misbuilt engine should surface at startup, not quietly serve a slow path.

## The server-mode probe

At startup the pool doesn't just check that a worker opened a socket — it sends a **known payload and verifies the answer is correct** (a non-zero, expected mean). This catches the subtle failure where a binary launches but computes garbage (a stale or partial build). Only after the probe passes does the API log `mojo_runtime_mode="pool"` and serve from the pool.

## Use this model when

* **Deciding fallback policy** — production wants `deny` + no subprocess fallback so a broken build can't masquerade as a healthy-but-slow one.
* **Sizing a host** — the pool is `cpu_count - 1` by default; more workers = more concurrency, more memory.
* **Building a custom binary** — only the modules you compile in (via `MOJO_RUNTIME_MODULE_FILTER`) are dispatchable; everything else returns "module not registered".
* **Debugging latency** — if calls are slow, check `engine_mode`; `subprocess_fallback` means you're off the warm path.

## Next

{% content-ref url="../engine/mojo-sidecar.md" %}
[mojo-sidecar.md](../engine/mojo-sidecar.md)
{% endcontent-ref %}

{% content-ref url="../engine/health.md" %}
[health.md](../engine/health.md)
{% endcontent-ref %}
