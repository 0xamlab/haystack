"""Algenta product editions and their curated MCP tool subsets.

``X-Algenta-Product`` / ``ALGENTA_PRODUCT`` selects an edition. Compatibility
aliases remain accepted for existing integrations but are not documentation
surfaces for separate products.

SECURITY MODEL — the product selector is a ROUTING HINT, not authorization:

  visible_tools = product_allowlist ∩ key_entitlements ∩ organization_policy
                  ∩ feature_entitlements          # what is listed/callable

Explicit endpoint, provider, and operator controls are enforced separately at
call time on a *visible* tool; they do not hide tools. Algenta editions have no
monthly execution quota or edition request meter.

FAIL CLOSED: an unknown/unentitled/not-yet-shipped product resolves to the EMPTY
set (no tools), never the full Algenta registry.
"""

from __future__ import annotations

from collections.abc import Iterable

# Public Algenta coding and repository-intelligence edition.
ALGENTA_CODING_TOOLS: frozenset[str] = frozenset(
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

PRODUCT_EDITIONS: dict[str, frozenset[str]] = {
    "algenta": ALGENTA_CODING_TOOLS,
    "codna": ALGENTA_CODING_TOOLS,
}

# ── Feature → tool map ───────────────────────────────────────────────────────
# A v2 license grants per-product *features*; this maps each granted feature to the
# concrete tools it unlocks. The local engine intersects this with the product
# allowlist: available_tools = installed ∩ product_allowlist ∩ license_feature_tools.
# Every Algenta tool is reachable via a base/feature bucket (invariant-tested:
# base plus all feature tools equals ALGENTA_CODING_TOOLS), so a fully-featured license exposes the
# full edition.
_ALGENTA_BASE_TOOLS: frozenset[str] = frozenset(
    {"get_me", "get_limits", "get_usage", "get_repository_intelligence_capabilities"}
)
_ALGENTA_FEATURE_TOOLS: dict[str, frozenset[str]] = {
    "repo_graph": frozenset(
        {"query_repository_graph", "create_repository_snapshot", "get_repository_snapshot"}
    ),
    "triage": frozenset({"triage_repository", "create_repository_decision_plan"}),
    "simulate": frozenset(
        {
            "simulate_repository",
            "simulate_repository_patch",
            "simulate",
            "plan_decision",
            "recommend",
            "log_decision",
            "list_decisions",
            "get_decision",
            "record_outcome",
        }
    ),
    "fix": frozenset(
        {
            "run_repository_fix",
            "run_repository_pipeline",
            "create_agent_run",
            "get_agent_run",
            "get_agent_run_events",
            "cancel_agent_run",
        }
    ),
    "apply": frozenset({"apply_repository"}),
}

PRODUCT_BASE_TOOLS: dict[str, frozenset[str]] = {
    "algenta": _ALGENTA_BASE_TOOLS,
    "codna": _ALGENTA_BASE_TOOLS,
}
PRODUCT_FEATURE_TOOLS: dict[str, dict[str, frozenset[str]]] = {
    "algenta": _ALGENTA_FEATURE_TOOLS,
    "codna": _ALGENTA_FEATURE_TOOLS,
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


def feature_tool_constraint(
    product: str | None, features: Iterable[str] | None
) -> frozenset[str] | None:
    """Map a v2 license's granted *features* for a product to the tools they unlock.

    Returns ``None`` when there is no feature-level narrowing to apply (the product has
    no feature map, or the license grants the product with no specific feature list — the
    full product allowlist stands). Pass the result straight into ``resolve_visible_tools``
    as a constraint (``None`` = no narrowing from this dimension).

    Returns a concrete frozenset (base tools ∪ the tools for each granted feature) when
    features are specified, narrowing the product allowlist to exactly the licensed
    features — fail-closed for any unknown feature (it contributes no tools).
    """
    feat_map = PRODUCT_FEATURE_TOOLS.get(product) if product else None
    if feat_map is None:
        return None
    feats = frozenset(features or ())
    if not feats:
        return None
    tools: set[str] = set(PRODUCT_BASE_TOOLS.get(product or "", frozenset()))
    for feature in feats:
        tools |= feat_map.get(feature, frozenset())
    return frozenset(tools)
