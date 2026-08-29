# LlamaIndex — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For LlamaIndex specifically: this is a workflow-level integration with receipt citations, built on `llama-index-tools-mcp`'s own primitives rather than a parallel MCP client.

## What backs this

- **`llamaindex-algenta`** (`python/llamaindex-algenta` in `thyn-ai/algenta-integrations`): a real, tested `create_algenta_tools` wrapping `llama-index-tools-mcp`'s own `BasicMCPClient`/`FunctionTool` primitives, with tool-profile filtering, two-layer `force`/`override_safety` scrubbing, and a typed `AlgentaToolDenied`/`AlgentaToolExecutionFailed` mapping of `execute_decision`'s real synchronous success-receipt/three-named-gate-denial contract. Status: **In conformance testing** — its own test suite passes; not yet run against the shared cross-framework conformance suite.

## The ask

Confirm the correct listing path for a workflow-level governance integration — LlamaIndex's integrations directory (`llama-index-integrations` or the equivalent current registry), or a docs example — and whether receipt-citation-in-workflow is a pattern the project wants documented generally.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public and `llamaindex-algenta` installable (see `README.md` blockers).
- [ ] Confirm the current LlamaIndex integrations submission process and required package-naming convention before finalizing (these have changed over time).
