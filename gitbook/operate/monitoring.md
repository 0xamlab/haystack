---
icon: gauge-high
description: Monitor a self-hosted Algenta deployment — scrape the protected /metrics endpoint, read the engine health signals, tail the structlog JSON logs, all inside your own network.
---

# Monitoring & observability

Algenta exposes everything you need to watch a self-hosted deployment — Prometheus metrics, engine health endpoints, and structured JSON logs — and it keeps all of it inside your network. There is no Sentry, Datadog, PostHog, or OpenTelemetry exporter wired in: observability is self-hosted by design.

The Algenta deployment starts and supervises its bundled compute runtime with the API. There is no separate runtime service to install or start. Use [Engine health & verification](../engine/health.md) when a compute probe is unhealthy.

## What you can observe

| Surface | Endpoint / source | Tells you |
| --- | --- | --- |
| Prometheus metrics | `GET /metrics` | Latency histograms, simulation/error counters, worker restarts. |
| Engine status | `GET /v1/infrastructure` | `engine_mode`, `engine_version`, node health, latency. |
| Liveness | `GET /v1/health` | The API process is up. |
| Readiness | `GET /v1/health/ready` | DB (critical) and Redis (optional) reachability. |
| Logs | stdout (structlog) | Structured per-request events, in JSON in production. |

## Scrape /metrics with Prometheus

The `/metrics` endpoint serves Prometheus exposition text via `prometheus_client`. It is **protected**, with two access paths:

- **Loopback is always allowed.** Requests from `127.0.0.1`, `::1`, or `localhost` are served without a secret — convenient for a scraper on the same host.
- **Remote requests require a secret.** Any non-loopback client must send the header `X-Metrics-Secret` matching the configured secret. If no secret is configured, or the header is missing or wrong, the endpoint returns `403 Forbidden`.

Set the secret via the `METRICS_SECRET` environment variable (settings field `metrics_secret`, default unset). Leaving it unset means the endpoint is loopback-only — no remote scraping is possible.

{% hint style="warning" %}
Treat `METRICS_SECRET` like any other credential. It is the only thing standing between the open internet and your `/metrics` output when the endpoint is reachable off-host.
{% endhint %}

{% stepper %}
{% step %}
### Configure the secret

```bash
export METRICS_SECRET="$(openssl rand -hex 32)"
# restart the API server so the new setting is loaded
```
{% endstep %}

{% step %}
### Verify a manual scrape

From a remote host, pass the secret in the header:

```bash
curl -sS \
  -H "X-Metrics-Secret: $METRICS_SECRET" \
  "$ALGENTA_API_URL/metrics"
```

On the same host you can omit the header entirely:

```bash
curl -sS http://127.0.0.1:8000/metrics
```

**Expected result** — an HTTP `200` with `Content-Type: text/plain; version=0.0.4` and Prometheus exposition lines, for example:

```text
# HELP simulation_duration_seconds End-to-end simulation request latency (server-side only).
# TYPE simulation_duration_seconds histogram
simulation_duration_seconds_bucket{mode="auto",plan="free",le="0.015"} 42.0
simulations_total{mode="auto",plan="free"} 57.0
mojo_worker_restarts_total 0.0
```

A `403 Forbidden` body means the secret is missing or wrong; a connection refused means the server is not listening on that address.
{% endstep %}

{% step %}
### Point Prometheus at it

```yaml
scrape_configs:
  - job_name: algenta
    metrics_path: /metrics
    scheme: https
    static_configs:
      - targets: ["algenta.internal:8000"]
    http_headers:
      X-Metrics-Secret:
        files: ["/etc/prometheus/secrets/algenta_metrics_secret"]
```

{% hint style="info" %}
`/metrics` uses the `X-Metrics-Secret` header, not `Authorization: Bearer`. Put only the secret value in the referenced file and restrict its filesystem permissions. Prometheus versions without custom `http_headers` support must scrape through a same-host collector that reaches the API over loopback.
{% endhint %}
{% endstep %}
{% endstepper %}

## Key metric families

Algenta defines these application metrics (in addition to the default process and Python runtime metrics that `prometheus_client` emits):

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `simulation_duration_seconds` | histogram | `mode`, `plan` | End-to-end simulation request latency (server-side). Drives p50/p95/p99. |
| `mojo_compute_duration_seconds` | histogram | `engine_type` | Mojo engine compute time inside the worker process. |
| `mojo_pool_wait_seconds` | histogram | — | Time spent waiting to acquire a worker from the warm pool. |
| `quota_check_duration_seconds` | histogram | `source` (`redis` / `db`) | Quota-check latency, Redis fast path vs. DB fallback. |
| `simulations_total` | counter | `mode`, `plan` | Total successful simulations. |
| `simulation_errors_total` | counter | `error_type` | Errors by type (`engine_error`, `quota_exceeded`, `rate_limit`). |
| `mojo_worker_restarts_total` | counter | — | Worker process restarts by the health monitor. A rising value signals an unhealthy engine. |

