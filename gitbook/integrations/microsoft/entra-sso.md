---
icon: key
description: Authenticate employees and service identities to the Decision API with audience-scoped Microsoft Entra access tokens, then map each principal to an organization and workspace
---

# Sign in with Microsoft Entra

The decision gateway accepts Microsoft Entra ID as its identity provider for the Decision API. Employees and automated services present an Entra **access token**, and the gateway proves who the caller is before any decision runs — then derives the caller's organization and workspace from an administrator-provisioned mapping.

This page is for tenant administrators. It covers which token the gateway accepts (and the common ones it rejects), the two identity shapes you provision, and how to register the app and map principals.

{% hint style="info" %}
Entra identity is **not active until you configure it**. The gateway only enforces these rules once both the expected audience and the allowed tenant are set (see [Configure the gateway's Entra settings](#configure-the-gateways-entra-settings)). Microsoft 365, Copilot, Teams, Excel, Microsoft Graph, and Entra are Microsoft-hosted services; the decision runtime itself runs in the decision plane you host in your own Azure.
{% endhint %}

## Audience-scoped access tokens

The single most important rule: the gateway accepts **only** an Entra **v2 access token whose audience is the Decision API** — the app-id URI of the gateway's own app registration, `api://$GATEWAY_AUDIENCE`, from an allowed tenant.

A token minted for a different Microsoft resource is **rejected — never forwarded to the decision runtime**. In particular the gateway refuses:

| Token presented | Result |
| --- | --- |
| Decision API access token (`aud = api://$GATEWAY_AUDIENCE`) from an allowed tenant | Accepted, mapped to a workspace |
| Microsoft Graph access token | Rejected — wrong resource |
| Azure Resource Manager (ARM / `management.azure.com`) token | Rejected — wrong resource |
| A raw **ID token** replayed as a bearer | Rejected — not an API access token |
| A v1 (legacy) token | Rejected — v2 issuer only |

For every bearer that reaches it, the gateway validates the full set of claims before it trusts the caller:

- **Issuer** — must be the Entra v2 issuer for the token's tenant (`https://login.microsoftonline.com/$TENANT_ID/v2.0`). v1 issuers are rejected.
- **Audience** — must equal the configured Decision API audience.
- **Tenant** — the token's tenant id (`tid`) must be in the gateway's allowlist; the gateway never fetches signing keys for a tenant that is not allowed.
- **Principal** — a stable object id (`oid`) must be present.
- **Scope or app role** — a delegated scope, an assigned app role, or the app-only marker must be present, which is how an ID token (carrying none of these) is refused.
- **Expiry** — expired tokens are rejected, with a small clock-skew allowance.
- **Signing key** — the RS256 signature is verified against the tenant's published keys, with an automatic refresh to ride key rotation.

{% hint style="warning" %}
A client-supplied workspace header is **never authoritative** for an Entra caller. The workspace and organization come only from the principal mapping you provision. A request that tries to select a workspace via a header is rejected — you decide, at provisioning time, exactly which workspace each identity may reach.
{% endhint %}

## Two identity shapes

Every verified token resolves to one of two identity shapes. Both are mapped, per principal, to an organization, a workspace, and a role.

{% tabs %}
{% tab title="Delegated employee identity" %}
A signed-in employee initiates a decision — for example from the Decision Agent in Copilot or Teams, or the Excel add-in. The token is issued **on behalf of the user**, carries delegated scopes, and resolves to that user's provisioned workspace and role.

Use this shape for interactive, user-initiated decisions where the acting person matters for audit.
{% endtab %}

{% tab title="Service / managed identity" %}
An automated caller — a scheduled refresh, a batch of evaluations, or an org-scoped agent — authenticates as an application or an Azure **managed identity**. The token is app-only and carries assigned app roles rather than delegated scopes.

Map each service identity to a **restricted workspace and role** scoped to exactly what the automation needs. A service identity does not inherit broad access simply for being a service — its permissions come only from its mapping.
{% endtab %}
{% endtabs %}

## Register the gateway app in Entra

You perform these steps once, as a tenant administrator, before turning on Entra sign-in.

{% stepper %}
{% step %}
### Register the app and expose the API

In the Microsoft Entra admin center, register an application for the decision gateway. Under **Expose an API**, set the Application ID URI to `api://$GATEWAY_AUDIENCE` and add:

- one or more **delegated scopes** (for example `Decisions.Run`) for signed-in employees, and
- one or more **app roles** (for example `Decisions.Service`) for service and managed identities.

This app registration's identifier is the audience the gateway will require.
{% endstep %}

{% step %}
### Grant admin consent

Grant tenant-wide admin consent for the scopes and app roles you exposed, and assign the app roles to the service principals (or managed identities) that will call the API. Employees consent to the delegated scope through the client applications (Copilot, Teams, or the Excel add-in) that request a Decision API token.
{% endstep %}

{% step %}
### Map principals to organizations and workspaces

On the gateway, provision a mapping for each identity that may call the API: the tenant id plus the principal's object id, resolved to an organization, a workspace, and a role. Mark inactive mappings as revoked.

Both employee and service principals must be mapped. An unmapped or revoked identity is rejected — and the gateway returns the same error for "unknown" and "revoked" so it never reveals which principals exist.
{% endstep %}
{% endstepper %}

## Configure the gateway's Entra settings

Set the gateway's Entra settings so it knows which audience and tenant to trust:

```bash
# The Decision API audience — the app-id URI (or client id) of the app
# you registered above. Tokens minted for any other resource are rejected.
ALGENTA_ENTRA_AUDIENCE="api://$GATEWAY_AUDIENCE"

# The allowed tenant. Its Entra v2 issuer
# (https://login.microsoftonline.com/$TENANT_ID/v2.0) is the only issuer
# the gateway trusts for this tenant.
ALGENTA_ENTRA_TENANT_ID="$TENANT_ID"
```

The **issuer** is derived and pinned from the tenant id, so you do not set it separately — the gateway only trusts the v2 issuer for an allowed tenant.

Two optional settings tighten access further:

- **Additional tenants** — allow more than one tenant to call this gateway (the configured tenant is always allowed). Leave unset for a single-tenant gateway.
- **Allowed client applications** — restrict which registered client apps may present tokens, by client id. Leave unset to allow any client app within an allowed tenant.

{% hint style="info" %}
Keep the audience exact. The gateway compares it against the token's `aud` claim, so `api://$GATEWAY_AUDIENCE` on the gateway must match the Application ID URI on the app registration character-for-character.
{% endhint %}

### Expected result

Once the app is registered, consent is granted, and the settings above are in place:

- A client requests a token **for the Decision API** (`api://$GATEWAY_AUDIENCE`) and calls the gateway with it as a bearer.
- The gateway verifies the issuer, audience, tenant, principal, scope or app role, expiry, and signature, then resolves the principal to its provisioned organization and workspace. The decision runs under that workspace and role — regardless of any workspace header on the request.
- A **Microsoft Graph** token, an **ARM / Azure-management** token, a **raw ID token**, or a token from a **tenant that is not allowed** is rejected with a precise error telling the caller to request a Decision API token instead.
- A validly signed token whose principal has **no mapping** (or a revoked one) is rejected as not provisioned.

An unmapped identity's error is your cue to add the missing principal mapping on the gateway — not to loosen token validation.

## Next steps

- [Deploy the decision gateway to your Azure](../azure/gateway.md)
- [Decision Agent in Copilot & Teams](copilot-teams.md)
- [Excel Decision Add-in](excel.md)