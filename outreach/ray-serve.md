# Ray Serve — draft outreach

**DRAFT — NOT SENT.** Requires human review. See [`README.md`](README.md) for pre-send blockers.

## Pitch

> Algenta is compiler-driven, self-hosted AI infrastructure: modular building blocks for AI applications, compiled into one deterministic runtime. The mature integration surface is MCP, with deterministic simulation, policy gates, approvals, execution receipts, and audit evidence running inside the customer's infrastructure. We have built a runnable integration for your ecosystem and would like to validate the correct contribution and listing path with your team.

For Ray Serve specifically: the pitch here is narrower and more concrete than the others — a real, measured multi-replica result, not a general governance-toolkit pitch (this package doesn't parse MCP content or reason about tool names at all; profile enforcement stays the connected engine's job).

## What backs this

- **`ray-serve-algenta`** (`python/ray-serve-algenta` in `thyn-ai/algenta-integrations`): a byte-transparent Ray Serve reverse proxy (`AlgentaMCPProxy`) for the engine's stateless `/mcp` surface — verified directly against this repository's own `apps/mcp_server/README.md` statement that the canonical `/mcp` route implements stateless Streamable HTTP (see [Protocol compatibility](../gitbook/trust/protocol-compatibility.md)). Its own conformance suite runs a real 2-replica `serve.run(...)` and proves, over real HTTP with a real MCP client, that interleaved concurrent calls route across both live replicas with zero cross-replica state leakage. A KubeRay `RayService` manifest (`manifests/rayservice.yaml`) ships with autoscaling floored at 2 replicas. Status: **In conformance testing** for the shared cross-framework suite; the 2-replica routing result itself is a real, narrower, already-measured result — described that way, not rounded up to "conformance-validated."

## The ask

Confirm the correct listing path for a stateless-MCP deployment pattern on Ray Serve — an example in Ray's own serve-examples directory, or a docs reference — and whether the multi-replica routing proof is useful as a general pattern for other stateless MCP servers on Ray Serve, independent of Algenta specifically.

## Before sending

- [ ] Confirm `thyn-ai/algenta-integrations` is public and `ray-serve-algenta` installable (see `README.md` blockers).
- [ ] Confirm the pinned Ray/KubeRay versions this was built and tested against are still current before finalizing.
- [ ] Do not describe this as validating Algenta's MCP tool behavior generally — it specifically validates transport-level stateless routing, and the draft should keep that scope narrow.
