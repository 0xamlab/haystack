---
icon: diagram-project
description: Route an objective to the right capability and execute it through the capability plane, using HTTP, the de CLI, or the Python SDK, with execution ownership made explicit.
---

# Route and execute capabilities

The [capability plane](../concepts/capability-plane.md) is the unified router that turns an objective into the right provider and skill, then executes it. By the end of this guide you will have listed what your organization can do, asked the engine to pick one capability for a plain-language objective, and executed that capability to get a result, all while seeing who runs it. Prerequisites: an API key (see [Authentication](../authentication.md)) and a running engine — the hosted API at `https://api.algenta.ai` or a local server at `http://localhost:8000`. Set `$ALGENTA_BASE_URL` and `$ALGENTA_API_KEY` before you start.

{% hint style="info" %}
Every capability carries an **execution owner**: `algenta_managed` (the engine runs it) or `client_managed` (your own adapter runs it). The route plan and the execution response both report this field, and the plane is fail-closed when ownership cannot be resolved. See [Execution ownership](../concepts/execution-ownership.md).
{% endhint %}

{% stepper %}
{% step %}
### List the providers wired into your organization

A provider is the source of one or more capabilities (an LLM, an optimizer, a data connector, an MCP server). `GET /v1/capability-providers` returns every provider visible to your org, each with the execution owners it supports.

```bash title="list-providers.sh"
curl -s "$ALGENTA_BASE_URL/v1/capability-providers" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Verify: the response is a JSON array. Each entry has a `provider_id`, a `provider_type`, an `active` flag, and a `supported_execution_owners` list. Note one `provider_id` you want to route against.
{% endstep %}

{% step %}
### List the capabilities you can route to

A capability is one discrete operation the plane can execute. `GET /v1/capabilities` returns the unified catalog. Narrow it with repeatable query params: `kinds`, `provider_ids`, and `binding_ids`.

```bash title="list-capabilities.sh"
curl -s "$ALGENTA_BASE_URL/v1/capabilities?provider_ids=provider.skill_pack.algenta" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Verify: each entry has a `capability_id`, a `kind`, a `name`, an `execution_owner`, and an `approval_required` flag. Pick a `capability_id` and confirm its `binding_status` is usable (a quarantined binding will not execute).
{% endstep %}

{% step %}
### Route an objective to one capability

Instead of choosing a `capability_id` yourself, describe the goal in plain language and let the engine pick. `POST /v1/capabilities/route` takes an `objective` plus optional filters (`provider_ids`, `kinds`, `execution_owners`, `tags`, `max_fallbacks`) and returns a deterministic route plan.

```bash title="route.sh"
curl -s -X POST "$ALGENTA_BASE_URL/v1/capabilities/route" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"objective": "summarize the quarterly revenue report", "max_fallbacks": 3}'
```

Verify: the response is a route plan with `selected_capability_id`, `selected_binding_id`, `execution_owner`, `confidence`, `requires_approval`, a human-readable `reason`, and a `fallbacks[]` list of alternatives. Keep `selected_capability_id` and `selected_binding_id` for the next step.
{% endstep %}

{% step %}
### Execute the selected capability

`POST /v1/capabilities/execute` runs one capability. Pass the `capability_id` (and optionally the `binding_id` from the route plan to pin which binding runs it), an `input` object, and a `request_id` for idempotency.

```bash title="execute.sh"
curl -s -X POST "$ALGENTA_BASE_URL/v1/capabilities/execute" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "capability_id": "cap.skill.summarize_revenue",
    "binding_id": "binding-from-route-plan",
    "input": {"document_id": "q3-revenue"},
    "request_id": "run-2026-06-21-001"
  }'
```

Verify: the response carries an `execution_session_id`, the resolved `execution_owner`, a `status`, and either an `output` object (on success) or an `error` object. A `client_managed` capability returns the resolved instruction for your adapter to run rather than a finished `output` — that is expected, not an error.
{% endstep %}

{% step %}
### Drive the same flow from the de CLI

The `de` CLI mirrors the HTTP surface. List and inspect inline; `route` and `execute` read a JSON request body from a file path.

```bash title="cli.sh"
de capabilities providers
de capabilities list

printf '%s' '{"objective": "summarize the quarterly revenue report"}' > route.json
de capabilities route route.json

printf '%s' '{"capability_id": "cap.skill.summarize_revenue", "input": {"document_id": "q3-revenue"}}' > exec.json
de capabilities execute exec.json
```

Verify: `de capabilities route route.json` prints the selected `Capability ID`, and `de capabilities execute exec.json` prints the `Capability ID` plus the execution status. Add `--json` to any command to emit the raw response.
{% endstep %}

{% step %}
### Drive the same flow from the Python SDK

`AlgentaClient` (imported from `decision_engine`) exposes the plane as typed methods. `route_capabilities` and `execute_capability` take a request dict and return parsed result objects.

```python title="capabilities.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url=os.environ.get("ALGENTA_BASE_URL", "http://localhost:8000"),
)

providers = client.list_capability_providers()
print("providers:", [p.provider_id for p in providers])

plan = client.route_capabilities({"objective": "summarize the quarterly revenue report"})
print("selected:", plan.selected_capability_id, "owner:", plan.execution_owner)

result = client.execute_capability({
    "capability_id": plan.selected_capability_id,
    "binding_id": plan.selected_binding_id,
    "input": {"document_id": "q3-revenue"},
})
print("status:", result.status, "session:", result.execution_session_id)
```

Verify: `plan.selected_capability_id` is non-empty and `plan.execution_owner` is `algenta_managed` or `client_managed`; `result.status` reflects the run and `result.execution_session_id` is set.
{% endstep %}
{% endstepper %}

**Expected result**: a route plan that names one `selected_capability_id` with a `confidence` and a `reason`, and an execution response with an `execution_session_id`, the resolved `execution_owner`, and either an `output` or a `client_managed` instruction to run yourself.

## Troubleshooting

* **Empty capability or provider list.** Nothing is bound for your scope yet. Bindings connect a provider profile to your org; without one there is nothing to route to. Confirm with `GET /v1/capability-bindings`.
* **Route returns low confidence or no selection.** The objective did not match an enabled capability. Broaden it, drop restrictive `provider_ids`/`kinds` filters, or raise `max_fallbacks` to surface alternatives.
* **Execution returns an `error` object.** Read the `error` payload on the response. A quarantined binding (`binding_status`) or unresolved execution ownership fails closed by design. A `403`/`401` means the key lacks access — see [API errors](../api/errors.md).
* **`approval_required` is true.** The route plan sets `requires_approval`; high-risk capabilities gate execution behind an approval before they will run.

## Next

{% content-ref url="../concepts/capability-plane.md" %}
[capability-plane.md](../concepts/capability-plane.md)
{% endcontent-ref %}

{% content-ref url="../concepts/execution-ownership.md" %}
[execution-ownership.md](../concepts/execution-ownership.md)
{% endcontent-ref %}

{% content-ref url="connect-data.md" %}
[connect-data.md](connect-data.md)
{% endcontent-ref %}
