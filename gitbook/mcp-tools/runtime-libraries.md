---
icon: microchip
description: MCP reference for runtime-library tools — list and execute local runtime-backed Mojo libraries directly, separate from the governed hosted data and query tools.
---

# Runtime library MCP tools

These two tools expose the **local runtime-backed Mojo library** surface: the compiled compute catalog your Algenta engine can execute directly. Unlike the rest of the MCP catalog, they do not route through the hosted `/v1` data and query APIs — they talk to the local Algenta runtime daemon. Reach for them when you need raw runtime-backed compute rather than the governed data, query, or decision tools.

{% hint style="info" %}
Both tools require a running local Algenta runtime. If the daemon is unreachable they return an error telling you to start it first. See [Run the Mojo engine](../engine/mojo-sidecar.md).
{% endhint %}

## Tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `list_runtime_libraries` | List executable local-runtime Mojo libraries and their functions, with runtime health. | `search` (lexical filter over module and function names), `limit` (max libraries after filtering) |
| `execute_runtime_library` | Execute one runtime library function by module and function name. | `module` (required), `function` (required), `args` (object, array, scalar, or null), `request_id` |

## Worked examples

### List the runtime catalog

`list_runtime_libraries` returns the runtime health, a module count, and each library's `name`, `engine`, and `functions`. Pass `search` to filter by module or function name.

{% tabs %}
{% tab title="MCP tool call" %}
```json title="list_runtime_libraries — arguments"
{ "search": "image", "limit": 10 }
```

```json title="list_runtime_libraries — result"
{
  "runtime_health": { "status": "ok" },
  "module_count": 1,
  "libraries": [
    { "name": "image", "engine": "mojo", "functions": ["resize", "decode", "encode"] }
  ]
}
```
{% endtab %}

{% tab title="Prompt" %}
A natural first prompt for an MCP host:

{% hint style="success" %}
List the runtime libraries, then run the `resize` function from the `image` module on my sample payload.
{% endhint %}
{% endtab %}
{% endtabs %}

### Execute a library function

`execute_runtime_library` takes the `module` and `function` names from the catalog above, plus an `args` payload that can be a JSON object, array, scalar, or null. The result reports the return value along with `latency_ms` and which `engine_used` served the call.

{% tabs %}
{% tab title="MCP tool call" %}
```json title="execute_runtime_library — arguments"
{
  "module": "image",
  "function": "resize",
  "args": { "width": 128, "height": 128 },
  "request_id": "req-demo-1"
}
```

```json title="execute_runtime_library — result"
{
  "module": "image",
  "function": "resize",
  "args": { "width": 128, "height": 128 },
  "result": { "width": 128, "height": 128 },
  "latency_ms": 3.1,
  "engine_used": "mojo",
  "success": true
}
```
{% endtab %}

{% tab title="Failure" %}
If the daemon is not running, the tool fails fast rather than silently falling back:

```json title="execute_runtime_library — error"
{ "error": "Local Algenta runtime daemon is unavailable. Start it before using runtime library MCP tools." }
```

A failed execution surfaces the runtime's own error message so you can act on it.
{% endtab %}
{% endtabs %}

## Related references

{% content-ref url="../engine/mojo-sidecar.md" %}
[mojo-sidecar.md](../engine/mojo-sidecar.md)
{% endcontent-ref %}

{% content-ref url="../sdk/mcp.md" %}
[mcp.md](../sdk/mcp.md)
{% endcontent-ref %}
