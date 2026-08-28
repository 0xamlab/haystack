---
icon: shield-halved
description: Who is responsible for what across Algenta's deployment modes, and exactly which parties ever see your data.
---

# Trust overview

This section is written for a security review, not for an operator. For how-to instructions on
any control mentioned here, follow the link into [Deploy & Operate](../self-hosting.md).

## Shared responsibility, by deployment mode

Responsibility is not the same in every mode, and stating it as one blanket line would hide that.
The engine reports its own `deployment_mode` (`self_hosted`, `air_gapped`, `vpc`, `hybrid_provider`,
or `saas`) in the privacy report at `GET /v1/admin/privacy-report` — check which one applies to a
given install before reading the row below.

| Control | Self-hosted / air-gapped | VPC / hybrid | SaaS |
| --- | --- | --- | --- |
| Runtime infrastructure (compute, network, OS patching) | You | You (VPC) / Shared (hybrid) | Algenta |
| Customer data at rest and in transit | You | You | Algenta, per your configuration |
| Encryption keys (BYOK) | You generate, hold, and rotate | You generate, hold, and rotate | You may supply; Algenta holds the default |
| Identity provider configuration (Entra/OIDC/API keys) | You | You | You |
| License activation and device binding | You (offline-capable) | You | Algenta |
| Application updates | You choose when to pull a new image | You choose when to pull a new image | Algenta |
| Egress and telemetry policy | You (default: outbound network and cloud/telemetry paths off) | You | Algenta defaults apply |
| Backups | You | You | Algenta |
| Vulnerability remediation in the engine | Algenta ships the fix; you apply it | Algenta ships the fix; you apply it | Algenta applies it |
| Audit log custody | You (your database) | You | Algenta, exportable by you at any time |

The one constant across every mode: [audit evidence](audit-and-evidence.md) is always yours to
export, and [governed-execution](governed-execution.md) controls apply identically regardless of
where the engine runs — they are enforced in application code, not by network placement.

## Subprocessor statement

**Fully self-hosted or air-gapped: no Algenta-hosted subprocessor touches your runtime data
plane.** The engine that stores your decisions, executes your plans, and holds your audit log is
the process you deployed, on infrastructure you control. That is what `deployment_mode:
self_hosted` or `air_gapped` — enforced by the [egress policy](data-boundaries.md), not merely
asserted by this page — is.

Outside the runtime data plane, two categories of processor exist regardless of deployment mode,
because they are how you obtained and are licensed to run the software, not how it runs:

- **Software distribution**: the container/package registries the image or package is pulled
  from (GHCR, PyPI, npm).
- **Commercial relationship**: license issuance and validation, account management, support
  ticketing, and billing (for paid editions) — processing account and support metadata, not your
  runtime decision data.

This is a scoped claim about the *runtime data plane* specifically. It does not extend to SaaS or
hybrid deployments, where Algenta operates the runtime by design — see the table above.

## What this section covers

- [Governed execution](governed-execution.md) — the control statements behind every plan approval
  and execution: named denial codes, single-use approval binding, content-hashed policy snapshots.
- [Data boundaries](data-boundaries.md) — the egress classification matrix and what the SSRF guard
  blocks unconditionally.
- [Audit and evidence](audit-and-evidence.md) — the hash-verifiable export and what's in it.
- [Identity and access](identity-and-access.md) — the four separate identity mechanisms and why
  they don't fall through to one another.
- [API stability](../api/stability.md) — which paths carry a compatibility promise.

## What is not yet published here

A security questionnaire response set, a formal threat model, a documented incident-response
process beyond [vulnerability reporting](https://github.com/thyn-ai/algenta/blob/main/SECURITY.md),
tested backup/restore runbooks with
stated recovery objectives, and a published support-tier/LTS commitment are none of them here yet.
Publishing any of them before they are true would be worse than the gap itself; they will land as
they become real commitments rather than descriptions of intent.

## Next steps

- [Governed execution](governed-execution.md)
- [Data boundaries](data-boundaries.md)
- [Audit and evidence](audit-and-evidence.md)
- [Identity and access](identity-and-access.md)
