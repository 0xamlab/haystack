---
icon: cubes
description: The runtime library surface — list, health-check, and execute individual runtime-backed functions over HTTP, the de CLI, or MCP. Off by default; an operator enables the HTTP routes.
---

# Runtime libraries

Beyond the high-level engines, Algenta can expose its individual **runtime libraries** — the compiled functions that the engines are built from — so you can call one directly. This is the low-level compute surface: you name a `module` and a `function`, pass JSON args, and get the result plus its latency. It is distinct from the governed data and query APIs; nothing here touches a dataset.

There are three ways to reach it: the HTTP routes, the `de` CLI, and the MCP tools. All three run against a live runtime and return the same results.

{% hint style="warning" %}
The HTTP routes (`/v1/libraries*`) are **off by default**. A self-host operator turns them on by setting `ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED=true` in the deployment configuration. If they are disabled, the routes return `404`; use the CLI or MCP tools instead, or ask your operator to enable the HTTP surface. See the [configuration reference](../configuration.md).
{% endhint %}

## HTTP surface

Every route requires a bearer API key and a verified account, and is rate-limited per plan. Base URL is `https://api.algenta.ai` or your own origin such as `http://localhost:8000`.

| Method + path | Purpose |
| --- | --- |
| `GET /v1/libraries` | List executable runtime libraries (paginated, filterable). |
| `GET /v1/libraries/health` | Report whether the runtime is available and how many modules it exposes. |
| `POST /v1/libraries/execute` | Execute one function by `module` + `function`. |

### List libraries

`GET /v1/libraries` returns the modules the runtime exposes, each with its exported functions.

| Query param | Default | Meaning |
| --- | --- | --- |
| `page` | `1` | Page number. |
| `limit` | `50` | Page size (max `200`). |
| `q` | — | Substring filter over module names and exported function names. |

{% code title="List and filter libraries" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/libraries?q=ab_testing&limit=50" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

```json title="Response"
{
  "modules": [
    {
      "name": "ab_testing",
      "engine": "mojo",
      "functions": ["confidence_interval", "sample_size", "significance"]
    }
  ],
  "count": 1,
  "total": 1,
  "page": 1,
  "limit": 50,
  "pages": 1
}
```

Each module carries a `name`, the `engine` that backs it (`mojo` when the runtime is live, `unavailable` otherwise), and its sorted `functions`.

### Check availability

`GET /v1/libraries/health` tells you whether the runtime is executing before you attempt a call.

{% code title="Runtime library health" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/libraries/health" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

```json title="Response"
{
  "status": "ok",
  "engine": "mojo",
  "module_count": 42,
  "runtime_available": true
}
```

When the runtime is not running you get `status: "unavailable"`, `engine: "unavailable"`, and `runtime_available: false`. Execute calls will then fail with a runtime error (see below).

### Execute a function

`POST /v1/libraries/execute` runs a single function.

| Body field | Required | Meaning |
| --- | --- | --- |
| `module` | yes | Runtime module name, e.g. `ab_testing` (dotted names are allowed). |
| `function` | yes | An exported function name from that module. |
| `args` | no | JSON args: an object (kwargs), an array (positional), a scalar, or `null`. |
| `request_id` | no | Caller-supplied idempotency or tracing identifier. |

{% code title="Execute one function" %}
```bash
curl -sS -X POST "$ALGENTA_BASE_URL/v1/libraries/execute" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "module": "ab_testing",
    "function": "sample_size",
    "args": { "baseline_rate": 0.1, "mde": 0.02, "power": 0.8 }
  }'
```
{% endcode %}

```json title="Response"
{
  "module": "ab_testing",
  "function": "sample_size",
  "result": { "per_variant": 3843, "total": 7686 },
  "latency_ms": 4.12,
  "engine_used": "mojo",
  "request_id": "req_..."
}
```

The response echoes the `module` and `function`, returns the `result`, and reports `latency_ms` and the `engine_used`. If you sent a `request_id`, it comes back on the response; otherwise the engine's own request id is used.

### Execute errors

Execution failures use the standard error envelope, with the HTTP status mapped from the failure `code`.

| Status | `code` | Meaning |
| --- | --- | --- |
| 404 | `module_not_registered` | No such module. Check `GET /v1/libraries`. |
| 404 | `function_not_registered` | The module has no such function. |
| 422 | `invalid_arguments` | The `args` shape did not match the function signature. |
| 503 | `compute_runtime_unavailable` | The runtime is not executing; start the runtime worker. |
| 504 | `mojo_library_timeout` | The function ran past its time budget. |
| 502 | (other) | Unexpected runtime error. |

```json title="Error envelope (404)"
{
  "error": {
    "code": "function_not_registered",
    "message": "Function 'sampl_size' is not registered for module 'ab_testing'.",
    "details": {},
    "request_id": "req_..."
  }
}
```

## The `de` CLI

The CLI mirrors the same surface for interactive use. It runs against the local runtime.

| Command | Does |
| --- | --- |
| `de runtime modules` | List available runtime modules. |
| `de runtime functions <module>` | List a module's exported functions. |
| `de runtime execute <module> <function> --args-json '<json>'` | Execute one function. |

{% code title="Execute via the CLI" %}
```bash
de runtime execute ab_testing sample_size \
  --args-json '{"baseline_rate": 0.1, "mde": 0.02, "power": 0.8}'
```
{% endcode %}

## MCP tools

MCP hosts (Claude Desktop, Codex, and other MCP clients) get two matching tools. Both are local/runtime-backed and require the local runtime daemon to be running.

| Tool | Input | Does |
| --- | --- | --- |
| `list_runtime_libraries` | `search` (optional), `limit` (optional) | List runtime modules and their functions. |
| `execute_runtime_library` | `module`, `function`, `args` (optional), `request_id` (optional) | Execute one function. |

`execute_runtime_library` accepts `args` as an object, array, scalar, or `null`, exactly like the HTTP route. If the local runtime daemon is not running, the tool returns an error telling you to start it first — see [Run the Mojo engine](mojo-sidecar.md).

## Related references

- [Configuration reference](../configuration.md) — the toggle that exposes the HTTP routes.
- [Run the Mojo engine](mojo-sidecar.md) — start the runtime that backs these calls.
- [Engine catalog](catalog.md) — the higher-level engines these libraries compose into.
- [MCP server](../sdk/mcp.md) — connect an MCP host to this instance.
