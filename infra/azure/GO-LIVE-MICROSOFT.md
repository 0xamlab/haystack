# Microsoft / Azure go-live runbook (Algenta Decision Service)

The single owner checklist for taking the Decision Service live on Microsoft Cloud. It ties together
the Entra app, the gateway, and the four listing surfaces, with the **concrete first-party values**
already provisioned. Everything here is **gated on Microsoft Partner Center verification**
(status: **PENDING** — Seville AI Technologies, Inc.); the engineering side is done and tested, so
each step below is one command / one form once verification lands.

> Boundary honesty: M365 / Copilot / Teams / Office / Graph / Entra / Copilot Studio / Power Platform
> are Microsoft-hosted. Only the Decision Service + engine + data plane run in the customer's Azure.
> See `gitbook/integrations/microsoft/entra-sso.md`.

## Provisioned facts (first-party / thyn.ai)

| Thing | Value |
|---|---|
| Decision gateway (Container App) | `algenta-api` · RG `algenta-decision-rg` · sub `fcb473cd-1126-4ba0-a07a-d1b1a1dce688` (tenant `8cc76be1-…`) · ACR `algentadec0fa681.azurecr.io` |
| Gateway public URL | `https://gateway.algenta.ai` (health `/v1/health` 200; agent spec `/openapi/decision-agent.json` 200) |
| Entra app (Decision API + sign-in) | **`3983990d-e9b5-4866-9a43-d52d6e0c20c3`** ("Thyn Accounts Sign-In") in tenant **`7a0cd533-…`** (thyn.ai) |
| App ID URI (audience) | `api://3983990d-e9b5-4866-9a43-d52d6e0c20c3` — the gateway also accepts the bare client id for app-only tokens |
| Delegated scope (employees) | `Decisions.Run` |
| App role (service / managed identities) | `Decisions.Service` |
| Access-token version | v2 (`requestedAccessTokenVersion=2`) |
| Partner Center legal entity | Seville AI Technologies, Inc. — 445 Park Ave Fl 9, New York, NY 10022 · Angel Marinov · angel@thyn.ai |

## ⚠️ Tenant topology — decide before turning Entra on

The gateway's Azure subscription is in tenant `8cc76be1-…`, but the Entra **app + its users + the
`thyn.ai` domain live in tenant `7a0cd533-…`**. The gateway validates the tenant that ISSUES the
tokens, so it must trust `7a0cd533` (where sign-ins happen), **not** its own subscription's tenant.
Today the gateway has `ALGENTA_ENTRA_TENANT_ID=8cc76be1-…` (a leftover) and `ALGENTA_ENTRA_AUDIENCE=""`
(Entra auth is DARK). Fix the tenant when you activate (step 2). For **customer** deployments the app
is multi-tenant — the customer admin-consents it in their tenant and their gateway trusts their tenant.

---

## 1. Entra app — expose the Decision API  ✅ done (idempotent)

Already applied to `3983990d` (App ID URI + `Decisions.Run` + `Decisions.Service`, v2, without
touching `signInAudience` so consumer sign-in keeps working). Re-run any time — it is a no-op once
present:

```bash
infra/azure/entra/configure-decision-api-app.sh                 # first-party app
CONSENT=1 infra/azure/entra/configure-decision-api-app.sh        # also grant tenant admin consent
```

**Verified live:** a real client-credentials token minted for `api://3983990d-…/.default` was accepted
by the engine's `verify_entra_token` (roles `Decisions.Service`, real tenant JWKS). The engine accepts
both `aud` shapes — App ID URI (delegated) and bare client id (app-only) — see PR #356.

## 2. Gateway — turn Entra auth on (currently DARK)

Set both on the `algenta-api` Container App, then it enforces audience + issuer + tenant on the
Decision API:

```bash
az containerapp update -n algenta-api -g algenta-decision-rg \
  --subscription fcb473cd-1126-4ba0-a07a-d1b1a1dce688 \
  --set-env-vars \
    ALGENTA_ENTRA_AUDIENCE="api://3983990d-e9b5-4866-9a43-d52d6e0c20c3" \
    ALGENTA_ENTRA_TENANT_ID="7a0cd533-4d98-450c-bc3a-93cee1495e06"
    # optional: ALGENTA_ENTRA_ALLOWED_TENANTS="<customer tenants,csv>"
```

