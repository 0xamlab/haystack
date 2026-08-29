---
icon: clipboard-question
description: Answers to the questions a vendor security review actually asks — each one checked against this repository's code and tests, with the gaps stated as plainly as the controls.
---

# Security questionnaire

This page answers the recurring questions in a vendor security review directly, so a reviewer doesn't have to extract them from the rest of this section. Every answer links to the page or the source file it's checked against. Where the honest answer is "not yet," it says so — a placeholder claim would fail the review it's meant to pass anyway once someone tries to verify it.

## Data handling

**Where does our data live?** Wherever you deploy the engine. Self-hosted and air-gapped deployments keep the runtime data plane — decisions, audit log, policy snapshots — entirely on infrastructure you control; see the [shared-responsibility table](overview.md#shared-responsibility-by-deployment-mode).

**Is there a subprocessor that touches our data?** Not on the runtime data plane, in a self-hosted or air-gapped deployment. Two narrower categories exist regardless of deployment mode — software distribution (image/package registries) and the commercial relationship (license issuance, support, billing) — and neither processes runtime decision data. See the [subprocessor statement](overview.md#subprocessor-statement).

**Is traffic encrypted in transit?** TLS termination is deliberately left to your own edge (nginx, Caddy, your platform's load balancer or ingress) rather than built into the API process — see [Self-hosting: TLS and exposure](../self-hosting.md#tls-and-exposure). Internal Compose-network traffic between the API and its Postgres/Redis/object-storage backends is not itself TLS-terminated by this stack; if that matters for your threat model, terminate it at your own network layer or via your cloud provider's private networking.

**Is data encrypted at rest?** That's a property of the Postgres/object-storage deployment you point the engine at, not something this application layer implements independently — use your database and storage provider's at-rest encryption. Bring-your-own-key (BYOK) provider credentials are held by you; see [Identity and access](identity-and-access.md) and the [BYOK guide](../guides/byok.md).

**Can the engine run with no outbound network access at all?** Yes — `air_gapped` deployment mode defaults every outbound-network-gated egress class off, and refuses to start if telemetry or metering is configured for control-plane sync. See [Data boundaries](data-boundaries.md).

## Access control

**How is a caller authenticated?** One of four mechanisms depending on the surface: Entra ID, generic OIDC (Okta/Auth0/Keycloak), a database-backed API key, or an offline-verified signed license JWT — never falling through from a failed Entra/OIDC verification to a weaker one. See [Identity and access](identity-and-access.md).

**Is there role-based access control?** Yes — roles are enforced server-side on every protected route (for example, the audit-log export and plan-approval endpoints both require the `admin` role explicitly, not by convention). See [Teams & roles (RBAC)](../operate/teams-rbac.md).

**Can one tenant see another tenant's data?** Every tenant-scoped query is checked against `workspace_scope_clauses`/an explicit `org_id` filter by an automated guard (`scripts/reliability_guards/guards/org_scope.py`) that flags any query missing it. This is a build-time/CI check on the query surface, not a claim about every possible code path.

## Logging and audit

**Is there an audit trail, and can we verify it wasn't altered?** Yes for a defined set of actions (see [Evidence walkthrough](evidence-walkthrough.md) for exactly which today) — `GET /v1/audit-logs/export.{fmt}` returns an `X-Content-SHA256` header over the exact exported bytes, which you re-derive yourself rather than trust. See [Audit and evidence](audit-and-evidence.md).

**Does an empty audit log mean nothing happened, or could it be hiding something?** The former. A fresh org's audit log returns genuinely empty — this was a real defect (a demo stub synthesized plausible-looking fake entries when the table was empty) that has been removed and is now covered by a regression test. See [Audit and evidence](audit-and-evidence.md).

**Are all executions in the audit trail?** Not yet, uniformly. See [Evidence walkthrough](evidence-walkthrough.md) for exactly which execution path writes an audit-log row today and which produces a receipt but doesn't yet — this is stated there because it's true, not because it's flattering.

## Vulnerability management

**How do we report a vulnerability, and what's the response time?** See [SECURITY.md](https://github.com/thyn-ai/algenta/blob/main/SECURITY.md): acknowledgement within 3 business days, initial severity triage within 7. Coordinated disclosure via a private GitHub Security Advisory or `security@algenta.ai`.

**Are container images scanned for known vulnerabilities?** Yes, on every build — SPDX and CycloneDX SBOMs plus a Grype vulnerability scan per image (API, worker, engine), by digest. Currently advisory (visible and diffable, not a release-blocking gate) — see [Supply chain](supply-chain.md) for why and when that changes.

**Are images or the Helm chart cryptographically signed?** Not yet. This is a deliberate gap, not an oversight — see [Supply chain](supply-chain.md) for the reason (a signing key is a permanent trust anchor once a customer starts verifying against it) and what unblocks it.

**Have you had a third-party penetration test or SOC 2 audit?** Neither has happened yet. Engaging one is an owner decision tracked as a real open item, not asserted here in advance of it happening.

## Incident response

**Is there a documented incident-response / threat-model process?** A public threat-model summary exists — see [Threat model](threat-model.md) — scoped to what's useful to a partner without detailing exploit paths. A fuller internal incident-response runbook and a formal CVE-numbering process are not published yet; vulnerability handling today follows [SECURITY.md](https://github.com/thyn-ai/algenta/blob/main/SECURITY.md)'s reporting and triage timeline.

**Do you have a support SLA / LTS commitment?** Not published yet — see [Support policy](support-policy.md) for exactly what that page commits to today (nothing invented ahead of an owner sign-off) versus what's still pending.

## Next steps

- [Trust overview](overview.md)
- [Supply chain](supply-chain.md)
- [Threat model](threat-model.md)
- [Support policy](support-policy.md)
