---
icon: diagram-project
description: TypeScript SDK reference for async jobs, webhook triggers, and the capability plane — submit and poll jobs, register triggers, and route, execute, and bind capabilities.
---

# TypeScript jobs, triggers, and capabilities

This page is the `AlgentaClient` reference for three operational surfaces: **async jobs** (long-running simulations), **triggers** (condition-driven simulations with webhooks), and the **capability plane** (discover, route, and execute tools, skills, and MCP capabilities). Method names are camelCase; request bodies and query parameters stay snake_case, mirroring the [HTTP contract](../../api/overview.md). All examples assume a constructed client:

```ts title="client.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY,
  baseUrl: process.env.ALGENTA_BASE_URL ?? "https://api.algenta.ai",
});
```

## Async jobs

Submit a `SimulateRequest` with `submitJob`, get back a `job_id` and `poll_url`, then either let `pollJob` block until the result is ready or poll `getJob` yourself and fetch `getJobResult` once `status === "completed"`. An optional second argument to `submitJob` is a `callbackUrl` (sent as `callback_url`) for webhook delivery. See the [async jobs guide](../../guides/async-jobs.md).

{% tabs %}
{% tab title="TypeScript" %}
```ts title="async_job.ts"
const job = await client.submitJob(
  {
    mode: "auto",
    scenario: {
      name: "pricing",
      variables: {
        unit_price: { low: 9, high: 19 },
        units_sold: { low: 1000, high: 5000 },
      },
      objective: "maximize_net_value",
    },
    runs: 10_000,
    seed: 42,
  },
  "https://example.com/algenta/webhook", // optional callback_url
);

console.log(job.job_id, job.status, job.poll_url);

// Block until the job finishes.
const result = await client.pollJob(job.job_id, { timeoutMs: 60_000, pollIntervalMs: 1_000 });
console.log(result);
```
{% endtab %}

{% tab title="Manual polling" %}
```ts title="manual_poll.ts"
const status = await client.getJob(job.job_id);
if (status.status === "completed") {
  const payload = await client.getJobResult(job.job_id);
  console.log(payload);
}

const history = await client.listJobs({ page: 1, limit: 25, status: "queued" });
await client.cancelJob(job.job_id);
console.log(history.total);
```
{% endtab %}
{% endtabs %}

Before wiring a callback into production, confirm the engine can reach it with `testWebhookDelivery`, which posts a probe payload and returns `{ success, status_code, message }`:

```ts title="webhook_test.ts"
const probe = await client.testWebhookDelivery("https://example.com/algenta/webhook");
console.log(probe.success, probe.status_code, probe.message);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `submitJob(request, callbackUrl?)` | `POST /v1/jobs` | `request` is a `SimulateRequest`; `callbackUrl` maps to `callback_url`. Returns `job_id`, `status`, `poll_url`. |
| `getJob(jobId)` | `GET /v1/jobs/{job_id}` | Job status (`job_id`, `run_id`, `status`, `poll_url`). |
| `getJobResult(jobId)` | `GET /v1/jobs/{job_id}/result` | The completed result payload. |
| `listJobs(options?)` | `GET /v1/jobs/list` | Paginated history. Options: `page`, `limit`, `status`. |
| `cancelJob(jobId)` | `POST /v1/jobs/{job_id}/cancel` | Cancel a queued or running job. |
| `pollJob(jobId, { timeoutMs, pollIntervalMs })` | polls `GET /v1/jobs/{job_id}` | Resolves to the result once complete; defaults `timeoutMs=300000`, `pollIntervalMs=2000`. |
| `testWebhookDelivery(callbackUrl)` | `POST /v1/webhooks/test` | Probe a callback URL; returns `{ success, status_code, message }`. |

## Triggers

A trigger watches a governed metric and, when its condition is met, runs a simulation template and optionally posts to a webhook. `registerTrigger` takes a `RegisterTriggerRequest` whose `condition` names a `source_id`, a `metric_hint`, a `threshold`, a `direction` (`above`, `below`, or `change`), and an optional `aggregation` (`sum`, `avg`, `max`, `min`, or `count`).

{% tabs %}
{% tab title="TypeScript" %}
```ts title="register_trigger.ts"
const trigger = await client.registerTrigger({
  name: "NPS drop watch",
  condition: {
    source_id: "src_nps_scores",
    metric_hint: "nps_score",
    threshold: 30,
    direction: "below",
    aggregation: "avg",
  },
  simulation_template: {
    mode: "auto",
    scenario: { name: "retention", objective: "maximize_net_value" },
  },
  webhook_url: "https://example.com/algenta/trigger",
  auto_execute: false,
});

