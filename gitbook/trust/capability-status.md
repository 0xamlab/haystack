---
icon: list-check
description: Every protocol surface and integration, labeled Available now, Validated integration, or In conformance testing — checked against the current code and tests, not restated from an announcement.
---

# Capability status

Three labels, used consistently across this section and never substituted for a stronger word:

| Label | Means |
| --- | --- |
| **Available now** | The code is merged on `main`, has passing tests, and you can exercise it against your own deployment today. |
| **Validated integration** | Available now, *and* the [cross-framework conformance suite](../mcp-tools/overview.md) passes for that specific integration. |
| **In conformance testing** | The code exists and is exercised by its own tests, but the specific validation this page would need to say "Validated" has not run yet, or has run and did not fully pass. |

Terms this page and the rest of this section do not use without that evidence behind them: "production-proven," "battle-tested," "certified," or any customer-adoption claim. Where a control below is absent rather than partial, it says so plainly rather than being omitted.

Every row was checked directly against source in `thyn-ai/algenta` (this repository) or `thyn-ai/algenta-integrations` at the time this page was written, not carried forward from an earlier status. Re-verify anything load-bearing before relying on it.

## Protocol surfaces (this repository)

| Surface | Status | Evidence |
| --- | --- | --- |
| MCP over stdio | Available now | `apps/mcp_server/transports/stdio.py`; see [MCP tools](../mcp-tools/overview.md) |
| MCP over Streamable HTTP (2025-11-25 sessionful handshake) | Available now | `apps/mcp_server/transports/http_sse.py` |
| MCP 2026-07-28 stateless per-request envelope (`server/discover`, no handshake) | Available now | Dual-served by the same `on_list_tools`/`on_call_tool` handlers as the 2025-11-25 path — one implementation, negotiated by the MCP SDK per request, not two code paths to keep in sync |
| MCP tool registry: 140 tools | Available now | Both `apps/mcp_server/registry.py` and the `packages/mcp` counterpart (`algenta_mcp/registry.py`) agree on the count |
| Per-edition MCP tool allowlists + opt-in full registry | Available now | `apps/mcp_server/products.py` |
| RFC 9728 protected-resource metadata (`/.well-known/oauth-protected-resource`, `.../mcp`) | Available now | `apps/api_server/routers/oauth_protected_resource.py` — 404s when no authorization server is configured, rather than advertising one that doesn't exist |
| `POST /v1/responses` — typed input array, tool calls, `previous_response_id` continuation | Available now | `apps/api_server/routers/llm.py`; contract test at `tests/test_llm_responses_tool_calling_contract.py` |
| `POST /v1/responses` — OpenResponses-spec conformance (external CLI compliance runner in CI) | **Not built** | No `openresponses` CLI wiring exists in this repository yet. Do not describe `/v1/responses` as "OpenResponses conformant" until that runner is green in CI. |
| `POST /v1/responses` — approval-required event for a policy-gated tool call | **Not built on this route** | The approval-required pause/resume pattern exists on `POST /v1/capabilities/execute` (see below), not yet threaded through as a Responses-protocol event |
| `/v1/chat/completions` — widened `finish_reason`, typed `model_capability_unsupported` 422, tool round-trip | Available now | `apps/api_server/routers/llm.py:471` onward |
| `/v1/chat/completions` — single capability-flag table (`supported_parameters`, `streaming_mode`) surfaced from one source | **Not built as a single table** | `GET /v1/models` reports real per-model `capabilities`/`supported_endpoints`/`available` fields (see below) rather than the specific `supported_parameters`/`streaming_mode` shape described in earlier planning notes — treat the live response as the source of truth, not this page |
| `GET /v1/models` — live capability descriptors (`capabilities`, `supported_endpoints`, `provider_auth_configured`, `available`, routing/fallback fields) | Available now | `apps/api_server/routers/llm.py:346` |
| Local inference (Qwen3-family, Metal decode) as a provider | Available now for synchronous generation; benchmarked | See [LLM inference overview](../benchmarks/llm-inference-overview.md); true token-by-token streaming is still pending — see the executor's own note below |
| Local inference true token streaming | **Not built** | `_executors_local.py` re-chunks a complete reply rather than streaming tokens as they generate; the code's own comment names this "persistent sessions" as the blocking gap |
| Governed execution lifecycle (`propose → approve → execute`, `plan_hash` + single-use nonce, named denial codes) | Available now | [Governed execution](governed-execution.md); `apps/api_server/routers/decision_cases.py` |
| Execution receipt (`ExecutionReceipt`, schema-versioned, `receipt_version: "1"`) | Available now | `apps/api_server/schemas/receipt.py`; walkthrough at [Evidence walkthrough](evidence-walkthrough.md) |
| Capability-plane approval gate (`POST /v1/capabilities/execute` returns `status: "approval_required"` + `plan_id`/`plan_hash`/`nonce` instead of executing, when a capability's catalog entry opts in) | Available now — merged very recently | `apps/api_server/services/capability_plane/_execution.py`; `tests/test_capability_plane_approval_gate.py`. This is newer than the cross-framework conformance suite run recorded below, which found no pause/resume path — this gate is why that finding may already be stale; it has not been re-measured against this gate yet, so this page states both facts rather than only the more flattering one. |
| Audit log export (`GET /v1/audit-logs/export.{fmt}`) with `X-Content-SHA256` | Available now | [Audit and evidence](audit-and-evidence.md); [Evidence walkthrough](evidence-walkthrough.md) |
| OpenAPI truth (spec regenerated from the live app, not hand-edited; drift-gated in CI) | Available now | `schemas/openapi/openapi.yaml` — 240 paths as of this writing; `tests/test_openapi_spec_drift.py` |
| API stability contract (versioned aliases, deprecation headers, sunset dates) | Available now | [API stability](../api/stability.md) |
| Generic OIDC (Okta / Auth0 / Keycloak) | Available now | `apps/api_server/services/oidc_auth.py`, wired at `apps/api_server/middleware/auth.py`; `tests/test_oidc_auth.py`, `tests/test_oidc_middleware_wiring.py` |
| Microsoft Entra ID | Available now (code path, verified by tests) | Production tenant/audience configuration for a given deployment is an operator/owner action, not a code gap — see [Identity and access](identity-and-access.md) |
| SBOM generation (SPDX + CycloneDX) per image, by digest | Available now | `.github/actions/image-sbom-scan/action.yml`; see [Supply chain](supply-chain.md) |
| Vulnerability scan (grype) per image | Available now — advisory, not a release gate | Same action; see [Supply chain](supply-chain.md) |
| Image signing (cosign) | **Not built** | Deliberately deferred — see [Supply chain](supply-chain.md) for why and what it's waiting on |
| SLSA/in-toto provenance attestation | **Not built** | Not started |
| VEX statements for triaged findings | **Not built** | Not started |
| Helm chart | Available now — merged and validated with a real `kind` cluster in CI | `infra/helm/algenta/`; `engine.replicaCount` is hardcoded to `1` (schema-enforced, and the Deployment template itself refuses anything else) — this is honest single-instance framing, not an oversight. Chart is pushed as an OCI artifact but **not signed** (blocked on the same image-signing decision as [Supply chain](supply-chain.md)) |

## Framework integrations (`thyn-ai/algenta-integrations`)

The engine-side conformance suite (12 named scenarios; see [Protocol compatibility](protocol-compatibility.md) for what it measures and what it found) is the baseline every framework package must reproduce through its own client before it earns **Validated integration**. As of this writing, no framework package has been run against that shared suite yet — each package's own repository states this explicitly, so this page states it too rather than rounding up.

| Ecosystem | Package | Status |
| --- | --- | --- |
| Pydantic AI | `pydantic-ai-algenta` | In conformance testing — real toolset wrapper, profile filtering, typed denial mapping, own test suite passing; not yet run against the shared conformance suite |
| LangChain / LangGraph | `langchain-algenta` | In conformance testing — same shape as above |
| LiteLLM (MCP Gateway, Lane 1) | `litellm-algenta` | In conformance testing — config generator + real proxy-process test suite passing; Lane 2 (a native `CustomLLM` provider upstreamed to LiteLLM itself) is out of scope until Chat Completions streaming/tools work lands here |
| Microsoft Agent Framework | `maf-algenta` | In conformance testing — real wrapper over MAF's own MCP tool primitives, tests passing |
| Microsoft Foundry | `maf-algenta/foundry/` (Bicep + Toolbox artifacts) | Documentation-only deliverable, explicitly not independently verified against a live Foundry project (none available to verify against) |
| Vercel AI SDK | `@thyn-ai/algenta-tools` | In conformance testing |
| n8n | `n8n-nodes-algenta` | In conformance testing — real community node; not eligible for n8n's own Cloud verification program (that program bans the runtime dependency this node genuinely needs) |
| Haystack | `haystack-algenta` | In conformance testing |
| LlamaIndex | `llamaindex-algenta` | In conformance testing |
| Ray Serve | `ray-serve-algenta` | In conformance testing — its own multi-replica test proves interleaved concurrent calls route across 2 live replicas with no cross-replica state leakage; that is a real, narrower result than full conformance |
| vLLM | `vllm-algenta` | In conformance testing — includes its own honest capability-gap table (no tool/function calling on `/v1/chat/completions` today; a hardcoded `finish_reason: "stop"`; `stream=true` is post-hoc rechunking, not incremental backend generation) |

Two facts govern every claim about this repository, independent of any individual package's status:

- **Not installable from a public registry yet.** Every package 404s on PyPI and npm today. Publishing needs two owner-side actions (Trusted Publisher registration per package, then flipping a repository variable) — the release pipeline itself already runs on every tagged release and would publish immediately once those two switches are set.
- **The repository's visibility is a standing, deliberate decision, not an oversight.** It has not been made public yet. Nothing in this section, and no outreach material built from it, should imply a partner can browse the code today — see [Support policy](support-policy.md) and the outreach materials for how this is tracked as an explicit pre-send condition.

## What "reproducible benchmark evidence" means here

22 published benchmark pages under [Benchmarks](../benchmarks/overview.md), each with a named baseline, reported hardware, and a reproduction command — not a single one of them a hypothetical. Statistical-significance claims that depend on the engine's own incomplete-beta implementation are excluded from publication until that implementation is verified against a reference; no benchmark page makes a p-value claim today.

## Next steps

- [Protocol compatibility](protocol-compatibility.md)
- [Architecture and trust boundaries](architecture.md)
- [Evidence walkthrough](evidence-walkthrough.md)
- [Trust overview](overview.md)
