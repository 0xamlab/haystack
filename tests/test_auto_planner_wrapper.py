from pathlib import Path

import apps.api_server.services.auto_planner as auto_planner


def test_auto_planner_wrapper_preserves_public_surface() -> None:
    planner = auto_planner.AutoPlanner(data_dir=Path("."), llm_policy="never")

    for method_name in (
        "discover_sources",
        "build_knowledge",
        "resolve_metric",
        "resolve_dimension",
        "find_join_keys",
        "plan",
        "execute_plan",
        "refresh_registry_source",
    ):
        assert callable(getattr(planner, method_name))

    assert planner._cache_version == auto_planner._CACHE_VERSION
    assert planner._mojo_column_rank_mode == auto_planner._MOJO_COLUMN_RANK_MODE
    assert planner._planner_logger is auto_planner.logger
    assert auto_planner.JoinHop.__name__ == "JoinHop"
    assert auto_planner.QueryPlan.__name__ == "QueryPlan"
    assert callable(auto_planner._profile_records)
