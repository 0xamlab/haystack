# LiteLLM — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For LiteLLM specifically: this is **not** another LLM provider pitch. The integration is a governed MCP execution service that sits behind the MCP Gateway your project already ships — the pitch should center that, not model routing.

## What backs this

- **Lane 1 — MCP Gateway integration** (`python/litellm-algenta` in `thyn-ai/algenta-integrations`): a config generator/linter mapping the shared tool-profile contract onto LiteLLM's real, verified `allowed_tools`/`allowed_params` enforcement, ready-to-use per-profile config templates (`observe`/`govern`/`execute`/`full`, including an OAuth2-client-credentials variant), and a conformance suite that runs a real `litellm` proxy process against a real stub MCP server — never mocked. Status: **In conformance testing** for the shared cross-framework suite; the gateway-level config/proxy tests themselves pass today.
- **Lane 2 — native `CustomLLM` provider, upstreamed to LiteLLM itself**: out of scope until Algenta's own Chat Completions surface has real streaming, tool calling, and capability flags fully contract-tested (Track C). Check [Capability status](../gitbook/trust/capability-status.md) before claiming this lane is unblocked — as of this writing, `/v1/chat/completions` has a widened `finish_reason` and a real tool round-trip, but true per-backend streaming and a single capability-flag table are not both landed.

## The ask

Confirm the correct path to list a self-hosted MCP Gateway integration — a community config/docs contribution, or something LiteLLM's project maintains a registry for — and whether Lane 1 alone (gateway config, no code dependency on LiteLLM's own repo) is reviewable now, ahead of any Lane 2 provider PR.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public and the package installable (see `README.md` blockers) — Lane 1's config templates need to be something a LiteLLM maintainer can actually pull down.
- [ ] Re-verify Track C's Chat Completions status before mentioning Lane 2 at all — if it has progressed, update the specific gap named above rather than deleting the caveat.
- [ ] Do not describe Lane 1 as "a LiteLLM integration" in a way that implies LiteLLM's own repository depends on anything here — it's a gateway configured to point at Algenta, nothing upstreamed.
