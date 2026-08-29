---
icon: table-columns
description: MCP version negotiation, the Responses and Chat Completions surfaces, and the 12-scenario conformance suite's real results — 9 passed, 0 failed, 3 blocked with named reasons.
---

# Protocol compatibility

This page is the matrix version of [Capability status](capability-status.md): narrower, focused only on the three protocol surfaces a framework or gateway integrates against, plus the one suite that turns "we built an integration" into "the integration behaves correctly."

## MCP protocol versions

| Version | Handshake | Status | Notes |
| --- | --- | --- | --- |
| stdio | N/A — local process | Available now | Used by desktop MCP hosts (Cursor, Claude Desktop, Zed, Windsurf, VS Code) |
| 2025-11-25 (Streamable HTTP, sessionful) | `initialize`/`initialized`, `Mcp-Session-Id` | Available now | Existing HTTP clients continue to work unchanged |
| 2026-07-28 (stateless per-request envelope) | None — self-contained requests, `server/discover` for capability discovery | Available now | Served by the same request handlers as 2025-11-25; there is one implementation, not a fork, so this is not "aspirationally planned" — it is the same code path the 2025-11-25 tests already exercise |

Both versions negotiate per request against the protocol-version header the MCP SDK reads; there is no server-side flag to flip between them. Legacy SSE remains available alongside Streamable HTTP for older clients.

Auth on the HTTP transports: bearer API keys, plus [RFC 9728 protected-resource metadata](https://www.rfc-editor.org/rfc/rfc9728) at `/.well-known/oauth-protected-resource` and `/.well-known/oauth-protected-resource/mcp` — both return 404 rather than advertising an authorization server when none is configured for the deployment.

**What "MCP 2026-07-28 conformant" would require, and hasn't run yet:** a behavioral matrix against the official SDKs (Python, TypeScript, at minimum) proving discovery, filtered tool exposure, authenticated and denied invocation, and load-balanced stateless operation across replicas. The dual-serving above is real; a green run of that specific matrix is the gate before this page (or any outreach material) calls the server conformant to the spec by name.

## Responses surface (`POST /v1/responses`)

| Capability | Status |
| --- | --- |
| Typed input array (`message` / `function_call` / `function_call_output` items) | Available now |
| Tool calling in a real multi-turn conversation | Available now |
| `previous_response_id` continuation | Available now |
| Streaming (SSE) | Available now |
| Approval-required pause/resume as a Responses-protocol event | Not built on this route (see [Capability status](capability-status.md) for where that pattern does exist today) |
| OpenResponses OpenAPI schema conformance, verified by its own CLI compliance runner in CI | Not built |

Until the CLI runner is wired in and green, this surface is described as "the Responses-shaped envelope Algenta implements," not as "OpenResponses compatible."

## Chat Completions surface (`POST /v1/chat/completions`)

| Capability | Status |
| --- | --- |
| `finish_reason` (`stop` / `length` / `tool_calls` / `content_filter`) | Available now |
| Tool round-trip (`tools`, `tool_choice`, assistant `tool_calls`, `tool` role) | Available now |
| Typed `422 model_capability_unsupported` when a model/backend can't do what was asked (e.g. streaming tool calls on a model that doesn't support them) | Available now |
| A single published capability-flag table (`supported_parameters` per model) | Not built as a standalone table — use the live `capabilities`/`supported_endpoints`/`available` fields on `GET /v1/models` instead, which are real and queryable today |

```bash title="check what a specific model actually supports, live"
curl -sS "$ALGENTA_BASE_URL/v1/models" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  | jq '.data[] | {id, capabilities, supported_endpoints, available}'
```

## The 12-scenario conformance suite

Defined once, in `demo/fixtures/expected.json` in `thyn-ai/algenta-integrations`, and run by `demo/conformance/runner.py` against a real self-hosted engine over HTTP with a real Postgres — never a mock. This suite is the "Validated integration" gate itself: no framework package earns that label without a passing run of its own client against these same scenarios, and none has run yet (see [Capability status](capability-status.md)).

The engine-level baseline run (the one every framework adapter must reproduce) recorded **9 passed, 0 failed, 3 blocked** — deliberately not reported as "12 passed" or "9 passed, 3 skipped," because a blocked scenario is not a pass and `pytest.skip`-style silence reads like success when it isn't.

| # | Scenario | Result |
| --- | --- | --- |
| 1 | Successful read-only recommendation | Passed |
| 2 | Execution denied by policy (409 named gate) | Passed |
| 3 | Execution paused for approval | Blocked — see note below |
| 4 | Approval granted, execution resumed | Passed |
| 5 | Approval rejected | Passed |
| 6 | Duplicate execution prevented (idempotency key) | Passed |
| 7 | Expired / reused approval rejected | Passed |
| 8 | Modified `plan_hash` rejected | Passed |
| 9 | Upstream timeout surfaced as a typed retryable error | Blocked — needs fault-injection infrastructure this suite doesn't have yet |
| 10 | Execution receipt (versioned envelope) | Passed |
| 11 | Audit export whose `X-Content-SHA256` verifies | Passed |
| 12 | Replay produces the same deterministic result | Blocked — this configuration runs with the Mojo runtime disabled, so there is nothing deterministic to compare |

**Why scenario 3 was blocked, and why that may already be out of date.** At the time that run was recorded, the decision-plan lifecycle (`propose → approve → execute`) *refuses* an unapproved execute with `409 plan_not_approved` rather than *pausing* — there was no suspended-execution state to resume from. Separately, and more recently, `POST /v1/capabilities/execute` shipped a real approval-required pause/resume path: a capability whose catalog entry opts into `approval_required` returns `status: "approval_required"` plus `plan_id`/`plan_hash`/`nonce` instead of executing, and a subsequent approved call resumes it (see [Capability status](capability-status.md)). That shipped after the conformance run above and has not been measured by it yet. Read scenario 3 as "blocked as of the last recorded run," not as "impossible" — and don't upgrade it to "passed" until the suite is actually re-run and says so.

**Why the suite is trustworthy rather than decorative:** the same runner was pointed at an earlier commit of the engine (before the audit export, receipt envelope, and named error codes existed) and returned **2 passed, 7 failed** with diagnostic, non-vague failures — a flattened HTTP error where a named gate should have been, a missing receipt envelope, a 404 where the export route now exists. Both runs are committed as evidence in that repository. A suite that cannot fail is not a gate.

## Next steps

- [Capability status](capability-status.md)
- [Evidence walkthrough](evidence-walkthrough.md)
- [Architecture and trust boundaries](architecture.md)
