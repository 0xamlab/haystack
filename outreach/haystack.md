# Haystack — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is a self-hosted governed execution layer for agents. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For Haystack specifically: this wraps Haystack's own `MCPToolset` rather than reimplementing MCP transport — the value-add is entirely the governance layer `MCPToolset` doesn't express on its own (tool-profile enforcement, approval/denial semantics, receipt typing), which also validates Haystack's own published guidance that more than 20-30 tools handed to a model at once is a real problem their `tool_names=` filtering exists to solve.

## What backs this

- **`haystack-algenta`** (`python/haystack-algenta` in `thyn-ai/algenta-integrations`): a real, tested `create_algenta_tools` wrapping Haystack's own `MCPToolset` (tool-profile filtering via its native `tool_names=`, two-layer never-model-facing field scrubbing via a rebuilt `Tool`) plus `build_algenta_governance_hooks` — an `Agent` `after_tool` hook raising a typed `AlgentaToolDenied` for `execute_decision`'s real synchronous 409 denial, via Haystack's own `after_tool` hook seam (not a monkey-patch). Status: **In conformance testing** — its own test suite passes (including `test_hooks.py`, `test_profile_filtering.py`); not yet run against the shared cross-framework conformance suite.

## The ask

Confirm the correct listing path — Haystack's integrations directory/docs, or a different venue for governance-layer packages built on `MCPToolset` — and whether the `after_tool` hook pattern for typed policy-gate denials is useful to document as a general integration pattern, independent of Algenta specifically.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public and `haystack-algenta` installable (see `README.md` blockers).
- [ ] Confirm the package still targets the same Haystack/`mcp-haystack` version combination it was built and tested against — pin versions explicitly in the final send.
