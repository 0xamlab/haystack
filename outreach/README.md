# Outreach kit — drafts only, not sent

**Nothing in this directory has been sent, posted, or opened as an issue/PR/discussion against any third-party repository, mailing list, or forum.** Every file here is a draft for a human to review, edit, and decide whether and when to send. No automation in this repository sends these. If you're reading this because an agent or script pointed you here as something already delivered, that's wrong — check first.

## What's here

- [`pitch-template.md`](pitch-template.md) — the base pitch (verbatim from the partnership plan) and the rules every customized draft below follows.
- One file per ecosystem: [`microsoft.md`](microsoft.md), [`litellm.md`](litellm.md), [`langchain.md`](langchain.md), [`vercel-ai-sdk.md`](vercel-ai-sdk.md), [`n8n.md`](n8n.md), [`haystack.md`](haystack.md), [`llamaindex.md`](llamaindex.md), [`pydantic-ai.md`](pydantic-ai.md), [`ray-serve.md`](ray-serve.md), [`vllm.md`](vllm.md).

## Read this before sending anything

Every claim in every draft was checked against `thyn-ai/algenta` (this repository) and `thyn-ai/algenta-integrations` at the time it was written — not carried forward from an earlier status, and not restated from the partnership plan without re-verification. Re-check anything load-bearing before it leaves this directory; both repositories move fast enough that a status line written today can be stale in a week.

### Blocking, before any of these can actually be sent

These are not claim-language issues — they mean a recipient literally cannot see what the draft references yet:

1. **`thyn-ai/algenta-integrations` is not public.** Every draft below references code that lives there. Its own README states this is a deliberate, standing decision, not an oversight — see that repository's "Status & roadmap" section. Until it's made public, no draft below can actually be verified by its recipient.
2. **No package is installable from a public registry.** Every framework package 404s on PyPI and npm today. The release pipeline already runs correctly on every tagged release (`auto-release.yml`, `publish.yml`) and would publish immediately once two account-owner actions land: registering a Trusted Publisher per package, and flipping the `PUBLISH_TO_REGISTRIES` repository variable. Until then, "install" in any draft below means "clone the repository and run it locally," not `pip install`/`npm install` — say so explicitly if you edit a draft, don't imply otherwise.

Sending any of these before both are resolved would ask a partner to review code they cannot reach.

### Claim discipline (checked per draft, not assumed)

- No draft uses "Validated integration" for a framework package. The shared cross-framework conformance suite (`demo/conformance/` in `algenta-integrations`) exists and has a real, passing engine-level baseline run, but no framework package has been run against it yet — that repository's own `demo/README.md` says explicitly that no package should carry that label until then. Every draft below says "In conformance testing" or describes what's actually been tested (the package's own unit/contract tests against its own stub), never more.
- No draft claims "production-proven," "battle-tested," "certified," or cites a customer.
- No draft claims image signing, SLSA/provenance, or VEX — those aren't built (see `gitbook/trust/supply-chain.md`).
- No draft claims a support SLA or LTS window — none is published yet (see `gitbook/trust/support-policy.md`).
- Where a draft names a specific artifact (a file path, a test count, a conformance result), that's something a reviewer can go check themselves in the referenced repository — not a paraphrase of an announcement.

## Evidence bundle these drafts point back to

- [Capability status](../gitbook/trust/capability-status.md) — every surface and integration, labeled.
- [Protocol compatibility](../gitbook/trust/protocol-compatibility.md) — MCP/Responses/Chat Completions matrix and the conformance suite's real 9/12 result.
- [Architecture and trust boundaries](../gitbook/trust/architecture.md)
- [Evidence walkthrough](../gitbook/trust/evidence-walkthrough.md) — the receipt envelope and audit export, worked.
- [Trust overview](../gitbook/trust/overview.md), [Security questionnaire](../gitbook/trust/security-questionnaire.md), [Supply chain](../gitbook/trust/supply-chain.md), [Threat model](../gitbook/trust/threat-model.md), [Support policy](../gitbook/trust/support-policy.md)
- [Benchmarks](../gitbook/benchmarks/overview.md) — 22 published pages, each with a named baseline and a reproduction command.

## Before you send any one draft

1. Re-read the "Blocking" section above — has either item resolved since this was written?
2. Re-check the specific status claims in that one draft against the current state of both repositories (a `git log`/PR search takes a minute and catches drift like this session found: a capability-plane approval gate merged the day this kit was written, which the conformance suite's own recorded run predates).
3. Confirm the recipient/venue (a named contact, a specific listing form, a specific repository's contribution process) — these drafts don't include one, on purpose; that's a decision for whoever sends it.
4. Get sign-off from whoever owns partnership outreach at Algenta before it goes out. This kit does not imply that sign-off has happened.
