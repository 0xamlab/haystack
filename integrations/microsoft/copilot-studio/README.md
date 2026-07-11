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
- `apiDefinition.swagger.json` — **generate from the live gateway** (below). A custom connector is
  Swagger 2.0; the Decision Agent spec is served as OpenAPI 3.0, so it is converted rather than
  hand-maintained (keeps it drift-free against the gateway).

## Generate the connector definition
```bash
# 1. Pull the reduced agent spec (OpenAPI 3.0) from the live gateway:
curl -s https://gateway.algenta.ai/openapi/decision-agent.json -o /tmp/decision-agent.oas3.json

# 2. Convert 3.0 -> Swagger 2.0 (custom connectors are 2.0 only):
npx api-spec-converter --from=openapi_3 --to=swagger_2 /tmp/decision-agent.oas3.json \
  > apiDefinition.swagger.json
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
