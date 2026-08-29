# vLLM — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For vLLM specifically: no certification language, ever — the ask is a validated-backend integration, not a "vLLM-certified" claim, and the package's own honest capability-gap documentation should be quoted rather than smoothed over.

## What backs this

- **`vllm-algenta`** (`python/vllm-algenta` in `thyn-ai/algenta-integrations`): a thin `build_client`/`build_async_client` helper pointing the standard, unmodified `openai` Python client at the engine's own `/v1/chat/completions`/`/v1/responses` surface, plus a conformance suite run against a stub built field-for-field from the engine's real schema (`apps/api_server/schemas/llm.py`). Status: **In conformance testing** for the shared cross-framework suite.
- **A real, important caveat to verify before sending, not after:** the package's own README documents a capability-gap table (no tool/function calling on `/v1/chat/completions`, a hardcoded `finish_reason: "stop"`, `stream=true` as post-hoc rechunking rather than incremental generation). As of this outreach draft being written, `thyn-ai/algenta`'s Chat Completions surface has since gained a widened `finish_reason` (`stop`/`length`/`tool_calls`/`content_filter`) and a real tool round-trip — see [Capability status](../gitbook/trust/capability-status.md). **Re-verify `vllm-algenta`'s own gap table against the engine's current state before this draft is sent** — it may already be stale in the package's favor, and sending an outdated self-deprecating gap table is exactly as dishonest as sending an inflated one.

## The ask

Confirm the correct listing path for a validated-backend integration — vLLM's own backend-compatibility documentation, or a community-integrations listing — once the capability-gap table above is re-verified and current.

## Before sending

- [ ] **Do not send until the capability-gap table is re-verified against the current engine.** This is the one draft in this kit where the known-stale direction is "the artifact undersells the current engine," which still must be corrected before sending — an outreach draft should never contain a claim its own author knows is wrong, even when the error makes the claim more modest.
- [ ] Confirm `thyn-ai/algenta-integrations` is public and `vllm-algenta` installable (see `README.md` blockers).
- [ ] Never describe this integration as "vLLM-certified" or similar — that language is banned outright by this program's claim discipline, not merely unearned yet.
