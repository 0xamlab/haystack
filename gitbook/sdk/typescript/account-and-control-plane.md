---
icon: gear
description: TypeScript SDK reference for the account and control plane — identity, usage, limits, billing, API keys, team, devices, audit logs, execution policy, deployments, health, and version.
---

# TypeScript account and control plane

This page is the `AlgentaClient` reference for administering your organization: who you are, what you've used, your API keys, teammates, devices, audit trail, execution policy, and managed deployments — plus health and version probes. Method names are camelCase; request bodies and query parameters stay snake_case, mirroring the [HTTP contract](../../api/overview.md). All examples assume a constructed client:

```ts title="client.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY,
  baseUrl: process.env.ALGENTA_BASE_URL ?? "https://api.algenta.ai",
});
```

## Identity and usage

`me` returns your user and organization; `updateMe` edits your display name or org name; `usage`, `limits`, `distributions`, and `templates` describe what your plan allows and what the engine supports.

{% tabs %}
{% tab title="TypeScript" %}
```ts title="identity.ts"
const me = await client.me();
console.log(me.user.email, me.org.name, me.org.plan);

await client.updateMe({ name: "Ada Lovelace", org_name: "Analytical Engines" });

const usage = await client.usage();
console.log(usage.simulations_run, usage.api_calls, usage.quota_used_pct);

const limits = await client.limits();
console.log(limits.plan, limits.rate_limit_per_minute);
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/me" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

```ts title="catalogs.ts"
const distributions = await client.distributions(); // supported probability distributions
const templates = await client.templates();         // ready-made simulation templates
console.log(distributions.total, templates.total);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `me()` | `GET /v1/me` | Current user and organization. |
| `updateMe(request)` | `PATCH /v1/me` | `UpdateMeRequest` (`name`, `org_name`). |
| `usage()` | `GET /v1/usage` | Simulations run, API calls, quota usage. |
| `limits()` | `GET /v1/limits` | Unlimited execution policy, request-shape bounds, and worker capacity. |
| `distributions()` | `GET /v1/distributions` | Supported distributions with example params. |
| `templates()` | `GET /v1/templates` | Simulation templates with example requests. |

## Billing and credits

`getBillingInfo` reports the current plan and subscription; `createBillingCheckout` and `createBillingPortal` return a hosted `url` to redirect to. `refreshCredits` and `ingestMeteringEvents` are generic managed-runtime compatibility methods. Self-hosted Algenta does not use them for billing or enforcement.

```ts title="billing.ts"
const billing = await client.getBillingInfo();
console.log(billing.plan, billing.subscription_status);

const checkout = await client.createBillingCheckout({ plan: "pro" }); // "developer" | "pro"
const portal = await client.createBillingPortal();
console.log(checkout.url, portal.url);
```

```ts title="metering.ts"
const credits = await client.refreshCredits({
  device_id: "device-abc",
  billing_period: "2026-07",
});
console.log(credits.monthly_remaining);

const flushed = await client.ingestMeteringEvents({
  device_id: "device-abc",
  events: [{ event_type: "simulate", engine_used: "mojo", latency_ms: 8, success: true }],
});
console.log(flushed.accepted, flushed.billing_period);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `getBillingInfo()` | `GET /v1/billing/info` | Plan, subscription status, current period end. |
| `createBillingCheckout(options?)` | `POST /v1/billing/checkout` | `plan` is `developer` or `pro`; returns a hosted `url`. |
| `createBillingPortal()` | `POST /v1/billing/portal` | Returns the billing-portal `url`. |
| `refreshCredits(request)` | `POST /v1/credits/refresh` | `CreditRefreshRequest` (`device_id`, `billing_period`, `credits_used`). |
| `ingestMeteringEvents(request)` | `POST /v1/metering` | `MeteringBatchRequest` (`device_id`, `events`); returns `{ accepted, billing_period }`. |

## API keys

Create scoped keys, list them, and revoke them. The raw secret is returned exactly once, on creation, as `raw_key`.

{% hint style="warning" %}
`createApiKey` returns `raw_key` only in the create response. Store it immediately in a secrets manager — you cannot retrieve it again, and later calls only expose the `key_prefix`.
{% endhint %}

```ts title="api_keys.ts"
const created = await client.createApiKey({
  label: "ci-pipeline",
  device_limit: 5,
});
console.log(created.raw_key); // shown once — store it now

const keys = await client.listApiKeys();
console.log(keys.map(k => `${k.label} (${k.key_prefix})`));

await client.revokeApiKey(created.id);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `listApiKeys()` | `GET /v1/api-keys` | All keys with `key_prefix`, `status`, and timestamps. |
| `createApiKey(request)` | `POST /v1/api-keys` | `CreateAPIKeyRequest` (`label`, `expires_at`, `device_limit`); returns `raw_key` once. |
| `revokeApiKey(keyId)` | `DELETE /v1/api-keys/{key_id}` | Revoke a key. |

## Team

Invite teammates, list members, change roles, and remove people. Roles are `owner`, `admin`, `member`, or `viewer`.

