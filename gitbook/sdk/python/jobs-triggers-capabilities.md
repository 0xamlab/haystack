---
icon: diagram-project
description: Python SDK reference for async jobs, deployments, triggers, data sources, and the capability plane — every AlgentaClient method with its endpoint and return type.
---

# Jobs, triggers and capabilities (Python SDK)

This reference covers the `AlgentaClient` methods for long-running work (async jobs and deployments), event-driven automation (triggers and data sources), and the capability plane (providers, bindings, the capability catalog, execution, and skills). Every method is a faithful client over the `/v1` HTTP contract; the async client `AsyncAlgentaClient` exposes the same names to `await`.

```python title="client.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",   # or http://localhost:8000 self-hosted
)
```

## Async jobs

| Method | HTTP | Returns |
| --- | --- | --- |
| `submit_job(request=None, callback_url=None, **kwargs)` | `POST /v1/jobs` | `dict` |
| `get_job(job_id)` | `GET /v1/jobs/{job_id}` | `dict` |
| `get_job_result(job_id)` | `GET /v1/jobs/{job_id}/result` | `dict` |
| `list_jobs(*, page=1, limit=25, status=None)` | `GET /v1/jobs/list` | `dict` |
| `cancel_job(job_id)` | `POST /v1/jobs/{job_id}/cancel` | `dict` |
| `test_webhook_delivery(callback_url)` | `POST /v1/webhooks/test` | `dict` |
| `poll_job(job_id, timeout=300.0, poll_interval=2.0)` | client-side helper | `dict` |

- `submit_job` accepts a job `request` body (or keyword fields) and an optional `callback_url` webhook for completion. It returns immediately with a job id.
- `poll_job` is a convenience loop: it polls `get_job` until the job reaches `completed` (then returns `get_job_result`) or raises if it ends `failed`/`cancelled` or exceeds `timeout`.
- `test_webhook_delivery` sends a test payload to a `callback_url` so you can confirm your endpoint receives deliveries before wiring it to a real job.

## Deployments

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_deployment_regions()` | `GET /v1/deployments/regions` | `DeploymentRegionsResult` |
| `get_deployment()` | `GET /v1/deployments` | `DeploymentResult \| None` |
| `create_deployment(*, provider="algenta_shared", region="algenta-shared", config=None, billing_markup_pct=20.0)` | `POST /v1/deployments` | `DeploymentResult` |
| `delete_deployment(deployment_id)` | `DELETE /v1/deployments/{deployment_id}` | `DeploymentDeleteResult` |
| `get_deployment_cost(deployment_id)` | `GET /v1/deployments/{deployment_id}/cost` | `DeploymentCostResult` |

- `get_deployment` returns your current deployment, or `None` if none exists yet.
- `list_deployment_regions` enumerates the regions you can pass to `create_deployment`.

## Triggers

| Method | HTTP | Returns |
| --- | --- | --- |
| `register_trigger(*, name, condition, simulation_template, webhook_url=None, execution_webhook_url=None, auto_execute=False, description=None)` | `POST /v1/triggers` | `TriggerSummaryResult` |
| `list_triggers(*, status="all", page=None, limit=None)` | `GET /v1/triggers` | `TriggerListResult` |
| `fire_trigger(trigger_id, *, force=False)` | `POST /v1/triggers/{trigger_id}/fire` | `TriggerFireResult` |
| `pause_trigger(trigger_id, *, paused=True)` | `POST /v1/triggers/{trigger_id}/pause` | `TriggerPauseResult` |
| `delete_trigger(trigger_id)` | `DELETE /v1/triggers/{trigger_id}` | `TriggerDeleteResult` |

- `register_trigger` binds a `condition` to a `simulation_template`; when the condition matches, the trigger runs the template and (if `auto_execute=True`) executes the recommended action. `webhook_url` and `execution_webhook_url` receive the results.
- `fire_trigger` runs a trigger on demand; `force=True` runs it even if its condition is not currently met. `pause_trigger` toggles a trigger active/paused via `paused`.

## Data sources

| Method | HTTP | Returns |
| --- | --- | --- |
| `register_source(source=None, *, description=None, **kwargs)` | `POST /v1/sources/register` | `SourceRegistrationResult` |
| `refresh_source(dataset_id)` | `POST /v1/data/{dataset_id}/refresh` | `SourceRegistrationResult` |

- `register_source` registers an external data source (passed as a `source` mapping or keyword fields) as a governed dataset.
- `refresh_source` re-pulls the latest data for an already-registered dataset by its `dataset_id`.

## Capability providers

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_capability_providers()` | `GET /v1/capability-providers` | `list[CapabilityProviderResult]` |
| `get_capability_provider(provider_id)` | `GET /v1/capability-providers/{provider_id}` | `CapabilityProviderResult` |
| `list_mcp_providers()` | `GET /v1/capability-providers` (filtered) | `list[CapabilityProviderResult]` |

- `list_mcp_providers` is a client-side convenience that returns only providers whose `provider_type` is `mcp_provider`.

