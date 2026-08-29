# Pitch template

## The base pitch, verbatim

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

This is the fixed base every per-ecosystem draft opens with, unedited. What follows in each draft is the specific evidence for that ecosystem: which package, its exact status label, and the artifact links that back the claim — never a generic "it works great" filled in around the pitch.

## The ask, every time

Three things, no more:

1. **The correct interface** — confirm we're integrating against the right primitive for how your ecosystem actually wants this (a native tool-calling provider vs. an MCP-based one, a community node vs. a core plugin, a config-driven gateway integration vs. a code package — whichever your project prefers).
2. **The contribution or listing path** — where this actually belongs (your integrations directory, your plugin marketplace, your own docs' partner list, an upstream PR) and what your project's bar is for that.
3. **A review of the runnable work** — not a pitch deck. The artifact link in each draft is something your team can clone and run today (once the two blocking items in [`README.md`](README.md) are resolved) or that already runs in this repository's own CI evidence.

Never ask for a customer reference, an adoption number, or a "certified" stamp — none of that exists, and no draft should imply otherwise.

## Status label discipline (do not deviate per-draft)

| Label | When to use it |
| --- | --- |
| **Available now** | The underlying engine capability is merged and tested. |
| **Validated integration** | Available now, and the framework's own client passed the shared cross-framework conformance suite. **No framework package qualifies for this yet** — see [Capability status](../gitbook/trust/capability-status.md). Do not use it in any draft until that changes. |
| **In conformance testing** | The correct label for every framework package today: real code, real package-level tests, not yet run against the shared suite. |

## Claim/release gates that apply to outreach copy specifically

From the partnership program's own gate table — a draft's language must not get ahead of these:

| Copy in a draft | Requires |
| --- | --- |
| "Validated integration" for framework X | The conformance suite passing for X's own client — not yet true for any framework |
| "Fully compatible LiteLLM model provider" / an upstreamed provider PR | Chat Completions native streaming + tools passing, contract-tested |
| A `ChatAlgenta` LangChain partner listing | `langchain-tests` `ChatModelIntegrationTests` passing |
| "Microsoft integration production-certified" | The full Foundry/MAF test matrix passing (Marketplace listing is separately an account-owner action) |
| A formal partner-directory listing request | An installable artifact (see the two blocking items in [`README.md`](README.md)) + a passing conformance result |
| "MCP 2026-07-28 conformant" | The behavioral matrix green against the official SDKs — not yet run (see [Protocol compatibility](../gitbook/trust/protocol-compatibility.md)) |
| "Highly available" deployment language | Engine failover demonstrated — not yet true; the engine is not active-active today |

## Tone

Direct, specific, short. Name the exact artifact. Don't pad with adjectives the evidence doesn't back. If the honest version of a claim is weaker than what would look best, use the honest version — a partner engineer checking the linked repository is the actual audience, not whoever reads the email once.
