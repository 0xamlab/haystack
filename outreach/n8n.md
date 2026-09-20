# n8n — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is compiler-driven, self-hosted AI infrastructure: modular building blocks for AI applications, compiled into one deterministic runtime. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For n8n specifically: this is a real community node, not an importable workflow-JSON sample — and it should be described to n8n as ineligible for their own Cloud verification program, upfront, rather than letting that surface as a surprise during review.

## What backs this

- **`n8n-nodes-algenta`** (`typescript/n8n-nodes-algenta` in `thyn-ai/algenta-integrations`): a real, tested community node exposing the engine's MCP tools as typed operations directly on the official `@modelcontextprotocol/sdk` (Streamable HTTP), with tool-profile enforcement checked before any network call, `execute_decision`'s typed receipt/denial contract mapped onto `NodeApiError`, and a real, importable production workflow (`demo/n8n/log-and-execute-decision.json` in the same repository) branching on policy denial vs. success. Status: **In conformance testing** — its own test suite passes; not yet run against the shared cross-framework conformance suite.
- **n8n Cloud verification**: explicitly not eligible. n8n's Cloud verification program bans runtime dependencies beyond what it directly bundles, and this node genuinely needs the MCP SDK. This is a real, documented tradeoff in the package itself, not something this draft should soften.

## The ask

Confirm the correct listing path for a self-hosted-only community node with a genuine runtime dependency — the community node registry (self-hosted-eligible tier, if one exists separately from Cloud verification), or a docs-only reference listing — and whether the bundled sample workflow is useful as a documented pattern independent of formal verification.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public and the node is npm-installable (see `README.md` blockers).
- [ ] Lead with the Cloud-verification ineligibility rather than letting a reviewer discover it — it reads as more credible stated upfront than found later.
- [ ] Confirm n8n's current community-node submission process hasn't changed since this draft was written.
