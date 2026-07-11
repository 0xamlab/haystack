---
icon: microchip
description: Verify the bundled Algenta compute runtime without installing, starting, or managing a separate engine process.
---

# Verify the bundled engine

Algenta owns the complete compute runtime lifecycle. Hosted Algenta already runs it, the self-hosted image contains it, and the standard installer starts it with the API. SDK and MCP users connect to Algenta; they do not install Mojo, a worker package, or a separate engine service.

{% hint style="success" %}
There is no second setup step. If the deployment is healthy, the bundled runtime is already available. If it is unhealthy, repair or redeploy the Algenta installation instead of starting another process.
{% endhint %}

## Installation contract

| Deployment | Runtime responsibility |
| --- | --- |
| Algenta cloud | Algenta operates the runtime. Configure only your API key and base URL. |
| Self-hosted | The signed Algenta image includes the runtime and starts it with the API. |
| Python, TypeScript, Cursor, Codex, or MCP client | The client calls Algenta. No local compute service is required. |

For a new self-hosted deployment, use the normal installer:

```bash
curl -sSL https://algenta.ai/install.sh | bash
```

The installer brings up the complete stack. It does not hand the runtime lifecycle back to the user.

## Verify the deployment

Check liveness first:

```bash
curl -sS "$ALGENTA_API_URL/v1/health"
```

Then ask the authenticated infrastructure endpoint to run its compute probe:

```bash
curl -sS "$ALGENTA_API_URL/v1/infrastructure" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

A healthy response has a primary node with `status: "live"` and `engine_mode: "binary"`. The endpoint executes a known payload; it does not report healthy merely because a file exists.

| Signal | Meaning | Action |
| --- | --- | --- |
| `status: "live"`, `engine_mode: "binary"` | The bundled compiled runtime executed the probe. | None. |
| `status: "error"` | The runtime was present but the compute probe failed. | Inspect deployment logs and redeploy a verified Algenta image. |
| `engine_mode: "missing"` | The deployment artifact does not contain the required runtime. | Replace the image or package; do not install a separate component. |

## Verify real compute

Run one deterministic simulation through the same public API your application uses:

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/simulate" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"auto","scenario":{"variables":{"x":{"low":50,"high":150}},"objective":"maximize_net_value"},"runs":100,"seed":42}'
```

The response must contain computed statistics and no fallback or unavailable error. Measure warm latency only after at least one successful request; installation and process startup are cold-path work.

## Related

{% content-ref url="health.md" %}
[health.md](health.md)
{% endcontent-ref %}

{% content-ref url="../self-hosting.md" %}
[self-hosting.md](../self-hosting.md)
{% endcontent-ref %}
