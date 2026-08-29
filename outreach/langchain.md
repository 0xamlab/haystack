# LangChain / LangGraph — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For LangChain specifically: the pitch is a governance/receipts toolkit that complements `langchain-mcp-adapters`, not a replacement for it — this integration exists because generic MCP tool-calling doesn't natively express approvals, typed denial reasons, or receipt schemas.

## What backs this

- **`langchain-algenta`** (`python/langchain-algenta` in `thyn-ai/algenta-integrations`): a governed-execution-aware LangChain/LangGraph tool list — tool-profile filtering, scrubbing of fields that must never be model-facing (`force`/`override_safety`), a typed `execute_decision` success receipt, and an `AlgentaExecutionBlocked` mapping of the engine's three real, synchronous named policy gates (`idempotency`/`confidence`/`risk_floor`). Status: **In conformance testing** — its own test suite (including `test_execution_denial.py`, `test_governance.py`) passes against a local stub; not yet run against the shared cross-framework conformance suite.
- **`ChatAlgenta`**: not built. This lands only once Track C (Chat Completions hardening) passes and it's validated by LangChain's own full `ChatModelIntegrationTests` suite — do not draft or promise this ahead of that.

## The ask

Confirm the correct contribution path for a toolkit package like this one — LangChain's own community-integrations process, or a listing alongside `langchain-mcp-adapters` — and whether a governance/receipts layer on top of MCP tool-calling is something the project wants documented as a pattern, independent of any future `ChatAlgenta` chat-model integration.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public and `langchain-algenta` installable (see `README.md` blockers).
- [ ] Do not mention `ChatAlgenta` as forthcoming without re-checking Track C's actual status in `thyn-ai/algenta` first — see [Capability status](../gitbook/trust/capability-status.md).
- [ ] Confirm which LangChain integration-review venue is current before naming one in the final send (community integrations move venues periodically).
