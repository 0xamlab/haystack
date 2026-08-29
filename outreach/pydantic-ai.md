# Pydantic AI — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For Pydantic AI specifically: this was the first framework package built precisely because typed models are Pydantic AI's own idiom — a typed receipt and a typed denial exception are a more natural fit here than almost anywhere else in this program, and it's worth saying so rather than treating this pitch as identical to every other ecosystem's.

## What backs this

- **`pydantic-ai-algenta`** (`python/pydantic-ai-algenta` in `thyn-ai/algenta-integrations`): a governed-execution-aware `WrapperToolset` over pydantic-ai's own `MCPToolset` — tool-profile filtering, never-model-facing field scrubbing, a typed `execute_decision` success receipt, and a `ToolDenied`-based mapping of the engine's three real, synchronous named policy gates (`idempotency`/`confidence`/`risk_floor`). Status: **In conformance testing** — its own test suite passes (including a receipt-model-override test); not yet run against the shared cross-framework conformance suite.

## The ask

Confirm the correct contribution path — a community-integrations listing, or a docs example under Pydantic AI's own MCP-tooling section — and whether a typed-receipt/typed-denial wrapper over `MCPToolset` is a pattern worth documenting generally for other MCP servers that want typed Python models on both sides of a tool call.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public and `pydantic-ai-algenta` installable (see `README.md` blockers).
- [ ] Confirm the pinned pydantic-ai version this package was built and tested against still matches current pydantic-ai releases before finalizing.
