---
icon: plug-circle-plus
description: Register an external MCP server with Algenta — discover its tools into the unified capability catalog and let the engine call them on your agent's behalf, all under the egress policy.
---

# Connect an external MCP server

Algenta is both an MCP **server** (it exposes its own tools — see [Tool discovery](../sdk/tool-discovery.md)) and an MCP **client**. This guide covers the client side: you register an external [Model Context Protocol](../sdk/mcp.md) server, Algenta discovers its tools into the unified [capability plane](../concepts/capability-plane.md), and the engine calls those tools on your agent's behalf. The external server's tools become first-class capabilities you can route and execute alongside Algenta's own — governed by the same egress policy, with the server's credentials encrypted at rest.

{% hint style="info" %}
Every call to the external server flows through your deployment's egress policy. On a self-hosted or air-gapped deployment, the server's host must be permitted by `ALGENTA_EGRESS_ALLOWLIST` — otherwise discovery fails closed. Link-local / cloud-metadata addresses (e.g. `169.254.169.254`) are always blocked. See [Run air-gapped](air-gapped.md).
{% endhint %}

## How it works

1. **Register** the server as a capability binding (its URL + auth go into the binding, encrypted at rest).
2. **Discover** — Algenta connects over the MCP Streamable HTTP transport, lists the server's tools, and persists each as an `mcp_tool` capability.
3. **Execute** — when you run an `mcp_tool` capability, Algenta proxies the `tools/call` to the external server and returns the result.

Two execution modes:

| `execution_owner` | Behavior |
| --- | --- |
| `algenta_managed` (default) | Algenta **calls** the external tool for you and returns the result. |
| `client_managed` | Algenta only **advertises/routes** the tool; your own execution node calls the server. |

## Register and use it

{% stepper %}
{% step %}
### Register the external MCP server

`POST /v1/capability-bindings` with the generic MCP provider, the server URL, and (optionally) auth. The auth credential is stored **encrypted** and is never returned in any response.

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/capability-bindings" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "provider.mcp.generic",
    "profile_id": "profile.mcp.workspace",
    "binding_name": "Acme tools",
    "scope": "workspace",
    "execution_owner": "algenta_managed",
    "config": {
      "server_url": "https://mcp.acme.internal/mcp",
      "auth": {"type": "bearer", "token": "'"$ACME_MCP_TOKEN"'"}
    }
  }'
```

Keep the returned `binding_id`. `auth.type` may be `bearer` (sends `Authorization: Bearer …`), `api_key` (a header, default `X-API-Key`, override with `auth.header`), or `none`.
{% endstep %}

{% step %}
### Discover its tools

`POST /v1/capability-bindings/{binding_id}/discover` connects to the server, lists its tools, and writes them into the capability catalog as `mcp_tool` capabilities.

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/capability-bindings/$BINDING_ID/discover" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result.** The response reports the discovered tools, and `GET /v1/capabilities` now lists one `mcp_tool` capability per remote tool — each with the tool's name, description, and input schema. If the server's host is not permitted by your egress policy, discovery fails closed with `403 mcp_egress_denied`.
{% endstep %}

{% step %}
### Execute a tool

`POST /v1/capabilities/execute` with the capability id and the tool's arguments. Algenta proxies the call to the external server and returns its result.

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/capabilities/execute" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"capability_id": "'"$CAPABILITY_ID"'", "input": {"arguments": {"query": "acme"}}}'
```

Use `POST /v1/capabilities/route` first if you want the engine to pick the best capability for an intent before executing.
{% endstep %}
{% endstepper %}

## Security model

* **Governed egress.** The server URL is treated as an explicitly-configured customer destination; it is subject to the egress policy and fails closed when not allowlisted on a private profile. Link-local / metadata addresses are blocked outright.
* **Encrypted credentials.** The `auth` block is encrypted at rest (see [Encryption at rest](../operate/byok-kms.md)) and redacted from every binding, catalog, and execution response.
* **Tenant isolation.** A binding is scoped to your organization and workspace; execution re-reads the server URL and auth from your own binding only.
* **Bounded.** Tool counts, response sizes, and pagination are capped so a hostile or oversized server cannot exhaust the engine.

## Next steps

{% content-ref url="../sdk/tool-discovery.md" %}
[tool-discovery.md](../sdk/tool-discovery.md)
{% endcontent-ref %}

{% content-ref url="capabilities.md" %}
[capabilities.md](capabilities.md)
{% endcontent-ref %}

{% content-ref url="../concepts/capability-plane.md" %}
[capability-plane.md](../concepts/capability-plane.md)
{% endcontent-ref %}

{% content-ref url="air-gapped.md" %}
[air-gapped.md](air-gapped.md)
{% endcontent-ref %}
