---
icon: shield-halved
description: Who runs a capability — algenta_managed (the engine executes) vs client_managed (your adapter executes) — and why an unresolved or unsupported owner fails closed.
---

# Execution ownership

Execution ownership is the field on every capability that says **who is allowed to run it**: `algenta_managed`, where the engine executes the work server-side, or `client_managed`, where the engine refuses to run the work and hands it back to a caller-provided **adapter** to execute. It is set per provider profile (`default_execution_owner`) and constrained by what each provider declares it supports (`supported_execution_owners`), then carried on the routed capability and into the execution session. When the owner cannot be honored on a real server-side path, execution **fails closed**: the engine returns a failed session with an explicit error code instead of running the capability on a fallback or guessed path.

## Why it exists

The capability plane routes a single objective across very different providers — governed datasets and Algenta runtime libraries the engine runs itself, alongside MCP tools, skills, and native tools that only the customer's environment can run. Some of those operations have side effects (calling an external system, mutating customer state). The dangerous failure is not an error; it is **silent execution on the wrong actor** — the engine quietly running something it was never meant to run, or returning an empty result that a planner treats as success.

Execution ownership removes that ambiguity. Every capability carries its owner explicitly, and `POST /v1/capabilities/execute` will only run a capability whose owner is `algenta_managed` **and** for which a real server-side path exists. A `client_managed` capability never executes inside the engine — it returns a failed session telling the caller to run it through their adapter. A capability whose type has no Algenta-managed execution path returns a distinct failed session rather than a wrong-path result. There is no default that runs the work anyway.

## The two owners

| Owner | Who executes | What the engine does on `execute` |
| --- | --- | --- |
| `algenta_managed` | The Algenta engine, server-side | Runs the capability if a real path exists (governed dataset summary/schema, runtime-library call, instruction skills/prompts); otherwise returns a failed session |
| `client_managed` | Your adapter, in your environment | Never runs the work; returns a failed session with `client_managed_capability_requires_adapter` so your adapter executes it |

## A concrete example

`execute_capability_service` resolves the capability, opens an execution session, and branches on the owner. A `client_managed` capability fails closed before any provider call:

```python title="apps/api_server/services/capability_plane/_execution.py"
if capability.execution_owner is ExecutionOwner.CLIENT_MANAGED:
    return await _complete_execution_session(
        db, auth,
        session=session,
        capability=capability,
        status=ExecutionSessionStatus.FAILED,
        error={
            "code": "client_managed_capability_requires_adapter",
            "message": (
                "This capability is marked client_managed and must execute "
                "through a customer-provided adapter."
            ),
        },
    )
```

An `algenta_managed` capability whose kind has no server-side path also fails closed rather than running on a guessed path:

```python title="apps/api_server/services/capability_plane/_execution.py"
return await _complete_execution_session(
    db, auth,
    session=session,
    capability=capability,
    status=ExecutionSessionStatus.FAILED,
    error={
        "code": "algenta_managed_capability_not_executable",
        "message": (
            "This capability type does not yet have an Algenta-managed "
            "execution path. Use routeCapabilities() plus the customer "
            "execution node."
        ),
    },
)
```

A failed session surfaces over the API as a normal `200` execution response with `status: "failed"` and a populated `error` object (`code` + `message`); routing-level rejections raise the capability-plane error envelope `{"error": {"code", "message", "details"}}`. The owner-related error codes are:

| Code | When it fires |
| --- | --- |
| `client_managed_capability_requires_adapter` | Owner is `client_managed`; the engine refuses and defers to your adapter |
| `algenta_managed_capability_not_executable` | Owner is `algenta_managed` but the capability kind has no server-side path |
| `preview_capability_not_executable` | A preview dataset capability has no concrete `dataset_id` to run |
| `dataset_execution_requires_governed_query_path` | A dataset operation other than `summary`/`schema` must use the governed query path |
| `runtime_library_metadata_missing` | A runtime-library capability is missing its `module`/`function` metadata |

The set of owners a provider supports is declared up front (`supported_execution_owners` on the provider, `default_execution_owner` on the profile, a non-null `capability_execution_owner` column), so an unsupported or unresolved owner is rejected at configuration time rather than discovered at execution time.

## Use this when

- You are calling `POST /v1/capabilities/execute` and need to know whether the engine will run the capability or hand it back to you.
- You are building the **adapter** that executes `client_managed` capabilities and want the exact deferral contract and error code.
- You routed an objective and the selected capability or a fallback has `execution_owner: client_managed` — that capability must run in your environment.
- You got a failed execution session with `*_not_executable` or `*_requires_adapter` and need to map the code to the right next action.
- You are deciding which provider profile to register and which owners it should support.

## Next

{% content-ref url="capability-plane.md" %}
[capability-plane.md](capability-plane.md)
{% endcontent-ref %}

{% content-ref url="../help/glossary.md" %}
[glossary.md](../help/glossary.md)
{% endcontent-ref %}