console.log(trigger.trigger_id, trigger.status);
```
{% endtab %}

{% tab title="Manage triggers" %}
```ts title="manage_triggers.ts"
const active = await client.listTriggers({ status: "active", page: 1, limit: 25 });
console.log(active.total);

// Evaluate now; `force` runs the simulation even if the condition is not met.
const fired = await client.fireTrigger(trigger.trigger_id, { force: true });
console.log(fired.condition_met, fired.fired, fired.recommended_action);

await client.pauseTrigger(trigger.trigger_id, { paused: true });  // pause
await client.pauseTrigger(trigger.trigger_id, { paused: false }); // resume
await client.deleteTrigger(trigger.trigger_id);
```
{% endtab %}
{% endtabs %}

| Method | HTTP | Notes |
| --- | --- | --- |
| `registerTrigger(request)` | `POST /v1/triggers` | `request` is a `RegisterTriggerRequest` (`name`, `condition`, `simulation_template`, `webhook_url`, `execution_webhook_url`, `auto_execute`, `description`). |
| `listTriggers(options?)` | `GET /v1/triggers` | Options: `status` (`active`, `paused`, `all`), `page`, `limit`. |
| `fireTrigger(triggerId, { force })` | `POST /v1/triggers/{trigger_id}/fire` | Evaluate the condition now; `force` defaults to `false`. |
| `pauseTrigger(triggerId, { paused })` | `PATCH /v1/triggers/{trigger_id}/pause` | Sends `?paused=true|false`; `paused` defaults to `true`. |
| `deleteTrigger(triggerId)` | `DELETE /v1/triggers/{trigger_id}` | Returns `{ trigger_id, deleted: true }`. |

## The capability plane

The capability plane discovers, routes, and executes tools, skills, and MCP capabilities. The everyday path is **route → inspect → execute → record outcome**. `routeCapabilities` takes a `CapabilityRouteRequest` whose `objective` describes the intent and returns a `CapabilityRoutePlan` naming the selected capability and its fallbacks.

{% tabs %}
{% tab title="TypeScript" %}
```ts title="route_execute.ts"
const plan = await client.routeCapabilities({
  objective: "summarize the latest incident report",
});

const capability = await client.getCapability(plan.selected_capability_id, {
  includeInstruction: true,
});

const execution = await client.executeCapability({
  capability_id: capability.capability_id,
  input: {},
});

await client.recordCapabilityOutcome({
  capability_id: capability.capability_id,
  provider_id: capability.provider_id,
  binding_id: capability.binding_id,
  success: execution.status === "completed",
  result_status: execution.status,
});
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/capabilities/route" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "objective": "summarize the latest incident report" }'
```
{% endtab %}
{% endtabs %}

### Providers, bindings, and authorization

Providers expose capabilities; a binding is your configured connection to a provider profile. Create a binding, test it, discover its capabilities, and — for OAuth-style providers — complete an authorization handshake.

```ts title="bindings.ts"
const providers = await client.listCapabilityProviders(); // GET /v1/capability-providers
const mcp = await client.listMcpProviders();              // providers where provider_type === "mcp_provider"

const binding = await client.createCapabilityBinding({
  provider_id: "provider.example",
  profile_id: "profile.example.default",
  binding_name: "My integration",
  scope: "organization", // "user" | "workspace" | "organization"
  execution_owner: "client_managed", // "algenta_managed" | "client_managed"
});

const test = await client.testCapabilityBinding(binding.binding_id);
const discovered = await client.discoverCapabilityBinding(binding.binding_id);
console.log(test.success, discovered.capability_count);

// OAuth-style providers: start, redirect the user, then complete.
const auth = await client.startCapabilityAuthorization(binding.binding_id, {
  redirect_uri: "https://example.com/callback",
});
await client.completeCapabilityAuthorization(binding.binding_id, {
  session_id: auth.session_id,
  authorization_code: "the-code-from-the-callback",
});
```

{% hint style="info" %}
`previewTestCapabilityBinding` and `previewDiscoverCapabilityBinding` run the same test/discover flow from a `CapabilityBindingPreviewRequest` **before** you persist a binding, so you can validate configuration first.
{% endhint %}

### Skills

Skills are instruction-only capabilities. `enableSkill` is a convenience wrapper that creates a skill-pack binding and returns its discovered capabilities; `disableSkill` deletes the binding; `listSkills` filters the catalog to `kind: "skill"`.

```ts title="skills.ts"
const enabled = await client.enableSkill({
  skill_name: "Incident summarizer",
  instruction: "Summarize an incident report into cause, impact, and remediation.",
  tags: ["ops"],
  execution_owner: "client_managed",
});
console.log(enabled.capability_count);