Provision an `EntraPrincipalMapping` (tenant id + principal oid → org/workspace/role) for each caller
before it can call — see `entra-sso.md` "Map principals to workspaces". Unmapped principals get 403
`entra_principal_not_mapped` (fail-closed).

## 3. Publisher Verification  ⛔ gated on Partner Center (PENDING)

Once Partner Center shows **verified** for Seville AI Technologies, Inc., attach the MPN / Partner One
ID to the app (Entra admin center → App registrations → `3983990d` → Branding & properties → Publisher
verification). `publisherDomain` is already `thyn.ai` (a verified domain). This is what removes the
"unverified publisher" consent warning for customers.

## 4. Listings — one per surface (build now, submit once verified)

### 4a. Azure AI Foundry (agent + tool + evals) — templates ready, pin values
`infra/azure/foundry/` has the agent (`agent-definition/decision-agent.json`), the OpenAPI tool
(`tool-definition/decision-tool.json`), and the eval pack (`evaluations/`). Fill the placeholders:
- `$GATEWAY_HOST` → `gateway.algenta.ai`
- `$GATEWAY_AUDIENCE` → `api://3983990d-e9b5-4866-9a43-d52d6e0c20c3`
- `$AZURE_OPENAI_DEPLOYMENT` → your Azure OpenAI deployment name

The tool auths as `managed_identity`; assign that MI the `Decisions.Service` app role (step 1).

### 4b. Azure Marketplace (managed application) — build the package
`infra/azure/managed-app/` has `createUiDefinition.json` + `viewDefinition.json`. Build the ARM
template from the bicep and zip the package:

```bash
infra/azure/managed-app/build-package.sh   # -> managed-app/dist/algenta-decision-managed-app.zip
```

Upload the zip as the Managed Application package in Partner Center. Customers supply secrets via the
portal form (createUiDefinition), so the package itself carries no `REPLACE_WITH_*` values. (A direct
bicep deploy instead uses `infra/azure/main.parameters.json`, which DOES need the `REPLACE_WITH_*`
values filled.)

### 4c. M365 Copilot / Teams declarative agent
`integrations/microsoft/copilot-agent/`. Fill: `manifest.json` `id` (a new GUID) + `validDomains`
(`gateway.algenta.ai`); `apiPlugin.json` `reference_id` (the Entra OAuth registration id) + spec `url`
(`https://gateway.algenta.ai/openapi/decision-agent.json`). Add `color.png` + `outline.png` icons, zip,
submit to the Teams admin center / AppSource.

### 4d. Excel add-in
`integrations/microsoft/excel-addin/`. Fill: `manifest.xml` `<Id>` (a new GUID), host URLs
(`SourceLocation`, icons) → your static host, `<WebApplicationInfo><Id>` (Entra client id
`3983990d-…`) + `<Resource>` (`api://3983990d-…`). Host `taskpane.html/js` + icons; submit to AppSource.

### 4e. Copilot Studio / Power Platform custom connector
`integrations/microsoft/copilot-studio/` (`apiDefinition.swagger.json` + `apiProperties.json`) — the
decision-agent ops with Entra OAuth. Import with `paconn create` or Power Platform → Custom connectors
→ Import an OpenAPI file. Set the OAuth client id/secret + resource `api://3983990d-…` at import.

## 5. Commercial (separate from Microsoft)
Licensing stays dark/free until the commercial flip; per-device billing is on Stripe (test mode until
the live key swap). Not a Microsoft dependency.

---

### Status at a glance
- ✅ Gateway live; agent spec 200; Entra app exposed + **live-token-tested**; engine accepts both aud shapes.
- ⛔ Publisher Verification + all four listing **submissions** — gated on Partner Center (PENDING).
- ▶️ Owner, once verified: run steps 2–4, attach Publisher Verification, submit each listing.