Useful starting queries:

```text
# p95 request latency (seconds)
histogram_quantile(0.95, sum(rate(simulation_duration_seconds_bucket[5m])) by (le))

# error rate by type
sum(rate(simulation_errors_total[5m])) by (error_type)

# worker restarts — should stay flat
increase(mojo_worker_restarts_total[1h])
```

{% hint style="info" %}
`mojo_pool_wait_seconds` climbing while `mojo_compute_duration_seconds` stays low means requests are queuing for licensed workers. Check capacity and edition limits in [Engine health & verification](../engine/health.md) and [Usage & limits](../billing.md).
{% endhint %}

## Check engine health

`GET /v1/infrastructure` is the authoritative engine signal. It runs a minimal probe simulation against the Mojo binary and reports the result.

```bash
curl -sS \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  "$ALGENTA_API_URL/v1/infrastructure"
```

```json
{
  "deployment_mode": "self_hosted",
  "engine_version": "0.3.1",
  "api_version": "1.0.0",
  "nodes": [{ "node_id": "algenta-primary", "status": "live", "region": "us-east-1" }],
  "probe_latency_ms": 8.2,
  "uptime_30d_pct": null,
  "avg_latency_ms": null,
  "p95_latency_ms": null,
  "throughput_rpm": null,
  "engine_mode": "binary",
  "last_health_check": "2026-06-21T12:00:00Z"
}
```

The `engine_mode` field on this endpoint takes one of two values:

| `engine_mode` | Meaning |
| --- | --- |
| `binary` | The compiled Mojo engine binary is present and was probed. |
| `missing` | The required runtime artifact is absent from the deployment. |

A primary node `status` of `error` with `engine_mode: binary` means the bundled runtime exists but the probe simulation failed. Inspect the API logs and redeploy a verified Algenta artifact. `engine_mode: missing` means the deployment artifact is incomplete; do not install a second runtime service. See [Engine health & verification](../engine/health.md).

`probe_latency_ms` is the duration of this request's compute probe. The endpoint returns `null` for 30-day uptime, average latency, p95 latency, and throughput because it has no historical metrics store and does not invent aggregates from one sample. Derive those values from Prometheus over the observation window you need.

For liveness and readiness probes (Kubernetes, Fly, load balancers):

```bash
curl -sS "$ALGENTA_API_URL/v1/health"        # {"status":"ok","timestamp":"…"} — process is up
curl -sS "$ALGENTA_API_URL/v1/health/ready"  # 200 when DB is reachable, 503 otherwise
```

`/v1/health/ready` reports the database as the only critical dependency: a failed DB yields `503`. A missing or failing Redis is reported in the body (`"redis":"down"`) but never fails readiness.

## Read the structlog JSON logs

Algenta logs structured events to **stdout** via structlog. In production (when not in development mode) the renderer is `JSONRenderer`, so each line is a JSON object you can ship to Loki, the ELK stack, or any log pipeline. In development the renderer switches to a human-readable console format.

Every event carries a timestamp (ISO), log level, and logger name. Credential-shaped fields (auth headers, API keys, tokens) are scrubbed by a redaction processor before the line is rendered, so secrets never reach stdout.

```bash
# tail the API server logs and pretty-print with jq
docker logs -f algenta-api 2>&1 | jq -c 'select(.level == "error")'
```

The log level is controlled by the `log_level` setting (for example `info`, `warning`, `error`).

## No phone home

Observability stays inside your network. Algenta does **not** ship logs, metrics, traces, or events to any third party:

- There is no Sentry, Datadog, PostHog, or OpenTelemetry exporter wired into the application. `sentry_dsn` and `otel_exporter_otlp_endpoint` exist only as inert configuration fields and emit nothing.
- The application imports no telemetry/analytics SDK at all — the released product carries no such dependency, and this property is enforced and tested so it cannot regress.
- Metrics are pull-based: Prometheus scrapes `/metrics` from inside your network. Algenta never pushes data out.

You own the entire observability pipeline. See [Configuration](../configuration.md) for every related setting and [Self-hosting](../self-hosting.md) for the deployment topology.

## Next steps

- [Engine health & verification](../engine/health.md) — supported probes for the bundled runtime.
- [Verify the bundled engine](../engine/bundled-runtime.md) — installation contract and deterministic compute check.
- [Configuration](../configuration.md) — `METRICS_SECRET`, `log_level`, and the rest of the observability settings.
- [Self-hosting](../self-hosting.md) — the deployment topology your monitoring stack runs alongside.
