---
icon: shield-halved
description: How ALGENTA_DEPLOYMENT_MODE selects a privacy profile — cloud, telemetry, metering, and egress defaults — and how the engine fails closed on outbound network in air-gapped runs.
---

# Deployment modes & privacy

A **deployment mode** is a single setting — `ALGENTA_DEPLOYMENT_MODE` — that selects a privacy profile for the engine: whether it may reach Algenta Cloud, whether it emits vendor telemetry, how it meters usage, and which outbound destinations are allowed. One value derives a coherent set of defaults so that "private" deployments are private by construction rather than by a checklist of individual flags. The public modes are `saas`, `vpc`, `self_hosted`, `air_gapped`, and `hybrid_provider`.

## Why it exists

Algenta runs in places with very different network trust: a multi-tenant hosted plane, a customer VPC, a fully isolated air-gapped install, and a developer laptop. Rather than ask operators to set a dozen independent booleans correctly, the engine reads one mode and derives the rest. The two private modes — `self_hosted` and `air_gapped` — flip to a `private_profile` that disables cloud, disables telemetry, and refuses outbound network by default. Air-gapped goes further: it requires a local license and forbids any control-plane sync, so a misconfiguration cannot silently phone home. Every outbound request is then classified and checked against the active policy, and denied requests fail closed.

## Example

The privacy profile is derived from the mode. The two private modes set `private_profile = True`, which changes the cloud, telemetry, metering, and outbound-network defaults. Each default can still be overridden by its own environment variable.

| Mode | Default cloud | Default telemetry | Default metering | Default outbound network | Local license |
| --- | --- | --- | --- | --- | --- |
| `saas` | enabled | `control_plane_sync` | `control_plane_sync` | allowed | not required |
| `vpc` | enabled | `control_plane_sync` | `control_plane_sync` | allowed | not required |
| `hybrid_provider` | enabled | `control_plane_sync` | `control_plane_sync` | allowed | not required |
| `self_hosted` | disabled | `local_audit` | `local_audit` | denied | not required |
| `air_gapped` | disabled | `local_audit` | `local_audit` | denied | required |

```bash title="Air-gapped: no outbound network, local-only telemetry and metering"
export ALGENTA_DEPLOYMENT_MODE=air_gapped
# Cloud, telemetry, and outbound network are off by construction.
# control_plane_sync is rejected at startup in this mode:
export ALGENTA_TELEMETRY_MODE=control_plane_sync   # raises air_gapped_control_plane_sync_forbidden
```

Egress is classified before it is allowed. Each outbound destination is classified into one of five classes — `algenta_cloud`, `vendor_telemetry`, `customer_connector`, `operator_service`, or `undeclared_public` — and returns an `allow`/`deny` decision with a reason. In a private profile with `allow_outbound_network=False`, an explicitly configured connector or operator service is still reachable only when its host appears in `ALGENTA_EGRESS_ALLOWLIST`; everything else is denied (`destination_not_allowlisted` or `undeclared_public_egress_disabled`).

```bash title="Allowlisting a private connector under a fail-closed profile"
export ALGENTA_DEPLOYMENT_MODE=self_hosted
# Comma-separated hosts; supports exact host, host:port, and *.suffix wildcards.
export ALGENTA_EGRESS_ALLOWLIST="warehouse.internal,*.db.example.com,minio.local:9000"
```

{% hint style="info" %}
The telemetry and metering modes share the same three values: `disabled`, `local_audit`, and `control_plane_sync`. `local_audit` records usage on the deployment without sending anything outbound; `control_plane_sync` flushes to the control plane and is only effective when outbound network is allowed. A redacted, hashed audit record is produced for every egress decision regardless of mode.
{% endhint %}

## Use this when

- You are choosing how a deployment talks to the network: pick `saas`/`vpc` to use Algenta Cloud, `self_hosted` for an on-prem stack, or `air_gapped` for a fully isolated install.
- You need a private install to be private by default — `self_hosted` and `air_gapped` disable cloud and telemetry and refuse outbound network without per-flag configuration.
- A private connector, warehouse, or operator service is being denied (`destination_not_allowlisted`) and you need to permit exactly that host via `ALGENTA_EGRESS_ALLOWLIST`.
- You are deciding how usage is recorded: `disabled`, `local_audit` on the box, or `control_plane_sync` back to the control plane via `ALGENTA_TELEMETRY_MODE` and `ALGENTA_METERING_MODE`.
- You need operator proof that a deployment is cloud-free for an audit or compliance review.

## Next

{% content-ref url="../self-hosting.md" %}
[self-hosting.md](../self-hosting.md)
{% endcontent-ref %}

{% content-ref url="execution-ownership.md" %}
[execution-ownership.md](execution-ownership.md)
{% endcontent-ref %}
