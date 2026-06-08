"""Tests for test_auto_planner: refresh_registry.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_helpers import *  # noqa: F401,F403


def test_refresh_registry_source_reuses_incremental_vector_resolver_for_new_source(
    tmp_path,
    monkeypatch,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            "UNIT_PRICE": _planner_node("unit_measure"),
            "EXT_PRICE": _planner_node("derived_measure"),
        }
    }
    planner.profiles = {"POS": {}}
    planner._connections = []
    planner._build_vector_resolver()

    rebuild_calls = {"count": 0}

    def _count_rebuild():
        rebuild_calls["count"] += 1

    monkeypatch.setattr(planner, "_build_vector_resolver", _count_rebuild)
    monkeypatch.setattr(
        auto_planner_module,
        "_registry_source_artifacts_from_meta",
        lambda **_kwargs: auto_planner_module._CachedRegistrySourceArtifacts(
            nodes={
                "UNIT_COST": _planner_node("unit_measure"),
                "EXT_COST": _planner_node("derived_measure"),
            },
            profile={},
            query_hints=[],
        ),
    )

    planner.refresh_registry_source(
        org_id="org-1",
        source_id="src-backlog",
        source_name="BACKLOG",
        schema_meta={},
        source_schema_revision="schema-rev-backlog",
        parquet_path=None,
        new_connections=[],
    )

    assert rebuild_calls["count"] == 0
    result = planner._vector_resolver.resolve(
        "extended cost",
        preferred_source="BACKLOG",
        role_hint="derived_measure",
    )
    assert result is not None
    assert result.source == "BACKLOG"
    assert result.column == "EXT_COST"


def test_refresh_registry_source_defers_vector_resolver_for_large_graph(
    tmp_path,
    monkeypatch,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            f"COL_{index:04d}": _planner_node(
                "derived_measure" if index % 2 == 0 else "unit_measure"
            )
            for index in range(1_600)
        }
    }
    planner.profiles = {"POS": {}}
    planner._vector_resolver = object()
    planner._vector_resolver_dirty = False

    append_calls = {"count": 0}
    rebuild_calls = {"count": 0}

    def _unexpected_append(_source_name: str) -> bool:
        append_calls["count"] += 1
        return True

    def _unexpected_rebuild() -> None:
        rebuild_calls["count"] += 1

    monkeypatch.setattr(planner, "_append_vector_resolver_source", _unexpected_append)
    monkeypatch.setattr(planner, "_build_vector_resolver", _unexpected_rebuild)
    monkeypatch.setattr(
        auto_planner_module,
        "_registry_source_artifacts_from_meta",
        lambda **_kwargs: auto_planner_module._CachedRegistrySourceArtifacts(
            nodes={
                "UNIT_COST": _planner_node("unit_measure"),
                "EXT_COST": _planner_node("derived_measure"),
            },
            profile={},
            query_hints=[],
        ),
    )

    planner.refresh_registry_source(
        org_id="org-1",
        source_id="src-backlog",
        source_name="BACKLOG",
        schema_meta={},
        source_schema_revision="schema-rev-backlog",
        parquet_path=None,
        new_connections=[],
    )

    assert append_calls["count"] == 0
    assert rebuild_calls["count"] == 0
    assert planner._vector_resolver_dirty is True


def test_refresh_registry_source_invalidates_adaptive_context_until_lazy_rebuild(
    tmp_path,
    monkeypatch,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            "UNIT_PRICE": _planner_node("unit_measure"),
            "EXT_PRICE": _planner_node("derived_measure"),
        }
    }
    planner.profiles = {
        "POS": {
            "EXT_PRICE": {
                "fill_rate": 1.0,
                "unique_count": 12,
                "total_count": 12,
                "strings": [f"P{i}" for i in range(4)],
            }
        }
    }
    planner._adaptive_source_context = {
        "POS": auto_planner_module.AdaptiveSourceContext(
            join_distinctiveness=((1.0, 12),),
            column_distinctiveness=((1.0, 12),),
        )
    }

    monkeypatch.setattr(
        auto_planner_module,
        "_registry_source_artifacts_from_meta",
        lambda **_kwargs: auto_planner_module._CachedRegistrySourceArtifacts(
            nodes={"EXT_COST": _planner_node("derived_measure")},
            profile={
                "EXT_COST": {
                    "fill_rate": 1.0,
                    "unique_count": 8,
                    "total_count": 8,
                    "strings": [f"C{i}" for i in range(4)],
                }
            },
            query_hints=[],
        ),
    )
    monkeypatch.setattr(planner, "_build_vector_resolver", lambda: None)

    planner.refresh_registry_source(
        org_id="org-1",
        source_id="src-backlog",
        source_name="BACKLOG",
        schema_meta={},
        source_schema_revision="schema-rev-backlog",
        parquet_path=None,
        new_connections=[],
    )

    assert "BACKLOG" not in planner._adaptive_source_context

    rebuilt = planner._source_distinctiveness_distribution("BACKLOG", join_only=False)

    assert rebuilt
    assert "BACKLOG" in planner._adaptive_source_context


def test_refresh_registry_source_updates_only_affected_join_cache_keys(
    tmp_path,
    monkeypatch,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "Orders": {"order_id": _planner_node("identifier")},
        "POS": {"sku": _planner_node("identifier")},
    }
    planner.profiles = {"Orders": {}, "POS": {}}

    old_source_connection = {
        "source_a": "src-orders",
        "source_a_name": "Orders",
        "col_a": "customer_id",
        "source_b": "src-customers",
        "source_b_name": "Customers",
        "col_b": "id",
        "confidence": 0.91,
        "overlap": 0.84,
        "cardinality": "many_to_one",
    }
    unrelated_connection = {
        "source_a": "src-pos",
        "source_a_name": "POS",
        "col_a": "sku",
        "source_b": "src-products",
        "source_b_name": "Products",
        "col_b": "sku",
        "confidence": 0.88,
        "overlap": 0.77,
        "cardinality": "many_to_one",
    }
    planner._connections = [old_source_connection, unrelated_connection]

    preserved_registry_cache = [
        {
            "field_a": "sku",
            "source_a": "POS",
            "field_b": "sku",
            "source_b": "Products",
            "confidence": 0.88,
            "overlap": 0.77,
            "cardinality": "many_to_one",
        }
    ]
    preserved_dynamic_cache = [
        {
            "field_a": "vendor_name",
            "source_a": "BACKLOG",
            "field_b": "vendor_name",
            "source_b": "Vendors",
            "confidence": 0.67,
            "overlap": 0.55,
            "cardinality": "many_to_many",
        }
    ]
    planner._join_cache = {
        ("Customers", "Orders"): [
            {
                "field_a": "customer_id",
                "source_a": "Orders",
                "field_b": "id",
                "source_b": "Customers",
                "confidence": 0.91,
                "overlap": 0.84,
                "cardinality": "many_to_one",
            }
        ],
        ("POS", "Products"): preserved_registry_cache,
        ("BACKLOG", "Vendors"): preserved_dynamic_cache,
        ("Orders", "Returns"): [
            {
                "field_a": "order_id",
                "source_a": "Orders",
                "field_b": "order_id",
                "source_b": "Returns",
                "confidence": 0.51,
                "overlap": 0.44,
                "cardinality": "many_to_many",
            }
        ],
    }

    monkeypatch.setattr(
        auto_planner_module,
        "_registry_source_artifacts_from_meta",
        lambda **_kwargs: auto_planner_module._CachedRegistrySourceArtifacts(
            nodes={"account_id": _planner_node("identifier")},
            profile={},
            query_hints=[],
        ),
    )
    monkeypatch.setattr(planner, "_build_vector_resolver", lambda: None)

    new_connections = [
        {
            "source_a": "src-orders",
            "source_a_name": "Orders",
            "col_a": "account_id",
            "source_b": "src-accounts",
            "source_b_name": "Accounts",
            "col_b": "id",
            "confidence": 0.95,
            "overlap": 0.89,
            "cardinality": "many_to_one",
        }
    ]

    planner.refresh_registry_source(
        org_id="org-1",
        source_id="src-orders",
        source_name="Orders",
        schema_meta={},
        source_schema_revision="schema-rev-orders",
        parquet_path=None,
        new_connections=new_connections,
    )

    assert planner._connections == [unrelated_connection, new_connections[0]]
    assert planner._join_cache[("POS", "Products")] is preserved_registry_cache
    assert planner._join_cache[("BACKLOG", "Vendors")] is preserved_dynamic_cache
    assert ("Customers", "Orders") not in planner._join_cache
    assert ("Orders", "Returns") not in planner._join_cache
    assert planner._join_cache[("Accounts", "Orders")] == [
        {
            "field_a": "account_id",
            "source_a": "Orders",
            "field_b": "id",
            "source_b": "Accounts",
            "confidence": 0.95,
            "overlap": 0.89,
            "cardinality": "many_to_one",
        }
    ]


