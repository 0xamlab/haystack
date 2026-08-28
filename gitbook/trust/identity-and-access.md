---
icon: id-badge
description: Four separate identity mechanisms, each scoped to one surface, none falling through to another.
---

# Identity and access

Algenta authenticates through four distinct mechanisms depending on which surface a caller is
using. They are deliberately separate planes, not four ways of reaching the same check — see
[Teams & roles (RBAC)](../operate/teams-rbac.md) for role management once a caller is
authenticated, and [Authentication & API keys](../authentication.md) for day-to-day setup.

| Surface | Mechanism | Falls through to another mechanism on failure? |
| --- | --- | --- |
| Engine API (`/v1/*`), Entra-configured gateway | Microsoft Entra ID bearer token | No — an Entra-shaped token that fails verification is rejected outright |
| Engine API (`/v1/*`), offline/self-hosted | Locally-verified signed license JWT (signature + expiry, no network call) | Falls through only to the API-key path below, for non-JWT credentials |
| Engine API (`/v1/*`), hosted or standard self-hosted | Database-backed API key (`X-API-Key` or `Authorization: Bearer`) | — |
| Website dashboard (`/account/*`) | Supabase session token (the site's own OAuth session) | No — a separate identity plane from the engine API entirely |

## Entra identity never downgrades

When the deployment is Entra-configured and an incoming bearer token is shaped like an Entra
token, Entra verification is the *only* path tried. A token that looks like an Entra token but
fails verification is rejected — it is never handed to the API-key or offline-license verifiers
as a second chance. There is no ambiguity about which identity provider authenticated a given
request.

## An Entra identity cannot select its own workspace

For every other credential type, a caller may select a workspace via `X-Workspace-Id`. An
Entra-authenticated caller's workspace comes only from its provisioned principal mapping — an
`X-Workspace-Id` header on an Entra-authenticated request is refused explicitly
(`workspace_scope_not_permitted`), not silently ignored. The workspace a person can act in is
therefore determined by how their identity was provisioned, not by anything the request itself
can claim.

## Offline license verification touches no network and no database

A signed license JWT is verified locally — signature and expiry only — with zero Postgres or
Redis calls on that path. This is what lets a self-hosted, air-gapped deployment keep authenticating
requests with the network fully dark. Any credential that is not a recognized license JWT falls
back to the database-backed API-key path; a license JWT that fails verification does not.

## The website dashboard is a separate identity plane entirely

`/account/*` routes (device management, usage, billing, team, organization settings) authenticate
against a Supabase session token — the signed-in user's own OAuth session on the website — not an
engine API key. This is deliberate plane separation: an engine API key never grants website
dashboard access, and a website session never grants direct API access.

## Next steps

- [Authentication & API keys](../authentication.md)
- [Teams & roles (RBAC)](../operate/teams-rbac.md)
