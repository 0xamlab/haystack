"""Product-edition routing for the MCP surface (Algenta plugin platform, Phase 0).

Verifies the single-source product registry, the Algenta coding allowlist's
integrity against the live tool registry (anti-drift), and the fail-closed
visibility filter on ``get_tool_specs`` / ``call_tool``.
"""

from __future__ import annotations

import asyncio

import pytest

from apps.mcp_server import products
from apps.mcp_server.registry import TOOLS, call_tool, get_tool_specs


def test_product_registry_has_all_four_verticals() -> None:
    assert set(products.PRODUCT_EDITIONS) == {"codna", "cohenta", "decimas", "escrypto"}
    # Algenta is the only edition populated so far; the rest fail closed (empty) until shipped.
    assert products.PRODUCT_EDITIONS["codna"]
    assert products.PRODUCT_EDITIONS["cohenta"] == frozenset()
    assert products.PRODUCT_EDITIONS["decimas"] == frozenset()
    assert products.PRODUCT_EDITIONS["escrypto"] == frozenset()


def test_codna_allowlist_is_subset_of_live_registry() -> None:
    """Anti-drift: every tool the Algenta edition advertises must exist in the registry."""
    missing = products.PRODUCT_EDITIONS["codna"] - set(TOOLS)
    assert not missing, f"Algenta edition references tools absent from the registry: {sorted(missing)}"


def test_product_allowlist_fails_closed() -> None:
    assert products.product_allowlist(None) is None  # unscoped → full registry
    assert products.product_allowlist("codna") == products.PRODUCT_EDITIONS["codna"]
    assert products.product_allowlist("unknown") == frozenset()  # fail closed
    assert products.product_allowlist("cohenta") == frozenset()  # not-yet-shipped → fail closed


def test_resolve_visible_tools_intersects_and_fails_closed() -> None:
    codna = products.PRODUCT_EDITIONS["codna"]
    assert products.resolve_visible_tools(None) is None
    assert products.resolve_visible_tools("codna") == codna
    # entitlement constraint narrows the edition
    ent = frozenset({"triage_repository", "get_me", "delete_connector"})
    assert products.resolve_visible_tools("codna", constraints=[ent]) == frozenset(
        {"triage_repository", "get_me"}
    )
    # unknown product ∩ anything → empty (fail closed)
    assert products.resolve_visible_tools("unknown", constraints=[ent]) == frozenset()


def test_get_tool_specs_respects_allowed() -> None:
    full = get_tool_specs()
    assert len(full) == len(TOOLS)  # None → full registry (backward compatible)

    codna = products.PRODUCT_EDITIONS["codna"]
    scoped = get_tool_specs(allowed=codna)
    names = {spec["name"] for spec in scoped}
    assert names == set(codna)

    assert get_tool_specs(allowed=frozenset()) == []  # fail-closed → no tools


def test_scope_product_reads_header() -> None:
    from apps.mcp_server.transports.http_sse import _scope_product

    assert _scope_product({"headers": [(b"x-algenta-product", b"codna")]}) == "codna"
    assert _scope_product({"headers": [(b"x-algenta-product", b"  ")]}) is None  # blank → None
    assert _scope_product({"headers": []}) is None  # absent → None (full)


def test_mcp_tools_route_filters_by_product_header() -> None:
    """End-to-end: the embedded /mcp/tools route honors X-Algenta-Product, fail-closed."""
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from apps.mcp_server.transports.http_sse import _build_fastapi_router

    router = _build_fastapi_router()
    assert router is not None
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # no product header → full registry (backward compatible)
    full = client.get("/mcp/tools").json()["tools"]
    assert len(full) == len(TOOLS)

    # X-Algenta-Product: codna → exactly the coding edition
    codna = client.get("/mcp/tools", headers={"X-Algenta-Product": "codna"}).json()["tools"]
    assert {t["name"] for t in codna} == set(products.PRODUCT_EDITIONS["codna"])

    # unknown / not-yet-shipped product → empty (fail closed, never full registry)
    unknown = client.get("/mcp/tools", headers={"X-Algenta-Product": "nope"}).json()["tools"]
    assert unknown == []
    cohenta = client.get("/mcp/tools", headers={"X-Algenta-Product": "cohenta"}).json()["tools"]
    assert cohenta == []


def test_call_tool_rejects_out_of_edition() -> None:
    codna = products.PRODUCT_EDITIONS["codna"]
    out_of_edition = next(name for name in TOOLS if name not in codna)
    # Rejected as if it did not exist (before the handler runs) — fail closed.
    with pytest.raises(KeyError):
        asyncio.run(call_tool(out_of_edition, {}, allowed=codna))
    # An entirely unknown tool is rejected too.
    with pytest.raises(KeyError):
        asyncio.run(call_tool("does_not_exist", {}, allowed=codna))


# ── P2: license product/feature → tool-gating ───────────────────────────────


def test_feature_tool_constraint_maps_features_to_tools() -> None:
    got = products.feature_tool_constraint("codna", ["repo_graph", "triage"])
    base = products.PRODUCT_BASE_TOOLS["codna"]
    feat = products.PRODUCT_FEATURE_TOOLS["codna"]
    assert got == base | feat["repo_graph"] | feat["triage"]
    assert got <= products.PRODUCT_EDITIONS["codna"]  # never exceeds the edition
    assert "apply_repository" not in got  # ungranted feature's tools excluded


def test_feature_tool_constraint_full_features_equals_edition() -> None:
    # Invariant: every codna tool is reachable via base ∪ exactly the granted features,
    # so a fully-featured license == the full edition (no orphaned/unreachable tools).
    base = products.PRODUCT_BASE_TOOLS["codna"]
    union = set(base)
    for tools in products.PRODUCT_FEATURE_TOOLS["codna"].values():
        union |= tools
    assert frozenset(union) == products.PRODUCT_EDITIONS["codna"]
    all_features = list(products.PRODUCT_FEATURE_TOOLS["codna"].keys())
    assert products.feature_tool_constraint("codna", all_features) == products.PRODUCT_EDITIONS[
        "codna"
    ]


def test_feature_tool_constraint_none_when_no_narrowing() -> None:
    assert products.feature_tool_constraint("codna", []) is None  # product, no feature list
    assert products.feature_tool_constraint("codna", None) is None
    assert products.feature_tool_constraint("cohenta", ["x"]) is None  # no feature map
    assert products.feature_tool_constraint(None, ["repo_graph"]) is None


def test_feature_tool_constraint_unknown_feature_yields_base_only() -> None:
    # A license granting only an unknown feature gets base tools only — fail closed.
    assert products.feature_tool_constraint("codna", ["bogus"]) == products.PRODUCT_BASE_TOOLS[
        "codna"
    ]


def test_resolve_visible_tools_narrows_by_license_feature_constraint() -> None:
    constraint = products.feature_tool_constraint("codna", ["triage"])
    visible = products.resolve_visible_tools("codna", constraints=[constraint])
    feat = products.PRODUCT_FEATURE_TOOLS["codna"]
    assert visible == products.PRODUCT_BASE_TOOLS["codna"] | feat["triage"]
    assert "run_repository_fix" not in visible  # fix not licensed → not visible
    assert visible <= products.PRODUCT_EDITIONS["codna"]
