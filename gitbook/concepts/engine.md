---
icon: gears
description: How Algenta integrates deterministic compiled compute, validates every request, and fails closed without exposing runtime lifecycle to users.
---

# How the engine works

Algenta combines a Python and TypeScript control plane with a compiled Mojo compute runtime. The control plane owns validation, authorization, persistence, and orchestration. The compiled runtime owns deterministic numerical kernels. They ship and operate as one product boundary.

## Integrated compiled compute

The runtime is included in the Algenta deployment and supervised with the API. Hosted users, SDK users, and self-hosted operators do not install or start a separate compute service. A request crosses a typed internal interface, executes in the bundled runtime, and returns a schema-validated result.

This boundary keeps business logic out of Mojo while preserving low-latency numerical execution:

1. The API parses and validates the external request.
2. Authorization and governance checks run before compute.
3. Algenta dispatches the typed payload to the bundled compiled runtime.
4. The runtime returns deterministic output for the same input and seed.
5. The API validates, records, and returns the public response.

## Warm execution

Algenta keeps licensed compute workers warm inside the deployment so repeated calls avoid process-creation overhead. Worker lifecycle, integrity verification, and replacement are implementation responsibilities of Algenta, not user setup steps. Edition limits determine worker concurrency per device.

## Fail-closed behavior

Production execution does not silently switch to an interpreted Python implementation when compiled compute is unavailable. A missing or unhealthy runtime surfaces as an explicit deployment or compute error. This makes a latency regression visible instead of masking it behind a slower implementation.

`GET /v1/infrastructure` reports `engine_mode: "binary"` when the compiled runtime artifact exists and a primary node `status: "live"` when the compute probe succeeds. Treat `missing` or `error` as deployment failures.

## Why this matters

* **Determinism** — identical validated inputs and seed produce identical compute outputs.
* **Performance** — warm compiled workers serve the numerical hot path.
* **Security** — external inputs are validated by the control plane before they reach compute.
* **Operability** — one deployment owns startup, health, and recovery.
* **Auditability** — the API records the request and result contract around each execution.

## Related

{% content-ref url="../engine/bundled-runtime.md" %}
[bundled-runtime.md](../engine/bundled-runtime.md)
{% endcontent-ref %}

{% content-ref url="../engine/health.md" %}
[health.md](../engine/health.md)
{% endcontent-ref %}
