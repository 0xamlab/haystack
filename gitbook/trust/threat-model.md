---
icon: shield-virus
description: A public summary of what this engine defends against and how — asset by asset, control by control — without exploit-level detail that would only help an attacker.
---

# Threat model (public summary)

This is a summary, not the complete internal threat model. It names the assets that matter, the threats considered for each, and the control that addresses it — enough for a security reviewer to assess the shape of the defense without a level of exploit detail that helps an attacker more than a defender. Where a category has no control yet, that's stated too.

## Assets

- **Decision data**: the inputs, results, and audit trail of every governed decision.
- **Execution authority**: the ability to make an approved plan actually run.
- **Identity and credentials**: API keys, license JWTs, Entra/OIDC tokens, BYOK provider credentials.
- **The runtime itself**: the API process, the engine worker, and their network reach.

## Threats and controls, by asset

### Decision data

| Threat | Control |
| --- | --- |
| One tenant reading another tenant's decisions, audit log, or connectors | Every tenant-scoped query is checked at CI time by an automated guard (`scripts/reliability_guards/guards/org_scope.py`) for a missing `workspace_scope_clauses`/`org_id` filter |
| An exported audit log silently altered after export | `X-Content-SHA256` on the export, verified by re-hashing the download — see [Audit and evidence](audit-and-evidence.md) |
| A fabricated-looking audit trail (synthesized entries standing in for a genuinely empty one) | Removed as a defect and covered by a regression test — see [Audit and evidence](audit-and-evidence.md) |

### Execution authority

| Threat | Control |
| --- | --- |
| Executing a plan that was never approved | Server-side lifecycle state machine — `execute` on a plan that isn't `approved` is refused (`plan_not_approved`), including a plan already executed once |
| Approving a plan that was edited after review | Approval is bound to an exact `plan_hash`; a mismatch is refused (`plan_hash_mismatch`) |
| Replaying a captured approval request | Single-use nonce; reuse is refused (`invalid_nonce`) |
| Two concurrent execute calls both succeeding (double execution) | Compare-and-set on the `approved` state — exactly one call transitions the plan; see [Governed execution](governed-execution.md) |
| A model or agent approving its own execution | Approval is a separately-authenticated, credentialed operation, deliberately not exposed as an MCP or LLM-facing tool |

### Identity and credentials

| Threat | Control |
| --- | --- |
| A forged token that merely looks like an Entra/OIDC token being accepted by a weaker fallback verifier | No fallback — a token shaped like an Entra or OIDC token that fails verification is rejected outright, never handed to the API-key path as a second chance. See [Identity and access](identity-and-access.md) |
| An identity provisioned for one workspace selecting a different one | An `X-Workspace-Id` header on an Entra/OIDC-authenticated request is refused explicitly (`workspace_scope_not_permitted`), not silently ignored |
| Credential verification requiring network access an air-gapped deployment doesn't have | Offline license-JWT verification checks signature and expiry locally, with zero Postgres/Redis calls |

### The runtime and its network reach

| Threat | Control |
| --- | --- |
| Server-side request forgery reaching cloud metadata endpoints | Unconditional block on link-local space (`169.254.0.0/16`, including the IPv4-mapped/NAT64/explicit-AWS-IPv6 forms of the metadata address) and multicast/unspecified addresses — no allowlist entry can override this. See [Data boundaries](data-boundaries.md) |
| Undeclared outbound network use in an air-gapped deployment | Every outbound call is classified into one of five egress classes before it's allowed; `air_gapped` mode defaults every network-gated class off and refuses to start if telemetry/metering is configured for control-plane sync |
| A known-vulnerable dependency shipping unnoticed | SBOM + vulnerability scan per image, per release — see [Supply chain](supply-chain.md) for what that does and does not cover today |

## What this summary does not cover

- **Exploit-level detail** for any of the above — a public summary that doubled as an attack guide would be worse than no summary.
- **Independent verification.** No third-party penetration test or security audit has been performed on this codebase as of this writing. Engaging one is a real, open, owner-level decision — see [Security questionnaire](security-questionnaire.md) — not something this page should imply has already happened.
- **A formal, versioned internal threat-model document** beyond this public summary, and a formal CVE-numbering/incident-response process beyond what [SECURITY.md](https://github.com/thyn-ai/algenta/blob/main/SECURITY.md) already commits to. Both are open items, not silently-abandoned ones.
- **Image/artifact signing and provenance** — see [Supply chain](supply-chain.md) for exactly what's built and what isn't.

## Next steps

- [Data boundaries](data-boundaries.md)
- [Identity and access](identity-and-access.md)
- [Security questionnaire](security-questionnaire.md)
- [Governed execution](governed-execution.md)
