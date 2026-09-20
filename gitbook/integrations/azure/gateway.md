---
icon: cloud
description: Deploy the Algenta gateway into your own Azure subscription with a guided Bicep template that keeps the runtime and data plane customer-hosted with cloud features off
---

# Deploy the decision gateway to your Azure

This is a **guided** deployment: you run the Algenta gateway inside your **own Azure subscription**, so the data plane stays with you and Algenta only supplies the software. A single deployment template (Bicep) stands up the whole gateway in one resource group, and a small parameters file supplies your image reference, database credentials, and secrets.

It is guided rather than one-click on purpose. A few steps need an operator with Owner or Contributor rights plus an Entra administrator, because tenant policy, Azure resource-provider registration, and Entra admin consent cannot be driven from a template.

## What the deployment provisions

In one resource group, the deployment template creates:

- A **Container App** running the decision runtime in a **private profile** with cloud features disabled — cloud egress and telemetry are turned off and the control-plane URL is empty, so decisions are computed in your Azure decision plane.
- **Azure Database for PostgreSQL Flexible Server**, with the `algenta` database, for gateway state.
- **Azure Blob Storage** (a storage account plus a private `artifacts` container) as the evidence and artifact store, via a **native Azure Blob storage backend** — no additional storage process is deployed.
- **Azure Key Vault** holding every secret (database password, config-encryption key, session-signing secret). The container references the vault by URL, so only secret **references**, never the secret values, live in configuration or the database.
- A **user-assigned managed identity** with **least-privilege** role assignments — `Key Vault Secrets User` and `Storage Blob Data Contributor`, nothing broader. The app authenticates to Key Vault and Blob with this identity, so no long-lived storage or database keys are distributed.
- **Log Analytics + Application Insights** for operational telemetry that stays in your subscription. Redis is **optional** — self-hosted Algenta is per-device licensed and does not meter or rate-limit requests, so a cache is only useful for cross-replica coordination in a scaled-out deployment.

**No admin key is emitted** as a deployment output. First-run onboarding uses a short-lived, Entra-bound handshake instead of a static credential.

{% hint style="warning" %}
Customer-hosted means **customer-controlled, not automatically network-private**. By default the Container App has public ingress reachable over the internet (protected by identity). Putting the gateway behind private endpoints, a VNet, or an API gateway with a WAF is a separate hardening step described at the end of this page.
{% endhint %}

## Before you start

Handle these prerequisites first — they are normal enterprise admin tasks:

- **Access** — you have Owner or Contributor on the target subscription, and an Entra administrator is available for the identity step.
- **Resource providers** — register the providers the template uses:

  ```bash
  for ns in Microsoft.App Microsoft.DBforPostgreSQL Microsoft.Cache \
            Microsoft.KeyVault Microsoft.Storage Microsoft.OperationalInsights; do
    az provider register --namespace "$ns"
  done
  ```

- **Image access** — the gateway container image must be **pullable by the Container App**. Either use a publicly readable image or grant the managed identity `AcrPull` on your registry (or supply a pull secret). Pin the image by digest.
- **Tenant policy and networking** — confirm Azure Policy in your tenant permits the resource types and region below, and that outbound access needed to pull the image is allowed.
- **Identity** — plan the Entra app registration and admin consent for the Microsoft-hosted clients (Copilot, Teams, Excel, Foundry) that will call the gateway. See [Sign in with Microsoft Entra](../microsoft/entra-sso.md).

{% hint style="info" %}
The deployment template (`$TEMPLATE_FILE`) and the parameters file (`$PARAMETERS_FILE`) ship in the Algenta Azure deployment package. Keep the parameters file out of source control — it carries secret values.
{% endhint %}

## Deploy the gateway

{% stepper %}
{% step %}
### Sign in and select a subscription

```bash
az login
az account set --subscription $SUBSCRIPTION_ID
```

Confirm the active subscription with `az account show` before continuing.
{% endstep %}

{% step %}
### Choose a region and create the resource group

Pick the Azure region closest to your users and the resource group name you want to deploy into.

```bash
export RESOURCE_GROUP=$RESOURCE_GROUP
export LOCATION=$LOCATION

az group create --name $RESOURCE_GROUP --location $LOCATION
```
{% endstep %}

{% step %}
### Fill in the parameters file

Edit the parameters file so it points at your image and supplies your secrets. Leave the Entra values empty for now if you are configuring identity later — the gateway treats them as inert until both are set.

```json
{
  "namePrefix": { "value": "algenta" },
  "apiImage": { "value": "$API_IMAGE" },
  "postgresAdminPassword": { "value": "$POSTGRES_PASSWORD" },
  "configEncryptionKey": { "value": "$CONFIG_ENCRYPTION_KEY" },
  "jwtSecret": { "value": "$JWT_SECRET" },
  "deployRedis": { "value": true },
  "entraTenantId": { "value": "$TENANT_ID" },
  "entraAudience": { "value": "$ENTRA_AUDIENCE" }
}
```

Use a strong PostgreSQL password, a Fernet-format `configEncryptionKey`, and a random `jwtSecret`.
{% endstep %}

{% step %}
### Deploy the template

Run the deployment against your resource group, passing the deployment template and the parameters file.

```bash
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --name algenta-gateway \
  --template-file $TEMPLATE_FILE \
  --parameters @$PARAMETERS_FILE
```

The deployment creates the managed identity and role assignments first, then Key Vault, storage, PostgreSQL, and finally the Container App wired to all of them. The gateway applies its database migrations automatically as it starts — there is no separate migration command to run before or after deploy, and a healthy `/v1/health` means they have already been applied.
{% endstep %}

{% step %}
### Read the gateway URL

The gateway base URL is a deployment output. Capture it into `$GATEWAY_URL`:

```bash
export GATEWAY_URL=$(az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --name algenta-gateway \
  --query properties.outputs.gatewayUrl.value -o tsv)

echo $GATEWAY_URL
```

Point your Microsoft-hosted adapters (Copilot, Excel, Foundry) at this URL. Note that those experiences run on Microsoft, not in your Azure — only the decision runtime here is customer-hosted.
{% endstep %}
{% endstepper %}

### Expected result

The gateway is live and running in its private profile with cloud features disabled.

```bash
curl -s $GATEWAY_URL/v1/health
```

Health returns an OK status:

```json
{ "status": "ok" }
```

The gateway's privacy posture confirms the private profile: cloud features are disabled, telemetry is off, no control-plane URL is configured, and the artifact store resolves to your Azure Blob container. Together these show the gateway is computing decisions in your customer-controlled Azure decision plane, with evidence and artifacts written to storage you own.

{% hint style="info" %}
To move the gateway off public ingress, front the Container App with Azure API Management and a WAF, or switch to VNet-integrated ingress with private endpoints for PostgreSQL, Storage, and Key Vault. This private-networking hardening is a follow-on step and does not change the deployment above.
{% endhint %}

## Next steps

- [Sign in with Microsoft Entra](../microsoft/entra-sso.md) — register the gateway app and grant admin consent so users and services can call it.
- [Monitoring & observability](../../operate/monitoring.md) — watch health, logs, and metrics from the Log Analytics and Application Insights resources this deployment created.
- [Algenta for Microsoft Cloud](../microsoft/overview.md) — see how the customer-hosted gateway connects to Copilot, Teams, Excel, and Foundry.
