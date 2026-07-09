---
icon: shield-halved
description: Read the engine's live egress policy, tighten it with deployment-mode settings, generate a 24-hour privacy report, and audit the redacted egress decision log.
---

# Audit and tighten egress

Algenta classifies every outbound network request before it is made and records a redacted decision for it. Three admin endpoints let you see and prove that behavior: read the **egress policy** the engine resolved from its configuration, generate a **privacy report** that summarizes the last 24 hours, and page through the **egress log** of individual allow/deny decisions. Together they answer "what is this deployment allowed to reach, and what has it actually reached?"

The policy itself is set through runtime configuration, so tightening it is a configuration change (a deployment mode plus a few overrides), not an API write. These endpoints are how you confirm the change took effect.

{% hint style="info" %}
`GET /v1/admin/egress-policy` requires the **admin** role. The privacy report and egress log read the authenticated org and are available to any authenticated key. All examples send `Authorization: Bearer $ALGENTA_API_KEY`; swap `https://api.algenta.ai` for `http://localhost:8000` on a self-hosted engine.
{% endhint %}

## Read, tighten, and prove the policy

{% stepper %}
{% step %}
### Read the resolved egress policy

Start from the truth the engine is running with. The policy reflects the active deployment mode and every derived default.

```bash title="GET /v1/admin/egress-policy"
curl -sS "https://api.algenta.ai/v1/admin/egress-policy" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The response includes the `deployment_mode`, the raw switches (`disable_cloud`, `disable_telemetry`, `telemetry_mode`, `metering_mode`, `allow_outbound_network`, `require_local_license`, `control_plane_url`, `egress_allowlist`), and the derived, human-readable booleans:

```json title="egress-policy.json"
{
  "deployment_mode": "self_hosted",
  "disable_cloud": true,
  "disable_telemetry": true,
  "telemetry_mode": "local_audit",
  "metering_mode": "local_audit",
  "allow_outbound_network": false,
  "require_local_license": false,
  "control_plane_url": "",
  "egress_allowlist": ["warehouse.internal", "*.db.example.com"],
  "algenta_cloud_enabled": false,
  "vendor_telemetry_enabled": false,
  "customer_connector_egress_enabled": true,
  "undeclared_public_egress_allowed": false,
  "mandatory_heartbeat_enabled": false,
  "metering_flush_enabled": false
}
```

The `privacy_registry` object and the `algenta_owned_hosts` / `vendor_telemetry_hosts` / `private_host_suffixes` lists in the same response tell you exactly which hosts each egress class covers.
{% endstep %}

{% step %}
### Tighten it through configuration

If the policy is looser than you want, change it on the engine host and restart. The single highest-leverage setting is the deployment mode: `self_hosted` and `air_gapped` disable cloud and telemetry and refuse outbound network by default. Layer overrides on top for a specific connector.

```bash title="Lock down outbound network, allow only named hosts"
export ALGENTA_DEPLOYMENT_MODE=self_hosted
export ALGENTA_DISABLE_TELEMETRY=1
# Comma-separated; supports exact host, host:port, and *.suffix wildcards.
export ALGENTA_EGRESS_ALLOWLIST="warehouse.internal,*.db.example.com,minio.local:9000"
```

See [Deployment modes & privacy](../concepts/deployment-modes.md) for how each mode derives its defaults and [Configuration reference](../configuration.md) for every variable.
{% endstep %}

{% step %}
### Generate a privacy report

The report rolls up the egress decisions from the last 24 hours alongside the current policy — a one-call answer for a compliance or audit review.

```bash title="GET /v1/admin/privacy-report"
curl -sS "https://api.algenta.ai/v1/admin/privacy-report" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

```json title="privacy-report.json"
{
  "deployment_mode": "self_hosted",
  "algenta_cloud_enabled": false,
  "vendor_telemetry_enabled": false,
  "customer_connector_egress_enabled": true,
  "undeclared_public_egress_allowed": false,
  "local_license_required": false,
  "local_license_active": false,
  "mandatory_heartbeat_enabled": false,
  "metering_flush_enabled": false,
  "telemetry_mode": "local_audit",
  "metering_mode": "local_audit",
  "algenta_owned_egress_count_24h": 0,
  "blocked_egress_attempt_count_24h": 3,
  "last_outbound_request_at": "2026-07-05T09:12:44Z",
  "last_algenta_owned_egress_at": null
}
```

For a locked-down deployment you want `algenta_cloud_enabled: false` and `algenta_owned_egress_count_24h: 0` — proof the engine has not reached Algenta Cloud.
{% endstep %}

{% step %}
### Audit the egress log

Drill into the individual decisions behind those counts. Each entry is redacted — the destination host is hashed and its display value is coarsened — so the log is safe to export.

```bash title="GET /v1/admin/egress-log"
curl -sS "https://api.algenta.ai/v1/admin/egress-log?page=1&limit=25" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

```json title="egress-log.json"
{
  "entries": [
    {
      "surface": "llm-provider",
      "egress_class": "undeclared_public",
      "destination_host_hash": "9f2c...e1",
      "destination_host_redacted": "*.example.com",
      "decision": "deny",
      "reason": "undeclared_public_egress_disabled",
      "timestamp": "2026-07-05T09:12:44Z",
      "deployment_mode": "self_hosted",
      "service_name": "api-server",
      "request_id": "req_01H..."
    }
  ],
  "total": 3,
  "page": 1,
  "limit": 25,
  "pages": 1
}
```

`page` defaults to `1` and `limit` to `25` (max `100`). `egress_class` is one of `algenta_cloud`, `vendor_telemetry`, `customer_connector`, `operator_service`, or `undeclared_public`; `decision` is `allow` or `deny` with a machine-readable `reason` such as `destination_not_allowlisted` or `destination_allowlisted`.
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — after tightening, `GET /v1/admin/egress-policy` shows `allow_outbound_network: false` with your hosts in `egress_allowlist`, the privacy report shows `algenta_cloud_enabled: false` and `algenta_owned_egress_count_24h: 0`, and any blocked attempts appear in the egress log with `decision: "deny"` and a `reason`.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Pick a privacy profile</strong></td><td>How deployment mode derives cloud, telemetry, and egress defaults.</td><td><a href="../concepts/deployment-modes.md">../concepts/deployment-modes.md</a></td></tr>
<tr><td><strong>Review team audit logs</strong></td><td>Who did what — invites, role changes, and content-hashed artifacts.</td><td><a href="teams-rbac.md">teams-rbac.md</a></td></tr>
<tr><td><strong>Run fully air-gapped</strong></td><td>No outbound network, local-only telemetry and metering.</td><td><a href="../guides/air-gapped.md">../guides/air-gapped.md</a></td></tr>
</tbody></table>
