---
icon: life-ring
description: What support and long-term-support commitments exist today, and what is explicitly pending an owner decision rather than invented ahead of it.
---

# Support policy

## What's real today

Security fixes land on `main` and in the latest published release of every artifact (API/worker/engine images, the Python and TypeScript SDKs, and `algenta-mcp`) — see [SECURITY.md](https://github.com/thyn-ai/algenta/blob/main/SECURITY.md) for the acknowledgement and triage timeline that already applies to every report, on every edition, today.

Community, Pro, Team, and Enterprise are real, shipping license editions with real capacity caps — see [Licensing & editions](../licensing.md). That page is the source of truth for what each edition unlocks; this page is only about support and lifecycle commitments layered on top of it.

## What is not published yet

A per-edition support-tier matrix (response-time targets, support channels, escalation paths mapped to Community/Pro/Team/Enterprise) and a formal long-term-support window (which releases get security backports, and for how long) do not exist yet. Both require an owner sign-off before they're published, because a support commitment is a promise made to every customer who reads it, not an engineering estimate — inventing numbers here would be worse than the gap itself.

The proposal on the table — not yet approved, stated here only so it's visible rather than hidden — is **latest-plus-previous** as the LTS window: security backports to the current release and the one before it, on Enterprise. Treat this as a proposal until this page says otherwise.

## What changes when this is signed off

This page will be updated, in the same change that ships the decision, with:

- A support-tier table mapped to license edition (channel, initial-response target, escalation path).
- A published LTS window and what "backport" means in practice for this project's rolling-release model (see [SECURITY.md](https://github.com/thyn-ai/algenta/blob/main/SECURITY.md#supported-versions) for how versions are supported today, absent a formal window).
- Whether an SLA is contractual (Enterprise) versus best-effort (Community/Pro/Team).

Until then, do not read a specific number — hours, days, a version count — into this page or into any material built from it. [Capability status](capability-status.md) points back here rather than restating a number that doesn't exist yet.

## Next steps

- [Licensing & editions](../licensing.md)
- [Trust overview](overview.md)
- [Security questionnaire](security-questionnaire.md)
