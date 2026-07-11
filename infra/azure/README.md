# Algenta Decision Service — guided Azure gateway

Deploys the Algenta Decision Service into **your own Azure subscription** — the customer keeps
the data plane; Algenta provides the software. This is a **guided** deployment: a few steps need
an operator with Owner/Contributor + an Entra admin, because tenant policy, resource-provider
registration, and Entra admin-consent can't be automated from a template.

## What the template creates
`main.bicep` provisions, in one resource group:

- a **user-assigned managed identity** (the app's identity — no long-lived storage/DB secrets),
- **Log Analytics + Application Insights**,
- **Key Vault** (RBAC) holding `config-encryption-key` and `jwt-secret`,
- a **Storage account + `artifacts` blob container** (the native decision-artifact store),
- **PostgreSQL Flexible Server** + the `algenta` database,
- optional **Azure Cache for Redis** (`deployRedis`),
- a **Container App** (the api) wired to the MI, Key Vault secret references, and the Azure Blob
  object store, in the **private profile** (`DISABLE_CLOUD=1`, empty control-plane URL).

The managed identity is granted **Key Vault Secrets User** + **Storage Blob Data Contributor**.
**No admin key is emitted** — first-run onboarding uses a short-lived, Entra-bound handshake.

## Validate (no deploy)
```bash
az bicep build --file main.bicep      # compiles to ARM; catches schema errors
```

## Deploy
```bash
# 1) fill in main.parameters.json (image digest, PG password, config/jwt secrets, Entra ids)
az group create -n algenta-rg -l eastus
az deployment group create -g algenta-rg -f main.bicep -p @main.parameters.json
# gatewayUrl is in the deployment outputs — point the Copilot/Excel/Foundry adapters there.
```

## Owner-only go-live steps (can't be templated — the Phase-0 gate)
1. **Image access** — make the pinned Algenta API image pullable by the Container App
   (public, or grant the MI `AcrPull` on your registry / a GHCR pull secret). Pin by digest.
2. **Entra app registration** — register the gateway API app; expose an app-id-URI or use its
   client id as `ALGENTA_ENTRA_AUDIENCE`; set `ALGENTA_ENTRA_TENANT_ID`. Grant **admin consent**
   for the Copilot/Teams/Excel/Foundry client apps that will call it.
3. **Provision employee/service mappings** — insert rows in `entra_principal_mappings` mapping
   each `(tenant_id, oid)` to an org/workspace + role (an org admin does this).
4. **Resource providers** — ensure `Microsoft.App`, `Microsoft.DBforPostgreSQL`, `Microsoft.Cache`,
   `Microsoft.KeyVault`, `Microsoft.Storage`, `Microsoft.OperationalInsights` are registered.
5. **(Optional) APIM / private networking** — front the Container App with API Management + a WAF,
   or move to VNet-integrated ingress with private endpoints (Phase 2).

## Notes
- The compiled ARM (`main.json`) is a build artifact — generate it with `az bicep build`; it is
  not committed. A "Deploy to Azure" button can point at a released `main.json`.
- Azure OpenAI: deploy an Azure OpenAI resource and point the engine's `openai_compatible`
  backend at it (base URL + key/managed identity) — see the LLM backend docs.
