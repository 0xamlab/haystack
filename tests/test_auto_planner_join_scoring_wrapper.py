from __future__ import annotations

from types import SimpleNamespace

from apps.api_server.services import auto_planner_join_paths, auto_planner_join_scoring


def test_auto_planner_join_paths_reexports_scoring_helpers() -> None:
    assert auto_planner_join_paths._source_aligned_foreign_key_flags(
        "orders",
        "customers",
        "customer_id",
        "id",
    ) == auto_planner_join_scoring._source_aligned_foreign_key_flags(
        "orders",
        "customers",
        "customer_id",
        "id",
    )

    assert auto_planner_join_paths.group_dimension_join_key_multiplier(
        "inventory_type",
        "bookings",
        "inventory",
        "order_id",
        "inventory_id",
    ) == auto_planner_join_scoring.group_dimension_join_key_multiplier(
        "inventory_type",
        "bookings",
        "inventory",
        "order_id",
        "inventory_id",
    )


def test_auto_planner_join_paths_reexports_join_key_semantic_multiplier() -> None:
    planner = SimpleNamespace(
        graph={
            "orders": {
                "customer_id": SimpleNamespace(role="identifier", is_numeric=False),
            },
            "customers": {
                "id": SimpleNamespace(role="identifier", is_numeric=False),
            },
        }
    )

    assert auto_planner_join_paths.join_key_semantic_multiplier(
        planner,
        "orders",
        "customers",
        "customer_id",
        "id",
    ) == auto_planner_join_scoring.join_key_semantic_multiplier(
        planner,
        "orders",
        "customers",
        "customer_id",
        "id",
    )
