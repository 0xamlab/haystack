---
icon: heart-pulse
description: Confirm that the API, dependencies, and bundled compute runtime are healthy through supported HTTP probes.
---

# Engine health & verification

Algenta starts and supervises its bundled runtime as part of the deployment. Health checks verify that integrated service; they are not instructions for managing a second process.

## Health endpoints

| Endpoint | Authentication | Tells you |
| --- | --- | --- |
| `GET /v1/health` | none | API process liveness. |
| `GET /v1/health/ready` | none | Readiness of critical dependencies. A database failure returns `503`. |
| `GET /v1/infrastructure` | API key | Executes a compute probe and reports node status and runtime mode. |
| `GET /v1/runtime/manifest` | API key | Lists the runtime modules included in this deployment. |
| `GET /v1/libraries/health` | API key | Runtime-library health when that optional HTTP surface is enabled. |

## Compute probe

```bash
curl -sS "$ALGENTA_API_URL/v1/infrastructure" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The current contract reports:

| Field | Healthy value | Failure value |
| --- | --- | --- |
| primary node `status` | `live` | `error` |
| `engine_mode` | `binary` | `binary` when the probe failed, or `missing` when the artifact is absent |
| `engine_version` | the executing runtime version | `unknown` when the probe fails |
| `probe_latency_ms` | measured latency of this probe | `null` when the probe fails |
| `uptime_30d_pct`, `avg_latency_ms`, `p95_latency_ms`, `throughput_rpm` | `null`; historical metrics require an external metrics store | `null` |

`engine_mode: "binary"` means the bundled compiled runtime is present; `status: "live"` proves it executed the probe successfully. Treat both fields together as the readiness signal.

## End-to-end smoke test

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/simulate" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"auto","scenario":{"variables":{"demand":{"low":80,"high":120}},"objective":"maximize_margin"},"runs":100,"seed":7}'
```

A successful response contains real summary statistics. Use repeated requests to evaluate warm performance; do not mix image download, service boot, or the first connection into a hot-path latency measurement.

## Failure handling

The production deployment fails closed when its required compute runtime cannot execute. It must not silently route to a Python implementation. If the infrastructure probe reports `missing` or `error`:

1. Confirm the deployment uses a current signed Algenta image or package.
2. Inspect the API startup logs for the first runtime verification or compute error.
3. Redeploy the same integrated service after correcting the artifact or platform mismatch.
4. Rerun both the infrastructure probe and deterministic simulation.

Do not install or operate an additional runtime service beside Algenta.

## Related

{% content-ref url="bundled-runtime.md" %}
[bundled-runtime.md](bundled-runtime.md)
{% endcontent-ref %}

{% content-ref url="../operate/monitoring.md" %}
[monitoring.md](../operate/monitoring.md)
{% endcontent-ref %}