const skills = await client.listSkills(); // listCapabilities({ kinds: ["skill"] })
await client.disableSkill(enabled.binding_id ?? "");
console.log(skills.length);
```

### Capability method reference

| Method | HTTP | Notes |
| --- | --- | --- |
| `listCapabilityProviders()` | `GET /v1/capability-providers` | All providers. |
| `getCapabilityProvider(providerId)` | `GET /v1/capability-providers/{provider_id}` | One provider with its profiles. |
| `listMcpProviders()` | `GET /v1/capability-providers` | Convenience filter for `provider_type === "mcp_provider"`. |
| `listCapabilityBindings(options?)` | `GET /v1/capability-bindings` | Options: `providerId` (→ `provider_id`), `scope`. |
| `createCapabilityBinding(request)` | `POST /v1/capability-bindings` | `request` is a `CapabilityBindingCreateRequest`. |
| `getCapabilityBinding(bindingId)` | `GET /v1/capability-bindings/{binding_id}` | One binding. |
| `updateCapabilityBinding(bindingId, request)` | `PATCH /v1/capability-bindings/{binding_id}` | `request` is a `CapabilityBindingUpdateRequest`. |
| `deleteCapabilityBinding(bindingId)` | `DELETE /v1/capability-bindings/{binding_id}` | Remove a binding. |
| `previewTestCapabilityBinding(request)` | `POST /v1/capability-bindings/test` | Test from a `CapabilityBindingPreviewRequest` before saving. |
| `testCapabilityBinding(bindingId)` | `POST /v1/capability-bindings/{binding_id}/test` | Test a saved binding; returns a `CapabilityBindingTestResult`. |
| `previewDiscoverCapabilityBinding(request)` | `POST /v1/capability-bindings/discover` | Discover from a preview request before saving. |
| `discoverCapabilityBinding(bindingId)` | `POST /v1/capability-bindings/{binding_id}/discover` | Discover a saved binding's capabilities. |
| `startCapabilityAuthorization(bindingId, request)` | `POST /v1/capability-bindings/{binding_id}/authorize/start` | Begin an OAuth-style handshake; returns an `authorize_url`. |
| `completeCapabilityAuthorization(bindingId, request)` | `POST /v1/capability-bindings/{binding_id}/authorize/complete` | Finish the handshake with the callback payload. |
| `listCapabilities(options?)` | `GET /v1/capabilities` | Options: `kinds`, `providerIds` (→ `provider_ids`), `bindingIds` (→ `binding_ids`). |
| `getCapability(capabilityId, { includeInstruction })` | `GET /v1/capabilities/{capability_id}` | `includeInstruction` sends `include_instruction=1`. |
| `routeCapabilities(request)` | `POST /v1/capabilities/route` | `request` is a `CapabilityRouteRequest` (`objective`, filters); returns a `CapabilityRoutePlan`. |
| `executeCapability(request)` | `POST /v1/capabilities/execute` | `request` is a `CapabilityExecutionRequest` (`capability_id`, `binding_id`, `input`, `request_id`). |
| `recordCapabilityOutcome(request)` | `POST /v1/capabilities/outcomes` | Feed results back for learning. |
| `listSkills()` | `GET /v1/capabilities` | `listCapabilities({ kinds: ["skill"] })`. |
| `enableSkill(request)` | `POST /v1/capability-bindings` + discover | Creates a skill-pack binding, then returns its `CapabilityDiscoverResponse`. |
| `disableSkill(bindingId)` | `DELETE /v1/capability-bindings/{binding_id}` | Deletes the skill binding. |

## Related pages

{% content-ref url="../../guides/capabilities.md" %}
[capabilities.md](../../guides/capabilities.md)
{% endcontent-ref %}

{% content-ref url="agent-runs.md" %}
[agent-runs.md](agent-runs.md)
{% endcontent-ref %}

{% content-ref url="account-and-control-plane.md" %}
[account-and-control-plane.md](account-and-control-plane.md)
{% endcontent-ref %}