```ts title="team.ts"
const invite = await client.inviteTeamMember({ email: "sam@example.com", role: "member" });
console.log(invite.invite_id);

const members = await client.listTeamMembers({ page: 1, limit: 25 });
console.log(members.total);

await client.updateTeamMemberRole(members.members[0].user_id, "admin");
await client.removeTeamMember(members.members[0].user_id);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `listTeamMembers(options?)` | `GET /v1/team` | Options: `page`, `limit`. |
| `inviteTeamMember(request)` | `POST /v1/team/invite` | `TeamInviteRequest` (`email`, `role`). |
| `updateTeamMemberRole(userId, role)` | `PATCH /v1/team/{user_id}/role` | `role` is `owner`, `admin`, `member`, or `viewer`. |
| `removeTeamMember(userId)` | `DELETE /v1/team/{user_id}` | Remove a member. |

## Devices

List devices bound to your keys and revoke a device registration.

```ts title="devices.ts"
const devices = await client.listDevices({ page: 1, limit: 25 });
console.log(devices.device_count, "of", devices.device_limit, "on plan", devices.plan);

const registration = devices.devices[0];
if (registration) {
  const revoked = await client.revokeDevice(registration.id);
  console.log(revoked.revoked, revoked.registration_id);
}
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `listDevices(options?)` | `GET /v1/device/list` | Options: `page`, `limit`. Reports `device_count`, `device_limit`, `plan`. |
| `revokeDevice(registrationId)` | `DELETE /v1/device/{registration_id}` | Revoke one device registration. |

## Audit logs

Read the tamper-evident audit trail, filtered by actor, action, resource, result, or provenance hashes. `getAuditLogArtifacts` adds a `content_hash` filter for artifact-level entries.

```ts title="audit.ts"
const logs = await client.getAuditLogs({
  page: 1,
  limit: 50,
  action: "capability.execute",
  result: "success",
});
console.log(logs.total, logs.entries[0]?.actor_email);

const artifacts = await client.getAuditLogArtifacts({
  content_hash: "sha256:...",
  resource_type: "agent_run",
});
console.log(artifacts.entries.length);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `getAuditLogs(options?)` | `GET /v1/audit-logs` | Filters: `actor_email`, `action`, `resource_type`, `result`, `policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`, `request_hash`, plus pagination. |
| `getAuditLogArtifacts(options?)` | `GET /v1/audit-logs/artifacts` | Same filters as above plus `content_hash`. |

## Execution policy

The execution policy gates which decisions the engine may act on. Read the current policy, list its immutable snapshots, and update it — every change creates a new snapshot.

```ts title="execution_policy.ts"
const policy = await client.getExecutionPolicy();
console.log(policy.min_confidence, policy.allow_reexecution, policy.snapshot_id);

const updated = await client.updateExecutionPolicy({
  min_confidence: 0.8,
  require_calibration: true,
  allow_reexecution: false,
});
console.log(updated.snapshot_id, updated.revision);

const snapshots = await client.listExecutionPolicySnapshots();
console.log(snapshots.total_snapshots);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `getExecutionPolicy()` | `GET /v1/execution/policy` | Current policy and its `snapshot_id`. |
| `listExecutionPolicySnapshots()` | `GET /v1/execution/policy/snapshots` | Full snapshot history. |
| `updateExecutionPolicy(request)` | `PATCH /v1/execution/policy` | `UpdateExecutionPolicyRequest` (`min_confidence`, `risk_floor`, `require_calibration`, `allow_reexecution`). |

## Deployments

List regions, read your managed deployment, create or delete one, and read its cost breakdown. `getDeployment` returns `null` when no deployment exists.

```ts title="deployments.ts"
const regions = await client.listDeploymentRegions();
console.log(regions.providers.map(p => p.id));

let deployment = await client.getDeployment();
if (deployment === null) {
  deployment = await client.createDeployment({ provider: "fly", region: "iad" });
}
console.log(deployment.deployment_id, deployment.status, deployment.endpoint_url);

const cost = await client.getDeploymentCost(deployment.deployment_id);
console.log(cost.year, cost.month, cost.provider, cost.region);

await client.deleteDeployment(deployment.deployment_id);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `listDeploymentRegions()` | `GET /v1/deployments/regions` | Providers and their regions. |
| `getDeployment()` | `GET /v1/deployments` | Your deployment, or `null`. |
| `createDeployment(request?)` | `POST /v1/deployments` | `CreateDeploymentRequest` (`provider`, `region`, `config`, `billing_markup_pct`). |
| `deleteDeployment(deploymentId)` | `DELETE /v1/deployments/{deployment_id}` | Tear down a deployment. |
| `getDeploymentCost(deploymentId)` | `GET /v1/deployments/{deployment_id}/cost` | Cost breakdown for a deployment. |

## Health and version

Unauthenticated liveness and build-version probes.

```ts title="health.ts"
const health = await client.health();   // { status, timestamp }
const version = await client.version();  // { api_version, engine_version, environment }
console.log(health.status, version.api_version, version.engine_version);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `health()` | `GET /v1/health` | `{ status, timestamp }`. |
| `version()` | `GET /v1/version` | `{ api_version, engine_version, environment }`. |

## Related pages

{% content-ref url="../../authentication.md" %}
[authentication.md](../../authentication.md)
{% endcontent-ref %}

{% content-ref url="jobs-triggers-capabilities.md" %}
[jobs-triggers-capabilities.md](jobs-triggers-capabilities.md)
{% endcontent-ref %}

{% content-ref url="../typescript.md" %}
[typescript.md](../typescript.md)
{% endcontent-ref %}
