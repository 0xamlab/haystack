# One-click deploy — Algenta Decision Gateway

The customer experience must be **one sign-in + Create**, not manual Bicep or app registration. There
are three levels, from what ships today to the full Marketplace product.

## What "one-click" means here

Deploying into a customer's **own** Azure always requires *them* to authenticate to *their* Azure
once — that single sign-in + **Create** is the click. (Zero-touch onboarding is the hosted SaaS
edition, where it is *not* their Azure.)

## Level 1 — "Deploy to Azure" button (pre-Marketplace)

A button (site/docs) opens the Azure portal's custom-deployment blade pre-loaded with this form
(`createUiDefinition.json`) + the compiled `mainTemplate.json`. The customer picks subscription +
region and clicks **Create**; the gateway deploys into their Azure.

```
https://portal.azure.com/#create/Microsoft.Template/uri/<URL-encoded mainTemplate.json>/createUIDefinitionUri/<URL-encoded createUiDefinition.json>
```

Owner step: host `mainTemplate.json` (`az bicep build -f ../main.bicep --outfile mainTemplate.json`)
and `createUiDefinition.json` at public HTTPS URLs, then encode them into the button.

## Level 2 — Azure Marketplace **Managed Application** (the product)

The true 1-click: the customer finds Algenta in the Marketplace, clicks **Create**, fills this same
form, and clicks **Create**. The package is a `.zip` of `mainTemplate.json` +
`createUiDefinition.json` (+ `viewDefinition.json`), published via Partner Center. No public URL
hosting needed — the package is bundled. Owner-gated (Partner Center account + listing).

## Level 3 — identity without manual app registration

Instead of each customer registering an Entra app by hand, publish **one multitenant Algenta app**
and give customers a single **admin-consent link**:

```
https://login.microsoftonline.com/common/adminconsent?client_id=<ALGENTA_APP_CLIENT_ID>
```

The customer's admin clicks it once → the app's service principal is provisioned in their tenant
automatically. The deployed gateway is configured with **their** tenant id, so it still validates
only their organization's tokens — **one-click onboarding + per-customer isolation**.

## Honest gaps to close (owner)

- Publish the Marketplace Managed Application (Partner Center) and/or host the Deploy-to-Azure
  template + createUiDefinition at public URLs.
- Register the multitenant Algenta app once and wire the admin-consent link into onboarding.
- For a *truly* fieldless form, have `main.bicep` auto-generate the three secrets when not supplied
  (today the form collects them so the template can store them in Key Vault).
