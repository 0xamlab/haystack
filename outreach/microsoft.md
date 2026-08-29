# Microsoft (Foundry / Agent Framework) — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers, both of which apply here in full.

## Pitch

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For Microsoft specifically: this covers two distinct deliverables under one outreach, and the draft should not blur them — Microsoft Agent Framework (MAF) is a real, independently pip-installable SDK integration with no Azure account required; Microsoft Foundry (the hosted platform) is a separate, documentation-only deliverable that has not been exercised against a live Foundry project.

## What backs this

- **MAF integration** (`python/maf-algenta` in `thyn-ai/algenta-integrations`): a real, tested wrapper (`create_algenta_tools`) over MAF's own `MCPStreamableHTTPTool`/`MiddlewareFailure` primitives, mapping the engine's real synchronous `execute_decision` success/denial contract onto a typed `AlgentaToolDenied`. Status: **In conformance testing** — package-level tests pass; not yet run against the shared cross-framework conformance suite.
- **Foundry registration artifacts** (`python/maf-algenta/foundry/`): an Entra app-registration Bicep template (compiles cleanly under `az bicep build`/`az bicep lint`) plus `azd ai`-based Toolbox registration steps, cited against current Microsoft Learn documentation with exact URLs and quoted requirements. Status: **documentation-only — explicitly not independently verified against a live Foundry project**, because none is available to verify against. The package's own README states this directly; the draft to Microsoft must too.
- **Current-backend hosted-agent integration** (Responses/Invocations-protocol libraries, not the retired `azure-ai-agentserver-*` preview adapters): not built yet in this repository.
- **Azure API Center registration**: not built yet.
- **The self-hosted MCP endpoint itself**: `POST`/discovery over `/mcp`, dual-serving MCP 2025-11-25 and 2026-07-28 — see [Protocol compatibility](../gitbook/trust/protocol-compatibility.md).

## The ask

The correct technical contact for validating (a) a remote-MCP-server registration path for a self-hosted engine, and (b) a Foundry Toolbox listing — independent of, and not waiting on, Partner Center verification or Marketplace listing timelines (those are separate, account-owner-level tracks). Ask specifically whether MAF's own integration bar wants the pip-installable package reviewed first, or the Foundry artifacts.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public (see `README.md` blocker #1) — a Microsoft reviewer cannot evaluate `python/maf-algenta` otherwise.
- [ ] Re-check whether the "current-backend hosted-agent integration" gap has closed since this draft was written; if it has, this draft needs the artifact link added, not just the status line changed.
- [ ] Do not send the Foundry-specific paragraph without the "not independently verified" caveat — that sentence is load-bearing, not boilerplate.
- [ ] Identify an actual named contact or program (this draft deliberately has none) before sending anything.
