"""Algenta product editions — the single source of truth for the curated tool
subset each vertical product exposes.

Algenta is the engine; each product (Codna=coding, Cohenta=marketing,
Decimas=trading, Escrypto=crypto governance) is a curated *edition* over the same
MCP/API core. ``X-Algenta-Product`` / ``ALGENTA_PRODUCT`` selects an edition.

SECURITY MODEL — the product selector is a ROUTING HINT, not authorization:

  visible_tools = product_allowlist ∩ key_entitlements ∩ organization_policy
                  ∩ feature_entitlements          # what is listed/callable

Usage limits (rate limit, monthly quota, managed-LLM spend cap) are enforced
separately, at call time, on a *visible* tool — they gate execution, they do not
hide tools.

FAIL CLOSED: an unknown/unentitled/not-yet-shipped product resolves to the EMPTY
set (no tools), never the full Algenta registry.
"""

from __future__ import annotations

from collections.abc import Iterable

# ── Codna — coding edition (the first shipped vertical) ──────────────────────
CODNA_CODING_TOOLS: frozenset[str] = frozenset(
    {
        # repository intelligence (the headline flow)
        "get_repository_intelligence_capabilities",
        "create_repository_snapshot",
        "get_repository_snapshot",
        "triage_repository",
        "create_repository_decision_plan",
        "query_repository_graph",
        "simulate_repository",
        "simulate_repository_patch",
        "run_repository_fix",
        "run_repository_pipeline",
        "apply_repository",
        # decision primitives the agent composes with
        "plan_decision",
        "simulate",
        "recommend",
        # decision memory (close the loop)
        "log_decision",
        "list_decisions",
        "get_decision",
        "record_outcome",
        # agent runs (long-running verified fixes)
        "create_agent_run",
        "get_agent_run",
        "get_agent_run_events",
        "cancel_agent_run",
        # account / metering visibility (onboarding + quota UX)
        "get_me",
        "get_limits",
        "get_usage",
    }
)

# Forward-looking verticals — intentionally EMPTY until each product ships, so
# selecting them fails closed (no tools) rather than exposing the full registry.
COHENTA_MARKETING_TOOLS: frozenset[str] = frozenset()
DECIMAS_TRADING_TOOLS: frozenset[str] = frozenset()
ESCRYPTO_GOVERNANCE_TOOLS: frozenset[str] = frozenset()

PRODUCT_EDITIONS: dict[str, frozenset[str]] = {
    "codna": CODNA_CODING_TOOLS,
    "cohenta": COHENTA_MARKETING_TOOLS,
    "decimas": DECIMAS_TRADING_TOOLS,
    "escrypto": ESCRYPTO_GOVERNANCE_TOOLS,
}


def product_allowlist(product: str | None) -> frozenset[str] | None:
    """Curated allowlist for a product edition.

    - ``None`` product  → ``None``  (no edition restriction; an unscoped/trusted
      key sees the full registry — preserves existing direct-integration behavior).
    - known product     → its allowlist (EMPTY for not-yet-shipped verticals).
    - unknown product   → EMPTY frozenset (fail closed).
    """
    if product is None:
        return None
    return PRODUCT_EDITIONS.get(product, frozenset())


def resolve_visible_tools(
    product: str | None,
    *,
    constraints: Iterable[frozenset[str] | None] = (),
) -> frozenset[str] | None:
    """Compute the visible tool set: ``product_allowlist ∩ constraints``.

    ``constraints`` are additional allow-sets resolved upstream from the verified
    key (e.g. key entitlements, organization policy, feature entitlements). A
    ``None`` constraint means "no restriction from this dimension" and is skipped.

    Returns ``None`` only when there is NO product and NO constraint (full
    registry). Once any dimension restricts, the result is a concrete set;
    intersection with the empty set (unknown/unentitled product) yields the empty
    set — fail closed.
    """
    effective: frozenset[str] | None = product_allowlist(product)
    for c in constraints:
        if c is None:
            continue
        effective = c if effective is None else (effective & c)
    return effective
