---
icon: key
description: Authenticate users and service clients to the Decision API with any standards-compliant OIDC provider — Okta, Auth0, Keycloak, or your own — then map each principal to an organization and workspace
---

# Sign in with a generic OIDC provider

The decision gateway accepts any standards-compliant OpenID Connect provider as its identity source for the Decision API — Okta, Auth0, Keycloak, or an identity provider you run yourself. A user or service client presents an OIDC **access token**, and the gateway proves who the caller is before any decision runs — then derives the caller's organization and workspace from an administrator-provisioned mapping.

{% hint style="info" %}
Already on Microsoft Entra? See [Sign in with Microsoft Entra](../microsoft/entra-sso.md) instead — it uses the same principal-mapping model but is tuned to Entra's specific tenant/audience shape. This page is for every other OIDC provider.
{% endhint %}

This page is for gateway operators. It covers which token the gateway accepts (and the ones it rejects), the two identity shapes you provision, and how to configure your identity provider and map principals.

{% hint style="info" %}
Generic OIDC identity is **not active until you configure it**. The gateway only enforces these rules once the issuer, audience, and JWKS URL are all set (see [Configure the gateway's OIDC settings](#configure-the-gateways-oidc-settings)). Your identity provider is whatever you already run; the decision runtime itself runs in the decision plane you host.
{% endhint %}

## The issuer is the trust boundary

Unlike Microsoft Entra — one fixed host serving many tenants, which is why Entra needs a separate tenant allowlist — a generic OIDC issuer URL already **is** the full tenant/realm identity. Keycloak's issuer for a realm is literally `{server}/realms/{realm}`; Okta's and Auth0's issuers are similarly per-tenant. So there is nothing to allowlist beyond the one issuer you configure: the gateway accepts a token if, and only if, its `iss` claim matches your configured issuer **exactly** (not a prefix, not a host match).

The gateway accepts **only** an access token whose audience is the Decision API, issued by that exact issuer. A token minted for a different resource, or issued by any other issuer, is rejected — never forwarded to the decision runtime.

| Token presented | Result |
| --- | --- |
| Access token (`aud` = the configured audience) from the configured issuer | Accepted, mapped to a workspace |
| Access token from a different issuer (a different realm/tenant/provider) | Rejected — wrong issuer |
| A token minted for a different audience | Rejected — wrong audience |
| A raw **ID token** replayed as a bearer (carries a `nonce`) | Rejected — not an API access token |

For every bearer that reaches it, the gateway validates the full set of claims before it trusts the caller:

- **Issuer** — must exactly match the configured issuer.
- **Audience** — must equal the configured Decision API audience.
- **Subject** — a stable subject (`sub`) must be present.
- **Scope or role, or a client-credentials shape** — a delegated scope, a role, or the machine-to-machine marker must be present, which is how a bare ID token (carrying none of these) is refused.
- **Client application** (optional) — if you configure an allowlist of client ids, only tokens from those clients are accepted.
- **Expiry** — expired tokens are rejected, with a small clock-skew allowance.
- **Signing key** — the RS256 signature is verified against your provider's published JWKS, with an automatic refresh to ride key rotation.

{% hint style="warning" %}
A client-supplied workspace header is **never authoritative** for an OIDC caller. The workspace and organization come only from the principal mapping you provision. A request that tries to select a workspace via a header is rejected — you decide, at provisioning time, exactly which workspace each identity may reach.
{% endhint %}

## Two identity shapes

Every verified token resolves to one of two identity shapes. Both are mapped, per principal, to an organization, a workspace, and a role.

{% tabs %}
{% tab title="User identity" %}
A signed-in human initiates a decision. The token carries delegated scopes or roles and resolves to that user's provisioned workspace and role.

Use this shape for interactive, user-initiated decisions where the acting person matters for audit.
{% endtab %}

{% tab title="Service / client-credentials identity" %}
An automated caller — a scheduled job, a CI pipeline, or an integration service — authenticates via the OAuth2 client-credentials grant. The token carries no delegated scope tied to a human; the gateway recognizes it as a machine identity from the token's own shape (a Keycloak service-account subject, or a subject that matches the client id, depending on your provider).

Map each service identity to a **restricted workspace and role** scoped to exactly what the automation needs. A service identity does not inherit broad access simply for being a service — its permissions come only from its mapping.
{% endtab %}
{% endtabs %}

## Configure your identity provider

You perform these steps once, on your identity provider, before turning on OIDC sign-in. The exact screens vary by provider; the shape is the same everywhere.

{% stepper %}
{% step %}
### Register a client for the gateway

Create a client/application registration for the decision gateway on your provider (Keycloak: a client under your realm; Okta/Auth0: an application plus an API/authorization server). Note its issuer URL and JWKS endpoint — you'll need both below.
{% endstep %}

{% step %}
### Set the audience

Configure your provider to stamp the Decision API's audience into access tokens for this client. Keycloak does this with an **audience mapper** on the client (mapping to the client id, or a custom value); Okta and Auth0 expose this as the authorization server's **audience**. Whatever value you choose here is what you set as `ALGENTA_OIDC_AUDIENCE` below — it must match exactly.
{% endstep %}

{% step %}
### Map principals to organizations and workspaces

On the gateway, provision a mapping for each identity that may call the API — the issuer plus the principal's subject, resolved to an organization, a workspace, and a role:

```bash
python scripts/provision_oidc_principal.py \
  --issuer "https://idp.example.com/realms/acme" \
  --subject "90b2e441-f049-41bf-b467-9ce85b36a24d" \
  --org-slug your-org --role admin --type user
```

Both user and service principals must be mapped. An unmapped or revoked identity is rejected — and the gateway returns the same error for "unknown" and "revoked" so it never reveals which principals exist.

{% hint style="info" %}
**Auto-link on first sign-in (optional).** Set `ALGENTA_OIDC_AUTO_PROVISION=1` and you don't pre-map every identity: a verified first-time principal from your configured issuer is linked automatically — it **joins your shared Team or Enterprise subscription** when a seat is free, otherwise it gets its own individual Community org. A **revoked** mapping is never auto-revived. Leave the flag off to keep the strict admin-provisioned model above.
{% endhint %}
{% endstep %}
{% endstepper %}

## Configure the gateway's OIDC settings

Set the gateway's OIDC settings so it knows which issuer, audience, and key source to trust:

```bash
# The exact issuer your provider stamps into every access token's `iss`
# claim. This is the WHOLE trust boundary — no separate tenant allowlist
# exists because the issuer already identifies your tenant/realm.
ALGENTA_OIDC_ISSUER="https://idp.example.com/realms/acme"

# The Decision API audience you configured on your provider above.
# Tokens minted for any other resource are rejected.
ALGENTA_OIDC_AUDIENCE="algenta-gateway"

# Your provider's published JWKS endpoint, used to verify token signatures.
ALGENTA_OIDC_JWKS_URL="https://idp.example.com/realms/acme/protocol/openid-connect/certs"

# Optional: restrict which client ids may present tokens (CSV; unset = any)
ALGENTA_OIDC_ALLOWED_CLIENT_APPS=
```

{% hint style="info" %}
Self-hosted operators: the JWKS host above is automatically trusted for egress once `ALGENTA_OIDC_JWKS_URL` is set — you don't need a separate `ALGENTA_EGRESS_ALLOWLIST` entry for it.
{% endhint %}

### Expected result

Once your provider is configured and the settings above are in place:

- A client requests a token **for the Decision API audience** and calls the gateway with it as a bearer.
- The gateway verifies the issuer, audience, subject, scope or role, expiry, and signature, then resolves the principal to its provisioned organization and workspace. The decision runs under that workspace and role — regardless of any workspace header on the request.
- A token from a **different issuer**, a **different audience**, or a **raw ID token** is rejected with a precise error telling the caller to request a Decision API access token instead.
- A validly signed token whose principal has **no mapping** (or a revoked one) is rejected as not provisioned.

An unmapped identity's error is your cue to add the missing principal mapping on the gateway — not to loosen token validation.

## Next steps

- [Self-hosting](../../self-hosting.md)
- [Configuration reference](../../configuration.md)
- [Sign in with Microsoft Entra](../microsoft/entra-sso.md)
