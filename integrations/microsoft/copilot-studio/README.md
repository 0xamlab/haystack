# Copilot Studio / Power Platform custom connector (Decision Agent)

A Power Platform **custom connector** that exposes the reduced Decision Agent API (the ~10 coarse ops:
`create_or_update_decision`, `run_decision_analysis`, `get_decision_result`, `inspect_decision_evidence`,
`propose_action_plan`, `record_decision_outcome`, …) to **Copilot Studio**, **Power Automate**, and
**Power Apps** — with **Entra (Azure AD) OAuth**, the same audience the gateway enforces.

This is the automation-plane sibling of the M365 Copilot/Teams declarative agent (`../copilot-agent/`)
and the Foundry tool (`../../infra/azure/foundry/tool-definition/`). All three call the **same**
Decision API; only the host wrapper differs.

## Files
- `apiProperties.json` — connection metadata: **Entra OAuth**, `AzureActiveDirectoryResourceId` =
  `api://3983990d-e9b5-4866-9a43-d52d6e0c20c3` (the Decision API audience). Fill
  `clientId` with the connector's own Entra app registration (a client, distinct from the Decision API
  app). `tenantId` is `common` for a multi-tenant connector; pin it to a single tenant for first-party.
- `apiDefinition.swagger.json` — the **Swagger 2.0** connector definition (committed here). A custom
  connector must be OpenAPI 2.0, `< 1 MB`, and use an `https` host — Power Platform does **not** accept
  OpenAPI 3.x. The gateway serves the reduced agent spec as **OpenAPI 3.1.0** over `http://`, so this
  file is derived (not raw-imported): the `http` server becomes `host: gateway.algenta.ai` +
  `schemes: [https]`, `anyOf`/nullable/`components` are flattened to 2.0 `definitions`, and every
  operation carries a certification-clean `summary` (<=80 chars, alphanumeric/parentheses only),
  a full-sentence `description`, and `x-ms-visibility`.

## Regenerate / refresh against the gateway
```bash
# 1. Pull the reduced agent spec from the live gateway (currently OpenAPI 3.1.0):
curl -s https://gateway.algenta.ai/openapi/decision-agent.json -o /tmp/decision-agent.oas.json

# NOTE: api-spec-converter only supports 3.0 -> 2.0, not 3.1. Do not blindly overwrite
# apiDefinition.swagger.json with its output — it drops paths on 3.1 input and re-introduces the
# http:// host, anyOf, and colon/arrow summaries that fail Microsoft certification. Diff any
# regenerated file against the committed one and re-apply the 2.0 fixups above.
```

## Import
```bash
# Power Platform CLI (paconn), or Portal -> Custom connectors -> New -> Import an OpenAPI file:
paconn create --api-def apiDefinition.swagger.json --api-prop apiProperties.json
```
At import, set the OAuth **client id + secret** for the connector app and confirm the resource is
`api://3983990d-e9b5-4866-9a43-d52d6e0c20c3`. Grant the connector app delegated `Decisions.Run` on the
Decision API and admin-consent it. See `../../infra/azure/GO-LIVE-MICROSOFT.md` step 4e and
`gitbook/integrations/microsoft/entra-sso.md`.

> The gateway accepts both the App ID URI and the bare client id as `aud`, so a delegated
> (user) connection and an app-only (service) connection both authenticate against the same audience.