## Capability bindings

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_capability_bindings(*, provider_id=None, scope=None)` | `GET /v1/capability-bindings` | `list[CapabilityBindingResult]` |
| `create_capability_binding(request)` | `POST /v1/capability-bindings` | `CapabilityBindingResult` |
| `get_capability_binding(binding_id)` | `GET /v1/capability-bindings/{binding_id}` | `CapabilityBindingResult` |
| `update_capability_binding(binding_id, request)` | `PATCH /v1/capability-bindings/{binding_id}` | `CapabilityBindingResult` |
| `delete_capability_binding(binding_id)` | `DELETE /v1/capability-bindings/{binding_id}` | `None` |
| `preview_test_capability_binding(request)` | `POST /v1/capability-bindings/test` | `CapabilityBindingTestResult` |
| `test_capability_binding(binding_id)` | `POST /v1/capability-bindings/{binding_id}/test` | `CapabilityBindingTestResult` |
| `preview_discover_capability_binding(request)` | `POST /v1/capability-bindings/discover` | `CapabilityDiscoverResult` |
| `discover_capability_binding(binding_id)` | `POST /v1/capability-bindings/{binding_id}/discover` | `CapabilityDiscoverResult` |
| `start_capability_authorization(binding_id, request)` | `POST /v1/capability-bindings/{binding_id}/authorize/start` | `CapabilityAuthorizationStartResult` |
| `complete_capability_authorization(binding_id, request)` | `POST /v1/capability-bindings/{binding_id}/authorize/complete` | `CapabilityAuthorizationCompleteResult` |

- The `preview_*` methods validate or discover against an unsaved `request` body; the id-taking variants act on a saved binding.
- `start_capability_authorization` / `complete_capability_authorization` drive an OAuth-style handshake for bindings that need delegated authorization.

## Capability catalog and execution

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_capabilities(*, kinds=None, provider_ids=None, binding_ids=None)` | `GET /v1/capabilities` | `list[CapabilityCatalogEntryResult]` |
| `get_capability(capability_id, *, include_instruction=False)` | `GET /v1/capabilities/{capability_id}` | `CapabilityCatalogEntryResult` |
| `route_capabilities(request)` | `POST /v1/capabilities/route` | `CapabilityRoutePlanResult` |
| `execute_capability(request)` | `POST /v1/capabilities/execute` | `CapabilityExecutionResult` |
| `record_capability_outcome(request)` | `POST /v1/capabilities/outcomes` | `CapabilityOutcomeRecordResult` |

- `route_capabilities` asks the plane which capability best fits an intent; `execute_capability` runs a chosen capability; `record_capability_outcome` reports back how it went, feeding future routing.

## Skills

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_skills()` | `GET /v1/capabilities` (`kinds=["skill"]`) | `list[CapabilityCatalogEntryResult]` |
| `enable_skill(*, skill_name, instruction, description=None, tags=None, artifact_affinities=None, execution_owner="client_managed")` | `POST /v1/capability-bindings` | `CapabilityDiscoverResult` |
| `disable_skill(binding_id)` | `DELETE /v1/capability-bindings/{binding_id}` | `None` |

- `enable_skill` is a shorthand: it creates an instruction-only skill capability binding from your `skill_name` and `instruction`, then discovers it so it is ready to route.
- `disable_skill` removes the skill by deleting its binding.

{% hint style="info" %}
Skills and MCP providers are two views of the same capability plane. `list_skills` and `list_mcp_providers` are convenience filters over `list_capabilities` and `list_capability_providers`; the underlying binding, routing, and execution methods are identical.
{% endhint %}

## Example: submit a job and wait for the result

```python title="submit_and_poll_job.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"], base_url="https://api.algenta.ai")

job = client.submit_job({
    "mode": "auto",
    "scenario": {
        "name": "Fleet reorder",
        "variables": {"demand": {"low": 1000, "high": 4000}},
        "objective": "maximize_net_value",
    },
    "runs": 50000,
})
print(job["job_id"], job["status"])

result = client.poll_job(job["job_id"], timeout=120.0, poll_interval=2.0)
print(result["status"])
```

## Example: route and execute a capability

```python title="route_and_execute_capability.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"], base_url="https://api.algenta.ai")

# Discover what is available, then let the plane pick the best fit.
catalog = client.list_capabilities(kinds=["skill", "tool"])
print(len(catalog), "capabilities")

plan = client.route_capabilities({"objective": "Send a summary to the on-call channel"})
execution = client.execute_capability({
    "capability_id": plan.selected_capability_id,
    "binding_id": plan.selected_binding_id,
    "input": {"message": "3 incidents open; remediation order attached."},
})
client.record_capability_outcome({
    "capability_id": execution.capability_id,
    "provider_id": execution.provider_id,
    "binding_id": execution.binding_id,
    "success": execution.status == "succeeded",
    "result_status": execution.status,
})
```

## Related references

{% content-ref url="account-and-control-plane.md" %}
[account-and-control-plane.md](account-and-control-plane.md)
{% endcontent-ref %}

{% content-ref url="../../guides/async-jobs.md" %}
[async-jobs.md](../../guides/async-jobs.md)
{% endcontent-ref %}

{% content-ref url="../../guides/capabilities.md" %}
[capabilities.md](../../guides/capabilities.md)
{% endcontent-ref %}
