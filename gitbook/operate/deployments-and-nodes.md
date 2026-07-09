---
icon: server
description: Provision an isolated cloud deployment across AWS, Azure, or GCP, track its status and monthly cost, and register self-hosted worker nodes that heartbeat into the engine.
---

# Manage deployments and nodes

Algenta can run your org on the shared managed pool or on an **isolated deployment** in your own cloud region. This page covers the deployment lifecycle — list regions, request a deployment, check status, read cost, and deprovision — and how self-hosted **worker nodes** register and heartbeat so they appear in your infrastructure view.

{% hint style="info" %}
Requesting or deprovisioning a deployment requires the **owner** role; reading cost requires **admin**. Listing regions, reading the current deployment, and node registration read the authenticated org. Examples send `Authorization: Bearer $ALGENTA_API_KEY`; swap `https://api.algenta.ai` for `http://localhost:8000` on a self-hosted engine.
{% endhint %}

## Provision and manage a deployment

{% stepper %}
{% step %}
### List providers and regions

Every deployment targets a provider and a region. Fetch the current options first — the `id` fields are what you pass when creating a deployment.

```bash title="GET /v1/deployments/regions"
curl -sS "https://api.algenta.ai/v1/deployments/regions" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The four providers are `algenta_shared` (the default multi-tenant pool, no setup), `aws`, `azure`, and `gcp`, each with a list of regions:

```json title="regions.json"
{
  "providers": [
    { "id": "algenta_shared", "name": "Algenta Managed", "regions": [ ... ] },
    { "id": "aws", "name": "Amazon Web Services", "regions": [ { "id": "us-east-1", "label": "US East (N. Virginia)", "flag": "🇺🇸" } ] },
    { "id": "azure", "name": "Microsoft Azure", "regions": [ ... ] },
    { "id": "gcp", "name": "Google Cloud Platform", "regions": [ ... ] }
  ]
}
```
{% endstep %}

{% step %}
### Request a deployment

Create the deployment with a `provider` and `region`. Optional `config` keys (`instance_size`, `storage_gb`, `max_concurrent_runs`, `auto_scale_max`) size it. The call returns `202 Accepted` immediately — provisioning is asynchronous and typically takes a few minutes.

```bash title="POST /v1/deployments"
curl -sS -X POST "https://api.algenta.ai/v1/deployments" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "aws",
    "region": "us-east-1",
    "config": { "instance_size": "medium", "storage_gb": 100 }
  }'
```

An unknown provider or region returns `422` (`invalid_provider` / `invalid_region`), and an org that already has an active or in-progress deployment returns `409` `deployment_exists` — deprovision the existing one first.
{% endstep %}

{% step %}
### Poll status

Read the org's current deployment. It returns `null` while you are on the shared pool, otherwise the deployment record with its `status`.

```bash title="GET /v1/deployments"
curl -sS "https://api.algenta.ai/v1/deployments" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

```json title="deployment.json"
{
  "deployment_id": "d1e2f3a4-...",
  "org_id": "0123abcd-...",
  "provider": "aws",
  "region": "us-east-1",
  "status": "provisioning",
  "endpoint_url": null,
  "cost_usd_month": 0.0,
  "billable_cost_usd_month": 0.0,
  "billing_markup_pct": 20.0,
  "created_at": "2026-07-05T09:12:44Z",
  "provisioned_at": null,
  "error_message": null
}
```

`status` moves `requested` → `provisioning` → `active`. When it is `active`, `endpoint_url` is populated and your API calls route automatically to the isolated deployment. A failed provision reports `status: "failed"` with an `error_message`.
{% endstep %}

{% step %}
### Read monthly cost

Check the current-month cloud cost for a deployment. `cost_usd_month` is the underlying cloud cost and `billable_cost_usd_month` applies the pass-through `billing_markup_pct`.

```bash title="GET /v1/deployments/{deployment_id}/cost"
curl -sS "https://api.algenta.ai/v1/deployments/$DEPLOYMENT_ID/cost" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The response echoes `provider`, `region`, the current `year` and `month`, both cost figures, the markup percentage, and `last_updated`.
{% endstep %}

{% step %}
### Deprovision

Tear the deployment down and revert the org to the shared pool. Like create, this returns `202` and runs asynchronously.

```bash title="DELETE /v1/deployments/{deployment_id}"
curl -sS -X DELETE "https://api.algenta.ai/v1/deployments/$DEPLOYMENT_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

It responds `{ "status": "deprovisioning", "deployment_id": "..." }`. An already-torn-down deployment returns `409` `already_deprovisioned`; an unknown id returns `404` `not_found`.
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `POST /v1/deployments` returns `202`, `GET /v1/deployments` shows the deployment advancing to `status: "active"` with a populated `endpoint_url`, and `GET /v1/deployments/{deployment_id}/cost` returns the current month's `cost_usd_month` and `billable_cost_usd_month`.
{% endhint %}

## Register self-hosted worker nodes

A self-hosted worker registers with the engine on startup and then heartbeats, so it shows up alongside the primary node in `GET /v1/infrastructure`.

{% stepper %}
{% step %}
### Register the node

Call register on startup. All fields are optional — omit `node_id` and one is generated for you.

```bash title="POST /v1/nodes/register"
curl -sS -X POST "https://api.algenta.ai/v1/nodes/register" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "worker-eu-1",
    "region": "eu-west-1",
    "engine_version": "0.3.1",
    "cpu_count": 8,
    "memory_gb": 32,
    "capabilities": ["large-memory"]
  }'
```

The `201` response returns the `node_id` and confirms where to send heartbeats.
{% endstep %}

{% step %}
### Send heartbeats

Send a heartbeat about every 30 seconds to keep the node live and report its current load. `status` may be `live`, `idle`, `error`, or `updating`.

```bash title="POST /v1/nodes/heartbeat"
curl -sS -X POST "https://api.algenta.ai/v1/nodes/heartbeat" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "worker-eu-1",
    "cpu_pct": 24.1,
    "memory_gb": 3.5,
    "jobs_per_sec": 251.0,
    "status": "live"
  }'
```

A heartbeat for an unregistered node returns `404` `node_not_found`; a node owned by a different org returns `403`.
{% endstep %}

{% step %}
### View infrastructure and deregister

See the primary node plus your registered workers, with live engine health and latency.

```bash title="GET /v1/infrastructure"
curl -sS "https://api.algenta.ai/v1/infrastructure" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Each node reports `node_id`, `status`, `engine_version`, `cpu_pct`, `memory_gb`, `jobs_per_sec`, `region`, and `last_heartbeat`. On graceful shutdown, deregister the node:

```bash title="DELETE /v1/nodes/{node_id}"
curl -sS -X DELETE "https://api.algenta.ai/v1/nodes/worker-eu-1" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `POST /v1/nodes/register` returns `201`, subsequent heartbeats return `{ "node_id": "...", "accepted": true }`, and the node appears in `GET /v1/infrastructure` with a recent `last_heartbeat` and its reported metrics.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Monitor the engine</strong></td><td>Health checks, metrics, and latency for your nodes.</td><td><a href="monitoring.md">monitoring.md</a></td></tr>
<tr><td><strong>Self-host the engine</strong></td><td>Run the runtime and workers on your own infrastructure.</td><td><a href="../self-hosting.md">../self-hosting.md</a></td></tr>
<tr><td><strong>Track plans and usage</strong></td><td>How deployment cost and markup roll into billing.</td><td><a href="../billing.md">../billing.md</a></td></tr>
</tbody></table>
