# Vercel AI SDK — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For Vercel specifically: this is a `ToolSet` built directly against the AI SDK's own `createMCPClient()`/`ai` v7 primitives, talking MCP directly (no `algenta-sdk` dependency in this package at all — a deliberate choice, since the package needs no HTTP client beyond MCP itself). The name was chosen deliberately as `@thyn-ai/algenta-tools`, not something that reads as a model provider — Algenta isn't one.

## What backs this

- **`@thyn-ai/algenta-tools`** (`typescript/algenta-tools/packages/algenta-tools` in `thyn-ai/algenta-integrations`): tool-profile filtering, never-model-facing field scrubbing, and `execute_decision`'s real typed success/denial contract — a typed `ExecutionReceipt` on success, a typed `ExecutionBlockedError` naming the real synchronous `idempotency`/`confidence`/`risk_floor` gate on denial. No approval-pause state is modeled, because none exists on the real tool today (stated honestly in the package rather than implied). Status: **In conformance testing** — its own vitest suite passes; not yet run against the shared cross-framework conformance suite.

## The ask

Confirm the correct listing path for a governed-tools package built on `createMCPClient()` — a community showcase, a docs example, or a package registry listing — and whether the AI SDK team wants the approval/receipt pattern documented as a reference implementation for other MCP-backed tool providers, independent of Algenta specifically.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public and `@thyn-ai/algenta-tools` is actually resolvable from npm (see `README.md` blockers) before referencing an install command.
- [ ] Double-check the package name in the final send matches whatever it publishes as — this draft assumes `@thyn-ai/algenta-tools`; re-verify against `typescript/algenta-tools/packages/algenta-tools/package.json` at send time.
